#!/usr/bin/env python3
"""Read-only static handoff audit for A733 vendor U-Boot bootm/booti variants.

Input is a local boot script file (.cmd/.scr), ARM64 raw Image, DTB and
initramfs. This does NOT model unobserved relocation, BL31 or memory runtime.
Never edits an input or accesses a block device.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

EXPECTED = {"kernel": 0x41000000, "fdt": 0x44000000,
            "ramdisk": 0x45000000, "stage2": 0x46000000}
# Static handoff screening is conservative; it is not a U-Boot simulator.
ALARM = re.compile(r"\b(bootm|booti|load|ext4load|fdt|env import|ramdisk|initrd|kernel_addr_r|fdt_addr_r)\b")
ADDR = re.compile(r"\b0x[0-9a-fA-F]{7,8}\b")
BOOTI = re.compile(r"(?m)^\s*booti\s+(.+)$")
SOURCE_HASHES = {
    "HBI_027_Image": "e4b2eff08dfc7e2553cf498def6658515f5f2f1e5e8066d0fcc60a73742069c7",
    "HBI_027_DTB": "5c9cd102215183cc56150aab2ce331216bea26d80741cdfc1fb0d95f5818e7b9",
}

def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()

def read_boot_script(p):
    raw = p.read_bytes()
    result = {"sha256": sha256(p), "size": len(raw), "format": "TEXT"}
    if len(raw) > 64 and raw[:4] == b"\x27\x05\x19\x56":
        # Standard 64-byte U-Boot legacy script wrapper, big-endian header.
        payload_size = struct.unpack_from(">I", raw, 12)[0]
        if len(raw) < 64 + payload_size:
            raise ValueError("U-Boot script claims more payload than the file contains")
        raw = raw[64:64+payload_size]
        result.update({"format": "UBOOT_LEGACY", "payload_size": payload_size})
    text = raw.decode("utf-8", errors="replace").replace("\x00", "")
    # A legacy script contains only source text plus optional trailing null.
    lines = text.splitlines()
    result["important_lines"] = [
        {"line": n, "text": s.strip()}
        for n, s in enumerate(lines, 1) if ALARM.search(s)
    ][:150]
    result["booti_lines"] = BOOTI.findall(text)
    result["literal_addresses"] = sorted(set(ADDR.findall(text)))
    result["contains_fdt_addr"] = "fdt addr " in text
    result["contains_fdt_resize"] = "fdt resize " in text
    result["contains_env_import"] = "env import " in text
    result["contains_bootm"] = bool(re.search(r"(?m)^\s*bootm\b", text))
    result["contains_booti"] = bool(re.search(r"(?m)^\s*booti\b", text))
    result["inconclusive"] = [
        "Environment variable expansion and conditionals are not executed.",
        "Memory relocation and BL31 overwrite cannot be inferred from this script alone.",
        "A single stored script may not be the script actually executed by the flashed SD card.",
    ]
    return result

def image_header(p):
    h = p.open("rb").read(64)
    if len(h) < 64:
        raise ValueError("ARM64 Image shorter than 64 bytes")
    off, size, flags = struct.unpack_from("<QQQ", h, 8)
    return {
        "magic": h[56:60].hex(),
        "valid_arm64_magic": h[56:60] == b"ARM\x64",
        "text_offset": hex(off),
        "image_size": size,
        "flags": hex(flags),
        "actual_size": p.stat().st_size,
        "sha256": sha256(p),
        "sha256_matches_pinned_HBI_027": sha256(p) == SOURCE_HASHES["HBI_027_Image"],
    }

def legacy_initrd_info(p):
    b = p.open("rb").read(128)
    result = {"sha256": sha256(p), "actual_size": p.stat().st_size}
    if len(b) >= 64 and b[:4] == b"\x27\x05\x19\x56":
        size = struct.unpack_from(">I", b, 12)[0]
        result.update({
            "type": "legacy_uInitrd",
            "legacy_data_size": size,
            "payload_gzip_magic_present": b[64:66] == b"\x1f\x8b",
            "within_16MiB_safety_envelope":
                size < 16*1024*1024,
        })
    else:
        result.update({
            "type": "raw_gzip" if b[:2] == b"\x1f\x8b" else "OTHER",
            "within_16MiB_safety_envelope":
                p.stat().st_size < 16*1024*1024,
        })
    return result

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--script", required=True, type=Path,
                    help="actual second-stage U-Boot .cmd or .scr")
    ap.add_argument("--image", required=True, type=Path)
    ap.add_argument("--dtb", required=True, type=Path)
    ap.add_argument("--initrd", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    inputs = [args.script, args.image, args.dtb, args.initrd]
    if any(not p.is_file() for p in inputs):
        ap.error("All four input files must exist")
    if args.output.exists():
        ap.error("Output exists, refusing overwrite")
    report = {
        "status": "OFFLINE_STATIC_AUDIT_NOT_KERNEL_BOOT_PROOF",
        "input_files": {k: str(getattr(args,k).resolve())
                        for k in ("script","image","dtb","initrd")},
        "script": read_boot_script(args.script),
        "image": image_header(args.image),
        "dtb": {"sha256": sha256(args.dtb),
                "size": args.dtb.stat().st_size,
                "sha256_matches_pinned_HBI_027":
                    sha256(args.dtb) == SOURCE_HASHES["HBI_027_DTB"]},
        "initrd": legacy_initrd_info(args.initrd),
        "expected_staging_addresses": {
            k: hex(v) for k, v in EXPECTED.items()
        },
        "unverified": [
            "Whether this is the exact script deployed to the flashed card",
            "Values of U-Boot environment variables at execution time",
            "Any runtime kernel/DTB/initramfs/BL31 relocation",
            "Actual entry into the Linux 6.18 kernel",
        ],
    }
    if not report["image"]["valid_arm64_magic"]:
        raise ValueError("Image lacks ARM64 raw header; stopped")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print("OFFLINE_STATIC_AUDIT_NOT_KERNEL_BOOT_PROOF")
    print(args.output)
    print("Image HBI pinned:", report["image"]["sha256_matches_pinned_HBI_027"])
    print("DTB HBI pinned:", report["dtb"]["sha256_matches_pinned_HBI_027"])
    print("Initrd:", report["initrd"]["type"])
    print("booti lines:", report["script"]["booti_lines"])

if __name__ == "__main__":
    main()
