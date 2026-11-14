# Boot-file allocation investigation

In the vendor-kernel `opi-3w-wbuild` image builder, a newly populated ext4 filesystem using `mkfs.ext4 -d` had a failing boot although compared kernel, initramfs, DTB and reserved boot bytes had identical contents to a working image. The failing kernel had **347 sparse logical 4 KiB blocks** and many extents, whereas the working kernel had **zero sparse holes**.

The validated fix, [`scripts/boot_allocation.py`](https://github.com/mkinderwater/opi-3w-wbuild/blob/main/scripts/boot_allocation.py), mounts the newly created ext4 image on a temporary loop device, checks hashes and links, rewrites regular boot files with physical allocation even for zero regions, confirms no sparse holes, preserves ownership/permissions/links, and checks hashes again. Assembly then runs fsck. The resulting diagnostic image booted with Wi-Fi, SSH, root expansion and GPU compute tests.

**Causation is not fully isolated:** the mount-and-rewrite procedure also initializes journal state. A host-side U-Boot ext4 reader could read the failing image, and the mount-only control test had no reported board result. Do not generalize this as proof that all U-Boot versions fail on sparse files. Sparse host `.img` storage is a separate issue.

The 0.7.6 image's `/usr/share/opi-3w-wbuild/boot-allocation.json` reports `boot_payloads_verified=true` and `all_regular_boot_files_dense=true`, with `boot/uImage` fully allocated (26,554,440 bytes).
