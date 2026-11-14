# M2cn evidence and publication boundaries

The included evidence is traceable to `opi3w-m2cn-results.tar.gz` captured on 2026-11-14. No vendor hardware bundle, bootloader binary, raw image, proprietary graphics module, or copied vendor driver code is included.

| Included file | Purpose |
| --- | --- |
| `evidence/m2cn/exit-code.txt` | Script exit status |
| `evidence/m2cn/source-commit.txt` | Exact input commit |
| `evidence/m2cn/source-gates.txt` | Source and config checks |
| `evidence/m2cn/isolated-artifacts.sha256` | Output checksums |
| `evidence/m2cn/original-git-status.txt` | Original worktree changes |
| `evidence/m2cn/held-for-review.txt` | Entries excluded by reconstruction |
| `evidence/m2cn/copied-untracked.txt` | Untracked source candidates included in reconstruction |
| `evidence/m2cn/run.log` | Build workflow summary |
| `evidence/m2cn/STATUS.txt` | Limitations from the test |

The original raw diff and full kernel build log are intentionally omitted from this commit pending provenance review. This publication reports a successful reconstruction audit, not a clean independently reproducible source release.
