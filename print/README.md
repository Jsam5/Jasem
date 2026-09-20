# الزمرة السادسة — Print files

Print-ready org chart for **white cork / foam board**.

## Use this file

| File | Purpose |
|------|---------|
| `zumrah-al-sadisa-A3-print.pdf` | **Print master** (vector A3 landscape) |
| `zumrah-al-sadisa-A3-300dpi.png` | 300 DPI raster proof (4961×3508 px) |
| `zumrah-al-sadisa-A3-preview.png` | Screen preview |
| `source-org-chart.jpg` | Original low-res reference |

## Print settings (cork / foam board)

1. Open the **PDF** (preferred over PNG).
2. Paper / board size: **A3 landscape** (420 × 297 mm).
3. Scale: **100%** (no “fit to page”).
4. Quality: **300 DPI** / best quality.
5. Color: ask the shop for **CMYK** if they need it; the PDF is RGB-safe for most board printers.

The PDF is vector (boxes, lines, text, flags), so edges stay sharp. Only the soft Dubai skyline is a photo.

## Regenerate

```bash
python3 scripts/generate_org_chart_pdf.py
```
