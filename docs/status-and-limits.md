# Evidence and limits (2026-11-14)

| Item | Observed evidence | What it does not prove |
| --- | --- | --- |
| Kernel and DTB | M2ca and M2cb ran successfully; `KERNEL=0`, `DTB=0` in M2cb | Any hardware boot |
| Board device tree | MMC0 at 0x04020000, PF0-PF5, PF6 active-low card detect, R-I2C0 pinmux PL0/PL1, PMIC at I2C 0x36 | Correct voltage startup, SD boot |
| M2r AXP8191 | DCDC1, CLDO5, DC1SW2 provider and built-in kernel source | No unwanted writes during regulator registration |
| M2cb AXP8191 write table | 0x10, 0x11, 0x12, 0x21, 0x33 only | Read-only behavior (those registers remain writable) |
| HDMI/DE352 | Audit and component builds | KMS/scanout, EDID or HPD working |
| PowerVR | Kernel config and vendor compute success in separate build | Upstream stock Mesa acceleration on 6.18 |
| 0.7.6 image | boot script and boot allocation audit inspected | Booting 6.18 with same bootloader |

## Hardware safety

Vendor MMC0 uses DC1SW2 (DCDC1 parent) and CLDO5 for a separate 1.8 V path. The experimental DTS exposes only the conservative 3.3 V MMC supply at <=25 MHz; it does not establish voltage-switching support. `regulator-always-on` does not imply that regulator registration cannot change rail state.

## Code provenance

The included PMIC patch is a captured local diff. The included DTS depends on A733 labels in the local common DTS. The full set of dependencies is not bundled. Device-tree and driver compilation occurred on the developer WSL host; this starter archive has not reproduced those builds in an independent clean kernel checkout.

Do not bundle proprietary GPU/NPU blobs, complete vendor kernel source, raw recovery card images or captured hardware bundles without a license review.
