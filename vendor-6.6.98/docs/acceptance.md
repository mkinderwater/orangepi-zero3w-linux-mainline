# Hardware acceptance, 6.6.98

| Scenario | Stock 6.6.98 | F1 vendor kernel/hybrid DTB | New control | New identity |
|---|---|---|---|---|
| Actual 6.6.98 kernel, login | PASS | PASS | PENDING | PENDING |
| SD ext4 mount | PASS | PASS | PENDING | PENDING |
| First boot resize | PASS | PASS | PENDING | PENDING |
| Board RAM detection | PASS | PASS | PENDING | PENDING |
| Onboard Wi-Fi/SSH | PASS | not yet established | PENDING | PENDING |
| USB-C Ethernet/SSH | not yet established | PASS | PENDING | PENDING |
| Linux HDMI console | PASS | FAIL | PENDING | PENDING |
| AXP8191/MMC | PASS | PASS | PENDING | PENDING |
| AXP515 | unknown | ERROR | PENDING | PENDING |
| Validated UART | unknown | unknown | PENDING | PENDING |
| Reboot and shutdown | unknown | unknown | PENDING | PENDING |

Do not infer boot failure from a frozen splash or LED state. Onboard RTC-less systems, timestamps are not reliable before clock sync. Capture `uname -a`, `/proc/cmdline`, `/sys/firmware/fdt`, `dmesg`, network, SD, UART and HDMI observations, source/config/DTB/image hashes. Preserve original firmware and image controls.

One change per experiment; test two independent hypotheses per batch. A compiler PASS is not a hardware PASS.
