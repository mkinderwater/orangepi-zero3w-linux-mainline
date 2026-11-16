#!/usr/bin/env python3
"""Read-only finished-image audit for Orange Pi Zero 3W VBI/HBI/F1 tests.

Requires root, util-linux (losetup, sfdisk, blkid), e2fsprogs (debugfs), u-boot-tools
(dumpimage). Never mounts or changes an image. Do not treat absence of Linux
messages or a frozen HDMI splash as proof of no kernel execution.
"""
import argparse
import difflib
import hashlib
import json
import posixpath
import re
import subprocess
import tempfile
from pathlib import Path

BOOT_FILES = [
    "/boot/boot.scr",
    "/boot/orangepiEnv.txt",
    "/boot/mainline/stock-vendor-stage2.scr",
    "/boot/uImage",
    "/boot/uInitrd",
    "/boot/dtb/allwinner/sun60i-a733-orangepi-zero3w.dtb",
]
MAX_EXTRACT = 160 * 1024 * 1024

def cmd(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def debugfs(dev, query, check=True):
    r = cmd("debugfs", "-R", query, dev, check=False)
    if check and (r.returncode or "File not found" in r.stderr or "not found" in r.stderr):
        raise RuntimeError(f"debugfs {query}: {r.stderr.strip()}")
    return r

def list_dir(dev, dirname):
    out = debugfs(dev, "ls -p " + dirname, check=False)
    if "not found" in out.stderr.lower():
        return []
    # debugfs 'ls -p' renders /inode/mode/uid/gid/name/size/.
    entries = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line.startswith("/"):
            continue
        parts = line.split("/")
        if len(parts) >= 7:
            name = parts[5]
            mode = parts[2]
            if name not in (".", "..") and re.fullmatch(r"[0-7]{5,7}", mode or ""):
                entries.append((name, mode))
    return entries

def discover(dev):
    paths = set(BOOT_FILES)
    for dirname in ("/boot", "/boot/mainline", "/boot/mainline/0.2.7",
                    "/boot/mainline/hybrid", "/boot/dtb/allwinner"):
        for name, mode in list_dir(dev, dirname):
            if dirname in ("/boot", "/boot/mainline", "/boot/mainline/0.2.7",
                           "/boot/mainline/hybrid"):
                if name.endswith((".scr", ".cmd", ".dtb", ".img", ".bin", ".gz", ".cpio")) or name in ("Image", "uImage", "uInitrd", "initrd", "orangepiEnv.txt"):
                    paths.add(dirname + "/" + name)
    return sorted(paths)

def extract(dev, src, dst):
    # debugfs dump does not follow inline (fast) ext4 symlinks.
    # Resolve symlinks inside the image, preserving the original link names.
    current = src
    visited = set()
    chain = []
    for _ in range(16):
        if current in visited:
            raise RuntimeError(f"Symlink cycle at {src}: {chain}")
        visited.add(current)
        stat = debugfs(dev, "stat " + current, check=False)
        if "not found" in stat.stderr.lower() or "File not found" in stat.stdout:
            if not chain:
                return None
            raise RuntimeError(f"Broken symlink: {src} -> {current}")
        match = re.search(r"Size:\s*(\d+)", stat.stdout)
        if not match:
            raise RuntimeError(f"Cannot read inode size: {current}")
        size = int(match.group(1))
        if "Type: symlink" not in stat.stdout:
            if "Type: regular" not in stat.stdout:
                return {"type": "nonregular", "resolved_path": current}
            break
        m = re.search(r'Fast link dest:\s*"([^"]+)"', stat.stdout)
        if not m:
            raise RuntimeError(f"Unsupported non-fast symlink at {current}")
        link = m.group(1)
        # Absolute symlinks refer to the image filesystem root.
        joined = link if link.startswith("/") else posixpath.join(posixpath.dirname(current), link)
        nextpath = posixpath.normpath(joined)
        if not nextpath.startswith("/"):
            raise RuntimeError(f"Symlink left filesystem root: {current}")
        chain.append({"path": current, "target": link})
        current = nextpath
    else:
        raise RuntimeError(f"Too many symlink hops for {src}")
    metadata = {"size": size, "type": "regular", "resolved_path": current}
    if chain:
        metadata["symlink_chain"] = chain
    if size > MAX_EXTRACT:
        metadata["skipped"] = "oversize"
        return metadata
    r = debugfs(dev, "dump " + current + " " + str(dst), check=False)
    if r.returncode or not dst.is_file() or dst.stat().st_size != size:
        raise RuntimeError(f"Cannot extract {src} (resolved {current}): {r.stderr.strip()}")
    metadata["sha256"] = sha256(dst)
    return metadata

def decode_script(path, output):
    r = cmd("dumpimage", "-T", "script", "-p", "0", "-o",
            str(output), str(path), check=False)
    if r.returncode:
        return {"error": r.stderr.strip()[:300]}
    raw = output.read_bytes().rstrip(bytes([0]))
    return {"decoded_sha256": hashlib.sha256(raw).hexdigest(),
            "text": raw.decode("utf-8", errors="replace")}

def inspect(label, path, dest):
    if not path.is_file():
        raise FileNotFoundError(path)
    image_hash = sha256(path)
    # WSL may expose no /dev/loopNp1 with --partscan, even for valid MBR.
    # Read the image's partition table, then create read-only offset loop
    # devices. Never guess an offset or assume filesystem is partition 1.
    layout = json.loads(cmd("sfdisk", "--json", str(path)).stdout)["partitiontable"]
    sector_size = int(layout.get("sectorsize", 512))
    if sector_size not in (512, 1024, 2048, 4096):
        raise RuntimeError(f"Unexpected logical sector size: {sector_size}")
    candidates = layout.get("partitions", [])
    if not candidates:
        raise RuntimeError(f"{label}: no partitions in sfdisk table")
    devices = []
    ext4 = []
    try:
        for part in candidates:
            start = int(part["start"])
            size = int(part["size"])
            if start < 0 or size <= 0 or (start + size) * sector_size > path.stat().st_size:
                raise RuntimeError(f"{label}: partition outside image bounds")
            dev = cmd("losetup", "--find", "--show", "--read-only",
                      "--offset", str(start * sector_size),
                      "--sizelimit", str(size * sector_size), str(path)).stdout.strip()
            devices.append(dev)
            fs = cmd("blkid", "-p", "-o", "value", "-s", "TYPE", dev, check=False)
            if fs.returncode == 0 and fs.stdout.strip() == "ext4":
                ext4.append((dev, start, size))
        if len(ext4) != 1:
            raise RuntimeError(f"{label}: require exactly one ext4 partition; detected {len(ext4)}")
        dev, start, size = ext4[0]
        record = {"image": str(path), "sha256": image_hash,
                  "size_bytes": path.stat().st_size, "ext4_device": dev,
                  "partition_start_sector": start, "partition_sector_count": size,
                  "sector_size": sector_size,
                  "boot_files": {}, "scripts": {}}
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for idx, name in enumerate(discover(dev)):
                target = tmp / ("file_" + str(idx))
                meta = extract(dev, name, target)
                if meta is None:
                    continue
                record["boot_files"][name] = meta
                if name.endswith(".scr") and "sha256" in meta:
                    decoded = decode_script(target, tmp / ("decoded_" + str(idx)))
                    record["scripts"][name] = decoded
        return record
    finally:
        for dev in reversed(devices):
            cmd("losetup", "-d", dev, check=False)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vbi", required=True, type=Path)
    ap.add_argument("--hbi", required=True, type=Path)
    ap.add_argument("--f1", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = {"state": "OFFLINE_AUDIT_ONLY", "control": "VBI_VENDOR_6_6_98",
              "images": {}}
    for label, filename in (("VBI", args.vbi), ("HBI", args.hbi), ("F1", args.f1)):
        if filename is None:
            continue
        print(f"Inspecting {label}: {filename}", flush=True)
        result["images"][label] = inspect(label, filename, args.output)
    # Keep complete decoded scripts separately; JSON hashes/metadata stay small.
    texts = {}
    for label, entry in result["images"].items():
        for path, obj in entry["scripts"].items():
            if "text" in obj:
                texts[(label, path)] = obj.pop("text")
                safe = path.strip("/").replace("/", "_")
                (args.output / f"{label}-{safe}.cmd").write_text(texts[(label, path)])
    labels = list(result["images"])
    if "VBI" in labels and "HBI" in labels:
        first = next(((k, v) for (l, k), v in texts.items()
                      if l == "VBI" and "stage2" in k.lower()), None)
        second = next(((k, v) for (l, k), v in texts.items()
                       if l == "HBI" and "stage2" in k.lower()), None)
        if first and second:
            diff = difflib.unified_diff(first[1].splitlines(keepends=True),
                                        second[1].splitlines(keepends=True),
                                        fromfile="VBI:" + first[0],
                                        tofile="HBI:" + second[0])
            (args.output / "VBI-vs-HBI-stage2.diff").write_text("".join(diff))
        # Changed payload hash list only. No assumption that a difference
        # establishes a boot failure cause.
        a = result["images"]["VBI"]["boot_files"]
        b = result["images"]["HBI"]["boot_files"]
        result["vbi_hbi_changed_paths"] = [
            name for name in sorted(set(a) | set(b))
            if a.get(name) != b.get(name)
        ]
    (args.output / "AUDIT.json").write_text(json.dumps(result, indent=2) + "\n")
    print("OFFLINE_AUDIT_COMPLETE", args.output / "AUDIT.json")

if __name__ == "__main__":
    main()
