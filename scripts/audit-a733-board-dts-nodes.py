#!/usr/bin/env python3
"""Read-only A733 Zero 3W DTS hardware-node inventory for canonical DTS design.

This is a source-location report, NOT a generated or bootable DTS.
"""
import argparse
import json
import re
from pathlib import Path

def snippets(path, needles, before=4, after=32):
    lines = path.read_text(errors="replace").splitlines()
    matches = []
    for needle in needles:
        found = [i for i, line in enumerate(lines) if re.search(needle, line)]
        for i in found[:4]:
            start, stop = max(0, i-before), min(len(lines), i+after+1)
            matches.append({"pattern": needle, "line": i+1,
                            "source": str(path),
                            "context": [f"{j+1}: {lines[j]}" for j in range(start, stop)]})
    return matches

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kernel", type=Path, required=True)
    p.add_argument("--board", type=Path, required=True)
    p.add_argument("--soc", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error("Refusing overwrite")
    sources = {
        "vendor_board": (a.board, (
            r"reg_dc1sw2\s*:", r"reg_cldo5\s*:", r"pmu@36\s*\{",
            r"twi@7083000\s*\{", r"&sdc0\s*\{",
            r"&uart0\s*\{", r"&pio\s*\{", r"&r_pio\s*\{",
            r"sdc0_pins_[a-z]\s*:", r"uart0.*pins")),
        "vendor_soc": (a.soc, (
            r"sdc0\s*:", r"uart0\s*:", r"pio\s*:",
            r"r_pio\s*:", r"ccu\s*:", r"r_ccu\s*:",
            r"(twi|r_twi)[0-9]*\s*:", r"interrupt-controller@",
            r"timer@")),
        "upstream_pinctrl": (a.kernel / "drivers/pinctrl/sunxi/pinctrl-sun60i-a733.c", (
            r"PF[0-9]", r"PB[0-9]", r"mmc0", r"uart0")),
        "upstream_r_pinctrl": (a.kernel / "drivers/pinctrl/sunxi/pinctrl-sun55i-a523-r.c", (
            r"PL[0-9]", r"r_i2c", r"sun60i-a733")),
        "upstream_example": (a.kernel / "arch/arm64/boot/dts/allwinner/sun55i-a523.dtsi", (
            r"ccu\s*:", r"pio\s*:", r"r_pio\s*:",
            r"uart0\s*:", r"mmc0\s*:", r"r_i2c0\s*:")),
    }
    report = {"status": "STATIC_ONLY_NOT_A_DTS",
              "caution": "Vendor addresses/pins must be verified against A733 upstream driver/bindings. No PMIC writes.",
              "sources": {}}
    for label, (path, patterns) in sources.items():
        if not path.is_file():
            p.error(f"Required source missing: {path}")
        report["sources"][label] = snippets(path, patterns)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n")
    for label, entries in report["sources"].items():
        print(f"=== {label}: {len(entries)} snippets ===")
        for entry in entries:
            print(f"{entry['line']}: {entry['pattern']} :: {entry['source']}")
    print("REPORT:", a.output)
    print("No Linux files, DTS, voltage or boot media modified.")

if __name__ == "__main__":
    main()
