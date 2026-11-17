# A733 upstream patch intake: archive examined, 2026-11-17

**Evidence:** user-uploaded `a733-upstream-patches-v1.tar.gz`, extracted and inspected in this session. The tar includes the four expected b4 mailbox files, cover letters, fetch logs and an inventory. This is *not* a kernel build or A733 hardware validation.

## Contents and verification

| Series | Messages | Patch scope |
| --- | ---: | --- |
| CCU v7, Junhui Liu (2026-11-12) | **8/8** | A733 clock/reset YAML and ID headers, dual SDM patterns, R-CCU/PRCM, PLL, bus and module clocks, gates and resets |
| Pinctrl base, Andre Przywara (2026-09-10) | **7/7** | Sunxi register-layout/IRQ refactor, A733 pinctrl bindings, A733 main and A523/A733-R driver |
| A733 voltage-auto v3, Enzo Adriano (2026-11-09) | **1/1** | A733 two-bit PIO POW_MOD_SEL programming; changes pinctrl main and R descriptions |
| A733 PF6 IRQ read, Vinicius Pedrosa (2026-11-10) | **1/1** | Drops `irq_read_needs_mux` for A733 |

All messages have expected titles and Message-IDs, and the archive b4 logs report the patch counts. CCU b4 reported **red crossed attestation markers** for all eight patches, unlike the pinctrl series which reported green validated markers. This is an authentication/provenance caveat, **not evidence the CCU patches are malicious or bad**. Keep exact Message-IDs and upstream comparison before releasing binaries.

## Source dependencies, from actual diffs

- CCU 1/8 adds YAML and clock/reset binding IDs.
- CCU 2/8 modifies the **shared upstream** `ccu_sdm.c/.h` for dual patterns. Do not drop it when applying later A733 CCU patches.
- CCU 3/8 adds A733 R-CCU source and Kconfig/Makefile definitions.
- CCU 4-8/8 create and incrementally fill `ccu-sun60i-a733.c`: PLLs first, then bus, modules, gates and resets. **Apply in order**, not as independent patches.
- Pinctrl 1-4/7 refactor shared register layout and IRQ support before adding the A733-specific data. Pinctrl 5-7/7 add binding, A733 R compatible and main driver.
- Voltage v3 targets code added by pinctrl base; it **must follow base**.
- Voltage v3 has a context line `irq_read_needs_mux = true` that PF6 removes. For clean context, apply **voltage v3 before PF6** in the isolated scratch checkout, not the reverse.
- The voltage patch writes `0x55555555` to `pctl->pow_mod_sel_offset` at controller initialization to select AUTO for every two-bit bank. The patch itself explicitly says **not tested: board boot, 1.8 V switching, A523**. It has a Reviewed/Suggested/Tested trailer in the thread, but its own cover notes indicate the v3 voltage-setting implementation was changed after the earlier hardware test. Treat this as a **physical safety gate**; it is not automatically approved for flashing the Zero 3W.
- PF6 patch deletes an IRQ pinmux read workaround: A733 IRQ mux function is 14, but the old helper restores function 6, breaking card insert/removal interrupts. Author reports a Cubie A7Z test, not the Zero 3W.

## No vendor inheritance

The previously built hybrid BSP had vendor CCU files totalling 3,918 lines and vendor pinctrl files totalling 2,996 lines, plus dependencies. These mailboxes target **upstream** `drivers/clk/sunxi-ng` and `drivers/pinctrl/sunxi`, so they avoid importing the old drivers. A clean Kconfig still needs board-specific CCU, pinctrl, MMC, PMIC and a canonical Zero 3W DTS before hardware boot.

## Concrete next step: dry-run against pinned 6.18.19

The original WSL kernel `/root/opi3w-hybrid-sources-0.1.0/linux` is at commit `4aea1dc4cad17cd146072e13b1fd404f32b8b3ef`, as last reported by the operator. The archived patches were authored for later upstream kernel releases. We **have not** proved patch applicability against that source yet.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only

python3 scripts/check-a733-upstream-backport.py \
  --archive /root/opi3w-m2-work/a733-upstream-patches-v1.tar.gz \
  --source /root/opi3w-hybrid-sources-0.1.0/linux \
  --output /root/opi3w-m2-work/a733-upstream-check-v1

cat /root/opi3w-m2-work/a733-upstream-check-v1/review.md
```

The tool extracts only mailbox files from the archive into a temporary directory, copies only files addressed by the patches from the pinned source into two **separate temporary scratch trees**, and uses `git apply --check` and scratch `git apply` in mail order. It does **not** edit the Linux tree, install dependencies or build a kernel. Reports exact first conflicts and stages patches as files in the new report directory. The CCU group and pinctrl group cannot influence each other. Pinctrl voltage is checked before PF6 to avoid a false patch context conflict. It refuses to overwrite output. Review the report before proceeding.

**Gate:** If a patch does not apply, port or backport the precise upstream prerequisite into a separate experimental source branch. Do not paper over with `git apply --reject`, import all of the BSP, or merge the voltage-mode register write into the MMC test by default.

The **first actual kernel tests** should be CCU-only and pinctrl-base-only as independent compile/integration variants, with separate serial logs and the immutable 0.2.7 PID1 baseline preserved. The PF voltage change needs explicit board-voltage safety review before hardware.
