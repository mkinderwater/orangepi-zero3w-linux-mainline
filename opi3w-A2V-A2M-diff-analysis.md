# A2V versus A2M: extracted boot-script analysis

**Evidence:** `opi3w-A2V-vs-A2M-bootdiff.tar.gz` provided by operator. A2V was reported to boot vendor Linux 6.6.98. A2M was reported to remain at the Orange Pi bootloader splash. No live U-Boot console transcript was supplied.

## Extraction note

The uploaded `dumpimage -T script -p 0` output carries **eight leading non-text bytes** (`00 00 0a 06 00 00 00 00` in A2V, `00 00 04 ea 00 00 00 00` in A2M). This is why the original `diff` produced only “Binary files ... differ”. The accompanying readable diff removes only those eight bytes from each *extracted diagnostic copy*; it does not modify either bootable image.

## Confirmed source differences

| Aspect | A2V: physically booting | A2M: visually failing | Consequence |
| --- | --- | --- | --- |
| Boot environment | Imports `/boot/orangepiEnv.txt` with `env import -t`; preserves existing `rootdev` | Skips import; forcibly derives `root=PARTUUID` | Root, console, board settings may differ |
| Boot arguments | Dynamic vendor command line including `clk_ignore_unused`, `swiotlb=65536`, optional extras and cgroups, serial/tty1 | Static short line, `console=ttyS0,115200n8 console=tty0 loglevel=7` | Multiple runtime changes, not an isolated handoff |
| Load addresses | Uses the vendor U-Boot `kernel_addr_r`, `fdt_addr_r`, `ramdisk_addr_r` environment | Overrides to `0x41000000`, `0x44000000`, `0x45000000` | Changes load and potential relocation ranges |
| Load order | Vendor loads initrd, kernel, DTB | A2M loads kernel, DTB, initrd | Changes state and final `filesize`; not known to be causal |
| DTB setup | `fdt addr ${fdt_addr_r}` then `fdt resize 65536`, followed by optional overlays | No explicit `fdt addr`, `fdt resize`, or overlay loop | Removes DTB preparation and any configured overlays; FDT may differ |
| Paths | `/boot/uInitrd`, `/boot/uImage`, `/boot/dtb/${fdtfile}` via `${prefix}` | Copies under `/boot/mainline/vendor-a2m/` | Loaded *bytes* must be checked, not merely filenames |
| Device selection | Uses `${devtype} ${devnum}` selected by bootloader | Hardcodes `mmc 0:1` | Could select the wrong device in some boot conditions |
| Failure handling | Runs `bootm` and returns to caller if it returns | Infinite loop after `bootm` returns, and after any failed load | An A2M hang may be deliberate script behavior, not a kernel crash |

## What this establishes

- A2V booting proves that the two-stage mechanism works when the original vendor script is preserved.
- A2M failing does **not** isolate the difference to `bootm`, a kernel defect, or a filesystem defect.
- The actual A2M failing branch is unknown without U-Boot console or persistent pre-handoff markers. In particular, A2M deliberately loops forever if PARTUUID lookup or any `ext4load` fails.
- `fdt addr` / `fdt resize`, environment import, addresses and bootargs are concrete differences; **none is proven causal**.

## Recommended controlled experiment

Use a **copy of the successful A2V image** for each test; retain untouched vendor Boot0/U-Boot, 6.6.98 kernel, original DTB, original uInitrd, original boot file layout and the first-stage script. Before changes, export the *compiled* scripts and compare SHA256 of actual loaded kernel, initrd and DTB files.

1. **S1: FDT test.** Retain vendor script and remove or disable only `fdt addr` / `fdt resize` (not the overlay policy, addresses or command line). This tests whether these calls are necessary in this configuration. Be aware an implicit U-Boot FDT setting may still exist; record both commands' return codes.
2. **S2: Environment test.** Retain vendor script and omit only `orangepiEnv.txt` import, preserving the rest verbatim. Compare effective `bootargs` and `fdtfile` before handoff. Ensure the script doesn't unintentionally load a missing DTB or root identifier.

If both pass, test address overrides and simplified `bootargs` in separate steps. For every experiment record script byte hash, loaded artifact hashes, final command line, the observed result, and any marker proving the reached boot stage. Do not infer kernel execution from a stationary splash.

**Kernel 6.18.19 HDMI build:** Keep the 0.2.7 compiled baseline unchanged until the vendor script variations are isolated. Once vendor controls are understood, substitute a matched 6.18 boot set into a vendor-derived boot procedure with raw `Image` / `booti` and no untested bootloader fallback.
