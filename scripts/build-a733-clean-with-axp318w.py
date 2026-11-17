#!/usr/bin/env python3
"""Full ARM64 link: proven CCU+pinctrl combined track plus upstream AXP318W PMIC.

No DTB generation, no boot media, no voltage I/O, no AXP8191-compatible alias.
All inputs are immutable; build output must be a new directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ALLOWED = (
    "drivers/mfd/axp20x.c",
    "drivers/mfd/axp20x-i2c.c",
    "drivers/mfd/axp20x-rsb.c",
    "drivers/regulator/axp20x-regulator.c",
    "include/linux/mfd/axp20x.h",
    "Documentation/devicetree/bindings/mfd/x-powers,axp152.yaml",
)
REQUIRED = ("SUN60I_A733_CCU", "SUN60I_A733_R_CCU",
            "PINCTRL_SUN60I_A733", "MMC_SUNXI",
            "I2C", "MFD_AXP20X", "MFD_AXP20X_I2C", "REGULATOR_AXP20X")

def output(*command):
    return subprocess.check_output([str(x) for x in command], stderr=subprocess.STDOUT)

def run(*command, env=None):
    print("+", " ".join(str(x) for x in command), flush=True)
    subprocess.run([str(x) for x in command], check=True, env=env)

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def changed(tree):
    raw = output("git", "-C", tree, "status", "--porcelain", "-z", "--untracked-files=all")
    # Git status porcelain -z includes rename second paths, which must never occur here.
    result = set()
    for record in raw.split(b"\0"):
        if not record:
            continue
        status = record[:2].decode("ascii", "replace")
        if "R" in status or "C" in status:
            raise ValueError("Renamed/copied paths are forbidden in PMIC track")
        result.add(record[3:].decode("utf-8", "surrogateescape"))
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--combined-tree", required=True, type=Path,
                   help="Existing known-good clean CCU+pinctrl source tree")
    p.add_argument("--pmic-tree", required=True, type=Path,
                   help="Successfully compiled, isolated upstream PMIC source tree")
    p.add_argument("--config", required=True, type=Path,
                   help="Original minimal clean config, not the PMIC subtree config")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--jobs", type=int, default=4)
    a = p.parse_args()
    a.combined_tree = a.combined_tree.resolve()
    a.pmic_tree = a.pmic_tree.resolve()
    a.output = a.output.resolve()
    if a.jobs < 1 or a.jobs > 64 or a.output.exists():
        p.error("Invalid job count or existing output; refusing overwrite")
    if a.combined_tree == a.pmic_tree or any(
        a.output == x or x in a.output.parents
        for x in (a.combined_tree, a.pmic_tree)
    ):
        p.error("Output must be separate from source trees")
    if not a.config.is_file():
        p.error("Clean config missing")
    for tree in (a.combined_tree, a.pmic_tree):
        if not (tree / "Makefile").is_file():
            p.error(f"Kernel source tree missing: {tree}")
    revs = [output("git", "-C", t, "rev-parse", "HEAD").decode().strip()
            for t in (a.combined_tree, a.pmic_tree)]
    if revs[0] != revs[1]:
        p.error("Upstream base commits differ. Do not merge")
    all_changes = changed(a.pmic_tree)
    if not all_changes or not all_changes.issubset(set(ALLOWED)):
        p.error("Unexpected PMIC source changes: " + repr(sorted(all_changes)))
    # AXP318W five-patch series must change every expected path.
    if all_changes != set(ALLOWED):
        p.error("Incomplete five-patch PMIC track. Present: " + repr(sorted(all_changes)))
    for path in all_changes:
        if not (a.pmic_tree / path).is_file():
            p.error("Missing PMIC file: " + path)
        # A733 CCU+pinctrl changes must not touch any PMIC source file.
        if (a.combined_tree / path).read_bytes() != output(
                "git", "-C", a.combined_tree, "show", f"HEAD:{path}"):
            p.error("Combined source already modifies PMIC path: " + path)

    a.output.mkdir(parents=True)
    combined = a.output / "linux"
    obj = a.output / "obj"
    run("cp", "-a", "--reflink=auto", a.combined_tree, combined)
    for name in sorted(all_changes):
        dst = combined / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(a.pmic_tree / name, dst)
    obj.mkdir()
    shutil.copy2(a.config, obj / ".config")
    for symbol in ("I2C", "MFD_AXP20X_I2C", "REGULATOR_AXP20X",
                   "SUN60I_A733_CCU", "SUN60I_A733_R_CCU", "PINCTRL_SUN60I_A733"):
        run(combined / "scripts/config", "--file", obj / ".config", "--enable", symbol)
    env = dict(os.environ, ARCH="arm64", CROSS_COMPILE="aarch64-linux-gnu-")
    run("make", "-C", combined, f"O={obj}", "ARCH=arm64", "olddefconfig", env=env)
    cfg = (obj / ".config").read_text().splitlines()
    missing = [s for s in REQUIRED if f"CONFIG_{s}=y" not in cfg]
    report = {"source_commit": revs[0],
              "pmic_paths": sorted(all_changes),
              "voltage_test": "NOT PERFORMED",
              "chip_identity": "UNVERIFIED",
              "board_dtb": "NOT INCLUDED",
              "original_combined_tree": str(a.combined_tree),
              "status": "CONFIG_CHECK"}
    def save():
        (a.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if missing:
        report["status"] = "CONFIG_FAILED"
        report["missing_config"] = missing
        save()
        p.error("Missing config: " + repr(missing))
    report["status"] = "LINK_STARTED"
    save()
    try:
        run("make", "-C", combined, f"O={obj}", "ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-", f"-j{a.jobs}", "Image", env=env)
    except subprocess.CalledProcessError:
        report["status"] = "LINK_FAILED"
        save()
        raise
    image = obj / "arch/arm64/boot/Image"
    if not image.is_file():
        raise RuntimeError("Build returned success but Image missing")
    system_map = (obj / "System.map").read_text()
    required_symbols = ("sun60i_a733_ccu_probe", "sun60i_a733_r_ccu_probe",
                        "a733_pinctrl_driver_init", "axp20x_i2c_probe")
    # MFD and regulator functions can be inlined/renamed. Verify objects separately.
    missing_symbols = [s for s in required_symbols if s not in system_map]
    objects = ("drivers/mfd/axp20x.o", "drivers/mfd/axp20x-i2c.o",
               "drivers/regulator/axp20x-regulator.o")
    missing_objects = [s for s in objects if not (obj / s).is_file()]
    report.update({"image_bytes": image.stat().st_size,
                   "image_sha256": sha256(image),
                   "missing_symbols": missing_symbols,
                   "missing_objects": missing_objects,
                   "status": "LINK_PASS" if not missing_symbols and not missing_objects
                             else "LINK_PASS_REVIEW_SYMBOLS"})
    save()
    print("CLEAN_CCU_PINCTRL_AXP318W_IMAGE:", image)
    print("SIZE_BYTES:", image.stat().st_size)
    print("SHA256:", report["image_sha256"])
    print("STATUS:", report["status"])
    if missing_symbols or missing_objects:
        print("REVIEW_MISSING_SYMBOLS:", missing_symbols)
        print("REVIEW_MISSING_OBJECTS:", missing_objects)
    print("No AXP8191 alias, no board DTB, no boot or voltage validation.")

if __name__ == "__main__":
    main()
