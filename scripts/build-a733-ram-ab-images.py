#!/usr/bin/env python3
"""Build two distinct RAM A/B DTBs and fresh test image COPIES from known control.

No kernel recompilation, bootloader modification, PMIC writes, or physical media writes.
The existing 2 GiB disk image is only read. Manual U-Boot start from mmc 0:2.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

BASE_SHA = "3bb7d274d5e5110189d240b555fd959481f2a855314f86695abf838b5c252145"
FAT_OFFSET = 65536 * 512
EXPECTED_SIZE = 2147483648
RAM_A = [0, 0x40000000, 0, 0x40000000]
RAM_B = [0, 0x40000000, 0, 0x08000000, 0, 0x49000000, 0, 0x37000000]
BL31 = [0, 0x48000000, 0, 0x01000000]

def run(args, *, capture=False):
    args = [str(x) for x in args]
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, check=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None,
                          text=capture)

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def fdt_cells(dtb, path, prop):
    value = run(["fdtget", "-t", "x", dtb, path, prop], capture=True).stdout.strip()
    return [int(x, 16) for x in value.split()]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path, help="Pinned Linux tree with upstream A733 v3 SoC DTS")
    p.add_argument("--control", required=True, type=Path, help="Known 2GiB UART image built on M2dc")
    p.add_argument("--output", required=True, type=Path, help="NEW directory for two .img files")
    args = p.parse_args()
    script_dir = Path(__file__).resolve().parent.parent
    src = args.source.resolve()
    control = args.control.resolve()
    output = args.output.resolve()
    if output.exists() or output == control or output in control.parents:
        p.error("Output exists or overlaps control")
    if not (src / "arch/arm64/boot/dts/allwinner/sun60i-a733.dtsi").is_file():
        p.error("Upstream A733 SoC DTS missing")
    if not control.is_file() or control.stat().st_size != EXPECTED_SIZE or digest(control) != BASE_SHA:
        p.error("Control disk size/SHA256 mismatch; refuse changes")
    for cmd in ("cpp", "dtc", "fdtget", "mcopy"):
        if not shutil.which(cmd):
            p.error(f"Missing tool {cmd}")
    board_dir = src / "arch/arm64/boot/dts/allwinner"
    input_files = {key: script_dir / "dts" / f"sun60i-a733-orangepi-zero3w-ram-{key}.dts"
                   for key in "ab"}
    for path in input_files.values():
        if not path.is_file():
            p.error(f"Board source missing {path}")
    output.mkdir(parents=True)
    report = {"state": "COMPILING", "control_sha256": BASE_SHA, "variants": {},
              "boot_policy": "NO AUTOBOOT CHANGE; MANUAL mmc 0:2 boot.scr",
              "hardware_result": "NOT TESTED"}
    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    for key in "ab":
        name = f"a733-ram-{key}"
        folder = output / name
        folder.mkdir()
        prep = folder / "board.preprocessed.dts"
        dtb = folder / "sun60i-a733-orangepi-zero3w.dtb"
        run(["cpp", "-nostdinc", "-undef", "-D__DTS__",
             "-I", src / "include", "-I", board_dir,
             "-x", "assembler-with-cpp", "-o", prep, input_files[key]])
        run(["dtc", "-I", "dts", "-O", "dtb", "-o", dtb, prep])
        ram = fdt_cells(dtb, "/memory@40000000", "reg")
        expected = RAM_A if key == "a" else RAM_B
        if ram != expected:
            raise ValueError(f"RAM-{key.upper()} reg differs: {ram} != {expected}")
        if run(["fdtget", "-t", "s", dtb, "/memory@40000000", "device_type"],
               capture=True).stdout.strip() != "memory":
            raise ValueError("Missing device_type=memory")
        if key == "a":
            if fdt_cells(dtb, "/reserved-memory/bl31@48000000", "reg") != BL31:
                raise ValueError("RAM-A BL31 carveout incorrect")
            props = run(["fdtget", "-p", dtb, "/reserved-memory/bl31@48000000"],
                        capture=True).stdout.split()
            if "no-map" not in props:
                raise ValueError("RAM-A lacks BL31 no-map")
        else:
            # RAM-B has no need to add a separate BL31 carveout: it isn't in usable RAM.
            test = subprocess.run(["fdtget", dtb, "/reserved-memory/bl31@48000000", "reg"],
                                  capture_output=True)
            if test.returncode == 0:
                raise ValueError("RAM-B unexpectedly includes extra BL31 reservation")
        for node in ("/soc@0/mmc@4020000", "/soc@0/i2c@7083000"):
            if run(["fdtget", "-t", "s", dtb, node, "status"], capture=True).stdout.strip() != "disabled":
                raise ValueError(f"Unsafe enabled node: {node}")
        probe = subprocess.run(["fdtget", dtb, "/soc@0/i2c@7083000/pmic@36", "compatible"],
                               capture_output=True)
        if probe.returncode == 0:
            raise ValueError("Unexpected PMIC node")
        image = output / f"a733-clean-uart-ram-{key}-v1.img"
        run(["cp", "--reflink=auto", "--sparse=always", "--", control, image])
        address = f"{image}@@{FAT_OFFSET}"
        run(["mcopy", "-o", "-i", address, dtb, "::mainline/sun60i-a733-orangepi-zero3w.dtb"])
        check = folder / "readback.dtb"
        run(["mcopy", "-i", address, "::mainline/sun60i-a733-orangepi-zero3w.dtb", check])
        if digest(check) != digest(dtb):
            raise ValueError("FAT roundtrip mismatch")
        report["variants"][key] = {
            "dtb_sha256": digest(dtb), "dtb_bytes": dtb.stat().st_size,
            "image": str(image), "image_sha256": digest(image),
            "image_bytes": image.stat().st_size, "memory_cells": expected,
            "status": "IMAGE_STAGED_UNBOOTED",
        }
        save()
        print(f"RAM_{key.upper()}_IMAGE_READY:", image)
        print(f"RAM_{key.upper()}_IMAGE_SHA256:", report["variants"][key]["image_sha256"])
    report["state"] = "TWO_IMAGES_BUILT_NOT_HARDWARE_TESTED"
    save()
    print("TWO_IMAGES_BUILT_NOT_HARDWARE_TESTED")
    print("Do not overwrite known-good control; write one test image per separate card.")
    print("Each image still requires MANUAL U-Boot loading from FAT mmc 0:2.")

if __name__ == "__main__":
    main()
