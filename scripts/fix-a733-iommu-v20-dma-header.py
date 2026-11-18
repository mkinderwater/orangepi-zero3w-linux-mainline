#!/usr/bin/env python3
"""Fix missing DMA API declarations in a disposable A733 v20 page-table source."""
import argparse
import hashlib
from pathlib import Path

EXPECTED = "c48d2f4c80f3d15455e811eaddbea0ab485af217654f9823e927fe299f329b76"
DEFAULT = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20/sunxi-iommu-pgtable.c")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT)
    args = parser.parse_args()
    src = args.source.resolve()
    if src.name != "sunxi-iommu-pgtable.c" or src.parent.name != "aw-v20":
        parser.error("Expected a staged aw-v20 page-table implementation")
    data = src.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED:
        parser.error("Staged source differs from verified vendor SHA256")
    needle = b"#include <linux/iommu.h>\n"
    if data.count(needle) != 1 or b"#include <linux/dma-mapping.h>" in data:
        parser.error("Unexpected source include layout")
    backup = src.with_name(src.name + ".vendor-original")
    if backup.exists():
        parser.error("Existing vendor backup; refuse repeat")
    backup.write_bytes(data)
    src.write_bytes(data.replace(needle, needle + b"#include <linux/dma-mapping.h>\n", 1))
    print("UPDATED STAGED SOURCE:", src)
    print("BACKUP:", backup)
    print("Unmodified vendor and kernel baselines; compile only, no runtime validation")

if __name__ == "__main__":
    main()
