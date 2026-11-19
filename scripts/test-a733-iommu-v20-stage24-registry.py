#!/usr/bin/env python3
"""Stage24 static source checks and offline identity model. No hardware tests."""
import argparse
import unittest
from pathlib import Path

ART=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
SOURCE=ART/"iommu-v20-stage24-registry-draft.c"

class Owners:
    def __init__(self):
        self.cache=True
        self.live=set()
    def alloc(self,p):
        if not self.cache or p in self.live:
            return False
        self.live.add(p)
        return True
    def free(self,p):
        if p not in self.live:
            return False
        self.live.remove(p)
        return True
    def destroy(self):
        if self.live or not self.cache:
            return False
        self.cache=False
        return True

class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=argparse.ArgumentParser()
        p.add_argument("--source",type=Path,default=SOURCE)
        args=p.parse_args()
        cls.src=args.source.read_text()
        cls.alloc=cls.src.split("unsigned int *sunxi_pgtable_alloc(void)",1)[1].split("void sunxi_pgtable_free(",1)[0]
        cls.free=cls.src.split("void sunxi_pgtable_free(unsigned int *pgtable)",1)[1].split("void sunxi_pgtable_clear(",1)[0]
        cls.cache=cls.src.split("void sunxi_pgtable_free_pte_cache(struct kmem_cache *iopte_cache)",1)[1].split("void sunxi_pgtable_set_dma_dev(",1)[0]

    def test_pointer_record_before_publish(self):
        self.assertLess(self.alloc.index("record = kzalloc("), self.alloc.index("list_add("))
        self.assertLess(self.alloc.index("record->addr = pgtable"), self.alloc.index("list_add("))
    def test_failed_record_allocation_never_publishes(self):
        self.assertIn("if (!record)\n\t\treturn NULL;",self.alloc)
    def test_registry_lock_allocation(self):
        self.assertIn("mutex_lock(&sunxi_pgtable_lifetime_lock);",self.alloc)
        self.assertIn("mutex_unlock(&sunxi_pgtable_lifetime_lock);",self.alloc)
    def test_registry_lock_release(self):
        self.assertIn("mutex_lock(&sunxi_pgtable_lifetime_lock);",self.free)
        self.assertIn("mutex_unlock(&sunxi_pgtable_lifetime_lock);",self.free)
    def test_wrong_pointer_not_freed(self):
        self.assertLess(self.free.index("if (WARN_ON_ONCE(!found))"),self.free.index("free_pages("))
    def test_unregister_before_free(self):
        self.assertLess(self.free.index("list_del(&found->node)"),self.free.index("free_pages("))
    def test_cache_needs_empty_registry(self):
        self.assertIn("WARN_ON_ONCE(!list_empty(&sunxi_pgtable_directories))",self.cache)
        self.assertLess(self.cache.index("list_empty("),self.cache.index("kmem_cache_destroy("))
    def test_cache_destroys_after_pointer_reset(self):
        self.assertLess(self.cache.index("sunxi_pgtable_params.iopte_cache = NULL;"),self.cache.index("kmem_cache_destroy("))
    def test_old_counter_and_last_pointer_removed(self):
        self.assertNotIn("sunxi_pgtable_live_directories",self.src)
        self.assertNotIn("sunxi_pgtable_params.pgtable =",self.src)
    def test_headers_and_other_functions_preserved(self):
        self.assertIn("#include <linux/list.h>",self.src)
        self.assertIn("#include <linux/mutex.h>",self.src)
        self.assertEqual(self.src.count("void sunxi_pgtable_set_dma_dev("),1)
        self.assertEqual(self.src.count("unsigned int *sunxi_pgtable_alloc("),1)
    def test_multiple_outstanding_cannot_destroy(self):
        o=Owners()
        self.assertTrue(o.alloc(100))
        self.assertTrue(o.alloc(200))
        self.assertFalse(o.destroy())
        self.assertTrue(o.free(100))
        self.assertFalse(o.destroy())
        self.assertTrue(o.free(200))
        self.assertTrue(o.destroy())
    def test_repeat_free_when_other_directory_remains(self):
        o=Owners()
        self.assertTrue(o.alloc(100))
        self.assertTrue(o.alloc(200))
        self.assertTrue(o.free(100))
        self.assertFalse(o.free(100))
        self.assertEqual(o.live,{200})
    def test_wrong_free_does_not_decrement(self):
        o=Owners()
        self.assertTrue(o.alloc(100))
        self.assertFalse(o.free(200))
        self.assertEqual(o.live,{100})
    def test_stale_free_after_destroy_rejected(self):
        o=Owners()
        o.alloc(100)
        o.free(100)
        o.destroy()
        self.assertFalse(o.free(100))
    def test_cache_cannot_reclaim_with_live_records(self):
        o=Owners()
        o.alloc(1)
        self.assertFalse(o.destroy())
    def test_registry_not_a_pte_fence(self):
        self.assertIn("does NOT serialize PTE map/unmap",self.src)

if __name__=="__main__":
    unittest.main(verbosity=2)
