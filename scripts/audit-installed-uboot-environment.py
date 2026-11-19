#!/usr/bin/env python3
"""Read-only audit: installed A733 U-Boot env strings, partition hypothesis.

Reads only an extracted 32 MiB firmware prefix (not a mounted/running target).
Does NOT modify any image, SD card, U-Boot configuration, or env file.
No claim of xrefs or compiled env settings from simple string proximity.
"""
import argparse
import hashlib
from pathlib import Path
import re
import struct

DEFAULT = Path("/root/opi3w-m2-work/uboot-firmware-audit/boot-region.bin")
PATTERNS = [
    rb"U-Boot 2018\.07", rb"uboot\.env", rb"drm_debug",
    rb"sunxi_show_logo", rb"Loading Environment from",
    rb"Saving Environment to", rb"Unable to use",
    rb"Unable to read", rb"using default environment",
    rb"load-environment", rb"mmc[0-9]?", rb"ext4",
    rb"(^|[^A-Za-z])0:[012](?![0-9])",
]
PRINTABLE = re.compile(rb"[\x20-\x7e]{4,}")
def ascii_strings(data):
    return [(m.start(),m.group().decode("ascii","replace")) for m in PRINTABLE.finditer(data)]
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, default=DEFAULT, help="Previously extracted 32 MiB firmware prefix")
    parser.add_argument("--report", type=Path, default=Path("/root/opi3w-m2-work/uboot-firmware-audit/environment-evidence.txt"))
    a=parser.parse_args()
    data=a.bin.read_bytes()
    if len(data)!=33554432:
        raise SystemExit("STOP: expected exact 32 MiB U-Boot/firmware prefix")
    strings=ascii_strings(data)
    marks={}
    for off,val in strings:
        if any(re.search(p,val.encode(),re.I) for p in PATTERNS):
            marks[off]=val
    firmware=[(o,s) for o,s in strings if "U-Boot 2018.07" in s]
    if not firmware:
        raise SystemExit("STOP: expected installed U-Boot 2018.07 signature absent")
    output=[
        "Installed Allwinner A733 U-Boot environment evidence (READ ONLY)",
        f"Input: {a.bin}",
        f"Size: {len(data)} bytes",
        f"SHA256: {hashlib.sha256(data).hexdigest()}",
        "Scope: printable strings ONLY, not disassembly or proven run-time device selection.",
        "",
        "== Identifier ==",
        *[f"0x{o:08x}: {s}" for o,s in firmware],
        "",
        "== Environment / DRM relevant strings ==",
    ]
    for off,val in sorted(marks.items()):
        if any(k in val.lower() for k in
               ("uboot.env","drm_debug","sunxi_show_logo","loading environment",
                "saving environment","unable to","load-environment",
                "default environment")):
            output.append(f"0x{off:08x}: {val[:220]}")
    envrefs=[off for off,val in strings if val=="uboot.env"]
    output.append("\n== Strings within +/-4096 bytes of each uboot.env occurrence ==")
    for off in envrefs:
        output.append(f"\nNear U-Boot env filename at 0x{off:08x}:")
        for o,v in strings:
            if abs(o-off)<=4096 and any(
                x in v.lower() for x in
                ("mmc","ext4","env","partition","0:1","0:2","file","boot","read","load")):
                output.append(f"0x{o:08x} delta={o-off:+6d}: {v[:200]}")
    output += [
        "\n== Discriminators ==",
        "Found 'uboot.env' alone proves a compiled string, NOT env file location.",
        "Nearby 'mmc' or '0:1' is not a reliable code cross-reference.",
        "The vendor 4.12 GiB image has one ext4 partition at LBA 65536;",
        "the diagnostic image has FAT partition 2 at 65536 and ext4 partition 1 at 196608.",
        "Neither vendor image nor test baseline was observed to import uboot.env.",
        "A valid CRC in a filesystem file does NOT establish bootloader access.",
        "Do not use saveenv, raw mmc writes, fw_setenv, or make boot-firmware changes.",
        "For definitive compiled device/path, disassemble actual U-Boot ELF/binary",
        "or obtain its precise source build .config, rather than infer from strings.",
    ]
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text("\n".join(output)+"\n")
    print("\n".join(output))
    print("\nReport:",a.report)
if __name__=="__main__":
    main()
