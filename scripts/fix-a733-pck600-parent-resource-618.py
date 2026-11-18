#!/usr/bin/env python3
"""Adapt isolated 6.18 A733 PCK-600 to vendor simple-mfd parent resource.

Keep the existing A523 driver path intact. Vendor A733 child has no reg;
the parent syscon node owns a 0xb000 MMIO region. Only A733 uses parent
resource mapping. Only DT-declared child domains are initialized.
"""
import argparse
from pathlib import Path

ap=argparse.ArgumentParser()
ap.add_argument("--root",type=Path,default=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4"))
a=ap.parse_args()
path=a.root/"linux/drivers/pmdomain/sunxi/sun55i-pck600.c"
if not path.is_file(): ap.error("Missing "+str(path))
text=path.read_text()
if "a733_parent_syscon_resource" in text: ap.error("Patch already applied")
if "sun60i_a733_pck600_desc" not in text: ap.error("Run integrate-a733-pck600-618.py first")
def change(a,b,label):
    global text
    if text.count(a)!=1: raise RuntimeError(f"{label}: source mismatch ({text.count(a)} instances)")
    text=text.replace(a,b,1)
change("#include <linux/of.h>","#include <linux/of.h>\n#include <linux/of_address.h>", "of_address header")
change("bool needs_reset;","bool needs_reset;\n\tbool a733_parent_syscon_resource;", "descriptor flag")
change(".needs_reset = false,\n    .pd_names = sun60i_a733_pck600_pd_names,",
       ".needs_reset = false,\n    .a733_parent_syscon_resource = true,\n    .pd_names = sun60i_a733_pck600_pd_names,", "A733 flag")
change("\tvoid __iomem *base;\n\tint i, ret;",
       "\tvoid __iomem *base;\n\tstruct device_node *parent;\n\tstruct resource res;\n\tint i, ret;", "local resource")
change("""\tbase = devm_platform_ioremap_resource(pdev, 0);
\tif (IS_ERR(base))
\t\treturn PTR_ERR(base);""",
"""\tif (desc->a733_parent_syscon_resource) {
\t\t/* The vendor A733 power-controller child has no reg property.
\t\t * Its enclosing syscon/simple-mfd PCK node owns the registers.
\t\t * Map without requesting the already-shared syscon region.
\t\t */
\t\tparent = of_get_parent(dev_of_node(dev));
\t\tif (!parent)
\t\t\treturn -EINVAL;
\t\tret = of_address_to_resource(parent, 0, &res);
\t\tof_node_put(parent);
\t\tif (ret)
\t\t\treturn dev_err_probe(dev, ret, "missing parent PCK register resource\\n");
\t\tif (resource_size(&res) < desc->num_domains * PPU_REG_SIZE)
\t\t\treturn dev_err_probe(dev, -EINVAL, "parent PCK resource too small\\n");
\t\tbase = devm_ioremap(dev, res.start, resource_size(&res));
\t\tif (!base)
\t\t\treturn -ENOMEM;
\t} else {
\t\tbase = devm_platform_ioremap_resource(pdev, 0);
\t\tif (IS_ERR(base))
\t\t\treturn PTR_ERR(base);
\t}""", "parent resource")
change("""\tfor (i = 0; i < desc->num_domains; i++) {
\t\tstruct sunxi_pck600_pd *pd = &pck->pds[i];

\t\tpd->genpd.name""",
"""\tfor (i = 0; i < desc->num_domains; i++) {
\t\tstruct sunxi_pck600_pd *pd = &pck->pds[i];

\t\tif (desc->a733_parent_syscon_resource) {
\t\t\tstruct device_node *child;
\t\t\tu32 domain_id;
\t\t\tbool declared = false;

\t\t\tfor_each_available_child_of_node_scoped(dev_of_node(dev), child) {
\t\t\t\tif (!of_property_read_u32(child, "reg", &domain_id) &&
\t\t\t\t    domain_id == i) {
\t\t\t\t\tdeclared = true;
\t\t\t\t\tbreak;
\t\t\t\t}
\t\t\t}
\t\t\tif (!declared)
\t\t\t\tcontinue;
\t\t}

\t\tpd->genpd.name""", "defined domain subset")
change("""\tfor (i--; i >= 0; i--)
\t\tpm_genpd_remove(genpds->domains[i]);""",
"""\tfor (i--; i >= 0; i--)
\t\tif (genpds->domains[i])
\t\t\tpm_genpd_remove(genpds->domains[i]);""","sparse cleanup")
backup=path.with_suffix(".c.pre-parent-syscon")
if backup.exists(): ap.error("backup exists, refusing overwrite")
backup.write_text(path.read_text())
path.write_text(text)
print("A733 parent resource mapping and DT-listed domain selection patched:",path)
print("Existing A523 resource mapping unchanged. No kernel/DTB/boot media modified.")
