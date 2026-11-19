#!/usr/bin/env python3
"""Stage16 draft source checks, not hardware safety or kernel runtime tests."""
from pathlib import Path
import argparse, unittest

DEFAULT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage16-probe-draft.c")
class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        a=argparse.ArgumentParser()
        a.add_argument("--source",type=Path,default=DEFAULT)
        args=a.parse_args()
        cls.src=args.source.read_text()
        cls.probe=cls.src.split("static int sunxi_iommu_probe(struct platform_device *pdev)",1)[1].split("static int sunxi_iommu_remove(struct platform_device *pdev)",1)[0]

    def test_explicit_errno(self):
        self.assertIn("ret = -ENODEV;",self.probe)
        self.assertIn("ret = -ENOMEM;",self.probe)
    def test_ioremap_errno(self):
        self.assertIn("IS_ERR(sunxi_iommu->base)",self.probe)
        self.assertIn("PTR_ERR(sunxi_iommu->base)",self.probe)
    def test_clocks_enable_checked(self):
        self.assertIn("ret = clk_prepare_enable(*pclk);",self.probe)
        self.assertIn("clocks_done++;",self.probe)
    def test_clock_rollback(self):
        self.assertIn("clk_disable_unprepare(sunxi_iommu->clk[i]);",self.probe)
        self.assertIn("kfree(sunxi_iommu->clk);",self.probe)
    def test_reset_rollback(self):
        self.assertIn("resets_done++;",self.probe)
        self.assertIn("reset_control_assert(sunxi_iommu->rst[i]);",self.probe)
    def test_sysfs_rollback(self):
        self.assertIn("if (core_sysfs)",self.probe)
        self.assertIn("if (driver_sysfs)",self.probe)
    def test_global_unpublished_on_failure(self):
        self.assertIn("if (global_iommu_dev == sunxi_iommu)",self.probe)
        self.assertIn("global_iommu_dev = NULL;",self.probe)
    def test_no_manual_devm_unwind(self):
        err=self.probe.split("err_cleanup:",1)[1]
        self.assertNotIn("devm_free_irq(",err)
        self.assertNotIn("devm_iounmap(",err)
    def test_single_cleanup_label(self):
        self.assertEqual(self.probe.count("\nerr_cleanup:"),1)
        for label in ("err_plat:","err_clk:","err_irq:","err_res:"):
            self.assertNotIn(label,self.probe)
    def test_always_keep_other_blockers_visible(self):
        self.assertIn("global_iommu_domain",self.src)
        self.assertIn("iommu_device_unregister(&sunxi_iommu->iommu);",self.src)

if __name__=="__main__":
    unittest.main(verbosity=2)
