#!/usr/bin/env python3
"""Apply compile-only IOMMU v20 interface adapters in a disposable stage tree.

Never promote outputs as bootable. Vendor singleton domain and HW-init error
handling remain UNSAFE and deliberately out of scope at this stage.
"""
from pathlib import Path
import argparse,hashlib,re,difflib,sys
EXPECTED="2cfa66d29a1223d259486c29ef6722fc6eb3679990f39592c8c4d4b11442e31d"
DEFAULT=Path("/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/iommu-v20-port-stage1-kcflags/linux/drivers/iommu/aw-v20/sunxi-iommu-v2.c")
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def one(s,old,new,label):
    n=s.count(old)
    if n!=1:raise ValueError(f"{label}: expected exactly one anchor, got {n}")
    return s.replace(old,new,1)
def scoped_one(s, start, stop, old, new, label):
    """Replace exactly one anchor inside a uniquely bounded source section."""
    if s.count(start)!=1:
        raise ValueError(f"{label}: expected one start marker, got {s.count(start)}")
    head, tail=s.split(start,1)
    if stop not in tail:
        raise ValueError(f"{label}: missing end marker")
    section, rest=tail.split(stop,1)
    section=one(section,old,new,label)
    return head+start+section+stop+rest
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=DEFAULT)
    p.add_argument("--out",type=Path,required=True,help="NEW standalone output .c, never overwrite source")
    a=p.parse_args()
    if not a.source.is_file():sys.exit("STOP: staged source not found")
    if a.out.exists():sys.exit("STOP: output already exists")
    if a.out.resolve()==a.source.resolve():sys.exit("STOP: will not overwrite input")
    if digest(a.source)!=EXPECTED:sys.exit("STOP: input is not exact verified vendor v2 source")
    before=a.source.read_text()
    s=before
    s=one(s,"static struct iommu_domain *sunxi_iommu_domain_alloc(unsigned type)",
        "static struct iommu_domain *sunxi_iommu_domain_alloc_paging(struct device *dev)","domain API")
    s=one(s,"if (type != IOMMU_DOMAIN_DMA && type != IOMMU_DOMAIN_UNMANAGED)\n\t\treturn NULL;",
        "/* Linux 6.18 paging-domain allocator; domain type is core-managed. */\n\t(void)dev;","domain type")
    # The obsolete cookie branch is disabled by the vendor source's
    # COOKIE_HANDLE_BY_CORE macro. Do not change its semantics; avoid an
    # undefined 'type' in dead preprocessor code only after verifying guard.
    s=one(s,"if (type == IOMMU_DOMAIN_DMA &&",
        "if (false &&", "dead guarded cookie reference")
    s=one(s,
        "static int sunxi_iommu_map(struct iommu_domain *domain, unsigned long iova,\n\t\t\t   phys_addr_t paddr, size_t size, int prot, gfp_t gfp)",
        "static int sunxi_iommu_map(struct iommu_domain *domain, unsigned long iova,\n\t\t\t   phys_addr_t paddr, size_t size, size_t count,\n\t\t\t   int prot, gfp_t gfp, size_t *mapped)","map signature")
    # Compile-only adapter. Validate multiplication before any DMA map.
    s=scoped_one(s,
        "static int sunxi_iommu_map(", "static size_t sunxi_iommu_unmap(",
        "\tWARN_ON(sunxi_domain->pgtable == NULL);\n\tiova_start = iova & IOMMU_PT_MASK;",
        "\tif (!size || !count || size > SIZE_MAX / count)\n\t\treturn -EINVAL;\n\t*mapped = 0;\n\tsize *= count;\n\tWARN_ON(sunxi_domain->pgtable == NULL);\n\tiova_start = iova & IOMMU_PT_MASK;",
        "map size")
    s=one(s,
        "\tsunxi_pgtable_prepare_l2_tables(sunxi_domain->pgtable,\n\t\t\t\t\tiova_start, iova_end, paddr, prot);\n\tspin_unlock_irqrestore(&sunxi_domain->dt_lock, flags);\n\n\treturn 0;",
        "\tret = sunxi_pgtable_prepare_l2_tables(sunxi_domain->pgtable,\n\t\t\t\t\tiova_start, iova_end, paddr, prot);\n\tspin_unlock_irqrestore(&sunxi_domain->dt_lock, flags);\n\tif (ret)\n\t\treturn ret;\n\t*mapped = size;\n\treturn 0;",
        "map result")
    s=one(s,
        "static size_t sunxi_iommu_unmap(struct iommu_domain *domain, unsigned long iova,\n\t\t\t\tsize_t size, struct iommu_iotlb_gather *gather)",
        "static size_t sunxi_iommu_unmap(struct iommu_domain *domain, unsigned long iova,\n\t\t\t\tsize_t size, size_t count,\n\t\t\t\tstruct iommu_iotlb_gather *gather)",
        "unmap signature")
    s=one(s,
        "\tplat_data = global_iommu_dev->plat_data;\n\tWARN_ON(sunxi_domain->pgtable == NULL);",
        "\tif (!size || !count || size > SIZE_MAX / count)\n\t\treturn 0;\n\tsize *= count;\n\tplat_data = global_iommu_dev->plat_data;\n\tWARN_ON(sunxi_domain->pgtable == NULL);",
        "unmap size")
    s=one(s,"void sunxi_iommu_iotlb_sync_map(struct iommu_domain *domain, unsigned long iova,",
        "static int sunxi_iommu_iotlb_sync_map(struct iommu_domain *domain, unsigned long iova,","iotlb signature")
    s=one(s,
        "\tsunxi_zap_tlb(iova, size);\n\tspin_unlock_irqrestore(&sunxi_domain->dt_lock, flags);\n\n\treturn;",
        "\tsunxi_zap_tlb(iova, size);\n\tspin_unlock_irqrestore(&sunxi_domain->dt_lock, flags);\n\n\treturn 0;",
        "iotlb result")
    s=one(s,
        "static int sunxi_iommu_of_xlate(struct device *dev,\n\t\t\t\tstruct of_phandle_args *args)",
        "static int sunxi_iommu_of_xlate(struct device *dev,\n\t\t\t\tconst struct of_phandle_args *args)","of_xlate const")
    # Both conditional implementations contain these fields. Only change the
    # SEPERATE_DOMAIN_API path selected by the exact vendor header.
    s=scoped_one(s,
        "#ifdef SEPERATE_DOMAIN_API", "#else",
        "\t.pgsize_bitmap = SZ_4K | SZ_16K | SZ_64K | SZ_256K | SZ_1M | SZ_4M |\n\t\t\t SZ_16M,",
        "", "obsolete ops bitmap")
    s=scoped_one(s,
        "#ifdef SEPERATE_DOMAIN_API", "#else",
        "\t.domain_alloc = sunxi_iommu_domain_alloc,",
        "\t.domain_alloc_paging = sunxi_iommu_domain_alloc_paging,","alloc ops")
    s=one(s,"\t.map = sunxi_iommu_map,","\t.map_pages = sunxi_iommu_map,","map ops")
    s=one(s,"\t.unmap = sunxi_iommu_unmap,","\t.unmap_pages = sunxi_iommu_unmap,","unmap ops")
    s=one(s,"\tsunxi_domain->domain.geometry.aperture_start = 0;",
        "\tsunxi_domain->domain.pgsize_bitmap = SZ_4K;\n\tsunxi_domain->domain.geometry.aperture_start = 0;",
        "domain page size")
    # Do not alter .remove on an unknown body: it has cleanup semantics.
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(s)
    diff="".join(difflib.unified_diff(before.splitlines(keepends=True),
                    s.splitlines(keepends=True),fromfile="vendor-v2.c",tofile="compile-stage2.c"))
    (a.out.parent/(a.out.name+".patch")).write_text(diff)
    print("CREATED (compile-only):",a.out)
    print("PATCH:",a.out.name+".patch")
    print("UNRESOLVED: platform remove callback, singleton-domain lifetime, hw_init errors, stream DMA and hardware tests")
if __name__=="__main__":main()
