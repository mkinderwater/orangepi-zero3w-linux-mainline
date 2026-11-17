#!/usr/bin/env python3
"""Stage upstream A733 UART v2 fixes in an independent Linux tree.

Never edits --source or an image. Requires b4 and git. An apply conflict is
reported, not "fixed" using fuzzy patching. Target is the fully prepared
Linux 6.18 source that produced the 4,562,952-byte RAM-A Image.
"""
import argparse
import hashlib
import json
import mailbox
import re
import shutil
import subprocess
from pathlib import Path

MID = "cover.1792439398.git.vinicius.eduardo.pedrosa@gmail.com"
EXPECTED = [
    "Keep the BUSY-safe divisor hook when DLF is present",
    "Only accept a contiguous DLF readback",
    "Add Allwinner A733",
    "Add Allwinner A733 UART",
]
EXPECTED_FILES = {
    "drivers/tty/serial/8250/8250_dw.c",
    "drivers/tty/serial/8250/8250_dwlib.c",
    "Documentation/devicetree/bindings/serial/snps-dw-apb-uart.yaml",
}
def cmd(*args, cwd=None, check=True):
    args = [str(a) for a in args]
    print("+", " ".join(args), flush=True)
    r = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and r.returncode:
        raise RuntimeError(f"Command failed ({r.returncode}): {' '.join(args)}\n{r.stdout}\n{r.stderr}")
    return r

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1048576), b""):
            h.update(buf)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True,
                   help="Already-patched A733 6.18 kernel source used for RAM-A")
    p.add_argument("--output", type=Path, required=True, help="New output directory")
    p.add_argument("--config", type=Path, help="Existing proven RAM-A kernel .config")
    p.add_argument("--build", action="store_true",
                   help="Use provided .config to build Image in output/obj")
    p.add_argument("--jobs", type=int, default=4)
    a = p.parse_args()
    source = a.source.resolve()
    output = a.output.resolve()
    if a.build and not a.config:
        p.error("--build requires --config")
    if a.jobs < 1 or a.jobs > 64:
        p.error("--jobs must be between 1 and 64")
    if output.exists() or output == source or output in source.parents:
        p.error("Output exists or overlaps source")
    if not (source / "Makefile").is_file() or not (source / "drivers/tty/serial/8250/8250_dw.c").is_file():
        p.error("Not a Linux source tree")
    for tool in ("b4", "git", "cp"):
        if not shutil.which(tool):
            p.error(f"{tool} missing")
    output.mkdir(parents=True)
    report = {"status": "INIT", "source": str(source), "message_id": MID,
              "patches_expected": 4, "hardware_result": "NOT TESTED",
              "uart0": "ENABLED", "ram_a": "DO NOT CHANGE"}
    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    try:
        fetch = cmd("b4", "am", "--no-parent", "-o", output, MID, check=False)
        (output / "b4.stdout").write_text(fetch.stdout)
        (output / "b4.stderr").write_text(fetch.stderr)
        if fetch.returncode:
            raise RuntimeError("b4 fetch failed: " + fetch.stderr)
        files = list(output.glob("*.mbx"))
        if len(files) != 1:
            raise RuntimeError(f"Expected one mailbox, found {len(files)}")
        messages = list(mailbox.mbox(str(files[0])))
        if len(messages) != 4:
            raise RuntimeError(f"Expected four v2 patches, got {len(messages)}")
        patches = []
        for i, (msg, part) in enumerate(zip(messages, EXPECTED), 1):
            subject = str(msg.get("Subject", ""))
            if f"v2 {i}/4" not in subject or part not in subject:
                raise RuntimeError(f"Unexpected patch {i} subject: {subject}")
            body = msg.get_payload(decode=True).decode("utf-8", "replace")
            paths = re.findall(r"^diff --git a/(\S+) b/(\S+)$", body, re.M)
            if not paths or any(x != y or x not in EXPECTED_FILES for x, y in paths):
                raise RuntimeError(f"Unexpected paths in patch {i}: {paths}")
            patch = output / f"uart-v2-{i:02}.patch"
            patch.write_text(body)
            patches.append(patch)
        report["patch_sha256"] = {q.name: sha(q) for q in patches}
        report["status"] = "PATCHES_VALIDATED"
        save()
        staged = output / "linux"
        cmd("cp", "-a", "--reflink=auto", source, staged)
        for patch in patches:
            test = cmd("git", "apply", "--check", patch, cwd=staged, check=False)
            if test.returncode:
                raise RuntimeError(f"Patch check failed for {patch.name}; no fuzzy edits:\n{test.stderr}")
            cmd("git", "apply", patch, cwd=staged)
        source_text = (staged / "drivers/tty/serial/8250/8250_dw.c").read_text()
        if '"allwinner,sun60i-a733-uart", .data = &dw8250_skip_set_rate_data' not in source_text:
            raise RuntimeError("A733 SKIP_SET_RATE match missing after apply")
        report["status"] = "PATCHES_APPLIED_UNBUILT"
        report["prepared_source"] = str(staged)
        save()
        if a.build:
            for tool in ("make", "aarch64-linux-gnu-gcc"):
                if not shutil.which(tool):
                    raise RuntimeError(f"{tool} missing")
            obj = output / "obj"
            obj.mkdir()
            shutil.copy2(a.config.resolve(), obj / ".config")
            cfg = (obj / ".config").read_text()
            for required in ("CONFIG_SERIAL_8250_DW=y", "CONFIG_SERIAL_8250=y", "CONFIG_ARM64=y"):
                if required not in cfg:
                    raise RuntimeError(f"Proven .config must include {required}")
            cmd("make", "-C", staged, "O=" + str(obj), "ARCH=arm64",
                "CROSS_COMPILE=aarch64-linux-gnu-", "olddefconfig")
            cmd("make", "-C", staged, "O=" + str(obj), "ARCH=arm64",
                "CROSS_COMPILE=aarch64-linux-gnu-", "-j" + str(a.jobs), "Image")
            kernel = obj / "arch/arm64/boot/Image"
            report["image"] = str(kernel)
            report["image_sha256"] = sha(kernel)
            report["image_bytes"] = kernel.stat().st_size
            report["status"] = "IMAGE_BUILT_NOT_HARDWARE_TESTED"
            save()
        print("RESULT:", report["status"])
        print("See", output / "report.json")
    except Exception as e:
        report["status"] = "FAILED"
        report["error"] = str(e)
        save()
        raise

if __name__ == "__main__":
    main()
