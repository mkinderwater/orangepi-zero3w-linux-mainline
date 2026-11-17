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

## 2026-11-17: real vendor/hybrid MMC DTB audit completed

The operator ran `scripts/audit-a733-mmc-dtb.py` against the A/B-identical staged vendor 6.6.98 DTB and hybrid 0.2.7 DTB. The upstream binding patch `0005-dt-bindings-mmc-a733-d1-fallback.patch` passed `git apply --check` in the combined clean source (the check emitted no errors), and the read-only MMC DTB audit completed.

**Observed configurations are identical in both vendor and hybrid DTBs:**

| Controller | Address | Legacy compatible | status | legacy erase property |
| --- | --- | --- | --- | --- |
| MMC0 (SD) | `0x04020000` | `allwinner,sunxi-mmc-v5p3x` | okay | absent |
| MMC1 (SDIO) | `0x04021000` | `allwinner,sunxi-mmc-v5p3x` | okay | absent |
| MMC2 | `0x04022000` | `allwinner,sunxi-mmc-v4p6x` | okay | **present** |
| MMC3 | `0x04023000` | `allwinner,sunxi-mmc-v5p6x` | disabled | **present** |

These MMC node definitions are inherited from vendor and are not supported as-is by the upstream `sunxi-mmc` compatible table. They are not evidence of the underlying physical MMC0 failing.

**Exact regulator phandles for MMC0 (both binaries):**
- `vmmc-supply`, `vqmmc33sw-supply`, `vdmmc33sw-supply` each resolve to **AXP8191 DC1SW2** (`/soc@3000000/twi@7083000/pmu@36/regulators@0/dc1sw2`).
- `vqmmc18sw-supply` and `vdmmc18sw-supply` resolve to **AXP8191 CLDO5** (`/soc@3000000/twi@7083000/pmu@36/regulators@0/cldo5`).
- The above are *vendor DTS wiring references*, not verified output voltages. In particular, a label with `33` or `18` does not electrically verify 3.3 V or 1.8 V on the board.
- MMC1 and MMC2 report no `*-supply` properties in this audit. This is not proof of an absent physical supply; it flags missing upstream regulator description or different hardware/firmware wiring.

### Near-term boot-minimal policy

1. **MMC0 only:** express hardware-backed `compatible = "allwinner,sun60i-a733-mmc", "allwinner,sun20i-d1-mmc";` in a new upstream board DTS, after inspecting exact A733 module clock, reset, IRQ, pinmux and supplies. The binding patch is source-only and does not make the existing compiled vendor/hybrid DTB upstream compatible.
2. **No extra hosts:** keep MMC1 for Wi-Fi after SD root is proven, disable MMC2 unless an actual boot/media requirement is established, retain MMC3 disabled. This is a deliberate *new minimal DTB* policy, not permission to edit the known-good vendor DTB.
3. **Never delete supplies to force probe:** identify and build minimum upstream regulator driver(s) for AXP8191/DC1SW2/CLDO5 and confirm their voltage-selection semantics, especially MMC0 PF bank. `vqmmc33sw-supply`, `vdmmc33sw-supply`, `vqmmc18sw-supply`, `vdmmc18sw-supply` are vendor properties: do not assume the upstream driver consumes them.
4. **Separate collision:** legacy `mmc-high-capacity-erase-size` is present on MMC2/3, not MMC0. The original 6.18 vendor CAP2 bit-9/UHS-II failure remains proof of bad vendor driver ABI, not evidence of an upstream MMC0 defect.
5. **No electrical edits:** the new MMC0 DTS must pass regulator phandle and 1.8/3.3V safety review before power switching is allowed. Do not invent vqmmc supply selection or hardcode a rail voltage.

Next: verify AXP8191 register/supply bindings and upstream MFD/regulator source support, then build a canonical MMC0-only Zero 3W DTS. The clean 4,429,832-byte upstream ARM64 Image is a compile baseline, not a bootable image.
