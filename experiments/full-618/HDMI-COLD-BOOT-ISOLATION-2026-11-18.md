# A733 HDMI cold-boot isolation: U-Boot pre-kernel display setup

Date: 2026-11-18. Board: Orange Pi Zero 3W (Allwinner A733). Status: **Test 1 pending**.

## Proven observations

- Linux 6.18 HDMI/PCK600 kernel boots to the `PCK600-RAM-SHELL` BusyBox prompt with HDMI disconnected at power-on.
- PCK600 power controller and DE_SYS, VO, VO1 register successfully; observed uptime 13m23s.
- Linux BusyBox shell remains responsive when HDMI is plugged or unplugged **after** Linux boots.
- With HDMI connected **before power-on**, the exact same kernel/DTB/initramfs loads through U-Boot `booti` and BL31 reports Linux address `0x41000000`, but no Linux UART output follows.
- Vendor U-Boot contains its own display/HDMI initialization, before the user-selectable `boot.scr`. Our RAM-only DTB **does not** contain the Linux HDMI graph. Changing boot scripts alone does not disable U-Boot's earlier HDMI initialization.

## Identical artifacts for tests

FAT image: `opi3w-618-pck600-ram-shell.img`, derived from `opi3w-618-pck600-fat-probe.img`.

Linux Image SHA256 `9f8c4af6f7f3d5ff604aac29bd7553e04dc3a41c0c8a5000308594c49ab5cb1c`.
PCK600 DTB SHA256 `c5cc45413f4be4efbf80a1c26c061462e2a9b2e3649a49bf055b008d5209f697`.

Use the **same physical microSD**, UART 115200 8N1, power supply and monitor for all variants. Do not run `saveenv` or issue raw register writes.

## Test 1: HDMI added at U-Boot prompt, before Linux

1. Power off fully. Unplug HDMI, leave UART and microSD attached.
2. Apply power; **interrupt U-Boot autoboot** to get its `=>` prompt. Confirm console responds to `mmc dev 0`.
3. **Connect the HDMI cable now**, while still at `=>`. Note whether the UART remains usable and whether U-Boot prints HDMI-related messages. The monitor may be blank; it is not expected to show Linux output.
4. Run the *identical manual launch*:

```text
mmc dev 0
setenv devtype mmc
setenv devnum 0:2
setenv prefix /
fatload mmc 0:2 0x46000000 /mainline/stage2.scr
source 0x46000000
```

5. Capture entire UART log after `source`. Require `PCK600-RAM-SHELL: /init entered` and an interactive shell, or record where output stops. At the shell, run `/bin/busybox uptime`.

**Meaning:** If Test 1 works while prior HDMI-before-power-on fails, the display init path *before* this U-Boot prompt is implicated more strongly than HDMI merely being connected when Linux begins. If Test 1 also fails, an HDMI connection by kernel handoff is sufficient to reproduce failure, but whether it is electrical/clock/firmware needs more isolation.

## Test 2: Leave HDMI unplugged through boot (control)

Power off, remove HDMI, reboot the **same card** without other changes, then run the same manual launch. Confirm Linux RAM-shell and PCK600 probes. This is the original positive control.

## Test 3: HDMI connected before power-on (existing reproducible failure)

Power off, connect HDMI **before power-on**, then run the same manual launch. Record firmware log, `BL3-1` handoff and presence/absence of Linux printk. Repeat only after Test 1 if another run is useful.

## Follow-up only after Test 1

If Test 1 PASS and Test 3 FAIL, compare U-Boot **pre-prompt** HDMI state and possible display/PHY clocks, FDT mutation and power rail initialization. Prefer firmware-provided options to disable U-Boot splash/HDMI; their existence and support must be verified in vendor U-Boot source before trying them. An environment variable in a *second-stage boot script* cannot disable init already executed before the script.

This test changes **no code or image** and does not establish HDMI scanout. Avoid making another Linux kernel build before determining the result.

## Test 1 operator result: PASS

Hardware result reported 2026-11-18: with HDMI **disconnected at power-on**, the operator interrupted autoboot at U-Boot, connected HDMI **at the U-Boot prompt**, then launched the same PCK600 RAM-shell image. Linux 6.18 reached userspace successfully:

```text
Freeing unused kernel memory: 320K
Run /init as init process
PCK600-RAM-SHELL: /init entered
PCK600-RAM-SHELL: no MMC/PMIC root discovery
PCK600-RAM-SHELL: interactive BusyBox follows
BusyBox v1.37.0 ... built-in shell (ash)
sh: can't access tty; job control turned off
```

Compare with previously reported HDMI-connected-**before-power-on** boot on same image: boot loader loads kernel/DTB/initramfs and stops producing UART messages after `BL3-1: Next image spsr = 0x3c5`. With HDMI disconnected throughout, Linux boots and the A733 PCK600 provider binds to DE_SYS, VO and VO1. With HDMI connected/disconnected **after Linux boot**, BusyBox remains responsive.

**Interpretation:** The key differentiator is whether HDMI is connected during the *early pre-prompt firmware initialization*. Merely having the cable attached at U-Boot handoff is not sufficient to cause the silence under this tested sequence. A vendor pre-prompt HDMI clock/display setup or firmware state transition is a leading hypothesis, NOT yet proven causal. The console still prints duplicate lines under `keep_bootcon`; that is a separate issue.

**Next engineering actions:** Preserve this exact test matrix; inspect vendor U-Boot HDMI initialization timing, setup and disable interfaces in the actual source before selecting a no-display firmware-init diagnostic. Avoid speculative U-Boot variables or raw clock/PHY writes. Then verify whether an early firmware-only display disable leaves Linux UART functioning while HDMI is connected at power-on. Finally enable Linux DE/TCON/HDMI graph after firmware conflict is resolved.
