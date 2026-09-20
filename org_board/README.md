# الزمرة السادسة — Organizational Board

Print-ready Arabic organizational chart for foam-board production.

## Specifications

| Item | Value |
|------|--------|
| Trim size | **100 cm × 70 cm** (landscape) |
| Proportion | 100:70 (exact) |
| Bleed | 5 mm on all sides (print PDF / PNG) |
| Target resolution | 300 DPI |
| Title | الزمرة السادسة |
| Boxes | Exactly **13** blank boxes (rows 3 / 3 / 4 / 3) |

## Outputs

Generated into `output/`:

1. `zumra_al_sadisa_100x70cm_print.pdf` — vector PDF with 5 mm bleed (101 × 71 cm)
2. `zumra_al_sadisa_100x70cm_trim.pdf` — vector PDF exact trim (100 × 70 cm)
3. `zumra_al_sadisa_100x70cm_300dpi.png` — raster proof / backup @ 300 DPI with bleed
4. `zumra_al_sadisa_100x70cm_300dpi.tif` — TIFF backup @ 300 DPI
5. `zumra_al_sadisa_preview_100dpi.png` — quick preview

## Generate

```bash
cd org_board
pip install -r requirements.txt
python3 generate_board.py
```

## Design notes

- Dark navy title box with gold outline and chamfered corners
- Cream content boxes with navy border, gold accent, top decorative tabs
- Organizational connector lines with circular nodes
- UAE flag ribbon accents (top-left & bottom-right)
- Soft sky + faint UAE skyline (no aviation / defense imagery)
- No measurements, guides, placeholders, or extra text
