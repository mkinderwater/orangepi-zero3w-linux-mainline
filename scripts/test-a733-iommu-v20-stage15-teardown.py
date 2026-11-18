#!/usr/bin/env python3
"""Stage15 source draft ordering checks, not hardware or runtime tests."""
from pathlib import Path
import argparse,re,unittest

P=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-stage15-teardown-draft.c")
class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parser=argparse.ArgumentParser()
        parser.add_argument("--source",type=Path,default=P)
        args=parser.parse_args()
        cls.src=args.source.read_text()
        cls.remove=cls.src.split("static int sunxi_iommu_remove(struct platform_device *pdev)",1)[1].split("/* Diagnostic API adapter:",1)[0]
    def test_unregister_before_cache_free(self):
        self.assertLess(self.remove.index("iommu_device_unregister(&sunxi_iommu->iommu)"),
                        self.remove.index("sunxi_pgtable_free_pte_cache(iopte_cache)"))
    def test_unregister_before_irq_free(self):
        self.assertLess(self.remove.index("iommu_device_unregister(&sunxi_iommu->iommu)"),
                        self.remove.index("devm_free_irq("))
    def test_unregister_before_iounmap(self):
        self.assertLess(self.remove.index("iommu_device_unregister(&sunxi_iommu->iommu)"),
                        self.remove.index("devm_iounmap("))
    def test_unregister_before_group_put(self):
        self.assertLess(self.remove.index("iommu_device_unregister(&sunxi_iommu->iommu)"),
                        self.remove.index("iommu_group_put(group)"))
    def test_global_group_reset_before_put(self):
        self.assertLess(self.remove.index("global_group = NULL;"),
                        self.remove.index("iommu_group_put(group)"))
    def test_no_duplicate_unregister(self):
        self.assertEqual(self.remove.count("iommu_device_unregister(&sunxi_iommu->iommu)"),1)
    def test_known_probe_hazards_still_present(self):
        probe=self.src.split("static int sunxi_iommu_probe(struct platform_device *pdev)",1)[1].split("static int sunxi_iommu_remove(",1)[0]
        self.assertIn("goto err_clk;",probe)
        self.assertIn("clk_prepare_enable(*pclk);",probe)
        # Explicitly record that this draft does not repair clock failure rollback.
        self.assertNotIn("clk_disable_unprepare(*pclk);",probe)
if __name__=="__main__":unittest.main(verbosity=2)
