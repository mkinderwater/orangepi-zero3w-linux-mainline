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

GROUPS = ("ccu-v7", "pinctrl-base", "pinctrl-voltage-v3", "pinctrl-pf6")
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

def rename_first_pinctrl_patch(work):
    """6.18 semantic backport of the rename-only pinctrl patch 1/7.

    Never edit source checkout. Require exact old token and known affected files.
    This deliberately does NOT substitute any register or IRQ behavior.
    """
    old = "SUNXI_PINCTRL_NEW_REG_LAYOUT"
    new = "SUNXI_PINCTRL_NCAT2_REG_LAYOUT"
    paths = (
        "drivers/pinctrl/sunxi/pinctrl-sun20i-d1.c",
        "drivers/pinctrl/sunxi/pinctrl-sun55i-a523-r.c",
        "drivers/pinctrl/sunxi/pinctrl-sun55i-a523.c",
        "drivers/pinctrl/sunxi/pinctrl-sunxi.c",
        "drivers/pinctrl/sunxi/pinctrl-sunxi.h",
    )
    replacements = {}
    for item in paths:
        file = work / item
        if not file.is_file():
            raise ValueError("Missing prerequisite for rename: " + item)
        data = file.read_text()
        if old not in data:
            raise ValueError("Expected legacy token absent: " + item)
        if new in data:
            raise ValueError("Mixed old/new layout flags: " + item)
        replacements[file] = data.replace(old, new)
    for file, body in replacements.items():
        file.write_text(body)
    return {str(f.relative_to(work)): body.count(new) for f, body in replacements.items()}


def validate_group(name, parsed, source, work, out, adapt_rename=False):
    results = []
    for i, patch in enumerate(parsed, 1):
        file = out / (name + "-%02d.patch" % i)
        file.write_text(patch["body"])
        if adapt_rename and name == "pinctrl-base" and i == 1:
            try:
                changed = rename_first_pinctrl_patch(work)
            except (ValueError, OSError) as err:
                results.append({"order": i, "subject": patch["subject"],
                                "message_id": patch["mid"], "paths": patch["files"],
                                "check": False, "diagnostic": str(err)})
                break
            results.append({"order": i, "subject": patch["subject"],
                            "message_id": patch["mid"], "paths": patch["files"],
                            "check": True, "scratch_apply": True,
                            "adaptation": "6.18 semantic flag rename only; not a clean patch apply",
                            "renamed_file_counts": changed, "diagnostic": ""})
            continue
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

def conflict_context(work, patch, out):
    """Capture exact 6.18 context for failed hunks, preserving the scratch tree.

    Intended for review, not partial patch application or auto-merging.
    """
    paths = sorted(set(patch["files"]))
    blocks = []
    markers = {
        "drivers/pinctrl/sunxi/pinctrl-sunxi.c": (
            "sunxi_bank_offset(", "sunxi_dlevel_reg(",
            "sunxi_pinctrl_init_with_flags(", "pctl->flags = flags;",
            "pctl->bank_mem_size = D1_BANK_MEM_SIZE;"),
        "drivers/pinctrl/sunxi/pinctrl-sunxi.h": (
            "D1_BANK_MEM_SIZE", "SUNXI_PINCTRL_NCAT2_REG_LAYOUT",
            "struct sunxi_pinctrl {", "sunxi_irq_base_reg("),
    }
    for name in paths:
        path = work / name
        if not path.is_file():
            blocks.append("MISSING " + name)
            continue
        data = path.read_text(errors="replace").splitlines()
        blocks.append("=== " + name + " ===")
        seen = set()
        for marker in markers.get(name, ()):
            offsets = [i for i, line in enumerate(data) if marker in line]
            for index in offsets[:2]:
                lo = max(0, index - 6)
                hi = min(len(data), index + 22)
                span = (lo, hi)
                if span in seen:
                    continue
                seen.add(span)
                blocks.append("--- marker: " + marker + " ---")
                blocks.extend(f"{j+1}: {data[j]}" for j in range(lo, hi))
    dest = out / "pinctrl-patch4-6.18-context.txt"
    dest.write_text("\n".join(blocks) + "\n")
    return str(dest)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--adapt-pinctrl-rename", action="store_true",
                   help="Apply only rename-only 1/7 semantics to scratch files for 6.18")
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
                  "groups": {}, "notice": "STATIC ONLY: no build, hardware or voltage tests",
                  "adapt_pinctrl_rename": args.adapt_pinctrl_rename}
        # All patch groups share a base tree only within pinctrl branch.
        for stage in ("ccu-v7", "pinctrl"):
            names = ("ccu-v7",) if stage == "ccu-v7" else (
                "pinctrl-base", "pinctrl-voltage-v3", "pinctrl-pf6")
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
                entries = validate_group(name, groups[name], args.source, work, args.output,
                                         adapt_rename=args.adapt_pinctrl_rename)
                if name == "pinctrl-base" and len(entries) >= 4 and not entries[3]["check"]:
                    path = conflict_context(work, groups[name][3], args.output)
                    entries[3]["review_context_file"] = path
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
