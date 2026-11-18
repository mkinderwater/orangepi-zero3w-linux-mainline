#!/usr/bin/env python3
"""Stage21 OFFLINE domain-owner model for shared A733 v20 IOMMU.

Models separate core-owned domains even though all devices share one group.
No real C, MMIO, DMA, TLB or hardware operations. Design gate only.
"""
import unittest

class LifecycleError(Exception):
    pass

class Domain:
    def __init__(self, name):
        self.name = name
        self.mapped = False
        self.freed = False

class Controller:
    def __init__(self):
        self.domains = set()
        self.active = None
        self.group_clients = set()
        self.cache_alive = True
        self.removed = False

    def allocate(self, name):
        if self.removed or not self.cache_alive:
            raise LifecycleError("controller unavailable")
        d = Domain(name)
        self.domains.add(d)
        return d

    def map(self, d):
        self.require_live(d)
        d.mapped = True

    def require_live(self, d):
        if d not in self.domains or d.freed or not self.cache_alive:
            raise LifecycleError("invalid domain")

    def add_client(self, name):
        if self.removed or name in self.group_clients:
            raise LifecycleError("invalid group client")
        self.group_clients.add(name)

    def attach(self, d, name, *, flush_ok=True):
        self.require_live(d)
        if name not in self.group_clients:
            raise LifecycleError("unknown client")
        if not d.mapped:
            raise LifecycleError("required mappings not ready")
        if not flush_ok:
            # Failure must not publish a domain without safe rollback.
            raise LifecycleError("hardware transition failed")
        # Abstractly represent a COMPLETE table change shared by every master.
        self.active = d

    def free(self, d):
        self.require_live(d)
        if self.active is d:
            raise LifecycleError("cannot free installed TTB")
        self.domains.remove(d)
        d.freed = True

    def release_client(self, name):
        if name not in self.group_clients:
            raise LifecycleError("unknown client")
        self.group_clients.remove(name)
        if not self.group_clients:
            # Hardware now in safe bypass or blocked state, not a dangling TTB.
            self.active = None

    def destroy_cache(self):
        if self.domains or self.group_clients or self.active:
            raise LifecycleError("cache still owned by domains/devices")
        self.cache_alive = False

    def remove(self):
        if self.domains or self.group_clients or self.active:
            raise LifecycleError("controller still in use")
        self.destroy_cache()
        self.removed = True

class Tests(unittest.TestCase):
    def test_independent_allocation(self):
        c=Controller()
        a,b=c.allocate("DMA"),c.allocate("replacement")
        self.assertIsNot(a,b)
        self.assertEqual(len(c.domains),2)

    def test_mapping_before_attach(self):
        c=Controller()
        c.add_client("DE0")
        d=c.allocate("DMA")
        c.map(d)
        c.attach(d,"DE0")
        self.assertIs(c.active,d)

    def test_unmapped_attachment_fails(self):
        c=Controller()
        c.add_client("DE0")
        with self.assertRaises(LifecycleError):
            c.attach(c.allocate("DMA"),"DE0")
        self.assertIsNone(c.active)

    def test_failed_switch_preserves_active(self):
        c=Controller()
        c.add_client("DE0")
        a,b=c.allocate("DMA"),c.allocate("new")
        c.map(a)
        c.map(b)
        c.attach(a,"DE0")
        with self.assertRaises(LifecycleError):
            c.attach(b,"DE0",flush_ok=False)
        self.assertIs(c.active,a)

    def test_switch_then_free_previous(self):
        c=Controller()
        c.add_client("DE0")
        a,b=c.allocate("DMA"),c.allocate("new")
        c.map(a)
        c.map(b)
        c.attach(a,"DE0")
        c.attach(b,"DE0")
        c.free(a)
        self.assertTrue(a.freed)
        self.assertIs(c.active,b)

    def test_active_free_rejected(self):
        c=Controller()
        c.add_client("DE0")
        d=c.allocate("DMA")
        c.map(d)
        c.attach(d,"DE0")
        with self.assertRaises(LifecycleError):
            c.free(d)

    def test_cache_protected_by_inactive_domain(self):
        c=Controller()
        d=c.allocate("staged")
        with self.assertRaises(LifecycleError):
            c.destroy_cache()
        c.free(d)
        c.destroy_cache()
        self.assertFalse(c.cache_alive)

    def test_cache_protected_by_clients(self):
        c=Controller()
        c.add_client("DE0")
        with self.assertRaises(LifecycleError):
            c.destroy_cache()

    def test_multiple_clients_same_group_one_table(self):
        c=Controller()
        c.add_client("DE0")
        c.add_client("G2D")
        d=c.allocate("DMA")
        c.map(d)
        c.attach(d,"DE0")
        c.attach(d,"G2D")
        self.assertIs(c.active,d)
        c.release_client("G2D")
        self.assertIs(c.active,d)
        c.release_client("DE0")
        self.assertIsNone(c.active)
        c.free(d)
        c.remove()
        self.assertTrue(c.removed)

    def test_reject_free_from_wrong_controller(self):
        a,b=Controller(),Controller()
        d=a.allocate("DMA")
        with self.assertRaises(LifecycleError):
            b.free(d)

    def test_no_alloc_after_removal(self):
        c=Controller()
        c.remove()
        with self.assertRaises(LifecycleError):
            c.allocate("DMA")

    def test_double_free_rejected(self):
        c=Controller()
        d=c.allocate("DMA")
        c.free(d)
        with self.assertRaises(LifecycleError):
            c.free(d)

    def test_remove_rejects_live_domain(self):
        c=Controller()
        d=c.allocate("DMA")
        with self.assertRaises(LifecycleError):
            c.remove()
        c.free(d)
        c.remove()

if __name__=="__main__":
    unittest.main(verbosity=2)
