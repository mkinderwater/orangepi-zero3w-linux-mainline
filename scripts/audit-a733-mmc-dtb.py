#!/usr/bin/env python3
"""Read-only Zero 3W MMC0-3 DTB inventory, including supply and clock phandles.

Does not modify device trees, drivers, regulator voltages or SD media.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import importlib.util

def parse_dtb(path):
    helper = Path(__file__).with_name("compare-zero3w-dtbs.py")
    spec = importlib.util.spec_from_file_location("fdt_compare_zero3w", helper)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    blob = path.read_bytes()
    nodes, reservations = mod.parse(blob)
    return blob, nodes

def cell(raw):
    return [struct.unpack_from(">I", raw, n)[0] for n in range(0, len(raw), 4)] if raw and len(raw) % 4 == 0 else None

def strings(raw):
    if not raw or not raw.endswith(b"\0"):
        return None
    try:
        values = [x.decode("utf-8") for x in raw[:-1].split(b"\0")]
        return values if all(values) else None
    except UnicodeDecodeError:
        return None

def identify(nodes):
    mapping = {}
    for path, props in nodes.items():
        for marker in ("phandle", "linux,phandle"):
            raw = props.get(marker)
            if raw and len(raw) == 4:
                mapping.setdefault(cell(raw)[0], []).append(path)
    return mapping

def inspect(path):
    raw, nodes = parse_dtb(path)
    refs = identify(nodes)
    mmc = []
    for name, props in sorted(nodes.items()):
        if not any(token in name.lower() for token in ("sdmmc@", "mmc@")):
            continue
        def item(key):
            val = props.get(key)
            if val is None:
                return None
            parsed = strings(val) if key in ("compatible", "status", "clock-names", "reset-names",
                                            "pinctrl-names") else None
            return parsed if parsed is not None else cell(val) if val else True
        supplies = {}
        for key, value in props.items():
            if key.endswith("-supply") or key in ("vmmc", "vqmmc"):
                words = cell(value)
                supplies[key] = {"cells": words,
                                 "phandle_targets": [refs.get(n, []) for n in words] if words else []}
        mmc.append({
            "node": name,
            "compatible": item("compatible"),
            "status": item("status") or ["okay (implicit)"],
            "reg": item("reg"),
            "interrupts": item("interrupts"),
            "clocks": item("clocks"),
            "clock_names": item("clock-names"),
            "resets": item("resets"),
            "reset_names": item("reset-names"),
            "pinctrl_0": item("pinctrl-0"),
            "pinctrl_names": item("pinctrl-names"),
            "supplies": supplies,
            "mmc_high_capacity_erase_size": "mmc-high-capacity-erase-size" in props,
            "sd_uhs": sorted(k for k in props if k.startswith("sd-uhs-")),
            "other_mmc_properties": sorted(k for k in props if k.startswith(("mmc-", "cap-", "no-"))),
        })
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
            "mmc_nodes": mmc}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hybrid-dtb", type=Path, required=True)
    ap.add_argument("--vendor-dtb", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True, help="New JSON report path")
    a = ap.parse_args()
    if a.output.exists():
        ap.error("Output exists; refusing overwrite")
    result = {"schema": 1, "status": "STATIC_MMC_ONLY",
              "warning": "DTB properties do not prove physical wiring or electrical voltage safety",
              "hybrid": inspect(a.hybrid_dtb), "vendor": inspect(a.vendor_dtb)}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    for label in ("vendor", "hybrid"):
        print("===", label, "===")
        for mmc in result[label]["mmc_nodes"]:
            print(mmc["node"], "compatible=", mmc["compatible"],
                  "status=", mmc["status"], "supplies=", mmc["supplies"],
                  "legacy_erase=", mmc["mmc_high_capacity_erase_size"])
    print("MMC_REPORT:", a.output)
    print("No source, boot image, or media modified.")

if __name__ == "__main__":
    main()
