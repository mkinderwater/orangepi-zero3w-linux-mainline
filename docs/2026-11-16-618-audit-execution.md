# Next Linux 6.18 diagnostic: two read-only independent evidence collectors

**2026-11-16 status:** Both scripts committed, NOT yet run against operator WSL files, NOT a hardware test. No new kernel build. No image, firmware, clock or SD changes.

Objective: determine whether our 0.2.7 hybrid is missing the A733 7.3 critical clock dependencies and whether its exact ARM64 `Image`/U-Boot interface matches our handoff theory. Maintain separate independent tracks.

## Track A: CCU/PSCI/fabric clocks (source/config/DTB)

```bash
cd /root/orangepi-zero3w-linux-mainline
git switch test/618-hbi-handoff-audit
git pull --ff-only

python3 scripts/audit-618-a733-clocks.py \
  --build /root/opi3w-hybrid-build-0.2.7 \
  --output /root/opi3w-m2-work/audit-618-a733-clocks-v1

cat /root/opi3w-m2-work/audit-618-a733-clocks-v1/clock-audit.md
```

Generated output: `clock-audit.json`, `clock-audit.md`. Script only inspects source, final effective kernel `.config`, Image header and compiled DTB. Source hits are **candidate matches**; vendor Kbuild may use different names and clock controller logic. The operator must compare retained-clock semantics against [MiniMyth2 6008](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6008-clk-sunxi-ng-a733-mark-the-CPUS-bus-gate-as-critical.patch) and [6009](https://github.com/warpme/minimyth2/blob/master/script/kernel/linux-7.3/files/6009-clk-sunxi-ng-a733-keep-the-MSI-Lite-bus-clocks-runni.patch). No automatic patching.

## Track B: exact kernel/DTB/booti initramfs handoff (static only)

Identify the actual retained **second-stage script**. We do not guess its pathname:

```bash
K=/root/opi3w-hybrid-build-0.2.7
find "$K" -type f \( -name '*.scr' -o -name '*.cmd' \) -print | sort
find /root/opi3w-m2-work -maxdepth 5 -type f \( -name '*stage2*.scr' -o -name '*stage2*.cmd' \) -print | sort
```

Then run with the **real image payload files** from the audited HBI image (not arbitrary files found elsewhere). Avoid assuming the .stage/boot initial initrd equals the final LED probe initramfs, because previous tests substituted that initrd.

```bash
python3 scripts/audit-618-booti-handoff.py \
  --script /ABSOLUTE/PATH/TO/EXACT/SECOND-STAGE.scr \
  --image /root/opi3w-hybrid-build-0.2.7/stage/boot/Image \
  --dtb /root/opi3w-hybrid-build-0.2.7/stage/boot/sun60i-a733-orangepi-zero3w.dtb \
  --initrd /root/opi3w-m2-work/618-pid1-led-v1/pid1-probe-initramfs.cpio.gz \
  --output /root/opi3w-m2-work/audit-618-booti-v1.json
```

The second command uses the *intended* LED probe payload. If a finished SD image was flashed and then mounted/repacked, its exact paths and bytes still require independent on-image verification. Static script parsing does **not** execute U-Boot conditional branches or know its actual relocation.

**Minimum tests:** Image header magic `ARMd`, actual bytes, header `image_size`, SHA against original pinned 0.2.7; DTB SHA; raw gzip versus legacy uInitrd header; presence of `env import`, `fdt addr`, `fdt resize`, `booti` and conditional fallback text. A source script containing a vendor fallback is not enough to prove which kernel ran.

## Interpretation and next changes

| Track A | Track B | Action |
| --- | --- | --- |
| Vendor BSP clock semantics match Linux 7.3 critical behavior | Handoff differs from known working 6.18 interface | Try the coherent initrd-format/booti interface change against vendor-kernel control first |
| Specific critical fabric gate confirmed disabled or incorrectly reset | Handoff matches | One isolated CCU change in fresh build; **do not** combine with initrd change |
| Both show discrepancies | Both unresolved | Prioritize independently controlled hypotheses, **two changes in separate images**, not stacked |
| No evidence either way | No proof of kernel entry | Add independent early kernel observation, not another blind rebuild |

No 7.3 kernel sources or third-party proprietary firmware are copied into this repo. Preserve vendor Zero 3W Boot0, PMIC rails, DRAM profile and PL7 LED. Firstboot LED state divergence remains documented/deferred.

**Important:** The clock collector scans only selected source directories for likely offsets/names. It is a bounded triage tool, not a complete formal CCU/PMIC audit. If its output is empty, inspect vendor BSP Makefiles and clock register tables manually before calling any clock absent.

## Actual Track B result, 2026-11-16 (operator WSL output)

Ran `scripts/audit-618-booti-handoff.py` using retained decoded HBI second-stage `/root/opi3w-m2-work/618-pid1-final-audit/HBI-boot_mainline_stock-vendor-stage2.scr.cmd`, built 0.2.7 `stage/boot/Image`, `stage/boot/sun60i-a733-orangepi-zero3w.dtb` and LED-v1 PID1 probe archive.

- Status `OFFLINE_STATIC_AUDIT_NOT_KERNEL_BOOT_PROOF`.
- ARM64 Image magic `41524d64` (`ARMd`), text offset `0`, image size in header `9,043,968` bytes, file size `8,591,368` bytes, flags `0xa`, SHA256 `e4b2eff08dfc7e2553cf498def6658515f5f2f1e5e8066d0fcc60a73742069c7`, matches pinned HBI 0.2.7 Image.
- DTB matches pinned HBI 0.2.7 DTB.
- **This specific LED-v1 diagnostic initramfs** is raw gzip, size `290,236` bytes, SHA256 `cada2a6ebd278238f51ec35b64a3342562b98b03abf045c9ae271d23cb447bfa`. This differs from earlier original PID1 probe SHA/size; the operator separately demonstrated the LED-v1 probe under vendor Linux 6.6.98. Do not confuse test payloads.
- Decoded HBI second-stage `booti ${kernel_addr_r} ${ramdisk_addr_r}:${opi3w_vendor_initrd_size} ${fdt_addr_r}`; no `bootm` fallback; `fdt addr`, `fdt resize` and `env import` appear.
- This static audit **does not evaluate** `opi3w_vendor_initrd_size`, verify the script's last `load` or its `filesize` capture, model U-Boot runtime relocation, or prove that these are flashed SD bytes.

**Open check:** Inspect actual second-stage script lines around the initrd `load`, `setenv opi3w_vendor_initrd_size ${filesize}` and `booti`. Ensure `filesize` comes from **the intended initrd**, not the subsequent kernel or DTB load. Check loader return codes and no hidden fallback. This is read-only, no new build or flash.

```bash
S=/root/opi3w-m2-work/618-pid1-final-audit/HBI-boot_mainline_stock-vendor-stage2.scr.cmd
grep -n -C 5 -E 'initrd|ramdisk|filesize|opi3w_vendor_initrd_size|booti|kernel_addr_r|fdt_addr_r' "$S"
```

When script semantics are confirmed, next controlled handoff experiment may compare **legacy uInitrd + booti address** against **raw gzip + booti address:size** while retaining the same kernel/DTB and independent 6.6 control; the coherent interface change must be isolated from any clock change.

**Track A and Track B remain unresolved as to actual 6.18 execution.** No hardware PASS and no confirmed BL31 collision.

## HBI second-stage command order confirmed (2026-11-16)

Operator used `grep -a -n -C 5` on the retained script `HBI-boot_mainline_stock-vendor-stage2.scr.cmd`. The previous `grep` without `-a` only returned "binary file matches" because this export contains binary content. This is a text-display issue, not a boot result.

Observed script lines:

```text
20: env import -t ${load_addr} ${filesize}
38: setenv bootargs "... clk_ignore_unused ..."
42: load ${devtype} ${devnum} ${ramdisk_addr_r} ${prefix}mainline/hybrid-0.2.7-vbi/initrd.img-6.18.19-opi3w-hybrid-0.2.7
43: setenv opi3w_vendor_initrd_size ${filesize}
44: load ${devtype} ${devnum} ${kernel_addr_r} ${prefix}mainline/hybrid-0.2.7-vbi/Image
46: load ${devtype} ${devnum} ${fdt_addr_r} ${prefix}mainline/hybrid-0.2.7-vbi/sun60i-a733-orangepi-zero3w.dtb
47: fdt addr ${fdt_addr_r}
48: fdt resize 65536
63: booti ${kernel_addr_r} ${ramdisk_addr_r}:${opi3w_vendor_initrd_size} ${fdt_addr_r}
```

**Conclusion: PASS for ordering in the retained script source.** The initrd size variable is assigned immediately following the initrd `load`, *before* the following Image and DTB `load` commands overwrite U-Boot's global `filesize`. We cannot claim that the load returned success, nor that its runtime variable had the expected value, without observing the executing U-Boot environment. Source does not contain return-code guards on the three payload loads.

**Clock hypothesis downgraded:** The bootargs string explicitly includes `clk_ignore_unused`, which should suppress ordinary late unused-clock cleanup when honored by the running 6.18 kernel. This corroborates, but is distinct from, per-clock `CLK_IGNORE_UNUSED` flags in the BSP. It does **not** prove all clocks are initially enabled or that early clock drivers work. Do not attribute a pre-PID1 failure to unused-clock shutdown without further evidence.

**Handoff differential still open:** raw gzip with `booti ramdisk:size` (vendor 6.6 control PASS) versus legacy-wrapped tiny uInitrd with `booti ramdisk` (nickyg666 reported 6.18 Zero 3W PASS). This is a format/bootloader-path hypothesis, not a confirmed fault. Keep bootloader, Image, DTB and PMIC unchanged in any controlled interface comparison. The existing `echo OPI3W-VBI: vendor raw Image` line in HBI script is a **stale label** and does not establish which kernel runs; use hashes/UNAME/early execution evidence.
