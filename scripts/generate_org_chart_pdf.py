#!/usr/bin/env python3
"""Generate a print-ready A3 vector PDF of the UAE-themed org chart for cork-board printing."""

from __future__ import annotations

from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "print" / "source-org-chart.jpg"
OUT_PDF = ROOT / "print" / "zumrah-al-sadisa-A3-print.pdf"
OUT_PREVIEW = ROOT / "print" / "zumrah-al-sadisa-A3-preview.png"
OUT_PROOF = ROOT / "print" / "zumrah-al-sadisa-A3-300dpi.png"
BG_CACHE = ROOT / "print" / "_bg_soft.jpg"

# A3 landscape — print at 100%; vector artwork stays sharp at any size
PAGE_W = 420 * mm
PAGE_H = 297 * mm

NAVY = HexColor("#0B2A5B")
NAVY_LINE = HexColor("#123A7A")
GOLD = HexColor("#C9A227")
GOLD_DARK = HexColor("#8B6914")
GOLD_LIGHT = HexColor("#E8D48B")
CREAM = HexColor("#F5EED9")
FLAG_RED = HexColor("#CE1126")
FLAG_GREEN = HexColor("#009E49")
FLAG_BLACK = HexColor("#000000")

# Noto Kufi fails to paint glyphs via ReportLab; Sans Arabic matches the original look
ARABIC_FONT = "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"
pdfmetrics.registerFont(TTFont("ArabicBold", ARABIC_FONT))


def reshape_ar(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def prepare_background() -> Path:
    img = Image.open(SOURCE).convert("RGB")
    w, h = img.size
    sky = img.crop((0, int(h * 0.05), w, int(h * 0.95)))
    sky = sky.resize((4961, 3508), Image.Resampling.LANCZOS)
    sky = sky.filter(ImageFilter.GaussianBlur(radius=0.8))
    sky = ImageEnhance.Brightness(sky).enhance(1.15)
    sky = ImageEnhance.Color(sky).enhance(0.8)
    sky = ImageEnhance.Contrast(sky).enhance(0.9)
    sky.save(BG_CACHE, quality=92, optimize=True)
    return BG_CACHE


def chamfer_path(c: canvas.Canvas, x, y, w, h, cut):
    path = c.beginPath()
    path.moveTo(x + cut, y)
    path.lineTo(x + w - cut, y)
    path.lineTo(x + w, y + cut)
    path.lineTo(x + w, y + h - cut)
    path.lineTo(x + w - cut, y + h)
    path.lineTo(x + cut, y + h)
    path.lineTo(x, y + h - cut)
    path.lineTo(x, y + cut)
    path.close()
    return path


def chamfer_rect(c: canvas.Canvas, x, y, w, h, cut, fill=None, stroke=None, sw=1):
    path = chamfer_path(c, x, y, w, h, cut)
    if fill is not None:
        c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
        c.setLineWidth(sw)
    c.drawPath(path, fill=1 if fill is not None else 0, stroke=1 if stroke is not None else 0)


def draw_title_banner(c: canvas.Canvas, cx, top, width, height):
    x = cx - width / 2
    y = top - height
    cut = 9 * mm

    chamfer_rect(c, x - 1.3 * mm, y - 1.3 * mm, width + 2.6 * mm, height + 2.6 * mm, cut + 0.7 * mm, fill=GOLD_DARK)
    chamfer_rect(c, x - 0.5 * mm, y - 0.5 * mm, width + 1.0 * mm, height + 1.0 * mm, cut + 0.25 * mm, fill=GOLD_LIGHT)
    chamfer_rect(c, x, y, width, height, cut, fill=NAVY)
    chamfer_rect(
        c,
        x + 1.6 * mm,
        y + 1.6 * mm,
        width - 3.2 * mm,
        height - 3.2 * mm,
        cut - 1.3 * mm,
        stroke=GOLD,
        sw=1.5,
    )

    text = reshape_ar("الزمرة السادسة")
    c.setFillColor(white)
    c.setFont("ArabicBold", 26)
    # Vertically center baseline for Arabic (approx. optical center)
    baseline = y + (height / 2) - 7
    c.drawCentredString(cx, baseline, text)
    return cx, y


def draw_box(c: canvas.Canvas, x, y, w, h):
    cut = 2.2 * mm
    c.setFillColor(Color(0, 0, 0, alpha=0.07))
    chamfer_rect(c, x + 0.7 * mm, y - 0.7 * mm, w, h, cut, fill=Color(0, 0, 0, alpha=0.07))

    chamfer_rect(c, x, y, w, h, cut, fill=GOLD_DARK)
    chamfer_rect(c, x + 0.65 * mm, y + 0.65 * mm, w - 1.3 * mm, h - 1.3 * mm, cut - 0.35 * mm, fill=CREAM)
    chamfer_rect(
        c,
        x + 1.45 * mm,
        y + 1.45 * mm,
        w - 2.9 * mm,
        h - 2.9 * mm,
        cut - 0.75 * mm,
        stroke=GOLD,
        sw=1.05,
    )

    tab_w = w * 0.2
    tab_h = 2.2 * mm
    tx = x + (w - tab_w) / 2
    ty = y + h - 0.35 * mm
    c.setFillColor(NAVY)
    path = c.beginPath()
    path.moveTo(tx, ty)
    path.lineTo(tx + tab_w, ty)
    path.lineTo(tx + tab_w - 1.1 * mm, ty + tab_h)
    path.lineTo(tx + 1.1 * mm, ty + tab_h)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def draw_uae_flag_panel(c: canvas.Canvas, x, y, w, h, mirror=False):
    c.saveState()
    if mirror:
        c.translate(x + w, y)
        c.scale(-1, 1)
        ox, oy = 0, 0
    else:
        ox, oy = x, y

    # Gold frame plate
    c.setFillColor(GOLD_DARK)
    path = c.beginPath()
    path.moveTo(ox, oy + h)
    path.lineTo(ox + w * 0.7, oy + h)
    path.curveTo(ox + w * 1.02, oy + h, ox + w * 1.0, oy + h * 0.5, ox + w * 0.9, oy + h * 0.18)
    path.curveTo(ox + w * 0.82, oy - 1 * mm, ox + w * 0.4, oy, ox, oy)
    path.close()
    c.drawPath(path, fill=1, stroke=0)

    inset = 2.4 * mm
    c.setFillColor(GOLD_LIGHT)
    path = c.beginPath()
    path.moveTo(ox + inset * 0.25, oy + h - inset)
    path.lineTo(ox + w * 0.66, oy + h - inset)
    path.curveTo(ox + w - inset * 0.2, oy + h - inset, ox + w - inset * 0.4, oy + h * 0.5, ox + w * 0.86, oy + h * 0.22)
    path.curveTo(ox + w * 0.78, oy + inset * 0.6, ox + w * 0.4, oy + inset, ox + inset * 0.25, oy + inset)
    path.close()
    c.drawPath(path, fill=1, stroke=0)

    fx = ox + inset * 0.9
    fy = oy + inset * 1.15
    fw = w * 0.74
    fh = h - inset * 2.4
    stripe = fh / 3.0

    c.saveState()
    clip = c.beginPath()
    clip.rect(fx, fy, fw, fh)
    c.clipPath(clip, stroke=0, fill=0)
    c.setFillColor(FLAG_GREEN)
    c.rect(fx, fy + 2 * stripe, fw, stripe + 0.5, fill=1, stroke=0)
    c.setFillColor(white)
    c.rect(fx, fy + stripe, fw, stripe + 0.5, fill=1, stroke=0)
    c.setFillColor(FLAG_BLACK)
    c.rect(fx, fy, fw, stripe + 0.5, fill=1, stroke=0)
    c.setFillColor(FLAG_RED)
    c.rect(fx, fy, fw * 0.27, fh, fill=1, stroke=0)
    c.restoreState()

    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    path = c.beginPath()
    path.moveTo(ox + inset * 0.25, oy + h - inset)
    path.lineTo(ox + w * 0.66, oy + h - inset)
    path.curveTo(ox + w - inset * 0.2, oy + h - inset, ox + w - inset * 0.4, oy + h * 0.5, ox + w * 0.86, oy + h * 0.22)
    path.curveTo(ox + w * 0.78, oy + inset * 0.6, ox + w * 0.4, oy + inset, ox + inset * 0.25, oy + inset)
    c.drawPath(path, fill=0, stroke=1)
    c.restoreState()


def layout_rows():
    margin_x = 26 * mm
    usable_w = PAGE_W - 2 * margin_x
    box_h = 23 * mm
    box_w_3 = 80 * mm
    box_w_4 = 70 * mm
    gap_y = 16 * mm
    top_y = PAGE_H - 72 * mm

    rows_spec = [(3, box_w_3), (3, box_w_3), (4, box_w_4), (3, box_w_3)]
    rows = []
    for i, (n, bw) in enumerate(rows_spec):
        y = top_y - i * (box_h + gap_y) - box_h
        total = n * bw
        gap = (usable_w - total) / (n + 1)
        rows.append([(margin_x + gap + j * (bw + gap), y, bw, box_h) for j in range(n)])
    return rows


def box_center_x(box):
    x, _, w, _ = box
    return x + w / 2


def box_top(box):
    _, y, _, h = box
    return y + h


def box_bottom(box):
    return box[1]


def draw_connectors(c: canvas.Canvas, banner_cx, banner_bottom_y, rows):
    """Clean tree: spine + horizontal rails above each row (matches original)."""
    c.setStrokeColor(NAVY_LINE)
    c.setLineWidth(1.4)
    c.setLineCap(1)
    c.setLineJoin(1)

    spine_x = banner_cx
    rail_gap = 8.5 * mm

    for i, row in enumerate(rows):
        centers = [box_center_x(b) for b in row]
        rail_y = box_top(row[0]) + rail_gap

        if i == 0:
            c.line(spine_x, banner_bottom_y, spine_x, rail_y)
        else:
            prev = rows[i - 1]
            # Drop from previous row bottoms into a merge rail, then down to this rail
            merge_y = box_bottom(prev[0]) - 5 * mm
            prev_centers = [box_center_x(b) for b in prev]
            for pcx in prev_centers:
                c.line(pcx, box_bottom(rows[i - 1][0]), pcx, merge_y)
            c.line(min(prev_centers), merge_y, max(prev_centers), merge_y)
            c.line(spine_x, merge_y, spine_x, rail_y)

        c.line(min(centers), rail_y, max(centers), rail_y)
        for cx in centers:
            c.line(cx, rail_y, cx, box_top(row[0]))


def build_pdf():
    bg = prepare_background()
    c = canvas.Canvas(str(OUT_PDF), pagesize=(PAGE_W, PAGE_H))
    c.setTitle("الزمرة السادسة — A3 Print Ready")
    c.setAuthor("Jasem")
    c.setSubject("Org chart for white cork / foam board — vector PDF, print at 100%, 300 DPI")

    c.drawImage(str(bg), 0, 0, width=PAGE_W, height=PAGE_H, preserveAspectRatio=False, mask="auto")
    c.setFillColor(Color(1, 1, 1, alpha=0.22))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    draw_uae_flag_panel(c, -3 * mm, PAGE_H - 82 * mm, 100 * mm, 84 * mm, mirror=False)
    draw_uae_flag_panel(c, PAGE_W - 97 * mm, -4 * mm, 100 * mm, 84 * mm, mirror=True)

    banner_cx, banner_bottom = draw_title_banner(c, PAGE_W / 2, PAGE_H - 16 * mm, 124 * mm, 30 * mm)

    rows = layout_rows()
    draw_connectors(c, banner_cx, banner_bottom, rows)
    for row in rows:
        for box in row:
            draw_box(c, *box)

    c.setFillColor(Color(0.15, 0.2, 0.3, alpha=0.45))
    c.setFont("Helvetica", 5.5)
    c.drawString(
        7 * mm,
        3.5 * mm,
        "A3 landscape · vector PDF · print at 100% · 300 DPI · white cork / foam board",
    )

    c.showPage()
    c.save()
    print(f"Wrote {OUT_PDF}")


def render_previews():
    import pymupdf as fitz

    doc = fitz.open(OUT_PDF)
    page = doc[0]
    for dpi, path in [(150, OUT_PREVIEW), (300, OUT_PROOF)]:
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        pix.save(str(path))
        print(f"Wrote {path} ({pix.width}x{pix.height})")


if __name__ == "__main__":
    build_pdf()
    render_previews()
