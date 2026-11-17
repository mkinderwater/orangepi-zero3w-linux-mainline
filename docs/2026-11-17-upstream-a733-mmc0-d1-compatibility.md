# A733 MMC0 integration: upstream D1 fallback, not vendor AW_MMC

**Status 2026-11-17:** Static source and DTS-binary audit stage; MMC0 has **not** been built with a canonical board DTB or tested on the Zero 3W. The clean 6.18 Image (SHA256 `24f58c911c8f382ee48c63952280d504ebe8f1412786fa37fb8af5a38dd8247e`, 4,429,832 bytes) is preserved.

## Grounded upstream compatibility

Jerome Brunet, 2026-07-31, submitted [A733 MMC0/1/2 D1 fallback](https://lists.infradead.org/pipermail/linux-arm-kernel/2026-July/1156864.html), [Message-ID](https://lists.openwall.net/linux-kernel/2026/07/31/1897) `20260731-allwinner-a733-mmc-support-v1-1-e9209e3f9761@baylibre.com`. A733 MMC0/1/2 are compatible with the D1 MMC IP and should advertise `compatible = "allwinner,sun60i-a733-mmc", "allwinner,sun20i-d1-mmc";`. MMC3 accesses DRAM differently and is **not** covered. Do not extrapolate the fallback to MMC3.

Our clean `CONFIG_MMC_SUNXI=y` host driver already recognizes `allwinner,sun20i-d1-mmc`; no new host code is justified at this stage. The existing imported BSP `AW_MMC` caused the confirmed `MMC_CAP2_HC_ERASE_SZ` bit-9 collision with Linux 6.18 UHS-II. **Do not reinstate AW_MMC, the old erase property, or earlier unexplained controller-specific capability flags.**

Binding backport staged at `patches/linux-6.18/0005-dt-bindings-mmc-a733-d1-fallback.patch`. This is a **binding only**, not a functional SD driver patch. Apply only in an isolated clean source copy once its `git apply --check` passes.

## Critical regulator and SD-card safeguards

The stock vendor/hybrid 0.2.7 DTB has MMC0 at 0x04020000, Wi-Fi MMC1 at 0x04021000, and MMC2 at 0x04022000. These are hardware controller locations, not an assertion of what is populated. Vendor and hybrid both include regulator phandle references, clock and pinctrl requirements. A counterpart's earlier A733 bring-up found the absence of a working AXP8191 regulator driver caused deferred MMC probe when `vmmc-supply` was declared, while deleting it caused `ocr_avail=0`. Restoring a real supply reference after PMIC functionality was available allowed their SD path to initialize. This is [third-party evidence](https://github.com/nickyg666/orangepi-zero3w-mainline), not a reproduced fix on our board.

**Do not remove `vmmc-supply` or fake voltages as a shortcut.** Verify the actual Zero 3W AXP8191/DC1SW2 rail, startup state, vqmmc and PF bank-voltage configuration. The old PF voltage-switch panic is a separate electrical gate. The D1-compatible controller requires correct A733 CCU clocks, reset, module clock, pinmux and voltage supplies before it can mount SD root.

## Immediate offline MMC DTB inspection

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only

git -C /root/opi3w-m2-work/a733-combined-clean-build-v1/linux apply --check \
  patches/linux-6.18/0005-dt-bindings-mmc-a733-d1-fallback.patch

python3 scripts/audit-a733-mmc-dtb.py \
  --vendor-dtb /root/opi3w-m2-work/m2dc-staged-verified/A/boot/dtb-6.6.98-sun60iw2/allwinner/sun60i-a733-orangepi-zero3w.dtb \
  --hybrid-dtb /root/opi3w-hybrid-build-0.2.7/stage/boot/sun60i-a733-orangepi-zero3w.dtb \
  --output /root/opi3w-m2-work/a733-mmc-dtb-audit-v1.json

cat /root/opi3w-m2-work/a733-mmc-dtb-audit-v1.json
```

The script reads binary device trees directly, identifies mmc nodes, property-level `compatible`/`status`, clocks/resets/pinctrl, legacy erase flags, and attempts supply phandle resolution. This prevents an easily missed prerequisite or mistaken regulator deletion. **No DTB is modified**.

## Next acceptance steps

1. Confirm actual MMC0 clock/reset IDs and their providers in the new upstream A733 CCU, and the GPIO pins/voltage bank in upstream A733 pinctrl. Compare to the actual Zero 3W board and the vendor working DTB, not guessed symbols.
2. Build a small canonical A733+Zero3W DTS using upstream mainline compatibles. Use the D1 fallback for MMC0 only initially, keep MMC1/2 disabled unless needed, and leave MMC3 unsupported. Preserve accurate regulator references.
3. Implement and validate minimum upstream AXP8191/AXP515 PMIC/regulator driver and bus requirements, or clearly document which rails are fixed/already supplied by firmware. Do not select guessed voltages.
4. Compile the DTB with `dtc`, validate with upstream bindings and compare its MMC/pinctrl/power nodes against baseline. Stage only after independent review.
5. Boot the new Image + DTB using existing proven firmware, serial and reversible boot path; require UART PID1, MMC0 enumeration, SD block availability, no PF voltage panic and repeatable ext4 root mount. Avoid boot claims until achieved.

**No legacy compatibility is inherited:** the one exception is the **upstream-supported D1-compatible MMC controller fallback**, which expresses genuine IP compatibility, not historic BSP ABI support.
