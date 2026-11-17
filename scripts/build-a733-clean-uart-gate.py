#!/usr/bin/env python3
"""Isolated A733 serial gate: compile upstream DesignWare 8250 and full ARM64 Image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

def call(*args, env=None):
    argv = [str(x) for x in args]
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, check=True, env=env)

def hash_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1048576), b""):
            h.update(data)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=4)
    a = p.parse_args()
    src = a.source.resolve()
    dst = a.output.resolve()
    if not (src / "Makefile").is_file() or not a.config.is_file():
        p.error("Kernel source and config required")
    if dst.exists() or dst == src or src in dst.parents or a.jobs < 1 or a.jobs > 64:
        p.error("Output exists, overlaps input or invalid job count")
    conf = a.config.read_text()
    if "CONFIG_SERIAL_8250=y" not in conf or "CONFIG_SERIAL_8250_CONSOLE=y" not in conf:
        p.error("Input must already support built-in 8250 serial console")
    dst.mkdir(parents=True)
    tree = dst / "linux"
    obj = dst / "obj"
    call("cp", "-a", "--reflink=auto", src, tree)
    obj.mkdir()
    shutil.copy2(a.config, obj / ".config")
    call(tree / "scripts/config", "--file", obj / ".config", "--enable", "SERIAL_8250_DW")
    env = os.environ.copy()
    env["ARCH"] = "arm64"
    env["CROSS_COMPILE"] = "aarch64-linux-gnu-"
    call("make", "-C", tree, f"O={obj}", "ARCH=arm64", "olddefconfig", env=env)
    effective = (obj / ".config").read_text()
    required = ("SERIAL_8250", "SERIAL_8250_CONSOLE", "SERIAL_EARLYCON",
                "SERIAL_8250_DW", "ARM_GIC_V3", "ARM_ARCH_TIMER",
                "SUN60I_A733_CCU", "SUN60I_A733_R_CCU", "PINCTRL_SUN60I_A733")
    missing = [k for k in required if f"CONFIG_{k}=y" not in effective.splitlines()]
    if missing:
        raise RuntimeError("Configuration incomplete: " + repr(missing))
    report = {"status": "CONFIG_PASS", "serial": "snps,dw-apb-uart",
              "source": str(src), "boot_test": "NOT PERFORMED",
              "pmic_rail_writes": "NOT PERFORMED", "dtb": "NOT BUILT"}
    def save():
        (dst / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    try:
        call("make", "-C", tree, f"O={obj}", "ARCH=arm64",
             "CROSS_COMPILE=aarch64-linux-gnu-", f"-j{a.jobs}", "Image", env=env)
    except subprocess.CalledProcessError:
        report["status"] = "BUILD_FAILED"
        save()
        raise
    image = obj / "arch/arm64/boot/Image"
    serial = obj / "drivers/tty/serial/8250/8250_dw.o"
    if not image.is_file() or not serial.is_file():
        raise RuntimeError("Missing Image or DesignWare 8250 object")
    report.update({"status": "UART_IMAGE_LINK_PASS_NOT_BOOTABLE",
                   "image_bytes": image.stat().st_size,
                   "image_sha256": hash_file(image),
                   "serial_object": str(serial)})
    save()
    print("UART_IMAGE_LINK_PASS:", image)
    print("IMAGE_BYTES:", report["image_bytes"])
    print("IMAGE_SHA256:", report["image_sha256"])
    print("UART_OBJECT:", serial)
    print("NOT_BOOTABLE: no canonical A733 DTS or real UART/power hardware validation")

if __name__ == "__main__":
    main()
