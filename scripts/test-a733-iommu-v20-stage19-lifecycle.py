#!/usr/bin/env python3
"""Read-only structural checks for Stage19 generated C, NOT runtime tests."""
import argparse
from pathlib import Path
import unittest

DEFAULT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage19-lifecycle-draft.c")
class Check(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=argparse.ArgumentParser()
        p.add_argument("--source",type=Path,default=DEFAULT)
        a=p.parse_args()
        cls.text=a.source.read_text()
        cls.probe=cls.text.split("static int sunxi_iommu_probe(struct platform_device *pdev)",1)[1].split("static int sunxi_iommu_remove(struct platform_device *pdev)",1)[0]
        cls.remove=cls.text.split("static int sunxi_iommu_remove(struct platform_device *pdev)",1)[1].split("/* Diagnostic API adapter:",1)[0]
        cls.sysfs=cls.text.split("static int sunxi_iommu_sysfs_create(",1)[1].split("static void sunxi_iommu_sysfs_remove(",1)[0]
    def test_sysfs_errors_propagate(self):
        self.assertIn("ret = sunxi_iommu_sysfs_create(",self.probe)
        self.assertIn("if (ret)\n\t\tgoto err_cleanup;",self.probe)
    def test_sysfs_undo_two_successes(self):
        self.assertIn("err_profile:",self.sysfs)
        self.assertIn("err_enable:",self.sysfs)
        self.assertIn("device_remove_file(",self.sysfs)
    def test_only_one_unregister_in_normal_remove(self):
        self.assertEqual(self.remove.count("iommu_device_unregister("),1)
        self.assertNotIn("iommu_device_unregister(",self.probe)
    def test_registration_fail_core_unwound_group(self):
        self.assertIn("registration_attempted = true;",self.probe)
        self.assertIn("if (registration_attempted)",self.probe)
        self.assertIn("iommu_group_put(group);",self.probe)
    def test_clear_dma_after_unregister_on_remove(self):
        self.assertLess(self.remove.index("iommu_device_unregister("),
                        self.remove.index("sunxi_pgtable_set_dma_dev(NULL)"))
    def test_cache_after_irq_shutdown(self):
        self.assertLess(self.remove.index("devm_free_irq("),
                        self.remove.index("sunxi_pgtable_free_pte_cache("))
    def test_cache_after_dma_clear(self):
        self.assertLess(self.remove.index("sunxi_pgtable_set_dma_dev(NULL)"),
                        self.remove.index("sunxi_pgtable_free_pte_cache("))
    def test_clock_unwind_success(self):
        self.assertIn("clk_disable_unprepare(",self.remove)
        self.assertIn("kfree(sunxi_iommu->clk);",self.remove)
    def test_reset_unwind_success(self):
        self.assertIn("reset_control_assert(",self.remove)
    def test_platform_data_unwind_success(self):
        self.assertIn("kfree(sunxi_iommu->plat_data);",self.remove)
    def test_global_ownership_cleanup(self):
        self.assertIn("global_group = NULL;",self.remove)
        self.assertIn("global_iommu_dev = NULL;",self.remove)
        self.assertIn("if (dma_dev == dev)",self.probe)
    def test_other_safety_blockers_unresolved(self):
        self.assertIn("global_iommu_domain",self.text)
        self.assertIn("sunxi_iommu_attach_dev",self.text)
if __name__=="__main__":
    unittest.main(verbosity=2)
