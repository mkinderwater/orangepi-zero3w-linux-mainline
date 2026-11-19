#!/usr/bin/env python3
"""Compare vendor 6.6.98 and 6.18 configurations without guessing feature equivalence.

Usage: python3 scripts/audit-vendor-kernel-parity.py VENDOR_CONFIG MAINLINE_CONFIG
Output: human-readable summary and full TSV delta, no file modification.
A renamed/moved Kconfig option is an unresolved mapping, not a missing feature.
"""
import argparse
import collections
import pathlib
import sys

def read_config(path):
    result = {}
    for line in pathlib.Path(path).read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            k, v = line.split("=", 1)
            result[k[7:]] = v
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            k = line[len("# CONFIG_"):-len(" is not set")]
            result[k] = "n"
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vendor", type=pathlib.Path)
    ap.add_argument("mainline", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path)
    args = ap.parse_args()
    vendor, mainline = read_config(args.vendor), read_config(args.mainline)
    out = args.out or pathlib.Path("/root/opi3w-m2-work/linux-618-full-integration/vendor-parity")
    out.mkdir(parents=True, exist_ok=True)
    categories = collections.Counter()
    rows = []
    keys = sorted(set(vendor) | set(mainline))
    for key in keys:
        a, b = vendor.get(key, "absent"), mainline.get(key, "absent")
        if a == b:
            continue
        if a in {"y", "m"} and b in {"n", "absent"}:
            kind = "VENDOR_ENABLED_MISSING_OR_RENAMED"
        elif b in {"y", "m"} and a in {"n", "absent"}:
            kind = "618_ENABLED_NOT_IN_VENDOR"
        elif a in {"y", "m"} and b in {"y", "m"}:
            kind = "BUILTIN_MODULE_DIFFERENCE"
        else:
            kind = "CONFIG_VALUE_OR_VERSION_DIFFERENCE"
        categories[kind] += 1
        rows.append((kind, "CONFIG_" + key, a, b))
    with (out / "diff.tsv").open("w") as stream:
        stream.write("category\toption\tvendor_6_6_98\tlinux_6_18\n")
        for row in rows:
            stream.write("\t".join(row) + "\n")
    with (out / "summary.txt").open("w") as stream:
        stream.write(f"Vendor: {args.vendor}\nMainline: {args.mainline}\n")
        stream.write("This is a CONFIG name/value audit, NOT proof of functional parity.\n")
        stream.write("Renamed/removed options, dependencies, BSP paths and kernel-internal settings require manual mapping.\n")
        for k, count in sorted(categories.items()):
            stream.write(f"{k}: {count}\n")
        stream.write(f"Total differences: {len(rows)}\n")
        stream.write("Review diff.tsv; allow only version-required differences and directly supported board functions.\n")
    print((out / "summary.txt").read_text(), end="")
    print(f"Full delta: {out / 'diff.tsv'}")

if __name__ == "__main__":
    main()
