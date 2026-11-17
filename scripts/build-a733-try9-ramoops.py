#!/usr/bin/env python3
"""Build experimental RAM-A + ramoops diagnostics (try9).

No writes to physical media. Keep known-good RAM-A untouched.
Uses standard upstream Linux PSTORE_RAM and PSTORE_CONSOLE. On some Allwinner
Boot0 resets, DRAM is reinitialized and the record will NOT survive.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

MEM_START=0x7c000000
MEM_SIZE=0x00100000
FAT_OFFSET=33554432
def run(*args):
    argv=[str(v) for v in args]
    print("+"," ".join(argv),flush=True)
    subprocess.run(argv,check=True)
def capture(*args):
    return subprocess.check_output([str(v) for v in args],text=True).strip()
def sha(p):
    d=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):d.update(b)
    return d.hexdigest()
def cells(dtb,node,key):
    return [int(x,16) for x in capture("fdtget","-t","x",dtb,node,key).split()]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source",required=True,type=Path,help="Built, tested Try8A Linux source")
    ap.add_argument("--config",required=True,type=Path,help="Try8A kernel .config")
    ap.add_argument("--soc-source",required=True,type=Path,help="Linux source with upstream A733 v3 SoC DTS")
    ap.add_argument("--control",required=True,type=Path,help="Original 2GiB RAM-A SD image")
    ap.add_argument("--output",required=True,type=Path,help="NEW output folder")
    ap.add_argument("--jobs",type=int,default=4)
    a=ap.parse_args()
    src=a.source.resolve(); soc=a.soc_source.resolve(); original=a.control.resolve()
    out=a.output.resolve()
    root=Path(__file__).resolve().parent.parent
    dts=root/"dts/sun60i-a733-orangepi-zero3w-ram-a.dts"
    if out.exists() or out==src or out in src.parents:
        ap.error("Output overlaps input or already exists")
    if not (src/"Makefile").is_file() or not (soc/"arch/arm64/boot/dts/allwinner/sun60i-a733.dtsi").is_file():
        ap.error("Missing prepared source or A733 DTS")
    if not (dts.is_file() and a.config.is_file() and original.is_file()):
        ap.error("Missing RAM-A DTS, .config or SD image")
    if original.stat().st_size!=2147483648:
        ap.error("Expected exactly 2GiB RAM-A SD image")
    if a.jobs<1 or a.jobs>64:ap.error("jobs must be 1..64")
    for prog in ("cp","make","cpp","dtc","fdtget","mcopy"):
        if not shutil.which(prog):ap.error("Missing "+prog)
    out.mkdir(parents=True)
    report={"state":"INIT","persistence":"UNVERIFIED: Boot0 may reinitialize DRAM",
            "ramoops_start":hex(MEM_START),"ramoops_size":hex(MEM_SIZE),
            "source":str(src),"control_sha256":sha(original)}
    def save():(out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    save()
    try:
        tree=out/"linux"
        run("cp","-a","--reflink=auto",src,tree)
        obj=out/"obj";obj.mkdir()
        shutil.copy2(a.config.resolve(),obj/".config")
        c=tree/"scripts/config"
        if not c.is_file():raise RuntimeError("Linux scripts/config missing")
        # Linux 6.18 fs/Kconfig sources fs/pstore/Kconfig only when
        # CONFIG_MISC_FILESYSTEMS is enabled. Without this, olddefconfig
        # silently drops every requested PSTORE option.
        run(c,"--file",obj/".config","--enable","MISC_FILESYSTEMS",
            "--enable","PSTORE","--enable","PSTORE_RAM",
            "--enable","PSTORE_CONSOLE","--enable","PSTORE_PMSG",
            "--disable","PSTORE_COMPRESS")
        run("make","-C",tree,"O="+str(obj),"ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-","olddefconfig")
        cfg=(obj/".config").read_text()
        for flag in ("CONFIG_MISC_FILESYSTEMS=y","CONFIG_PSTORE=y","CONFIG_PSTORE_RAM=y","CONFIG_PSTORE_CONSOLE=y","CONFIG_PSTORE_PMSG=y"):
            if flag not in cfg:raise RuntimeError("Pstore setting missing after olddefconfig: "+flag)
        run("make","-C",tree,"O="+str(obj),"ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-","-j"+str(a.jobs),"Image")
        kernel=obj/"arch/arm64/boot/Image"
        # Only add an isolated reserved-memory node; preserve BL31 and RAM size.
        data=dts.read_text()
        anchor='''\t\tbl31@48000000 {
\t\t\treg = <0x0 0x48000000 0x0 0x01000000>;
\t\t\tno-map;
\t\t};'''
        if data.count(anchor)!=1:raise RuntimeError("BL31 DT anchor changed")
        node='''
\t\t/* Try9 only: console/oops records; retention after Boot0 is unproven. */
\t\tramoops@7c000000 {
\t\t\tcompatible = "ramoops";
\t\t\treg = <0x0 0x7c000000 0x0 0x00100000>;
\t\t\tno-map;
\t\t\trecord-size = <0x00010000>;
\t\t\tconsole-size = <0x00040000>;
\t\t\tpmsg-size = <0x00010000>;
\t\t\tecc-size = <16>;
\t\t};'''
        board=out/"ram-a-ramoops.dts"
        board.write_text(data.replace(anchor,anchor+node,1).replace(
            "RAM-A full + BL31 reserved","RAM-A + ramoops diagnostic"))
        prep=out/"board.preprocessed.dts"; dtb=out/"sun60i-a733-orangepi-zero3w.dtb"
        socdir=soc/"arch/arm64/boot/dts/allwinner"
        run("cpp","-nostdinc","-undef","-D__DTS__",
            "-I",soc/"include","-I",socdir,"-x","assembler-with-cpp","-o",prep,board)
        run("dtc","-I","dts","-O","dtb","-o",dtb,prep)
        if cells(dtb,"/memory@40000000","reg")!=[0,0x40000000,0,0x40000000]:
            raise RuntimeError("RAM-A 1GiB not retained")
        if cells(dtb,"/reserved-memory/bl31@48000000","reg")!=[0,0x48000000,0,0x01000000]:
            raise RuntimeError("BL31 reservation changed")
        nodepath="/reserved-memory/ramoops@7c000000"
        if cells(dtb,nodepath,"reg")!=[0,MEM_START,0,MEM_SIZE]:
            raise RuntimeError("Ramoops memory region changed")
        if capture("fdtget","-t","s",dtb,nodepath,"compatible")!="ramoops":
            raise RuntimeError("Ramoops compatible missing")
        if "no-map" not in capture("fdtget","-p",dtb,nodepath).split():
            raise RuntimeError("Missing no-map")
        image=out/"a733-try9-ramoops.img"
        run("cp","--reflink=auto","--sparse=always","--",original,image)
        fat=str(image)+"@@"+str(FAT_OFFSET)
        run("mcopy","-o","-i",fat,kernel,"::mainline/Image")
        run("mcopy","-o","-i",fat,dtb,"::mainline/sun60i-a733-orangepi-zero3w.dtb")
        for name,path in [("Image",kernel),("sun60i-a733-orangepi-zero3w.dtb",dtb)]:
            readback=out/("readback-"+name)
            run("mcopy","-i",fat,"::mainline/"+name,readback)
            if sha(readback)!=sha(path):raise RuntimeError("FAT roundtrip mismatch: "+name)
        report.update(state="IMAGE_STAGED_UNBOOTED",image=str(image),
                      image_sha256=sha(image),kernel_sha256=sha(kernel),
                      dtb_sha256=sha(dtb),ramoops_support="CONFIG_PSTORE_RAM=y")
        save()
        print("RESULT: IMAGE_STAGED_UNBOOTED")
        print("IMAGE:",image)
        print("SHA256:",report["image_sha256"])
    except Exception as e:
        report.update(state="FAILED",error=str(e));save();raise

if __name__=="__main__":main()
