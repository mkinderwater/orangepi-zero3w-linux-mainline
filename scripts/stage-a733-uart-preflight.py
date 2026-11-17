#!/usr/bin/env python3
"""Stage verified A733 UART-only artifacts and a NONBOOTING U-Boot FDT preflight."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HASH_IMAGE = "a2e34a97113b9fff7c64112d46e6f9e131bf2ebe13d9cb1734b4fea49803e311"
HASH_DTB = "b81ae21342c8748bc65a40d38640a2e5c708cd839457e91265cff4d013a851a2"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--dtb", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error("Refusing to overwrite existing output")
    if not a.image.is_file() or sha(a.image) != HASH_IMAGE:
        p.error("Image hash mismatch")
    if not a.dtb.is_file() or sha(a.dtb) != HASH_DTB:
        p.error("DTB hash mismatch")
    a.output.mkdir(parents=True)
    shutil.copy2(a.image, a.output / "Image")
    shutil.copy2(a.dtb, a.output / "sun60i-a733-orangepi-zero3w-uart-only.dtb")
    script = r'''# A733 ZERO3W UART-ONLY: INSPECT RAM AND FDT, NEVER BOOT
echo "A733 PREFLIGHT: no boot will be attempted"
echo "=== U-BOOT DRAM BANKS ==="
bdinfo
echo "=== U-BOOT BOOT VARIABLES ==="
printenv devtype devnum prefix
printenv kernel_addr_r fdt_addr_r ramdisk_addr_r
printenv bootargs
echo "=== TEST DTB ==="
setenv a733_test_fdt 0x44000000
if load ${devtype} ${devnum} ${a733_test_fdt} ${prefix}uart-preflight/sun60i-a733-orangepi-zero3w-uart-only.dtb; then
  fdt addr ${a733_test_fdt}
  echo "=== CHOSEN / ALIASES ==="
  fdt print /chosen
  fdt print /aliases
  echo "=== MEMORY: absent until firmware supplies a bank map ==="
  fdt print /memory
  fdt print /memory@40000000
  echo "=== UART0 ==="
  fdt print /soc/serial@2500000
  fdt print /soc/uart@2500000
else
  echo "LOAD FAILED: inspect devtype devnum prefix"
fi
echo "PREFLIGHT COMPLETE, NO booti, NO PMIC writes"
'''
    cmd = a.output / "preflight.cmd"
    cmd.write_text(script)
    built = False
    if shutil.which("mkimage"):
        res = subprocess.run(
            ["mkimage", "-A", "arm", "-T", "script", "-C", "none",
             "-n", "A733 no-boot preflight", "-d", cmd, a.output / "preflight.scr"],
            capture_output=True, text=True)
        (a.output / "mkimage.log").write_text(res.stdout + res.stderr)
        if res.returncode:
            raise RuntimeError("mkimage failed; inspect mkimage.log")
        built = True
    (a.output / "README.txt").write_text(
        "PRE-FLIGHT ONLY. DO NOT MODIFY THE PROVEN M2dc MEDIUM.\n"
        "Copy this folder to /boot/uart-preflight/ on a SEPARATE test medium.\n"
        "Interrupt autoboot to reach a U-Boot prompt and confirm devtype/devnum/prefix.\n"
        "  load ${devtype} ${devnum} 0x46000000 ${prefix}uart-preflight/preflight.scr\n"
        "  source 0x46000000\n"
        "The script runs bdinfo and examines the FDT. It NEVER boots a kernel.\n"
        "Capture UART logs and actual memory banks before planning any booti.\n"
        "If preflight.scr was not generated, install u-boot-tools and rerun in a NEW directory.\n"
    )
    report = {"status": "PREFLIGHT_STAGED_NO_BOOT", "image_sha256": HASH_IMAGE,
              "dtb_sha256": HASH_DTB, "preflight_scr": built,
              "missing_memory_node": "UNRESOLVED: no memory node in UART-only board DTS",
              "notes": "No booti/bootm. No SD/PMIC writes. Proven control untouched."}
    (a.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("PREFLIGHT_STAGED_NO_BOOT:", a.output)
    print("MKIMAGE_SCRIPT:", built)
    print("Image SHA256:", HASH_IMAGE)
    print("DTB SHA256:", HASH_DTB)

if __name__ == "__main__":
    main()
