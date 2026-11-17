#!/usr/bin/env python3
"""Try8A: preserve firmware UART0 settings during initial native console setup.

Diagnostic only. Patches ONLY serial_core.c uart_set_options(), restricting
bypass to co != NULL, A733 UART0 physical address, and a real console object.
All non-console termios operations keep their original code path.
Produces a kernel Image in a NEW source/output tree; does not touch SD media.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

UART0 = 0x02500000

def cmd(*args):
    argv = [str(x) for x in args]
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, check=True)

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True,
                    help="Proven 6.18 try5b Linux source with RAM-A UART support")
    ap.add_argument("--config", type=Path, required=True, help="Source kernel .config")
    ap.add_argument("--output", type=Path, required=True, help="NEW directory")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    src, output = a.source.resolve(), a.output.resolve()
    original = src / "drivers/tty/serial/serial_core.c"
    uart = src / "drivers/tty/serial/8250/8250_dw.c"
    if output.exists() or output == src or output in src.parents:
        ap.error("Output already exists or overlaps source")
    if not original.is_file() or not uart.is_file() or not a.config.is_file():
        ap.error("Missing Linux source, UART driver or kernel config")
    if not 1 <= a.jobs <= 64:
        ap.error("Jobs outside 1-64")
    for program in ("cp", "make", "aarch64-linux-gnu-gcc"):
        if not shutil.which(program):
            ap.error("Missing " + program)
    text = original.read_text()
    start = re.search(
        r"\buart_set_options\s*\(\s*struct uart_port\s*\*port\s*,\s*"
        r"struct console\s*\*co\s*,\s*int baud\s*,\s*int parity\s*,"
        r"\s*int bits\s*,\s*int flow\s*\)\s*\{", text)
    if start is None:
        ap.error("Unexpected serial_core.c uart_set_options() signature")
    end = text.find("EXPORT_SYMBOL_GPL(uart_set_options);", start.end())
    if end < 0:
        ap.error("Cannot find uart_set_options() export")
    function = text[start.start():end]
    anchor = "port->ops->set_termios(port, &termios, &dummy);"
    if function.count(anchor) != 1:
        ap.error("Expected exactly one initial console set_termios call")
    if "A733CONSOLEBYPASS" in text:
        ap.error("Diagnostic is already applied")
    # No kernel message from within console setup to avoid printk recursion.
    bypass = r"""/*
         * A733CONSOLEBYPASS: diagnostic only.
         *
         * The firmware already configured UART0 at 115200 8N1.
         * Avoid reprogramming it from uart_set_options() during the
         * first native console setup, but leave all other ports and
         * all ordinary non-console termios operations untouched.
         *
         * This is not a production driver fix: software baud state
         * may diverge from the preserved hardware state.
         */
        if (!(co && port->mapbase == 0x02500000))
                port->ops->set_termios(port, &termios, &dummy);"""
    edited = function.replace(anchor, bypass, 1)
    result = text[:start.start()] + edited + text[end:]
    if result.count("A733CONSOLEBYPASS") != 1:
        ap.error("Diagnostic marker count mismatch")
    output.mkdir(parents=True)
    report = {
        "state": "SOURCE_VALIDATED", "source": str(src),
        "test": "Try8A preserve firmware UART on native console setup",
        "diagnostic_only": True, "hardware_test": "NOT RUN",
        "extra_register_writes": False,
        "bypass_scope": "co != NULL and port->mapbase == 0x02500000",
        "source_core_sha256": digest(original)
    }
    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    try:
        tree = output / "linux"
        cmd("cp", "-a", "--reflink=auto", src, tree)
        target = tree / "drivers/tty/serial/serial_core.c"
        target.write_text(result)
        if digest(tree / "drivers/tty/serial/8250/8250_dw.c") != digest(uart):
            raise RuntimeError("UART DesignWare driver changed unexpectedly")
        report.update(state="SOURCE_PATCHED", patched_core_sha256=digest(target))
        save()
        obj = output / "obj"
        obj.mkdir()
        shutil.copy2(a.config.resolve(), obj / ".config")
        config = (obj / ".config").read_text()
        for required in ("CONFIG_ARM64=y", "CONFIG_SERIAL_8250=y", "CONFIG_SERIAL_8250_DW=y"):
            if required not in config:
                raise RuntimeError("Kernel .config missing " + required)
        cmd("make", "-C", tree, "O=" + str(obj), "ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-", "olddefconfig")
        cmd("make", "-C", tree, "O=" + str(obj), "ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-", "-j" + str(a.jobs), "Image")
        image = obj / "arch/arm64/boot/Image"
        report.update(state="IMAGE_BUILT_UNBOOTED", image=str(image),
                      image_size=image.stat().st_size, image_sha256=digest(image))
        save()
        print("RESULT:", report["state"])
        print("IMAGE:", image)
        print("SHA256:", report["image_sha256"])
    except Exception as exc:
        report["state"] = "FAILED"
        report["error"] = str(exc)
        save()
        raise

if __name__ == "__main__":
    main()
