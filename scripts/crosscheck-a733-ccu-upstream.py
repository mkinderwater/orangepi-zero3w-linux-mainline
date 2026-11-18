#!/usr/bin/env python3
"""Offline read-only A733 Linux 6.18 vs accepted upstream CCU v7 source comparison."""
import argparse, difflib, hashlib, subprocess
from pathlib import Path
COMMITS = [
("39e4303e8bbc","bindings"), ("b213bddd53ab","SDM"),
("2a5ae6df088b","PRCM"), ("93c637ce9f0a","PLL"),
("103168ac6eec","bus clocks"), ("4646c19620e6","module clocks"),
("ed757071ac3d","gates"), ("308e4087bbda","resets")]
FILES = [
"drivers/clk/sunxi-ng/ccu-sun60i-a733.c",
"drivers/clk/sunxi-ng/ccu-sun60i-a733-r.c",
"drivers/clk/sunxi-ng/ccu-sdm.c",
"drivers/clk/sunxi-ng/ccu-sdm.h",
"include/dt-bindings/clock/allwinner,sun60i-a733-ccu.h",
"include/dt-bindings/clock/allwinner,sun60i-a733-r-ccu.h",
"include/dt-bindings/reset/allwinner,sun60i-a733-ccu.h",
"include/dt-bindings/reset/allwinner,sun60i-a733-r-ccu.h"]
KEYS=("hdmi","tcon","de_","pll_ref","pll-ref","video","sdm","mbus","pck","reset")
def git(repo,*args):
    return subprocess.run(["git","-C",str(repo),*args],capture_output=True,text=True)
def sha(data):return hashlib.sha256(data).hexdigest()[:16]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--local",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/linux"))
    ap.add_argument("--upstream",type=Path,required=True)
    ap.add_argument("--out",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/ccu-v7-crosscheck"))
    a=ap.parse_args()
    if a.out.exists():raise SystemExit("STOP: output directory already exists")
    if not (a.local/"Makefile").is_file() or not (a.upstream/".git").exists():
        raise SystemExit("STOP: both Linux checkouts required")
    head=git(a.upstream,"rev-parse","HEAD")
    if head.returncode:raise SystemExit("STOP: invalid upstream")
    for c,name in COMMITS:
        if git(a.upstream,"rev-parse","--verify",c+"^{commit}").returncode:
            raise SystemExit("STOP: missing upstream commit "+c)
        if git(a.upstream,"merge-base","--is-ancestor",c,"HEAD").returncode:
            raise SystemExit("STOP: upstream HEAD does not contain "+c)
    a.out.mkdir(parents=True)
    report=["# A733 CCU upstream cross-check",
      "Accepted into sunxi/clk-for-7.5 on 2026-11-15.",
      "https://lists.openwall.net/linux-kernel/2026/11/15/635",
      "No source or image modified.",
      "Local: "+str(a.local),"Upstream HEAD: "+head.stdout.strip(),
      "## Applied upstream series"]
    for c,name in COMMITS:
        report.append("- "+name+": https://git.kernel.org/sunxi/linux/c/"+c)
    report+=["","## Exact source comparison",
       "| Path | 6.18 SHA prefix | Upstream SHA prefix | Result |",
       "|---|---|---|---|"]
    for i,rel in enumerate(FILES):
        l=a.local/rel;u=a.upstream/rel
        if not (l.is_file() and u.is_file()):
            report.append("| "+rel+" | "+("present" if l.is_file() else "missing")+" | "+("present" if u.is_file() else "missing")+" | BLOCKED |")
            continue
        lb=l.read_bytes(); ub=u.read_bytes()
        if lb==ub:
            report.append("| "+rel+" | "+sha(lb)+" | "+sha(ub)+" | IDENTICAL |")
            continue
        diff=list(difflib.unified_diff(lb.decode(errors="replace").splitlines(),
                       ub.decode(errors="replace").splitlines(),
                       fromfile="local/"+rel,tofile="accepted-v7/"+rel,lineterm=""))
        name=f"{i:02d}-"+Path(rel).name+".diff"
        (a.out/name).write_text("\n".join(diff)+"\n")
        report.append("| "+rel+" | "+sha(lb)+" | "+sha(ub)+" | REVIEW "+name+" |")
        keylines=[v[:180] for v in diff if v.startswith(("+","-")) and
                  not v.startswith(("+++","---")) and any(k in v.lower() for k in KEYS)]
        report.extend("  - "+x for x in keylines[:25])
        if len(keylines)>25:report.append("  - additional keyword edits: "+str(len(keylines)-25))
    report+=["","## Manual gate",
      "- Review every changed CCU parent, mux, divider, reset and gate register.",
      "- Reconcile 26 MHz pll-ref logic and HDMI CEC/SFR/TCON against hardware-proven code.",
      "- Do not blindly copy new Linux bindings or overwrite a validated PCK600 implementation.",
      "- Classify each difference as ALREADY_PRESENT, NEEDS_PORT, NOT_APPLICABLE or UNVERIFIED.",
      "- No kernel build or flash promotion until this review is complete."]
    (a.out/"summary.md").write_text("\n".join(report)+"\n")
    print("DONE:",a.out/"summary.md")
if __name__=="__main__": main()
