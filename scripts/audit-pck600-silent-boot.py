#!/usr/bin/env python3
"""Compare PCK600/HDMI silent boot against the boot-proven RAM-B kernel.

Read-only. ARM64 image headers, stage4 config and RAM-B source config,
DTB hashes, and booti address overlap. No images are modified.
"""
from pathlib import Path
import hashlib
import struct
import argparse

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def image_info(path):
    d=path.read_bytes()
    if len(d)<64 or d[56:60]!=b"ARM\x64":
        raise ValueError(f"Not a raw ARM64 Image: {path}")
    offset,size,flags=struct.unpack_from("<QQQ",d,8)
    return {"file_bytes":len(d), "text_offset":offset,"image_size":size,
            "flags":hex(flags),"physical_range_if_0x41000000":(
                hex(0x41000000),hex(0x41000000+max(len(d),offset+size)))}

def config(path):
    data={}
    for l in path.read_text(errors="replace").splitlines():
        if l.startswith("CONFIG_") and "=" in l:
            k,v=l.strip().split("=",1)
            data[k]=v
        elif l.startswith("# CONFIG_") and l.endswith(" is not set"):
            data[l[2:].split(" ",1)[0]]="n"
    return data

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4"))
    ap.add_argument("--known-image",type=Path,default=Path("/home/Image-ram-b-script-fix"))
    ap.add_argument("--known-config",type=Path,default=Path("/root/opi3w-m2-work/ram-b-script-fix/obj/.config"))
    ap.add_argument("--known-dtb",type=Path,default=Path("/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb"))
    ap.add_argument("--output",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/SILENT-BOOT-AUDIT.txt"))
    a=ap.parse_args()
    candidate=a.root/"artifacts/Image-618-vendor-hdmi-pck600-syscon"
    candconfig=a.root/"artifacts/Image-618-vendor-hdmi-pck600-syscon.config"
    dtb=a.root/"artifacts/ram-b-26mhz-pck600-probe.dtb"
    for path in (a.known_image,a.known_config,a.known_dtb,candidate,candconfig,dtb):
        if not path.is_file():ap.error(f"Missing {path}")
    expected={
        str(a.known_image):"67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8",
        str(a.known_dtb):"1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d",
        str(candidate):"9f8c4af6f7f3d5ff604aac29bd7553e04dc3a41c0c8a5000308594c49ab5cb1c",
        str(dtb):"c5cc45413f4be4efbf80a1c26c061462e2a9b2e3649a49bf055b008d5209f697",
    }
    out=["A733 Linux 6.18 silent boot diagnostic, READ ONLY"]
    for path,h in expected.items():
        got=sha(Path(path))
        out.append(f"{path}\n  sha256={got}  {'PASS' if got==h else 'MISMATCH'}")
        if got!=h:raise SystemExit(f"STOP: wrong input {path}")
    for label,path in (("WORKING RAM-B",a.known_image),("SILENT PCK600",candidate)):
        out.append(f"\n=== {label}: ARM64 Image header ===")
        for k,v in image_info(path).items():out.append(f"  {k}: {v}")
    old,new=config(a.known_config),config(candconfig)
    wanted=[
        "CONFIG_BINFMT_ELF","CONFIG_BINFMT_SCRIPT","CONFIG_ARM64","CONFIG_EFI",
        "CONFIG_EFI_STUB","CONFIG_CMDLINE","CONFIG_CMDLINE_FORCE",
        "CONFIG_SERIAL_EARLYCON","CONFIG_SERIAL_8250","CONFIG_SERIAL_8250_CONSOLE",
        "CONFIG_SERIAL_8250_DW","CONFIG_SERIAL_8250_DWLIB","CONFIG_PRINTK",
        "CONFIG_EARLY_PRINTK","CONFIG_TTY","CONFIG_VT","CONFIG_VT_CONSOLE",
        "CONFIG_PROC_FS","CONFIG_SYSFS","CONFIG_DEVTMPFS","CONFIG_OF",
        "CONFIG_OF_EARLY_FLATTREE","CONFIG_PSTORE_RAM","CONFIG_KASAN",
        "CONFIG_RANDOMIZE_BASE","CONFIG_ARM64_VA_BITS","CONFIG_ARM64_PAGE_SHIFT",
        "CONFIG_ARM64_PAN","CONFIG_SUN60I_A733_CCU","CONFIG_SUN60I_A733_R_CCU",
        "CONFIG_SUN55I_PCK600","CONFIG_IOMMU_SUPPORT","CONFIG_DRM","CONFIG_AW_DRM",
        "CONFIG_FRAMEBUFFER_CONSOLE","CONFIG_INITRAMFS_SOURCE",
    ]
    out.append("\n=== Critical config comparison: WORKING | SILENT ===")
    for name in wanted:
        v1,v2=old.get(name,"absent"),new.get(name,"absent")
        out.append(f"{name}: {v1} | {v2} {'CHANGED' if v1!=v2 else ''}")
    out.append("\n=== All config differences (first 350) ===")
    keys=sorted(set(old)|set(new))
    diffs=[f"{k}: {old.get(k,'absent')} -> {new.get(k,'absent')}" for k in keys if old.get(k)!=new.get(k)]
    out.extend(diffs[:350])
    if len(diffs)>350:out.append(f"... {len(diffs)-350} more diffs omitted")
    out.append(f"\nTOTAL config changes: {len(diffs)}")
    out.append("Do not infer PCK600 failure from a silent kernel. Separate kernel regression from DTB variant.")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text("\n".join(out)+"\n")
    print("\n".join(out[:len(expected)*2+55]))
    print(f"\nDetailed report: {a.output}")
if __name__=="__main__":main()
