#!/usr/bin/env python3
"""Construct one isolated legacy-uInitrd booti image from a pinned VBI/HBI donor.

Writes a NEW .img only. Copies the full donor, modifies precisely second-stage
script and initramfs, preserves firmware and original kernel/DTB, then runs
pinned mounted-ext4 /boot normalization. No physical SD writes.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile

VBI_SHA = "7c76d125013df144d238526e396c1c9d5878c2cdf57eaa3ac09f613e32afa63c"
HBI_SHA = "6604ba2427c918c893880fcb8f44b8733f1c3e74b5acf91454f77c62e55c88f5"
ALLOCATOR_SHA = "1e8027393d07c5fc56955403c20df238dbe1b3f4"
FIRST_SHA = "ad96554b6d5d7ec09e7bc09bce3c899b0e2dc16a267a1979902efea0a8631135"
ENV_SHA = "59c00b3ac7c4d5964ee7b3138a61060ab4d48d235a132f9b334444d308fcddab"
STAGE2 = "boot/mainline/stock-vendor-stage2.scr"
# Never use JavaScript substitution in this file. These are U-Boot env tokens.
DOLLAR = "$"
KERNEL = DOLLAR + "{kernel_addr_r}"
RAMDISK = DOLLAR + "{ramdisk_addr_r}"
FDT = DOLLAR + "{fdt_addr_r}"
SIZE = DOLLAR + "{opi3w_vendor_initrd_size}"
OLD = "booti " + KERNEL + " " + RAMDISK + ":" + SIZE + " " + FDT
NEW = "booti " + KERNEL + " " + RAMDISK + " " + FDT
PROFILES = {
    "vendor": {
        "image": VBI_SHA,
        "stage2": "ec7c2338fc654260868af803c60f57ac62148e2fa7cf18d1446efd3ad24",
        "initrd": "boot/mainline/verified-vendor-initrd.gz",
        "initrd_sha": "1ef9e0286d58300563d1724d299ce9762b2da402b1054f420f21025e8bf15168",
        "kernel": "boot/mainline/verified-vendor-Image",
        "kernel_sha": "58c616d26616977d9bc4aef0d362cd3f23ed03fe086c0ad10294e026d097a946",
        "dtb": "boot/dtb/allwinner/sun60i-a733-orangepi-zero3w.dtb",
        "dtb_sha": "d0b9b052c6afcd64d1ac8e41c03b7dca11b007d62b72f0b6fb9b2b042fe78c1d",
    },
    "hybrid": {
        "image": HBI_SHA,
        "stage2": "50a01b89be14e44e0f941766bed92aeffce2bd13765bd6b7e4cf59500334d328",
        "initrd": "boot/mainline/hybrid-0.2.7-vbi/initrd.img-6.18.19-opi3w-hybrid-0.2.7",
        "initrd_sha": "d647e0ce4a0c07408ad46a230d9402b4782936b86f5c22e0992e2587bf3ec9fd",
        "kernel": "boot/mainline/hybrid-0.2.7-vbi/Image",
        "kernel_sha": "e4b2eff08dfc7e2553cf498def6658515f5f2f1e5e8066d0fcc60a73742069c7",
        "dtb": "boot/mainline/hybrid-0.2.7-vbi/sun60i-a733-orangepi-zero3w.dtb",
        "dtb_sha": "5c9cd102215183cc56150aab2ce331216bea26d80741cdfc1fb0d95f5818e7b9",
    },
}
PART_OFFSET = 65536 * 512
PART_SIZE = 8577024 * 512

def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)

def sha(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while limit is None or limit:
            b = f.read(min(4 * 1024 * 1024, limit) if limit is not None else 4 * 1024 * 1024)
            if not b:
                break
            h.update(b)
            if limit is not None:
                limit -= len(b)
    if limit not in (0, None):
        raise RuntimeError("Truncated input")
    return h.hexdigest()

def check(root, name, digest):
    p = root / name
    if not p.is_file() or p.is_symlink() or sha(p) != digest:
        raise RuntimeError("Retained source checksum or type mismatch: " + str(p))

def script_payload(path):
    raw = path.read_bytes()
    if len(raw) < 64 or raw[:4] != bytes.fromhex("27051956"):
        raise RuntimeError("Expected U-Boot legacy script header")
    n = struct.unpack_from(">I", raw, 12)[0]
    if n <= 0 or len(raw) != n + 64:
        raise RuntimeError("Legacy script header length mismatch")
    return raw[64:].rstrip(b"\x00").decode("utf-8")

def validate_source_script(path, cfg):
    if sha(path) != cfg["stage2"]:
        raise RuntimeError("Second-stage source hash changed")
    body = script_payload(path)
    if body.count(OLD) != 1 or NEW in body:
        raise RuntimeError("Unexpected booti invocation")
    if "fdt resize 65536" not in body or "env import -t " not in body:
        raise RuntimeError("Missing proven FDT/environment setup")
    if any(line.lstrip().startswith("bootm ") for line in body.splitlines()):
        raise RuntimeError("Unexpected fallback bootm")
    if body.count("setenv opi3w_vendor_initrd_size " + DOLLAR + "{filesize}") != 1:
        raise RuntimeError("Existing filesize capture missing")
    return body

def validate_new_script(path):
    body = script_payload(path)
    if body.count(NEW) != 1 or OLD in body:
        raise RuntimeError("Legacy booti command not installed correctly")
    if "fdt resize 65536" not in body or "env import -t " not in body:
        raise RuntimeError("Missing retained U-Boot prerequisites")

def inventory(root):
    items = {}
    for dirpath, dirs, files in os.walk(root, followlinks=False):
        directory = Path(dirpath)
        for name in files:
            f = directory / name
            rel = f.relative_to(root).as_posix()
            st = f.lstat()
            if stat.S_ISLNK(st.st_mode):
                items[rel] = ("link", os.readlink(f))
            elif stat.S_ISREG(st.st_mode):
                items[rel] = ("file", sha(f), stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid)
            else:
                raise RuntimeError("Unexpected special file: " + rel)
        for name in dirs:
            f = directory / name
            if f.is_symlink():
                items[f.relative_to(root).as_posix()] = ("link", os.readlink(f))
    return items

def replace_file(dest, source):
    info = dest.stat()
    temporary = dest.with_name(dest.name + ".legacy-new")
    if temporary.exists():
        raise RuntimeError("Staging file already exists")
    try:
        with open(source, "rb") as inp, open(temporary, "xb") as out:
            shutil.copyfileobj(inp, out, 1024*1024)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, stat.S_IMODE(info.st_mode))
        os.chown(temporary, info.st_uid, info.st_gid)
        os.replace(temporary, dest)
    finally:
        temporary.unlink(missing_ok=True)

def verify_ramdisk(wrapper, probe):
    w = wrapper.read_bytes()
    data = probe.read_bytes()
    if w[:4] != bytes.fromhex("27051956") or w[64:] != data:
        raise RuntimeError("uInitrd payload mismatch")
    if struct.unpack_from(">I", w, 12)[0] != len(data):
        raise RuntimeError("uInitrd size mismatch")
    if w[28:32] != bytes((5, 2, 3, 1)):
        raise RuntimeError("uInitrd OS/arch/type/compression must be Linux/ARM/ramdisk/gzip")
    if len(w) >= 16*1024*1024:
        raise RuntimeError("Legacy initrd exceeds conservative limit")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", choices=sorted(PROFILES), required=True)
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--probe", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--wbuild-scripts", required=True, type=Path)
    args = ap.parse_args()
    cfg = PROFILES[args.profile]
    source, probe, dest = (p.resolve() for p in (args.source, args.probe, args.output))
    if os.geteuid() != 0:
        ap.error("Requires root (ext4 loop mount)")
    if not source.is_file() or not probe.is_file() or dest.exists() or dest in (source, probe):
        ap.error("Source and probe must exist; output must be a NEW different path")
    allocator_dir = args.wbuild_scripts.resolve()
    if run("git", "hash-object", str(allocator_dir / "boot_allocation.py")).stdout.strip() != ALLOCATOR_SHA:
        raise RuntimeError("Unpinned boot normalizer")
    sys.path.insert(0, str(allocator_dir))
    dense_boot = importlib.import_module("boot_allocation").dense_boot
    if sha(source) != cfg["image"]:
        raise RuntimeError("Donor image hash mismatch")
    prefix = sha(source, PART_OFFSET)
    run("gzip", "-t", str(probe))
    listing = run("bash", "-o", "pipefail", "-c",
                  'gzip -dc "$1" | cpio -it --quiet', "probe", str(probe)).stdout.splitlines()
    if "init" not in listing and "./init" not in listing:
        raise RuntimeError("No /init in probe")
    geo = json.loads(run("sfdisk", "--json", str(source)).stdout)["partitiontable"]
    parts = geo.get("partitions", [])
    if len(parts) != 1 or int(geo.get("sectorsize",512)) != 512 or \
            int(parts[0]["start"]) != 65536 or int(parts[0]["size"]) != 8577024:
        raise RuntimeError("Unexpected image geometry")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="opi3w-legacy-") as dirname:
        tmp = Path(dirname)
        wrap = tmp / "pid1-uInitrd"
        run("mkimage", "-A", "arm", "-O", "linux", "-T", "ramdisk",
            "-C", "gzip", "-n", "OPI3W PID1 legacy test", "-d", str(probe), str(wrap))
        verify_ramdisk(wrap, probe)
        # No physical devices: copied regular image only.
        with open(source, "rb") as inp, open(dest, "xb") as out:
            shutil.copyfileobj(inp, out, 8*1024*1024)
        loop = None
        mounted = False
        completed = False
        root = tmp / "root"
        root.mkdir()
        try:
            loop = run("losetup", "--find", "--show", "--offset", str(PART_OFFSET),
                       "--sizelimit", str(PART_SIZE), str(dest)).stdout.strip()
            run("mount", "-t", "ext4", "-o", "rw", loop, str(root))
            mounted = True
            check(root, "boot/boot.scr", FIRST_SHA)
            check(root, "boot/orangepiEnv.txt", ENV_SHA)
            check(root, cfg["kernel"], cfg["kernel_sha"])
            check(root, cfg["dtb"], cfg["dtb_sha"])
            check(root, cfg["initrd"], cfg["initrd_sha"])
            body = validate_source_script(root / STAGE2, cfg)
            textfile = tmp / "stage2.cmd"
            textfile.write_text(body.replace(OLD, NEW) + "\n")
            stage2 = tmp / "stage2.scr"
            run("mkimage", "-C", "none", "-A", "arm", "-T", "script",
                "-d", str(textfile), str(stage2))
            validate_new_script(stage2)
            before = inventory(root)
            replace_file(root / STAGE2, stage2)
            replace_file(root / cfg["initrd"], wrap)
            after = inventory(root)
            changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            if changed != sorted((STAGE2, cfg["initrd"])):
                raise RuntimeError("Unapproved changes: " + repr(changed[:30]))
            retained_shas = {
                "boot/boot.scr": FIRST_SHA,
                "boot/orangepiEnv.txt": ENV_SHA,
                cfg["kernel"]: cfg["kernel_sha"],
                cfg["dtb"]: cfg["dtb_sha"],
            }
            for name, digest in retained_shas.items():
                check(root, name, digest)
            verify_new = {STAGE2: sha(root / STAGE2), cfg["initrd"]: sha(root / cfg["initrd"])}
            normalized = dense_boot(root)
            if not normalized or inventory(root) != after:
                raise RuntimeError("Boot normalizer changed contents or ownership")
            for name, digest in verify_new.items():
                check(root, name, digest)
            os.sync()
            run("umount", str(root))
            mounted = False
            run("e2fsck", "-fn", loop)
            completed = True
        finally:
            if mounted:
                subprocess.run(["umount", str(root)], check=False)
            if loop:
                subprocess.run(["losetup", "-d", loop], check=False)
            if not completed:
                dest.unlink(missing_ok=True)
        if sha(dest, PART_OFFSET) != prefix:
            dest.unlink(missing_ok=True)
            raise RuntimeError("Firmware prefix changed")
        record = {
            "status": "ASSEMBLED_OFFLINE_NOT_HARDWARE_TESTED",
            "profile": args.profile,
            "source_sha256": cfg["image"],
            "output": str(dest),
            "output_sha256": sha(dest),
            "firmware_prefix_sha256": prefix,
            "original_kernel_sha256": cfg["kernel_sha"],
            "original_dtb_sha256": cfg["dtb_sha"],
            "probe_gzip_sha256": sha(probe),
            "legacy_uInitrd_sha256": sha(wrap),
            "stage2_sha256": verify_new[STAGE2],
            "only_changed_files": changed,
            "boot_normalizer_blob": ALLOCATOR_SHA,
            "normalized_regular_boot_files": normalized,
            "warning": "Neither Linux 6.18 entry nor U-Boot runtime relocation is proven.",
        }
        Path(str(dest) + ".audit.json").write_text(json.dumps(record, indent=2) + "\n")
        Path(str(dest) + ".sha256").write_text(record["output_sha256"] + "  " + dest.name + "\n")
        print("ASSEMBLED_OFFLINE_NOT_HARDWARE_TESTED:", dest)
        print("SHA256:", record["output_sha256"])
        print("Changed:", changed)

if __name__ == "__main__":
    main()
