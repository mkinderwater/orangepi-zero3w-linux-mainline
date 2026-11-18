#!/usr/bin/env bash
# RAM-B read-only baseline inventory. Does not reset source, modify firmware or build.
set -euo pipefail
SRC="${SRC:-/root/opi3w-m2-work/a733-try9-ramoops-v2}"
OUT="${OUT:-/root/opi3w-m2-work/ram-b-audit}"
K="$SRC/linux"
OBJ="$SRC/obj"
[[ -d "$K/.git" || -f "$K/.git" ]] || { echo "Missing Git worktree: $K" >&2; exit 1; }
[[ -f "$OBJ/.config" && -f "$OBJ/arch/arm64/boot/Image" ]] || { echo "Missing RAM-A build artifacts" >&2; exit 1; }
mkdir -p "$OUT"
date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT/audit-utc.txt"
git -C "$K" rev-parse HEAD > "$OUT/base-commit.txt"
git -C "$K" status --porcelain=v1 -uall > "$OUT/source-status.txt"
git -C "$K" diff --binary HEAD > "$OUT/tracked-working-tree.patch"
git -C "$K" diff --cached --binary > "$OUT/staged-changes.patch"
git -C "$K" ls-files --others --exclude-standard -z > "$OUT/untracked-paths.nul"
# Archive untracked files; preserve binary blobs and spaces in filenames.
# Git archive alone does not include dirty/untracked files.
if [[ -s "$OUT/untracked-paths.nul" ]]; then
    tar --null -C "$K" --files-from="$OUT/untracked-paths.nul" -cf "$OUT/untracked-files.tar"
else
    : > "$OUT/no-untracked-files.txt"
fi
cp "$OBJ/.config" "$OUT/ram-a.config"
sha256sum "$OBJ/.config" "$OBJ/arch/arm64/boot/Image" > "$OUT/ram-a-sha256.txt"
stat -c '%s %y %n' "$OBJ/.config" "$OBJ/arch/arm64/boot/Image" > "$OUT/build-artifact-stats.txt"
git -C "$K" diff --name-only HEAD > "$OUT/changed-tracked-paths.txt"
(
  echo "Kernel source: $K"
  echo "Object directory: $OBJ"
  echo "Git upstream base: $(git -C "$K" rev-parse HEAD)"
  echo "Kernel version: $(make -s -C "$K" kernelversion)"
  echo "Audit files:"
  ls -lh "$OUT"
) > "$OUT/SUMMARY.txt"
echo "Audit saved to $OUT"
echo "WARNING: do not reset or clean RAM-A. Review source-status.txt and untracked-files.tar."
