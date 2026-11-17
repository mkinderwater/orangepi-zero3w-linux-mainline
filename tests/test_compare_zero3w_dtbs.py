#!/usr/bin/env python3
"""Synthetic DTB fixtures for the read-only binary comparator."""
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/compare-zero3w-dtbs.py"
spec = importlib.util.spec_from_file_location("dtbcompare", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def fixture(props=None, mmc=None):
    if props is None:
        props = {"compatible": b"old,board\x00"}
    all_names = list(props) + list((mmc or {}).keys())
    strings = b""
    offsets = {}
    for name in dict.fromkeys(all_names):
        offsets[name] = len(strings)
        strings += name.encode() + b"\x00"
    def tok(x):
        return struct.pack(">I", x)
    def field(name, value):
        return tok(3) + struct.pack(">II", len(value), offsets[name]) + value + bytes((-len(value)) % 4)
    data = tok(1) + bytes(4)
    for name, value in props.items():
        data += field(name, value)
    if mmc is not None:
        sub = b"sdmmc@4022000\x00"
        data += tok(1) + sub + bytes((-len(sub)) % 4)
        for name, value in mmc.items():
            data += field(name, value)
        data += tok(2)
    data += tok(2) + tok(9)
    so = 56
    st = so + len(data)
    total = st + len(strings)
    head = struct.pack(">10I", 0xd00dfeed, total, so, st, 40, 17, 16, 0, len(strings), len(data))
    return head + bytes(16) + data + strings

class CompareTests(unittest.TestCase):
    def test_raw_compatibles_status_and_boolean(self):
        before = module.parse(fixture(mmc={"status": b"okay\x00"}))[0]
        after = module.parse(fixture(
            props={"compatible": b"new,board\x00"},
            mmc={"status": b"disabled\x00", "mmc-high-capacity-erase-size": b""}))[0]
        differences = module.compare(before, after)
        self.assertEqual(len(differences), 3)
        self.assertTrue(any(i.get("property") == "mmc-high-capacity-erase-size" and
                            i["change"] == "added" and i["critical"]
                            for i in differences))
        self.assertTrue(any(i.get("property") == "status" and
                            i["vendor"]["strings"] == ["okay"] and
                            i["hybrid"]["strings"] == ["disabled"] for i in differences))

    def test_invalid_headers(self):
        raw = fixture()
        with self.assertRaises(ValueError):
            module.parse(raw[:-1])
        with self.assertRaises(ValueError):
            module.parse(bytes(4) + raw[4:])

    def test_report_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            one, two, output = base / "v.dtb", base / "h.dtb", base / "out"
            one.write_bytes(fixture())
            two.write_bytes(fixture(mmc={"mmc-high-capacity-erase-size": b""}))
            args = [sys.executable, str(SCRIPT), "--vendor", str(one),
                    "--hybrid", str(two), "--output", str(output)]
            first = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            data = json.loads((output / "dtb-diff.json").read_text())
            self.assertEqual(data["status"], "STATIC_ONLY")
            self.assertEqual(len(data["changes"]), 1)
            second = subprocess.run(args, capture_output=True)
            self.assertNotEqual(second.returncode, 0)

if __name__ == "__main__":
    unittest.main()
