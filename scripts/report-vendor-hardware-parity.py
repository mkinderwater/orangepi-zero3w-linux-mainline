#!/usr/bin/env python3
"""Produce hardware-focused vendor 6.6.98 -> Linux 6.18 Kconfig differences.

This is symbol triage, not a conclusion about driver support. Broad matchers
can include unrelated hardware and miss vendor-specific symbols; retain all rows.
"""
import argparse
import csv
import pathlib
import re
from collections import Counter

# Distinct, ordered categories. A match identifies an audit candidate, not a
# proven functional regression or required enablement.
DOMAINS = [
    ("uart", r"UART|SERIAL|8250|EARLYCON|TTY|CONSOLE"),
    ("hdmi-display", r"HDMI|DISPLAY|DISP_|DISP$|SUNXI_DISP|SUNXI_DRM|SUN4I_DRM|SUN8I|TCON|DE2|DE3|DE35|MIXER|VOP|PANEL|BRIDGE|PHY.*HDMI|HDMI.*PHY"),
    ("gpu-drm", r"DRM|POWERVR|PVR|IMAGINATION|GPU|RGX|MALI|VULKAN|SYNC_FILE|DMA_BUF"),
    ("clock-reset", r"CLOCK|CLK|CCU|RESET|RTC|PLL|OSC"),
    ("power-regulator", r"AXP|PMIC|REGULATOR|MFD|POWER_DOMAIN|PM_DOMAINS|GENPD|PWR"),
    ("pinctrl-gpio", r"PINCTRL|GPIO|SUNXI_PIO|IRQCHIP"),
    ("dma-iommu", r"DMA|IOMMU|CMA|SWIOTLB|ION|HEAP"),
    ("storage", r"MMC|SDIO|SDHCI|BLOCK|EXT4|FAT|VFAT"),
    ("audio", r"SND|SOUND|AUDIO|I2S|PCM|CODEC"),
    ("network", r"NET|ETH|GMAC|WLAN|WIFI|AIC8800|RFKILL"),
    ("usb", r"USB|PHY|TYPEC"),
]
PATTERNS = [(k, re.compile(v, re.I)) for k, v in DOMAINS]

def load(path):
    values = {}
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            name, value = line.split("=", 1)
            values[name[7:]] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            values[line[9:-11]] = "n"
    return values

def classify(a, b):
    if a in {"y", "m"} and b not in {"y", "m"}:
        return "vendor_enabled_missing_or_renamed"
    if b in {"y", "m"} and a not in {"y", "m"}:
        return "618_enabled_not_in_vendor"
    if a in {"y", "m"} and b in {"y", "m"} and a != b:
        return "builtin_module_mismatch"
    return "other_difference"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vendor", type=pathlib.Path)
    ap.add_argument("mainline", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("/root/opi3w-m2-work/linux-618-full-integration/vendor-parity/hardware-focus"))
    args = ap.parse_args()
    for p in (args.vendor, args.mainline):
        if not p.is_file():
            ap.error(f"not a file: {p}")
    v, m = load(args.vendor), load(args.mainline)
    rows = []
    for name in sorted(set(v) | set(m)):
        old, new = v.get(name, "absent"), m.get(name, "absent")
        if old == new:
            continue
        groups = [group for group, rx in PATTERNS if rx.search(name)]
        if not groups:
            continue
        rows.append({"domain": groups[0], "other_domains": ",".join(groups[1:]),
                     "category": classify(old, new), "symbol": f"CONFIG_{name}",
                     "vendor_6_6_98": old, "linux_6_18": new})
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "hardware-differences.tsv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [
            "domain", "other_domains", "category", "symbol", "vendor_6_6_98", "linux_6_18"
        ], delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    bydomain = Counter(r["domain"] for r in rows)
    bycategory = Counter(r["category"] for r in rows)
    attention = [r for r in rows if r["category"] == "vendor_enabled_missing_or_renamed"]
    with (args.out / "summary.txt").open("w") as f:
        f.write(f"Vendor: {args.vendor}\n6.18: {args.mainline}\n")
        f.write("Classification by CONFIG symbol names ONLY; not feature parity.\n")
        f.write("A missing symbol may have been renamed/replaced; added symbols may be required in 6.18.\n")
        f.write(f"Hardware-domain symbol differences: {len(rows)}\n")
        for k, count in sorted(bycategory.items()):
            f.write(f"{k}: {count}\n")
        f.write("\nHardware domains:\n")
        for domain, count in bydomain.most_common():
            f.write(f"  {domain}: {count}\n")
        f.write("\nVendor-enabled gap candidates, UART / HDMI / GPU priority:\n")
        first = [r for r in attention if r["domain"] in {"uart","hdmi-display","gpu-drm"}]
        for r in first:
            f.write(f"  {r['domain']} {r['symbol']} vendor={r['vendor_6_6_98']} 618={r['linux_6_18']}\n")
        f.write("\nAll candidates: hardware-differences.tsv\n")
        f.write("No configuration file was changed.\n")
    print((args.out / "summary.txt").read_text(), end="")

if __name__ == "__main__":
    main()
