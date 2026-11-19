#!/usr/bin/env python3
"""Stage 10 OFFLINE A733 v20 single-TTB ownership state-machine tests.

No driver code, MMIO, DTB, kernel build or hardware interaction. This model
defines intended invariants, not evidence that Linux core supports the design.
"""
import unittest

class Reject(Exception):
    pass

class Controller:
    def __init__(self):
        self.ready=False
        self.context=None
        self.domain=None
        self.enabled=set()
        self.members={}
        self.epoch=0

    def probe(self):
        if self.ready: raise Reject("double probe")
        self.ready=True

    def allocate(self, tag, hardware_ok=True):
        if not self.ready or self.domain is not None:
            raise Reject("no free controller translation context")
        # Allocation does not publish a global domain until init succeeded.
        if not hardware_ok:
            raise Reject("initialization failed")
        self.epoch+=1
        self.domain=(tag,self.epoch)
        self.context=self.domain
        return self.domain

    def attach(self, dom, dev, master, flag):
        if self.domain!=dom or self.context!=dom:
            raise Reject("not the active domain")
        if not 0<=master<12 or master in (4,5):
            raise Reject("invalid or skipped master ID")
        if flag!=1:
            raise Reject("translation not requested by this model")
        if master in self.members and self.members[master]!=dev:
            raise Reject("master already owned")
        if dev in self.members.values() and self.members.get(master)!=dev:
            raise Reject("device already has another master")
        self.members[master]=dev
        self.enabled.add(master)

    def detach(self, dom, dev, master):
        if self.domain!=dom or self.members.get(master)!=dev:
            raise Reject("incorrect domain or owner")
        # Model quiescence requirement separately: no hardware DMA here.
        self.enabled.remove(master)
        del self.members[master]

    def free(self, dom):
        if self.domain!=dom:
            raise Reject("foreign or stale domain")
        if self.members or self.enabled:
            raise Reject("attached clients must detach")
        self.context=None
        self.domain=None

    def remove(self):
        if self.domain is not None or self.members or self.enabled:
            raise Reject("active translation context")
        if not self.ready:raise Reject("not probed")
        self.ready=False

class Tests(unittest.TestCase):
    def setUp(self):
        self.c=Controller()
        self.c.probe()

    def test_de0_happy_path(self):
        d=self.c.allocate("de")
        self.c.attach(d,"DE0",8,1)
        self.assertEqual(self.c.members,{8:"DE0"})
        self.c.detach(d,"DE0",8)
        self.c.free(d)
        self.c.remove()

    def test_no_publication_on_init_failure(self):
        with self.assertRaises(Reject):self.c.allocate("de",hardware_ok=False)
        self.assertIsNone(self.c.domain)
        d=self.c.allocate("retry")
        self.c.free(d)

    def test_double_alloc_never_aliases(self):
        d=self.c.allocate("first")
        with self.assertRaises(Reject):self.c.allocate("second")
        self.c.free(d)
        d2=self.c.allocate("new")
        self.assertNotEqual(d,d2)
        self.c.free(d2)

    def test_stale_domain_cannot_attach(self):
        d=self.c.allocate("old")
        self.c.free(d)
        new=self.c.allocate("new")
        with self.assertRaises(Reject):self.c.attach(d,"DE0",8,1)
        self.c.free(new)

    def test_no_double_master(self):
        d=self.c.allocate("de")
        self.c.attach(d,"DE0",8,1)
        with self.assertRaises(Reject):self.c.attach(d,"G2D",8,1)
        self.c.detach(d,"DE0",8)
        self.c.free(d)

    def test_invalid_and_skip_master_ids(self):
        d=self.c.allocate("de")
        for m in (-1,4,5,12,999):
            with self.subTest(master=m),self.assertRaises(Reject):
                self.c.attach(d,"client",m,1)
        self.c.free(d)

    def test_unsupported_flag_rejected(self):
        d=self.c.allocate("de")
        with self.assertRaises(Reject):self.c.attach(d,"ISP",2,0)
        self.c.free(d)

    def test_cannot_free_while_attached(self):
        d=self.c.allocate("de")
        self.c.attach(d,"DE0",8,1)
        with self.assertRaises(Reject):self.c.free(d)
        with self.assertRaises(Reject):self.c.remove()
        self.c.detach(d,"DE0",8)
        self.c.free(d)

    def test_wrong_owner_cannot_detach(self):
        d=self.c.allocate("de")
        self.c.attach(d,"DE0",8,1)
        with self.assertRaises(Reject):self.c.detach(d,"other",8)
        self.c.detach(d,"DE0",8)
        self.c.free(d)

    def test_shared_translation_domain_membership(self):
        d=self.c.allocate("display")
        for dev,master in (("DE0",8),("DI",9),("G2D",10),("EINK",11)):
            self.c.attach(d,dev,master,1)
        self.assertEqual(len(self.c.members),4)
        for dev,master in (("DE0",8),("DI",9),("G2D",10),("EINK",11)):
            self.c.detach(d,dev,master)
        self.c.free(d)

if __name__=="__main__":
    unittest.main(verbosity=2)
