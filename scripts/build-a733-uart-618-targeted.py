#!/usr/bin/env python3
"""Backport upstream A733 UART clock and DLF guards to pinned Linux 6.18.

Source and control images are read-only. This handles the *older* 6.18 DW
driver; newer upstream patch 1's BUSY-safe divisor hook does not exist here.
Do not claim patch 1 was applied. Compile and test this independently.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

def run(*args):
    a = [str(v) for v in args]
    print("+", " ".join(a), flush=True)
    subprocess.run(a, check=True)

def hash_file(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def replace_exact(text, before, after, label):
    if text.count(before) != 1:
        raise ValueError(f"{label}: wanted exactly one source anchor, found {text.count(before)}")
    return text.replace(before, after, 1)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--jobs", type=int, default=4)
    a = p.parse_args()
    src, dest = a.source.resolve(), a.output.resolve()
    if dest.exists() or dest == src or dest in src.parents:
        p.error("Output already exists or overlaps input; no files changed")
    if not (src / "drivers/tty/serial/8250/8250_dw.c").is_file():
        p.error("Missing pinned Linux source")
    if not a.config.is_file():
        p.error("Missing proven .config")
    for binary in ("cp", "make", "aarch64-linux-gnu-gcc"):
        if not shutil.which(binary):
            p.error(f"Missing {binary}")
    if a.jobs < 1 or a.jobs > 64:
        p.error("--jobs must be 1..64")
    dest.mkdir(parents=True)
    report = {"status": "INIT", "source": str(src), "source_proven_kernel": "6.18.19+",
              "variant": "6.18-A733-SKIP_SET_RATE-and-DLF-mask",
              "upstream_series": "Vinicius Pedrosa v2 2026-10-19",
              "upstream_patch_1": "NOT APPLIED: requires newer BUSY-safe divisor architecture",
              "boot_test": "NOT TESTED"}
    def save():
        (dest / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    try:
        tree = dest / "linux"
        run("cp", "-a", "--reflink=auto", src, tree)
        driver = tree / "drivers/tty/serial/8250/8250_dw.c"
        lib = tree / "drivers/tty/serial/8250/8250_dwlib.c"
        d = driver.read_text()
        l = lib.read_text()

        # Verify existing quirk is fully implemented, do not reimplement it.
        for marker in ("DW_UART_QUIRK_SKIP_SET_RATE", "p->set_termios = dw8250_do_set_termios",
                       "dw8250_skip_set_rate_data"):
            if marker not in d:
                raise ValueError(f"Missing expected 6.18 UART facility: {marker}")
        if '"allwinner,sun60i-a733-uart"' in d:
            raise ValueError("A733 compatible already installed: refuse duplicate")
        # Insert the specific compatible before generic snps fallback.
        generic = re.compile(
            r'(?m)^(?P<indent>\s*)\{\s*\.compatible\s*=\s*"snps,dw-apb-uart"\s*,\s*'
            r'\.data\s*=\s*&dw8250_dw_apb\s*\},?\s*$'
        )
        matches = list(generic.finditer(d))
        if len(matches) != 1:
            raise ValueError(f"Generic DesignWare match anchor count {len(matches)}")
        m = matches[0]
        addition = m.group("indent") + '{ .compatible = "allwinner,sun60i-a733-uart", .data = &dw8250_skip_set_rate_data },\n'
        d = d[:m.start()] + addition + d[m.start():]

        # This older dwlib probes DLF but misreads A733 RS485_CTL 0xc0.
        # Upstream patch v2 2/4: a valid DLF mask is contiguous from bit 0.
        m = re.search(r'(?s)void dw8250_setup_port\(struct uart_port \*p\).*?'
                      r'dw8250_writel_ext\(p,\s*DW_UART_DLF,\s*old_dlf\);'
                      r'(?P<space>\s*)if\s*\(reg\)\s*\{', l)
        if not m or len(re.findall(r'void dw8250_setup_port\(struct uart_port \*p\)', l)) != 1:
            raise ValueError("Cannot locate exact DLF probe in 6.18 dw8250_setup_port")
        # This modification is global to DW DLF detection, exactly as upstream patch 2.
        before = m.group(0)
        after = before.replace("if (reg) {",
            "/* DLF must read back as a contiguous low-bit mask (2^n - 1). */\n"
            "\tif (reg && !(reg & (reg + 1))) {")
        if before == after:
            raise ValueError("DLF if(reg) replacement did not occur")
        l = l.replace(before, after, 1)
        driver.write_text(d)
        lib.write_text(l)

        # Binary/source validation before compiling.
        if d.count('"allwinner,sun60i-a733-uart"') != 1:
            raise ValueError("A733 compatible not unique")
        if "if (reg && !(reg & (reg + 1)))" not in l:
            raise ValueError("DLF guard missing")
        report["status"] = "SOURCE_PATCHED_UNBUILT"
        report["source_sha256"] = {f.name: hash_file(f) for f in (driver, lib)}
        save()
        obj = dest / "obj"
        obj.mkdir()
        shutil.copy2(a.config.resolve(), obj / ".config")
        config = (obj / ".config").read_text()
        for val in ("CONFIG_ARM64=y", "CONFIG_SERIAL_8250=y", "CONFIG_SERIAL_8250_DW=y"):
            if val not in config:
                raise ValueError(f"Proven config lacks {val}")
        run("make", "-C", tree, f"O={obj}", "ARCH=arm64", "CROSS_COMPILE=aarch64-linux-gnu-", "olddefconfig")
        run("make", "-C", tree, f"O={obj}", "ARCH=arm64", "CROSS_COMPILE=aarch64-linux-gnu-", f"-j{a.jobs}", "Image")
        kernel = obj / "arch/arm64/boot/Image"
        report.update(status="IMAGE_BUILT_UNBOOTED", kernel=str(kernel),
                      kernel_bytes=kernel.stat().st_size, kernel_sha256=hash_file(kernel))
        save()
        print("RESULT:", report["status"], "\nIMAGE:", kernel)
        print("SHA256:", report["kernel_sha256"])
    except Exception as ex:
        report["status"] = "FAILED"
        report["error"] = str(ex)
        save()
        raise

if __name__ == "__main__":
    main()
