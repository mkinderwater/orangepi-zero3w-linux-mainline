#!/usr/bin/env python3
"""Build isolated RAM-B firmware A/B test image.

Source VBI first 32 MiB contains hardware-proven Boot0/U-Boot/ATF firmware.
Remaining bytes come exclusively from the assembled RAM-B Test A image.
Partition table, FAT payloads, stage2/initramfs and ext4 are unchanged from A.

No input modification, no raw block device writes. Validate byte ranges both
before and after assembly. Flash ONLY to spare microSD for UART testing.
"""
from pathlib import Path
import argparse
import hashlib
import os
import shutil

PREFIX = 32 * 1024 * 1024
VBI_HASH = "7c76d125013df144d238526e396c1c9d5878c2cdf57eaa3ac09f613e32afa63c"
RAMB_BASE_HASH = "0829e193cf90a4f54bfa6beca0be456316de1e648f978d25ecaa37ddafcf2ba1"
KERNEL_HASH = "67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8"
DTB_HASH = "1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d"

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4*1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_range(path, start, length, h=None):
    if h is None:
        h=hashlib.sha256()
    with path.open("rb") as f:
        f.seek(start)
        remaining=length
        while remaining:
            data=f.read(min(4*1024*1024,remaining))
            if not data: raise RuntimeError(f"Unexpected EOF: {path}")
            h.update(data)
            remaining-=len(data)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vbi",type=Path,default=Path("/home/opi3w-VBI-vendor-A2V-booti.img"))
    ap.add_argument("--control",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/opi3w-618-ram-b-control-A.img"))
    ap.add_argument("--ramb-base",type=Path,default=Path("/root/opi3w-m2-work/a733-ram-ab-v1/a733-clean-uart-ram-b-v1.img"))
    ap.add_argument("--output",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/opi3w-618-ram-b-vbi-firmware-test.img"))
    args=ap.parse_args()
    for src in (args.vbi,args.control,args.ramb_base):
        if not src.is_file(): ap.error(f"Missing {src}")
    if args.output.exists(): ap.error(f"Refusing to overwrite {args.output}")
    for src in (args.vbi,args.control,args.ramb_base):
        if src.resolve()==args.output.resolve(): ap.error("Refusing to modify input image")
    if digest(args.vbi)!=VBI_HASH:ap.error("VBI SHA mismatch")
    if digest(args.ramb_base)!=RAMB_BASE_HASH:ap.error("RAM-B source SHA mismatch")
    size=args.control.stat().st_size
    if size != 2147483648:ap.error(f"Unexpected A image size {size}")
    if args.vbi.stat().st_size<PREFIX:ap.error("VBI shorter than 32 MiB")
    if args.ramb_base.stat().st_size!=size:ap.error("RAM-B source size differs")
    if read_range(args.control,0,PREFIX)!=read_range(args.ramb_base,0,PREFIX):
        ap.error("Control A firmware differs from the expected RAM-B source")
    # Check Control A partition region is already a clone of the known source
    # except for the FAT region [32,96) MiB, containing two new payloads.
    root_start=96*1024*1024
    if read_range(args.control,root_start,size-root_start)!=read_range(args.ramb_base,root_start,size-root_start):
        ap.error("Control A ext4 partition differs from expected RAM-B source")
    # Require exact known RAM-B kernel and DTB files on build host.
    artifacts=[(Path("/home/Image-ram-b-script-fix"),KERNEL_HASH),
               (Path("/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb"),DTB_HASH)]
    for file,expected in artifacts:
        if not file.is_file() or digest(file)!=expected:
            ap.error(f"Known RAM-B artifact absent/hash mismatch: {file}")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    try:
        shutil.copyfile(args.control,args.output)
        with args.vbi.open("rb") as donor, args.output.open("r+b") as out:
            remaining=PREFIX
            while remaining:
                data=donor.read(min(4*1024*1024,remaining))
                if not data:raise IOError("Short VBI firmware prefix")
                out.write(data)
                remaining-=len(data)
            out.flush()
            os.fsync(out.fileno())
        if read_range(args.output,0,PREFIX)!=read_range(args.vbi,0,PREFIX):
            raise RuntimeError("VBI firmware prefix mismatch")
        if read_range(args.output,PREFIX,size-PREFIX)!=read_range(args.control,PREFIX,size-PREFIX):
            raise RuntimeError("Control A partition area changed")
        if args.output.stat().st_size!=size:raise RuntimeError("Output image size changed")
        # MBR partition table is in the first 32 MiB and was copied from VBI.
        # REQUIRE an exact MBR partition-table match, else the FAT/ext4
        # offsets would point at the wrong data even if byte regions matched.
        def mbr_table(path):
            with path.open("rb") as f:
                f.seek(0x1be)
                return f.read(66)
        if mbr_table(args.vbi)!=mbr_table(args.control):
            raise RuntimeError("STOP: VBI and RAM-B MBR partition tables differ. Cannot safely prefix-swap. Build a VBI-layout image instead.")
        final_sha=digest(args.output)
        manifest=args.output.with_suffix(".manifest.txt")
        manifest.write_text(
            "VBI firmware / RAM-B control A firmware-isolation test\n"
            f"VBI input: {args.vbi}\n"
            f"RAM-B Test A input: {args.control}\n"
            f"Output: {args.output}\n"
            f"Output SHA256: {final_sha}\n"
            "Only first 32 MiB replaced from VBI; FAT/ext4 payloads bytewise unchanged from Test A.\n"
            "MBR table verified equal. No user-space/HDMI/PCK600 effects claimed.\n"
            "Requires spare SD and live UART capture; not yet hardware tested.\n"
        )
        args.output.with_suffix(".sha256").write_text(f"{final_sha}  {args.output}\n")
        print("SUCCESS:",args.output)
        print("SHA256:",final_sha)
        print("VBI firmware prefix verified; all partition data unchanged from Control A.")
        print("NOT hardware tested. Flash only on a spare microSD.")
    except Exception:
        args.output.unlink(missing_ok=True)
        raise

if __name__=="__main__":
    main()
