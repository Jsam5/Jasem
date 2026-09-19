#!/usr/bin/env python3
"""
Generate a print-ready Arabic organizational board.
Final trim size: 100 cm × 70 cm (landscape).
Exports: PDF (vector), PNG (high-resolution), optional TIFF.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.colors import CMYKColor, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas

# Allow large print-resolution images (100 cm × 70 cm @ 300 DPI)
Image.MAX_IMAGE_PIXELS = 200_000_000

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
OUTPUT = ROOT / "output"

TITLE_AR = "الزمرة السادسة"
FONT_PATH = FONTS / "NotoKufiArabic-Bold.ttf"

# Physical size (trim)
TRIM_W_CM = 100.0
TRIM_H_CM = 70.0
BLEED_CM = 0.5  # 5 mm bleed each side

# Layout proportions (internal, never drawn as labels)
TITLE_W_CM = 22.0
TITLE_H_CM = 8.0
BOX_W_CM = 14.0
BOX_H_CM = 6.0
H_GAP_CM = 1.75  # ~1.5–2 cm between boxes

# Colors (RGB 0–255)
NAVY = (12, 32, 68)
NAVY_DEEP = (8, 24, 52)
GOLD = (196, 162, 78)
GOLD_LIGHT = (220, 190, 110)
CREAM = (250, 246, 236)
CREAM_EDGE = (238, 230, 214)
SKY_TOP = (214, 230, 242)
SKY_MID = (236, 244, 250)
SKY_BOT = (248, 250, 252)
SKYLINE = (210, 220, 230)
UAE_RED = (255, 0, 0)
UAE_GREEN = (0, 115, 47)
UAE_WHITE = (255, 255, 255)
UAE_BLACK = (0, 0, 0)
LINE = (12, 32, 68)

RowSpec = List[int]  # boxes per row
ROWS: RowSpec = [3, 3, 4, 3]  # exactly 13


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

Point = Tuple[float, float]


def cm_to_pt(cm: float) -> float:
    return cm * 72.0 / 2.54


def chamfer_polygon(x: float, y: float, w: float, h: float, c: float) -> List[Point]:
    """Axis-aligned rectangle with chamfered (cut) corners. y is top."""
    return [
        (x + c, y),
        (x + w - c, y),
        (x + w, y + c),
        (x + w, y + h - c),
        (x + w - c, y + h),
        (x + c, y + h),
        (x, y + h - c),
        (x, y + c),
    ]


def poly_flat(pts: Sequence[Point]) -> List[float]:
    out: List[float] = []
    for px, py in pts:
        out.extend([px, py])
    return out


@dataclass
class Box:
    x: float  # left, cm from left of trim
    y: float  # top, cm from top of trim
    w: float
    h: float
    is_title: bool = False

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def tab_anchor(self) -> Point:
        """Connection point at decorative tab top-center."""
        tab_h = 0.55 if not self.is_title else 0.0
        return (self.cx, self.y - tab_h if not self.is_title else self.y)


def compute_layout() -> Tuple[Box, List[List[Box]]]:
    """Return title box and rows of content boxes in trim coordinates (cm, top-left origin)."""
    title = Box(
        x=(TRIM_W_CM - TITLE_W_CM) / 2.0,
        y=2.35,
        w=TITLE_W_CM,
        h=TITLE_H_CM,
        is_title=True,
    )

    # Vertical rhythm under title
    row_tops = [13.55, 23.85, 34.15, 44.45]  # tuned for even spacing + connector room
    assert len(row_tops) == 4

    rows: List[List[Box]] = []
    for n, top in zip(ROWS, row_tops):
        total_w = n * BOX_W_CM + (n - 1) * H_GAP_CM
        start = (TRIM_W_CM - total_w) / 2.0
        row: List[Box] = []
        for i in range(n):
            row.append(
                Box(
                    x=start + i * (BOX_W_CM + H_GAP_CM),
                    y=top,
                    w=BOX_W_CM,
                    h=BOX_H_CM,
                )
            )
        rows.append(row)

    assert sum(len(r) for r in rows) == 13
    return title, rows


# ---------------------------------------------------------------------------
# Drawing – Pillow (raster PNG / TIFF)
# ---------------------------------------------------------------------------

class RasterBoard:
    def __init__(self, dpi: int = 300, with_bleed: bool = True):
        self.dpi = dpi
        self.with_bleed = with_bleed
        self.bleed = BLEED_CM if with_bleed else 0.0
        self.page_w_cm = TRIM_W_CM + 2 * self.bleed
        self.page_h_cm = TRIM_H_CM + 2 * self.bleed
        self.scale = dpi / 2.54  # px per cm
        self.w = int(round(self.page_w_cm * self.scale))
        self.h = int(round(self.page_h_cm * self.scale))
        self.img = Image.new("RGB", (self.w, self.h), SKY_BOT)
        self.draw = ImageDraw.Draw(self.img)
        self.title_box, self.rows = compute_layout()
        self.font = ImageFont.truetype(str(FONT_PATH), size=max(24, int(3.15 * self.scale)))

    def px(self, cm_x: float, cm_y: float) -> Tuple[int, int]:
        """Trim-cm (top-left origin) → pixel including bleed offset."""
        x = (cm_x + self.bleed) * self.scale
        y = (cm_y + self.bleed) * self.scale
        return int(round(x)), int(round(y))

    def s(self, cm: float) -> int:
        return int(round(cm * self.scale))

    def render(self) -> Image.Image:
        self._paint_sky()
        self._paint_skyline()
        self._paint_flag_ribbons()
        self._paint_connectors()
        self._paint_title()
        for row in self.rows:
            for box in row:
                self._paint_content_box(box)
        return self.img

    # -- background ---------------------------------------------------------

    def _paint_sky(self) -> None:
        # Soft vertical gradient
        for y in range(self.h):
            t = y / max(1, self.h - 1)
            if t < 0.45:
                u = t / 0.45
                c = _lerp_rgb(SKY_TOP, SKY_MID, u)
            else:
                u = (t - 0.45) / 0.55
                c = _lerp_rgb(SKY_MID, SKY_BOT, u)
            self.draw.line([(0, y), (self.w, y)], fill=c)

        # Soft cloud veils (very subtle)
        overlay = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        clouds = [
            (0.12, 0.10, 0.28, 0.08),
            (0.55, 0.06, 0.32, 0.07),
            (0.30, 0.18, 0.25, 0.06),
            (0.70, 0.22, 0.22, 0.05),
        ]
        for cx, cy, rw, rh in clouds:
            x0 = int((cx - rw / 2) * self.w)
            y0 = int((cy - rh / 2) * self.h)
            x1 = int((cx + rw / 2) * self.w)
            y1 = int((cy + rh / 2) * self.h)
            od.ellipse([x0, y0, x1, y1], fill=(255, 255, 255, 55))
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=max(2, self.s(0.8))))
        self.img = Image.alpha_composite(self.img.convert("RGBA"), overlay).convert("RGB")
        self.draw = ImageDraw.Draw(self.img)

    def _paint_skyline(self) -> None:
        """Faint UAE skyline silhouette along the lower area."""
        base_y = self.px(0, 58.5)[1]
        ground = self.px(0, TRIM_H_CM)[1]
        # Building footprints as (left_cm, width_cm, height_cm) relative to baseline
        buildings = [
            (4, 2.2, 6.5),
            (7, 1.6, 9.0),
            (9.2, 2.8, 5.5),
            (13, 1.4, 11.5),  # tall tower suggestion
            (15, 0.55, 16.5),  # Burj-like needle
            (15.7, 1.8, 8.0),
            (19, 2.4, 6.0),
            (23, 1.5, 10.0),
            (25.2, 3.0, 4.8),
            (30, 2.0, 7.5),
            (33, 1.2, 12.0),
            (35, 2.6, 5.2),
            (40, 1.8, 9.5),
            (43, 0.7, 14.0),
            (44.2, 2.2, 7.0),
            (48, 2.8, 5.0),
            (53, 1.5, 10.5),
            (55.5, 2.4, 6.2),
            (60, 1.3, 11.0),
            (62, 0.5, 15.5),
            (63, 2.0, 8.5),
            (67, 2.5, 5.5),
            (72, 1.6, 9.0),
            (75, 2.2, 6.8),
            (79, 1.1, 12.5),
            (81, 2.8, 4.5),
            (86, 1.8, 8.0),
            (90, 2.4, 6.0),
            (94, 1.5, 9.5),
        ]
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        fill = (*SKYLINE, 70)
        for left, bw, bh in buildings:
            x0, _ = self.px(left, 0)
            x1, _ = self.px(left + bw, 0)
            y0 = base_y - self.s(bh)
            # Simple stepped tower tops for a few
            ld.rectangle([x0, y0, x1, ground], fill=fill)
            if bh > 13:
                # Needle tip
                tip = y0 - self.s(bh * 0.25)
                mid = (x0 + x1) // 2
                ld.polygon([(mid, tip), (x0, y0), (x1, y0)], fill=fill)
        # Soft ground haze
        ld.rectangle(
            [0, base_y - self.s(1.5), self.w, ground],
            fill=(245, 248, 250, 90),
        )
        self.img = Image.alpha_composite(self.img.convert("RGBA"), layer).convert("RGB")
        self.draw = ImageDraw.Draw(self.img)

    def _paint_flag_ribbons(self) -> None:
        # Flowing fabric-like spines kept in corners so the chart stays clear
        tl = _bezier_spine(
            [
                (-5.0, -4.0),
                (0.5, -0.5),
                (7.5, 2.2),
                (13.5, 6.5),
                (18.5, 12.0),
                (22.0, 18.5),
                (24.0, 24.5),
            ],
            n=64,
        )
        br = _bezier_spine(
            [
                (105.5, 74.5),
                (100.0, 71.5),
                (93.5, 68.0),
                (87.0, 63.5),
                (81.5, 58.0),
                (77.5, 52.5),
                (75.0, 47.5),
            ],
            n=64,
        )
        self._ribbon(spine=tl, width=7.6, wave=1.25)
        self._ribbon(spine=br, width=7.6, wave=1.25)

    def _ribbon(
        self,
        spine: Sequence[Point],
        width: float,
        wave: float,
    ) -> None:
        """Draw a flowing UAE flag ribbon along a spine (cm trim coords)."""
        dense = list(spine)
        left_edge, right_edge = _offset_ribbon(dense, width / 2, wave)

        # UAE flag across ribbon width: red hoist, then green / white / black
        bands = [
            (0.00, 0.22, UAE_RED),
            (0.22, 0.48, UAE_GREEN),
            (0.48, 0.74, UAE_WHITE),
            (0.74, 1.00, UAE_BLACK),
        ]
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)

        for a, b, color in bands:
            e0 = _lerp_edge(left_edge, right_edge, a)
            e1 = _lerp_edge(left_edge, right_edge, b)
            poly = e0 + list(reversed(e1))
            pix = [self.px(x, y) for x, y in poly]
            ld.polygon(pix, fill=(*color, 240))

        # Soft rounded end caps for fabric feel
        for edge_pt, opp_pt in (
            (left_edge[0], right_edge[0]),
            (left_edge[-1], right_edge[-1]),
        ):
            mx = (edge_pt[0] + opp_pt[0]) / 2
            my = (edge_pt[1] + opp_pt[1]) / 2
            rr = max(2, self.s(width * 0.28))
            cx, cy = self.px(mx, my)
            ld.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(*GOLD, 90))

        # Gold trim along outer edges
        lw = max(2, self.s(0.14))
        ld.line([self.px(x, y) for x, y in left_edge], fill=(*GOLD, 230), width=lw)
        ld.line([self.px(x, y) for x, y in right_edge], fill=(*GOLD, 230), width=lw)

        # Soft fold shading / highlight for fabric depth
        mid = _lerp_edge(left_edge, right_edge, 0.5)
        shade = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shade)
        for i in range(0, len(mid) - 1, 2):
            x0, y0 = self.px(*mid[i])
            amp = 0.55 + 0.25 * math.sin(i / max(1, len(mid) - 1) * math.pi * 2)
            sd.ellipse(
                [x0 - self.s(amp), y0 - self.s(0.28), x0 + self.s(amp), y0 + self.s(0.28)],
                fill=(0, 0, 0, 22),
            )
            hx, hy = self.px(*_lerp_edge(left_edge, right_edge, 0.18)[i])
            sd.ellipse(
                [hx - self.s(0.35), hy - self.s(0.18), hx + self.s(0.35), hy + self.s(0.18)],
                fill=(255, 255, 255, 28),
            )
        shade = shade.filter(ImageFilter.GaussianBlur(radius=max(1, self.s(0.4))))
        layer = Image.alpha_composite(layer, shade)
        # Slight edge blur for cloth softness without losing stripe clarity
        layer = Image.alpha_composite(
            Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0)),
            layer,
        )
        self.img = Image.alpha_composite(self.img.convert("RGBA"), layer).convert("RGB")
        self.draw = ImageDraw.Draw(self.img)

    # -- chart ---------------------------------------------------------------

    def _paint_connectors(self) -> None:
        title = self.title_box
        stroke = max(2, self.s(0.09))
        node_r = max(3, self.s(0.22))

        # Drop from title bottom-center
        t_cx, t_bot = title.cx, title.bottom
        row1 = self.rows[0]
        # Junction above row 1
        j1_y = row1[0].tab_anchor[1] - 1.35

        self._line((t_cx, t_bot), (t_cx, j1_y), stroke)
        self._hline_nodes([b.cx for b in row1], j1_y, stroke, node_r)
        for b in row1:
            ax, ay = b.tab_anchor
            self._line((b.cx, j1_y), (ax, ay), stroke)
            self._node(b.cx, j1_y, node_r)

        # Between subsequent rows: from center spine + row bus
        for ri in range(len(self.rows) - 1):
            upper = self.rows[ri]
            lower = self.rows[ri + 1]
            # Collect drop points from upper boxes → shared bus → lower tabs
            bus_y = (upper[0].bottom + lower[0].tab_anchor[1]) / 2.0
            # Verticals from each upper box bottom-center down to bus
            for b in upper:
                self._line((b.cx, b.bottom), (b.cx, bus_y), stroke)
                self._node(b.cx, bus_y, node_r)
            # Horizontal bus spanning union of upper and lower centers
            xs = sorted({b.cx for b in upper} | {b.cx for b in lower})
            self._line((xs[0], bus_y), (xs[-1], bus_y), stroke)
            for b in lower:
                ax, ay = b.tab_anchor
                self._line((b.cx, bus_y), (ax, ay), stroke)
                self._node(b.cx, bus_y, node_r)
            # Center spine node
            self._node(TRIM_W_CM / 2.0, bus_y, node_r)

        # Title junction node
        self._node(t_cx, j1_y, node_r)
        self._node(t_cx, t_bot, node_r)

    def _line(self, a: Point, b: Point, stroke: int) -> None:
        self.draw.line([self.px(*a), self.px(*b)], fill=LINE, width=stroke)

    def _hline_nodes(self, xs: Sequence[float], y: float, stroke: int, node_r: int) -> None:
        self._line((xs[0], y), (xs[-1], y), stroke)

    def _node(self, x: float, y: float, r: int) -> None:
        cx, cy = self.px(x, y)
        self.draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=NAVY, outline=GOLD, width=max(1, r // 4))

    def _paint_title(self) -> None:
        b = self.title_box
        chamfer = 0.55
        pts = chamfer_polygon(b.x, b.y, b.w, b.h, chamfer)
        pix = [self.px(x, y) for x, y in pts]

        # Outer gold outline (slightly expanded)
        expand = 0.12
        outer = chamfer_polygon(b.x - expand, b.y - expand, b.w + 2 * expand, b.h + 2 * expand, chamfer + 0.05)
        self.draw.polygon([self.px(x, y) for x, y in outer], fill=GOLD)

        # Navy fill
        self.draw.polygon(pix, fill=NAVY)

        # Inner gold accent line
        inset = 0.28
        inner = chamfer_polygon(b.x + inset, b.y + inset, b.w - 2 * inset, b.h - 2 * inset, max(0.2, chamfer - 0.15))
        self.draw.polygon([self.px(x, y) for x, y in inner], outline=GOLD_LIGHT, width=max(2, self.s(0.08)))

        # Soft bevel hint (top edge lighter)
        bevel = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bevel)
        top_band = chamfer_polygon(b.x + 0.2, b.y + 0.15, b.w - 0.4, b.h * 0.22, 0.25)
        bd.polygon([self.px(x, y) for x, y in top_band], fill=(255, 255, 255, 28))
        self.img = Image.alpha_composite(self.img.convert("RGBA"), bevel).convert("RGB")
        self.draw = ImageDraw.Draw(self.img)

        # Arabic title
        cx, cy = self.px(b.cx, b.y + b.h / 2)
        self._draw_arabic_centered(TITLE_AR, cx, cy, self.font, fill=(255, 255, 255))

    def _paint_content_box(self, b: Box) -> None:
        chamfer = 0.35
        tab_w, tab_h = 1.35, 0.55

        # Decorative tab (behind / on top edge)
        tab_x = b.cx - tab_w / 2
        tab_y = b.y - tab_h
        tab_pts = [
            (tab_x + 0.15, tab_y),
            (tab_x + tab_w - 0.15, tab_y),
            (tab_x + tab_w, tab_y + tab_h),
            (tab_x, tab_y + tab_h),
        ]
        # Gold outline under tab
        self.draw.polygon([self.px(x, y) for x, y in tab_pts], fill=GOLD)
        inset_tab = [
            (tab_x + 0.22, tab_y + 0.08),
            (tab_x + tab_w - 0.22, tab_y + 0.08),
            (tab_x + tab_w - 0.08, tab_y + tab_h),
            (tab_x + 0.08, tab_y + tab_h),
        ]
        self.draw.polygon([self.px(x, y) for x, y in inset_tab], fill=NAVY)

        # Gold outer ring
        expand = 0.08
        outer = chamfer_polygon(b.x - expand, b.y - expand, b.w + 2 * expand, b.h + 2 * expand, chamfer + 0.04)
        self.draw.polygon([self.px(x, y) for x, y in outer], fill=GOLD)

        # Navy border body then cream fill via inset
        body = chamfer_polygon(b.x, b.y, b.w, b.h, chamfer)
        self.draw.polygon([self.px(x, y) for x, y in body], fill=NAVY)

        inset = 0.18
        inner = chamfer_polygon(b.x + inset, b.y + inset, b.w - 2 * inset, b.h - 2 * inset, max(0.12, chamfer - 0.1))
        self.draw.polygon([self.px(x, y) for x, y in inner], fill=CREAM)

        # Thin gold accent inside
        g_inset = 0.32
        g_inner = chamfer_polygon(
            b.x + g_inset, b.y + g_inset, b.w - 2 * g_inset, b.h - 2 * g_inset, max(0.08, chamfer - 0.18)
        )
        self.draw.polygon(
            [self.px(x, y) for x, y in g_inner],
            outline=GOLD,
            width=max(1, self.s(0.05)),
        )

        # Soft top bevel on cream
        bevel = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bevel)
        band = chamfer_polygon(b.x + 0.35, b.y + 0.3, b.w - 0.7, b.h * 0.2, 0.12)
        bd.polygon([self.px(x, y) for x, y in band], fill=(255, 255, 255, 40))
        self.img = Image.alpha_composite(self.img.convert("RGBA"), bevel).convert("RGB")
        self.draw = ImageDraw.Draw(self.img)

    def _draw_arabic_centered(self, text: str, cx: int, cy: int, font: ImageFont.FreeTypeFont, fill) -> None:
        # Pillow RTL shaping (connected Arabic)
        bbox = self.draw.textbbox((0, 0), text, font=font, direction="rtl", language="ar")
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = cx - tw // 2 - bbox[0]
        y = cy - th // 2 - bbox[1]
        self.draw.text((x, y), text, font=font, fill=fill, direction="rtl", language="ar")


# ---------------------------------------------------------------------------
# Drawing – ReportLab PDF (vector)
# ---------------------------------------------------------------------------

class VectorBoard:
    def __init__(self, with_bleed: bool = True):
        self.with_bleed = with_bleed
        self.bleed = BLEED_CM if with_bleed else 0.0
        self.page_w = cm_to_pt(TRIM_W_CM + 2 * self.bleed)
        self.page_h = cm_to_pt(TRIM_H_CM + 2 * self.bleed)
        self.title_box, self.rows = compute_layout()
        pdfmetrics.registerFont(TTFont("NotoKufiBold", str(FONT_PATH)))

    def _c(self, cm_x: float, cm_y_top: float) -> Tuple[float, float]:
        """Trim cm (top-left) → PDF points (bottom-left origin) with bleed."""
        x = cm_to_pt(cm_x + self.bleed)
        y = cm_to_pt(TRIM_H_CM - cm_y_top + self.bleed)
        return x, y

    def _s(self, cm: float) -> float:
        return cm_to_pt(cm)

    def export(self, path: Path) -> None:
        c = pdf_canvas.Canvas(str(path), pagesize=(self.page_w, self.page_h))
        c.setTitle("الزمرة السادسة — Organizational Board")
        c.setAuthor("Org Board Generator")
        c.setSubject("Print-ready foam board 100cm x 70cm")

        self._sky(c)
        self._skyline(c)
        self._ribbons(c)
        self._connectors(c)
        self._title(c)
        for row in self.rows:
            for box in row:
                self._content_box(c, box)

        # Trim box mark (hairline outside content, optional — skip to keep clean)
        c.showPage()
        c.save()

    def _sky(self, c: pdf_canvas.Canvas) -> None:
        steps = 80
        for i in range(steps):
            t0 = i / steps
            t1 = (i + 1) / steps
            if t0 < 0.45:
                u = t0 / 0.45
                rgb = _lerp_rgb(SKY_TOP, SKY_MID, u)
            else:
                u = (t0 - 0.45) / 0.55
                rgb = _lerp_rgb(SKY_MID, SKY_BOT, u)
            y1 = self.page_h * (1 - t0)
            y0 = self.page_h * (1 - t1)
            c.setFillColor(Color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255))
            c.rect(0, y0, self.page_w, y1 - y0, fill=1, stroke=0)

    def _skyline(self, c: pdf_canvas.Canvas) -> None:
        buildings = [
            (4, 2.2, 6.5), (7, 1.6, 9.0), (9.2, 2.8, 5.5), (13, 1.4, 11.5),
            (15, 0.55, 16.5), (15.7, 1.8, 8.0), (19, 2.4, 6.0), (23, 1.5, 10.0),
            (25.2, 3.0, 4.8), (30, 2.0, 7.5), (33, 1.2, 12.0), (35, 2.6, 5.2),
            (40, 1.8, 9.5), (43, 0.7, 14.0), (44.2, 2.2, 7.0), (48, 2.8, 5.0),
            (53, 1.5, 10.5), (55.5, 2.4, 6.2), (60, 1.3, 11.0), (62, 0.5, 15.5),
            (63, 2.0, 8.5), (67, 2.5, 5.5), (72, 1.6, 9.0), (75, 2.2, 6.8),
            (79, 1.1, 12.5), (81, 2.8, 4.5), (86, 1.8, 8.0), (90, 2.4, 6.0),
            (94, 1.5, 9.5),
        ]
        base_top = 58.5
        c.setFillColor(Color(SKYLINE[0] / 255, SKYLINE[1] / 255, SKYLINE[2] / 255, alpha=0.28))
        for left, bw, bh in buildings:
            x0, y_base = self._c(left, TRIM_H_CM)
            x1, _ = self._c(left + bw, TRIM_H_CM)
            _, y_top = self._c(left, base_top - bh)
            c.rect(x0, y_base, x1 - x0, y_top - y_base, fill=1, stroke=0)
            if bh > 13:
                tip_y = y_top + self._s(bh * 0.25)
                mid = (x0 + x1) / 2
                p = c.beginPath()
                p.moveTo(mid, tip_y)
                p.lineTo(x0, y_top)
                p.lineTo(x1, y_top)
                p.close()
                c.drawPath(p, fill=1, stroke=0)

    def _ribbons(self, c: pdf_canvas.Canvas) -> None:
        tl = _bezier_spine(
            [
                (-5.0, -4.0),
                (0.5, -0.5),
                (7.5, 2.2),
                (13.5, 6.5),
                (18.5, 12.0),
                (22.0, 18.5),
                (24.0, 24.5),
            ],
            n=64,
        )
        br = _bezier_spine(
            [
                (105.5, 74.5),
                (100.0, 71.5),
                (93.5, 68.0),
                (87.0, 63.5),
                (81.5, 58.0),
                (77.5, 52.5),
                (75.0, 47.5),
            ],
            n=64,
        )
        self._ribbon_pdf(c, spine=tl, width=7.6, wave=1.25)
        self._ribbon_pdf(c, spine=br, width=7.6, wave=1.25)

    def _ribbon_pdf(self, c: pdf_canvas.Canvas, spine: Sequence[Point], width: float, wave: float) -> None:
        dense = list(spine)
        left_edge, right_edge = _offset_ribbon(dense, width / 2, wave)
        bands = [
            (0.00, 0.22, UAE_RED),
            (0.22, 0.48, UAE_GREEN),
            (0.48, 0.74, UAE_WHITE),
            (0.74, 1.00, UAE_BLACK),
        ]
        for a, b, color in bands:
            e0 = _lerp_edge(left_edge, right_edge, a)
            e1 = _lerp_edge(left_edge, right_edge, b)
            poly = e0 + list(reversed(e1))
            p = c.beginPath()
            x0, y0 = self._c(*poly[0])
            p.moveTo(x0, y0)
            for pt in poly[1:]:
                x, y = self._c(*pt)
                p.lineTo(x, y)
            p.close()
            c.setFillColor(Color(color[0] / 255, color[1] / 255, color[2] / 255, alpha=0.94))
            c.drawPath(p, fill=1, stroke=0)
        # Gold edges
        c.setStrokeColor(Color(GOLD[0] / 255, GOLD[1] / 255, GOLD[2] / 255))
        c.setLineWidth(self._s(0.14))
        c.setLineCap(1)
        c.setLineJoin(1)
        for edge in (left_edge, right_edge):
            p = c.beginPath()
            x0, y0 = self._c(*edge[0])
            p.moveTo(x0, y0)
            for pt in edge[1:]:
                x, y = self._c(*pt)
                p.lineTo(x, y)
            c.drawPath(p, fill=0, stroke=1)

    def _connectors(self, c: pdf_canvas.Canvas) -> None:
        title = self.title_box
        c.setStrokeColor(Color(LINE[0] / 255, LINE[1] / 255, LINE[2] / 255))
        c.setFillColor(Color(NAVY[0] / 255, NAVY[1] / 255, NAVY[2] / 255))
        c.setLineWidth(self._s(0.09))
        c.setLineCap(1)
        c.setLineJoin(1)

        t_cx, t_bot = title.cx, title.bottom
        row1 = self.rows[0]
        j1_y = row1[0].tab_anchor[1] - 1.35

        self._pdf_line(c, (t_cx, t_bot), (t_cx, j1_y))
        self._pdf_line(c, (row1[0].cx, j1_y), (row1[-1].cx, j1_y))
        for b in row1:
            self._pdf_line(c, (b.cx, j1_y), b.tab_anchor)
            self._pdf_node(c, b.cx, j1_y)

        for ri in range(len(self.rows) - 1):
            upper = self.rows[ri]
            lower = self.rows[ri + 1]
            bus_y = (upper[0].bottom + lower[0].tab_anchor[1]) / 2.0
            for b in upper:
                self._pdf_line(c, (b.cx, b.bottom), (b.cx, bus_y))
                self._pdf_node(c, b.cx, bus_y)
            xs = sorted({b.cx for b in upper} | {b.cx for b in lower})
            self._pdf_line(c, (xs[0], bus_y), (xs[-1], bus_y))
            for b in lower:
                self._pdf_line(c, (b.cx, bus_y), b.tab_anchor)
                self._pdf_node(c, b.cx, bus_y)
            self._pdf_node(c, TRIM_W_CM / 2.0, bus_y)

        self._pdf_node(c, t_cx, j1_y)
        self._pdf_node(c, t_cx, t_bot)

    def _pdf_line(self, c: pdf_canvas.Canvas, a: Point, b: Point) -> None:
        x0, y0 = self._c(*a)
        x1, y1 = self._c(*b)
        # Convert top-based y carefully: _c already converts using top coordinate
        # For bottom of box we pass top-origin y which increases downward — correct.
        c.line(x0, y0, x1, y1)

    def _pdf_node(self, c: pdf_canvas.Canvas, x: float, y: float) -> None:
        px, py = self._c(x, y)
        r = self._s(0.22)
        c.setFillColor(Color(NAVY[0] / 255, NAVY[1] / 255, NAVY[2] / 255))
        c.circle(px, py, r, fill=1, stroke=0)
        c.setStrokeColor(Color(GOLD[0] / 255, GOLD[1] / 255, GOLD[2] / 255))
        c.setLineWidth(self._s(0.05))
        c.circle(px, py, r, fill=0, stroke=1)
        c.setStrokeColor(Color(LINE[0] / 255, LINE[1] / 255, LINE[2] / 255))
        c.setLineWidth(self._s(0.09))

    def _title(self, c: pdf_canvas.Canvas) -> None:
        b = self.title_box
        chamfer = 0.55
        expand = 0.12
        self._pdf_chamfer_fill(c, b.x - expand, b.y - expand, b.w + 2 * expand, b.h + 2 * expand, chamfer + 0.05, GOLD)
        self._pdf_chamfer_fill(c, b.x, b.y, b.w, b.h, chamfer, NAVY)
        inset = 0.28
        self._pdf_chamfer_stroke(
            c, b.x + inset, b.y + inset, b.w - 2 * inset, b.h - 2 * inset, max(0.2, chamfer - 0.15), GOLD_LIGHT, 0.08
        )

        # Arabic title — render with Pillow RTL for correct shaping, embed as image
        from reportlab.lib.utils import ImageReader
        import io

        font_px = max(64, int(3.15 * 72 / 2.54 * 4))  # ~4x supersample
        font = ImageFont.truetype(str(FONT_PATH), size=font_px)
        tmp = Image.new("RGBA", (font_px * 12, font_px * 3), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        bbox = td.textbbox((0, 0), TITLE_AR, font=font, direction="rtl", language="ar")
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad = 8
        text_img = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
        td = ImageDraw.Draw(text_img)
        td.text((pad - bbox[0], pad - bbox[1]), TITLE_AR, font=font, fill=(255, 255, 255, 255), direction="rtl", language="ar")

        # Target size inside title box (~80% width, ~42% height)
        target_w = self._s(b.w * 0.82)
        target_h = self._s(b.h * 0.42)
        scale = min(target_w / text_img.width, target_h / text_img.height)
        draw_w = text_img.width * scale
        draw_h = text_img.height * scale
        cx, cy = self._c(b.cx, b.y + b.h / 2)
        buf = io.BytesIO()
        text_img.save(buf, format="PNG")
        buf.seek(0)
        c.drawImage(
            ImageReader(buf),
            cx - draw_w / 2,
            cy - draw_h / 2,
            width=draw_w,
            height=draw_h,
            mask="auto",
        )

    def _content_box(self, c: pdf_canvas.Canvas, b: Box) -> None:
        chamfer = 0.35
        tab_w, tab_h = 1.35, 0.55
        tab_x = b.cx - tab_w / 2
        tab_y = b.y - tab_h
        # Tab gold then navy
        p = c.beginPath()
        pts = [
            (tab_x + 0.15, tab_y),
            (tab_x + tab_w - 0.15, tab_y),
            (tab_x + tab_w, tab_y + tab_h),
            (tab_x, tab_y + tab_h),
        ]
        x0, y0 = self._c(*pts[0])
        p.moveTo(x0, y0)
        for pt in pts[1:]:
            x, y = self._c(*pt)
            p.lineTo(x, y)
        p.close()
        c.setFillColor(Color(GOLD[0] / 255, GOLD[1] / 255, GOLD[2] / 255))
        c.drawPath(p, fill=1, stroke=0)

        p2 = c.beginPath()
        pts2 = [
            (tab_x + 0.22, tab_y + 0.08),
            (tab_x + tab_w - 0.22, tab_y + 0.08),
            (tab_x + tab_w - 0.08, tab_y + tab_h),
            (tab_x + 0.08, tab_y + tab_h),
        ]
        x0, y0 = self._c(*pts2[0])
        p2.moveTo(x0, y0)
        for pt in pts2[1:]:
            x, y = self._c(*pt)
            p2.lineTo(x, y)
        p2.close()
        c.setFillColor(Color(NAVY[0] / 255, NAVY[1] / 255, NAVY[2] / 255))
        c.drawPath(p2, fill=1, stroke=0)

        expand = 0.08
        self._pdf_chamfer_fill(c, b.x - expand, b.y - expand, b.w + 2 * expand, b.h + 2 * expand, chamfer + 0.04, GOLD)
        self._pdf_chamfer_fill(c, b.x, b.y, b.w, b.h, chamfer, NAVY)
        inset = 0.18
        self._pdf_chamfer_fill(
            c, b.x + inset, b.y + inset, b.w - 2 * inset, b.h - 2 * inset, max(0.12, chamfer - 0.1), CREAM
        )
        g_inset = 0.32
        self._pdf_chamfer_stroke(
            c,
            b.x + g_inset,
            b.y + g_inset,
            b.w - 2 * g_inset,
            b.h - 2 * g_inset,
            max(0.08, chamfer - 0.18),
            GOLD,
            0.05,
        )

    def _pdf_chamfer_fill(
        self, c: pdf_canvas.Canvas, x: float, y: float, w: float, h: float, ch: float, rgb: Tuple[int, int, int]
    ) -> None:
        pts = chamfer_polygon(x, y, w, h, ch)
        p = c.beginPath()
        x0, y0 = self._c(*pts[0])
        p.moveTo(x0, y0)
        for pt in pts[1:]:
            px, py = self._c(*pt)
            p.lineTo(px, py)
        p.close()
        c.setFillColor(Color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255))
        c.drawPath(p, fill=1, stroke=0)

    def _pdf_chamfer_stroke(
        self,
        c: pdf_canvas.Canvas,
        x: float,
        y: float,
        w: float,
        h: float,
        ch: float,
        rgb: Tuple[int, int, int],
        lw_cm: float,
    ) -> None:
        pts = chamfer_polygon(x, y, w, h, ch)
        p = c.beginPath()
        x0, y0 = self._c(*pts[0])
        p.moveTo(x0, y0)
        for pt in pts[1:]:
            px, py = self._c(*pt)
            p.lineTo(px, py)
        p.close()
        c.setStrokeColor(Color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255))
        c.setLineWidth(self._s(lw_cm))
        c.drawPath(p, fill=0, stroke=1)


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def _lerp_rgb(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _bezier_spine(anchors: Sequence[Point], n: int = 64) -> List[Point]:
    """Smooth spine through anchors using Catmull-Rom → cubic segments."""
    if len(anchors) < 2:
        return list(anchors)
    pts = [anchors[0]] + list(anchors) + [anchors[-1]]
    out: List[Point] = []
    segs = len(pts) - 3
    per = max(2, n // max(1, segs))
    for i in range(segs):
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        for j in range(per):
            t = j / per
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            out.append((x, y))
    out.append(anchors[-1])
    return out


def _densify_polyline(pts: Sequence[Point], n: int) -> List[Point]:
    if len(pts) < 2:
        return list(pts)
    # Chord-length parameterization
    dists = [0.0]
    for i in range(1, len(pts)):
        dists.append(dists[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    total = dists[-1] or 1.0
    out: List[Point] = []
    for i in range(n):
        target = total * i / (n - 1)
        j = 0
        while j < len(dists) - 2 and dists[j + 1] < target:
            j += 1
        seg = dists[j + 1] - dists[j] or 1.0
        t = (target - dists[j]) / seg
        x = pts[j][0] + (pts[j + 1][0] - pts[j][0]) * t
        y = pts[j][1] + (pts[j + 1][1] - pts[j][1]) * t
        out.append((x, y))
    return out


def _offset_ribbon(spine: Sequence[Point], half_w: float, wave: float) -> Tuple[List[Point], List[Point]]:
    left: List[Point] = []
    right: List[Point] = []
    n = len(spine)
    for i, (x, y) in enumerate(spine):
        if i == 0:
            dx, dy = spine[1][0] - x, spine[1][1] - y
        elif i == n - 1:
            dx, dy = x - spine[i - 1][0], y - spine[i - 1][1]
        else:
            dx, dy = spine[i + 1][0] - spine[i - 1][0], spine[i + 1][1] - spine[i - 1][1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        # Vary width slightly for fabric feel
        w = half_w * (1.0 + 0.12 * math.sin(i / n * math.pi * 2 * wave))
        # Lateral undulation
        und = 0.35 * math.sin(i / n * math.pi * 3)
        left.append((x + nx * (w + und), y + ny * (w + und)))
        right.append((x - nx * (w - und * 0.5), y - ny * (w - und * 0.5)))
    return left, right


def _lerp_edge(a: Sequence[Point], b: Sequence[Point], t: float) -> List[Point]:
    return [
        (a[i][0] + (b[i][0] - a[i][0]) * t, a[i][1] + (b[i][1] - a[i][1]) * t)
        for i in range(len(a))
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Preview at 100 DPI for quick QA
    print("Rendering preview (100 DPI)...")
    preview = RasterBoard(dpi=100, with_bleed=True).render()
    preview_path = OUTPUT / "zumra_al_sadisa_preview_100dpi.png"
    preview.save(preview_path, "PNG", optimize=True)
    print(f"  -> {preview_path} ({preview.size[0]}×{preview.size[1]})")

    # Print PNG at 300 DPI
    print("Rendering print PNG (300 DPI)...")
    print_img = RasterBoard(dpi=300, with_bleed=True).render()
    png_path = OUTPUT / "zumra_al_sadisa_100x70cm_300dpi.png"
    print_img.save(png_path, "PNG", dpi=(300, 300), compress_level=6)
    print(f"  -> {png_path} ({print_img.size[0]}×{print_img.size[1]})")

    # Optional TIFF backup
    print("Rendering TIFF backup...")
    tiff_path = OUTPUT / "zumra_al_sadisa_100x70cm_300dpi.tif"
    print_img.save(tiff_path, "TIFF", dpi=(300, 300), compression="tiff_lzw")
    print(f"  -> {tiff_path}")

    # Vector PDF
    print("Exporting vector PDF...")
    pdf_path = OUTPUT / "zumra_al_sadisa_100x70cm_print.pdf"
    VectorBoard(with_bleed=True).export(pdf_path)
    print(f"  -> {pdf_path}")

    # Trim-size PDF without bleed (exact 100×70 cm)
    print("Exporting trim-size PDF (exact 100×70 cm)...")
    pdf_trim = OUTPUT / "zumra_al_sadisa_100x70cm_trim.pdf"
    VectorBoard(with_bleed=False).export(pdf_trim)
    print(f"  -> {pdf_trim}")

    # Also copy preview to artifacts
    artifacts = Path("/opt/cursor/artifacts")
    if artifacts.exists():
        preview.save(artifacts / "zumra_board_preview.png", "PNG", optimize=True)
        # Smaller web-friendly proof at 150 DPI trim crop conceptually
        proof = RasterBoard(dpi=72, with_bleed=False).render()
        proof.save(artifacts / "zumra_board_proof_72dpi.png", "PNG", optimize=True)
        print("  artifacts updated")

    print("Done.")
    print(f"Title: {TITLE_AR}")
    print(f"Boxes: {sum(ROWS)} in rows {ROWS}")
    print(f"Page with bleed: {TRIM_W_CM + 2 * BLEED_CM} × {TRIM_H_CM + 2 * BLEED_CM} cm")
    print(f"Trim: {TRIM_W_CM} × {TRIM_H_CM} cm")


if __name__ == "__main__":
    main()
