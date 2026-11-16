#!/usr/bin/env python3
"""Read-only A733 Linux 6.18 versus Linux 7.3 critical-clock audit.

Runs on the operator's WSL host against the ACTUAL hybrid 0.2.7 sources.
Does not build, modify source, access devices, mount disks or flash images.
Returns JSON and Markdown to a new output directory, failing on overwrite.
The 7.3 rules are comparison questions, not instructions to flip registers.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

CHECKS = (
    ("CPUS_AHB", "0x5c0", 28, "6008",
     "Access path to CPUS power controller/PSCI; may need a retained gate"),
    ("MSI_LITE0_BUS", "0x594", 0, "6009",
     "MSI-Lite0 bus interconnect gate"),
    ("MSI_LITE1_BUS", "0x59c", 0, "6009",
     "MSI-Lite1 bus interconnect gate"),
    ("MSI_LITE2_BUS", "0x5a4", 0, "6009",
     "MSI-Lite2 bus interconnect gate"),
    ("MSI_LITE0_AHB", "0x5c0", 16, "6009",
     "AHB route into MSI-Lite0"),
    ("MSI_LITE0_MBUS", "0x5e0", 29, "6009",
     "MBUS route into MSI-Lite0"),
    ("MSI_LITE2_MBUS", "0x5e0", 31, "6009",
     "MBUS route into MSI-Lite2"),
    ("USB_AHB", "0x5c0", 9, "6010",
     "USB bus-fabric path"),
    ("DISPLAY_AHB", "0x5c0", 5, "6022",
     "Display-engine AHB path"),
    ("DISPLAY_MBUS", "0x5e0", 11, "6022",
     "Display-engine MBUS path"),
)
CONFIGS = (
    "ARM64", "ARCH_SUNXI", "AW_BSP", "AW_SUN60IW2_CCU",
    "AW_PINCTRL_SUN60IW2", "AW_PINCTRL_SUN60IW2_R",
    "AW_TWI", "AW_DMA", "AW_MMC", "MMC_SUNXI",
    "AW_MFD_AXP2101", "AW_MFD_AXP2101_I2C",
    "AW_REGULATOR_AXP2101", "AW_UART_NG",
    "LEDS_CLASS", "LEDS_GPIO", "GPIOLIB", "OF_GPIO",
    "BLK_DEV_INITRD", "RD_GZIP", "DEVTMPFS", "DEVTMPFS_MOUNT",
    "CLK_IGNORE_UNUSED", "SERIAL_EARLYCON",
)
TERMS = re.compile(
    r"0x(?:5c0|5e0|594|59c|5a4)\b|"
    r"(?:ahb[_-]?cpus|msi[_-]?lite|ahb[_-]?usb[_-]?sys|mbus[_-]?desys)|"
    r"CLK_IS_CRITICAL|clk_disable_unused|"
    r"(?:critical|ignore_unused|clk_ignore_unused)",
    re.IGNORECASE,
)

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def parse_config(path):
    table = {}
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            k, v = line.split("=", 1)
            table[k[7:]] = v
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            table[line[len("# CONFIG_"):-len(" is not set")]] = "n"
    return {k: table.get(k, "UNKNOWN") for k in CONFIGS}

def excerpt_sources(root, max_files):
    hits, scanned = [], 0
    # Never follow links outside this BSP source subtree. Limit to driver text
    # and 500 KiB/file to keep the audit bounded and human-reviewable.
    for folder in (root / "bsp" / "drivers" / "clk",
                   root / "bsp" / "drivers" / "pinctrl",
                   root / "bsp" / "drivers" / "clock",
                   root / "bsp" / "drivers" / "ccu",
                   root / "drivers" / "clk" / "sunxi-ng"):
        if not folder.is_dir():
            continue
        for p in sorted(folder.rglob("*")):
            if not p.is_file() or p.is_symlink() or p.suffix not in (".c", ".h", ".dtsi", ".dts"):
                continue
            scanned += 1
            if scanned > max_files:
                return hits, scanned, True
            if p.stat().st_size > 512 * 1024:
                continue
            lines = p.read_text(errors="replace").splitlines()
            matching = [i for i, line in enumerate(lines) if TERMS.search(line)]
            for i in matching:
                hits.append({
                    "path": str(p.relative_to(root)),
                    "line": i + 1,
                    "context": "\n".join(
                        f"{j+1}: {lines[j]}"
                        for j in range(max(0, i-2), min(len(lines), i+3))
                    ),
                })
    return hits, scanned, False

def dt_info(dtb):
    if not dtb:
        return {}
    if not dtb.is_file():
        return {"error": f"Missing DTB {dtb}"}
    proc = subprocess.run(
        ["dtc", "-I", "dtb", "-O", "dts", str(dtb)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        return {"error": proc.stderr[-2000:]}
    source = proc.stdout
    # Keys allow manual verification without claiming a mapped phandle.
    found = {
        "sha256": sha256(dtb),
        "size": dtb.stat().st_size,
        "has_gpio_leds": 'compatible = "gpio-leds"' in source,
        "has_status_led": 'label = "status_led"' in source,
        "has_arm_vendor_root_compatible": '"arm,sun60iw2p1"' in source,
        "has_a733_root_compatible": '"allwinner,sun60i-a733"' in source,
        "has_power_domain_binding": "power-domains =" in source,
    }
    lines = source.splitlines()
    candidates = [i for i, ln in enumerate(lines)
                  if re.search(r'led-0|status_led|reserved-memory|psci \{|clock-controller|pinctrl@', ln)]
    found["interesting_dts_excerpts"] = [
        {"line": i+1, "context": "\n".join(lines[max(0, i-2):i+7])}
        for i in candidates[:35]
    ]
    return found

def arm64_image_info(image):
    if not image:
        return {}
    if not image.is_file():
        return {"error": f"Missing Image {image}"}
    import struct
    with image.open("rb") as f:
        b = f.read(64)
    if len(b) < 64:
        return {"error": "Image shorter than 64-byte ARM64 header"}
    text_offset, image_size, flags = struct.unpack_from("<QQQ", b, 8)
    magic = b[56:60]
    return {
        "size": image.stat().st_size,
        "sha256": sha256(image),
        "arm64_magic": magic.hex(),
        "arm64_magic_valid": magic == b"ARM\x64",
        "text_offset": hex(text_offset),
        "header_image_size": image_size,
        "flags": hex(flags),
        "kernel_start_assumed_only": "0x41000000",
        "header_image_end_assuming_0x41000000":
            hex(0x41000000 + (image_size or image.stat().st_size)),
        "warning": "Only static bounds. U-Boot runtime relocation is unobserved.",
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path,
        default=Path("/root/opi3w-hybrid-build-0.2.7"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-files", type=int, default=20000)
    args = parser.parse_args()
    root = args.build.resolve()
    conf = root / "build" / ".config"
    src = root / "linux"
    if not conf.is_file() or not (src / "bsp").is_dir():
        parser.error("Missing exact .config or hybrid bsp/ source under --build")
    out = args.output.resolve()
    if out.exists():
        parser.error("--output must be a NEW directory; refusing overwrite")
    hits, scanned, limited = excerpt_sources(src, args.max_files)
    image = root / "stage" / "boot" / "Image"
    dtb = root / "stage" / "boot" / "sun60i-a733-orangepi-zero3w.dtb"
    report = {
        "schema": 1, "status": "OFFLINE_READ_ONLY_REVIEW_NOT_HARDWARE_PASS",
        "source_root": str(src),
        "config_path": str(conf), "config_sha256": sha256(conf),
        "config": parse_config(conf),
        "source_files_scanned": scanned, "scan_truncated": limited,
        "references": [
            {"name": name, "offset": off, "bit": bit, "patch": patch,
             "reference_meaning": why, "our_equivalence": "UNDETERMINED"}
            for name, off, bit, patch, why in CHECKS
        ],
        "hits": hits,
        "image": arm64_image_info(image),
        "dtb": dt_info(dtb),
        "interpretation": [
            "A name/offset match does not prove a clock is enabled or disabled.",
            "No hit does not prove a missing feature; vendor CCU may use different names.",
            "Newer upstream A733 register descriptions must not be automatically patched into vendor BSP.",
            "Existing original 0.2.7 artifacts remain unchanged.",
            "No flashing, kernel rebuild or physical hardware interaction performed."
        ],
    }
    out.mkdir(parents=True, exist_ok=False)
    (out / "clock-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    md = [
        "# A733 clock source audit, Linux 6.18.19 hybrid 0.2.7",
        "", f"Source: `{src}`",
        f"Configuration SHA256: `{report['config_sha256']}`",
        f"Source files inspected: {scanned} (truncated={limited})",
        "", "## Effective kernel configuration", "",
        "| Symbol | Value |", "| --- | --- |",
    ]
    md += [f"| `CONFIG_{k}` | `{v}` |" for k, v in report["config"].items()]
    md += ["", "## Linux 7.3 clock checks to reconcile", "",
           "| Clock path | Register | Bit | Patch | Interpretation |",
           "| --- | --- | --- | --- | --- |"]
    md += [f"| {name} | {off} | {bit} | {patch} | UNDETERMINED |"
           for name, off, bit, patch, _ in CHECKS]
    md += ["", "## Candidate driver source excerpts", ""]
    for hit in hits[:200]:
        md += [f"### `{hit['path']}:{hit['line']}`",
               "", "~~~c", hit["context"], "~~~", ""]
    if len(hits) > 200:
        md.append(f"Additional {len(hits) - 200} excerpts in clock-audit.json.")
    md += ["", "## ARM64 Image", "", "~~~json",
           json.dumps(report["image"], indent=2), "~~~",
           "", "## Compiled DTB", "", "~~~json",
           json.dumps({k:v for k,v in report["dtb"].items()
                       if k != "interesting_dts_excerpts"}, indent=2),
           "~~~", "", "**Offline evidence only. No driver fix is approved by this report.**"]
    (out / "clock-audit.md").write_text("\n".join(md) + "\n")
    print("OFFLINE_READ_ONLY_REVIEW_NOT_HARDWARE_PASS")
    print("Files:", out / "clock-audit.json", out / "clock-audit.md")
    print("Scanned:", scanned, "hits:", len(hits), "truncated:", limited)

if __name__ == "__main__":
    main()
