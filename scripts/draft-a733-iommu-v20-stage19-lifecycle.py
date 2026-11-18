#!/usr/bin/env python3
"""Generate a read-only-input Stage19 C draft atop the Stage16 C draft.

Writes only named output artifacts outside the kernel tree. This draft is
NOT runtime safe and may not be enabled or booted. Cross-build required.
"""
import argparse
import difflib
import hashlib
from pathlib import Path

ART = Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts")
SOURCE = ART / "iommu-v20-stage16-probe-draft.c"

def one(src, old, new, label):
    if src.count(old) != 1:
        raise ValueError("Source drift / nonunique " + label +
                         " (found " + str(src.count(old)) + ")")
    return src.replace(old, new, 1)

def segment(src, start, end, name):
    if src.count(start) != 1 or src.count(end) != 1:
        raise ValueError("Nonunique " + name + " boundaries")
    prefix, rest = src.split(start, 1)
    body, suffix = rest.split(end, 1)
    return prefix, start + body, end + suffix

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=SOURCE)
    p.add_argument("--out", type=Path, default=ART / "iommu-v20-stage19-lifecycle-draft.c")
    p.add_argument("--patch", type=Path, default=ART / "iommu-v20-stage19-lifecycle-draft.patch")
    a = p.parse_args()
    if a.out.exists() or a.patch.exists():
        p.error("Refusing to overwrite output")
    original = a.source.read_text()
    required = ("iommu_group_ref_get(global_group)", "err_cleanup:",
                "core_sysfs = true;", "driver_sysfs = true;",
                "iommu_device_unregister(&sunxi_iommu->iommu);",
                "sunxi_pgtable_set_dma_dev(dma_dev);")
    if any(s not in original for s in required):
        p.error("Requires the exact Stage14+Stage15+Stage16 combined C draft")
    src = original

    # 1. The void sysfs helper ignores errors. All three sysfs files must
    # either exist or be removed on creation failure.
    pre, old, post = segment(
        src, "static void sunxi_iommu_sysfs_create(",
        "static void sunxi_iommu_sysfs_remove(", "vendor sysfs create")
    new = r'''static int sunxi_iommu_sysfs_create(struct platform_device *_pdev,
                                    struct sunxi_iommu_dev *sunxi_iommu)
{
    int ret;

    ret = device_create_file(&_pdev->dev, &sunxi_iommu_enable_attr);
    if (ret)
        return ret;
    ret = device_create_file(&_pdev->dev, &sunxi_iommu_profilling_attr);
    if (ret)
        goto err_enable;
    ret = device_create_file(&_pdev->dev, &sunxi_iommu_map_attr);
    if (ret)
        goto err_profile;
#if IS_ENABLED(CONFIG_AW_IOMMU_IOVA_TRACE)
    sunxi_iommu_init_debugfs(sunxi_iommu);
#endif
    return 0;

err_profile:
    device_remove_file(&_pdev->dev, &sunxi_iommu_profilling_attr);
err_enable:
    device_remove_file(&_pdev->dev, &sunxi_iommu_enable_attr);
    return ret;
}

'''
    if "device_create_file(" not in old or "static void sunxi_iommu_sysfs_create" not in old:
        p.error("Unexpected vendor sysfs implementation")
    src = pre + new + post

    # 2. Honor sysfs error; partial sysfs helper handles its own unwind.
    pre, probe, post = segment(
        src, "static int sunxi_iommu_probe(struct platform_device *pdev)",
        "static int sunxi_iommu_remove(struct platform_device *pdev)", "probe")
    probe = one(probe,
        "\tsunxi_iommu_sysfs_create(pdev, sunxi_iommu);\n\tdriver_sysfs = true;",
        "\tret = sunxi_iommu_sysfs_create(pdev, sunxi_iommu);\n"
        "\tif (ret)\n\t\tgoto err_cleanup;\n\tdriver_sysfs = true;",
        "checked sysfs call")
    # 3. Record registration state to disambiguate failed core registration
    # (which unregisters internally) versus never attempting registration.
    probe = one(probe,
        "bool driver_sysfs = false, core_sysfs = false;",
        "bool driver_sysfs = false, core_sysfs = false;\n"
        "\tbool registration_attempted = false;",
        "registration_attempted flag")
    probe = one(probe,
        "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 15, 0)\n"
        "\tret = iommu_device_register(",
        "\tregistration_attempted = true;\n"
        "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 15, 0)\n"
        "\tret = iommu_device_register(",
        "registration flag before core call")
    # 4. Core already unregisters on registration failure; release only the
    # controller's retained group ref, never call unregister a second time.
    probe = one(probe,
        "err_cleanup:\n    /* Unregister-on-failure cleanup is owned by the Linux IOMMU core. */",
        "err_cleanup:\n"
        "    /* After a failed registration, Linux 6.18 already unregistered. */\n"
        "    if (registration_attempted) {\n"
        "        struct iommu_group *group;\n"
        "        mutex_lock(&sunxi_iommu_group_lock);\n"
        "        group = global_group;\n"
        "        global_group = NULL;\n"
        "        mutex_unlock(&sunxi_iommu_group_lock);\n"
        "        if (group)\n"
        "            iommu_group_put(group);\n"
        "    }",
        "core registration cleanup")
    probe = one(probe,
        "    if (global_iommu_dev == sunxi_iommu)\n        global_iommu_dev = NULL;",
        "    /* Page-table users must be gone after core registration unwind. */\n"
        "    if (dma_dev == dev) {\n"
        "        sunxi_pgtable_set_dma_dev(NULL);\n"
        "        dma_dev = NULL;\n"
        "    }\n"
        "    if (global_iommu_dev == sunxi_iommu)\n"
        "        global_iommu_dev = NULL;",
        "DMA device clear on probe error")
    src = pre + probe + post

    # 5. Normal removal: unregister first (Stage15), then clear DMA globals
    # and release all resources once. No use of devm_free_irq/devm_iounmap:
    # devres will clean those on successful driver detach.
    pre, rem, post = segment(
        src, "static int sunxi_iommu_remove(struct platform_device *pdev)",
        "/* Diagnostic API adapter: Linux 6.18 platform_driver.remove is void. */",
        "remove")
    if rem.count("iommu_device_unregister(&sunxi_iommu->iommu);") != 1:
        p.error("Invalid Stage15 unregister ordering")
    begin = rem.index("static int sunxi_iommu_remove(")
    brace = rem.index("{", begin)
    old_body = rem[brace:]
    # Keep local variables simple and avoid depending on an unverified struct
    # field for number of clocks or resets.
    replacement = r'''
{
    struct sunxi_iommu_dev *sunxi_iommu = platform_get_drvdata(pdev);
    struct iommu_resv_region *entry, *next;
    struct iommu_group *group;
    struct clk **clock;
    int nclks = 0, nresets, i;

    /* Core detaches all clients and frees the last group default domain. */
    iommu_device_unregister(&sunxi_iommu->iommu);

    mutex_lock(&sunxi_iommu_group_lock);
    group = global_group;
    global_group = NULL;
    mutex_unlock(&sunxi_iommu_group_lock);
    if (group)
        iommu_group_put(group);

    if (dma_dev == &pdev->dev) {
        sunxi_pgtable_set_dma_dev(NULL);
        dma_dev = NULL;
    }

    /* External domain owners and any in-flight page-table work must be
     * excluded before cache teardown. This is not yet proven.
     */
    sunxi_pgtable_free_pte_cache(iopte_cache);
    iopte_cache = NULL;

    list_for_each_entry_safe(entry, next, &sunxi_iommu->rsv_list, list) {
        list_del(&entry->list);
        kfree(entry);
    }

    sunxi_iommu_sysfs_remove(pdev);
    iommu_device_sysfs_remove(&sunxi_iommu->iommu);

    if (sunxi_iommu->clk) {
        for (clock = sunxi_iommu->clk; *clock; clock++)
            nclks++;
        for (i = nclks - 1; i >= 0; i--)
            clk_disable_unprepare(sunxi_iommu->clk[i]);
        kfree(sunxi_iommu->clk);
        sunxi_iommu->clk = NULL;
    }

    nresets = of_count_phandle_with_args(pdev->dev.of_node, "resets",
                                         "#reset-cells");
    if (nresets > 0 && sunxi_iommu->rst) {
        for (i = nresets - 1; i >= 0; i--)
            reset_control_assert(sunxi_iommu->rst[i]);
    }

    if (sunxi_iommu->plat_data) {
        for (i = 0; i < IOMMU_MIC_MAX_MASTER * IOMMU_HW_SET_COUNT; i++)
            kfree(sunxi_iommu->plat_data->master[i]);
        kfree(sunxi_iommu->plat_data);
        sunxi_iommu->plat_data = NULL;
    }
    global_iommu_dev = NULL;
    platform_set_drvdata(pdev, NULL);
    return 0;
}

'''
    if "sunxi_pgtable_free_pte_cache(iopte_cache);" not in old_body:
        p.error("Unexpected Stage15 remove body")
    rem = rem[:brace] + replacement.lstrip("\n")
    src = pre + rem + post

    # Verify key lifecycle invariants before writing.
    _, newprobe, newrem = segment(
        src, "static int sunxi_iommu_probe(struct platform_device *pdev)",
        "static int sunxi_iommu_remove(struct platform_device *pdev)", "result")
    for marker in ("if (registration_attempted)", "sunxi_pgtable_set_dma_dev(NULL)",
                   "if (core_sysfs)", "if (driver_sysfs)"):
        if marker not in newprobe:
            p.error("Missing probe cleanup: " + marker)
    if newrem.index("iommu_device_unregister(") > newrem.index(
            "sunxi_pgtable_free_pte_cache("):
        p.error("Premature cache teardown")
    if newrem.index("devm_free_irq(") > newrem.index("sunxi_pgtable_free_pte_cache("):\n        p.error("IRQ handler remains live after cache destruction")\n    if newrem.count("iommu_device_unregister(") != 1:
        p.error("Duplicate unregister")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(src)
    a.patch.write_text("".join(difflib.unified_diff(
        original.splitlines(True), src.splitlines(True),
        fromfile="a/drivers/iommu/aw-v20/sunxi-iommu-v2.c",
        tofile="b/drivers/iommu/aw-v20/sunxi-iommu-v2.c")))
    print("SOURCE_SHA256:", hashlib.sha256(original.encode()).hexdigest())
    print("DRAFT_SHA256:", hashlib.sha256(src.encode()).hexdigest())
    print("OUTPUT:", a.out)
    print("PATCH:", a.patch)
    print("NOT A BOOT CANDIDATE. SOURCE/DMA LIFETIME REMAINS UNPROVEN.")

if __name__ == "__main__":
    main()
