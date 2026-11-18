#!/usr/bin/env python3
"""Add a conventional guard to the exact staged vendor sunxi-iommu.h only.

The original BSP header has no guard. sunxi-iommu-common.c includes the
same file via both quoted and angle bracket syntax; once the search path is
correct, struct dump_region is defined twice. This is a compile-only fix.
"""
from pathlib import Path
import argparse, hashlib, sys

EXPECTED = "1e156fd9cef40a7bebb8b95cb3141a510d60a6367c5ecedebb0e2dda79e1011a"
DEFAULT = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20/sunxi-iommu.h")
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--header", type=Path, default=DEFAULT)
    a = p.parse_args()
    h = a.header.resolve()
    if h.name != "sunxi-iommu.h" or h.parent.name != "aw-v20":
        sys.exit("STOP: header is not a staged aw-v20/sunxi-iommu.h")
    if not h.is_file():
        sys.exit("STOP: staged header missing")
    old = h.read_bytes()
    digest = hashlib.sha256(old).hexdigest()
    if digest != EXPECTED:
        sys.exit("STOP: staged header SHA256 differs: " + digest)
    if b"struct dump_region" not in old:
        sys.exit("STOP: expected vendor structure missing")
    backup = h.with_name("sunxi-iommu.h.vendor-original")
    if backup.exists():
        sys.exit("STOP: backup already exists; no changes")
    pre = b"#ifndef __AW_A733_IOMMU_V20_STAGED_H__\n#define __AW_A733_IOMMU_V20_STAGED_H__\n\n"
    post = b"\n#endif /* __AW_A733_IOMMU_V20_STAGED_H__ */\n"
    backup.write_bytes(old)
    try:
        h.write_bytes(pre + old + (b"" if old.endswith(b"\n") else b"\n") + post)
    except Exception:
        h.write_bytes(old)
        backup.unlink()
        raise
    print("STAGED HEADER GUARDED:", h)
    print("ORIGINAL BACKUP:", backup)
    print("NEW SHA256:", hashlib.sha256(h.read_bytes()).hexdigest())
    print("Original vendor tree and working Linux source untouched.")
if __name__ == "__main__":
    main()
