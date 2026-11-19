#!/usr/bin/env python3
"""Focused read-only Stage17 A733 v20 provider lifecycle and DMA audit.

Inspect exact kernel files, report matching functions and line-numbered context.
No source modification, MMIO access, build or boot. Fail closed on hashes.
"""
from __future__ import annotations
import argparse
import hashlib
import re
from pathlib import Path

ART = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
KERNEL = ART / "iommu-v20-port-stage1-kcflags/linux"
EXPECTED = {
    "v20": "aa78ce2829693be1c27e93647244f50dd86dc4f386930b2301ba8990b7d19b53",
    "core": "f130ba36dcb140e3e749f3cb77ca7a2df15033843d4d15ae55b8803fa60f2082",
    "pgtable": "aacc30517e7101177d55f4c67bbeaa4ab6ae7f70a4d15eecf9ab81197fdd6017",
}
FILES = {
    "v20": "drivers/iommu/aw-v20/sunxi-iommu-v2.c",
    "core": "drivers/iommu/iommu.c",
    "pgtable": "drivers/iommu/aw-v20/sunxi-iommu-pgtable.c",
    "common": "drivers/iommu/aw-v20/sunxi-iommu-common.c",
}
FUNCTIONS = {
    "v20": ("sunxi_iommu_probe", "sunxi_iommu_remove",
            "sunxi_iommu_sysfs_create", "sunxi_iommu_sysfs_remove",
            "sunxi_iommu_probe_distribute_masters",
            "sunxi_iommu_device_group", "sunxi_iommu_of_xlate",
            "sunxi_iommu_probe_device_finalize", "sunxi_iommu_release_device"),
    "core": ("iommu_device_register", "iommu_device_unregister",
             "iommu_init_device", "iommu_deinit_device", "bus_iommu_probe",
             "iommu_group_alloc", "iommu_group_ref_get", "iommu_group_put"),
    "pgtable": ("sunxi_pgtable_set_dma_dev", "sunxi_pgtable_alloc_pte_cache",
                "sunxi_pgtable_free_pte_cache", "sunxi_pgtable_alloc",
                "sunxi_pgtable_free", "sunxi_pgtable_clear"),
    "common": ("sunxi_iommu_sysfs_create", "sunxi_iommu_sysfs_remove",
               "sunxi_pgtable_set_dma_dev"),
}
TOKENS = (
    "dma_dev", "sunxi_pgtable_set_dma_dev", "sunxi_iommu_sysfs_create",
    "sunxi_iommu_sysfs_remove", "iommu_device_register",
    "iommu_device_unregister", "global_iommu_dev", "global_group",
    "clk_disable_unprepare", "clk_prepare_enable", "reset_control_assert",
    "reset_control_deassert", "iommu_group_put", "sunxi_iommu_remove",
)

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def function_definitions(text: str, name: str):
    """Find definitions by a bounded signature and brace, not comments/calls."""
    pattern = re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?(?:inline[ \t]+)?"
                         r"[\w \t*]+?\b" + re.escape(name) + r"\s*\(")
    for m in pattern.finditer(text):
        p = text.find("(", m.start())
        level = 0
        end_paren = None
        for i in range(p, min(len(text), p + 700)):
            if text[i] == "(":
                level += 1
            elif text[i] == ")":
                level -= 1
                if not level:
                    end_paren = i
                    break
        if end_paren is None:
            continue
        suffix = re.match(r"\s*\{", text[end_paren + 1:])
        if suffix is None:
            continue
        open_brace = end_paren + 1 + suffix.end() - 1
        level = 0
        for i in range(open_brace, len(text)):
            if text[i] == "{":
                level += 1
            elif text[i] == "}":
                level -= 1
                if level == 0:
                    start_line = text.count("\n", 0, m.start()) + 1
                    end_line = text.count("\n", 0, i) + 1
                    yield start_line, end_line
                    break

def excerpt(lines, first, last):
    return [f"{idx + 1}: {lines[idx]}" for idx in range(first - 1, last)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel", type=Path, default=KERNEL)
    ap.add_argument("--out", type=Path,
                    default=ART / "iommu-v20-stage17-cleanup.txt")
    a = ap.parse_args()
    if a.out.exists():
        ap.error("Refusing to overwrite report; choose a fresh --out")
    paths = {key: a.kernel / rel for key, rel in FILES.items()}
    for key, path in paths.items():
        if not path.is_file():
            ap.error(f"Missing {key} source: {path}")
        if key in EXPECTED and digest(path) != EXPECTED[key]:
            ap.error(f"{key} hash changed: {digest(path)}; re-audit first")
    report = ["A733 v20 Stage17 probe/remove, sysfs and DMA lifetime evidence",
              "READ ONLY. Runtime activation BLOCKED.", ""]
    for key, path in paths.items():
        src = path.read_text(errors="replace")
        lines = src.splitlines()
        report.extend([f"FILE {key}: {path}", f"SHA256 {digest(path)}"])
        for name in FUNCTIONS[key]:
            definitions = list(function_definitions(src, name))
            report.append(f"FUNCTION {name}: {len(definitions)} definitions")
            for lo, hi in definitions:
                if hi - lo > 200:
                    report.append(f"  LINES {lo}-{hi} (first 110 and last 55)")
                    report.extend(excerpt(lines, lo, lo + 109))
                    report.append("  ...")
                    report.extend(excerpt(lines, hi - 54, hi))
                else:
                    report.extend(excerpt(lines, lo, hi))
                report.append("")
        report.append("ALL RELEVANT TOKEN OCCURRENCES")
        for term in TOKENS:
            found = [i for i, line in enumerate(lines)
                     if re.search(r"\b" + re.escape(term) + r"\b", line)]
            if not found:
                continue
            report.append(f"  {term}: {len(found)} at " +
                          ", ".join(str(i + 1) for i in found[:40]) +
                          (" (truncated)" if len(found) > 40 else ""))
        report.append("")
    report.extend([
        "REVIEW QUESTIONS (not assumed PASS):",
        "A. Does sunxi_pgtable_set_dma_dev have an inverse? Who holds dma_dev?",
        "B. Does vendor sysfs creation return an error or allow partial creation?",
        "C. Does iommu_device_register unwind all previously probed clients on error?",
        "D. Does successful remove disable clocks, assert resets and free platform data?",
        "E. Does the provider remain valid until final domain/client release?",
        "F. Are all global pointers cleared only after no user can dereference them?",
        "No patch or hardware activation follows from this report alone."
    ])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(report) + "\n")
    print(f"REPORT: {a.out}")
    print(f"LINES: {len(report)}")
    print("PROBE/REMOVE EVIDENCE ONLY; HARDWARE ACTIVATION BLOCKED")

if __name__ == "__main__":
    main()
