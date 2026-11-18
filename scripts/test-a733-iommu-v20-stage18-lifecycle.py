#!/usr/bin/env python3
"""Stage18 OFFLINE failure-injection model for A733 IOMMU provider lifecycle.

Does not operate on a kernel, devices or MMIO. This specification guards
ordering requirements; it cannot establish actual driver correctness.
"""
import unittest


class Fault(Exception):
    pass


class Model:
    """Controller owns resources; the core owns register-failure unregister."""

    def __init__(self):
        self.actions = []
        self.registered = False
        self.clients = 0
        self.cache = False
        self.dma_ptr = False
        self.clocks = 0
        self.resets = 0
        self.sysfs = 0

    def acquire(self, fail=None):
        try:
            self.cache = True
            self.actions.append("cache")
            if fail == "cache":
                raise Fault("cache")
            self.resets = 2
            self.actions.append("resets")
            if fail == "resets":
                raise Fault("resets")
            self.clocks = 3
            self.actions.append("clocks")
            if fail == "clocks":
                raise Fault("clocks")
            for n in range(3):
                if fail == "sysfs" + str(n):
                    raise Fault("sysfs")
                self.sysfs += 1
                self.actions.append("sysfs_create" + str(n))
            self.dma_ptr = True
            self.actions.append("dma_set")
            if fail == "register":
                # Simulate core acquiring a client, then undoing registration.
                self.clients = 1
                self.actions.append("core_probe")
                self.core_unregister()
                raise Fault("register")
            self.registered = True
            self.clients = 2
            self.actions.append("registered")
        except Fault:
            self.cleanup()
            raise

    def core_unregister(self):
        self.actions.append("core_unregister")
        self.clients = 0
        self.registered = False

    def cleanup(self):
        if self.registered:
            self.core_unregister()
        if self.clients:
            raise Fault("client/domain users remain during cleanup")
        if self.dma_ptr:
            self.actions.append("dma_clear")
            self.dma_ptr = False
        while self.sysfs:
            self.sysfs -= 1
            self.actions.append("sysfs_remove" + str(self.sysfs))
        if self.clocks:
            self.actions.append("clocks_disable")
            self.clocks = 0
        if self.resets:
            self.actions.append("resets_assert")
            self.resets = 0
        if self.cache:
            self.actions.append("cache_destroy")
            self.cache = False


class Tests(unittest.TestCase):
    def check_clean(self, s):
        self.assertFalse(s.registered)
        self.assertEqual(s.clients, 0)
        self.assertFalse(s.dma_ptr)
        self.assertEqual(s.sysfs, 0)
        self.assertEqual(s.resets, 0)
        self.assertEqual(s.clocks, 0)
        self.assertFalse(s.cache)

    def test_happy_teardown(self):
        s = Model()
        s.acquire()
        s.cleanup()
        self.check_clean(s)
        self.assertLess(s.actions.index("core_unregister"),
                        s.actions.index("dma_clear"))
        self.assertLess(s.actions.index("dma_clear"),
                        s.actions.index("cache_destroy"))

    def test_registration_failure_core_unregistered_once(self):
        s = Model()
        with self.assertRaises(Fault):
            s.acquire("register")
        self.check_clean(s)
        self.assertEqual(s.actions.count("core_unregister"), 1)

    def test_partial_sysfs_failure_at_each_attribute(self):
        for step in range(3):
            with self.subTest(step=step):
                s = Model()
                with self.assertRaises(Fault):
                    s.acquire("sysfs" + str(step))
                self.check_clean(s)
                self.assertEqual(len([x for x in s.actions
                                      if x.startswith("sysfs_remove")]), step)

    def test_cache_failure(self):
        s = Model()
        with self.assertRaises(Fault):
            s.acquire("cache")
        self.check_clean(s)

    def test_reset_failure(self):
        s = Model()
        with self.assertRaises(Fault):
            s.acquire("resets")
        self.check_clean(s)

    def test_clock_failure(self):
        s = Model()
        with self.assertRaises(Fault):
            s.acquire("clocks")
        self.check_clean(s)

    def test_no_unregister_on_pre_register_sysfs_error(self):
        s = Model()
        with self.assertRaises(Fault):
            s.acquire("sysfs1")
        self.assertEqual(s.actions.count("core_unregister"), 0)

    def test_sysfs_removed_reverse_order(self):
        s = Model()
        s.acquire()
        s.cleanup()
        self.assertEqual([x for x in s.actions
                          if x.startswith("sysfs_remove")],
                         ["sysfs_remove2", "sysfs_remove1", "sysfs_remove0"])

    def test_dma_ptr_does_not_survive_successful_remove(self):
        s = Model()
        s.acquire()
        s.cleanup()
        self.assertIn("dma_clear", s.actions)
        self.assertFalse(s.dma_ptr)

    def test_cache_not_destroyed_with_clients(self):
        s = Model()
        s.cache = True
        s.clients = 1
        with self.assertRaises(Fault):
            s.cleanup()
        self.assertTrue(s.cache)

    def test_repeat_cleanup_safe_without_registered_clients(self):
        s = Model()
        s.acquire()
        s.cleanup()
        s.cleanup()
        self.check_clean(s)
        self.assertEqual(s.actions.count("core_unregister"), 1)

    def test_failure_cannot_leave_controller_resources(self):
        for stage in ("cache", "resets", "clocks", "sysfs0", "sysfs1",
                      "sysfs2", "register"):
            with self.subTest(stage=stage):
                s = Model()
                with self.assertRaises(Fault):
                    s.acquire(stage)
                self.check_clean(s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
