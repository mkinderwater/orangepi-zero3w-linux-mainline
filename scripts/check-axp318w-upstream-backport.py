#!/usr/bin/env python3
"""Check AXP318W v8 patch applicability in a temporary, minimal source copy.

No original kernel source, PMIC registers, DTB, boot image or media changes.
"""
import argparse
import hashlib
import json
import mailbox
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

DIFF = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.M)
EXPECTED = [f"[PATCH v8 {i}/5]" for i in range(1, 6)]

def run(*command, cwd=None):
    p = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)[-8000:]

def extract(archive, path):
    with tarfile.open(archive, "r:gz") as tar:
        candidates = [m for m in tar if m.isfile() and m.name.endswith(".mbx")]
        if len(candidates) != 1 or candidates[0].size > 2_000_000:
            raise ValueError("Expected one bounded AXP318W mailbox")
        with tar.extractfile(candidates[0]) as source:
            path.write_bytes(source.read())

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error("Refusing to overwrite existing output directory")
    if not (a.source / "Makefile").is_file():
        p.error("Missing Linux source")
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        box = temp / "axp318w.mbx"
        extract(a.archive, box)
        messages = list(mailbox.mbox(str(box)))
        if len(messages) != 5:
            p.error("Expected exactly five patch messages, got " + str(len(messages)))
        patches = []
        for index, message in enumerate(messages):
            subject = str(message.get("Subject", ""))
            if EXPECTED[index] not in subject:
                p.error("Unexpected patch order: " + subject)
            body = message.get_payload(decode=True)
            if not isinstance(body, bytes):
                p.error("Unparseable patch: " + subject)
            text = body.decode("utf-8", "replace")
            files = []
            for left, right in DIFF.findall(text):
                if left != right or left.startswith("/") or ".." in Path(left).parts:
                    p.error("Unsafe or renamed patch path")
                files.append(left)
            if not files:
                p.error("Patch has no diff: " + subject)
            patches.append((subject, text, files))
        work = temp / "work"
        work.mkdir()
        touched = sorted(set(x for _, _, files in patches for x in files))
        for name in touched:
            source = a.source / name
            if not source.is_file():
                p.error("Missing 6.18 source: " + name)
            target = work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        a.output.mkdir(parents=True)
        report = {"status": "SOURCE_APPLICABILITY_ONLY", "source": str(a.source),
                  "archive_sha256": hashlib.sha256(a.archive.read_bytes()).hexdigest(),
                  "patches": [], "forbidden_actions": "No PMIC write or voltage test"}
        for index, (subject, body, files) in enumerate(patches, 1):
            dest = a.output / f"axp318w-v8-{index:02d}.patch"
            dest.write_text(body)
            rc, output = run("git", "apply", "--check", str(dest), cwd=work)
            item = {"index": index, "subject": subject, "files": files,
                    "check": rc == 0, "diagnostic": output}
            if rc == 0:
                rc, output = run("git", "apply", str(dest), cwd=work)
                item["scratch_applied"] = rc == 0
                item["diagnostic"] += output
            report["patches"].append(item)
            if not item["check"] or not item.get("scratch_applied"):
                report["status"] = "CONFLICT"
                break
        (a.output / "review.json").write_text(json.dumps(report, indent=2) + "\n")
        print("AXP318W:", report["status"])
        for item in report["patches"]:
            print(f"{item['index']}/5 {item['subject']}:",
                  "PASS" if item["check"] and item.get("scratch_applied") else "CONFLICT")
            if item["diagnostic"]:
                print(item["diagnostic"])
        print("No original Linux source modified. No boot or electrical validation.")

if __name__ == "__main__":
    main()
