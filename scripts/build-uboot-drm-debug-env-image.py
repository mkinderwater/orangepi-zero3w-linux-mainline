#!/usr/bin/env python3
"""Experimental U-Boot drm_debug=1 env test image for A733/Orange Pi Zero 3W.

Make a distinct copy of the proven RAM-shell raw image, adding only the
U-Boot EXT4 environment file '/uboot.env' to ext4 partition 1. Leaves
original firmware, FAT boot files, kernel, PCK600 DTB and initrd unchanged.

IMPORTANT: installed U-Boot (2018.07-orangepi-config-dirty) contains strings
'drm_debug' and 'uboot.env', but its compiled environment device/partition
and initial load timing have NOT been established. Image is unverified.
Use a spare SD only. No saveenv, no bootloader rebuild.

Environment is intentionally minimal: 'drm_debug=1', 'bootdelay=3' and
'bootcmd=run distro_bootcmd' (the latter preserves the observed bootcmd).
It does not claim to preserve runtime-generated environment variables;
if loaded successfully, all other U-Boot environment entries may be absent.
The diagnostic remains manually bootable from the U-Boot prompt.

For source default environment preservation, provide --env-text pointing to
a *complete* NUL-free dump of the installed board's 'printenv' output.
It will preserve those entries and override drm_debug, bootdelay, bootcmd.
Do not share private serial numbers included in such dumps.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zlib

DEFAULT_INPUT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/opi3w-618-pck600-ram-shell.img")
DEFAULT_OUTPUT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/opi3w-618-pck600-drm-debug1-ext4-env.img")
PART_START=196608 * 512
PART_SIZE=3997696 * 512
FAT_START=65536 * 512
FAT_SIZE=131072 * 512
ENV_SIZE=131072

def sh(*args,**kwargs):
    return subprocess.run([str(v) for v in args],check=True,**kwargs)

def digest(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(4*1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def stop_if(not_ok,msg):
    if not_ok:raise RuntimeError("STOP: "+msg)

def parse_env_file(path):
    entries={}
    if path:
        for line in path.read_text().splitlines():
            line=line.strip()
            if not line or line.startswith("#") or line.startswith("=> ") or line.startswith("Environment size:"):
                continue
            if line.startswith("printenv") or line.startswith("arch=") and False:
                continue
            if "=" not in line:continue
            k,v=line.split("=",1)
            if not k.isascii() or not k.replace("_","").isalnum() or not k:
                continue
            stop_if("\x00" in v,"NUL in environment value")
            entries[k]=v
    # All builds must be interactive even if the copied env has no bootcmd.
    # Preserve observed default behavior if no complete env dump provided.
    entries.setdefault("bootcmd","run distro_bootcmd")
    entries["bootdelay"]="3"
    entries["drm_debug"]="1"
    return entries

def create_blob(entries):
    payload=b"".join(k.encode()+b"="+v.encode()+b"\0" for k,v in entries.items())+b"\0"
    stop_if(len(payload)>ENV_SIZE-4,"U-Boot env too large")
    data=payload.ljust(ENV_SIZE-4,b"\0")
    return struct.pack("<I",zlib.crc32(data)&0xffffffff)+data

def compare_region(a,b,start,size):
    with a.open("rb") as x,b.open("rb") as y:
        x.seek(start); y.seek(start)
        while size:
            n=min(4*1024*1024,size)
            stop_if(x.read(n)!=y.read(n),"immutable region differs at "+hex(start))
            start+=n;size-=n

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=DEFAULT_INPUT)
    p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    p.add_argument("--env-text",type=Path,help="Optional complete 'printenv' text file from same board")
    a=p.parse_args()
    stop_if(os.geteuid()!=0,"requires root to loop mount ext4")
    for tool in ("mount","umount","e2fsck","sync"):
        stop_if(shutil.which(tool) is None,"missing tool "+tool)
    stop_if(not a.input.is_file(),"source image missing")
    stop_if(a.output.exists(),"output already exists, refusing to overwrite")
    stop_if(a.input.resolve()==a.output.resolve(),"input and output identical")
    stop_if(a.input.stat().st_size<PART_START+PART_SIZE,"source image smaller than expected partition")
    stop_if(a.env_text is not None and not a.env_text.is_file(),"--env-text not found")
    entries=parse_env_file(a.env_text)
    blob=create_blob(entries)
    stop_if(zlib.crc32(blob[4:])&0xffffffff!=struct.unpack_from("<I",blob)[0],"internal CRC mismatch")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    created=False
    with tempfile.TemporaryDirectory() as t:
        m=Path(t)/"root";m.mkdir()
        mounted=False
        try:
            # Prevent accidental images with incompatible geometry.
            import json
            parts=json.loads(subprocess.check_output(["sfdisk","-J",str(a.input)]))["partitiontable"]["partitions"]
            stop_if(not any(int(x["start"])==196608 and int(x["size"])==3997696 for x in parts),
                    "source ext4 geometry does not match baseline")
            stop_if(not any(int(x["start"])==65536 and int(x["size"])==131072 for x in parts),
                    "source FAT geometry does not match baseline")
            shutil.copyfile(a.input,a.output)
            created=True
            sh("mount","-t","ext4","-o",f"rw,loop,offset={PART_START},sizelimit={PART_SIZE}",a.output,m)
            mounted=True
            f=m/"uboot.env"
            stop_if(f.exists(),"source already contains /uboot.env, refusing overwrite")
            f.write_bytes(blob)
            os.chmod(f,0o644)
            sh("sync")
            sh("umount",m);mounted=False
            sh("e2fsck","-fn",a.output) if False else None  # Never fsck whole disk image as ext4.
            sh("mount","-t","ext4","-o",f"ro,noload,loop,offset={PART_START},sizelimit={PART_SIZE}",a.output,m)
            mounted=True
            stop_if((m/"uboot.env").read_bytes()!=blob,"on-image env mismatch")
            sh("umount",m);mounted=False
            compare_region(a.input,a.output,0,FAT_START)
            compare_region(a.input,a.output,FAT_START,FAT_SIZE)
            end=PART_START+PART_SIZE
            compare_region(a.input,a.output,end,a.input.stat().st_size-end)
            hashval=digest(a.output)
            Path(str(a.output)+".sha256").write_text(f"{hashval}  {a.output}\n")
            Path(str(a.output)+".manifest.txt").write_text(
                "EXPERIMENTAL, NOT HARDWARE TESTED\n"
                f"Input: {a.input}\nInput SHA256: {digest(a.input)}\n"
                f"Output: {a.output}\nOutput SHA256: {hashval}\n"
                "Only ext4 partition filesystem changed: added /uboot.env.\n"
                "Firmware first 32 MiB and FAT boot partition verified identical.\n"
                "The installed firmware's environment location and load timing are UNVERIFIED.\n"
                "U-Boot env format: CRC32 little-endian + 131068-byte data, total 131072 bytes.\n"
                "Boot settings included: drm_debug=1, bootdelay=3, bootcmd=run distro_bootcmd.\n"
                f"Other entries: {'provided printenv text' if a.env_text else 'NONE; diagnostic only'}.\n"
                "If U-Boot reads this file, it may discard other runtime settings.\n"
                "Do NOT run saveenv. Test on spare microSD only.\n"
            )
            print("Created experimental image:",a.output)
            print("SHA256:",hashval)
            print("Expected test: cold boot HDMI connected; inspect UART pre-prompt, printenv drm_debug.")
            print("No guarantee installed firmware loads this /uboot.env file.")
        except BaseException:
            if created:
                a.output.unlink(missing_ok=True)
                Path(str(a.output)+".sha256").unlink(missing_ok=True)
                Path(str(a.output)+".manifest.txt").unlink(missing_ok=True)
            raise
        finally:
            if mounted:sh("umount",m)
if __name__=="__main__":
    main()
