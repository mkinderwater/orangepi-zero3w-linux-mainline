#!/usr/bin/env python3
"""Read-only A733 HDMI handoff audit, Linux 6.18 versus vendor firmware.

No writing to input images, source trees, SD cards, DTBs, environment or clocks.
Inputs are existing host files from the PCK600/HDMI investigation.
Output is a text report and optional DTS extracts inside --output.

The tool distinguishes *source evidence* from *hardware observation*;
it never claims an installed U-Boot binary matches the source.
"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess

DEFAULT_ROOT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4")
DEFAULT_SOURCE=Path("/root/opi3w-uboot-audit/u-boot-orangepi")
DEFAULT_TEST_DTB=DEFAULT_ROOT/"artifacts/ram-b-26mhz-pck600-probe.dtb"
DEFAULT_VENDOR_DTS=DEFAULT_ROOT/"vendor-dtb-topology/vendor-control.dts"
DEFAULT_CONFIG=DEFAULT_ROOT/"artifacts/Image-618-vendor-hdmi-pck600-syscon.config"
DEFAULT_FIRMWARE=Path("/root/opi3w-m2-work/uboot-firmware-audit/boot-region.bin")

NODES = ["sunxi-drm","/soc/de","de@5000000","tcon3@5730000","tcon4@5731000",
         "hdmi0@5520000","pck-600","power-controller","iommu"]
CLOCKS = ["clk_hdmi_tv","CLK_HDMI_TV","CLK_TCONTV0","CLK_TCONTV1",
          "CLK_BUS_HDMI_TV","CLK_BUS_TCONTV0","CLK_BUS_TCONTV1",
          "hdmi-tv","hdmi-cec","hdmi-sfr","video0","video1","pll-ref"]
SOURCE_AREAS = [
 ("U-Boot pre-prompt and logo", "board/sunxi/board_common.c",
  ("int board_early_init_r(", "int board_env_late_init(",
   "int initr_sunxi_display(", "sunxi_show_logo")),
 ("U-Boot boot-time sequence", "common/board_r.c",
  ("static int initr_sunxi_plat(", "static int initr_env(", "init_sequence_r[]")),
 ("U-Boot display probe / handoff", "drivers/video/drm/sunxi_drm_drv.c",
  ("int check_drm_debug_mode(", "struct sunxi_drm_device *sunxi_drm_device_get(",
   "int sunxi_drm_kernel_para_flush(", "static int sunxi_de_add_kernel_iova_premap(")),
 ("U-Boot HDMI and HPD", "drivers/video/drm/sunxi_drm_hdmi.c",
  ("static int _sunxi_drv_hdmi_hpd_get(", "int sunxi_drm_hdmi_probe(")),
 ("U-Boot env backend", "env/ext4.c", ("static int env_ext4_load(",)),
]
def sh(*args):
    return subprocess.run([str(a) for a in args],text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,check=False)
def hash_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()
def read(path):
    try: return path.read_text(errors="replace")
    except OSError: return ""
def matches(text, terms, limit=45):
    return [(n,line.rstrip()[:220]) for n,line in enumerate(text.splitlines(),1)
            if any(term.lower() in line.lower() for term in terms)][:limit]
def selection(lines, anchor, context=9):
    hits=[i for i,x in enumerate(lines) if anchor in x]
    if not hits:return ["NOT FOUND: "+anchor]
    result=[]
    for idx in hits[:2]:
        for j in range(max(0,idx-context),min(len(lines),idx+context+1)):
            result.append(str(j+1)+": "+lines[j])
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,default=DEFAULT_SOURCE)
    p.add_argument("--test-dtb",type=Path,default=DEFAULT_TEST_DTB)
    p.add_argument("--vendor-dts",type=Path,default=DEFAULT_VENDOR_DTS)
    p.add_argument("--kernel-config",type=Path,default=DEFAULT_CONFIG)
    p.add_argument("--firmware-prefix",type=Path,default=DEFAULT_FIRMWARE)
    p.add_argument("--output",type=Path,default=DEFAULT_ROOT/"artifacts/hdmi-handoff-offline")
    a=p.parse_args()
    if a.output.exists(): raise SystemExit("STOP: output directory exists; use a new --output")
    a.output.mkdir(parents=True)
    out=["A733 HDMI / U-Boot / Linux 6.18 OFFLINE EVIDENCE AUDIT",
         "Status: source and DT inspections only; no new hardware test",
         "Source references do not prove installed 2018.07 firmware uses identical code.",
         "Public Linux 7.4 CCU v7 series: https://lists.openwall.net/linux-kernel/2026/11/12/989",
         "Same-board clock handoff report: https://github.com/aricshow/orangepi-zero3w-armbian-cyberdeck-mods",
         ""]
    for name,path in [("U-Boot source",a.source),("Linux diagnostic DTB",a.test_dtb),
                      ("vendor reference DTS",a.vendor_dts),
                      ("6.18 kernel config",a.kernel_config),
                      ("installed firmware prefix",a.firmware_prefix)]:
        out.append(name+": "+str(path))
        if path.is_file():
            out.append("  SHA256: "+hash_file(path))
        elif not path.exists():out.append("  MISSING (no inference from absent file)")
    out.append("\n== U-Boot early stage, environment, DRM/logo and FDT handoff ==")
    for label,relative,anchors in SOURCE_AREAS:
        file=a.source/relative
        lines=read(file).splitlines()
        out+=["\n-- "+label+" / "+relative+" --"]
        if not lines:
            out.append("MISSING source file")
            continue
        for anchor in anchors:
            out+=["\n"+anchor]+selection(lines,anchor,7)
    out.append("\n== Actual U-Boot source branch and config ==")
    cfg=a.source/"configs/sun60iw2p1_t736_defconfig"
    cfgtext=read(cfg)
    out.extend(str(i)+": "+s for i,s in matches(cfgtext,
        ["CONFIG_AW_DRM","CONFIG_DISP2","CONFIG_BOOT_GUI","CONFIG_ENV_IS_IN",
         "CONFIG_DEFAULT_DEVICE_TREE","CONFIG_CLK_SUNXI"]))
    if (a.source/".git").exists():
        r=sh("git","-C",a.source,"rev-parse","HEAD")
        out.append("U-Boot source commit: "+r.stdout.strip() if r.returncode==0 else
                   "Could not read source commit")
    out.append("\n== Compiled firmware strings: indicate presence only ==")
    if a.firmware_prefix.exists():
        d=a.firmware_prefix.read_bytes()
        for m in re.finditer(rb"[\x20-\x7e]{6,}",d):
            item=m.group().decode("ascii","replace")
            if any(term in item.lower() for term in
                  ["drm_debug","sunxi_show_logo","uboot.env","u-boot 2018.07",
                   "load-environment","environment from"]):
                out.append(hex(m.start())+": "+item[:175])
    else:out.append("MISSING firmware prefix")
    out.append("\n== Device-tree tree and display dependencies ==")
    vendor_text=read(a.vendor_dts)
    if vendor_text:
        for term in NODES+CLOCKS:
            found=matches(vendor_text,[term],limit=12)
            out.append("\nVendor "+term+": "+str(len(found))+" matching lines (max 12)")
            out.extend(str(i)+": "+s for i,s in found)
    else:out.append("MISSING vendor DTS. Supply --vendor-dts after decompiling vendor 6.6.98 DTB.")
    if a.test_dtb.is_file():
        if not shutil.which("dtc"):
            out.append("MISSING dtc; install device-tree-compiler")
        else:
            target=a.output/"pck600-test.dts"
            proc=sh("dtc","-I","dtb","-O","dts","-o",target,a.test_dtb)
            out.append("dtc exit: "+str(proc.returncode))
            if proc.returncode:
                out.append(proc.stderr[-1000:])
            else:
                text=read(target)
                for term in NODES+CLOCKS:
                    found=matches(text,[term],limit=12)
                    out.append("\nPCK600 test "+term+": "+str(len(found))+" matching lines (max 12)")
                    out.extend(str(i)+": "+s for i,s in found)
                # Explicit read-only comparisons between significant node presence.
                for term in ["hdmi0@5520000","tcon3@5730000","sunxi-drm","de@5000000",
                             "power-controller","pck-600"]:
                    v=term.lower() in vendor_text.lower() if vendor_text else None
                    t=term.lower() in text.lower()
                    out.append("PRESENCE "+term+": vendor="+str(v)+" test="+str(t))
    out.append("\n== Kernel config: source build capability is NOT an active device ==")
    k=read(a.kernel_config)
    for item in ["CONFIG_SUN55I_PCK600","CONFIG_AW_DRM","CONFIG_DRM",
                 "CONFIG_DRM_POWERVR","CONFIG_PROC_FS","CONFIG_SYSFS",
                 "CONFIG_IOMMU_SUPPORT","CONFIG_COMMON_CLK"]:
        entries=[s for s in k.splitlines() if s.startswith(item+"=") or
                 s=="# "+item+" is not set"]
        out.append(item+": "+(", ".join(entries) if entries else "not present"))
    out.extend(["\n== Hardware baseline (operator-confirmed, not newly measured) ==",
        "HDMI absent at power-on: 6.18 reaches interactive BusyBox, PCK genpd domains DE_SYS/VO/VO1 probe 0.",
        "HDMI attached only at U-Boot prompt: 6.18 reaches interactive BusyBox.",
        "HDMI hotplug after 6.18 boot: BusyBox remains responsive.",
        "HDMI connected at power-on: no UART after BL31 handoff; Linux execution not independently measured.",
        "No validated persistent drm_debug environment import. drm_debug=1 set at prompt boots, but too late to test early DRM.",
        "Prior U-Boot messages include sunxi_de_add_kernel_iova_premap fail ret-4 and FDT subnode failure.",
        "\n== Research-grounded interpretation ==",
        "1. A733 HDMI clocks are shared across boot stages, but this diagnostic Linux DTB lacks HDMI/DE/TCON nodes.",
        "2. A source-level U-Boot logo bypass only affects a subset of firmware display operations.",
        "3. FDT mutation errors can arise when vendor U-Boot expects /soc/de in the Linux DTB.",
        "4. Separate Linux 7.4 clock fixes from cold-boot UART behavior; neither is proven causal.",
        "5. Do not recommend a new flash until an independent Linux execution marker is selected.",
        "\nNo firmware modifications, registers, images or input files were written."
    ])
    report=a.output/"report.txt"
    report.write_text("\n".join(out)+"\n")
    print("DONE (read-only source/data audit): "+str(report))
    print("Report lines: "+str(len(out)))
    print("Review missing inputs and PRESENCE lines before any new hardware test.")
if __name__=="__main__":
    main()
