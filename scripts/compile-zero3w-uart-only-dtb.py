#!/usr/bin/env python3
"""Compile Zero 3W UART-only board DTS against the previously tested A733 v3 SoC.

Input Linux source tree is never changed. Output DTB is for static review only.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

def call(args):
    cmd = [str(a) for a in args]
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, capture_output=True, text=True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--board", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists() or not a.board.is_file():
        p.error("Existing output or missing board DTS")
    source = a.source.resolve()
    soc_dir = source / "arch/arm64/boot/dts/allwinner"
    if not (soc_dir / "sun60i-a733.dtsi").is_file():
        p.error("Upstream A733 SoC DTS missing")
    a.output.mkdir(parents=True)
    prep = a.output / "zero3w-uart-only.preprocessed.dts"
    dtb = a.output / "sun60i-a733-orangepi-zero3w-uart-only.dtb"
    report = {"status": "NOT_STARTED", "source": str(source),
              "board_sha256": hashlib.sha256(a.board.read_bytes()).hexdigest(),
              "hardware_validation": "NONE", "pmic": "DISABLED",
              "mmc": "DISABLED", "memory_fixups": "FIRMWARE_REQUIRED"}
    def save():
        (a.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    def stage(name, cmd):
        result = call(cmd)
        (a.output / (name + ".stdout")).write_text(result.stdout)
        (a.output / (name + ".stderr")).write_text(result.stderr)
        return result
    cpp = ["cpp", "-nostdinc", "-undef", "-D__DTS__",
           "-I", source / "include", "-I", soc_dir,
           "-x", "assembler-with-cpp", "-o", prep, a.board]
    r = stage("cpp", cpp)
    if r.returncode:
        report["status"] = "CPP_FAILED"
        save()
        print(r.stderr[-10000:])
        return 1
    r = stage("dtc", ["dtc", "-I", "dts",
                      "-O", "dtb", "-o", dtb, prep])
    if r.returncode:
        report["status"] = "DTC_FAILED"
        save()
        print(r.stderr[-10000:])
        return 1
    # Read back the binary via dtc and verify both policy and structural items.
    decoded = a.output / "zero3w-uart-only.decoded.dts"
    r = stage("decode", ["dtc", "-I", "dtb", "-O", "dts", "-o", decoded, dtb])
    if r.returncode:
        report["status"] = "DECODE_FAILED"
        save()
        return 1
    data = decoded.read_text()
    # These are useful structural policy assertions, not substitutes for dt-schema.
    checks = {
        "model": "Xunlong Orange Pi Zero 3W (UART-only validation)" in data,
        "console_alias": "serial0 = " in data and "serial@2500000" in data,
        "console_stdout": 'stdout-path = "serial0:115200n8"' in data,
        "no_axp318w_alias": "x-powers,axp318w" not in data,
        "no_bootargs_override": "bootargs =" not in a.board.read_text(),
        "no_fixed_memory_size": "memory@" not in a.board.read_text(),
    }
    # Check status by parsing the node block in the dtc text, not a global search.
    import re
    for name, node in (("mmc0_disabled", "mmc@4020000"),
                       ("r_i2c0_disabled", "i2c@7083000")):
        match = re.search(r"\b" + re.escape(node) + r"\s*\{(.*?)\n\s*\};", data, re.S)
        checks[name] = bool(match and re.search(r'status\s*=\s*"disabled";', match.group(1)))
    report["checks"] = checks
    report["dtb_bytes"] = dtb.stat().st_size
    report["dtb_sha256"] = hashlib.sha256(dtb.read_bytes()).hexdigest()
    report["status"] = "DTC_PASS_UART_ONLY_NOT_BOOT_VALIDATED" if all(checks.values()) else "DTC_PASS_POLICY_REVIEW"
    save()
    print("STATUS:", report["status"])
    print("CHECKS:", checks)
    print("DTB:", dtb)
    print("SHA256:", report["dtb_sha256"])
    if r.stderr:
        print("DECODE WARNINGS:", r.stderr[-5000:])
    print("Do not flash until static review and boot-image-specific memory/initrd fixups.")
    return 0 if all(checks.values()) else 2

if __name__ == "__main__":
    raise SystemExit(main())
