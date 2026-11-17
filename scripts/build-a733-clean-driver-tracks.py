#!/usr/bin/env python3
"""Stage and compile A733 upstream CCU/pinctrl independently, in fresh source copies.

Never touches pinned source, legacy PID1 build, boot image or GPIO hardware.
Requires prior successful check-a733-upstream-backport.py --adapt-* report.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

def run(args, **kwargs):
    print("+", " ".join(str(x) for x in args), flush=True)
    subprocess.run([str(x) for x in args], check=True, **kwargs)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--review", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=4)
    a = p.parse_args()
    if a.jobs < 1 or a.jobs > 64:
        p.error("--jobs must be 1..64")
    if a.output.exists():
        p.error("output directory exists; refusing overwrite")
    if not a.source.is_dir() or not (a.source / "Makefile").is_file():
        p.error("missing kernel source")
    if not a.config.is_file() or not (a.review / "review.json").is_file():
        p.error("missing clean config or review.json")
    review = json.loads((a.review / "review.json").read_text())
    if Path(review["source"]).resolve() != a.source.resolve():
        p.error("review source differs from requested source")
    if not review.get("adapt_pinctrl_rename") or not review.get("adapt_pinctrl_layout"):
        p.error("review must contain both 6.18 pinctrl adapters")
    if any(review["groups"][k]["status"] != "PASS_SOURCE_APPLICABILITY_ONLY"
           for k in ("ccu-v7", "pinctrl-base", "pinctrl-pf6")):
        p.error("source applicability review has a failed required series")
    source_hash = (a.source / "drivers/pinctrl/sunxi/pinctrl-sunxi.c").read_bytes()
    original_digest = hashlib.sha256(source_hash).hexdigest()
    a.output.mkdir(parents=True)
    results = {"source": str(a.source.resolve()), "tracks": {}, "voltage_patch": "EXCLUDED"}
    for track in ("ccu", "pinctrl"):
        tree = a.output / (track + "-linux")
        obj = a.output / (track + "-obj")
        run(["cp", "-a", "--reflink=auto", a.source, tree])
        if track == "ccu":
            patches = [a.review / ("ccu-v7-%02d.patch" % n) for n in range(1, 9)]
        else:
            # First semantic rename and full flags bridge are in the review
            # checker; apply the same strictly checked logic to this new copy.
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from importlib import import_module
            checker = import_module("check-a733-upstream-backport")
            checker.rename_first_pinctrl_patch(tree)
            patches = [a.review / ("pinctrl-base-%02d.patch" % n) for n in range(2, 8)]
        for patch in patches:
            if track == "pinctrl" and patch.name == "pinctrl-base-04.patch":
                checker.bridge_pinctrl_618_flags(tree)
            run(["git", "-C", tree, "apply", "--check", patch])
            run(["git", "-C", tree, "apply", patch])
        if track == "pinctrl":
            pf6 = a.review / "pinctrl-pf6-01.patch"
            run(["git", "-C", tree, "apply", "--check", pf6])
            run(["git", "-C", tree, "apply", pf6])
        obj.mkdir()
        shutil.copy2(a.config, obj / ".config")
        symbols = (["SUN60I_A733_CCU", "SUN60I_A733_R_CCU"] if track == "ccu"
                   else ["PINCTRL_SUN60I_A733"])
        for symbol in symbols:
            run([tree / "scripts/config", "--file", obj / ".config",
                 "--enable", symbol])
        env = dict(os.environ, ARCH="arm64", CROSS_COMPILE="aarch64-linux-gnu-")
        run(["make", "-C", tree, "O=" + str(obj), "ARCH=arm64", "olddefconfig"], env=env)
        config = (obj / ".config").read_text()
        effective = {s: "y" if "CONFIG_" + s + "=y" in config.splitlines() else "UNRESOLVED"
                     for s in symbols}
        results["tracks"][track] = {"symbols": effective, "tree": str(tree), "obj": str(obj)}
        if any(v != "y" for v in effective.values()):
            (a.output / "report.json").write_text(json.dumps(results, indent=2) + "\n")
            raise SystemExit("FAIL: required A733 symbol disabled after olddefconfig: " + str(effective))
        targets = (["drivers/clk/sunxi-ng/"] if track == "ccu"
                   else ["drivers/pinctrl/sunxi/"])
        # Build the target subtree, not the entire kernel/DTB.
        run(["make", "-C", tree, "O=" + str(obj), "ARCH=arm64",
             "CROSS_COMPILE=aarch64-linux-gnu-", "-j" + str(a.jobs)] + targets,
            env=env)
        results["tracks"][track]["build"] = "PASS_SUBTREE_ONLY"
        (a.output / "report.json").write_text(json.dumps(results, indent=2) + "\n")
    if hashlib.sha256((a.source / "drivers/pinctrl/sunxi/pinctrl-sunxi.c").read_bytes()).hexdigest() != original_digest:
        raise SystemExit("ERROR: original source changed")
    print("PASS: both isolated driver subtree builds completed; no DTB/hardware testing")

if __name__ == "__main__":
    main()
