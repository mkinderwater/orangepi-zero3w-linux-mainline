#!/usr/bin/env python3
"""Read-only inventory of the *actual* hybrid 6.18 worktree and patch set.

Produces evidence, not an edited kernel. No network or privileged operations.
"""
import argparse
import difflib
import hashlib
import json
import re
import subprocess
from pathlib import Path

SUSPECT = ("sunxi-dis-signal-vol-sw", "mmc-high-capacity-erase-size",
           "power-source", "vmmc-supply", "vqmmc", "arm,sun60iw2p1",
           "allwinner,sun60i-a733", "sd-uhs-", "clk_ignore_unused",
           "mmc-high-capacity-erase-size", "clock-frequency",
           "max-frequency", "status = \"disabled\"")
CAP_RE = re.compile(r"^\s*#define\s+(MMC_CAP2_[A-Za-z0-9_]+)\s+\(1\s*<<\s*(\d+)\)", re.M)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return path.read_text(errors="replace") if path.is_file() else ""
def run(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return dict(rc=result.returncode, output=(result.stdout + result.stderr)[-20000:])
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return dict(rc=-1, output=str(exc))
def snapshot(path):
    return dict(path=str(path), present=path.is_file(), sha256=sha(path) if path.is_file() else None)
def compare(a, b):
    if not a.is_file() or not b.is_file():
        return dict(left=snapshot(a), right=snapshot(b), status="MISSING_REFERENCE")
    if sha(a) == sha(b):
        return dict(left=snapshot(a), right=snapshot(b), status="IDENTICAL")
    al, bl = read(a).splitlines(), read(b).splitlines()
    diff = list(difflib.unified_diff(bl, al, fromfile=str(b), tofile=str(a), lineterm=""))
    return dict(left=snapshot(a), right=snapshot(b), status="DIFFERENT",
                diff_preview="\n".join(diff[:180]), diff_lines=len(diff))
def macros(root):
    vals = {}
    for path in (root / "include/linux/mmc/host.h", root / "bsp/drivers/mmc/sunxi-mmc.h"):
        vals[str(path)] = {name:int(bit) for name,bit in CAP_RE.findall(read(path))}
    return vals
def get_status(root):
    return run("git", "-C", str(root), "status", "--short")
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hybrid", type=Path, default=Path("/root/opi3w-hybrid-build-0.2.7/linux"))
    p.add_argument("--mainline", type=Path, default=Path("/root/opi3w-hybrid-sources-0.1.0/linux"))
    p.add_argument("--vendor", type=Path, default=None,
                   help="optional known vendor 6.6.98 source root")
    p.add_argument("--repo", type=Path, default=Path("/root/orangepi-zero3w-linux-mainline"))
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if not (a.hybrid / "Makefile").is_file():
        p.error("hybrid Linux source missing")
    if not (a.mainline / "Makefile").is_file():
        p.error("mainline reference Linux source missing")
    a.output.mkdir(parents=True, exist_ok=True)
    evidence = dict(schema=1, hybrid=str(a.hybrid), mainline=str(a.mainline),
                    vendor=str(a.vendor) if a.vendor else None,
                    warning="read-only; not hardware-validation or full reproducibility",
                    git=dict(mainline=get_status(a.mainline),
                             hybrid=get_status(a.hybrid), repo=get_status(a.repo)),
                    core={}, mmc={}, patches=[], device_trees=[], configurations={})
    for name in ("Kbuild", "Kconfig", "Makefile"):
        evidence["core"][name] = compare(a.hybrid / name, a.mainline / name)
    srcmmc = a.hybrid / "bsp/drivers/mmc"
    for name in ("sunxi-mmc.c", "sunxi-mmc.h", "sunxi-mmc-v5p3x.c"):
        evidence["mmc"][name] = snapshot(srcmmc / name)
    core = macros(a.hybrid)
    vendor_macros = core[str(srcmmc / "sunxi-mmc.h")]
    modern_macros = core[str(a.hybrid / "include/linux/mmc/host.h")]
    conflicts = []
    for name, bit in vendor_macros.items():
        for new_name, new_bit in modern_macros.items():
            if bit == new_bit and name != new_name:
                conflicts.append(dict(legacy=name, modern=new_name, bit=bit))
    evidence["mmc"]["legacy_macro_collisions"] = conflicts
    mmc_source = read(srcmmc / "sunxi-mmc.c")
    for name in ("HC_ERASE_SZ", "CACHE_CTRL", "PACKED_WR", "PACKED_RD"):
        flag = "MMC_CAP2_" + name
        evidence["mmc"][flag] = dict(occurrences=mmc_source.count(flag),
                                          header=vendor_macros.get(flag))
    evidence["mmc"]["uhs2_callback_in_sunxi_host"] = "uhs2_control" in mmc_source
    evidence["mmc"]["legacy_property_assign"] = (
        'mmc-high-capacity-erase-size' in mmc_source)
    evidence["configurations"]["build_config"] = snapshot(a.hybrid.parent / "build/.config")
    cfg = read(a.hybrid.parent / "build/.config")
    config_names = ("AW_MMC","MMC_SUNXI","AW_TWI","AW_SUN60IW2_CCU",
                    "AW_PINCTRL_SUN60IW2","AW_PINCTRL_SUN60IW2_R",
                    "AW_MFD_AXP2101","AW_REGULATOR_AXP2101",
                    "AW_UART_NG","SERIAL_EARLYCON","DRM")
    for name in config_names:
        evidence["configurations"][name] = next(
            (line for line in cfg.splitlines() if line.startswith("CONFIG_"+name+"=")
             or line.startswith("# CONFIG_"+name+" is not set")), "UNKNOWN")
    dts_root = a.hybrid / "arch/arm64/boot/dts"
    candidates = sorted(set(dts_root.rglob("*zero3w*.dts")) |
                        set(dts_root.rglob("*a733*.dtsi")))
    for path in candidates:
        rel = path.relative_to(a.hybrid)
        text = read(path)
        evidence["device_trees"].append(dict(path=str(rel), sha256=sha(path),
                     counterpart=compare(path, a.mainline / rel),
                     flags=[s for s in SUSPECT if s in text],
                     root_compatibles=[line.strip() for line in text.splitlines()
                                       if "compatible" in line][:15]))
    for path in sorted(a.repo.rglob("*.patch")):
        if ".git" not in path.parts:
            evidence["patches"].append(dict(path=str(path.relative_to(a.repo)),
                                            sha256=sha(path), bytes=path.stat().st_size))
    if a.vendor:
        candidates = sorted((a.vendor / "arch/arm64/boot/dts").rglob("*zero3w*.dts"))
        evidence["vendor_dts"] = [snapshot(path) for path in candidates]
    dest = a.output / "integration-inventory.json"
    dest.write_text(json.dumps(evidence, indent=2) + "\n")
    md = ["# Hybrid Linux 6.18 integration inventory", "",
          "**Read-only source audit, not a boot test.**", "",
          "## Core changes vs pinned 6.18", ""]
    for name, data in evidence["core"].items():
        md.append(f"- {name}: {data['status']}")
    md += ["", "## Vendor MMC macro collisions", ""]
    for c in conflicts:
        md.append(f"- **BIT({c['bit']})**: {c['legacy']} aliases {c['modern']}")
    if not conflicts:
        md.append("- No direct literal (1 << N) collisions found; macros may still be aliases.")
    md += ["", "## MMC usage", ""]
    for name in ("HC_ERASE_SZ","CACHE_CTRL","PACKED_WR","PACKED_RD"):
        v=evidence["mmc"]["MMC_CAP2_"+name]
        md.append(f"- {name}: header bit {v['header']}, source references {v['occurrences']}")
    md += ["", "## DTS source candidates (not compiled DTB)", ""]
    for obj in evidence["device_trees"]:
        md.append(f"- {obj['path']} | upstream: {obj['counterpart']['status']} | flags: {', '.join(obj['flags'])}")
    md += ["", "## Patch files found in this repo", ""]
    for obj in evidence["patches"]:
        md.append(f"- {obj['path']} SHA256 {obj['sha256']}")
    md += ["", "## Caveats", "",
           "- This enumerates repository patch files, not every unpublished WSL edit or applied patch.",
           "- Compare the compiled DTB via fdtget/dtc separately; source strings may not reflect final overlays.",
           "- Review untracked files, .config, build logs and module revisions before declaring complete reproducibility.",
           "- Preserve historic vendor boot artifacts; do not merge obsolete experimental PMIC patches.",
           "- No patches are applied, no device-tree values are modified, and no flash media is touched.", ""]
    (a.output / "integration-inventory.md").write_text("\n".join(md))
    print(f"INVENTORY_WRITTEN: {dest}")
    print(f"CAP2_COLLISIONS: {len(conflicts)}")
    print(f"DTS_CANDIDATES: {len(evidence['device_trees'])}")
    print(f"PATCH_FILES: {len(evidence['patches'])}")
if __name__ == "__main__":
    main()
