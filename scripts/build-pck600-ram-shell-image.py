#!/usr/bin/env python3
"""Clone PCK600 FAT boot image, replacing only the initramfs with RAM-only PID1.

The source Image, DTB, two U-Boot scripts, firmware region and ext4 root
partition are preserved byte-for-byte. Produces a NEW raw .img for spare SD.
Requires root, gzip, cpio, readelf, mount, umount and sfdisk on Debian.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

ROOT = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4")
KERNEL_SHA = "9f8c4af6f7f3d5ff604aac29bd7553e04dc3a41c0c8a5000308594c49ab5cb1c"
DTB_SHA = "c5cc45413f4be4efbf80a1c26c061462e2a9b2e3649a49bf055b008d5209f697"
FILES = {
    "boot.scr": None,
    "mainline/stage2.scr": None,
    "mainline/Image": KERNEL_SHA,
    "mainline/sun60i-a733-orangepi-zero3w.dtb": DTB_SHA,
    "mainline/uart-diagnostic-initrd.gz": None,
}
INIT = """#!/bin/busybox sh
echo "PCK600-RAM-SHELL: /init entered"
echo "PCK600-RAM-SHELL: no MMC/PMIC root discovery"
mkdir -p /proc /sys /dev
/bin/busybox mount -t proc proc /proc 2>/dev/null || echo "proc unavailable"
/bin/busybox mount -t sysfs sysfs /sys 2>/dev/null || echo "sys unavailable"
/bin/busybox mount -t devtmpfs devtmpfs /dev 2>/dev/null || echo "devtmpfs unavailable"
echo "PCK600-RAM-SHELL: interactive BusyBox follows"
exec /bin/busybox sh </dev/console >/dev/console 2>&1
"""

def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)

def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        while True:
            chunk=f.read(4*1024*1024)
            if not chunk: break
            h.update(chunk)
    return h.hexdigest()

def need(value, message):
    if not value: raise RuntimeError("STOP: "+message)

def parse_partitions(path):
    info=json.loads(subprocess.check_output(["sfdisk","-J",str(path)]))["partitiontable"]
    entries=info.get("partitions",[])
    t=lambda x: str(x.get("type","")).lower().removeprefix("0x")
    fat=[x for x in entries if t(x) in ("b","c","0b","0c")]
    root=[x for x in entries if t(x)=="83"]
    need(len(fat)==1 and len(root)==1 and fat[0]["start"]==65536 and root[0]["start"]==196608,
         "Unexpected FAT/ext4 partition map")
    sector=int(info.get("sectorsize",512))
    return (fat[0]["start"]*sector,fat[0]["size"]*sector,
            root[0]["start"]*sector,root[0]["size"]*sector)

def verify(mount):
    result={}
    for name,wanted in FILES.items():
        p=mount/name
        need(p.is_file() and not p.is_symlink(),"Missing FAT boot file "+name)
        result[name]=sha(p)
        if wanted: need(result[name]==wanted,"Unexpected hash for "+name)
    return result

def build_initrd(source, directory):
    rd=directory/"rd"
    rd.mkdir()
    # Extract trusted archive from already-built local test image.
    with source.open("rb") as f:
        ungzip=subprocess.Popen(["gzip","-dc"],stdin=f,stdout=subprocess.PIPE)
        try:
            run("cpio","-idm","--no-absolute-filenames","--quiet",
                stdin=ungzip.stdout,cwd=rd,stdout=subprocess.DEVNULL)
        finally:
            ungzip.stdout.close()
            need(ungzip.wait()==0,"Original initramfs gzip stream failed")
    busybox=rd/"bin/busybox"
    need(busybox.is_file() and os.access(busybox,os.X_OK),
         "Original initramfs lacks executable /bin/busybox")
    elf=subprocess.check_output(["readelf","-h",str(busybox)],text=True)
    need("AArch64" in elf,"BusyBox is not AArch64")
    headers=subprocess.check_output(["readelf","-l",str(busybox)],text=True)
    need("Requesting program interpreter" not in headers,
         "BusyBox is dynamic; not safe to assume dependencies")
    (rd/"init").write_text(INIT)
    (rd/"init").chmod(0o755)
    for node in ("proc","sys","dev"):
        (rd/node).mkdir(exist_ok=True)
    console=rd/"dev/console"
    if not console.exists():
        os.mknod(console,stat.S_IFCHR|0o600,os.makedev(5,1))
    entries=[]
    for base,dirs,files in os.walk(rd,followlinks=False):
        dirs.sort();files.sort()
        parent=Path(base)
        for name in dirs+files:
            item=parent/name
            entries.append("./"+str(item.relative_to(rd)))
    entries.sort()
    names=b"\0".join(x.encode() for x in entries)+b"\0"
    new=directory/"ram-shell-initrd.gz"
    with new.open("wb") as dest:
        cpio=subprocess.Popen(["cpio","--null","-o","--format=newc","--quiet"],
                              stdin=subprocess.PIPE,stdout=subprocess.PIPE,cwd=rd)
        compressed=subprocess.Popen(["gzip","-n","-6"],stdin=cpio.stdout,
                                    stdout=dest)
        cpio.stdout.close()
        cpio.stdin.write(names)
        cpio.stdin.close()
        need(compressed.wait()==0,"Compression failed")
        need(cpio.wait()==0,"CPIO creation failed")
    run("gzip","-t",new)
    return new

def compare_region(a,b,start,size):
    with a.open("rb") as x,b.open("rb") as y:
        x.seek(start);y.seek(start)
        while size:
            n=min(4*1024*1024,size)
            need(x.read(n)==y.read(n),"Unexpected change to disk region "+hex(start))
            size-=n
            start+=n

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,default=ROOT/"artifacts/opi3w-618-pck600-fat-probe.img")
    ap.add_argument("--output",type=Path,default=ROOT/"artifacts/opi3w-618-pck600-ram-shell.img")
    args=ap.parse_args()
    need(os.geteuid()==0,"Run as root on Debian")
    for cmd in ("sfdisk","mount","umount","gzip","cpio","readelf"):
        need(shutil.which(cmd),"Missing tool "+cmd)
    need(args.input.is_file(),"Input PCK600 FAT image not found")
    need(not args.output.exists(),"Refusing to overwrite "+str(args.output))
    need(args.input.resolve()!=args.output.resolve(),"Output equals input")
    offset,length,root_offset,root_length=parse_partitions(args.input)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    created=False
    try:
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp)
            mnt=temp/"fat";mnt.mkdir()
            mounted=False
            try:
                run("mount","-t","vfat","-o",
                    f"ro,loop,offset={offset},sizelimit={length}",args.input,mnt)
                mounted=True
                original=verify(mnt)
                for name in ("boot.scr","mainline/stage2.scr"):
                    shutil.copyfile(mnt/name,temp/name.replace("/","_"))
                orig_init=temp/"original-initrd.gz"
                shutil.copyfile(mnt/"mainline/uart-diagnostic-initrd.gz",orig_init)
                run("umount",mnt);mounted=False
                new_init=build_initrd(orig_init,temp)
                shutil.copyfile(args.input,args.output);created=True
                run("mount","-t","vfat","-o",
                    f"rw,loop,offset={offset},sizelimit={length}",args.output,mnt)
                mounted=True
                shutil.copyfile(new_init,mnt/"mainline/uart-diagnostic-initrd.gz")
                run("sync")
                run("umount",mnt);mounted=False
                run("mount","-t","vfat","-o",
                    f"ro,loop,offset={offset},sizelimit={length}",args.output,mnt)
                mounted=True
                final=verify(mnt)
                for name in FILES:
                    if name!="mainline/uart-diagnostic-initrd.gz":
                        need(final[name]==original[name],"Boot file changed: "+name)
                need(final["mainline/uart-diagnostic-initrd.gz"]==sha(new_init),
                     "New initramfs hash mismatch")
                run("umount",mnt);mounted=False
                compare_region(args.input,args.output,0,32*1024*1024)
                compare_region(args.input,args.output,root_offset,root_length)
                output_hash=sha(args.output)
                Path(str(args.output)+".sha256").write_text(
                    f"{output_hash}  {args.output}\n")
                Path(str(args.output)+".manifest.txt").write_text(
                    "PCK600 RAM-only shell image, NOT HARDWARE TESTED\n"
                    f"Input: {args.input}\nOutput: {args.output}\n"
                    f"Image SHA256: {output_hash}\n"
                    f"Kernel unchanged SHA256: {KERNEL_SHA}\n"
                    f"DTB unchanged SHA256: {DTB_SHA}\n"
                    f"Old initrd SHA256: {sha(orig_init)}\n"
                    f"New initrd SHA256: {sha(new_init)}\n"
                    "Only FAT initramfs replaced. Firmware, boot scripts, kernel, DTB and ext4 unchanged.\n"
                )
                print("SUCCESS:",args.output)
                print("SHA256:",output_hash)
                print("Changed: FAT /mainline/uart-diagnostic-initrd.gz ONLY")
                print("Expected marker: PCK600-RAM-SHELL: /init entered")
                print("Hardware untested; spare microSD only.")
            finally:
                if mounted: run("umount",mnt)
    except BaseException:
        if created:
            args.output.unlink(missing_ok=True)
            Path(str(args.output)+".sha256").unlink(missing_ok=True)
            Path(str(args.output)+".manifest.txt").unlink(missing_ok=True)
        raise
if __name__=="__main__":
    main()
