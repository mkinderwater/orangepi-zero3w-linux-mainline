#!/usr/bin/env python3
"""Fail-closed validation of isolated A733 PCK-600 candidate DTB.

Compare flattened DT structure with the SHA-known baseline. The only allowed
addition is /soc@0/pck-600@7060000 and its subtree. Existing nodes/properties
must be byte-for-byte equivalent after parsing. No hardware writes.
"""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess

BASE_HASH="1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d"
CAND_HASH="c5cc45413f4be4efbf80a1c26c061462e2a9b2e3649a49bf055b008d5209f697"
ROOT="/soc@0/pck-600@7060000"
EXPECTED_CHILDREN={
    ROOT,
    ROOT+"/power-controller",
    ROOT+"/power-controller/pd_de_sys@1",
    ROOT+"/power-controller/pd_vo@9",
    ROOT+"/power-controller/pd_vo1@a",
}

def dtc_bytes(path):
    return subprocess.check_output(["dtc","-q","-I","dtb","-O","dts",str(path)],stderr=subprocess.PIPE).decode(errors="replace")

def parse(text):
    stack=[]
    nodes={}
    current=None
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith("//") or line.startswith("/*") or line.startswith("*"): continue
        if line.endswith("{"):
            label=line[:-1].strip()
            stack.append(label)
            current="/"+"/".join(part for part in stack if part!="/")
            nodes[current]={}
        elif line in ("};","}"):
            if stack:stack.pop()
            current="/"+"/".join(part for part in stack if part!="/")
        elif current and line.endswith(";"):
            key=line.split("=",1)[0].strip().rstrip(";")
            nodes[current][key]=line
        elif current:
            # Continuation line can occur on dtc output. Append to last property.
            if not nodes[current]:raise ValueError("Unrecognized DTS continuation: "+line)
            key=next(reversed(nodes[current]))
            nodes[current][key]+=" "+line
    return nodes

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--baseline",type=Path,default=Path("/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb"))
    ap.add_argument("--candidate",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/ram-b-26mhz-pck600-probe.dtb"))
    a=ap.parse_args()
    for p in (a.baseline,a.candidate):
        if not p.is_file(): ap.error("Missing DTB "+str(p))
    hs=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (a.baseline,a.candidate)]
    if hs[0]!=BASE_HASH:ap.error("Wrong baseline hash: "+hs[0])
    if hs[1]!=CAND_HASH:ap.error("Candidate hash changed; review needed: "+hs[1])
    base=parse(dtc_bytes(a.baseline))
    cand=parse(dtc_bytes(a.candidate))
    removed=set(base)-set(cand)
    additions=set(cand)-set(base)
    changed={key for key in base.keys() & cand.keys() if base[key]!=cand[key]}
    if removed or changed or additions != EXPECTED_CHILDREN:
        print("Removed nodes:",sorted(removed))
        print("Changed nodes:",sorted(changed))
        print("Added nodes:",sorted(additions))
        raise SystemExit("STOP: DTB diff differs from the five expected nodes.")
    parent=cand[ROOT]
    pd=cand[ROOT+"/power-controller"]
    if "allwinner,sun60iw2-pck" not in parent.get("compatible",""):
        raise SystemExit("STOP: parent compatible absent")
    if "0x7060000" not in parent.get("reg","").lower() or "0xb000" not in parent.get("reg","").lower():
        raise SystemExit("STOP: parent MMIO region incorrect")
    if "allwinner,sun60iw2-pck-600" not in pd.get("compatible",""):
        raise SystemExit("STOP: power controller compatible incorrect")
    nums=[int(x,16) for x in re.findall(r"0x[0-9a-f]+",pd.get("clocks","").lower())]
    if nums!=[8,18]:raise SystemExit("STOP: wrong clock provider or ID "+repr(nums))
    expected={1,9,10}
    actual=set()
    for path in additions:
        if "/pd_" not in path:continue
        values=[int(x,16) for x in re.findall(r"0x[0-9a-f]+",cand[path].get("reg","").lower())]
        if len(values)!=1:raise SystemExit("STOP: invalid domain reg "+path)
        actual.add(values[0])
    if actual!=expected:raise SystemExit("STOP: domain IDs mismatched: "+repr(actual))
    print("PASS: baseline SHA256 correct")
    print("PASS: candidate SHA256 correct")
    print("PASS: no baseline nodes or properties changed")
    print("PASS: exactly five intended nodes added")
    print("PASS: parent MMIO 0x7060000/0xb000")
    print("PASS: modern R-CCU phandle 8, CLK_BUS_R_PPU 18")
    print("PASS: domains 1, 9 and 10 only")
    print("Structural validation only. Hardware behavior remains UNTESTED.")

if __name__=="__main__":main()
