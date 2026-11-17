# A733 / Orange Pi Zero 3W: MMC OCR diagnosis

Date: 2026-11-17. Workstream version: 0.1.0. Status: **source experiment, not compiled or tested**.

## Scope

Linux 6.18.19+ RAM-A diagnostic baseline, vendor Boot0/U-Boot retained. Kernel from the on-card FAT partition `/mainline/Image`, DTB `/mainline/sun60i-a733-orangepi-zero3w.dtb`, and initramfs `/mainline/uart-diagnostic-initrd.gz`. Kernel loads at 0x41000000, DTB at 0x44000000 and initramfs at 0x45000000. Stage2 reloads the DTB, therefore RAM-only FDT changes must be applied **after loading**, immediately before manual `booti`.

## Physical evidence

- U-Boot `mmc 0` identifies SD card GE8QT, 238.5 GiB, four-bit, 50 MHz, SD High Speed.
- On-card DOS partitions: FAT32 partition 2 starts at LBA 65536 and occupies 131072 sectors; Linux type 83 partition 1 starts at LBA 196608 and occupies 3997696 sectors.
- Base Linux DTB has `/soc/mmc@4020000` disabled. RAM-only enable, 4-bit, 25 MHz allows the driver to probe.
- Linux logs: `sunxi-mmc 4020000.mmc: initialized`; `supply vcc-pf not found, using dummy regulator`; `no support for card's volts`; `mmc0: error -22 whilst initialising SD card`.
- A second RAM-only DT test adds `voltage-ranges = <3300 3400>` and `no-1-8-v`. Error remains unchanged.
- Early `-517` deferred probes resolve later. UART output corrupts and subsequent Boot0 startup is observed; cause of restart is unproven.

## Experiment matrix

| ID | Description | Status |
|---|---|---|
| RAM-A | Known Linux 6.18.19+ RAM diagnostic | Known kernel entry and driver probe |
| DT-A | Enable MMC0, four-bit, 25 MHz | Driver probes; voltage error |
| DT-B | DT-A + voltage-ranges and no-1-8-v | Same voltage error |
| OCR-A | Instrument core card/host OCR overlap and host setup | **Not built** |
| OCR-B | OCR-A plus conditional device-tree OCR path | **Not built; hold until helper API and 6.18 source semantics are verified** |

## Source patcher

`apply.py` modifies `drivers/mmc/core/core.c` and `drivers/mmc/host/sunxi-mmc.c` in a supplied Linux 6.18 tree. A and B require **separate clean trees**. It expects exact source anchors and aborts if absent; this is *not* an all-or-nothing filesystem transaction. Preserve source in version control or a separate source copy.

Run on build host (substitute real paths):

```sh
python3 apply.py /path/to/linux-mmc-A --variant A
```

Do not apply OCR-B until its `mmc_of_parse_voltage` call is verified against the exact kernel headers and the successful build tree. The expected helper signature must not be assumed; a compile failure is not a valid electrical test. B is *not* a proven regulator fix.

The important OCR-A output is `A733-OCR-DIAG select: card=... host=... overlap=...`. Record the exact masks. A host mask that appears zero or incompatible requires source/regulator investigation, not blind insertion of bits.

## Acceptance gates

1. Reproducible build with recorded source SHA, `.config` and compiler.
2. MMC controller probes and SD card enumerates.
3. Partitions appear without transfer errors.
4. Read-only filesystem mount and known-file hash comparison pass.
5. Later, write-test a disposable partition, unmount/remount and verify after cold reboot.
6. Only then attempt persistent ext4 root.

**Do not overwrite the original SD bootloader, stage2 script or RAM diagnostic Image. No writes to card during OCR tests.**
