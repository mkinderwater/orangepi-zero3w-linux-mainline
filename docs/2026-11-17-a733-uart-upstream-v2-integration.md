# A733 upstream serial v2: native UART takeover fix trial

## Evidence

The proven RAM-A board image boots Linux 6.18.19+, recognizes 1 GiB at 0x40000000 with BL31 16MiB no-map, brings up all eight CPUs, loads initramfs, probes both A733 CCUs. UART output corrupts immediately when `8250_dw` binds to `2500000.serial` and changes the native console. `base_baud=1384615` is an observation, **not evidence of the root cause**. Linux PID1 is still unverified.

## Verified upstream candidate

Vinicius Pedrosa's **v2 4/4**, October 19, 2026:
https://patchwork.armbian.eu/project/patchwork/cover/cover.1792439398.git.vinicius.eduardo.pedrosa@gmail.com/

1. Preserve BUSY-safe divisor hook when DLF exists
2. Only accept contiguous DLF readback; A733 RS485 register at 0xc0 reads 0x19f
3. Add A733-specific DT compatible
4. Attach existing SKIP_SET_RATE quirk to `allwinner,sun60i-a733-uart`

This was developed for A733 termios/console corruption and is substantially closer to our symptom than changing the 24 MHz oscillator or removing UART0. It may still not solve **first console takeover**: the reported author testing concerns termios changes during traffic. Preserve the baseline.

## Prepare a controlled upstream-patch build

The user must supply the *actual kernel source that produced RAM-A*, with preexisting A733 clock/pinctrl adaptations. Do **not** use an untouched 6.18 release or the separate DTS-v3 intake tree unless they are confirmed to contain every existing kernel patch.

```bash
cd /root/orangepi-zero3w-linux-mainline
git pull --ff-only
python3 scripts/stage-a733-uart-v2.py \
  --source /PATH/TO/ACTUAL/RAM-A/6.18-PREPARED-SOURCE \
  --config /root/opi3w-m2-work/a733-clean-uart-gate-v1/obj/.config \
  --build --jobs 4 \
  --output /root/opi3w-m2-work/a733-uart-v2-try1
```

The script fetches **exact v2 message ID** by `b4`, validates all four subjects and changed file paths, checks/apply patches one by one in a fresh **source copy**, confirms A733 `SKIP_SET_RATE` match, rebuilds Image separately from the proven config, and writes a report with SHA256. It neither alters the proven source nor writes an SD card. Any compile or patch conflict is a hard failure, not permission to modify source blind.

A compiled `Image` is **not** yet a boot image. After build, compare its config and Image, then create a fresh copy of the **working RAM-A SD image** and replace only `/mainline/Image` in its FAT partition, preserving the RAM-A DTB, initramfs and firmware. One variable: kernel UART changes. Validate FAT readback SHA256 and name the copy distinctly before flashing. Do not source old `boot.scr` with inherited USB environment: `devtype=mmc`, `devnum=0:2`, `prefix=/` at U-Boot prompt.

## Acceptance

- Image links, native UART0 (not disabled) matches A733-specific compatible.
- Native console emits readable output at 115200 through `2500000.serial: ttyS0`.
- A733 all eight CPUs + 1 GiB still pass.
- Diagnostic initrd runs `/init`; input works after handoff. Repeated termios transitions can be tested after a shell is available.
- If still corrupt: do not adjust clocks randomly; capture serial raw bytes and check UART clock from clock provider, divisor, pinctrl and DT overlay.
