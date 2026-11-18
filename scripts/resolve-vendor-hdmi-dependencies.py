#!/usr/bin/env python3
"""Resolve A733 vendor HDMI/DE/TCON DTB phandles and compare RAM-B providers.

Read-only. Operates on two decompiled DTBs. No numeric phandle values are
transferred to the baseline, and no source/boot files are changed.
"""
import argparse
import collections
import pathlib
import re

NODE_OPEN = re.compile(r'^\s*([^{};]+?)\s*\{\s*$')
PHANDLE = re.compile(r'^\s*phandle\s*=\s*<\s*0x([0-9a-fA-F]+)\s*>\s*;')
PROP = re.compile(r'^\s*([\w,#.+-]+)\s*=\s*(.+);\s*$')
NAMES = re.compile(r'"([^"]+)"')
VALUE = re.compile(r'0x[0-9a-fA-F]+|\b\d+\b')
LINKS = {
    'clocks', 'resets', 'power-domains', 'phys', 'assigned-clocks',
    'assigned-clock-parents', 'pinctrl-0', 'pinctrl-1',
    'remote-endpoint', 'dmas', 'iommus', 'interconnects', 'mboxes',
}
TARGETS = (
    'allwinner,sunxi-drm',
    'allwinner,display-engine-v352',
    'allwinner,tcon-top0',
    'allwinner,tcon-top1',
    'allwinner,tcon-tv',
    'allwinner,sunxi-hdmi',
)
def dts_path(parts):
    # The dtc root node is named '/', not a normal path component.
    # Construct paths consistently for both opening braces and properties.
    names = [p for p in parts if p and p != '/']
    return '/' + '/'.join(names)

def parse(path):
    nodes = {}
    stack = []
    acc = None
    for line in pathlib.Path(path).read_text(errors='replace').splitlines():
        if acc is not None:
            acc += ' ' + line.strip()
            if ';' not in line:
                continue
            line = acc
            acc = None
        stripped = line.strip()
        opened = NODE_OPEN.match(line)
        if opened:
            title = opened.group(1).strip()
            nodepath = dts_path([*stack, title])
            stack.append(title)
            nodes[nodepath] = {}
            continue
        if stripped.startswith('};') or stripped == '}':
            if stack:
                stack.pop()
            continue
        if not stack:
            continue
        if '=' in stripped and ';' not in stripped:
            acc = stripped
            continue
        m = PROP.match(line)
        if m:
            nodepath = dts_path(stack)
            if nodepath not in nodes:
                raise ValueError(f'DTS node path missing while parsing {path}: {nodepath}')
            nodes[nodepath][m.group(1)] = m.group(2)
    return nodes
def phandles(nodes):
    result = {}
    for path, props in nodes.items():
        s = props.get('phandle')
        if not s: continue
        m = re.search(r'0x([0-9a-fA-F]+)', s)
        if m:
            result[int(m.group(1),16)] = path
    return result

SPECIFIER_CELLS = {
    'clocks': '#clock-cells',
    'assigned-clocks': '#clock-cells',
    'assigned-clock-parents': '#clock-cells',
    'resets': '#reset-cells',
    'power-domains': '#power-domain-cells',
    'phys': '#phy-cells',
    'dmas': '#dma-cells',
    'iommus': '#iommu-cells',
    'interconnects': '#interconnect-cells',
    'mboxes': '#mbox-cells',
}

def resolve_reference_stream(raw, key, id_map, nodes):
    """Consume [phandle, provider-specifiers...] using provider #*-cells.

    Fail closed for absent providers or unknown cell counts. Never interpret
    arbitrary specifier values as phandles.
    """
    cells = [int(token, 0) for token in VALUE.findall(raw)]
    direct = key.startswith('pinctrl-') or key == 'remote-endpoint'
    spec_property = SPECIFIER_CELLS.get(key)
    if not direct and not spec_property:
        return ["not parsed: unknown provider cell semantics"]
    result = []
    cursor = 0
    while cursor < len(cells):
        phandle = cells[cursor]
        cursor += 1
        provider = id_map.get(phandle)
        if provider is None:
            result.append(f"UNRESOLVED provider phandle 0x{phandle:x}")
            break
        args_count = 0
        if not direct:
            n = nodes[provider].get(spec_property)
            nums = VALUE.findall(n or '')
            if len(nums) != 1:
                result.append(f"UNRESOLVED {provider}: {spec_property} missing or ambiguous")
                break
            args_count = int(nums[0], 0)
        if args_count < 0 or cursor + args_count > len(cells):
            result.append(f"INVALID specifier count for {provider}: {args_count}")
            break
        args = cells[cursor: cursor+args_count]
        cursor += args_count
        result.append(f"provider 0x{phandle:x} -> {provider} ({nodes[provider].get('compatible','no compatible')}); specifiers {args}")
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('vendor_dts',type=pathlib.Path)
    ap.add_argument('baseline_dts',type=pathlib.Path)
    ap.add_argument('--output',type=pathlib.Path,required=True)
    args=ap.parse_args()
    vendor=parse(args.vendor_dts)
    base=parse(args.baseline_dts)
    ids=phandles(vendor)
    base_compat=collections.defaultdict(list)
    for p,prop in base.items():
        for c in NAMES.findall(prop.get('compatible','')):
            base_compat[c].append(p)
    targets=[]
    for path,props in vendor.items():
        if any(t in NAMES.findall(props.get('compatible','')) for t in TARGETS):
            targets.append(path)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    lines=[]
    lines.append('Vendor display controller dependency map (read-only)')
    lines.append(f'Vendor DTS: {args.vendor_dts}')
    lines.append(f'RAM-B DTS: {args.baseline_dts}')
    lines.append(f'Matched display nodes: {len(targets)}')
    lines.append('IMPORTANT: phandle integers are vendor-local, never copy into RAM-B.')
    lines.append('Clock/reset/power-domain references resolved by provider cell counts;')
    lines.append('Unresolved providers/cell counts are reported, never guessed.')
    lines.append('')
    for path in targets:
        props=vendor[path]
        compat=NAMES.findall(props.get('compatible',''))
        lines.append(f'=== {path} ===')
        lines.append(f'  compatible: {", ".join(compat)}')
        lines.append(f'  status: {props.get("status","(default okay)")}')
        lines.append(f'  reg: {props.get("reg","(none)")}')
        lines.append(f'  matching baseline compatible nodes: {", ".join(sum([base_compat.get(c,[]) for c in compat],[])) or "NONE"}')
        for key in ('clock-names','reset-names','phy-names','assigned-clock-rates'):
            if key in props:
                lines.append(f'  {key}: {props[key]}')
        for key in sorted(LINKS):
            raw=props.get(key)
            if not raw: continue
            lines.append(f'  {key}: {raw}')
            for resolved in resolve_reference_stream(raw,key,ids,vendor):
                lines.append(f'    {resolved}')
        lines.append('')
    lines.append('NEXT: inspect vendor provider #clock-cells/#reset-cells/#power-domain-cells,')
    lines.append('graph endpoints and current A733 Linux CCU/power-domain capabilities before staging a boot DTB.')
    lines.append('This report does not prove HDMI initialization or PowerVR support.')
    args.output.write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
if __name__=='__main__':
    main()
