#!/usr/bin/env python3
"""Read-only source audit for hybrid 0.2.7. Writes to Windows Downloads."""
from pathlib import Path
import difflib
import hashlib
import json
import os
import subprocess
import sys

BASE=Path(os.getenv("OPI_BASE","/root/opi3w-hybrid-sources-0.1.0/linux"))
HYBRID=Path(os.getenv("OPI_HYBRID","/root/opi3w-hybrid-build-0.2.7/linux"))
BSP=Path(os.getenv("OPI_BSP","/root/opi3w-hybrid-sources-0.1.0/allwinner-bsp"))
OUT=Path(os.getenv("OPI_OUT","/mnt/c/Users/mkinderwater/Downloads/opi3w-hybrid-027-source-audit"))
PINS={str(BASE):"4aea1dc4cad17cd146072e13b1fd404f32b8b3ef",
      str(BSP):"656a550c826787e7e72fae58ca793df9e0988ac8"}
def status(msg):
    raise SystemExit("STOP: "+msg)
for p in (BASE,HYBRID,BSP):
    if not p.is_dir(): status("missing "+str(p))
for p,pin in PINS.items():
    got=subprocess.check_output(["git","-C",p,"rev-parse","HEAD"],text=True).strip()
    if got!=pin: status("unexpected pinned revision at "+p+": "+got)

def inventory(root,ignored):
    found={}
    for d,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=sorted(x for x in dirs if x not in ignored)
        for name in sorted(files):
            p=Path(d)/name
            rel=p.relative_to(root).as_posix()
            if p.is_symlink():
                found[rel]={"kind":"symlink","target":os.readlink(p)}
            elif p.is_file():
                h=hashlib.sha256()
                with p.open("rb") as f:
                    for block in iter(lambda:f.read(1024*1024),b""):
                        h.update(block)
                found[rel]={"kind":"file","bytes":p.stat().st_size,"sha256":h.hexdigest()}
    return found
def delta(a,b):
    return {
      "added":sorted(set(b)-set(a)),
      "missing":sorted(set(a)-set(b)),
      "changed":sorted(p for p in set(a)&set(b) if a[p]!=b[p])
    }

top=delta(inventory(BASE,{".git"}),inventory(HYBRID,{".git","bsp"}))
bsp=delta(inventory(BSP,{".git"}),inventory(HYBRID/"bsp",{".git"}))
OUT.mkdir(parents=True,exist_ok=True)
patch=""
for name in ("Kbuild","Kconfig"):
    if name in top["changed"]:
        before=(BASE/name).read_text(errors="replace").splitlines(keepends=True)
        after=(HYBRID/name).read_text(errors="replace").splitlines(keepends=True)
        patch+="".join(difflib.unified_diff(before,after,fromfile="a/"+name,tofile="b/"+name))
(OUT/"hybrid-top-level.patch").write_text(patch)
(OUT/"bsp-differences.txt").write_text(
    "CHANGED\n"+"\n".join(bsp["changed"])+"\n\nADDED\n"+
    "\n".join(bsp["added"])+"\n\nMISSING\n"+"\n".join(bsp["missing"])+"\n")
result={
  "state":"OFFLINE_SOURCE_AUDIT_NOT_BUILD_REPRODUCTION",
  "pins":PINS,
  "top_level":top,
  "bsp":bsp,
  "note":"This does not reconstruct the original transform script, kernel config, modules, initramfs, or image assembler."
}
(OUT/"audit.json").write_text(json.dumps(result,indent=2)+"\n")
(OUT/"summary.md").write_text(
    "# Hybrid 0.2.7 source comparison\n\n"+
    "Top-level: "+str(len(top["changed"]))+" changed, "+str(len(top["added"]))+
    " added, "+str(len(top["missing"]))+" missing\n\n"+
    "Imported BSP: "+str(len(bsp["changed"]))+" changed, "+str(len(bsp["added"]))+
    " added, "+str(len(bsp["missing"]))+" missing\n\n"+
    "Modified Linux files: "+", ".join(top["changed"])+"\n\n"+
    "Review third-party licensing and secrets before publishing generated patches.\n")
print((OUT/"summary.md").read_text())
print("SOURCE_AUDIT_COMPLETE_NOT_REPRODUCED:",OUT)
