# Orange Pi Zero 3W Linux mainline: November 14, 2026 evidence update

This is an **additive** documentation update for [orangepi-zero3w-linux-mainline](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline). Copy `docs/` and `evidence/` into that repository and add the linked README status paragraph manually. **No claim is made that Linux 6.18.19 has booted.**

## Hardware-tested control

The separately assembled M2cm **UNARMED** image, derived from the 0.7.6 Debian 13 release, booted on a physical Orange Pi Zero 3W on 2026-11-14. The boot ran vendor Linux `6.6.98-sun60iw2`, displayed a working HDMI login console, connected to Wi-Fi and accepted SSH login. Observed command results: `uname -r` -> `6.6.98-sun60iw2`, `systemctl is-active ssh` -> `active`, `wlan0` -> `192.168.24.122/24` (temporary DHCP address). **Neither the mainline kernel, mainline display nor PowerVR on mainline is hardware-validated.**

The default boot remains the vendor boot. The 6.18 experimental branch requires `/boot/mainline/armed`; it was not activated in the reported test. The vendor fallback was not tested after an experimental crash. Do not describe the marker as a reliable one-shot or automatic rollback.

## Current artifact evidence

- M2cg: vendor-compatible legacy header packaging succeeds, but alternative Zero 3W work reports that `bootm` rejects a conventional ARM64 `uImage` header, and instead uses `booti` with a raw `Image`. Header matching is not a boot test.
- M2ch: all 1,426 modules staged for `6.18.19-00022-g908869c38e30-dirty`; MMC, EXT4 and AXP framework options are built in. WSL module install initially failed due to `INSTALL_MOD_STRIP=0`, fixed by using an empty variable.
- M2ci: direct-root boot script and a separate large matching initramfs candidate created. Neither path hardware-tested.
- M2cl: unarmed dual-path 2 GiB image assembled with original vendor boot area, layout, UUID, module tree and new experimental files; mounted-ext4 normalization and fsck passed.
- M2cm: added a systemd userspace marker for experimental kernel; 11 source-presence/consistency checks passed. The marker cannot diagnose failures before systemd. UNARMED hardware boot completed on vendor branch.

See `docs/` for exact addresses, known failure modes, HDMI vendor baseline and staged release requirements.

## Publication policy

No vendor proprietary driver source, firmware, binary hardware bundles, SSH private keys, host credentials, full raw SD images or unreviewed third-party code are included. The `evidence` files are edited summaries, not the full private system logs. The root UUID and local IP do not need to be reproduced in published documentation. Do not tag the project as a bootable Linux 6.18.19 release.
