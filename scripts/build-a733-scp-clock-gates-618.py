#!/usr/bin/env python3
"""Audit A733 CCU critical gates and stage Nov 12 SCP gate protection.

Input should be the compiled try3 Linux 6.18 source. All changes occur in a
new copy. A missing expected CCU critical gate fails closed, rather than
guessing how to repair incomplete CCU v7 source. The SCP patch addresses
firmware clock retention, not a proven UART baud-rate fix.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

CRITICAL_MAIN = ("ahb_cpus_clk", "mbus_store_clk", "gic_clk", "mbus_clk")
SCP = {
    "bus_r_msgbox_clk": "bus-r-msgbox",
    "bus_r_riscv_clk": "bus-r-riscv",
}
def call(*args):
    argv = [str(x) for x in args]
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, check=True)

def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def gate(text, symbol):
    # All A733 CCU declarations use static SUNXI_CCU_* macro statements.
    matches = re.findall(
        r"(?ms)^\s*static\s+SUNXI_CCU_[A-Z0-9_]+\s*\(\s*"
        + re.escape(symbol) + r"\s*,.*?\);", text)
    if len(matches) != 1:
        raise ValueError(f"Gate {symbol}: expected one declaration, found {len(matches)}")
    return matches[0]

def mark_gate(text, symbol):
    declaration = gate(text, symbol)
    if "CLK_IS_CRITICAL" in declaration:
        return text, "ALREADY_CRITICAL"
    # Guard known v7 gates (no reorder or parent modifications).
    if re.search(r",\s*0\s*\);\s*$", declaration) is None:
        raise ValueError(f"{symbol}: unexpected nonzero flags; refusing automatic edit")
    updated = re.sub(r",\s*0\s*\);\s*$",
                     ", CLK_IS_CRITICAL);", declaration)
    if updated == declaration:
        raise ValueError(f"{symbol}: edit failed")
    return text.replace(declaration, updated, 1), "PATCHED"

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True,
                   help="Completed UART try3 Linux tree, not vendor kernel")
    p.add_argument("--config", type=Path, required=True,
                   help="Proven UART try3 .config")
    p.add_argument("--output", type=Path, required=True,
                   help="New, nonexistent destination")
    p.add_argument("--jobs", type=int, default=4)
    args = p.parse_args()
    src, dst = args.source.resolve(), args.output.resolve()
    mainccu = src / "drivers/clk/sunxi-ng/ccu-sun60i-a733.c"
    prcm = src / "drivers/clk/sunxi-ng/ccu-sun60i-a733-r.c"
    uart = src / "drivers/tty/serial/8250/8250_dw.c"
    if dst.exists() or dst == src or dst in src.parents:
        p.error("Destination exists or overlaps source")
    if not all(x.is_file() for x in (mainccu, prcm, uart, args.config)):
        p.error("Missing A733 CCU, PRCM, UART source or compiled .config")
    if not (1 <= args.jobs <= 64):
        p.error("--jobs must be 1..64")
    for executable in ("make", "cp", "aarch64-linux-gnu-gcc"):
        if not shutil.which(executable):
            p.error(f"Missing {executable}")

    dst.mkdir(parents=True)
    result = {"state": "AUDITING", "source": str(src),
              "candidate": "A733 6.18 try3 + SCP critical gates v2",
              "reference": "20261112-a733-fwclk-v2@gmail.com",
              "test": "NOT RUN ON HARDWARE"}
    def save():
        (dst / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    save()
    try:
        ccudata = mainccu.read_text()
        if "sun60i-a733" not in mainccu.name:
            raise ValueError("Unexpected main CCU")
        gates = {}
        for symbol in CRITICAL_MAIN:
            declaration = gate(ccudata, symbol)
            gates[symbol] = "CLK_IS_CRITICAL" in declaration
        result["main_ccu_gates"] = gates
        save()
        if not all(gates.values()):
            raise RuntimeError("One or more v7 main CCU critical gates absent; source audit required")
        prcmdata = prcm.read_text()
        plan = {}
        for symbol, clock_name in SCP.items():
            declaration = gate(prcmdata, symbol)
            if f'"{clock_name}"' not in declaration:
                raise ValueError(f"Unexpected clock name in {symbol}")
            plan[symbol] = "ALREADY_CRITICAL" if "CLK_IS_CRITICAL" in declaration else "NEEDS_CRITICAL"
        result["scp_preflight"] = plan
        save()
        staged = dst / "linux"
        call("cp", "-a", "--reflink=auto", src, staged)
        updated = (staged / "drivers/clk/sunxi-ng/ccu-sun60i-a733-r.c").read_text()
        for symbol in SCP:
            updated, state = mark_gate(updated, symbol)
            result.setdefault("scp_changes", {})[symbol] = state
        patched = staged / "drivers/clk/sunxi-ng/ccu-sun60i-a733-r.c"
        patched.write_text(updated)
        for symbol in SCP:
            if "CLK_IS_CRITICAL" not in gate(updated, symbol):
                raise RuntimeError(f"Missing final critical flag for {symbol}")
        if checksum(uart) != checksum(staged / "drivers/tty/serial/8250/8250_dw.c"):
            raise RuntimeError("UART source changed unexpectedly")
        result["state"] = "SCP_PROTECTIONS_PRESENT_BUILD_PENDING"
        result["prcm_sha256"] = checksum(patched)
        save()
        obj = dst / "obj"
        obj.mkdir()
        shutil.copy2(args.config.resolve(), obj / ".config")
        config = (obj / ".config").read_text()
        for required in ("CONFIG_ARM64=y", "CONFIG_COMMON_CLK=y", "CONFIG_SERIAL_8250_DW=y"):
            if required not in config:
                raise RuntimeError(f"Missing config {required}")
        call("make", "-C", staged, f"O={obj}", "ARCH=arm64",
             "CROSS_COMPILE=aarch64-linux-gnu-", "olddefconfig")
        call("make", "-C", staged, f"O={obj}", "ARCH=arm64",
             "CROSS_COMPILE=aarch64-linux-gnu-", f"-j{args.jobs}", "Image")
        binary = obj / "arch/arm64/boot/Image"
        result.update(state="IMAGE_BUILT_NOT_BOOTED", image=str(binary),
                      image_sha256=checksum(binary), image_bytes=binary.stat().st_size)
        save()
        print("RESULT:", result["state"])
        print("IMAGE:", binary)
    except Exception as e:
        result["state"] = "FAILED"
        result["error"] = str(e)
        save()
        raise
if __name__ == "__main__":
    main()
