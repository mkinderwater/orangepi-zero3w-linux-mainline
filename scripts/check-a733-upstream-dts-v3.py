#!/usr/bin/env python3
"""Review upstream A733 v3 SoC DTS patch against pinned Linux 6.18 source.

Acquisition: b4 v3 message-ID, only commit candidate DTS in a disposable tree.
No board DTS, regulator write, voltage handling or boot image.
"""
import argparse
import json
import mailbox
import re
import shutil
import subprocess
from pathlib import Path

MID = "cover.1794227241.git.enzo.adriano.code@gmail.com"

def run(*args, cwd=None, check=True):
    args = [str(x) for x in args]
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    if a.output.exists() or not (a.source / 'Makefile').is_file():
        p.error("Output exists or pinned Linux source missing")
    a.output.mkdir(parents=True)
    result = {"mid": MID, "status": "FETCHING", "boot_or_voltage_test": "NONE"}
    def save():
        (a.output / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    save()
    fetch = run("b4", "am", "--no-parent", "-o", a.output, MID, check=False)
    (a.output / "fetch.stdout").write_text(fetch.stdout)
    (a.output / "fetch.stderr").write_text(fetch.stderr)
    if fetch.returncode:
        result["status"] = "FETCH_FAILED"
        save()
        raise SystemExit(fetch.stderr)
    mbxs = list(a.output.glob("*.mbx"))
    if len(mbxs) != 1:
        result["status"] = "UNEXPECTED_MAILBOXES"
        save()
        raise SystemExit(f"Expected one mailbox, got {len(mbxs)}")
    msgs = list(mailbox.mbox(str(mbxs[0])))
    if len(msgs) != 3:
        result["status"] = "UNEXPECTED_PATCH_COUNT"
        save()
        raise SystemExit(f"Expected 3 patches, got {len(msgs)}")
    expected = ('[PATCH v3 1/3]', '[PATCH v3 2/3]', '[PATCH v3 3/3]')
    for i, (msg, prefix) in enumerate(zip(msgs, expected), 1):
        if prefix not in str(msg.get("Subject", "")):
            raise SystemExit(f"Unexpected patch {i}: {msg.get('Subject')}")
    body = msgs[1].get_payload(decode=True).decode("utf-8", "replace")
    paths = re.findall(r"^diff --git a/(\S+) b/(\S+)$", body, re.M)
    target = "arch/arm64/boot/dts/allwinner/sun60i-a733.dtsi"
    if paths != [(target, target)]:
        raise SystemExit(f"Unexpected SoC patch paths: {paths}")
    patch = a.output / "a733-soc-dts-v3-02.patch"
    patch.write_text(body)
    scratch = a.output / "linux"
    run("cp", "-a", "--reflink=auto", a.source, scratch)
    check = run("git", "-C", scratch, "apply", "--check", patch, check=False)
    result["apply_check_stdout"] = check.stdout
    result["apply_check_stderr"] = check.stderr
    if check.returncode:
        result["status"] = "APPLY_CONFLICT"
        save()
        print('DT_SOURCES_APPLY_CONFLICT: inspect report.json')
        return
    run("git", "-C", scratch, "apply", patch)
    result["status"] = "SOC_DTS_SOURCE_APPLIES_NO_DTB_BUILD"
    result["soc_dts"] = str(scratch / target)
    save()
    print('A733_V3_SOC_DTS_APPLY_PASS:', scratch / target)
    print('No board DTS, no dtc/schema validation and no hardware boot')

if __name__ == "__main__":
    main()
