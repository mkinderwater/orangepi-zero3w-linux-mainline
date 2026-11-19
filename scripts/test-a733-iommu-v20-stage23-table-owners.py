#!/usr/bin/env python3
"""Stage23 structural checks plus offline owner-count race model.

These tests cannot validate kernel allocation identity or DMA quiescence.
"""
import argparse
import unittest
from pathlib import Path

ART=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
SOURCE=ART/"iommu-v20-stage23-table-owners-draft.c"

class Model:
    def __init__(self):
        self.cache=False
        self.live=0
    def create_cache(self):
        if self.cache:
            return False
        self.cache=True
        return True
    def alloc(self):
        if not self.cache:
            return False
        self.live+=1
        return True
    def free(self):
        if self.live==0:
            return False
        self.live-=1
        return True
    def destroy_cache(self):
        if self.live or not self.cache:
            return False
        self.cache=False
        return True

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ap=argparse.ArgumentParser()
        ap.add_argument("--source",type=Path,default=SOURCE)
        args=ap.parse_args()
        cls.src=args.source.read_text()
        cls.alloc=cls.src.split("unsigned int *sunxi_pgtable_alloc(void)",1)[1].split("void sunxi_pgtable_free(unsigned int *pgtable)",1)[0]
        cls.free=cls.src.split("void sunxi_pgtable_free(unsigned int *pgtable)",1)[1].split("void sunxi_pgtable_clear(",1)[0]
        cls.cache_free=cls.src.split("void sunxi_pgtable_free_pte_cache(struct kmem_cache *iopte_cache)",1)[1].split("void sunxi_pgtable_set_dma_dev(",1)[0]

    def test_allocation_lock(self):
        self.assertIn("mutex_lock(&sunxi_pgtable_lifetime_lock);",self.alloc)
        self.assertIn("sunxi_pgtable_live_directories++;",self.alloc)
    def test_release_lock(self):
        self.assertIn("mutex_lock(&sunxi_pgtable_lifetime_lock);",self.free)
        self.assertIn("sunxi_pgtable_live_directories--;",self.free)
    def test_zero_count_blocks_cache_destroy(self):
        self.assertIn("WARN_ON_ONCE(sunxi_pgtable_live_directories)",self.cache_free)
        self.assertLess(self.cache_free.index("WARN_ON_ONCE(sunxi_pgtable_live_directories)"),
                        self.cache_free.index("kmem_cache_destroy(iopte_cache);"))
    def test_global_last_dir_no_longer_written(self):
        self.assertNotIn("sunxi_pgtable_params.pgtable =",self.src)
    def test_cache_pointer_cleared_before_free(self):
        self.assertLess(self.cache_free.index("sunxi_pgtable_params.iopte_cache = NULL;"),
                        self.cache_free.index("kmem_cache_destroy(iopte_cache);"))
    def test_cache_teardown_lock(self):
        self.assertIn("mutex_lock(&sunxi_pgtable_lifetime_lock);",self.cache_free)
        self.assertIn("mutex_unlock(&sunxi_pgtable_lifetime_lock);",self.cache_free)
    def test_nonzero_count_blocks_model_teardown(self):
        m=Model()
        self.assertTrue(m.create_cache())
        self.assertTrue(m.alloc())
        self.assertTrue(m.alloc())
        self.assertFalse(m.destroy_cache())
        self.assertTrue(m.free())
        self.assertFalse(m.destroy_cache())
        self.assertTrue(m.free())
        self.assertTrue(m.destroy_cache())
    def test_no_new_dir_after_cache_destroy(self):
        m=Model()
        m.create_cache()
        m.destroy_cache()
        self.assertFalse(m.alloc())
    def test_duplicate_cache_setup_rejected(self):
        m=Model()
        self.assertTrue(m.create_cache())
        self.assertFalse(m.create_cache())
    def test_unbalanced_free_rejected_model(self):
        m=Model()
        self.assertFalse(m.free())
    def test_original_setter_preserved(self):
        self.assertEqual(self.src.count("void sunxi_pgtable_set_dma_dev("),1)
    def test_bare_count_not_ownership_proof(self):
        self.assertIn("A count alone cannot prevent wrong-pointer or repeat-free bugs.",self.src)

if __name__=="__main__":
    unittest.main(verbosity=2)
