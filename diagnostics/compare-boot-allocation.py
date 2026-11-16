#!/usr/bin/env python3
"""Read-only /boot allocation comparison on two existing 1-ext4 HBI images.

Uses the recorded stock geometry and a ro,noload mount. No modifications.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

START = 65536
SECTORS = 8577024

def call(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def inspect(path):
    layout = json.loads(call("sfdisk", "--json", str(path)))["partitiontable"]
    parts = layout["partitions"]
    if len(parts) != 1 or int(layout.get("sectorsize", 512)) != 512 or int(parts[0]["start"]) != START or int(parts[0]["size"]) != SECTORS:
        raise RuntimeError("unexpected partition geometry")
    loop = call("losetup", "--read-only", "--find", "--show", "--offset", str(START*512),
                "--sizelimit", str(SECTORS*512), str(path))
    mounted = False
    try:
        with tempfile.TemporaryDirectory(prefix="opi3w-alloc-ro-") as tmp:
            try:
                call("mount", "-t", "ext4", "-o", "ro,noload", loop, tmp)
                mounted = True
            except subprocess.CalledProcessError as e:
                raise RuntimeError("read-only ext4 mount unavailable: " + e.stderr.strip()) from e
            root = Path(tmp)
            report = {}
            for p in sorted((root/"boot").rglob("*")):
                if p.is_symlink() or not p.is_file():
                    continue
                name = p.relative_to(root).as_posix()
                size = p.stat().st_size
                with p.open("rb") as f:
                    fd = f.fileno()
                    hole = os.lseek(fd, 0, os.SEEK_HOLE) if size else 0
                if hole < size:
                    raise_if = False  # record only; original image can be sparse
                report[name] = {"size": size, "first_hole": hole, "has_hole": hole < size}
            call("umount", tmp)
            mounted = False
        return {"image": str(path), "image_sha256": sha(path), "files": report,
                "sparse_files": sorted(k for k, v in report.items() if v["has_hole"])}
    finally:
        if mounted:
            subprocess.run(["umount", tmp], capture_output=True)
        subprocess.run(["losetup", "-d", loop], capture_output=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True, type=Path)
    ap.add_argument("--normalized", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.original.resolve() == args.normalized.resolve():
        ap.error("require two distinct images")
    if os.geteuid() != 0:
        ap.error("must run as root")
    originals = inspect(args.original.resolve())
    normalized = inspect(args.normalized.resolve())
    allpaths = sorted(set(originals["files"]) | set(normalized["files"]))
    differences = {
        path: {"original": originals["files"].get(path), "normalized": normalized["files"].get(path)}
        for path in allpaths
        if originals["files"].get(path) != normalized["files"].get(path)
    }
    result = {"state": "OFFLINE_ALLOCATION_ONLY", "original": originals,
              "normalized": normalized, "differences": differences}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("Original sparse boot files:", len(originals["sparse_files"]))
    print("Normalized sparse boot files:", len(normalized["sparse_files"]))
    print("Changed allocation profiles:", len(differences))
    print("Allocation audit:", args.output)

if __name__ == "__main__":
    main()
