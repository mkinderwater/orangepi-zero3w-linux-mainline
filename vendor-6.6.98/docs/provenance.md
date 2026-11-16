# Vendor 6.6.98 source provenance and defects

Kernel source: https://github.com/orangepi-xunlong/linux-orangepi/tree/2ac08e8c7cdc28abbdc5c9a9dd812f887ae9c79f

Build definitions: https://github.com/orangepi-xunlong/orangepi-build/tree/7f24222b928eab94780f2af03289ce527e07241e

Zero 3W board config selects `sun60iw2`, `linux-sun60iw2-current-a733` and `sun60i-a733-orangepi-zero3w.dtb`. Kernel Makefile is `VERSION=6 PATCHLEVEL=6 SUBLEVEL=98`.

Official Zero 3W DTS contains an inconsistent board identifier: `xunlong,orangepi-4-pro`. Retain `arm,sun60iw2p1`; vendor HDMI `sunxi_hdmi_init()` matches it through `hdmi_plat_match`. Earlier hybrid 0.2.7 DTS removed the fallback and F1 HDMI core initialization failed with `check point match is err or null`, followed by DRM bind failure.

Other confirmed F1 observations: AXP8191 successfully registers, MMC mounts root, AXP515 probe errors, DDR clock warning, RTC I2C timeout. None should be changed without isolated hardware validation.

The original vendor OS image, F1 image, running DTB and logs are control evidence; compute their SHA256 where available. This repository does not redistribute large or vendor firmware binaries. The original image source commit is not proven byte-identical to the shipped image; compare build outputs before asserting reproduction.
