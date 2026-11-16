# WSL resource inventory (2026-11-15)

**Origin:** Operator-run `scripts/audit-wsl-resource-inventory.sh`; the original `resources.tsv` and `git-worktrees.txt` were reviewed. All checksums below describe files on the operator's WSL host, not files committed to this repository. Image names are controls, not releases.

## Pinned checkouts verified on host

| Source | Commit |
| --- | --- |
| `/root/opi3w-vendor-6698-work/kernel` | `2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f` |
| `/root/opi3w-hybrid-sources-0.1.0/linux` | `4aea1dc4cad17cd146072e13b1fd404f32b8b3ef` |
| `/root/opi3w-hybrid-sources-0.1.0/allwinner-bsp` | `656a550c826787e7e72fae58ca793df9e0988ac8` |
| `/root/opi3w-hybrid-sources-0.1.0/a733-integration` | `fc71840a8b5bb17a73ed42cc00e46838a97c8aa1` |
| `/root/opi3w-hybrid-sources-0.1.0/zero3w-vendor-reference` | `2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f` |

## Compiled artifact inventory

| Artifact | Size (bytes) | SHA256 |
| --- | ---: | --- |
| Vendor 6.6.98 control Image | 25,178,120 | `e7c19a16ca94c4832f40ee04c26e6510a15c1d7b636957f001e82abb5f442340` |
| Vendor 6.6.98 control DTB | 214,166 | `116f9c900d75bfae64fc24653c03108dc1cff56bbe3fdbbb9b291bbd25a49fc6` |
| Vendor 6.6.98 identity Image | 25,178,120 | `f41226db14e80a518220d0bb90795c4c4baa081cd8a935b110f91df2779d967c` |
| Vendor 6.6.98 identity DTB | 214,166 | `5868cc38042c7de3d9a714f45215e90083223e2b0e2ec7eb3af87a064fb5e443` |
| Hybrid 6.18.19 `vmlinux` | 11,491,584 | `bd0e1ae852534c8fe6d2fa5ad0338351a2c347a0660dab7537fb2bc4105b2046` |
| Hybrid 6.18.19 Image | 8,591,368 | `e4b2eff08dfc7e2553cf498def6658515f5f2f1e5e8066d0fcc60a73742069c7` |
| Hybrid 6.18.19 DTB | 171,337 | `5c9cd102215183cc56150aab2ce331216bea26d80741cdfc1fb0d95f5818e7b9` |
| F1 running DTB | 589,952 | `5a8db361113336b27f428520fb5b00e80c9a16ae9dd755743dc0d65ed9376db9` |

**Important:** Control and identity kernel Image hashes differ despite both building from the same pinned source and differing intentionally only in the root DTS. This could arise from build metadata or nondeterminism; until binary comparison and embedded version/config analysis, **do not claim byte identity or that the kernel payload is unchanged**.

## Disk image manifests (not committed)

| Disk image | Size (bytes) | SHA256 |
| --- | ---: | --- |
| Stock vendor 1.0.2 | 4,424,990,720 | `0dbf4f5de26760760afe859c70e69cab695e6aedd38d6bd238b7c3a6572f5537` |
| VBI | 4,424,990,720 | `7c76d125013df144d238526e396c1c9d5878c2cdf57eaa3ac09f613e32afa63c` |
| HBI-027 | 4,424,990,720 | `6604ba2427c918c893880fcb8f44b8733f1c3e74b5acf91454f77c62e55c88f5` |
| K2 | 4,424,990,720 | `9be8075b4cf12788576980c299cf1e4940ad7e995ce5845770af01c9e709a150` |
| F1 | 4,424,990,720 | `2cf782f2e2cb37ca5582b6e9a490df309d30a1eab77561211f81eeca3449f8a6` |
| F2 | 4,424,990,720 | `7a393e3f3cc1ddff39d963899f5073bb5a5f858abd08884b75046bcb42135758` |

Every image above exists in the inventoried WSL location. **No disk image was uploaded to GitHub.**

## Missing from canonical repository

1. Exact complete hybrid 0.2.7 BSP source transformation, including copied files, modified files, any untracked source files and the build recipe.
2. Complete reproducible kernel config and module-install/initramfs/assembler implementation for 0.2.7, not merely source pins and finished binary hashes.
3. Finished-image assembler for VBI/HBI/K2/F1/F2, with verifiable one-change audits and original firmware preservation.
4. F1 proof archive was **not found at the inventoried Windows Downloads path**. The source was previously inspected in the conversation; recover the original if archival bytes are desired.
5. Test control vs identity kernel Image difference before identifying the DTS as the sole binary change.

**Next:** export the exact hybrid builder and inspect its source contents for credentials, third-party license obligations, generated files and redundancies. Do not blindly commit the whole `/root/opi3w-hybrid-build-0.2.7/linux` tree. See [engineering index](../docs/2026-11-15-engineering-index.md).
