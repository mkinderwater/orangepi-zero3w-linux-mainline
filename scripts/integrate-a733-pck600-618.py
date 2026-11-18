#!/usr/bin/env python3
"""Stage an A733-specific descriptor in Linux 6.18 PCK-600 driver.

Uses the vendor 11-domain ordering/delay values, not A523 defaults. Only
modifies the isolated stage4 tree, backs up the driver and Kconfig. No DTB,
hardware, or boot media changes. Compile separately after running.
"""
from pathlib import Path
import argparse
import re

ap = argparse.ArgumentParser()
ap.add_argument("--root", type=Path, default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4"))
args = ap.parse_args()
root = args.root
driver = root / "linux/drivers/pmdomain/sunxi/sun55i-pck600.c"
kconfig = root / "linux/drivers/pmdomain/sunxi/Kconfig"
for path in (driver, kconfig):
    if not path.is_file():
        ap.error(f"Missing {path}")
old = driver.read_text()
kc_old = kconfig.read_text()
if 'sun60i_a733_pck600_desc' in old:
    ap.error("A733 PCK-600 already staged, refusing double application")

def exactly_once(text, before, after, label):
    if text.count(before) != 1:
        raise ValueError(f"{label}: expected one source match, found {text.count(before)}")
    return text.replace(before, after, 1)

new = exactly_once(old,
    'struct sunxi_pck600_desc {\n',
    'struct sunxi_pck600_desc {\n\tbool needs_reset;\n',
    "descriptor needs-reset field")
# Preserve upstream A523 behavior; A733 vendor provider does not require reset.
new = exactly_once(new,
    'static const struct sunxi_pck600_desc sun55i_a523_pck600_desc = {\n',
    'static const struct sunxi_pck600_desc sun55i_a523_pck600_desc = {\n\t.needs_reset = true,\n',
    "A523 reset policy")
old_rst = '''\trst = devm_reset_control_get_exclusive_released(dev, NULL);
\tif (IS_ERR(rst))
\t\treturn dev_err_probe(dev, PTR_ERR(rst), "failed to get reset control\\n");'''
new_rst = '''\tif (desc->needs_reset) {
\t\trst = devm_reset_control_get_exclusive_released(dev, NULL);
\t\tif (IS_ERR(rst))
\t\t\treturn dev_err_probe(dev, PTR_ERR(rst), "failed to get reset control\\n");
\t}'''
new = exactly_once(new, old_rst, new_rst, "A733 no-reset handling")
descriptor = '''
/* A733 (sun60iw2) vendor PCK-600 domain order, binding indices 0..10.
 * All domains have identical vendor delay parameters but DIFFER from A523.
 * Domain indices: 1 DE_SYS, 9 VO, 10 VO1 for display/HDMI.
 */
static const char * const sun60i_a733_pck600_pd_names[] = {
    "VI", "DE_SYS", "VE_DEC", "VE_ENC", "NPU", "GPU_TOP",
    "GPU_CORE", "PCIE", "USB2", "VO", "VO1",
};

static const struct sunxi_pck600_desc sun60i_a733_pck600_desc = {
    .needs_reset = false,
    .pd_names = sun60i_a733_pck600_pd_names,
    .num_domains = ARRAY_SIZE(sun60i_a733_pck600_pd_names),
    .logic_power_switch0_delay_offset = 0xc00,
    .logic_power_switch1_delay_offset = 0xc04,
    .off2on_delay_offset = 0xc10,
    .device_ctrl0_delay = 0x1f1f1f,
    .device_ctrl1_delay = 0x1f1f,
    .logic_power_switch0_delay = 0x8080808,
    .logic_power_switch1_delay = 0x808,
    .off2on_delay = 0x8,
};

'''
anchor='static const struct of_device_id sunxi_pck600_of_match[] = {'
new = exactly_once(new, anchor, descriptor + anchor, "A733 descriptor")
match = '''\t{\n\t\t.compatible\t= "allwinner,sun55i-a523-pck-600",'''
# Existing A523 match preserved; new A733 match inserted before sentinel
sentinel = '''\t{ }'''
if sentinel not in new:
    # Accept style from the exact displayed upstream source
    sentinel='''\t{}'''
if sentinel not in new:
    raise SystemExit("STOP: cannot locate PCK-600 match sentinel")
entry='''\t{
\t\t.compatible = "allwinner,sun60iw2-pck-600",
\t\t.data = &sun60i_a733_pck600_desc,
\t},
'''
new = exactly_once(new, sentinel, entry + sentinel, "A733 compatible")
kc_new = exactly_once(kc_old,
    'tristate "Allwinner A523 PCK-600 power domain driver"',
    'tristate "Allwinner A523/A733 PCK-600 power domain driver"',
    "Kconfig description")
backup = driver.with_suffix(".c.pre-a733-pck600")
kbak = kconfig.with_suffix(".Kconfig.pre-a733-pck600")
if backup.exists() or kbak.exists():
    ap.error("Backup already exists; refusing repeat edit")
# Only write after all validations.
backup.write_text(old)
kbak.write_text(kc_old)
driver.write_text(new)
kconfig.write_text(kc_new)
print("Staged A733 PCK-600 11-domain descriptor in:", driver)
print("Vendor delays: 0x1f1f1f / 0x1f1f; PCK no-reset policy.")
print("A523 descriptor remains intact. No DTB, clock, firmware, or boot changes.")
print("NEXT: enable CONFIG_SUN55I_PCK600=y, then build Image/modules and test provider with board-exact DTB.")
