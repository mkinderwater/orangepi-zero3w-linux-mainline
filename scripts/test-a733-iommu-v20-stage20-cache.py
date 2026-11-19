#!/usr/bin/env python3
"""Stage20 static cache-lifetime regression checks; not kernel execution."""
from pathlib import Path
import argparse
import unittest

ART=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
DEFAULT=ART/"iommu-v20-stage20-cache-draft.c"

class CacheReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=argparse.ArgumentParser()
        p.add_argument("--source",type=Path,default=DEFAULT)
        a=p.parse_args()
        cls.src=a.source.read_text()
        cls.alloc=cls.src.split("struct kmem_cache *sunxi_pgtable_alloc_pte_cache(void)",1)[1].split("void sunxi_pgtable_free_pte_cache(",1)[0]
        cls.free=cls.src.split("void sunxi_pgtable_free_pte_cache(struct kmem_cache *iopte_cache)",1)[1].split("void sunxi_pgtable_set_dma_dev(",1)[0]

    def test_no_second_cache_allocation(self):
        self.assertIn("WARN_ON_ONCE(sunxi_pgtable_params.iopte_cache)",self.alloc)
        self.assertLess(self.alloc.index("WARN_ON_ONCE("),self.alloc.index("kmem_cache_create("))
    def test_alloc_null_not_published(self):
        self.assertIn("if (!cache)\n\t\treturn NULL;",self.alloc)
        self.assertLess(self.alloc.index("if (!cache)"),self.alloc.index("sunxi_pgtable_params.iopte_cache = cache;"))
    def test_no_double_free_on_null(self):
        self.assertIn("if (!iopte_cache)\n\t\treturn;",self.free)
    def test_wrong_cache_rejected(self):
        self.assertIn("WARN_ON_ONCE(sunxi_pgtable_params.iopte_cache != iopte_cache)",self.free)
    def test_live_page_directory_prevents_cache_free(self):
        self.assertIn("WARN_ON_ONCE(sunxi_pgtable_params.pgtable)",self.free)
    def test_internal_pointer_cleared_before_destroy(self):
        self.assertLess(self.free.index("sunxi_pgtable_params.iopte_cache = NULL;"),
                        self.free.index("kmem_cache_destroy(iopte_cache);"))
    def test_clear_only_on_valid_owner(self):
        self.assertLess(self.free.index("WARN_ON_ONCE(sunxi_pgtable_params.iopte_cache != iopte_cache)"),
                        self.free.index("sunxi_pgtable_params.iopte_cache = NULL;"))
    def test_no_dma_pointer_mutation_in_cache_helper(self):
        self.assertNotIn("sunxi_pgtable_params.dma_dev =",self.free)
    def test_cache_allocators_use_same_global(self):
        self.assertIn("kmem_cache_zalloc(sunxi_pgtable_params.iopte_cache",self.src)
        self.assertIn("kmem_cache_free(sunxi_pgtable_params.iopte_cache",self.src)
    def test_no_other_definitions_lost(self):
        self.assertEqual(self.src.count("void sunxi_pgtable_set_dma_dev("),1)
        self.assertEqual(self.src.count("void sunxi_pgtable_free_pte_cache("),1)
        self.assertEqual(self.src.count("struct kmem_cache *sunxi_pgtable_alloc_pte_cache("),1)

if __name__=="__main__":
    unittest.main(verbosity=2)
