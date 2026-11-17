#!/usr/bin/env python3
"""Build read-only A733 clock-register and expected-divisor diagnostic (try6).

Input: already built try5b source and .config. Use a fresh copy. Read only
the CCU APB_UART register; never toggle DLAB or write any UART register.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

def run(*args):
    cmd = [str(v) for v in args]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def replace_one(s, a, b):
    count = s.count(a)
    if count != 1:
        raise ValueError(f"Expected one anchor, got {count}: {a[:90]!r}")
    return s.replace(a, b, 1)

def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for buf in iter(lambda: f.read(1048576), b""):
            h.update(buf)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--jobs", type=int, default=4)
    args = p.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    original = source / "drivers/tty/serial/8250/8250_dw.c"
    if output.exists() or output == source or output in source.parents:
        p.error("Output already exists or overlaps source")
    if not original.is_file() or not args.config.is_file():
        p.error("Missing prepared try5b source or config")
    if not 1 <= args.jobs <= 64:
        p.error("jobs outside 1..64")
    for tool in ("cp", "make", "aarch64-linux-gnu-gcc"):
        if shutil.which(tool) is None:
            p.error(f"Missing {tool}")
    if "A733UARTDIAG pre-reset" in original.read_text():
        p.error("Unexpected pre-rendered debug code; check input source")
    if "static void a733_uart_snapshot(" not in original.read_text():
        p.error("Source is not instrumented try5b")
    output.mkdir(parents=True)
    result = {"state":"STARTED", "source":str(source), "variant":"try6 raw clock read",
              "physical_ccu_addr":"0x02002538", "writes_to_uart":False,
              "divisor":"CALCULATED ONLY, never read or written", "hardware":"NOT TESTED"}
    def save():
        (output/"report.json").write_text(json.dumps(result, indent=2)+"\n")
    save()
    try:
        targettree = output/"linux"
        run("cp", "-a", "--reflink=auto", source, targettree)
        target = targettree/"drivers/tty/serial/8250/8250_dw.c"
        s=target.read_text()
        if "#include <linux/io.h>" not in s:
            s=replace_one(s,"#include <linux/clk.h>","#include <linux/clk.h>\n#include <linux/io.h>")
        anchor='''        pr_emerg("A733UARTDIAG %s: clk=%lu parent=%s parent_rate=%lu uartclk=%u type=%u shift=%u LCR=%02x IER=%02x%s LSR=%02x MCR=%02x USR=%02x\\n",'''
        # Inject after the existing full log's terminating argument line.
        needle='''                 lsr, mcr, usr);
}'''
        new=r'''                 lsr, mcr, usr);

        /*
         * CCU 0x02002538: hardware APB_UART mux/divider.
         * Read raw value only. Do not interpret mux bits blindly.
         */
        {
                void __iomem *reg = ioremap(0x02002538, sizeof(u32));
                unsigned long rate_hz = p->uartclk;
                unsigned int divisor = DIV_ROUND_CLOSEST_ULL(rate_hz, 16ULL * 115200);
                unsigned long modeled_baud = divisor ? rate_hz / (16UL * divisor) : 0;

                if (reg) {
                        u32 value = readl(reg);
                        pr_emerg("A733UARTDIAG %s: APB_UART_RAW=0x%08x model_divisor=%u model_baud=%lu (clock=%lu, not measured divisor)\n",
                                 phase, value, divisor, modeled_baud, rate_hz);
                        iounmap(reg);
                } else {
                        pr_emerg("A733UARTDIAG %s: APB_UART register mapping FAILED\n", phase);
                }
        }
}'''
        s = replace_one(s,needle,new)
        if s.count("APB_UART_RAW") != 1 or s.count("ioremap(0x02002538") != 1:
            raise ValueError("Instrumentation check failed")
        target.write_text(s)
        result["state"] = "SOURCES_READY"
        result["driver_sha256"] = digest(target)
        save()
        obj=output/"obj"
        obj.mkdir()
        shutil.copy2(args.config.resolve(),obj/".config")
        cfg=(obj/".config").read_text()
        for entry in ("CONFIG_ARM64=y","CONFIG_SERIAL_8250_DW=y"):
            if entry not in cfg: raise ValueError("Config lacks "+entry)
        run("make","-C",targettree,"O="+str(obj),"ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-","olddefconfig")
        run("make","-C",targettree,"O="+str(obj),"ARCH=arm64",
            "CROSS_COMPILE=aarch64-linux-gnu-","-j"+str(args.jobs),"Image")
        image=obj/"arch/arm64/boot/Image"
        result.update(state="IMAGE_BUILT_NOT_BOOTED",image=str(image),sha256=digest(image),size=image.stat().st_size)
        save()
        print("RESULT:",result["state"])
        print("IMAGE:",image)
    except Exception as e:
        result["state"]="FAILED"
        result["error"]=str(e)
        save()
        raise

if __name__=="__main__":
    main()
