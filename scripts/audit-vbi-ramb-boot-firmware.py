#!/usr/bin/env python3
"""Read-only VBI and RAM-B boot firmware comparison, excluding MBR table.

The first 512 bytes contain MBR partition metadata. Differences there do
not establish Boot0 changes. Compare [512,32MiB) separately and report
first differing offsets and the region in which they occur.
"""
import argparse
import hashlib
from pathlib import Path
import struct

MiB=1024*1024
def sha_range(file,start,end):
    h=hashlib.sha256()
    with file.open("rb") as f:
        f.seek(start)
        remaining=end-start
        while remaining:
            data=f.read(min(1024*1024,remaining))
            if not data:raise EOFError(file)
            h.update(data)
            remaining-=len(data)
    return h.hexdigest()

def differences(left,right,start,end,cap=12):
    results=[]
    with left.open("rb") as a, right.open("rb") as b:
        a.seek(start);b.seek(start);cursor=start
        while cursor<end:
            n=min(1024*1024,end-cursor)
            x=a.read(n);y=b.read(n)
            if len(x)!=n or len(y)!=n:raise EOFError("Unexpected short input")
            if x!=y:
                for i,(v,w) in enumerate(zip(x,y)):
                    if v!=w:
                        results.append((cursor+i,v,w))
                        if len(results)>=cap:return results
            cursor+=n
    return results

def partitions(path):
    with path.open("rb") as f:
        f.seek(446)
        data=f.read(66)
    if data[-2:]!=b"\x55\xaa":raise ValueError("Invalid MBR signature")
    out=[]
    for i in range(4):
        e=data[i*16:(i+1)*16]
        ptype=e[4]
        if ptype:
            start,length=struct.unpack_from("<II",e,8)
            out.append((i+1,hex(ptype),start,length))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vbi",type=Path,default=Path("/home/opi3w-VBI-vendor-A2V-booti.img"))
    ap.add_argument("--ramb",type=Path,default=Path("/root/opi3w-m2-work/a733-ram-ab-v1/a733-clean-uart-ram-b-v1.img"))
    ap.add_argument("--out",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/VBI-RAMB-FIRMWARE-AUDIT.txt"))
    a=ap.parse_args()
    for file in (a.vbi,a.ramb):
        if not file.is_file() or file.stat().st_size<32*MiB:
            ap.error(f"Missing or undersized image: {file}")
    regions=[
        ("MBR boot code / disk signature",0,446),
        ("MBR partition entries and signature",446,512),
        ("post-MBR gap",512,8*1024),
        ("early firmware from 8KiB to 1MiB",8*1024,MiB),
        ("firmware from 1MiB to 32MiB",MiB,32*MiB),
        ("entire reserved first 32MiB excluding MBR",512,32*MiB),
    ]
    lines=["VBI vs RAM-B early boot comparison, read-only",
           "Do NOT infer Boot0 differences from byte 457: it is inside the MBR partition table.",
           f"VBI={a.vbi}",f"RAM-B={a.ramb}",
           "=== MBR partitions (number, type, LBA start, sectors) ===",
           "VBI: "+repr(partitions(a.vbi)),
           "RAM-B: "+repr(partitions(a.ramb))]
    for name,start,end in regions:
        x,y=sha_range(a.vbi,start,end),sha_range(a.ramb,start,end)
        lines.extend([f"=== {name}: {start:#x}..{end:#x} ===",
                      f"  VBI_SHA256={x}",f"  RAMB_SHA256={y}",
                      "  "+("IDENTICAL" if x==y else "DIFFERENT")])
        if x!=y:
            lines.append("  First differing bytes (offset, VBI, RAM-B): "+
                         repr([(hex(p),hex(v),hex(w)) for p,v,w in
                               differences(a.vbi,a.ramb,start,end)]))
    lines.append("Decision: If post-MBR boot firmware regions match, do NOT blame firmware differences.")
    lines.append("VBI Linux success proves its combination works, not that RAM-B boot is equally configured.")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text("\n".join(lines)+"\n")
    print("\n".join(lines))
    print("Report:",a.out)
if __name__=="__main__":main()
