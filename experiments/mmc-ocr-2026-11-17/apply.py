#!/usr/bin/env python3
"""Fail-closed Linux 6.18 MMC OCR diagnostic overlay. Python is build-host only."""
import argparse
from pathlib import Path
import shutil
import sys


def replace_once(s, old, new, path):
    n = s.count(old)
    if n != 1:
        raise ValueError(f'{path}: expected one anchor, found {n}: {old[:85]!r}')
    return s.replace(old, new, 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path, help='Linux source tree')
    p.add_argument('--variant', choices=('A', 'B'), required=True)
    a = p.parse_args()
    paths = [a.source/'drivers/mmc/core/core.c', a.source/'drivers/mmc/host/sunxi-mmc.c']
    raw = []
    for f in paths:
        if not f.is_file():
            sys.exit(f'Missing {f}')
        raw.append(f.read_text())
    c, h = raw
    if 'A733-OCR-DIAG' in c or 'A733-OCR-DIAG' in h:
        sys.exit('Already patched. Use a fresh tree for each variant.')
    c = replace_once(c, '\tocr &= host->ocr_avail;\n\tif (!ocr) {',
        '\t/* A733-OCR-DIAG: log actual card / host masks, no voltage override. */\n'
        '\tdev_warn(mmc_dev(host),\n'
        '\t\t "A733-OCR-DIAG select: card=%08x host=%08x overlap=%08x\\n",\n'
        '\t\t ocr, host->ocr_avail, ocr & host->ocr_avail);\n'
        '\tocr &= host->ocr_avail;\n\tif (!ocr) {', str(paths[0]))
    h = replace_once(h, '\tret = mmc_add_host(mmc);',
        '\t/* A733-OCR-DIAG: values before core add_host and regulator handling. */\n'
        '\tdev_warn(&pdev->dev,\n'
        '\t\t "A733-OCR-DIAG host: ocr=%08x sd=%08x mmc=%08x sdio=%08x caps=%08x\\n",\n'
        '\t\t mmc->ocr_avail, mmc->ocr_avail_sd, mmc->ocr_avail_mmc,\n'
        '\t\t mmc->ocr_avail_sdio, mmc->caps);\n'
        '\tret = mmc_add_host(mmc);', str(paths[1]))
    h = replace_once(h, '\tret = mmc_add_host(mmc);\n\tif (ret)\n\t\tgoto error_free_dma;',
        '\tret = mmc_add_host(mmc);\n\tif (ret)\n\t\tgoto error_free_dma;\n'
        '\tdev_warn(&pdev->dev,\n'
        '\t\t "A733-OCR-DIAG post-add: ocr=%08x sd=%08x mmc=%08x sdio=%08x\\n",\n'
        '\t\t mmc->ocr_avail, mmc->ocr_avail_sd,\n'
        '\t\t mmc->ocr_avail_mmc, mmc->ocr_avail_sdio);', str(paths[1]))
    if a.variant == 'B':
        # Narrow correction only for zero host OCR and explicit DT voltage-ranges.
        # Never force a 3.3V bit or override an existing nonzero supply mask.
        anchor = '\tret = mmc_of_parse(mmc);\n\tif (ret)\n\t\tgoto error_free_dma;'
        replacement = anchor + '''
    
	/* A733-OCR-DIAG B: honor an explicit voltage-ranges property only
	 * when the host currently has no OCR capability mask. No default
	 * voltage is invented; do not override a regulator-derived mask.
	 */
	if (!mmc->ocr_avail) {
		u32 range_ocr = 0;
		int voltage_ret = mmc_of_parse_voltage(mmc, &range_ocr);

		if (voltage_ret < 0) {
			ret = voltage_ret;
			goto error_free_dma;
		}
		if (voltage_ret > 0 && range_ocr) {
			mmc->ocr_avail = range_ocr;
			dev_warn(&pdev->dev,
				 "A733-OCR-DIAG B: using DT voltage-ranges mask=%08x\\n",
				 range_ocr);
		}
	}
'''
        h = replace_once(h, anchor, replacement, str(paths[1]))
    # Verify both anchors before writing any file.
    for f, result in zip(paths, (c, h)):
        shutil.copy2(f, f.with_suffix(f.suffix + '.ocr-original'))
        f.write_text(result)
    print(f'Applied variant {a.variant} to {a.source}')
    print('Saved *.c.ocr-original files. No DTB, bootloader, or images modified.')


if __name__ == '__main__':
    main()
