#!/usr/bin/env python3
"""Read-only finished-image audit for Orange Pi Zero 3W VBI/HBI/F1 tests.

Requires root, util-linux (losetup, lsblk), e2fsprogs (debugfs), u-boot-tools
(dumpimage). Never mounts or changes an image. Do not treat absence of Linux
messages or a frozen HDMI splash as proof of no kernel execution.
"""
import argparse
import difflib
import hashlib
import json
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
    # Do not parse filesystem structures manually. debugfs reads the ext4
    # file without altering journal, inode, or allocation state.
    stat = debugfs(dev, "stat " + src, check=False)
    if "not found" in stat.stderr.lower() or "File not found" in stat.stdout:
        return None
    match = re.search(r"Size:\s*(\d+)", stat.stdout)
    if not match:
        return None
    size = int(match.group(1))
    if size > MAX_EXTRACT:
        return {"size": size, "skipped": "oversize"}
    r = debugfs(dev, "dump " + src + " " + str(dst), check=False)
    if r.returncode or not dst.is_file() or dst.stat().st_size != size:
        raise RuntimeError(f"Cannot extract {src}: {r.stderr.strip()}")
    return {"size": size, "sha256": sha256(dst)}

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
    r = cmd("losetup", "--find", "--show", "--read-only", "--partscan", str(path))
    loop = r.stdout.strip()
    try:
        disks = cmd("lsblk", "-nrpo", "NAME,FSTYPE", loop).stdout.splitlines()
        ext4 = [line.split()[0] for line in disks if len(line.split()) >= 2 and line.split()[1] == "ext4"]
        if len(ext4) != 1:
            raise RuntimeError(f"{label}: require precisely one ext4 partition, found {ext4}")
        dev = ext4[0]
        record = {"image": str(path), "sha256": image_hash,
                  "size_bytes": path.stat().st_size, "ext4_device": dev,
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
        cmd("losetup", "-d", loop, check=False)

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
