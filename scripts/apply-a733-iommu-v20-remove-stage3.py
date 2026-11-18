#!/usr/bin/env python3
"""Apply only the Linux 6.18 platform .remove signature adaptation.

Read a Stage 2 generated source, write a new Stage 3 source and patch.
No input modification, no kernel installation and no hardware activation.
"""
import argparse,difflib,pathlib,sys
P=pathlib.Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--source",type=pathlib.Path,default=P/"iommu-v20-api-stage2.c")
    a.add_argument("--out",type=pathlib.Path,default=P/"iommu-v20-api-stage3.c")
    x=a.parse_args()
    if not x.source.is_file():sys.exit("STOP: Stage 2 source missing")
    if x.out.exists() or x.source.resolve()==x.out.resolve():
        sys.exit("STOP: output exists or equals input")
    s=x.source.read_text()
    # Strict Stage 2 markers, so the old vendor source cannot be patched by mistake.
    for marker in [".domain_alloc_paging = sunxi_iommu_domain_alloc_paging,",
                   ".map_pages = sunxi_iommu_map,",
                   ".unmap_pages = sunxi_iommu_unmap,"]:
        if s.count(marker)!=1:sys.exit("STOP: Stage 2 API marker not unique: "+marker)
    signature="static int sunxi_iommu_remove(struct platform_device *pdev)"
    reference="\t\t\t       .remove = sunxi_iommu_remove,"
    if s.count(signature)!=1 or s.count(reference)!=1:
        sys.exit("STOP: remove function or registration not uniquely located")
    # Preserve original cleanup logic; wrapper adapts a legacy int return
    # without fabricating a success result.
    # It is not evidence that resource teardown is lifecycle-safe.
    wrapper=(
        "/* Diagnostic API adapter: Linux 6.18 platform_driver.remove is void. */\n"
        "static void sunxi_iommu_remove_618(struct platform_device *pdev)\n"
        "{\n"
        "\t(void)sunxi_iommu_remove(pdev);\n"
        "}\n\n"
    )
    # Place after the old implementation and before the registration.
    # There must be exactly one registration reference.
    pos=s.index(reference)
    s=s[:pos].replace("\nstatic struct platform_driver\n", "\n"+wrapper+"static struct platform_driver\n") +s[pos:]
    if s.count(wrapper)!=1:sys.exit("STOP: platform driver declaration not found")
    s=s.replace(reference,reference.replace("sunxi_iommu_remove,","sunxi_iommu_remove_618,"),1)
    x.out.parent.mkdir(parents=True,exist_ok=True)
    patch=x.out.with_suffix(x.out.suffix+".patch")
    if patch.exists():sys.exit("STOP: patch output exists")
    x.out.write_text(s)
    patch.write_text("".join(difflib.unified_diff(
        x.source.read_text().splitlines(keepends=True),
        s.splitlines(keepends=True),
        fromfile="iommu-v20-api-stage2.c",tofile="iommu-v20-api-stage3.c")))
    print("STAGE3 SOURCE:",x.out)
    print("DIFF:",patch)
    print("UNSAFE FOR BOOT: device teardown and domain lifetime not validated")
if __name__=="__main__":main()
