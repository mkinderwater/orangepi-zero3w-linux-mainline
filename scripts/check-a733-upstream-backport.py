#!/usr/bin/env python3
"""Dry-run acquired A733 mail patches against a pinned upstream tree.

Copy *only touched files* to an isolated directory; never alter Linux sources.
Examine generated review.json before any real build.
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

GROUPS = ("ccu-v7", "pinctrl-base", "pinctrl-pf6", "pinctrl-voltage-v3")
EXPECTED = {"ccu-v7": 8, "pinctrl-base": 7,
            "pinctrl-pf6": 1, "pinctrl-voltage-v3": 1}
DIFF = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.M)

def command(*args, cwd=None):
    p = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    return p.returncode, (p.stdout + p.stderr)[-5000:]

def extract_mailboxes(archive, dest):
    found = {}
    with tarfile.open(archive, "r:gz") as f:
        for m in f:
            if not m.isfile() or not m.name.endswith(".mbx"):
                continue
            group = next((x for x in GROUPS if
                          "/" + x + "/" in "/" + m.name), None)
            if group is None or group in found or m.size > 5_000_000:
                raise ValueError("unexpected, duplicate or oversized mailbox")
            path = dest / (group + ".mbx")
            with f.extractfile(m) as source, path.open("wb") as target:
                shutil.copyfileobj(source, target)
            found[group] = path
    if set(found) != set(GROUPS):
        raise ValueError("missing series: " + str(set(GROUPS) - set(found)))
    return found

def patches(path):
    out = []
    for message in mailbox.mbox(str(path)):
        body = message.get_payload(decode=True)
        if not isinstance(body, bytes):
            raise ValueError("multipart or unparseable mailbox")
        text = body.decode("utf-8", "replace")
        if "diff --git a/" not in text:
            raise ValueError("message without patch content")
        files = []
        for left, right in DIFF.findall(text):
            for item in (left, right):
                itempath = Path(item)
                if itempath.is_absolute() or ".." in itempath.parts:
                    raise ValueError("unsafe patch path")
            if left != right:
                raise ValueError("rename patches unsupported")
            files.append(left)
        out.append({"subject": " ".join(message.get("Subject", "").split()),
                    "mid": message.get("Message-ID", ""),
                    "body": text, "files": files})
    return out

def validate_group(name, parsed, source, work, out):
    results = []
    for i, patch in enumerate(parsed, 1):
        file = out / (name + "-%02d.patch" % i)
        file.write_text(patch["body"])
        rc, msg = command("git", "apply", "--check", str(file), cwd=work)
        record = {"order": i, "subject": patch["subject"], "message_id": patch["mid"],
                  "paths": patch["files"], "check": rc == 0, "diagnostic": msg}
        results.append(record)
        if rc != 0:
            break
        rc2, msg2 = command("git", "apply", str(file), cwd=work)
        record["scratch_apply"] = rc2 == 0
        if rc2 != 0:
            record["diagnostic"] += "\n" + msg2
            break
    return results

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        p.error("Refusing to overwrite output directory")
    if not (args.source / "Makefile").is_file():
        p.error("Not a Linux source tree")
    if args.source.resolve() == args.output.resolve():
        p.error("Source and output must differ")
    with tempfile.TemporaryDirectory() as scratch:
        t = Path(scratch)
        found = extract_mailboxes(args.archive, t)
        groups = {name: patches(found[name]) for name in GROUPS}
        for name in GROUPS:
            if len(groups[name]) != EXPECTED[name]:
                p.error("Unexpected patch count for " + name)
        args.output.mkdir(parents=True)
        report = {"source": str(args.source.resolve()),
                  "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
                  "groups": {}, "notice": "STATIC ONLY: no build, hardware or voltage tests"}
        # All patch groups share a base tree only within pinctrl branch.
        for stage in ("ccu-v7", "pinctrl"):
            names = ("ccu-v7",) if stage == "ccu-v7" else (
                "pinctrl-base", "pinctrl-pf6", "pinctrl-voltage-v3")
            work = t / (stage + "-scratch")
            work.mkdir()
            paths = set()
            for name in names:
                for patch in groups[name]:
                    paths.update(patch["files"])
            for rel in sorted(paths):
                original = args.source / rel
                if original.is_file():
                    target = work / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, target)
            blocked = False
            for name in names:
                if blocked:
                    report["groups"][name] = {"status": "BLOCKED_BY_PRIOR_SERIES"}
                    continue
                entries = validate_group(name, groups[name], args.source, work, args.output)
                success = len(entries) == EXPECTED[name] and all(
                    e["check"] and e.get("scratch_apply") for e in entries)
                report["groups"][name] = {
                    "expected": EXPECTED[name],
                    "passed": len(entries) if success else sum(
                        1 for e in entries if e["check"] and e.get("scratch_apply")),
                    "status": "PASS_SOURCE_APPLICABILITY_ONLY" if success else "CONFLICT",
                    "patches": entries}
                if not success:
                    blocked = True
        (args.output / "review.json").write_text(json.dumps(report, indent=2) + "\n")
        lines = ["# A733 upstream source-only backport checks", "",
                 "No original Linux source modified. No builds or electrical validation.", ""]
        for name in GROUPS:
            value = report["groups"][name]
            lines.append("## " + name + ": " + value["status"])
            for entry in value.get("patches", []):
                lines.append("- " + entry["subject"] + ": " +
                             ("PASS" if entry["check"] and entry.get("scratch_apply") else "CONFLICT"))
                if entry["diagnostic"]:
                    lines.append("  " + entry["diagnostic"].replace("\n", " ").strip())
            lines.append("")
        (args.output / "review.md").write_text("\n".join(lines))
        print("\n".join(lines))
    # Deliberately return success when review is complete even if conflicts exist.
    # The JSON/MD status is the authoritative backport result.
if __name__ == "__main__":
    main()
