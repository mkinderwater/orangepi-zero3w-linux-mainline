#!/usr/bin/env python3
"""Inventory EXISTING Zero 3W vendor/6.18 DTB integration evidence.

No recompilation, no overlays, no source rewrites and no writes to inputs.
Reuses prior report artifacts, tested DTBs and build configs, reporting gaps.
Outputs summary.md and artifacts.tsv to a new audit-only directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4")
ART = ROOT/"artifacts"
SOURCE = ROOT/"linux"
VENDOR = Path("/root/opi3w-vendor-6698-work/kernel")
DTB = ART/"ram-b-26mhz-pck600-probe.dtb"
CONFIG = ART/"Image-618-vendor-hdmi-pck600-syscon.config"
VENDOR_DTS = ROOT/"vendor-dtb-topology/vendor-control.dts"
KNOWN = [
    ("Vendor reference DTS",VENDOR_DTS),
    ("6.18 PCK600 hardware-probed DTB",DTB),
    ("6.18 HDMI/PCK600 kernel config",CONFIG),
    ("Vendor/6.18 display binding map",ROOT/"display-binding-map.tsv"),
    ("Resolved vendor HDMI dependencies",ROOT/"vendor-dtb-topology/phandle-dependencies.txt"),
    ("Vendor HDMI graph extraction",ROOT/"vendor-dtb-topology/vendor-control.dts"),
    ("PCK600 hardware test image",ART/"opi3w-618-pck600-ram-shell.img"),
    ("Prior full vendor baseline",ART/"opi3w-VENDOR-6698-full-stock-baseline.img"),
    ("HDMI handoff offline audit",ART/"hdmi-handoff-offline/report.txt"),
    ("Legacy DTB readiness audit",ROOT/"hdmi-dtb-readiness/summary.txt"),
    ("Legacy provider compatibility audit",ROOT/"provider-compat/summary.txt"),
]
PROBES = {
    "Native UART / 26 MHz root clock": "HARDWARE PASS (earlier RAM-B tests)",
    "Linux 6.18 PCK600 genpd: DE_SYS, VO, VO1": "HARDWARE PASS (earlier PCK600 RAM shell)",
    "Vendor 6.6.98 HDMI and Debian": "HARDWARE PASS on earlier vendor VBI; new clone not separately booted",
    "6.18 DE352, TCON3, HDMI PHY/scanout": "NOT HARDWARE VALIDATED",
    "6.18 display IOMMU v20": "NOT IN CURRENT BUILT CONFIG",
    "6.18 PowerVR GPU": "NOT IN CURRENT BUILT CONFIG",
    "6.18 AXP8191 + MMC supply and root": "EARLIER SOURCE WORK; NOT PROVEN WITH CURRENT PCK600 KERNEL/DTB",
    "Cold boot HDMI plugged before power-on": "UART SILENT after BL31 on 6.18 RAM-only diagnostic",
}
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for part in iter(lambda:f.read(4*1024*1024),b""):
            h.update(part)
    return h.hexdigest()
def cmd(*args):
    return subprocess.run([str(a) for a in args],text=True,capture_output=True)
def lines_matching(path,pattern,limit=24):
    if not path.is_file():return []
    pat=re.compile(pattern,re.I)
    ret=[]
    for n,line in enumerate(path.read_text(errors="replace").splitlines(),1):
        if pat.search(line):ret.append(f"{n}: {line[:175].strip()}")
        if len(ret)>=limit:break
    return ret
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=ROOT/"artifacts/dtb-existing-evidence-inventory")
    ap.add_argument("--vendor-dts",type=Path,default=VENDOR_DTS)
    ap.add_argument("--dtb",type=Path,default=DTB)
    ap.add_argument("--config",type=Path,default=CONFIG)
    a=ap.parse_args()
    if a.out.exists():raise SystemExit("STOP: output already exists. Supply a NEW --out.")
    a.out.mkdir(parents=True)
    rows=["asset\tstatus\tbytes\tsha256\tpath"]
    report=[
        "# Existing A733 / Zero 3W Linux 6.18 DTB evidence inventory",
        "",
        "Read-only input inspection. Reports are not regenerated.",
        "No image, DTB or device modified. Test status is based on prior operator observations.",
        "",
        "## Existing assets",
    ]
    for label,p in KNOWN:
        if label=="Vendor reference DTS":p=a.vendor_dts
        if label=="6.18 PCK600 hardware-probed DTB":p=a.dtb
        if label=="6.18 HDMI/PCK600 kernel config":p=a.config
        found=p.is_file()
        size=p.stat().st_size if found else ""
        digest=sha(p) if found and p.stat().st_size<=20*1024*1024 else "omitted: large image"
        rows.append("\t".join(map(str,[label,"PRESENT" if found else "NOT FOUND AT DEFAULT PATH",size,digest,p])))
        report.append(f"- **{label}:** {'present' if found else 'not found at default path'}: "+str(p))
    report+=["","## Prior hardware status (not new tests)"]
    report.extend(f"- **{k}:** {v}" for k,v in PROBES.items())
    report+=["","## Exact built kernel configuration"]
    keys=["AW_DRM","DRM","SUN55I_PCK600","IOMMU_SUPPORT","DRM_POWERVR",
          "MFD_AXP20X","MFD_AXP20X_I2C","REGULATOR_AXP20X",
          "MMC_SUNXI","COMMON_CLK","PROC_FS","SYSFS"]
    config_text=a.config.read_text(errors="replace") if a.config.is_file() else ""
    for key in keys:
        pattern=re.compile(r"^(CONFIG_"+key+r"=[^\n]+|# CONFIG_"+key+r" is not set)$",re.M)
        m=pattern.search(config_text)
        report.append(f"- {key}: "+(m.group(1) if m else "not established"))
    report+=["","## Confirmed source-level HDMI gate and reset mappings"]
    # Use committed hand-audited mappings as reference, not dynamic guesses.
    mappings=[
      ("HDMI main bus","0x168c bit0","vendor CLK_HDMI=253","6.18 CLK_BUS_HDMI_TV=251"),
      ("HDMI TV","0x1684","vendor CLK_HDMI_TV=252","6.18 CLK_HDMI_TV=250"),
      ("HDMI SFR","0x1690","vendor CLK_HDMI_SFR=254","6.18 CLK_HDMI_SFR=252"),
      ("DPSS TOP0","0x16c4 bit0","vendor CLK_DPSS_TOP0=256","6.18 CLK_BUS_DPSS_TOP0=254"),
      ("DPSS TOP1","0x16cc bit0","vendor CLK_DPSS_TOP1=257","6.18 CLK_BUS_DPSS_TOP1=255"),
      ("TCON TV0","0x1604 bit0","vendor CLK_TCONTV0=247","6.18 CLK_BUS_TCON_TV0=244"),
      ("TCON TV1","0x160c bit0","vendor CLK_TCONTV1=248","6.18 CLK_BUS_TCON_TV1=245"),
    ]
    report.append("| Function | Shared register | Vendor binding | 6.18 binding |")
    report.append("|---|---|---|---|")
    report.extend("| "+" | ".join(row)+" |" for row in mappings)
    report.append("**Source-level register match only.** Parent/rate/mux behavior may differ.")
    report+=["","## Device-tree graph audit"]
    dts_text=a.vendor_dts.read_text(errors="replace") if a.vendor_dts.is_file() else ""
    test_dts=""
    if a.dtb.is_file():
        p=cmd("dtc","-q","-I","dtb","-O","dts",a.dtb)
        if p.returncode==0:
            test_dts=p.stdout
            (a.out/"pck600-test.dts").write_text(test_dts)
        else:
            report.append("- dtc unavailable or failed: "+p.stderr[-400:])
    targets=["sunxi-drm","de@5000000","tcon3@5730000","tcon4@5731000",
             "hdmi0@5520000","iommu@3900000","pck-600@7060000","power-controller"]
    report.append("| Node | Vendor DTS | PCK600 test DTB |")
    report.append("|---|---|---|")
    for target in targets:
        report.append(f"| {target} | {target in dts_text} | {target in test_dts} |")
    report+=["","## Existing provider and mapping tools (re-use, don't reimplement)"]
    scripts=[
       "resolve-vendor-hdmi-dependencies.py",
       "compare-a733-display-bindings.py",
       "compare-a733-hdmi-ccu-registers.py",
       "audit-hdmi-provider-compat-618.sh",
       "audit-hdmi-dtb-readiness-618.sh",
       "audit-vendor-zero3w-display-dtbs.sh",
       "stage-a733-pck600-probe-dtb.py",
       "validate-a733-pck600-probe-dtb.py",
       "integrate-axp8191-m2r.sh",
    ]
    report.extend(f"- scripts/{name}" for name in scripts)
    report+=["","## Genuine integration gaps"]
    gaps=[
        "6.18 active vendor-equivalent DE352/TCON3/HDMI/PHY device nodes with validated provider phandles",
        "IOMMU v20 source driver, binding and kernel config in same isolated 6.18 tree",
        "AXP8191 and HDMI regulators DCDC2/CLDO2 verified against THIS 6.18 kernel",
        "MMC0 and root filesystem supply dependencies verified alongside display",
        "Dynamic/firmware clock handoff and actual HDMI-connected cold boot without silent UART",
        "Exact final kernel+DTB+modules+initrd+rootfs cross-version pairing",
    ]
    report.extend(f"- {gap}" for gap in gaps)
    report+=["","## Controlled next engineering gate",
        "Use this inventory plus previous binding map and phandle report to produce a translated",
        "6.18 DTB in a NEW file. Fail on missing providers/driver compatibles. Do not copy",
        "numeric vendor phandles or activate unsupported hardware nodes.",
        "Do not infer A733 HDMI success from a vendor 6.6.98 full-DTB control boot.",
        "The current RAM shell is a validated diagnostic baseline, not an OS-wide baseline.",
        ""]
    (a.out/"summary.md").write_text("\n".join(report))
    (a.out/"artifacts.tsv").write_text("\n".join(rows)+"\n")
    print("PASS: existing evidence inventory written:",a.out/"summary.md")
    print("Missing at default path:",sum("NOT FOUND AT DEFAULT PATH" in row for row in rows))
    print("No firmware, kernel, DTB or boot image modified.")
if __name__=="__main__":
    main()
