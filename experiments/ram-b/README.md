# RAM-B: Stable A733 Linux 6.18 baseline

Date: 2026-11-17. **Status: PLAN / SOURCE AUDIT ONLY. NOT BUILT. NOT HARDWARE TESTED.**

## Goal

Establish one reproducible, last-known-good (LKG) **RAM-only** Linux 6.18.19 boot for the Orange Pi Zero 3W (Allwinner A733): stable 115200 8N1 serial TX/RX, no unexpected reset, reliable initramfs prompt, verified firmware handoff and 24-hour continuous uptime. The long-term project is a native-C, unattended, 24/7 microphone, local classification/Whisper and web-status appliance. RAM-B is the prerequisite, not the final application.

## What is proven

- Vendor 6.6.98 reference boots.
- Vendor Boot0/U-Boot runs, reads SD and reaches `booti`.
- RAM-A Linux `6.18.19+` reaches eight CPUs and native `ttyS0` registration, but its serial output later corrupts and Boot0 starts again. Reset cause unknown.
- Suspected 26 MHz DCXO / 24 MHz software mis-model is a **hypothesis**, not a validated electrical fact.
- RTC/CCU must be audited against hardware. No automatic 26 MHz substitution.
- MMC `no support for card's volts` is independent work, paused until RAM-B clocks and stable UART are proven.

## LKG preservation rules

1. Never alter the existing original RAM-A `Image`, DTB, initramfs, stage2 script, stock Boot0/U-Boot, vendor recovery media, or their only copies.
2. Preserve the entire *dirty* RAM-A source state, **including untracked files**, before any clean-tree reset or patch removal. `git diff HEAD` alone is insufficient.
3. Keep existing SD image read-only for auditing. Use a separate test image/card for RAM-B.
4. Audit actual `boot.scr` and `stage2.scr`, addresses, payload sizes, `booti` parameters and reserved-memory regions against a single manifest.
5. Stage2 currently reloads the DTB; any RAM-only DT modifications must follow the last DTB load. Do not `saveenv`.
6. Prefer upstream 6.18.19 plus a **minimal reviewed and documented A733 patch series**. Do not copy over all uncommitted changes.
7. Treat UART corruption and subsequent reboot as separate symptoms until a common root cause is observed.

## Acceptance gates

| Gate | Requirement |
|---|---|
| Source | Pinned commit, clean build worktree, reviewed patches, .config, reproducible image hash |
| Boot | Original firmware prefix verified, no load/script overlap, correct DTB handoff |
| CPU | Eight CPUs, GIC/timers, no panic/oops |
| UART | Clean native ttyS0 TX/RX, 115200 8N1, stable shell, no keep_bootcon in normal test |
| Clock | Verify actual DCXO/RTC/PLL_REF and APB-UART parent/divisor, not guessed |
| Reset | Determine whether hardware reset, software reboot, watchdog or other cause |
| Runtime | Ten cold boots, ten warm boots and at least 24h uptime without unexplained reset |
| Evidence | Console logs, checksums, exact commands and conditions recorded |
| Promotion | Only label LKG after all gates pass on board |

## Isolated experiment matrix

- **B0 audit**: Collect source provenance and boot media manifest without modifying known-good artifacts.
- **B1A**: Same RAM-A image/DTB/initramfs, boot arguments without `keep_bootcon` (one-variable comparison).
- **B1B**: Reviewed RTC/DCXO/PLL reference correction; only after actual clock-tree path and source register semantics checked.
- **B2**: Clean rebuilt kernel with minimum verified A733 support; separate artifact, not automatically promoted.
- **B3**: If spontaneous reset persists, inspect watchdog, firmware handoff and ramoops validity without mixing with UART modifications.
- **B4**: Repeated boots and 24h stability.

Never change two independent variables *in one variant*. Evaluate two variants in parallel against the same unchanged control.

## Operator first step

Run `bash scripts/ram-b-source-audit.sh` from this repository clone as root on the Debian build host. It writes metadata under `/root/opi3w-m2-work/ram-b-audit`, not to the tracked repository or source tree. Review the report and ensure untracked changes are preserved before constructing new worktrees.

## Existing evidence

- [2026-11-15 boot chain](../../docs/2026-11-15-boot-chain.md)
- [2026-11-15 hardware matrix](../../docs/2026-11-15-hardware-matrix.md)
- [Clock reference](../../docs/2026-11-15-clock-frequency-reference.md)
- [MMC experimental PR #2](https://github.com/mkinderwater/orangepi-zero3w-linux-mainline/pull/2)
- User-supplied November 17 native UART diagnostic logs in conversation uploads; full raw captures must be archived separately with hashes and sanitized before public upload.

## Status ledger

| Date | Event | Result |
|---|---|---|
| 2026-11-17 | RAM-B work branch created | Source audit pending; no build or hardware test |
