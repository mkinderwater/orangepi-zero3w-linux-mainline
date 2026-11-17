#!/usr/bin/env python3
"""Make a read-only, fail-closed kernel release preflight manifest.

No flashing, package installation, boot-script edits, firmware changes or boot
selection. Input paths must be explicit. The output is a single JSON file.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

ARM64_MAGIC = b"ARM\x64"
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
MAX_DTB = 64 * 1024 * 1024


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as src:
        while True:
            block = src.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def file_record(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Expected a regular non-symlink file: {path}")
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": digest(path)}


def image_check(path):
    rec = file_record(path)
    with path.open("rb") as src:
        head = src.read(64)
    if len(head) != 64 or head[56:60] != ARM64_MAGIC:
        raise ValueError("Invalid raw ARM64 Image header (magic ARMd)")
    text_offset, image_size, flags = struct.unpack_from("<QQQ", head, 8)
    if image_size == 0 or image_size < rec["bytes"]:
        raise ValueError("ARM64 Image declared image_size is zero or smaller than file")
    rec["text_offset"] = text_offset
    rec["declared_image_size"] = image_size
    rec["flags"] = flags
    return rec


def dtb_check(path):
    rec = file_record(path)
    with path.open("rb") as src:
        head = src.read(40)
    if len(head) != 40 or head[:4] != FDT_MAGIC:
        raise ValueError("Invalid FDT magic")
    total = struct.unpack_from(">I", head, 4)[0]
    if not 40 <= total <= rec["bytes"] or total > MAX_DTB:
        raise ValueError("Invalid FDT totalsize")
    rec["dtb_totalsize"] = total
    return rec


def initrd_check(path):
    rec = file_record(path)
    with path.open("rb") as src:
        magic = src.read(4)
    if magic[:2] == b"\x1f\x8b":
        rec["format"] = "raw-gzip"
    elif magic == b"\x27\x05\x19\x56":
        with path.open("rb") as src:
            hdr = src.read(64)
        if len(hdr) < 64 or hdr[30] != 3:
            raise ValueError("Invalid legacy ramdisk image type")
        rec["format"] = "legacy-uInitrd"
    else:
        raise ValueError("Unrecognized initrd format; only gzip or legacy uInitrd accepted")
    return rec


def modules_check(path, release):
    if not path.is_dir() or path.is_symlink():
        raise ValueError(f"Missing or symlink modules directory: {path}")
    if path.name != release:
        raise ValueError("Modules directory basename must equal kernel release")
    files = sorted(p for p in path.rglob("*") if p.is_file())
    if not files:
        raise ValueError("Modules directory is empty")
    mods = [p for p in files if p.suffix in (".ko", ".xz", ".zst", ".gz")]
    if not mods:
        raise ValueError("Modules directory contains no module candidate")
    if any(p.is_symlink() for p in files):
        raise ValueError("Symlink module entry detected; inspect it before release")
    return {"path": str(path.resolve()), "kernel_release": release,
            "files": len(files), "modules_or_compressed_files": len(mods),
            "module_tree_hash": hashlib.sha256(
                "\n".join(f"{p.relative_to(path)} {digest(p)}" for p in files)
                .encode("utf-8")).hexdigest()}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--dtb", type=Path, required=True)
    cli.add_argument("--initrd", type=Path, required=True)
    cli.add_argument("--modules", type=Path, required=True,
                     help="Exact /lib/modules/<kernel-release> tree")
    cli.add_argument("--kernel-release", required=True)
    cli.add_argument("--output", type=Path, required=True,
                     help="New JSON file, never overwrite")
    cli.add_argument("--upstream-sha", default="UNKNOWN")
    cli.add_argument("--bsp-sha", default="UNKNOWN")
    args = cli.parse_args()
    if not args.kernel_release or any(x in args.kernel_release for x in "/\\\x00"):
        cli.error("Invalid kernel-release")
    if args.output.exists():
        cli.error("Output exists, refusing overwrite")
    paths = [args.image, args.dtb, args.initrd]
    if len({str(p.resolve()) for p in paths}) != 3:
        cli.error("Image, DTB and initrd must be distinct")
    try:
        data = {
            "schema": 1,
            "status": "STATIC_PREFLIGHT_ONLY_NOT_HARDWARE_TESTED",
            "kernel_release": args.kernel_release,
            "source": {"upstream_sha": args.upstream_sha,
                       "bsp_sha": args.bsp_sha},
            "image": image_check(args.image),
            "dtb": dtb_check(args.dtb),
            "initrd": initrd_check(args.initrd),
            "modules": modules_check(args.modules, args.kernel_release),
            "not_checked": [
                "actual kernel uname matches release label",
                "kernel/module symbol versions and vermagic",
                "boot script and FDT compatibility on vendor U-Boot",
                "all DT binding warnings and board RAM variants",
                "regulator and PF voltage safety on hardware",
                "signature trust, signed packages, or rollback",
                "dense /boot allocation on final ext4 media"
            ]
        }
    except (ValueError, OSError) as exc:
        cli.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        args.output.unlink(missing_ok=True)
        raise
    print(f"RELEASE_PREFLIGHT_ONLY: {args.output}")


if __name__ == "__main__":
    main()
