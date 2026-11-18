#!/usr/bin/env python3
"""Stage A733 IOMMU-v20 for an ISOLATED source-only compiler diagnostic.

Does not build bootable images, modify vendor/stage4 source, or change firmware.
A successful compile does NOT authorize hardware probing or display DMA use.
"""
from __future__ import annotations
import argparse, hashlib, os, pathlib, shutil, subprocess, sys
VENDOR=pathlib.Path("/root/opi3w-vendor-6698-work/kernel")
KERNEL=pathlib.Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/linux")
OUT=pathlib.Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1")
EXPECTED_CONFIG_SHA="f98a84b103b7fb897f4bd962ac4f13a8d0b614cd8a3ec206eda80d18b3174be5"
FILES=("sunxi-iommu-v2.c","sunxi-iommu-common.c","sunxi-iommu-pgtable.c",
       "sunxi-iommu-pgtable.h","sunxi-iommu.h")
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""): h.update(b)
    return h.hexdigest()
def run(cmd,log,env=None):
    with log.open("a") as f:
        f.write("\n$ "+" ".join(str(c) for c in cmd)+"\n");f.flush()
        p=subprocess.run([str(c) for c in cmd],stdout=f,stderr=subprocess.STDOUT,env=env)
        f.write("exit_code="+str(p.returncode)+"\n")
    return p.returncode
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--vendor",type=pathlib.Path,default=VENDOR)
    p.add_argument("--linux",type=pathlib.Path,default=KERNEL)
    p.add_argument("--out",type=pathlib.Path,default=OUT)
    p.add_argument("--config",type=pathlib.Path,help="Existing Stage 4 kernel configuration file")
    p.add_argument("--jobs",type=int,default=2)
    p.add_argument("--cross-compile",default="aarch64-linux-gnu-",help="ARM64 cross-toolchain prefix")
    p.add_argument("--stage-only",action="store_true")
    a=p.parse_args()
    if a.out.exists(): sys.exit("STOP: output already exists; choose fresh --out")
    if a.jobs<1 or a.jobs>16:sys.exit("STOP: jobs must be 1..16")
    source=a.vendor/"bsp/drivers/iommu"
    for q in [a.linux/"Makefile",a.linux/"Kconfig",source/"Makefile",*[source/f for f in FILES]]:
        if not q.is_file():sys.exit("STOP: source missing "+str(q))
    if not (a.linux/"scripts/config").is_file():sys.exit("STOP: missing Linux scripts/config")
    # The validated Stage 4 config may be archived outside the source tree.
    # Only accept the precise hash recorded with the compiled Stage 4 kernel.
    artifacts=a.linux.parent/"artifacts"
    candidates=[
        a.linux/".config",
        artifacts/"Image-618-vendor-hdmi-pck600-syscon.config",
        artifacts/".config",
        artifacts/"linux-618.config",
    ]
    if a.config is not None:
        candidates=[a.config]
    config=next((p for p in candidates if p.is_file() and sha(p)==EXPECTED_CONFIG_SHA),None)
    if config is None:
        for pth in candidates:
            if pth.is_file():
                print("REJECT: unexpected config hash:",pth,sha(pth),file=sys.stderr)
        sys.exit(
            "STOP: validated Stage 4 .config not found. Locate it read-only with:\n"
            "find /root/opi3w-m2-work/linux-618-hdmi-stage4 -type f "
            "\\( -name '.config' -o -name '*.config' \\) -print\n"
            "Then rerun with --config /absolute/path/to/config; expected SHA256 "
            + EXPECTED_CONFIG_SHA)
    cfg_text=config.read_text(errors="replace")
    if "CONFIG_ARM64=y" not in cfg_text:
        sys.exit("STOP: archived config lacks CONFIG_ARM64=y")
    gcc=a.cross_compile+"gcc"
    readelf=a.cross_compile+"readelf"
    if not shutil.which(gcc):sys.exit("STOP: ARM64 cross-compiler not found: "+gcc)
    if not shutil.which(readelf):
        readelf=shutil.which("readelf")
    if not readelf:sys.exit("STOP: readelf unavailable for ELF verification")
    # Staging must not be nested within either input kernel tree.
    out=a.out.resolve()
    for root in (a.linux.resolve(),a.vendor.resolve()):
        if out==root or root in out.parents:sys.exit("STOP: output nested inside an input tree")
    a.out.mkdir(parents=True)
    work=a.out/"linux"
    log=a.out/"build.log"
    manifest=a.out/"manifest.txt"
    # Copy the exact patched 6.18 source, including its existing staged uncommitted patches.
    # cp --reflink=auto is GNU coreutils: falls back to full copy if reflinks unavailable.
    rc=run(["cp","-a","--reflink=auto",str(a.linux)+"/.",str(work)],log)
    if rc:sys.exit("STOP: source copy failed; see "+str(log))
    shutil.copy2(config,work/".config")
    target=work/"drivers/iommu/aw-v20"
    target.mkdir(parents=True,exist_ok=False)
    for name in FILES:shutil.copy2(source/name,target/name)
    # Keep vendor sources untouched, and NEVER make this driver eligible to link
    # into a boot image at this stage. This subdir's object target is diagnostic only.
    (target/"Makefile").write_text(
        "obj-y += sunxi-iommu-v20.o sunxi-iommu-common.o sunxi-iommu-pgtable.o\n")
    # Do not put CONFIG_* into the main Kconfig/Makefile yet. The Makefile target
    # compiles standalone objects without registering any driver in the kernel.
    manifest.write_text(
        "A733 IOMMU v20 stage1, source-only compile diagnostic\n"
        "No Kconfig additions, DTB modifications, or kernel image updates.\n"
        "Stage Linux source: "+str(a.linux)+"\n"
        "Stage vendor source: "+str(source)+"\n"
        "Architecture: arm64\n"+"Cross compiler: "+gcc+"\n"+
        "Validated configuration: "+str(config)+"\n"
        "Linux .config SHA256: "+sha(config)+"\n"+
        "\n".join(name+" SHA256 "+sha(source/name) for name in FILES)+"\n")
    if a.stage_only:
        print("STAGED (no compilation):",a.out);return
    # Running the exact directory target may fail at the first old API/compiler
    # mismatch. Preserve full diagnostics and return a nonzero code on failure.
    env=os.environ.copy()
    env["KBUILD_BUILD_TIMESTAMP"]="1970-01-01"
    env["ARCH"]="arm64"
    env["CROSS_COMPILE"]=a.cross_compile
    env.pop("CC",None)
    env.pop("HOSTCC",None)
    # Enable only in this copied build tree. Otherwise CONFIG_IOMMU_SUPPORT=n
    # exposes stub iommu_ops definitions and floods the compiler with false
    # API errors. Do not change the validated archived config or live tree.
    rc=run([str(work/"scripts/config"),"--file",str(work/".config"),
            "-e","IOMMU_SUPPORT","-e","IOMMU_DMA"],log,env)
    if rc:
        print("ISOLATED CONFIG ENABLE FAIL; log:",log)
        sys.exit(rc)
    rc=run(["make","-C",str(work),"olddefconfig"],log,env)
    if not rc:
        rc=run(["make","-C",str(work),"-j"+str(a.jobs),"prepare"],log,env)
    cfg_after=(work/".config").read_text(errors="replace")
    for opt in ("CONFIG_IOMMU_SUPPORT=y","CONFIG_IOMMU_DMA=y","CONFIG_ARM64=y"):
        if opt not in cfg_after:
            with log.open("a") as lf:
                lf.write("ERROR: isolated config missing required option "+opt+"\n")
            sys.exit("STOP: isolated config did not retain "+opt)
    with manifest.open("a") as mf:
        mf.write("Isolated IOMMU-enabled config SHA256: "+sha(work/".config")+"\n")
    if rc:
        with manifest.open("a") as f:f.write("Kernel prepare failed: "+str(rc)+"\n")
        print("PREPARE FAIL; log:",log)
        sys.exit(rc)
    # Explicit single-object targets bypass missing parent Makefile wiring.
    # Merely building the directory yielded a false PASS in Stage 1.
    objects=("sunxi-iommu-v2.o","sunxi-iommu-common.o","sunxi-iommu-pgtable.o")
    status=0
    for obj in objects:
        target_obj="drivers/iommu/aw-v20/"+obj
        rc=run(["make","-C",str(work),"-j"+str(a.jobs),"V=0",target_obj],log,env)
        if rc:
            status=rc
            break
        objpath=work/target_obj
        if not objpath.is_file() or objpath.stat().st_size==0:
            with log.open("a") as lf:lf.write("ERROR: Kbuild returned zero but object missing: "+str(objpath)+"\n")
            status=11
            break
        cp=subprocess.run([readelf,"-h",str(objpath)],text=True,capture_output=True)
        if cp.returncode or "Machine:" not in cp.stdout or "AArch64" not in cp.stdout:
            with log.open("a") as lf:
                lf.write("ERROR: object architecture is not AArch64: "+str(objpath)+"\\n"+cp.stdout+cp.stderr)
            status=12
            break
        with manifest.open("a") as mf:
            mf.write(obj+" SHA256 "+sha(objpath)+" (AArch64 ELF)\\n")
    with manifest.open("a") as mf:mf.write("Compile-only return code: "+str(status)+"\n")
    print("STAGED:",a.out)
    print("COMPILE", "PASS: all three AArch64 objects generated (not hardware validated)" if status==0 else "FAIL: inspect first compiler error")
    print("LOG:",log)
    if status:sys.exit(status)
if __name__=="__main__":main()
