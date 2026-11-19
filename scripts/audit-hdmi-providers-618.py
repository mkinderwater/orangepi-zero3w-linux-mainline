#!/usr/bin/env python3
"""Read-only provider audit. Matches *names/compatibles*, not raw numeric IDs."""
from pathlib import Path
import argparse
import re

ap=argparse.ArgumentParser()
ap.add_argument("--source",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/linux"))
ap.add_argument("--output",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/provider-audit.txt"))
a=ap.parse_args()
src=a.source
providers={
    "Main A733 CCU":"allwinner,sun60iw2-ccu",
    "RTC CCU":"allwinner,sun60iw2-rtc-ccu",
    "PCK-600 power":"allwinner,sun60iw2-pck-600",
    "IOMMU":"allwinner,iommu-v20",
}
roots=["drivers/clk","drivers/pmdomain","drivers/iommu","arch/arm64/boot/dts"]
report=["Linux 6.18 HDMI provider source inventory (read-only)",
        "Symbol presence is not evidence that a probe or clock/reset gate works.",
        "Vendor clock IDs: DE 118/119/70/85, TCON TOP 256/257, HDMI 251/253/254/255.",
        "Vendor RTC clock specifier 12; power-domain specifiers 1/9/10.",
        ""]
for title,compatible in providers.items():
    report.append("=== "+title+" / "+compatible+" ===")
    matched=[]
    for root in roots:
        directory=src/root
        if not directory.exists(): continue
        for p in directory.rglob("*"):
            if p.suffix not in (".c",".h",".dts",".dtsi"): continue
            try: text=p.read_text(errors="replace")
            except OSError: continue
            if compatible in text:
                matched.append(str(p.relative_to(src)))
    report.extend(sorted(set(matched)) or ["NO MATCH in searched source directories"])
    report.append("")
report.append("=== A733 dt-bindings files ===")
for root in ("include/dt-bindings/clock","include/dt-bindings/reset","include/dt-bindings/power"):
    directory=src/root
    if directory.exists():
        report.extend(str(p.relative_to(src)) for p in sorted(directory.glob("*")) if re.search("a733|sun60|sunxi",p.name,re.I))
report.append("")
report.append("NEXT: confirm compatible-string probe drivers, provider cell mapping,")
report.append("CCU gate IDs, IOMMU behavior and PCK power-domain implementation.")
report.append("Do not paste vendor DTB phandle values into RAM-B.")
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text("\n".join(report)+"\n")
print("\n".join(report))
