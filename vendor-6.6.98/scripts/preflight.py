#!/usr/bin/env python3
"""Fail-closed offline gate for rebuilt 6.6.98 control and identity artifacts.

Reads outputs only. Never writes a disk image or flashes a device.
"""
from pathlib import Path
import hashlib
import os
import re
import subprocess
import sys

RESULTS = Path(os.getenv("RESULTS_DIR", "/mnt/c/Users/mkinderwater/Downloads/opi3w-vendor-6698-results"))
WORK = Path(os.getenv("WORK_ROOT", "/root/opi3w-vendor-6698-work"))
PIN = "2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f"
DTB_NAME = "sun60i-a733-orangepi-zero3w.dtb"
OLD = 'compatible = "xunlong,orangepi-4-pro", "arm,sun60iw2p1";'
NEW = 'compatible = "xunlong,orangepi-zero3w", "arm,sun60iw2p1";'
failures = []
def check(cond, label):
    print(("PASS" if cond else "FAIL") + ": " + label)
    if not cond:
        failures.append(label)
def run(args, **kwargs):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kwargs).stdout
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()
def verify_manifest(folder):
    mf = folder/"SHA256SUMS"
    check(mf.is_file(), f"{folder.name}: SHA256SUMS present")
    if not mf.is_file():
        return
    for line in mf.read_text().splitlines():
        m=re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9_.-]+)",line)
        if not m:
            check(False, f"{folder.name}: malformed manifest entry")
            continue
        expected, name=m.groups()
        f=folder/name
        check(f.is_file() and sha(f)==expected, f"{folder.name}: SHA256 {name}")

for mode in ("control","identity"):
    out=RESULTS/mode
    check(out.is_dir(), f"{mode}: output exists")
    if not out.is_dir(): continue
    verify_manifest(out)
    manifest=out/"build-manifest.txt"
    if manifest.is_file():
        s=manifest.read_text()
        check(f"SOURCE_COMMIT={PIN}" in s and f"MODE={mode}" in s,
              f"{mode}: pinned commit and mode")
        check("KCONFIG_REPAIR=gt9xx_secondary_double_slash" in s and
              "VE_KBUILD_REPAIR=source_tree_codec_include" in s,
              f"{mode}: two tracked source repairs")
    else: check(False,f"{mode}: build-manifest.txt exists")
    dpatch=out/"dts.patch"
    if dpatch.is_file():
        d=dpatch.read_text()
        if mode=="control":
            check(not d.strip(), "control: no board DTS patch")
        else:
            removed=[x[1:] for x in d.splitlines() if x.startswith("-") and not x.startswith("---")]
            added=[x[1:] for x in d.splitlines() if x.startswith("+") and not x.startswith("+++")]
            check(len(removed)==1 and len(added)==1 and removed[0].strip()==OLD and
                  added[0].strip()==NEW, "identity: exactly one board ID substitution")
    else: check(False,f"{mode}: dts.patch exists")

for mode in ("control","identity"):
    p=WORK/("obj-"+mode)/"include/config/kernel.release"
    check(p.is_file(),f"{mode}: kernelrelease in object tree")
    if p.is_file():
        val=p.read_text().strip()
        check(val.startswith("6.6.98"),f"{mode}: kernelrelease {val}")
    dtb=RESULTS/mode/DTB_NAME
    check(dtb.is_file() and dtb.stat().st_size>40,f"{mode}: nonempty DTB")
    if dtb.is_file() and dtb.stat().st_size>40:
        data=dtb.read_bytes()
        check(data[:4]==bytes.fromhex("d00dfeed"),f"{mode}: DTB magic FDT")
        total=int.from_bytes(data[4:8],"big")
        check(40<=total<=len(data),f"{mode}: DTB totalsize within file")

c=RESULTS/"control"/"Image"; i=RESULTS/"identity"/"Image"
if c.is_file() and i.is_file():
    same=sha(c)==sha(i)
    print(f"INFO: control and identity Image hashes identical: {same}")
    if not same:
        print("INFO: kernel payload differs. Investigate metadata/toolchain; no equality assertion.")
c=RESULTS/"control"/DTB_NAME;i=RESULTS/"identity"/DTB_NAME
if c.is_file() and i.is_file():
    print(f"INFO: control DTB SHA256: {sha(c)}")
    print(f"INFO: identity DTB SHA256: {sha(i)}")
    check(sha(c)!=sha(i),"identity: compiled DTB actually changed")

print()
if failures:
    print(f"STOP_OFFLINE_PREFLIGHT_FAILED: {len(failures)} checks")
    sys.exit(1)
print("OFFLINE_PREFLIGHT_PASS_NOT_FLASHABLE_NOT_HARDWARE_TESTED")
print("Next: use a separately reviewed single-change stock-image assembler; no automatic flashing.")
