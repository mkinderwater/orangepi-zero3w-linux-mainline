#!/usr/bin/env python3
"""Compile upstream A733 SoC DTS with a synthetic board stub (NOT BOOTABLE).

Read-only inputs. No PMIC compatible alias, regulator consumers, or firmware image.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

def command(args, *, stdout=None):
    print("+", " ".join(str(x) for x in args), flush=True)
    return subprocess.run([str(x) for x in args], stdout=stdout,
                          capture_output=stdout is None, text=stdout is None)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True,
                   help="Prepared source tree with upstream v3 sun60i-a733.dtsi")
    p.add_argument("--output", type=Path, required=True,
                   help="New, empty output directory")
    a = p.parse_args()
    source = a.source.resolve()
    dts_dir = source / "arch/arm64/boot/dts/allwinner"
    soc = dts_dir / "sun60i-a733.dtsi"
    if not soc.is_file() or not (source / "Makefile").is_file():
        p.error("Prepared Linux source or upstream A733 SoC DTS absent")
    if a.output.exists() or source == a.output.resolve() or source in a.output.resolve().parents:
        p.error("Output exists or overlaps Linux source; refusing overwrite")
    a.output.mkdir(parents=True)
    stub = a.output / "a733-soc-syntax-only.dts"
    preprocessed = a.output / "a733-soc-syntax-only.preprocessed.dts"
    dtb = a.output / "a733-soc-syntax-only.dtb"
    stub.write_text(
        "/dts-v1/;\n"
        '#include "sun60i-a733.dtsi"\n'
        "/ {\n"
        '    model = "A733 source syntax test, NOT A BOARD";\n'
        '    compatible = "test,a733-soc-syntax-only", "allwinner,sun60i-a733";\n'
        "};\n"
    )
    cpp = ["cpp", "-nostdinc", "-undef", "-D__DTS__",
           "-I", source / "include",
           "-I", dts_dir, "-x", "assembler-with-cpp",
           "-o", preprocessed, stub]
    r = command(cpp)
    report = {
        "status": "CPP_FAILED" if r.returncode else "CPP_PASS",
        "source_dtsi": str(soc),
        "source_sha256": hashlib.sha256(soc.read_bytes()).hexdigest(),
        "synthetic_board_only": True,
        "hardware_validation": "NONE",
        "pmic_alias_or_regulator_write": "NONE",
        "cpp_returncode": r.returncode,
        "cpp_stderr": r.stderr,
    }
    def save():
        (a.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    if r.returncode:
        print(r.stderr[-12000:])
        print("DTB_CPP_FAILED; see report.json")
        return 1
    cmd = ["dtc", "-I", "dts", "-O", "dtb", "-o", dtb, preprocessed]
    r = command(cmd)
    report["dtc_returncode"] = r.returncode
    report["dtc_stderr"] = r.stderr
    report["status"] = "DTC_FAILED" if r.returncode else "DTC_PASS_SYNTHETIC_ONLY"
    if r.returncode == 0:
        report["dtb_size"] = dtb.stat().st_size
        report["dtb_sha256"] = hashlib.sha256(dtb.read_bytes()).hexdigest()
    save()
    if r.stderr:
        print("DTC DIAGNOSTICS:\n" + r.stderr[-16000:])
    print("STATUS:", report["status"])
    print("REPORT:", a.output / "report.json")
    if r.returncode == 0:
        print("SYNTHETIC_DTB:", dtb)
    print("NOT a Zero 3W board DTB. No voltage, serial or hardware boot claim.")
    return 0 if r.returncode == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
