#!/usr/bin/env python3
"""Host-side regression tests. No kernel build or hardware needed."""
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/release-kernel-manifest.py"
RELEASE = "6.18.19-opi3w-test"


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.img = self.root / "Image"
        self.dtb = self.root / "board.dtb"
        self.initrd = self.root / "initrd.gz"
        self.mods = self.root / RELEASE
        self.mods.mkdir()
        (self.mods / "controller.ko").write_bytes(b"synthetic module fixture")
        image = bytearray(128)
        struct.pack_into("<QQQ", image, 8, 0, 4096, 0xA)
        image[56:60] = b"ARMd"
        self.img.write_bytes(image)
        dtb = bytearray(64)
        dtb[:4] = b"\xd0\x0d\xfe\xed"
        struct.pack_into(">I", dtb, 4, 64)
        self.dtb.write_bytes(dtb)
        self.initrd.write_bytes(b"\x1f\x8b" + bytes(40))
        self.output = self.root / "out.json"

    def invoke(self):
        return subprocess.run([sys.executable, str(SCRIPT),
            "--image", str(self.img),
            "--dtb", str(self.dtb),
            "--initrd", str(self.initrd),
            "--modules", str(self.mods),
            "--kernel-release", RELEASE,
            "--output", str(self.output)],
            text=True, capture_output=True)

    def test_happy_path_and_refuse_overwrite(self):
        r = self.invoke()
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(self.output.read_text())
        self.assertEqual(data["status"], "STATIC_PREFLIGHT_ONLY_NOT_HARDWARE_TESTED")
        self.assertEqual(data["kernel_release"], RELEASE)
        self.assertEqual(data["image"]["declared_image_size"], 4096)
        self.assertNotEqual(self.invoke().returncode, 0)

    def test_bad_image_rejected_without_output(self):
        self.img.write_bytes(b"bad")
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.output.exists())

    def test_bad_dtb_rejected_without_output(self):
        self.dtb.write_bytes(b"bad")
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.output.exists())

    def test_missing_module_tree_rejected_without_output(self):
        (self.mods / "controller.ko").unlink()
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.output.exists())

    def test_module_release_mismatch_rejected(self):
        self.mods.rename(self.root / "wrong-release")
        self.mods = self.root / "wrong-release"
        self.assertNotEqual(self.invoke().returncode, 0)

    def test_legacy_initrd_supported(self):
        hdr = bytearray(64)
        hdr[:4] = b"\x27\x05\x19\x56"
        hdr[30] = 3
        self.initrd.write_bytes(hdr + b"fixture")
        r = self.invoke()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(self.output.read_text())["initrd"]["format"], "legacy-uInitrd")


if __name__ == "__main__":
    unittest.main()
