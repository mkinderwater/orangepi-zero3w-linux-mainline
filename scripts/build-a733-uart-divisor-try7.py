#!/usr/bin/env python3
"""Build A733 UART try7: observe exact divisor chosen by Linux 8250 termios.

Does not write UART/clock registers beyond the unmodified driver's behavior.
Inserts one read-only printk before the driver's own port lock and writes.
Selected divisor is NOT proof of a successful hardware write.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

def run(*args):
    args = [str(x) for x in args]
    print("+", " ".join(args), flush=True)
    subprocess.run(args, check=True)

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True,
                   help="Built try5b Linux tree; includes current A733 UART quirk")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=4)
    a = p.parse_args()
    src, out = a.source.resolve(), a.output.resolve()
    core = src / "drivers/tty/serial/8250/8250_port.c"
    if out.exists() or out == src or out in src.parents:
        p.error("Output must not exist or overlap input")
    if not core.is_file() or not a.config.is_file():
        p.error("Missing Linux source or kernel configuration")
    if a.jobs not in range(1, 65):
        p.error("jobs must be 1-64")
    for program in ("cp", "make", "aarch64-linux-gnu-gcc"):
        if not shutil.which(program):
            p.error(f"Missing {program}")
    out.mkdir(parents=True)
    report = {
        "status": "CREATED", "input_source": str(src),
        "instrument": "serial8250_do_set_termios computed baud/quot/frac, before port lock",
        "writes_added": False, "boot_result": "NOT TESTED",
    }
    def save():
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    try:
        tree = out / "linux"
        run("cp", "-a", "--reflink=auto", src, tree)
        target = tree / "drivers/tty/serial/8250/8250_port.c"
        source = target.read_text()
        if "A733DIVDIAG" in source:
            raise ValueError("Source already instrumented")
        # Linux 6.18 uses "const struct ktermios *old", and separates
        # the return type "void" and function name across two lines.
        impl = re.search(
            r"(?m)^void\s+serial8250_do_set_termios\s*\(\s*"
            r"struct uart_port\s*\*port,\s*struct ktermios\s*\*termios,\s*"
            r"(?:const\s+)?struct ktermios\s*\*old\s*\)\s*\{",
            source,
        )
        if impl is None:
            raise ValueError("Expected Linux 6.18 termios function not found")
        exports = list(re.finditer(
            r"(?m)^EXPORT_SYMBOL(?:_GPL)?\(serial8250_do_set_termios\);",
            source[impl.end():],
        ))
        if len(exports) != 1:
            raise ValueError(f"Expected one termios export, got {len(exports)}")
        next_func = impl.end() + exports[0].start()
        section = source[impl.end():next_func]
        # Older kernels call this 'cval'; newer ones may call it 'lcr'.
        # Confirm a local declaration to avoid emitting invalid C.
        if re.search(r"\b(?:unsigned char|u8)\s+cval\s*;", section):
            lcr_variable = "cval"
        elif re.search(r"\b(?:unsigned char|u8)\s+lcr\s*;", section):
            lcr_variable = "lcr"
        else:
            raise ValueError("Cannot find local LCR variable")
        # The core chooses divisor before it disables interrupts and takes lock.
        pattern = re.compile(
            r"(?m)^(?P<indent>[ \t]*)baud\s*=\s*serial8250_get_baud_rate"
            r"\(port,\s*termios,\s*old\);\s*\n"
            r"[ \t]*quot\s*=\s*serial8250_get_divisor"
            r"\(port,\s*baud,\s*&frac\);"
        )
        matches = list(pattern.finditer(section))
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one divisor selection, found {len(matches)}")
        match = matches[0]
        insert = r'''

        /*
         * A733-only: record the divisor the core actually SELECTS before
         * any UART register write or port spinlock.
         * This is not a readback or proof the hardware accepted the write.
         */
        if (port->mapbase == 0x02500000)
                pr_emerg("A733DIVDIAG requested_baud=%u uartclk=%u quot=%u frac=%u lcr_selected=0x%x actual_integer_model_baud=%llu\n",
                         baud, port->uartclk, quot, frac, cval,
                         quot ? (unsigned long long)port->uartclk / (16ULL * quot) : 0ULL);
'''
        insert = insert.replace("baud, port->uartclk, quot, frac, cval,",
                                f"baud, port->uartclk, quot, frac, {lcr_variable},")
        section = section[:match.end()] + insert + section[match.end():]
        source = source[:impl.end()] + section + source[next_func:]
        if source.count("A733DIVDIAG") != 1:
            raise RuntimeError("Unexpected diagnostic count")
        target.write_text(source)
        report.update(status="SOURCE_INSTRUMENTED", source_sha256=digest(target))
        save()
        obj = out / "obj"
        obj.mkdir()
        shutil.copy2(a.config.resolve(), obj / ".config")
        cfg = (obj / ".config").read_text()
        for expected in ("CONFIG_ARM64=y", "CONFIG_SERIAL_8250=y",
                         "CONFIG_SERIAL_8250_DW=y"):
            if expected not in cfg:
                raise ValueError("Proven kernel config lacks " + expected)
        run("make", "-C", tree, "O=" + str(obj), "ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-", "olddefconfig")
        run("make", "-C", tree, "O=" + str(obj), "ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-", "-j" + str(a.jobs), "Image")
        image = obj / "arch/arm64/boot/Image"
        report.update(status="IMAGE_BUILT_UNBOOTED", image=str(image),
                      image_bytes=image.stat().st_size, image_sha256=digest(image))
        save()
        print("RESULT:", report["status"])
        print("IMAGE:", image)
        print("SHA256:", report["image_sha256"])
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = str(exc)
        save()
        raise

if __name__ == "__main__":
    main()
