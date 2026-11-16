#!/usr/bin/env python3
"""Generate independently modified vendor stage-two U-Boot scripts from A2V."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

CHANGES = {
    "S1-env-import": (b"env import -t ${load_addr} ${filesize}", b"echo S1-env-import-skipped"),
    "S2-fdt-resize": (b"fdt resize 65536", b"echo S2-fdt-resize-skipped"),
}

def run(*cmd):
    subprocess.run(cmd, check=True, capture_output=True)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def decode(src, dest):
    data = src.read_bytes()
    if len(data) < 64 or data[:4] != bytes.fromhex("27051956"):
        raise ValueError("Expected U-Boot legacy image")
    run("dumpimage", "-T", "script", "-p", "0", "-o", str(dest), str(src))
    return dest.read_bytes()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proven_a2v_stage2", type=Path)
    ap.add_argument("output_directory", type=Path)
    args = ap.parse_args()
    out = args.output_directory
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        original = decode(args.proven_a2v_stage2, Path(d) / "original.cmd")
        changes = {}
        for label, (old, new) in CHANGES.items():
            if original.count(old) != 1:
                raise ValueError(f"{label}: exact operation must occur once; found {original.count(old)}")
            changes[label] = (old, new)
        manifest = {"control_sha256": digest(args.proven_a2v_stage2.read_bytes()),
                    "decoded_control_sha256": digest(original), "hardware_status": "UNTESTED", "variants": {}}
        for label, (old, new) in changes.items():
            cmd = out / (label + ".cmd")
            scr = out / (label + ".scr")
            updated = original.replace(old, new)
            cmd.write_bytes(updated)
            run("mkimage", "-A", "arm", "-O", "linux", "-T", "script",
                "-C", "none", "-n", label, "-d", str(cmd), str(scr))
            extracted = decode(scr, Path(d) / (label + ".decoded"))
            if extracted != updated:
                raise ValueError(f"{label}: payload mismatch after compilation")
            manifest["variants"][label] = {"sha256": digest(scr.read_bytes()),
                "decoded_sha256": digest(extracted), "hardware_status": "UNTESTED"}
        (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
