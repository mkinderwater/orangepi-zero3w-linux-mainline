# LED-backed PID1 experiment: vendor first, then Linux 6.18

Status: source committed; no newly compiled or flashed image has been verified.

## Verified prerequisites

- Physical Zero 3W running vendor Linux 6.6.98: status_led sysfs three-flash test passed twice; DT GPIO cells <0x35 0 7 0> map active-high PL7; heartbeat trigger.
- Compiled hybrid 0.2.7 DTB contains led-0 with label status_led, gpio-leds, PL7 active-high and heartbeat.
- Compiled Linux 6.18.19 config has LEDS_CLASS=y, LEDS_GPIO=y, GPIOLIB=y, OF_GPIO=y, AW_PINCTRL_SUN60IW2_R=y. This is not proof of runtime LED registration.
- Previous vendor PID1 console probe reached /init on physical board and printed 6.6.98, START, HOLD and ALIVE.

## Probe semantics

PID1 mounts devtmpfs and sysfs without mounting or scanning storage, waits up to 15 seconds for /sys/class/leds/status_led, selects LED trigger none, then gives three 250-ms flashes separated by 250-ms gaps. It keeps PID1 alive, prints ALIVE, and emits one 250-ms pulse approximately every 10 seconds. Missing pulses can mean driver/pinctrl/LED registration failure rather than failed kernel entry. A pulse is evidence of PID1 only when the correct image was flashed and its kernel identified.

## Build

Use new paths, not the old PID1 probe directory and output images:

    cd /root/orangepi-zero3w-linux-mainline
    git pull --ff-only
    bash diagnostics/build-pid1-probe.sh /root/opi3w-m2-work/618-pid1-led-v1
    cd /root/opi3w-m2-work/618-pid1-led-v1 && sha256sum -c SHA256SUMS

## Test 1: vendor 6.6.98 control

    cd /root/orangepi-zero3w-linux-mainline
    python3 diagnostics/build-vbi-pid1-control.py \
      --source /root/opi3w-vendor-booti-0.1.0/opi3w-VBI-vendor-A2V-booti.img \
      --probe /root/opi3w-m2-work/618-pid1-led-v1/pid1-probe-initramfs.cpio.gz \
      --wbuild-scripts /root/opi-3w-wbuild/scripts \
      --output /root/opi3w-m2-work/opi3w-VBI-PID1-LED-v1.img

Verify the SHA256 and independently audit finished image versus VBI. Only the referenced initramfs may change. Flash a spare card. Vendor test PASS requires photo/video of three start flashes followed by individual ALIVE pulses and console output if visible.

## Test 2: 6.18 hybrid

Only after vendor LED probe proves the pattern, build from the pinned original HBI-027 using the same LED probe and normalization:

    python3 diagnostics/build-hbi-pid1-image.py \
      --source /root/opi3w-HBI-027-vendor-VBI-booti.img \
      --probe /root/opi3w-m2-work/618-pid1-led-v1/pid1-probe-initramfs.cpio.gz \
      --wbuild-scripts /root/opi-3w-wbuild/scripts \
      --output /root/opi3w-m2-work/opi3w-HBI-027-PID1-LED-v1.img

Again independently audit and verify the finished SD image. Three pulses would be positive PID1 evidence under 6.18 when flashed artifact/kernel identity is controlled. No pulses and a frozen splash remain inconclusive. Do not diagnose Linux 6.18 as not entering solely from no LED or HDMI.

Neither test boots Debian, mounts the SD root or activates the NIC. Do not expect SSH or link lights.
## Hardware observation, November 16, 2026

**Vendor 6.6.98 LED PID1 probe: HW PASS (operator-reported, photograph).** HDMI shows `OPI3W_PID1: START`, `UNAME Linux 6.6.98-sun60iw2 aarch64`, `LED_READY status_led: 3 short PID1 flashes`, `HOLD`, and repeating `ALIVE` messages through at least 25 seconds. Operator reports both LED flashing and HDMI worked. This validates the probe and vendor LED output, **not** 6.18 PID1 execution. Do not assume a static photo measures exact LED timing; the three flashes are operator-observed.

Next: create the HBI-derived 6.18 PID1 LED image using the same probe archive and pinned normalizer. Verify image checksum and independently audit the final image before physical testing. Missing LED/HDMI output under 6.18 is inconclusive until driver registration or earlier kernel entry is independently observed.

## Linux 6.18 LED-v1: first-boot versus later power cycles, November 16

**Hardware observation, operator-reported. Not yet explained; investigation intentionally deferred.**

The HBI-027-derived Linux 6.18 PID1 LED-v1 image consistently showed the Orange Pi "initializing boot loader" splash, without the expected three PID1 flashes or confirmed Linux 6.18 output. The attached USB NIC had no link/activity; the PID1-only probe does not initialize networking, so that observation is not a kernel-entry test.

The operator reflashed the test image three times and noted a repeatable distinction:

| State | Recorded LED behaviour | HDMI |
| --- | --- | --- |
| Immediately after rewriting/flashing the image, first power-on | LED initially solid, flashes once at the bootloader splash, then returns to solid | "Initializing boot loader" persists |
| Subsequent power cycles without reflashing | LED initially solid, flashes once at the splash, then turns off and stays off | Same splash persists |
| Complete disconnection of power, HDMI, USB peripherals, followed by reconnection | Blink, then off | Same splash persists |
| Next ordinary power cycle after complete disconnection | Blink, then off | Same splash persists |

This is **not** the three-short-flash PID1 checkpoint. A single LED blink may originate in firmware, GPIO setup, or another boot stage; it does not prove Linux kernel or PID1 execution. Full disconnection did not restore the first-flash solid state, making a simple residual-power explanation less compelling, but the result does not prove storage writes or rule out other causes.

**Unverified hypotheses:** persistent SD changes during first boot; different ext4 metadata or physical allocation; boot-stage state or timing; LED ownership/driver initialization. No raw postboot SD comparison or kernel-stage instrumentation has identified a cause. Earlier PID1-DIAG vs PID1-NORMALIZED hole tests found **zero sparse boot files in both** and identical file-size/first-hole profiles; this excludes observed sparse holes in those two filesystems, not physical extent differences and not the new LED-v1 firstboot effect.

**Decision:** preserve this observation and the original images. **Defer** firstboot-state/root-cause work and avoid further reflash/PMIC/LED experiments solely to explain it. Proceed with Linux 6.18 kernel-entry diagnosis using independently verified signals, without interpreting an off LED or retained splash as proof of failure.
