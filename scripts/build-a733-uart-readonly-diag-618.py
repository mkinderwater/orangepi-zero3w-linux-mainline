#!/usr/bin/env python3
"""Build an A733 UART non-invasive probe diagnostic from the try4 source tree.

Records clock rates and UART control registers BEFORE native console takeover.
Does not touch divisor latches: changing DLAB would alter the running console.
Does not modify source, known-good image, firmware or DTB.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

def cmd(*args):
    vals = [str(x) for x in args]
    print("+", " ".join(vals), flush=True)
    subprocess.run(vals, check=True)

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()

def once(text, before, after):
    n = text.count(before)
    if n != 1:
        raise RuntimeError(f"Expected exactly one anchor ({n}): {before[:90]!r}")
    return text.replace(before, after, 1)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, type=Path, help="Try4 kernel source tree")
    ap.add_argument("--config", required=True, type=Path, help="Try4 kernel .config")
    ap.add_argument("--output", required=True, type=Path, help="New output directory")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    src, out = a.source.resolve(), a.output.resolve()
    kernel_file = src / "drivers/tty/serial/8250/8250_dw.c"
    if out.exists() or out == src or out in src.parents:
        ap.error("Output exists or overlaps source")
    if not kernel_file.is_file() or not a.config.is_file():
        ap.error("Missing try4 Linux source or .config")
    if not (1 <= a.jobs <= 64):
        ap.error("--jobs must be 1..64")
    for t in ("cp", "make", "aarch64-linux-gnu-gcc"):
        if shutil.which(t) is None:
            ap.error(f"Missing {t}")
    out.mkdir(parents=True)
    report = {"state":"INIT", "baseline":"try4", "source":str(src),
              "no_write_registers":True, "hardware_test":"NOT TESTED"}
    def save():
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    try:
        tree = out / "linux"
        cmd("cp", "-a", "--reflink=auto", src, tree)
        target = tree / "drivers/tty/serial/8250/8250_dw.c"
        s = target.read_text()
        # Enable only when exact existing source structure is present.
        anchor = "static int dw8250_probe(struct platform_device *pdev)\n{"
        addition = r'''
/*
 * Zero 3W UART0 diagnostic. Read-only, limited to physical UART0.
 * Never toggle LCR.DLAB or read divisor latches here.
 */
static void a733_uart_snapshot(struct uart_port *p, struct clk *clk,
                               const char *phase)
{
        struct clk *parent;
        const char *parent_name = "(none)";
        unsigned long parent_rate = 0;
        unsigned long rate = 0;
        u32 lcr, ier, lsr, mcr, usr;

        if (p->mapbase != 0x02500000 || !p->membase)
                return;
        if (p->iotype != UPIO_MEM32 || p->regshift != 2) {
                pr_emerg("A733UARTDIAG %s: unexpected iotype=%u shift=%u\n",
                         phase, p->iotype, p->regshift);
                return;
        }
        if (clk) {
                rate = clk_get_rate(clk);
                parent = clk_get_parent(clk);
                if (parent) {
                        parent_rate = clk_get_rate(parent);
                        parent_name = __clk_get_name(parent);
                }
        }
        lcr = readl(p->membase + (UART_LCR << 2));
        /* IER offset aliases DLH if DLAB=1: do not read it then. */
        ier = (lcr & UART_LCR_DLAB) ? 0xffffffff :
              readl(p->membase + (UART_IER << 2));
        lsr = readl(p->membase + (UART_LSR << 2));
        mcr = readl(p->membase + (UART_MCR << 2));
        usr = readl(p->membase + 0x7c);
        pr_emerg("A733UARTDIAG %s: clk=%lu parent=%s parent_rate=%lu uartclk=%u type=%u shift=%u LCR=%02x IER=%02x%s LSR=%02x MCR=%02x USR=%02x\n",
                 phase, rate, parent_name, parent_rate, p->uartclk,
                 p->iotype, p->regshift, lcr, ier,
                 (lcr & UART_LCR_DLAB) ? "(DLAB,IER skipped)" : "",
                 lsr, mcr, usr);
}

'''
        s = once(s, anchor, addition + anchor)
        # Source formatting varies between 6.18 trees; match complete
        # statements rather than relying on spaces vs tabs.
        def insert_after_stmt(source, pattern, snippet, label):
            matches = list(re.finditer(pattern, source, re.M))
            if len(matches) != 1:
                raise RuntimeError(f"{label}: expected exactly one semantic anchor, found {len(matches)}")
            pos = matches[0].end()
            return source[:pos] + "\n" + snippet + source[pos:]

        s = insert_after_stmt(
            s,
            r'^\s*if\s*\(!p->uartclk\)\s*\n\s*return\s+dev_err_probe\(\s*dev\s*,\s*-EINVAL\s*,\s*"clock rate not defined\\n"\s*\);',
            '        a733_uart_snapshot(p, data->clk, "pre-reset");',
            "pre-reset")
        s = insert_after_stmt(
            s,
            r'^\s*if\s*\(!data->skip_autocfg\)\s*\n\s*dw8250_setup_port\(p\);',
            '        a733_uart_snapshot(p, data->clk, "post-setup");',
            "post-setup")
        s = insert_after_stmt(
            s,
            r'^\s*data->data\.line\s*=\s*serial8250_register_8250_port\(up\);',
            '        a733_uart_snapshot(p, data->clk, "pre-register");',
            "pre-register")
        # Do not snapshot after register: serial8250_register can trigger
        # native console switch before it returns.
        target.write_text(s)
        if s.count("A733UARTDIAG") != 2 or s.count("a733_uart_snapshot(p, data->clk") != 3:
            raise RuntimeError("Incorrect instrumentation count")
        report["source_sha256"] = sha(target)
        report["state"] = "INSTRUMENTED_UNBUILT"
        save()
        obj = out / "obj"
        obj.mkdir()
        shutil.copy2(a.config.resolve(), obj / ".config")
        config = (obj / ".config").read_text()
        for flag in ("CONFIG_ARM64=y", "CONFIG_SERIAL_8250=y", "CONFIG_SERIAL_8250_DW=y"):
            if flag not in config:
                raise RuntimeError("Missing expected config: "+flag)
        cmd("make", "-C", tree, "O="+str(obj), "ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-", "olddefconfig")
        cmd("make", "-C", tree, "O="+str(obj), "ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-", "-j"+str(a.jobs), "Image")
        image = obj / "arch/arm64/boot/Image"
        report.update(state="BUILT_UNBOOTED", image=str(image),
                      image_sha256=sha(image), image_size=image.stat().st_size)
        save()
        print("RESULT:", report["state"])
        print("IMAGE:", image)
    except Exception as e:
        report["state"] = "FAILED"
        report["error"] = str(e)
        save()
        raise

if __name__ == "__main__":
    main()
