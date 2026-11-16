#!/usr/bin/env python3
"""Create HBI-PID1 from the proven HBI-027 image, changing ONLY its initramfs.

Requires root on Linux/WSL with read-write ext4 loop mounting. Fails closed if
mounted ext4 is unavailable. Never edits source image or any physical SD card.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import importlib
import sys

SOURCE_SHA = "6604ba2427c918c893880fcb8f44b8733f1c3e74b5acf91454f77c62e55c88f5"
SOURCE_INITRD_SHA = "d647e0ce4a0c07408ad46a230d9402b4782936b86f5c22e0992e2587bf3ec9fd"
FILE_HASHES = {
    "boot/boot.scr": "ad96554b6d5d7ec09e7bc09bce3c899b0e2dc16a267a1979902efea0a8631135",
    "boot/orangepiEnv.txt": "59c00b3ac7c4d5964ee7b3138a61060ab4d48d235a132f9b334444d308fcddab",
    "boot/mainline/stock-vendor-stage2.scr": "50a01b89be14e44e0f941766bed92aeffce2bd13765bd6b7e4cf59500334d328",
    "boot/mainline/hybrid-0.2.7-vbi/Image": "e4b2eff08dfc7e2553cf498def6658515f5f2f1e5e8066d0fcc60a73742069c7",
    "boot/mainline/hybrid-0.2.7-vbi/sun60i-a733-orangepi-zero3w.dtb": "5c9cd102215183cc56150aab2ce331216bea26d80741cdfc1fb0d95f5818e7b9",
}
INITRD = "boot/mainline/hybrid-0.2.7-vbi/initrd.img-6.18.19-opi3w-hybrid-0.2.7"
FIRMWARE_RESERVED_BYTES = 32 * 1024 * 1024
# Pinned upstream boot normalizer, not a reimplementation.
BOOT_ALLOCATOR_SHA = '1e8027393d07c5fc56955403c20df238dbe1b3f4'

def run(*argv, check=True):
    return subprocess.run(argv, check=check, text=True, capture_output=True)

def sha(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as src:
        remaining = limit
        while True:
            size = 4 * 1024 * 1024 if remaining is None else min(4 * 1024 * 1024, remaining)
            if not size:
                break
            b = src.read(size)
            if not b:
                break
            h.update(b)
            if remaining is not None:
                remaining -= len(b)
        if remaining not in (None, 0):
            raise ValueError("image shorter than firmware-prefix limit")
    return h.hexdigest()

def require_hash(path, expected):
    found = sha(path)
    if found != expected:
        raise RuntimeError(f"HASH FAIL {path}: expected {expected}, observed {found}")

def verify(root, initrd_sha):
    for name, digest in FILE_HASHES.items():
        require_hash(root / name, digest)
    require_hash(root / INITRD, initrd_sha)
    if (root / INITRD).is_symlink():
        raise RuntimeError("initrd must be a regular file, not a symlink")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--probe", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--wbuild-scripts", type=Path, required=True,
                    help="directory with pinned opi-3w-wbuild scripts/boot_allocation.py")
    args = ap.parse_args()
    source, probe, out = (p.resolve() for p in (args.source, args.probe, args.output))
    if os.geteuid() != 0:
        ap.error("must run as root")
    if source == out or not source.is_file() or not probe.is_file() or out.exists():
        ap.error("source and probe must exist, output must be new and distinct")
    scripts = args.wbuild_scripts.resolve()
    require_hash(scripts / "boot_allocation.py", BOOT_ALLOCATOR_SHA)
    sys.path.insert(0, str(scripts))
    allocator = importlib.import_module("boot_allocation")
    require_hash(source, SOURCE_SHA)
    # Pin the exact known full donor, then independently require the entire
    # reserved 32 MiB to remain byte-for-byte identical after image assembly.
    # Historical 'bootloader_reserved_region_sha256' was not documented as a
    # SHA256 over raw bytes [0, 32 MiB), so do not equate those values.
    source_prefix_sha = sha(source, FIRMWARE_RESERVED_BYTES)
    run("gzip", "-t", str(probe))
    listing = run("bash", "-o", "pipefail", "-c",
                  'gzip -dc "$1" | cpio -it --quiet', "archive", str(probe)).stdout.splitlines()
    if "init" not in listing and "./init" not in listing:
        raise RuntimeError("probe archive has no /init")
    layout = json.loads(run("sfdisk", "--json", str(source)).stdout)["partitiontable"]
    parts = layout.get("partitions", [])
    if len(parts) != 1 or int(layout.get("sectorsize", 512)) != 512:
        raise RuntimeError("HBI stock geometry mismatch")
    part = parts[0]
    if int(part["start"]) != 65536 or int(part["size"]) != 8577024:
        raise RuntimeError("HBI partition start/size mismatch")
    out.parent.mkdir(parents=True, exist_ok=True)
    # New output file only. Copy source before touching any filesystem.
    with open(source, "rb") as src, open(out, "xb") as dst:
        shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
    loop = None
    mounted = False
    complete = False
    try:
        loop = run("losetup", "--find", "--show", "--offset", str(65536 * 512),
                   "--sizelimit", str(8577024 * 512), str(out)).stdout.strip()
        with tempfile.TemporaryDirectory(prefix="opi3w-pid1-") as mp:
            root = Path(mp)
            try:
                run("mount", "-t", "ext4", "-o", "rw", loop, str(root))
            except subprocess.CalledProcessError as e:
                raise RuntimeError("RW ext4 loop mounting unavailable; no image was finalized: "
                                   + e.stderr.strip()) from e
            mounted = True
            verify(root, SOURCE_INITRD_SHA)
            dest = root / INITRD
            if not dest.is_file():
                raise RuntimeError("initrd is not a regular file")
            # Write every byte to a fresh regular file. Avoid sparse holes and
            # preserve ownership, mode and final pathname.
            stage = dest.with_name(dest.name + ".pid1-new")
            if stage.exists():
                raise RuntimeError("unexpected staging filename in original image")
            with open(probe, "rb") as src, open(stage, "xb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
                dst.flush()
                os.fsync(dst.fileno())
            st = dest.stat()
            os.chmod(stage, st.st_mode & 0o7777)
            os.chown(stage, st.st_uid, st.st_gid)
            os.replace(stage, dest)
            probe_sha = sha(probe)
            verify(root, probe_sha)
            # Proven mounted-ext4 normalization from opi-3w-wbuild.
            # It snapshots all /boot metadata, preserves symlinks and hardlinks,
            # preallocates/re-writes full bytes including zeros, checks SEEK_HOLE,
            # and verifies the complete snapshot again.
            normalized = allocator.dense_boot(root)
            verify(root, probe_sha)
            if not normalized:
                raise RuntimeError("No regular boot files normalized")
            audit = {
                "schema": 1,
                "allocator_sha256": BOOT_ALLOCATOR_SHA,
                "all_regular_boot_files_dense": True,
                "files": normalized,
                "probe_sha256": probe_sha,
                "status": "OFFLINE_NORMALIZATION_ONLY"
            }
            # Keep audit outside the image, so nothing under /boot changes
            # after the normalizer and before final filesystem verification.
            allocation_audit = Path(str(out) + ".boot-allocation.json")
            allocation_audit.write_text(json.dumps(audit, indent=2) + "\n")
            os.sync()
            run("umount", str(root))
            mounted = False
        run("e2fsck", "-fn", loop)
        complete = True
    finally:
        if mounted:
            run("umount", str(root), check=False)
        if loop:
            run("losetup", "-d", loop, check=False)
        if not complete:
            # Never leave an incomplete copy that looks like a test image.
            out.unlink(missing_ok=True)
    output_prefix_sha = sha(out, FIRMWARE_RESERVED_BYTES)
    if output_prefix_sha != source_prefix_sha:
        out.unlink(missing_ok=True)
        raise RuntimeError("firmware reserved prefix changed unexpectedly")
    record = {
        "status": "ASSEMBLED_OFFLINE_NOT_HARDWARE_TESTED",
        "parent_image": str(source),
        "parent_sha256": SOURCE_SHA,
        "image": str(out),
        "image_sha256": sha(out),
        "firmware_reserved_bytes": FIRMWARE_RESERVED_BYTES,
        "firmware_prefix_sha256": output_prefix_sha,
        "firmware_prefix_source_sha256": source_prefix_sha,
        "changed_file": "/" + INITRD,
        "original_initrd_sha256": SOURCE_INITRD_SHA,
        "probe_initrd_sha256": sha(probe),
        "retained_file_sha256": FILE_HASHES,
        "partition_start": 65536,
        "partition_sectors": 8577024,
        "boot_allocation_audit": str(allocation_audit),
        "allocator_sha256": BOOT_ALLOCATOR_SHA,
        "warning": "Output needs independent read-only filesystem audit and flash hardware tests; missing UART marker inconclusive",
    }
    manifest = Path(str(out) + ".audit.json")
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    Path(str(out) + ".sha256").write_text(record["image_sha256"] + "  " + out.name + "\n")
    print("ASSEMBLED_OFFLINE_NOT_HARDWARE_TESTED:", out)
    print("SHA256:", record["image_sha256"])

if __name__ == "__main__":
    main()
