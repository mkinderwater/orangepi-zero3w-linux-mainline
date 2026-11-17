#!/usr/bin/env python3
"""Compile upstream AXP318W v8 independently from clean Linux 6.18.

Source-only exercise, never uses an AXP8191-compatible alias or accesses a PMIC.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

def run(*argv, env=None):
    argv = [str(arg) for arg in argv]
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, env=env, check=True)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--review", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    if a.jobs < 1 or a.jobs > 64 or a.output.exists():
        ap.error("Invalid job count or output exists; refusing overwrite")
    if not (a.source / "Makefile").is_file() or not a.config.is_file():
        ap.error("Missing Linux source or clean .config")
    results = json.loads((a.review / "review.json").read_text())
    if results.get("status") != "SOURCE_APPLICABILITY_ONLY" or len(results.get("patches", [])) != 5:
        ap.error("Five verified source-applicable patches are required")
    if not all(x.get("check") and x.get("scratch_applied") for x in results["patches"]):
        ap.error("AXP318W source applicability has an unresolved conflict")
    if Path(results["source"]).resolve() != a.source.resolve():
        ap.error("Source tree differs from the reviewed source")
    if a.output.resolve() == a.source.resolve() or a.source.resolve() in a.output.resolve().parents:
        ap.error("Output must not be inside the pinned source tree")
    tree = a.output / "linux"
    obj = a.output / "obj"
    a.output.mkdir(parents=True)
    run("cp", "-a", "--reflink=auto", a.source, tree)
    original_sha = hashlib.sha256((a.source / "drivers/mfd/axp20x.c").read_bytes()).hexdigest()
    report = {"state": "PATCH_STAGING", "source": str(a.source), "voltage_writes": "NONE",
              "original_mfd_sha256": original_sha, "pmic_identity": "UNVERIFIED",
              "dc1sw2_swout2_equivalence": "UNVERIFIED"}
    def save():
        (a.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    for i in range(1, 6):
        patch = a.review / f"axp318w-v8-{i:02d}.patch"
        if not patch.is_file():
            ap.error("Missing reviewed patch " + str(patch))
        run("git", "-C", tree, "apply", "--check", patch)
        run("git", "-C", tree, "apply", patch)
    obj.mkdir()
    shutil.copy2(a.config, obj / ".config")
    for key in ("I2C", "MFD_AXP20X_I2C", "REGULATOR_AXP20X"):
        run(tree / "scripts/config", "--file", obj / ".config", "--enable", key)
    env = dict(os.environ, ARCH="arm64", CROSS_COMPILE="aarch64-linux-gnu-")
    run("make", "-C", tree, f"O={obj}", "ARCH=arm64", "olddefconfig", env=env)
    actual = (obj / ".config").read_text()
    needed = ("I2C", "MFD_AXP20X", "MFD_AXP20X_I2C", "REGULATOR_AXP20X")
    report["config"] = {k: ("y" if f"CONFIG_{k}=y" in actual.splitlines() else "UNRESOLVED") for k in needed}
    if any(x != "y" for x in report["config"].values()):
        report["state"] = "CONFIG_BLOCKED"
        save()
        raise SystemExit("Required PMIC config missing: " + str(report["config"]))
    report["state"] = "BUILDING"
    save()
    try:
        run("make", "-C", tree, f"O={obj}", "ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-", f"-j{a.jobs}",
            "drivers/mfd/", "drivers/regulator/", env=env)
    except subprocess.CalledProcessError:
        report["state"] = "BUILD_FAILED"
        save()
        raise
    objects = [obj / "drivers/mfd/axp20x.o", obj / "drivers/mfd/axp20x-i2c.o",
               obj / "drivers/regulator/axp20x-regulator.o"]
    report["objects"] = {str(x.relative_to(obj)): x.is_file() for x in objects}
    report["state"] = "PASS_SUBTREE_ONLY" if all(x.is_file() for x in objects) else "OBJECT_MISSING"
    save()
    if report["state"] != "PASS_SUBTREE_ONLY":
        raise SystemExit("Expected AXP objects missing")
    if hashlib.sha256((a.source / "drivers/mfd/axp20x.c").read_bytes()).hexdigest() != original_sha:
        raise SystemExit("Pinned original source changed")
    print("AXP318W_MFD_REGULATOR_COMPILE_PASS")
    print("NOT_HARDWARE_VALIDATED: do not bind AXP8191 to AXP318W until register identity confirmed")

if __name__ == "__main__":
    main()
