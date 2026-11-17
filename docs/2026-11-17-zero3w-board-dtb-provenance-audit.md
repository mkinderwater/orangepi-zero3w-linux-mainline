# Zero 3W 0.2.7 board DTS provenance and enabled-device review

**Evidence:** Operator WSL output on 2026-11-17, actual hybrid 0.2.7 `board/` paths and SHA256 of DTB.
**Status:** static board-definition review only. Do not remove/disable device nodes on this evidence alone.
**Purpose:** separate confirmed physical Zero 3W hardware from enabled vendor reference nodes and make upstream-compatible, maintainable DTS.

## Proven source chain and identity

- Hybrid board top-level DTS: `/root/opi3w-hybrid-build-0.2.7/board/sun60i-a733-orangepi-zero3w.dts` includes `zero3w-vendor-board.dtsi`.
- Vendor-derived include: `/root/opi3w-hybrid-build-0.2.7/board/zero3w-vendor-board.dtsi` (must capture full source and hash; operator grep excerpt alone is not a complete file).
- Pinned vendor reference DTS: `/root/opi3w-hybrid-sources-0.1.0/zero3w-vendor-reference/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts`.
- Preprocessed hybrid: `/root/opi3w-hybrid-build-0.2.7/audit/sun60i-a733-orangepi-zero3w.preprocessed.dts`.
- Audit DTB and installed-stage DTB **identical** SHA256 `5c9cd102215183cc56150aab2ce331216bea26d80741cdfc1fb0d95f5818e7b9`.
- No `.*.dtb.cmd` for this board in `build/`; the only result was `drivers/of/.empty_root.dtb.cmd`. The top-level `board/` source is not in the main kernel source tree. The grep for build-script references was empty. **Compiler invocation and include path remain untraced**; hash equality does not prove a clean-source reconstruction.

The top-level DTS overrides root:
```dts
compatible = "xunlong,orangepi-zero3w", "allwinner,sun60i-a733";
```
where the included vendor board DTSI originally defines `"xunlong,orangepi-4-pro", "arm,sun60iw2p1"`. The override **discards `arm,sun60iw2p1`**, required by imported BSP HDMI platform detection (F1 vendor kernel with hybrid DTB failed HDMI match). This is a **known source compatibility deficiency**. Proposed correction retains board identity and adds the necessary SoC fallback in one explicit, separately tested board DTS change; it is not an MMC or boot-entry fix.

Top-level DTS sets `serial0`, `mmc0`, `mmc1`, `mmc2` aliases, `stdout-path`, `earlycon`, deletes initrd-start/end (bootloader supplies them), explicitly enables UART0 `allwinner,uart-v100`, drops UART DMA. Do **not** reinsert PB9/PB10 pinmux guesses: the source comments explain the vendor UART pins are empty and PB9/PB10 belong to TWI8.

## Potentially overenabled nodes to verify on real Zero 3W hardware

These items are **enabled in the pasted vendor DTSI or referenced by it**, not proven absent from the board. Check the complete compiled DTB, schematic/BOM and trusted vendor working DTB before modifications.

| Node/function | Source evidence | Classification |
| --- | --- | --- |
| MMC0 SD, MMC1 Wi-Fi SDIO, MMC2 optional eMMC | enabled `sdc0/sdc1/sdc2`; MMC0 supplies DC1SW2/CLDO5 | Essential boot/storage paths; validate physical MMC2 population, not blanket-disable |
| AXP8191 and AXP515 | `x-powers,axp8191`, `x-powers,axp515` both enabled | Keep and validate PMIC/regulator probe, don't guess voltages |
| USB-C role/CC | `fcs,fusb302`, `usb-c-connector`, vbus-supply | Critical if populated; check FUSB302 presence, Type-C IRQ and role switching |
| PWM fan | `compatible = "pwm-fan"`, `fan-supply=<&reg_dc1sw2>`, status okay | May be reference-board only, unverified |
| GT9271 touchscreen | `goodix,gt9271` on enabled TWI12 | May be unpopulated, unverified |
| Display DP/eDP/panels | enabled `allwinner,drm-dp`; disabled panel subtrees and HDMI supply refs | Verify actual Zero 3W connectors and optional display modules |
| PCIe and supply rails | PCIe node enabled, AXP8191 `pcie1v8`/`pcie3v3` supplies | Need board routing and reset proof |
| Camera/VIN | several sensor nodes marked okay with empty supplies or reset properties | Likely inherited reference nodes; verify before enabling or deleting |
| Video capture NPU/GPU | node and regulator bindings present | Keep kernel capability without implying an unpopulated board peripheral or tested feature |
| I2S/I2C/SPI/PWM/GMAC | mix of enabled/disabled nodes | Distinguish SoC controllers from physically fitted consumers; don't delete controllers just because no fitted peripheral |
| Audio | I2S3 and card may be enabled | Confirm populated codec, I2S pins, regulator and actual analog outputs |
| HYM8563 RTC | enabled node; older tests reported timeouts | Verify component and board clock dependency; not automatically a real RTC |

**Discipline:** `status="okay"` in a source node describes **a request to probe**, not proof that the physical component is fitted or working. Do not infer a phantom board or alter power rails without schematic/physical and vendor runtime evidence.

## DTB cleanup and upstream direction

1. Capture the complete `board/sun60i-a733-orangepi-zero3w.dts`, `board/zero3w-vendor-board.dtsi` and their SHA256, plus generated preprocessed DTS and exact build command/tool versions. Store owned source in Git with explicit provenance; avoid copying large vendor blobs into the public repository without confirming reuse/redistribution rights.
2. Compare *compiled* hybrid DTB with the working stock vendor DTB by canonical node path and property, classify additions, deletions, changed compatible/status/interrupt/clock/reset/regulator/pinctrl and `power-source`. An unfiltered `grep` is a triage view, **not** a complete DTB delta.
3. Apply the first board patch only after finding original `arm,sun60iw2p1` fallback in vendor HDMI matching. Board identity fix must not change other node statuses or regulators.
4. Audit active MMC2 legacy `mmc-high-capacity-erase-size` against the imported `AW_MMC` bit-9 collision. Source driver correction is **separate** from board DTS. Do not disable MMC2 or legitimate eMMC capability as a workaround.
5. Audit PF pin voltage control and effective states against working 6.6 kernel/DTB. No guess-based 1.8/3.3V rail writes.
6. Assign each active child node to `board-fitted`, `connector-exposed`, `SoC-internal`, `optional-overlay`, or `unverified`. These are engineering categories, not automatic DTS patches.
7. Create a canonical Zero 3W board DTS with only verified hardware enabled by default; optional connector accessories handled through documented overlays. Keep one versioned DTB paired with kernel ABI and test in real hardware.
8. Audit all DT warnings against binding schemas and SoC hardware, keeping exact warnings and conclusions. Build complete source and DTB through reproducible scripts from a pinned tree.

## Minimal WSL evidence requests

```bash
K=/root/opi3w-hybrid-build-0.2.7
sha256sum "$K/board/sun60i-a733-orangepi-zero3w.dts" \
  "$K/board/zero3w-vendor-board.dtsi" \
  "$K/audit/sun60i-a733-orangepi-zero3w.preprocessed.dts"

# Inspect build provenance and the original vendor board include relation:
find "$K" -maxdepth 3 -type f \( -name '*.sh' -o -name '*.py' \) \
  -print | sort
head -45 "$K/board/zero3w-vendor-board.dtsi"
find /root/opi3w-hybrid-sources-0.1.0/zero3w-vendor-reference \
  -name '*.dts' -o -name '*.dtsi' | head -50
```

To move from triage to a full property-by-property diff, provide the **complete original vendor DTB**, **complete hybrid DTB** and their exact source hashes, not only selected grep results.

**Next gate:** provenance and compatibility review before any board-component pruning or a move to `MMC_SUNXI`. The 6.18 kernel already reached PID1, so no new early bootloader experiment is justified by these DTB questions.
