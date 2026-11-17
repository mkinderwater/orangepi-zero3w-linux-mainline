#!/usr/bin/env python3
"""Combine independently compiled A733 CCU and pinctrl tracks and link ARM64 Image.

Copies only changed/added tracked source paths. Never changes either source track,
pinned upstream Linux, existing PID1 image, or boot media.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

def run(args, *, cwd=None, env=None):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)

def git_output(tree, *args):
    return subprocess.check_output(["git", "-C", str(tree), *args])

def changed_files(tree):
    # NUL-delimited, safe for arbitrary supported filenames.
    tracked = git_output(tree, "diff", "--name-only", "-z", "HEAD")
    staged = git_output(tree, "diff", "--cached", "--name-only", "-z", "HEAD")
    untracked = git_output(tree, "ls-files", "--others", "--exclude-standard", "-z")
    def names(raw):
        return {x.decode("utf-8", "surrogateescape") for x in raw.split(b"\0") if x}
    return names(tracked) | names(staged) | names(untracked)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True, help="Unchanged pinned upstream tree")
    p.add_argument("--ccu-tree", type=Path, required=True, help="Successful CCU-only source tree")
    p.add_argument("--pinctrl-tree", type=Path, required=True, help="Successful pinctrl-only source tree")
    p.add_argument("--config", type=Path, required=True, help="Fresh, minimal v3 .config")
    p.add_argument("--output", type=Path, required=True, help="Brand-new output directory")
    p.add_argument("--jobs", type=int, default=4)
    a = p.parse_args()
    for key in ("source", "ccu_tree", "pinctrl_tree", "output"):
        setattr(a, key, getattr(a, key).resolve())
    if a.jobs < 1 or a.jobs > 64 or a.output.exists():
        p.error("Invalid job count or output exists; refusing overwrite")
    paths = (a.source, a.ccu_tree, a.pinctrl_tree)
    if len(set(paths)) != 3 or any(a.output == x or x in a.output.parents for x in paths):
        p.error("Source trees must be separate; output must not be inside a source tree")
    if not a.config.is_file() or any(not (x / "Makefile").is_file() for x in paths):
        p.error("Source or config is missing")
    commits = {str(x): git_output(x, "rev-parse", "HEAD").decode().strip() for x in paths}
    if len(set(commits.values())) != 1:
        p.error("Source tracks do not share the pinned upstream HEAD")
    if git_output(a.source, "status", "--porcelain"):
        p.error("Pinned upstream source is dirty; refusing ambiguous merge")

    maps = {}
    allowed = {
        "ccu": ("drivers/clk/sunxi-ng/", "include/dt-bindings/clock/",
                "include/dt-bindings/reset/", "Documentation/devicetree/bindings/clock/"),
        "pinctrl": ("drivers/pinctrl/sunxi/", "Documentation/devicetree/bindings/pinctrl/",
                    "include/dt-bindings/pinctrl/"),
    }
    for name, tree in (("ccu", a.ccu_tree), ("pinctrl", a.pinctrl_tree)):
        changed = changed_files(tree)
        if not changed:
            p.error(name + " source track has no changes")
        if any(not value.startswith(allowed[name]) or
               ".." in Path(value).parts or Path(value).is_absolute()
               for value in changed):
            p.error(name + " has unexpected changed paths: " + repr(sorted(changed)))
        if any(not (tree / value).is_file() for value in changed):
            p.error(name + " contains deleted or non-file paths; review manually")
        maps[name] = sorted(changed)
    overlap = set(maps["ccu"]) & set(maps["pinctrl"])
    if overlap:
        p.error("CCU and pinctrl modify overlapping files: " + repr(sorted(overlap)))

    source_head_before = git_output(a.source, "status", "--porcelain")
    a.output.mkdir(parents=True)
    combined = a.output / "linux"
    obj = a.output / "obj"
    run(["cp", "-a", "--reflink=auto", a.source, combined])
    for name, donor in (("ccu", a.ccu_tree), ("pinctrl", a.pinctrl_tree)):
        for value in maps[name]:
            target = combined / value
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(donor / value, target)
    obj.mkdir()
    shutil.copy2(a.config, obj / ".config")
    for symbol in ("SUN60I_A733_CCU", "SUN60I_A733_R_CCU", "PINCTRL_SUN60I_A733"):
        run([combined / "scripts/config", "--file", obj / ".config", "--enable", symbol])
    env = os.environ.copy()
    env.update(ARCH="arm64", CROSS_COMPILE="aarch64-linux-gnu-")
    run(["make", "-C", combined, f"O={obj}", "ARCH=arm64", "olddefconfig"], env=env)
    config = (obj / ".config").read_text().splitlines()
    required = ("SUN60I_A733_CCU", "SUN60I_A733_R_CCU", "PINCTRL_SUN60I_A733",
                "MMC_SUNXI", "MMC_BLOCK", "EXT4_FS", "BLK_DEV_INITRD")
    missing = [x for x in required if f"CONFIG_{x}=y" not in config]
    if missing:
        p.error("Config unresolved: " + ", ".join(missing))
    manifest = {"base_commit": next(iter(commits.values())),
                "status": "SOURCE_COMBINED_NO_KERNEL_BUILD_YET",
                "source_changed_paths": maps,
                "config": str(obj / ".config"),
                "unsafe_voltage_patch": "EXCLUDED",
                "warning": "Even a linked Image is NOT a bootable Zero 3W kernel without MMC/PMIC/DTS"}
    (a.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        run(["make", "-C", combined, f"O={obj}", "ARCH=arm64",
             "CROSS_COMPILE=aarch64-linux-gnu-", f"-j{a.jobs}", "Image"], env=env)
    except subprocess.CalledProcessError:
        manifest["status"] = "LINK_FAILED"
        (a.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        raise
    image = obj / "arch/arm64/boot/Image"
    if not image.is_file():
        raise RuntimeError("Image target returned success but Image missing")
    manifest["status"] = "ARM64_IMAGE_LINK_PASS_NO_BOOT_CLAIM"
    manifest["image_size"] = image.stat().st_size
    manifest["image_sha256"] = sha(image)
    (a.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if git_output(a.source, "status", "--porcelain") != source_head_before:
        raise RuntimeError("Original source was modified")
    print("COMBINED_IMAGE_PASS:", image)
    print("IMAGE_SHA256:", manifest["image_sha256"])
    print("NOT_BOOTABLE: A733 MMC/PMIC/DTS still require integration and hardware validation")

if __name__ == "__main__":
    main()
