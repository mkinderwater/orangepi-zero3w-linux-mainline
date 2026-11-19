#!/usr/bin/env python3
"""Stage16 OFFLINE-only probe cleanup patch, based on Stage15 generated draft.

Fail closed if input source differs in critical ways. NO build, MMIO or boot.
Remaining domain and DMA hazards prohibit activating this driver.
"""
from pathlib import Path
import argparse, difflib, hashlib, re

ROOT = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
PROBE = "static int sunxi_iommu_probe(struct platform_device *pdev)"
REMOVE = "static int sunxi_iommu_remove(struct platform_device *pdev)"

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Unexpected source, expected exactly one: " + old[:90])
    return text.replace(old, new, 1)

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--source", type=Path, default=ROOT/"iommu-v20-stage15-teardown-draft.c")
    a.add_argument("--out", type=Path, default=ROOT/"iommu-v20-stage16-probe-draft.c")
    a.add_argument("--patch", type=Path, default=ROOT/"iommu-v20-stage16-probe-draft.patch")
    args = a.parse_args()
    if args.out.exists() or args.patch.exists():
        a.error("Refusing overwrite: pick new --out and --patch")
    original = args.source.read_text()
    if original.count(PROBE) != 1 or original.count(REMOVE) != 1:
        a.error("Missing/duplicate probe or remove functions")
    if "iommu_group_ref_get(global_group)" not in original:
        a.error("Input is not Stage14+ group reference draft")
    if "iommu_device_unregister(&sunxi_iommu->iommu);" not in original:
        a.error("Input lacks Stage15 teardown")
    head, rest = original.split(PROBE, 1)
    probe, tail = rest.split(REMOVE, 1)
    probe = PROBE + probe
    if "err_plat:" not in probe or "err_clk:" not in probe:
        a.error("Unexpected probe error labels")

    probe = replace_once(probe,
        "\tint ret, irq, irq_got;",
        "\tint ret, irq, irq_got = 0;\n"
        "\tint resets_done = 0, clocks_done = 0;\n"
        "\tbool driver_sysfs = false, core_sysfs = false;")
    probe = replace_once(probe,
        "\t\tsunxi_iommu->base = devm_ioremap_resource",
        "\t\tsunxi_iommu->base = devm_ioremap_resource") if False else probe
    probe = replace_once(probe,
        "\tif (!sunxi_iommu->base) {",
        "\tif (IS_ERR(sunxi_iommu->base)) {")
    probe = replace_once(probe,
        "\t\tret = -ENOENT;\n\t\tgoto err_res;\n\t}\n\n\tfor (irq_got",
        "\t\tret = PTR_ERR(sunxi_iommu->base);\n\t\tgoto err_res;\n\t}\n\n\tfor (irq_got")
    probe = replace_once(probe,
        "\t\tif (irq <= 0) {\n\t\t\tdev_dbg(dev, \"Unable to find IRQ resource\\n\");\n\t\t\tret = -ENOENT;",
        "\t\tif (irq < 0) {\n\t\t\tdev_dbg(dev, \"Unable to find IRQ resource\\n\");\n\t\t\tret = irq;")
    probe = replace_once(probe,
        "\t\tif (!sunxi_iommu->rst)\n\t\t\tgoto err_clk;",
        "\t\tif (!sunxi_iommu->rst) {\n\t\t\tret = -ENOMEM;\n\t\t\tgoto err_cleanup;\n\t\t}")
    probe = replace_once(probe,
        "\t\t\tif (IS_ERR_OR_NULL(sunxi_iommu->rst[i])) {\n"
        "\t\t\t\tdev_err(dev, \"unable to get reset[%d]\", i);\n\t\t\t\tgoto err_clk;",
        "\t\t\tif (IS_ERR_OR_NULL(sunxi_iommu->rst[i])) {\n"
        "\t\t\t\tret = IS_ERR(sunxi_iommu->rst[i]) ?\n"
        "\t\t\t\t\tPTR_ERR(sunxi_iommu->rst[i]) : -ENODEV;\n"
        "\t\t\t\tdev_err(dev, \"unable to get reset[%d]\", i);\n"
        "\t\t\t\tgoto err_cleanup;")
    probe = replace_once(probe,
        "\t\t\tif (reset_control_deassert(sunxi_iommu->rst[i])) {\n"
        "\t\t\t\tdev_err(dev, \"Couldn't reset control deassert\\n\");\n"
        "\t\t\t\tgoto err_clk;\n\t\t\t}",
        "\t\t\tret = reset_control_deassert(sunxi_iommu->rst[i]);\n"
        "\t\t\tif (ret) {\n"
        "\t\t\t\tdev_err(dev, \"Couldn't reset control deassert\\n\");\n"
        "\t\t\t\tgoto err_cleanup;\n\t\t\t}\n"
        "\t\t\tresets_done++;")
    probe = replace_once(probe,
        "\tif (clk_count <= 0) {\n\t\tdev_err(dev, \"no clocks found\\n\");\n\t\tgoto err_clk;",
        "\tif (clk_count <= 0) {\n\t\tret = clk_count < 0 ? clk_count : -ENOENT;\n"
        "\t\tdev_err(dev, \"no clocks found\\n\");\n\t\tgoto err_cleanup;")
    probe = replace_once(probe,
        "\tsunxi_iommu->clk = kzalloc(\n\t\tsizeof(void *) * (clk_count + 1 /*sentinel*/), GFP_KERNEL);",
        "\tsunxi_iommu->clk = kcalloc(clk_count + 1, sizeof(*pclk), GFP_KERNEL);\n"
        "\tif (!sunxi_iommu->clk) {\n\t\tret = -ENOMEM;\n\t\tgoto err_cleanup;\n\t}")
    probe = replace_once(probe,
        "\t\tif (IS_ERR(*pclk)) {\n"
        "\t\t\tsunxi_iommu->clk = NULL;\n"
        "\t\t\tdev_dbg(dev, \"Unable to find clock %s\\n\", name);\n"
        "\t\t\tret = -ENOENT;\n\t\t\tgoto err_clk;",
        "\t\tif (IS_ERR(*pclk)) {\n"
        "\t\t\tret = PTR_ERR(*pclk);\n"
        "\t\t\tdev_dbg(dev, \"Unable to find clock %s\\n\", name);\n"
        "\t\t\tgoto err_cleanup;")
    probe = replace_once(probe,
        "\tpclk = sunxi_iommu->clk;\n\twhile (*pclk) {\n"
        "\t\tclk_prepare_enable(*pclk);\n\t\tpclk++;\n\t}",
        "\tpclk = sunxi_iommu->clk;\n\twhile (*pclk) {\n"
        "\t\tret = clk_prepare_enable(*pclk);\n"
        "\t\tif (ret)\n\t\t\tgoto err_cleanup;\n"
        "\t\tclocks_done++;\n\t\tpclk++;\n\t}")
    probe = replace_once(probe,
        "\tglobal_iommu_dev = sunxi_iommu;\n\tsunxi_iommu->plat_data =\n\t\tkmalloc(",
        "\t/* Provider callbacks during registration need this pointer. */\n"
        "\tglobal_iommu_dev = sunxi_iommu;\n"
        "\tsunxi_iommu->plat_data =\n\t\tkzalloc(")
    probe = replace_once(probe,
        "\t\tdev_err(dev,\n\t\t\t\"iommu version mismatch, please check and reconfigure\\n\");\n\t\tgoto err_plat;",
        "\t\tdev_err(dev,\n\t\t\t\"iommu version mismatch, please check and reconfigure\\n\");\n"
        "\t\tret = -ENODEV;\n\t\tgoto err_cleanup;")
    probe = replace_once(probe,
        "\tsunxi_iommu_sysfs_create(pdev, sunxi_iommu);\n"
        "\tret = iommu_device_sysfs_add(",
        "\tsunxi_iommu_sysfs_create(pdev, sunxi_iommu);\n"
        "\tdriver_sysfs = true;\n\tret = iommu_device_sysfs_add(")
    probe = replace_once(probe,
        "\tif (ret) {\n\t\tdev_err(dev, \"Failed to register iommu in sysfs\\n\");\n\t\tgoto err_plat;\n\t}",
        "\tif (ret) {\n\t\tdev_err(dev, \"Failed to register iommu in sysfs\\n\");\n"
        "\t\tgoto err_cleanup;\n\t}\n\tcore_sysfs = true;")
    probe = replace_once(probe,
        "\tif (ret) {\n\t\tdev_err(dev, \"Failed to register iommu\\n\");\n\t\tgoto err_plat;\n\t}",
        "\tif (ret) {\n\t\tdev_err(dev, \"Failed to register iommu\\n\");\n"
        "\t\tgoto err_cleanup;\n\t}")
    # Legacy jump destinations are now all redirected to a single reverse unwind.
    probe = probe.replace("goto err_res;", "goto err_cleanup;").replace(
        "goto err_irq;", "goto err_cleanup;").replace(
        "goto err_clk;", "goto err_cleanup;").replace(
        "goto err_plat;", "goto err_cleanup;")
    start=probe.index("\nerr_plat:")
    end=probe.index("\n}", start)
    cleanup=r'''
err_cleanup:
    /* Unregister-on-failure cleanup is owned by the Linux IOMMU core. */
    if (core_sysfs)
        iommu_device_sysfs_remove(&sunxi_iommu->iommu);
    if (driver_sysfs)
        sunxi_iommu_sysfs_remove(pdev);
    if (global_iommu_dev == sunxi_iommu)
        global_iommu_dev = NULL;
    if (sunxi_iommu->plat_data) {
        for (i = 0; i < IOMMU_MIC_MAX_MASTER * IOMMU_HW_SET_COUNT; i++)
            kfree(sunxi_iommu->plat_data->master[i]);
        kfree(sunxi_iommu->plat_data);
        sunxi_iommu->plat_data = NULL;
    }
    if (sunxi_iommu->clk) {
        for (i = clocks_done - 1; i >= 0; i--)
            clk_disable_unprepare(sunxi_iommu->clk[i]);
        kfree(sunxi_iommu->clk);
        sunxi_iommu->clk = NULL;
    }
    for (i = resets_done - 1; i >= 0; i--)
        reset_control_assert(sunxi_iommu->rst[i]);
    /* IRQ and ioremap were devm-managed. No premature manual free. */
    sunxi_pgtable_free_pte_cache(iopte_cache);
    iopte_cache = NULL;
    platform_set_drvdata(pdev, NULL);
    return ret;
'''
    probe=probe[:start] + "\n" + cleanup + probe[end:]
    new=head+probe+REMOVE+tail
    if new == original:
        a.error("No change made")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(new)
    args.patch.write_text("".join(difflib.unified_diff(
        original.splitlines(True),new.splitlines(True),
        fromfile="a/drivers/iommu/aw-v20/sunxi-iommu-v2.c",
        tofile="b/drivers/iommu/aw-v20/sunxi-iommu-v2.c")))
    print("INPUT SHA256:",hashlib.sha256(original.encode()).hexdigest())
    print("DRAFT SHA256:",hashlib.sha256(new.encode()).hexdigest())
    print("DRAFT:",args.out,"\nPATCH:",args.patch)
    print("PROBE cleanup draft only. No activation or boot approval.")
if __name__=="__main__":
    main()
