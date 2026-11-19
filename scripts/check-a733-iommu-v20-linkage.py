#!/usr/bin/env python3
"""Isolated A733 IOMMU v20 relocatable linkage diagnostic.

Validates three compiled AArch64 objects and links them with ld -r.
Unresolved references to core Linux symbols are expected and are reported,
not treated as proof of missing kernel exports. No images or firmware touched.
"""
from __future__ import annotations
import argparse
import hashlib
import pathlib
import re
import shutil
import subprocess
import sys

BASE = pathlib.Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
OBJECTS = ("sunxi-iommu-v2.o", "sunxi-iommu-common.o", "sunxi-iommu-pgtable.o")

def run(cmd):
    p = subprocess.run([str(x) for x in cmd], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--objects", type=pathlib.Path,
                    default=BASE / "iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20")
    ap.add_argument("--out", type=pathlib.Path, default=BASE / "iommu-v20-linkage-stage4")
    ap.add_argument("--prefix", default="aarch64-linux-gnu-")
    args = ap.parse_args()
    if args.out.exists():
        sys.exit("STOP: destination exists, use a new --out")
    sources = [args.objects / name for name in OBJECTS]
    if not all(p.is_file() for p in sources):
        sys.exit("STOP: one or more required object files are missing")
    for binary in ("ld", "readelf", "nm"):
        if not shutil.which(args.prefix + binary):
            sys.exit("STOP: missing " + args.prefix + binary)
    manifest = ["A733 v20 relocatable linkage diagnostic", "No full-kernel linkage or hardware test."]
    for obj in sources:
        rc, header = run([args.prefix + "readelf", "-h", obj])
        if rc or not re.search(r"Machine:\s*AArch64\b", header):
            sys.exit("STOP: invalid AArch64 ELF " + str(obj))
        manifest.append(obj.name + " SHA256 " + sha(obj))

    args.out.mkdir(parents=True)
    linked = args.out / "iommu-v20-combined.o"
    rc, output = run([args.prefix + "ld", "-r", "-o", linked, *sources])
    (args.out / "link.log").write_text(output)
    manifest.append("ld -r exit code: " + str(rc))
    if rc:
        (args.out / "results.txt").write_text("\n".join(manifest) + "\n" + output)
        print("LINK FAIL: " + str(args.out / "results.txt"))
        sys.exit(rc)

    rc, hdr = run([args.prefix + "readelf", "-h", linked])
    if rc or not re.search(r"Machine:\s*AArch64\b", hdr):
        sys.exit("STOP: linked result is not an AArch64 ELF")
    manifest.append("Combined ELF SHA256 " + sha(linked))

    rc, nm_output = run([args.prefix + "nm", "-u", linked])
    (args.out / "undefined-symbols.txt").write_text(nm_output)
    undefined = [line.strip() for line in nm_output.splitlines() if line.strip()]
    manifest.append("Undefined symbols remaining (including expected Linux core references): " +
                    str(len(undefined)))
    manifest.append("Undefined symbol listing: undefined-symbols.txt")
    if rc:
        manifest.append("nm returned code " + str(rc))
    (args.out / "results.txt").write_text("\n".join(manifest) + "\n")
    print("\n".join(manifest))
    print("UPLOAD: " + str(args.out / "results.txt"))
    print("ALSO UPLOAD: " + str(args.out / "undefined-symbols.txt"))
    print("Not a modpost, runnable driver, or safety validation.")

if __name__ == "__main__":
    main()
