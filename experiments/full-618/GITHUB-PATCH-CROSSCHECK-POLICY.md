# Mandatory GitHub patch cross-check for A733 / Zero 3W integration

**Applies to:** every new or modified source file, DTS/DTB, kernel option, build script, boot script, patch, configuration, or image assembly step on `work/linux-6.18-full-integration`.

## Rule

**Research before changing; reconcile before building; verify after changing.**

For each proposed change, identify the **specific subsystem and exact file/function/binding**. Search the corresponding upstream and vendor **GitHub source, commits, branches, PRs, issues and patch collections**, then compare actual code, not just repository descriptions. Do not treat a README claim, a similar SoC, or a successful compile as evidence of hardware compatibility. GitHub search must include related board implementations where appropriate, but prioritize the exact A733 and Zero 3W hardware.

### Relevant comparison repositories (starting points, not an exhaustive whitelist)

| Area | Required starting points |
|---|---|
| A733 Linux kernel, DTS and clocks | [torvalds/linux](https://github.com/torvalds/linux); [orangepi-xunlong/orangepi-build](https://github.com/orangepi-xunlong/orangepi-build); [jonas5/Allwinner-A733-kernel](https://github.com/jonas5/Allwinner-A733-kernel) |
| Vendor kernel BSP and display drivers | [alexcaoys/allwinner-bsp](https://github.com/alexcaoys/allwinner-bsp) (pin exact used commit), plus locally recorded `6.6.98-sun60iw2` source provenance |
| U-Boot/boot chain | [u-boot/u-boot](https://github.com/u-boot/u-boot); [orangepi-xunlong/u-boot-orangepi](https://github.com/orangepi-xunlong/u-boot-orangepi) `v2018.05-sun60iw2`; [dlan17/u-boot](https://github.com/dlan17/u-boot) A733 branch |
| Zero 3W board-specific Linux and DT | [nickyg666/orangepi-zero3w-mainline](https://github.com/nickyg666/orangepi-zero3w-mainline); [aricshow/orangepi-zero3w-armbian-cyberdeck-mods](https://github.com/aricshow/orangepi-zero3w-armbian-cyberdeck-mods) |
| A733 display / firmware alternatives | [vehoelite/edk2-a733](https://github.com/vehoelite/edk2-a733); [jonas5/Allwinner-A733-kernel](https://github.com/jonas5/Allwinner-A733-kernel) |
| A523/H616/H618 related code | Relevant upstream commits and board ports **only where register/binding equivalence is validated**; do not transfer code blindly |

Add other repositories and patch series when the precise file or feature warrants it. Check mailing-list patch submissions and Patchwork in addition to GitHub for upstream changes that have **not yet landed on GitHub**. Linux 7.x/7.4 A733 CCU and A733 U-Boot patch series are especially relevant to the present bring-up.

### Per-change gate

1. **Scope**: list exact target file(s), functions, compatible strings, clock/reset IDs, register locations and affected image contents.
2. **Source revision**: record local git commit and target kernel/U-Boot release. Do not equate vendor U-Boot 2018.07 installed binary to a different 2018.05 public tree.
3. **GitHub search**: check exact file/function/symbol in current upstream, vendor, A733-specific fork, and relevant board ports. Inspect matching commit history and open/merged PRs; search exact error text when applicable.
4. **External patch queue**: check LKML/U-Boot mailing lists, Patchwork, and unresolved vN patch series for fixes not yet in a repository. Record *date and revision*.
5. **Comparison**: document same/different register offset, bit position, clock parent, compatible, ABI, binding, function semantics, conditionals, prerequisites and affected users.
6. **Status**: classify each candidate as `APPLIED`, `ALREADY_PRESENT`, `NOT_APPLICABLE`, `SUPERSEDED`, `NEEDS_PORT`, `CONFLICTING`, or `UNVERIFIED`. Never mark a patch applied solely because similar code exists.
7. **Provenance**: include stable GitHub commit/PR links, source tag or SHA, concrete changed lines and rationale. Distinguish source claims from hardware evidence.
8. **Safety**: verify minimal diffs, dependency ordering, source hashes and regression tests. Preserve known-good images and firmware; new output paths only.
9. **Post-change recheck**: compare updated file to upstream and local earlier fixes to ensure a later patch didn't regress or overwrite them.
10. **Release gate**: no integration build or image promotion until all consequential `NEEDS_PORT`/`CONFLICTING`/`UNVERIFIED` items are acknowledged, with an explicit test/rollback plan.

If GitHub or mailing-list access is unavailable, mark the cross-check **BLOCKED**, record precisely what was inaccessible, and do not represent the work as fully patch-audited.

## Required record, per change

Create or update one record (copy this table for each change):

| Field | Entry |
|---|---|
| Change ID and exact local path/function | |
| Target branch, commit, kernel/toolchain | |
| Function and hardware dependency | |
| Relevant GitHub upstream/vendor/board repositories checked | |
| Commit/PR/issues/patch-series URLs with dates and revisions | |
| Existing local patch(es) and their SHA(s) | |
| Source differences, clock/reset/power/ABI compatibility | |
| Decision for each candidate patch | |
| Chosen change and why | |
| Tests, affected images, rollback | |
| Unresolved issues / cross-check status | |

Save these under `experiments/full-618/patch-crosschecks/`, using a filename keyed to the **change**, not a broad undocumented catchall. Update before editing the target file and after tests.

## Immediate application

Before the next integrated DTB and 6.18 build, cross-check at least:
- PCK600 clock-gating and power-domain handling
- A733 video/DE PLL, HDMI SFR/CEC and TCON clock bindings against current upstream patch series
- DE352 and TCON3 / HDMI PHY display graph, endpoints, reset mappings, PMIC rails
- IOMMU v20 vendor driver and any upstream replacement
- AXP8191/SDMMC/PMIC clock and regulator patch series
- U-Boot HDMI pre-prompt initialization and FDT mutation handling
- 26 MHz oscillator modeling, IRQ/pinctrl fixes, UART and kernel console handoff

An inventory of files or a source grep is not an adequate substitute for the per-change patch review.

**Standing rule:** Do not skip this gate for small edits, scripts or renamed symbols. Record `NOT APPLICABLE` only with a reason.
