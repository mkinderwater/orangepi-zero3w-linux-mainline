#!/usr/bin/env python3
"""Stage 14: offline group reference/teardown specification.

Not Linux or kernel code. No hardware or files modified. Models the required
controller-held ref + one borrowed-return ref for each client, including error
paths and repeated probe after teardown.
"""
import unittest

class Failure(Exception):
    pass

class SharedGroup:
    def __init__(self):
        self.refs=1  # controller owns the initial iommu_group_alloc reference
        self.devices=set()
        self.closed=False

    def acquire(self,dev):
        if self.closed or dev in self.devices: raise Failure("invalid group get")
        self.refs+=1
        self.devices.add(dev)

    def release(self,dev):
        if self.closed or dev not in self.devices: raise Failure("invalid group put")
        self.devices.remove(dev)
        self.refs-=1

    def shutdown(self):
        if self.closed or self.devices: raise Failure("active group users")
        self.refs-=1
        if self.refs!=0: raise Failure("leaked group references")
        self.closed=True

class Controller:
    def __init__(self):
        self.group=None
        self.registered=False

    def register(self):
        if self.registered:raise Failure("already registered")
        self.group=SharedGroup()
        self.registered=True

    def attach_device(self,dev,group_probe_ok=True):
        if not self.registered:raise Failure("not registered")
        self.group.acquire(dev)
        if not group_probe_ok:
            # An unsuccessful core probe must drop its acquired group reference
            self.group.release(dev)
            raise Failure("device probing failed")

    def detach_device(self,dev):
        self.group.release(dev)

    def unregister(self):
        if not self.registered:raise Failure("not registered")
        self.group.shutdown()
        self.group=None
        self.registered=False

class TestGroupLifetime(unittest.TestCase):
    def setUp(self):
        self.c=Controller()
        self.c.register()

    def test_one_device(self):
        self.c.attach_device("DE0")
        self.assertEqual(self.c.group.refs,2)
        self.c.detach_device("DE0")
        self.assertEqual(self.c.group.refs,1)
        self.c.unregister()

    def test_multiple_group_members(self):
        for dev in ("DE0","DI","G2D","VE"):
            self.c.attach_device(dev)
        self.assertEqual(self.c.group.refs,5)
        for dev in ("DI","DE0","VE","G2D"):
            self.c.detach_device(dev)
        self.c.unregister()

    def test_failure_unwind(self):
        with self.assertRaises(Failure):
            self.c.attach_device("DE0",group_probe_ok=False)
        self.assertEqual(self.c.group.refs,1)
        self.assertFalse(self.c.group.devices)
        self.c.unregister()

    def test_repeated_acquire_rejected(self):
        self.c.attach_device("DE0")
        with self.assertRaises(Failure):self.c.attach_device("DE0")
        self.assertEqual(self.c.group.refs,2)
        self.c.detach_device("DE0")
        self.c.unregister()

    def test_remove_blocked_with_users(self):
        self.c.attach_device("DE0")
        with self.assertRaises(Failure):self.c.unregister()
        self.assertTrue(self.c.registered)
        self.c.detach_device("DE0")
        self.c.unregister()

    def test_no_stale_pointer_after_reprobe(self):
        old=self.c.group
        self.c.unregister()
        self.assertTrue(old.closed)
        self.c.register()
        self.assertIsNot(old,self.c.group)
        self.c.unregister()

    def test_double_release_rejected(self):
        self.c.attach_device("DE0")
        self.c.detach_device("DE0")
        with self.assertRaises(Failure):self.c.detach_device("DE0")
        self.c.unregister()

if __name__=="__main__":
    unittest.main(verbosity=2)
