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
