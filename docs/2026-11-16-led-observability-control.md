# Zero 3W vendor LED baseline

Vendor 6.6.98 PID1 probe is hardware-proven: HDMI shows START, UNAME 6.6.98-sun60iw2, HOLD, and periodic ALIVE through 33 seconds.
Vendor DTS maps active-high red LED to PL7, /leds/led-0, heartbeat default. Hybrid 6.18 driver and pinctrl remain unverified.

On a normally booted vendor 6.6.98 OS (not PID1-only image):

    bash diagnostics/vendor-led-test.sh --inventory

Choose the reported exact LED name. Then:

    sudo bash diagnostics/vendor-led-test.sh --blink EXACT_LED_NAME

Blink test flashes three times and restores trigger. Record whether physical LED follows those pulses.
Do not guess MMIO addresses, PMIC commands or sysfs LED names. Do not conflate LED status with kernel entry.

After vendor mapping is confirmed, validate that the hybrid 6.18 kernel and DTB implement the corresponding LED subsystem before modifying PID1. No 6.18 LED evidence yet.