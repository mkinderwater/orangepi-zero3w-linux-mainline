#!/usr/bin/env python3
"""Read-only structural DTB difference report; does not modify either DTB."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

CRITICAL = ("compatible", "status", "supply", "pinctrl", "clock", "reset",
            "interrupt", "power", "voltage", "mmc", "sd-uhs", "cap-",
            "non-removable", "bus-width", "dma", "gpio", "phy", "reg")

def u32(data, pos):
    return struct.unpack_from(">I", data, pos)[0]

def align(n):
    return (n + 3) & ~3

def parse(raw):
    if not 40 <= len(raw) <= 64 * 1024 * 1024:
        raise ValueError("Invalid DTB length")
    h = struct.unpack_from(">10I", raw)
    magic, total, so, to, ro, version, last, boot, ts, ss = h
    if magic != 0xd00dfeed or total != len(raw) or version < 17 or last > version:
        raise ValueError("Invalid FDT header")
    if (so % 4 or to % 4 or ro % 8 or min(so, to, ro) < 40
            or so + ss > total or to + ts > total):
        raise ValueError("Invalid section bounds")
    tokens = raw[so:so + ss]
    strings = raw[to:to + ts]
    reserve, i = [], ro
    while i + 16 <= total:
        addr, size = struct.unpack_from(">QQ", raw, i)
        i += 16
        if addr == size == 0:
            break
        reserve.append((hex(addr), hex(size)))
        if len(reserve) > 100000:
            raise ValueError("Too many reserved ranges")
    else:
        raise ValueError("Missing reservation terminator")
    nodes, stack, i, finished = {}, [], 0, False
    while i + 4 <= len(tokens):
        tok = u32(tokens, i)
        i += 4
        if tok == 1:
            j = tokens.find(b"\0", i)
            if j < 0:
                raise ValueError("Invalid node name")
            name = tokens[i:j].decode("utf-8")
            i = align(j + 1)
            if not stack:
                if name or nodes:
                    raise ValueError("Invalid root node")
                path = "/"
            else:
                if not name or "/" in name:
                    raise ValueError("Invalid child node")
                path = stack[-1].rstrip("/") + "/" + name
            if path in nodes:
                raise ValueError("Duplicate node")
            nodes[path] = {}
            stack.append(path)
            if len(nodes) > 200000 or len(stack) > 128:
                raise ValueError("Too many nodes")
        elif tok == 2:
            if not stack:
                raise ValueError("Unbalanced end node")
            stack.pop()
        elif tok == 3:
            if not stack or i + 8 > len(tokens):
                raise ValueError("Invalid property")
            length, off = struct.unpack_from(">II", tokens, i)
            i += 8
            if off >= len(strings) or length > len(tokens) - i:
                raise ValueError("Invalid property bounds")
            j = strings.find(b"\0", off)
            if j < 0:
                raise ValueError("Invalid property name")
            name = strings[off:j].decode("ascii")
            if not name or name in nodes[stack[-1]]:
                raise ValueError("Duplicate or empty property")
            nodes[stack[-1]][name] = bytes(tokens[i:i + length])
            i = align(i + length)
        elif tok == 4:
            continue
        elif tok == 9:
            if stack or not nodes:
                raise ValueError("Unbalanced FDT end")
            finished = True
            break
        else:
            raise ValueError("Unknown FDT token")
    if not finished:
        raise ValueError("No FDT end token")
    return nodes, reserve

def show(name, data):
    if data is None:
        return None
    record = {"hex": data.hex(), "length": len(data)}
    if not data:
        record["boolean"] = True
    elif name in ("compatible", "model", "status", "stdout-path",
                  "clock-names", "reset-names", "dma-names", "pinctrl-names") and data.endswith(b"\0"):
        try:
            record["strings"] = [v.decode("utf-8") for v in data[:-1].split(b"\0")]
        except UnicodeDecodeError:
            pass
    elif len(data) % 4 == 0 and len(data) <= 128:
        record["cells"] = [u32(data, i) for i in range(0, len(data), 4)]
    return record

def category(node):
    node = node.lower()
    if any(t in node for t in ("sdmmc", "mmc@", "pinctrl", "pio@", "pmu@", "regulator")):
        return "P0 MMC power"
    if any(t in node for t in ("ccu@", "interrupt-controller", "cpu@", "memory@", "reserved-memory", "psci")):
        return "P0 CPU clock memory"
    if any(t in node for t in ("hdmi", "tcon", "gpu", "display", "dsi", "/de@")):
        return "P1 Display"
    if any(t in node for t in ("usb", "pcie", "wlan", "wifi", "rfkill", "gmac")):
        return "P1 Connectivity"
    return "P2 Other"

def compare(v, h):
    changes = []
    for path in sorted(v.keys() | h.keys()):
        if path not in v or path not in h:
            changes.append({"node": path, "category": category(path),
                            "change": "added node" if path not in v else "removed node"})
            continue
        for prop in sorted(v[path].keys() | h[path].keys()):
            old, new = v[path].get(prop), h[path].get(prop)
            if old == new:
                continue
            changes.append({"node": path, "category": category(path), "property": prop,
                            "change": "added" if old is None else "removed" if new is None else "changed",
                            "critical": any(t in prop.lower() for t in CRITICAL),
                            "vendor": show(prop, old), "hybrid": show(prop, new)})
    return changes

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vendor", type=Path, required=True)
    ap.add_argument("--hybrid", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True, help="New output directory")
    a = ap.parse_args()
    if a.output.exists():
        ap.error("Output exists; refusing overwrite")
    if a.vendor.resolve() == a.hybrid.resolve():
        ap.error("Must supply distinct vendor/hybrid DTB files")
    try:
        vr, hr = a.vendor.read_bytes(), a.hybrid.read_bytes()
        vn, rv = parse(vr)
        hn, rh = parse(hr)
        result = {"schema": 1, "status": "STATIC_ONLY",
                  "vendor": {"path": str(a.vendor), "sha256": hashlib.sha256(vr).hexdigest(),
                             "nodes": len(vn), "reservations": rv},
                  "hybrid": {"path": str(a.hybrid), "sha256": hashlib.sha256(hr).hexdigest(),
                             "nodes": len(hn), "reservations": rh},
                  "changes": compare(vn, hn)}
        lines = ["# Zero 3W vendor vs hybrid compiled DTB comparison", "",
                 "Static binary evidence, not proof of actual hardware presence.", "",
                 "Vendor SHA256: " + result["vendor"]["sha256"],
                 "Hybrid SHA256: " + result["hybrid"]["sha256"],
                 "Changed entries: " + str(len(result["changes"])), ""]
        for cat in ("P0 MMC power", "P0 CPU clock memory", "P1 Display",
                    "P1 Connectivity", "P2 Other"):
            items = [x for x in result["changes"] if x["category"] == cat]
            lines.extend(["## " + cat + " (" + str(len(items)) + ")", ""])
            for item in items:
                lines.append("- " + item["node"] + ": " + item["change"] +
                             (" " + item["property"] if "property" in item else ""))
                if item.get("critical"):
                    lines.append("  vendor: " + json.dumps(item["vendor"]))
                    lines.append("  hybrid: " + json.dumps(item["hybrid"]))
            lines.append("")
        lines.extend(["## Limits", "",
                      "- Raw cells are not resolved into phandle targets.",
                      "- Bootloader runtime DTB fixups are not included.",
                      "- Status okay does not prove physical hardware is fitted.",
                      "- No DTB, kernel, boot script, or media is modified.", ""])
        a.output.mkdir(parents=True, exist_ok=False)
        (a.output / "dtb-diff.json").write_text(json.dumps(result, indent=2) + "\n")
        (a.output / "dtb-diff.md").write_text("\n".join(lines))
    except (OSError, ValueError, UnicodeError) as e:
        ap.error(str(e))
    print("DTB_DIFF_WRITTEN:", a.output)
    print("VENDOR_NODES:", len(vn))
    print("HYBRID_NODES:", len(hn))
    print("CHANGED_ENTRIES:", len(result["changes"]))

if __name__ == "__main__":
    main()
