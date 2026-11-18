#!/usr/bin/env python3
"""Clone proven vendor 6.6.98 VBI image, byte-for-byte, as a new CONTROL.

No modifications to image contents. Firmware, boot scripts, stock vendor
kernel, initramfs, complete vendor DTB, rootfs and module tree are inherited.
The clone is intentionally NOT a Linux 6.18 image and does not claim to be
a pristine original vendor factory image: input VBI has an A2V booti path.

Requires: Debian root, sfdisk, mount, umount and optional dtc.
Creates a new raw flashable .img and .sha256/.manifest.txt ONLY.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

INPUT_DEFAULT=Path("/home/opi3w-VBI-vendor-A2V-booti.img")
OUTPUT_DEFAULT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/opi3w-VENDOR-6698-full-stock-baseline.img")
EXPECTED_SHA="7c76d125013df144d238526e396c1c9d5878c2cdf57eaa3ac09f613e32afa63c"
DISPLAY_MARKERS=(b"sunxi-drm",b"hdmi0",b"tcon3",b"allwinner")

def require(yes,why):
    if not yes: raise RuntimeError("STOP: "+why)
def call(*args):
    return subprocess.run([str(x) for x in args],check=True,text=True,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda:f.read(4*1024*1024),b""):
            h.update(buf)
    return h.hexdigest()
def partition_geometry(path):
    info=json.loads(call("sfdisk","-J",path))["partitiontable"]
    parts=info["partitions"]
    sector=int(info.get("sectorsize",512))
    require(len(parts)==1,"expected VBI one-partition layout")
    p=parts[0]
    require(int(p["start"])==65536 and
            str(p.get("type","")).lower().removeprefix("0x")=="83",
            "VBI vendor partition layout differs from known-good")
    offset=p["start"]*sector
    limit=p["size"]*sector
    require(path.stat().st_size>=offset+limit,"truncated vendor image")
    return offset,limit

def inspect(mount):
    boot=mount/"boot"
    require(boot.is_dir(),"missing /boot")
    # Known prior boot evidence; VBI path still uses complete vendor payloads.
    files={
        "stage1":boot/"boot.scr",
        "vendor_stage2":boot/"mainline/stock-vendor-stage2.scr",
        "vendor_kernel":boot/"mainline/verified-vendor-Image",
        "vendor_initrd":boot/"mainline/verified-vendor-initrd.gz",
        "vendor_kernel_config":boot/"config-6.6.98-sun60iw2",
    }
    for label,path in files.items():
        require(path.is_file(),f"missing {label}: {path}")
    require(files["vendor_kernel"].stat().st_size>3_000_000,
            "unexpectedly small vendor kernel")
    config=files["vendor_kernel_config"].read_text(errors="replace")
    require("CONFIG_AW_DRM=y" in config and "CONFIG_DRM=y" in config,
            "source vendor kernel config does not enable Allwinner DRM")
    dtbroot=boot/"dtb-6.6.98-sun60iw2"
    require(dtbroot.is_dir(),"missing vendor DTB directory")
    candidates=sorted(dtbroot.rglob("*.dtb"))
    require(candidates,"no full vendor DTB in vendor DTB directory")
    # Discover the exact named board DTB; never silently choose a different board.
    board=[x for x in candidates if "zero3w" in x.name.lower() or "zero-3w" in x.name.lower()]
    require(len(board)==1,"need exactly one Zero 3W board DTB, found: "+", ".join(str(x.relative_to(dtbroot)) for x in board))
    dtb=board[0]
    dtbbytes=dtb.read_bytes()
    require(len(dtbbytes)>=1024 and dtbbytes[:4]==b"\xd0\x0d\xfe\xed",
            "Zero 3W DTB does not have an FDT header")
    if shutil.which("dtc"):
        dts=call("dtc","-I","dtb","-O","dts",dtb)
        for node in ("de@5000000","tcon3@5730000","hdmi0@5520000","sunxi-drm"):
            require(node in dts,"complete vendor display graph missing: "+node)
    else:
        require(all(x in dtbbytes for x in DISPLAY_MARKERS[:3]),
                "cannot verify full DTB display markers; install device-tree-compiler")
    info={label:(str(p.relative_to(mount)),sha256(p),p.stat().st_size)
          for label,p in files.items()}
    info["vendor_board_dtb"]=(str(dtb.relative_to(mount)),sha256(dtb),dtb.stat().st_size)
    # This is an informational control, not proof the stage2 uses this particular DTB.
    return info

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,default=INPUT_DEFAULT)
    p.add_argument("--output",type=Path,default=OUTPUT_DEFAULT)
    a=p.parse_args()
    require(os.geteuid()==0,"root required for read-only ext4 mount")
    for utility in ("sfdisk","mount","umount"):
        require(shutil.which(utility),"missing "+utility)
    require(a.input.is_file(),"known-good vendor image not found")
    require(a.input.resolve()!=a.output.resolve(),"input and output same")
    require(not a.output.exists(),"refusing to overwrite output image")
    source_hash=sha256(a.input)
    require(source_hash==EXPECTED_SHA,
            "vendor VBI image SHA mismatch: "+source_hash)
    offset,limit=partition_geometry(a.input)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    created=False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            mount=Path(tmp)/"root"
            mount.mkdir()
            mounted=False
            try:
                call("mount","-t","ext4","-o",
                     f"ro,noload,loop,offset={offset},sizelimit={limit}",
                     a.input,mount)
                mounted=True
                original_files=inspect(mount)
                call("umount",mount)
                mounted=False
                # New baseline is an exact clone. We intentionally do NOT
                # edit the vendor DTB, kernel, firmware or boot script.
                with a.input.open("rb") as src,a.output.open("xb") as dst:
                    created=True
                    shutil.copyfileobj(src,dst,4*1024*1024)
                    dst.flush()
                    os.fsync(dst.fileno())
                result_hash=sha256(a.output)
                require(result_hash==source_hash,"cloned raw image hash differs")
                require(partition_geometry(a.output)==(offset,limit),
                        "partition layout changed")
                call("mount","-t","ext4","-o",
                     f"ro,noload,loop,offset={offset},sizelimit={limit}",
                     a.output,mount)
                mounted=True
                cloned_files=inspect(mount)
                require(original_files==cloned_files,
                        "vendor stock payload hashes changed")
                call("umount",mount)
                mounted=False
                Path(str(a.output)+".sha256").write_text(
                    f"{result_hash}  {a.output}\n")
                lines=[
                    "Vendor 6.6.98 full-stock kernel/DTB baseline (A2V VBI control clone)",
                    "NOT a pristine OEM image. The proven VBI reference uses vendor booti.",
                    "New image has NOT yet been independently flashed or booted.",
                    f"Input: {a.input}",
                    f"Output: {a.output}",
                    f"Image SHA256 (source and clone identical): {result_hash}",
                    "The entire image is identical, including Boot0/BL31/SCP/U-Boot,",
                    "kernel, initramfs, full vendor DTB tree, modules, ext4 and scripts.",
                    "HDMI connected at power-on and UART should be retested on spare SD.",
                    "All subsequent 6.18 integration changes must be separate images.",
                    "Verification:",
                ]
                lines.extend(f"  {k}: {v[0]} SHA256={v[1]} bytes={v[2]}"
                             for k,v in sorted(cloned_files.items()))
                Path(str(a.output)+".manifest.txt").write_text("\n".join(lines)+"\n")
                print("PASS: byte-identical vendor VBI baseline",a.output)
                print("SHA256:",result_hash)
                print("Files verified:",len(cloned_files))
                print("Note: control baseline is stock 6.6.98 kernel + DTB, NOT Linux 6.18")
            finally:
                if mounted:call("umount",mount)
    except BaseException:
        if created:
            a.output.unlink(missing_ok=True)
            Path(str(a.output)+".sha256").unlink(missing_ok=True)
            Path(str(a.output)+".manifest.txt").unlink(missing_ok=True)
        raise

if __name__=="__main__":
    main()
