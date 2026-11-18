#!/usr/bin/env python3
"""Arm a cloned VBI RAM-B isolation image for automatic Linux 6.18 boot.

Input: successful build-vbi-ramb-boot-isolation.sh output, retaining the VBI
vendor files and adding three verified RAM-B payloads. Output: new image only.
The VBI stage1 loads stock-vendor-stage2.scr at 0x46000000; replace only that
script on this cloned image. NEVER change VBI or the working recovery card.
"""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile

VBI_SHA="7c76d125013df144d238526e396c1c9d5878c2cdf57eaa3ac09f613e32afa63c"
KERNEL_SHA="67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8"
DTB_SHA="1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d"
INITRD_SHA="1a68a774c6b47081f338bcc8f595b4a154dbd433293cf3ad1b8df31cc7ac919b"
BASE="/boot/mainline"
STAGE1="/boot/boot.scr"
STAGE2=BASE+"/stock-vendor-stage2.scr"
BACKUP=BASE+"/stock-vendor-stage2.preserved.scr"
TEST=BASE+"/ram-b-vbi-isolation"

def run(*args, **kw):
    return subprocess.run(args,check=True,**kw)
def digest(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for part in iter(lambda:f.read(4*1024*1024),b""):h.update(part)
    return h.hexdigest()
def require(ok,reason):
    if not ok:raise RuntimeError("STOP: "+reason)
def check(path,expected):
    require(Path(path).is_file(),f"Missing {path}")
    require(digest(path)==expected,f"SHA mismatch: {path}")
def partition(img):
    import json
    j=json.loads(subprocess.check_output(["sfdisk","-J",str(img)]))["partitiontable"]
    p=j["partitions"]
    require(len(p)==1 and str(p[0].get("type","")).lower().removeprefix("0x")=="83" and p[0]["start"]==65536,"Not VBI one-ext4 layout")
    sector=int(j.get("sectorsize",512))
    return p[0]["start"]*sector,p[0]["size"]*sector
def compare_prefix(a,b):
    with open(a,"rb") as x,open(b,"rb") as y:
        remaining=32*1024*1024
        while remaining:
            n=min(1024*1024,remaining)
            require(x.read(n)==y.read(n),"First 32 MiB changed")
            remaining-=n
def checked_paths(mount):
    for name,hashval in (("Image",KERNEL_SHA),("ram-b-26mhz.dtb",DTB_SHA),("initrd.gz",INITRD_SHA)):
        check(mount/TEST.lstrip("/")/name,hashval)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vbi",type=Path,default=Path("/home/opi3w-VBI-vendor-A2V-booti.img"))
    ap.add_argument("--input",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/opi3w-VBI-RAMB-isolation.img"))
    ap.add_argument("--output",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/opi3w-VBI-RAMB-autoboot.img"))
    a=ap.parse_args()
    require(os.geteuid()==0,"Run as root")
    for command in ("mount","umount","sfdisk","mkimage","dumpimage","strings"):
        require(shutil.which(command) is not None,"Missing "+command)
    check(a.vbi,VBI_SHA)
    require(a.input.is_file(),"Build VBI-RAMB-isolation.img first")
    require(not a.output.exists(),"Output already exists, refusing overwrite")
    require(a.input.resolve()!=a.vbi.resolve() and a.input.resolve()!=a.output.resolve(),"Input/output collision")
    require(a.input.stat().st_size==a.vbi.stat().st_size,"Input image size differs from VBI")
    compare_prefix(a.vbi,a.input)
    offset,length=partition(a.input)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    dollar=chr(36)
    cmd="""# VBI isolated RAM-B auto-start; NO vendor fallback
setenv kernel_addr_r 0x41000000
setenv fdt_addr_r 0x44000000
setenv ramdisk_addr_r 0x45000000
setenv bootargs "earlycon=uart8250,mmio32,0x02500000 console=ttyS0,115200n8 keep_bootcon loglevel=8 ignore_loglevel initcall_debug rdinit=/init panic=-1"
echo "VBI RAM-B AUTO: loading Linux 6.18"
if load mmc 0:1 0x41000000 /boot/mainline/ram-b-vbi-isolation/Image; then
  if load mmc 0:1 0x44000000 /boot/mainline/ram-b-vbi-isolation/ram-b-26mhz.dtb; then
    fdt addr 0x44000000
    fdt resize 65536
    if load mmc 0:1 0x45000000 /boot/mainline/ram-b-vbi-isolation/initrd.gz; then
      echo "VBI RAM-B AUTO: entering booti"
      booti 0x41000000 0x45000000:@SIZE@ 0x44000000
    fi
  fi
fi
echo "VBI RAM-B AUTO: load or boot failed. NO FALLBACK"
while true; do sleep 5; done
""".replace("@SIZE@",dollar+"{filesize}")
    with tempfile.TemporaryDirectory() as td:
        temp=Path(td)
        mnt=temp/"mnt"
        mnt.mkdir()
        (temp/"stage2.cmd").write_text(cmd)
        run("mkimage","-A","arm","-O","linux","-T","script","-C","none",
            "-n","VBI RAM-B auto test","-d",str(temp/"stage2.cmd"),str(temp/"stage2.scr"),
            stdout=subprocess.DEVNULL)
        run("dumpimage","-T","script","-p","0","-o",str(temp/"decoded.cmd"),str(temp/"stage2.scr"),
            stdout=subprocess.DEVNULL)
        require((temp/"decoded.cmd").read_bytes()==(temp/"stage2.cmd").read_bytes(),"U-Boot script roundtrip mismatch")
        shutil.copyfile(a.input,a.output)
        mounted=False
        success=False
        first=None
        old_stage2=None
        try:
            run("mount","-t","ext4","-o",f"loop,offset={offset},sizelimit={length}",str(a.output),str(mnt))
            mounted=True
            first=mnt/STAGE1.lstrip("/")
            original=mnt/STAGE2.lstrip("/")
            saved=mnt/BACKUP.lstrip("/")
            require(first.is_file() and original.is_file(),"Original VBI stage1/stage2 missing")
            require(not saved.exists(),"Stage2 backup already exists in clone")
            require("stock-vendor-stage2.scr" in subprocess.check_output(["strings","-a",str(first)]).decode(),"Stage1 does not reference target stage2")
            checked_paths(mnt)
            stage1_bytes=first.read_bytes()
            old_stage2=original.read_bytes()
            saved.write_bytes(old_stage2)
            new=(temp/"stage2.scr").read_bytes()
            with original.open("wb",buffering=0) as f:
                os.posix_fallocate(f.fileno(),0,len(new))
                f.write(new)
                os.fsync(f.fileno())
            require(first.read_bytes()==stage1_bytes,"Stage1 changed")
            require(original.read_bytes()==new,"Stage2 replacement failed")
            require(saved.read_bytes()==old_stage2,"Vendor stage2 backup mismatch")
            checked_paths(mnt)
            run("sync")
            run("umount",str(mnt))
            mounted=False
            run("mount","-t","ext4","-o",f"ro,noload,loop,offset={offset},sizelimit={length}",str(a.output),str(mnt))
            mounted=True
            require((mnt/STAGE1.lstrip("/")).read_bytes()==stage1_bytes,"Final stage1 mismatch")
            require((mnt/STAGE2.lstrip("/")).read_bytes()==new,"Final stage2 mismatch")
            require((mnt/BACKUP.lstrip("/")).read_bytes()==old_stage2,"Final vendor stage2 backup mismatch")
            checked_paths(mnt)
            run("umount",str(mnt))
            mounted=False
            compare_prefix(a.vbi,a.output)
            final=digest(a.output)
            Path(str(a.output)+".sha256").write_text(f"{final}  {a.output}\n")
            Path(str(a.output)+".manifest.txt").write_text(
                "VBI RAM-B automatic hardware test, NOT YET TESTED\n"
                f"Source VBI: {a.vbi}\nSource isolated image: {a.input}\n"
                f"Output SHA256: {final}\n"
                "Vendor firmware/MBR and first-stage script unchanged.\n"
                "Only cloned VBI stage2 replaced; original saved under stock-vendor-stage2.preserved.scr.\n"
                "RAM-B kernel/DTB/initramfs hashes checked before and after.\n"
                "No fallback after attempted booti; flash only to spare microSD.\n"
            )
            success=True
            print("SUCCESS:",a.output)
            print("SHA256:",final)
            print("Hardware test NOT yet run. Stage1 will auto-load RAM-B via ext4.")
        finally:
            if mounted:run("umount",str(mnt))
            if not success:
                a.output.unlink(missing_ok=True)
                Path(str(a.output)+".sha256").unlink(missing_ok=True)
                Path(str(a.output)+".manifest.txt").unlink(missing_ok=True)
if __name__=="__main__":main()
