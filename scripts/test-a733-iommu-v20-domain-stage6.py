#!/usr/bin/env python3
"""Offline smoke test for the Stage 6 guarded source transformation."""
import importlib.util
import pathlib
import unittest

SCRIPT=pathlib.Path(__file__).with_name("draft-a733-iommu-v20-domain-stage6.py")
spec=importlib.util.spec_from_file_location("stage6",SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class GuardTests(unittest.TestCase):
    def test_replace_requires_one_anchor(self):
        self.assertRaises(ValueError,mod.once,"a a","a","b","ambiguous")
        self.assertRaises(ValueError,mod.once,"abc","xyz","b","missing")
        self.assertEqual(mod.once("abc","b","Z","unique"),"aZc")
    def test_scoped_replacement_does_not_touch_other_section(self):
        text="start\nreturn 0;\nend\nreturn 0;"
        self.assertEqual(
            mod.scope(text,"start","end","return 0;","return -EINVAL;","scoped"),
            "start\nreturn -EINVAL;\nend\nreturn 0;")
    def test_rejects_ambiguous_scope(self):
        self.assertRaises(ValueError,mod.scope,"start\nend\nstart\nend",
                          "start","end","x","y","ambiguous")
    def test_audited_source_if_available(self):
        default=mod.BASE/"iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20/sunxi-iommu-v2.c"
        if not default.is_file():
            self.skipTest("Audited staged source is only on build host")
        import hashlib
        original=default.read_text()
        self.assertEqual(hashlib.sha256(default.read_bytes()).hexdigest(),mod.SOURCE_SHA)
        patched=mod.transform(original)
        self.assertNotEqual(original,patched)
        self.assertIn("return NULL;",patched)
        self.assertIn("err_hw_init:",patched)
        self.assertIn("global_iommu_domain = NULL;",patched)
        self.assertIn("owner->data != global_iommu_dev",patched)
        self.assertEqual(mod.transform(original),patched)

if __name__=="__main__":unittest.main()
