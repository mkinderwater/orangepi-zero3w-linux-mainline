#!/usr/bin/env python3
"""Make a separate earlycon-only image from pinned RAM-A disk, never mutate the input."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

FAT_OFFSET = 65536 * 512
IMAGE_BYTES = 2147483648
EXPECTED_RAM = [0, 0x40000000, 0, 0x40000000]
EXPECTED_BL31 = [0, 0x48000000, 0, 0x01000000]
DTB_NAME = "sun60i-a733-orangepi-zero3w.dtb"

def call(*args, text=False):
    args = [str(x) for x in args]
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, check=True, capture_output=text, text=text)

def sha256(p):
    digest = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def prop(dtb, node, key, mode="x"):
    return call("fdtget", "-t", mode, dtb, node, key, text=True).stdout.strip()

def cells(dtb, node, key):
    return [int(x, 16) for x in prop(dtb, node, key).split()]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path,
                   help="Pinned Linux tree containing sun60i-a733.dtsi")
    p.add_argument("--ram-a-image", required=True, type=Path,
                   help="Already booted RAM-A 2GiB image to copy, never edit")
    p.add_argument("--output", required=True, type=Path,
                   help="New, nonexistent output directory")
    args = p.parse_args()

    root = Path(__file__).resolve().parent.parent
    src = args.source.resolve()
    original = args.ram_a_image.resolve()
    output = args.output.resolve()
    board = root / "dts/sun60i-a733-orangepi-zero3w-ram-a-earlycon-only.dts"
    soc = src / "arch/arm64/boot/dts/allwinner/sun60i-a733.dtsi"
    if not soc.is_file() or not board.is_file():
        p.error("Missing pinned A733 SoC DTS or earlycon-only board DTS")
    if not original.is_file() or original.stat().st_size != IMAGE_BYTES:
        p.error("Expected complete 2 GiB RAM-A image; no change made")
    if output.exists() or output == original or output in original.parents:
        p.error("Output path exists or overlaps input; no change made")
    for name in ("cpp", "dtc", "fdtget", "mcopy"):
        if shutil.which(name) is None:
            p.error(f"Missing tool: {name}")
    output.mkdir(parents=True)
    expanded = output / "board.dts"
    dtb = output / DTB_NAME
    call("cpp", "-nostdinc", "-undef", "-D__DTS__", "-I", src / "include",
         "-I", soc.parent, "-x", "assembler-with-cpp", "-o", expanded, board)
    call("dtc", "-I", "dts", "-O", "dtb", "-o", dtb, expanded)
    if cells(dtb, "/memory@40000000", "reg") != EXPECTED_RAM:
        raise ValueError("Wrong RAM-A 1GiB node")
    if cells(dtb, "/reserved-memory/bl31@48000000", "reg") != EXPECTED_BL31:
        raise ValueError("Missing 16MiB BL31 carveout")
    if "no-map" not in call("fdtget", "-p", dtb, "/reserved-memory/bl31@48000000", text=True).stdout.split():
        raise ValueError("BL31 no-map absent")
    # Verify UART0 is disabled in the compiled tree, not merely the source.
    uart_nodes = call("fdtget", "-l", dtb, "/soc@0", text=True).stdout.split()
    uart_path = next((f"/soc@0/{n}" for n in uart_nodes if n == "serial@2500000"), None)
    if uart_path is None or prop(dtb, uart_path, "status", "s") != "disabled":
        raise ValueError("Native UART0 is not disabled in compiled DTB")
    image = output / "a733-clean-ram-a-earlycon-only-v1.img"
    call("cp", "--reflink=auto", "--sparse=always", "--", original, image)
    fat = f"{image}@@{FAT_OFFSET}"
    call("mcopy", "-o", "-i", fat, dtb, "::mainline/" + DTB_NAME)
    readback = output / "fat-dtb-readback.dtb"
    call("mcopy", "-i", fat, "::mainline/" + DTB_NAME, readback)
    if sha256(readback) != sha256(dtb):
        raise ValueError("FAT copy verification failed")
    report = {
        "state": "STAGED_UNBOOTED", "base": str(original),
        "base_sha256": sha256(original), "image": str(image),
        "image_sha256": sha256(image),
        "dtb_sha256": sha256(dtb),
        "ram": "1 GiB 0x40000000, BL31 16MiB no-map 0x48000000",
        "native_uart0": "disabled", "earlycon": "firmware-programmed",
        "boot": "manual mmc 0:2 boot.scr", "notes": "UART input in Linux not expected"
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("EARLYCON_ONLY_IMAGE_READY", image)
    print("SHA256", report["image_sha256"])
    print("Original RAM-A remains unchanged")

if __name__ == "__main__":
    main()
