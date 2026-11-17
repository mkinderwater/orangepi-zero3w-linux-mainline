# Full compiled DTB comparison: vendor 6.6.98 versus hybrid 6.18.19

**Status:** Comparator and synthetic tests committed; no vendor DTB from WSL has been supplied or physically tested in this commit.

This is the next step after identifying hybrid board source at:

- /root/opi3w-hybrid-build-0.2.7/board/sun60i-a733-orangepi-zero3w.dts
- /root/opi3w-hybrid-build-0.2.7/board/zero3w-vendor-board.dtsi
- /root/opi3w-hybrid-build-0.2.7/stage/boot/sun60i-a733-orangepi-zero3w.dtb
- /root/opi3w-hybrid-sources-0.1.0/zero3w-vendor-reference/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w.dts

The hybrid audit and staged DTBs have matching SHA256 **5c9cd102215183cc56150aab2ce331216bea26d80741cdfc1fb0d95f5818e7b9**. The root board DTS overwrote an included vendor fallback compatible, losing **arm,sun60iw2p1**, known necessary for the imported BSP HDMI platform selector. The vendor-derived DTSI contains many enabled reference-design nodes; presence in DTS does not confirm a fitted device.

## How to run

1. Fetch tests and run the synthetic parser/structure tests:

    cd /root/orangepi-zero3w-linux-mainline
    git pull --ff-only
    python3 -m unittest discover -s tests -p 'test_compare_zero3w_dtbs.py' -v

2. Identify the **actual compiled vendor Zero 3W DTB**. It must come from the original working 6.6.98 image or a verified vendor build. Do not substitute the text vendor DTS as a compiled DTB or choose a Cubie/Orange Pi 4 Pro DTB. To locate candidates:

    find /root/opi3w-hybrid-sources-0.1.0 /root/opi3w-m2-work /root/opi3w-vendor-booti-0.1.0 \
      -type f -name 'sun60i-a733-orangepi-zero3w.dtb' -print 2>/dev/null

   A filename alone does not prove origin. Confirm it was extracted from a known-good stock image/boot mount, and record the SHA256. If there is no such file, extract it from the stock vendor image read-only before running the comparison. Do not compare against an unspecified file.

3. With a verified vendor DTB path:

    VENDOR_DTB=/absolute/path/to/verified-stock-6.6.98-zero3w.dtb
    HYBRID_DTB=/root/opi3w-hybrid-build-0.2.7/stage/boot/sun60i-a733-orangepi-zero3w.dtb

    sha256sum "$VENDOR_DTB" "$HYBRID_DTB"

    python3 scripts/compare-zero3w-dtbs.py \
      --vendor "$VENDOR_DTB" \
      --hybrid "$HYBRID_DTB" \
      --output /root/opi3w-m2-work/618-vendor-hybrid-dtb-diff-v1

    cat /root/opi3w-m2-work/618-vendor-hybrid-dtb-diff-v1/dtb-diff.md

The tool parses raw FDT nodes and properties rather than grepping decompiled text. It writes both JSON with exact raw property bytes and a prioritized Markdown report. It **does not** interpret numeric phandles into meaning: phandle IDs can legitimately differ across DTBs even if target devices are equivalent. The report must be read with that limitation. It also records the reservation table. It refuses to overwrite an existing report directory and modifies neither input.

## Required triage before editing the DTS

- **P0:** MMC0/1/2/3, capability flags, supply phandles, 1.8/3.3V pin states, PF bank, AXP8191/AXP515, pinctrl revision, R-TWI, CCU, CPU interrupt controller and secure-memory.
- **P1:** HDMI, DE, TCON, GPU, PHY, display connectors, USB-C FUSB302, Wi-Fi, PCIe and clocks/resets.
- **P2:** on-board or externally exposed SPI/PWM/I2S/I2C, RTC, touchscreens, cameras, audio and optional sensors.

Do not remove a DTS node purely because a hardware population cannot be confirmed, and do not infer that two DTBs' different phandle numbers represent different supplies. Build a per-node classification of **present and required**, **exposed as optional**, **SoC-internal**, **vendor-driver-only binding**, **unverified**, or **not fitted (independently verified)**.

## Follow-on upgrade architecture

Correct the board root fallback to include the BSP's verified SoC compatibility while retaining Zero 3W identity, but run it as an isolated DTB-only test. Fix MMC CAP2 BIT(9) in the vendor driver separately. Test AW_MMC and upstream MMC_SUNXI as competing permanent architectures, not by changing arbitrary compatible properties on an already-failing image. Preserve a known-good vendor image, and keep building toward Debian ARM64 with versioned kernel/DTB/modules packages rather than SD-image-only releases.

**Acceptance:** the next phase is reviewed raw DTB delta plus a provenance record of both source files and compiled DTBs. There has been no 6.18 root mount or validated PF voltage correction; avoid claiming stable Linux until those gates pass.
