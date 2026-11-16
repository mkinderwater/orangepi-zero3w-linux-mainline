# Linux 6.18.19: A2V vendor-script isolation (Batch S)

Status: **script tests prepared, hardware NOT TESTED**. This is a prerequisite to interpreting experimental 6.18 handoff failures, not a 6.18 boot claim.

## Proven control

* A2P: stock vendor Linux 6.6.98, original `boot.scr`: hardware PASS.
* A2V: minimal stage one sources a byte-identical stock vendor stage two at 0x46000000: hardware PASS.
* A2M: rewritten vendor `bootm` procedure: frozen splash. It changed multiple boot operations, so its cause is not established.
* Linux 6.18.19 hybrid 0.2.7: compile PASS, hardware execution UNVERIFIED.

## Two competing tests, independently based on original A2V

| ID | Single changed operation | Everything else |
| --- | --- | --- |
| S1 | Suppress only `env import -t ${load_addr} ${filesize}` (leave outer file-existence/load conditional in place) | Unchanged vendor script |
| S2 | Suppress only `fdt resize 65536` | Unchanged vendor script |

Generate **each** script by decoding the *actual compiled* `/boot/mainline/stock-vendor-stage2.scr` from the proven A2V card, not by fetching a newer script from a repository. Require exactly one match for the operation being changed; fail closed if it differs. Recompile using `mkimage -A arm -T script -C none`, re-decode and compare payload bytes. Preserve original binaries and their SHA256.

An isolated source-generation utility is provided with this test set as `build_stage2_variants.py` for offline use.

## Card preparation

1. Preserve original A2V image, SHA256, `boot.scr`, `stock-vendor-stage2.scr` and partition metadata.
2. Make two **independent copies** of A2V. Do not stack S1 and S2 changes.
3. On each copy, replace only `/boot/mainline/stock-vendor-stage2.scr` with the corresponding generated script. **Never** replace stage one `/boot/boot.scr`.
4. Apply the proven mounted-ext4 boot-file normalization and validate SHA256/absence of sparse boot holes, filesystem checks, script compilation/payload, and identical kernel/DTB/initrd, bootloader and layout.
5. Validate each finished SD image, not just the source template. Retain audit manifest and hashes. Use disposable cards.
6. Boot A2V control again, then S1 and S2 independently. Record serial/HDMI/SSH observations; splash alone does not prove the kernel stage.
7. Do not mark PASS without direct operator confirmation. Never add a fallback boot path that may disguise the tested handoff.

**Important:** This procedure does not automatically generate final SD images; image copying, mounted filesystem changes and normalization are intentionally separate to avoid overwriting proven controls.

## Linux 6.18 integration after isolation

Preserve vendor initialization semantics. A raw ARM64 `Image` needs a separately verified `booti` handoff, not a literal reuse of vendor `bootm`. Confirm actual raw Image header and footprint, script/kernel/DTB/initrd memory non-overlap, matching 6.18.19 initramfs/modules, Zero 3W DTB source, expanded bootargs and root device. No vendor fallback on the test branch. Obtain a storage-independent early `/init` or serial/GPIO checkpoint before diagnosing HDMI. Keep HDMI/KMS support included and test it after confirmed kernel entry.

## Acceptance

Only call the milestone successful after physical `uname -r` reports Linux 6.18.19, root storage is mounted, HDMI modesetting is demonstrated, networking and RAM detection are validated. Treat compilation alone as BUILD-ONLY.
