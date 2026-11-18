#!/usr/bin/env python3
"""Build a *separate* U-Boot T736 no-logo candidate for A733 experiments.

Modifies exactly the two sunxi_show_logo calls in board_env_late_init()
inside a cloned checkout. Never writes a disk image, firmware, or U-Boot env.
The downloaded vendor source is NOT an exact match to installed 2018.07 U-Boot.
Outputs are NOT flash-ready without a separate compatibility/package audit.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess

SOURCE_REV = "b791be842935b27268ae3d00e943a9075495f30a"
SOURCE_DEFAULT = Path("/root/opi3w-uboot-audit/u-boot-orangepi")
OUT_DEFAULT = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/uboot-no-logo-isolation")
BOARD_FILE = Path("board/sunxi/board_common.c")
DEFCONFIG = "sun60iw2p1_t736_defconfig"

def run(args, *, cwd=None, logfile=None):
    p = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, check=False)
    if logfile is not None:
        logfile.write_text(p.stdout)
    print(p.stdout[-3500:], end="")
    if p.returncode != 0:
        raise RuntimeError(f"STOP: command failed ({p.returncode}): {' '.join(map(str,args))}")
    return p.stdout

def require(ok, why):
    if not ok:
        raise RuntimeError("STOP: "+why)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--cross", default=os.environ.get("CROSS_COMPILE","arm-linux-gnueabi-"))
    parser.add_argument("--jobs", type=int, default=4)
    a=parser.parse_args()
    require(a.jobs>=1, "jobs must be >=1")
    require((a.source/".git").exists(), "local U-Boot source missing")
    require(not a.output.exists(), "refuse to overwrite output directory")
    for binary in ("git","make", a.cross+"gcc",a.cross+"ld"):
        require(shutil.which(binary), "missing executable "+binary)
    head=run(["git","rev-parse","HEAD"],cwd=a.source).strip()
    require(head==SOURCE_REV, "source revision differs; inspect before build")
    clean=run(["git","status","--porcelain"],cwd=a.source)
    require(not clean.strip(), "source checkout has local changes")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    run(["git","clone","--local","--no-hardlinks","--quiet",
         str(a.source.resolve()),str(a.output.resolve())])
    run(["git","checkout","--detach","--quiet",SOURCE_REV],cwd=a.output)
    evidence=a.output/"evidence"
    evidence.mkdir()
    file=a.output/BOARD_FILE
    text=file.read_text()
    old='run_command("sunxi_show_logo", 0);'
    start=text.find("int board_env_late_init(void)")
    require(start>=0,"board_env_late_init not found")
    following=re.search(r"\n(?:static )?(?:int|void) [A-Za-z_]\w*\s*\(",text[start+10:])
    end=start+10+following.start() if following else len(text)
    block=text[start:end]
    require(block.count(old)==2, "expected exactly TWO logo callsites in board_env_late_init")
    require(text.count(old)==2, "unexpected other logo callsites")
    require("#ifdef CONFIG_AW_DRM" in block, "missing AW_DRM branch")
    new='printf("A733-ISOLATION: skipped U-Boot DRM logo\\n");'
    file.write_text(text[:start]+block.replace(old,new)+text[end:])
    changed=run(["git","diff","--name-only"],cwd=a.output).strip()
    require(changed==str(BOARD_FILE),"unexpected source changes: "+changed)
    run(["git","diff","--check"],cwd=a.output)
    patch=run(["git","diff","--",str(BOARD_FILE)],cwd=a.output)
    (evidence/"no-logo-only.patch").write_text(patch)
    (evidence/"STATUS.txt").write_text(
        "Source-only U-Boot experimental no-logo bypass, UNTESTED on hardware.\n"
        f"Base git commit: {SOURCE_REV}\nConfig: {DEFCONFIG}\n"
        "Change: replace two logo calls in board_env_late_init with print markers.\n"
        "Firmware Boot0/BL31/SCP and existing images UNCHANGED.\n"
        "The actual installed U-Boot is 2018.07-orangepi-config-dirty,\n"
        "whereas this source is a 2018.05-derived branch.\n"
        "This bypass does not prove that all early DRM probes are disabled.\n"
        "Do not flash binary without packaging, ABI and recovery validation.\n"
    )
    env=os.environ.copy()
    env.update({"ARCH":"arm","CROSS_COMPILE":a.cross})
    build=a.output/"out"
    def do_make(targets,log):
        args=["make","-C",str(a.output),"O="+str(build)]+targets
        with (evidence/log).open("w") as writer:
            p=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,text=True)
            tail=[]
            for line in p.stdout:
                writer.write(line)
                tail.append(line)
                if len(tail)>50:tail.pop(0)
            result=p.wait()
        print("".join(tail))
        require(result==0,f"{log} failed, see evidence")
    do_make([DEFCONFIG],"configure.log")
    cfg=(build/".config").read_text()
    require("CONFIG_AW_DRM=y\n" in cfg,"built config missing AW_DRM")
    require('CONFIG_DEFAULT_DEVICE_TREE="sun60iw2p1-soc-system"' in cfg,
            "unexpected selected DTB")
    do_make(["-j",str(a.jobs)],"build.log")
    artifacts=[]
    for name in ("u-boot.bin","u-boot-dtb.bin","u-boot-sunxi-with-spl.bin","u-boot.fex","u-boot"):
        p=build/name
        if p.is_file():
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            artifacts.append(f"{h}  {p}")
    require(artifacts,"no recognized U-Boot build artifact")
    (evidence/"artifacts.sha256").write_text("\n".join(artifacts)+"\n")
    print("SOURCE ISOLATION BUILD PASS, NOT FLASH READY")
    print("\n".join(artifacts))
    print("Evidence:",evidence)
    print("STOP before flashing. Installed binary packaging and source equivalence not verified.")

if __name__=="__main__":
    main()
