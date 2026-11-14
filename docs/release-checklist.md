# Before tagging 0.1.0

- [ ] Run `scripts/export-from-wsl.sh` and inspect all generated sources and diffs.
- [ ] Reconstruct a **complete, ordered, self-contained** Linux 6.18.19 kernel patch series from the correct upstream base, including A733 SoC prerequisites.
- [ ] Remove hard-coded `/root/...` paths and any copied vendor source from publication patches.
- [ ] Check code provenance, licensing and third-party notices.
- [ ] Record the exact kernel commit, compiler version, configuration and reproducible commands.
- [ ] Rebuild kernel and DTB in a clean checkout; publish logs and sha256 evidence.
- [ ] Check that PMIC regulator initialization cannot accidentally change critical rails before a hardware boot.
- [ ] Build a 6.18.19-specific initramfs and modules, with an independent test image and the existing boot normalization.
- [ ] Do not claim Linux 6.18 boots or HDMI/PowerVR works without physical evidence.

First commit can be labeled `experimental bring-up notes` before all checks pass. A versioned release should state its verification scope explicitly.
