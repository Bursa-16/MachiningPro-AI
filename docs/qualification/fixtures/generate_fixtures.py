"""Deterministic generator for the MachiningPro AI qualification drawing set (QUALIFICATION_02).

Every drawing is SELF-AUTHORED and synthetic. The source of truth for each drawing is a small
primitive list (``sources/<QUAL_ID>.drawing.json``) from which this script derives:

    sources/<QUAL_ID>.drawing.json     canonical, hashable drawing description
    sources/<QUAL_ID>.svg              human-viewable vector rendering of the same primitives
    raster/<QUAL_ID>.png               8-bit grayscale raster used as the qualification image
    pdf/<QUAL_ID>.pdf                  one-page PDF embedding the raster (NOT vector-only)
    authoring_intent/<QUAL_ID>.authoring_intent.json   what was deliberately drawn
    provenance/<QUAL_ID>.provenance.json               provenance record with SHA-256 hashes

plus the probe fixtures required by the frozen specification (section 4.3):

    P-VEC   Q01 as a vector-only PDF (no embedded image)
    P-OVER  Q10 re-rendered above the R3D whole-image limits
    P-CROP  Q09 split into four quadrant PDFs (the planned first G2 candidate)

AUTHORING_INTENT is not frozen ground truth. Ground truth is authored, reviewed and frozen in a
later task. No customer, OEM, proprietary or downloaded drawing is used anywhere.

Usage (from the repository root):  python docs/qualification/fixtures/generate_fixtures.py
Re-running reproduces identical bytes for a given Pillow version (versions are recorded).
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import unicodedata
import zlib
from pathlib import Path

import PIL
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
GENERATOR_VERSION = "1.0"
AUTHORED_ON = "2026-10-08"  # fixed so regeneration is byte-identical
SUPERSAMPLE = 2
OBJ = 3.0   # object line width, final px
DIM = 1.6   # dimension / extension line width
THIN = 1.2  # centre lines


# ----------------------------------------------------------------------------------------
# Primitive model
# ----------------------------------------------------------------------------------------


class Sheet:
    def __init__(self, qual_id: str, title: str, width: int, height: int) -> None:
        self.qual_id, self.title, self.width, self.height = qual_id, title, width, height
        self.items: list[dict] = []

    # geometry -------------------------------------------------------------------------
    def line(self, x0, y0, x1, y1, w=OBJ, dash=None):
        self.items.append({"t": "line", "x0": x0, "y0": y0, "x1": x1, "y1": y1, "w": w, "dash": dash})

    def rect(self, x0, y0, x1, y1, w=OBJ):
        self.items.append({"t": "rect", "x0": x0, "y0": y0, "x1": x1, "y1": y1, "w": w})

    def circle(self, cx, cy, r, w=OBJ):
        self.items.append({"t": "circle", "cx": cx, "cy": cy, "r": r, "w": w})

    def arc(self, cx, cy, r, a0, a1, w=OBJ):
        """Clockwise (screen) arc from a0 to a1 degrees, 0 = 3 o'clock."""
        self.items.append({"t": "arc", "cx": cx, "cy": cy, "r": r, "a0": a0, "a1": a1, "w": w})

    def poly(self, pts, fill=False, w=OBJ):
        self.items.append({"t": "poly", "pts": [list(p) for p in pts], "fill": fill, "w": w})

    def text(self, x, y, s, size=22, anchor="ls", tag="TEXT", group=None):
        self.items.append({"t": "text", "x": x, "y": y, "s": s, "size": size, "anchor": anchor,
                           "tag": tag, "group": group})

    # helpers --------------------------------------------------------------------------
    def arrow(self, x, y, dx, dy, length=14.0, half=4.5):
        n = math.hypot(dx, dy)
        ux, uy = dx / n, dy / n
        bx, by = x - ux * length, y - uy * length
        self.poly([(x, y), (bx - uy * half, by + ux * half), (bx + uy * half, by - ux * half)], fill=True, w=1)

    def hdim(self, x0, x1, y, text, ref_y0, ref_y1=None, size=22, tag="DIMENSION", gap=6):
        """Horizontal dimension: extension lines, dimension line with arrows, text above."""
        for x, ry in ((x0, ref_y0), (x1, ref_y1 if ref_y1 is not None else ref_y0)):
            sgn = 1 if y > ry else -1
            self.line(x, ry + sgn * gap, x, y + sgn * 8, DIM)
        self.line(x0, y, x1, y, DIM)
        self.arrow(x0, y, 1, 0)
        self.arrow(x1, y, -1, 0)
        self.text((x0 + x1) / 2, y - 9, text, size, "ms", tag)

    def vdim(self, y0, y1, x, text, ref_x0, ref_x1=None, size=22, tag="DIMENSION", gap=6, side="right"):
        """Vertical dimension with horizontal text beside the line."""
        for y, rx in ((y0, ref_x0), (y1, ref_x1 if ref_x1 is not None else ref_x0)):
            sgn = 1 if x > rx else -1
            self.line(rx + sgn * gap, y, x + sgn * 8, y, DIM)
        self.line(x, y0, x, y1, DIM)
        self.arrow(x, y0, 0, 1)
        self.arrow(x, y1, 0, -1)
        if side == "right":
            self.text(x + 12, (y0 + y1) / 2, text, size, "lm", tag)
        else:
            self.text(x - 12, (y0 + y1) / 2, text, size, "rm", tag)

    def leader(self, px, py, qx, qy, text, size=22, anchor="lm", tag="DIMENSION", tx=None, ty=None):
        """Leader from a feature point to a text anchor."""
        self.line(px, py, qx, qy, DIM)
        self.arrow(px, py, px - qx, py - qy)
        self.text(qx if tx is None else tx, qy if ty is None else ty, text, size, anchor, tag)

    def centre(self, cx, cy, r, ext=18):
        self.line(cx - r - ext, cy, cx + r + ext, cy, THIN, dash=(14, 5))
        self.line(cx, cy - r - ext, cx, cy + r + ext, THIN, dash=(14, 5))


# ----------------------------------------------------------------------------------------
# Drawings
# ----------------------------------------------------------------------------------------


def build_q01() -> Sheet:
    s = Sheet("Q01", "Plate with one hole - control fixture", 480, 320)
    s.rect(40, 70, 360, 262)
    s.circle(200, 166, 32)
    s.centre(200, 166, 32, 12)
    s.hdim(40, 360, 48, "100 MM", 70, size=24)
    s.vdim(70, 262, 388, "60 MM", 360, size=24)
    s.text(200, 236, "HOLE 20 MM", 24, "ms", "LABEL")
    return s


def build_q02() -> Sheet:
    s = Sheet("Q02", "Plate with two holes - diameter callouts", 800, 600)
    s.rect(80, 120, 720, 480)
    s.circle(240, 300, 80)
    s.circle(520, 300, 48)
    s.centre(240, 300, 80)
    s.centre(520, 300, 48)
    s.hdim(80, 720, 84, "80 mm", 120)
    s.leader(240, 220, 240, 186, "DIA 20 mm", 22, "ms", ty=172, tx=240)
    s.leader(520, 348, 520, 392, "DIA 12 mm", 22, "ms", ty=420, tx=520)
    s.text(80, 548, "2 HOLES THRU ALL", 22, "ls", "NOTE")
    return s


def corner_plate(s, x0, y0, x1, y1, radii):
    """Rectangle with rounded corners; radii = (tl, tr, br, bl) px (0 = sharp)."""
    tl, tr, br, bl = radii
    s.line(x0 + tl, y0, x1 - tr, y0)
    s.line(x1, y0 + tr, x1, y1 - br)
    s.line(x1 - br, y1, x0 + bl, y1)
    s.line(x0, y1 - bl, x0, y0 + tl)
    if tl:
        s.arc(x0 + tl, y0 + tl, tl, 180, 270)
    if tr:
        s.arc(x1 - tr, y0 + tr, tr, 270, 360)
    if br:
        s.arc(x1 - br, y1 - br, br, 0, 90)
    if bl:
        s.arc(x0 + bl, y1 - bl, bl, 90, 180)


def build_q03() -> Sheet:
    s = Sheet("Q03", "Plate with rounded corners - radius callouts", 800, 600)
    corner_plate(s, 100, 120, 660, 480, (40, 96, 64, 0))
    r = 40 * math.cos(math.radians(45))
    s.leader(160 - r, 160 - r, 112, 112, "R5 mm", 22, "rm", tx=104, ty=112)
    r = 96 * math.cos(math.radians(45))
    s.leader(564 + r, 216 - r, 690, 96, "R12 mm", 22, "lm", tx=698, ty=96)
    r = 64 * math.cos(math.radians(45))
    s.leader(596 + r, 416 + r, 690, 524, "R8 mm", 22, "lm", tx=698, ty=524)
    s.circle(380, 300, 50)
    s.centre(380, 300, 50)
    s.text(100, 560, "FILLETED CORNER PLATE", 22, "ls", "LABEL")
    return s


def build_q04() -> Sheet:
    s = Sheet("Q04", "Chamfered and angled plate - angular dimensions", 800, 600)
    pts = [(120, 140), (536, 140), (600, 204), (600, 460), (240, 460), (120, 391)]
    s.poly(pts, w=OBJ)
    s.hdim(120, 600, 96, "60 mm", 140, size=22)
    s.vdim(140, 460, 700, "40 mm", 600, size=22)
    s.line(536, 140, 706, 140, DIM)  # virtual-corner extension for the 40 mm dimension
    s.leader(568, 172, 480, 226, "45°", 22, "rm", tx=470, ty=226)
    s.leader(180, 425.5, 110, 500, "30°", 22, "rm", tx=100, ty=500)
    s.text(300, 540, "CHAMFER AND ANGLE CUT", 22, "ls", "LABEL")
    return s


def build_q05() -> Sheet:
    s = Sheet("Q05", "Notched block - several dimensions in one view", 1200, 900)
    # outline with notch and a filleted bottom-right corner
    s.line(200, 250, 450, 250)
    s.line(450, 250, 450, 375)
    s.line(450, 375, 650, 375)
    s.line(650, 375, 650, 250)
    s.line(650, 250, 900, 250)
    s.line(900, 250, 900, 620)
    s.arc(870, 620, 30, 0, 90)
    s.line(870, 650, 200, 650)
    s.line(200, 650, 200, 250)
    s.circle(525, 520, 35)
    s.centre(525, 520, 35)
    s.hdim(200, 900, 190, "140 mm", 250, size=24)
    s.hdim(450, 650, 232, "40 mm", 250, 250, size=24)
    s.vdim(250, 650, 980, "80 mm", 900, size=24)
    s.line(420, 250, 420, 375, DIM)
    s.arrow(420, 250, 0, 1)
    s.arrow(420, 375, 0, -1)
    s.text(408, 312, "25 mm", 24, "rm", "DIMENSION")
    s.leader(490, 520, 445, 520, "DIA 14 mm", 24, "rm", tx=437, ty=520)
    r = 30 * math.cos(math.radians(45))
    s.leader(870 + r, 620 + r, 950, 700, "R6 mm", 24, "lm", tx=958, ty=700)
    s.hdim(200, 525, 720, "65 mm", 650, 556, size=24)
    s.vdim(520, 650, 760, "26 mm", 525, 900, size=24)
    s.text(200, 820, "TOP VIEW", 24, "ls", "LABEL")
    return s


def title_block(s: Sheet, x0: int, y0: int, x1: int, y1: int, fields: list[tuple[str, str]], size=22):
    s.rect(x0, y0, x1, y1, 2.5)
    row = (y1 - y0) / len(fields)
    for i, (label, value) in enumerate(fields):
        yy = y0 + row * i
        if i:
            s.line(x0, yy, x1, yy, 1.5)
        s.text(x0 + 14, yy + row / 2, f"{label}: {value}", size, "lm", "TITLE_FIELD")


TITLE_FIELDS_BASE = [
    ("PART NAME", "TEST BRACKET"),
    ("DRAWING NO", "QUAL-{q}"),
    ("MATERIAL", "GENERIC STEEL"),
    ("SCALE", "1:1"),
    ("SHEET", "1 OF 1"),
    ("REV", "A"),
    ("DATE", "2026-10-08"),
    ("UNITS", "MM"),
]


def build_q06() -> Sheet:
    s = Sheet("Q06", "Bracket with notes and a fictional title block", 1200, 900)
    s.rect(200, 220, 650, 445)
    s.hdim(200, 650, 175, "90 mm", 220, size=24)
    s.vdim(220, 445, 710, "45 mm", 650, size=24)
    for i, line in enumerate(["NOTES:", "1. BREAK SHARP EDGES.", "2. DEBURR ALL SURFACES.",
                              "3. MATERIAL PER TITLE BLOCK."]):
        s.text(200, 560 + i * 38, line, 22, "ls", "NOTE")
    fields = [(a, b.format(q="Q06")) for a, b in TITLE_FIELDS_BASE]
    title_block(s, 700, 600, 1160, 880, fields)
    return s


def build_q07() -> Sheet:
    s = Sheet("Q07", "Plate with toleranced dimensions", 1200, 900)
    # outline with a bottom slot (x 410..610, depth 100)
    for seg in [(260, 300, 920, 300), (920, 300, 920, 600), (920, 600, 610, 600), (610, 600, 610, 500),
                (610, 500, 410, 500), (410, 500, 410, 600), (410, 600, 260, 600), (260, 600, 260, 300)]:
        s.line(*seg)
    s.circle(860, 420, 30)
    s.centre(860, 420, 30)
    s.hdim(260, 920, 250, "132.0 ±0.1 mm", 300, size=22)
    s.vdim(300, 600, 980, "60 +0.2/-0.1 mm", 920, size=22)
    s.hdim(410, 610, 660, "40 +0.1/0 mm", 600, size=22)
    # slot depth, text to the right of the dimension line
    s.line(610, 500, 636, 500, DIM)
    s.line(630, 500, 630, 600, DIM)
    s.arrow(630, 500, 0, 1)
    s.arrow(630, 600, 0, -1)
    s.text(644, 550, "20 +0/-0.05 mm", 22, "lm", "DIMENSION")
    s.hdim(260, 860, 740, "120.0 ±0.05 mm", 600, 450, size=22)
    s.vdim(420, 600, 200, "36 ±0.2 mm", 860, 260, size=22, side="left")
    return s


def gdt_frame(s: Sheet, x: int, y: int, cells: list[str], group: str, size=22, h=40):
    cx = x
    for i, c in enumerate(cells):
        w = int(ImageFont.load_default(size).getlength(c)) + 26
        s.rect(cx, y, cx + w, y + h, 2.2)
        s.text(cx + w / 2, y + h / 2, c, size, "mm", "GDT_CELL", group)
        cx += w
    return cx


def datum_symbol(s: Sheet, x: int, y: int, letter: str, attach: tuple[int, int], end: tuple[int, int], size=22):
    s.rect(x, y, x + 36, y + 36, 2.2)
    s.text(x + 18, y + 18, letter, size, "mm", "DATUM_LABEL")
    s.line(attach[0], attach[1], end[0], end[1], DIM)


def frame_leader(s: Sheet, x0, y0, x1, y1):
    s.line(x0, y0, x1, y1, DIM)
    s.arrow(x1, y1, x1 - x0, y1 - y0)


def build_q08() -> Sheet:
    s = Sheet("Q08", "Plate with datum labels and GD&T frames", 1200, 900)
    s.rect(200, 260, 700, 560)
    s.circle(450, 410, 40)
    s.centre(450, 410, 40)
    s.hdim(200, 700, 225, "100 mm", 260, size=22)
    s.vdim(260, 560, 780, "60 mm", 700, size=22)
    datum_symbol(s, 400, 590, "A", (418, 560), (418, 590))
    datum_symbol(s, 114, 392, "B", (200, 410), (150, 410))
    gdt_frame(s, 880, 150, ["FLATNESS", "0.05 mm"], "FRAME-FLATNESS")
    frame_leader(s, 880, 170, 640, 260)
    gdt_frame(s, 100, 640, ["POSITION", "DIA 0.2 mm", "A", "B"], "FRAME-POSITION")
    frame_leader(s, 330, 640, 420, 446)
    gdt_frame(s, 650, 640, ["CIRCULARITY", "0.02 mm"], "FRAME-CIRCULARITY")
    frame_leader(s, 700, 640, 480, 442)
    gdt_frame(s, 860, 480, ["SYMMETRY", "0.1 mm", "A"], "FRAME-SYMMETRY")
    frame_leader(s, 860, 500, 700, 500)
    gdt_frame(s, 100, 150, ["PERPENDICULARITY", "0.1 mm", "A"], "FRAME-NEGATIVE-PERPENDICULARITY")
    frame_leader(s, 300, 190, 220, 260)
    return s


def part_with_chains(s: Sheet, ox: int, oy: int, top: list[str], overall_top: str, right: list[str],
                     hole: str, hole_prefix: str = "", size=22, plate_w=480, plate_h=300):
    """Generic plate with a 3-segment top chain, an overall top dimension, a 4-segment right chain
    and one diameter callout. Everything stays inside an (ox..ox+900, oy..oy+650) zone."""
    x0, y0 = ox + 100, oy + 210
    x1, y1 = x0 + plate_w, y0 + plate_h
    s.rect(x0, y0, x1, y1)
    seg = plate_w / len(top)
    for i, text in enumerate(top):
        a, b = x0 + seg * i, x0 + seg * (i + 1)
        s.hdim(a, b, oy + 170, text, y0, size=size)
    s.hdim(x0, x1, oy + 110, overall_top, y0, size=size)
    seg_v = plate_h / len(right)
    for i, text in enumerate(right):
        a, b = y0 + seg_v * i, y0 + seg_v * (i + 1)
        s.vdim(a, b, x1 + 60, text, x1, size=size)
    cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, 40
    s.circle(cx, cy, r)
    s.centre(cx, cy, r, 12)
    s.leader(cx, cy + r, cx, cy + r + 34, hole, size, "ms", tx=cx, ty=cy + r + 62)


def build_q09() -> Sheet:
    s = Sheet("Q09", "Dense four-view sheet (mm and inch)", 1800, 1300)
    # top-left (mm), top-right (inch), bottom-left (mm with tolerances)
    part_with_chains(s, 0, 0, ["30 mm", "45 mm", "25 mm"], "100 mm", ["22 mm", "28 mm", "26 mm", "24 mm"], "DIA 12 mm")
    part_with_chains(s, 900, 0, ["1.250 in", "1.750 in", "1.000 in"], "4.000 in",
                     ["0.875 in", "1.125 in", "1.000 in", "0.750 in"], "DIA 0.500 in")
    part_with_chains(s, 0, 650, ["25 ±0.1 mm", "35 ±0.1 mm", "20 ±0.2 mm"], "80 ±0.2 mm",
                     ["20 mm", "18 mm", "22 mm", "16 mm"], "DIA 10 mm")
    # bottom-right: a small part, notes and a fictional title block
    ox, oy = 900, 650
    s.rect(ox + 100, oy + 140, ox + 400, oy + 260)
    s.hdim(ox + 100, ox + 400, oy + 110, "75 mm", oy + 140, size=22)
    s.vdim(oy + 140, oy + 260, ox + 460, "30 mm", ox + 400, size=22)
    for i, line in enumerate(["NOTES:", "1. BREAK SHARP EDGES.", "2. DEBURR ALL EDGES.", "3. DIMENSIONS IN MM."]):
        s.text(ox + 580, oy + 100 + i * 36, line, 22, "ls", "NOTE")
    fields = [(a, b.format(q="Q09")) for a, b in TITLE_FIELDS_BASE]
    fields[0] = ("PART NAME", "TEST HOUSING")
    title_block(s, ox + 100, oy + 330, ox + 800, oy + 610, fields)
    return s


def build_q10() -> Sheet:
    s = Sheet("Q10", "Large flange plate near the whole-image size limit", 2000, 1400)
    x0, y0, x1, y1 = 300, 400, 1500, 1000
    # outline: R8 top-left corner (80 px) and a 45 degree chamfer (150 px) bottom-right
    s.line(x0 + 80, y0, x1, y0)
    s.line(x1, y0, x1, y1 - 150)
    s.line(x1, y1 - 150, x1 - 150, y1)
    s.line(x1 - 150, y1, x0, y1)
    s.line(x0, y1, x0, y0 + 80)
    s.arc(x0 + 80, y0 + 80, 80, 180, 270)
    segs = ["30 mm", "35 mm", "30 mm", "25 mm"]
    seg = (x1 - x0) / len(segs)
    for i, t in enumerate(segs):
        s.hdim(x0 + seg * i, x0 + seg * (i + 1), 330, t, y0, size=26)
    s.hdim(x0, x1, 260, "120 mm", y0, size=26)
    rs = ["20 mm", "22 mm", "18 mm"]
    sv = (y1 - y0) / len(rs)
    for i, t in enumerate(rs):
        s.vdim(y0 + sv * i, y0 + sv * (i + 1), x1 + 90, t, x1, size=26)
    for cx, cy, r in ((600, 700, 60), (1200, 700, 90)):
        s.circle(cx, cy, r)
        s.centre(cx, cy, r, 16)
    s.leader(600, 760, 600, 810, "DIA 12 mm", 26, "ms", tx=600, ty=845)
    s.leader(1200, 790, 1200, 850, "DIA 18 mm", 26, "ms", tx=1200, ty=885)
    s.leader(x0 + 80 - 56.6, y0 + 80 - 56.6, 250, 350, "R8 mm", 26, "rm", tx=244, ty=350)
    s.leader(1425, 925, 1330, 860, "45°", 26, "rm", tx=1318, ty=860)
    for i, line in enumerate(["NOTES:", "1. BREAK SHARP EDGES.", "2. ALL DIMENSIONS IN MM."]):
        s.text(300, 1230 + i * 40, line, 24, "ls", "NOTE")
    return s


BUILDERS = {
    "Q01": build_q01, "Q02": build_q02, "Q03": build_q03, "Q04": build_q04, "Q05": build_q05,
    "Q06": build_q06, "Q07": build_q07, "Q08": build_q08, "Q09": build_q09, "Q10": build_q10,
}

# ----------------------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------------------

_FONTS: dict[float, ImageFont.FreeTypeFont] = {}


def font(size: float):
    key = round(size, 2)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.load_default(size=key)
    return _FONTS[key]


def render_raster(sheet: Sheet, scale: float = 1.0) -> Image.Image:
    k = SUPERSAMPLE * scale
    w, h = round(sheet.width * scale), round(sheet.height * scale)
    big = Image.new("L", (w * SUPERSAMPLE, h * SUPERSAMPLE), 255)
    d = ImageDraw.Draw(big)

    def px(v):
        return v * k

    def lw(v):
        return max(1, round(v * k))

    for it in sheet.items:
        t = it["t"]
        if t == "line":
            if it.get("dash"):
                dash, gap = it["dash"]
                n = math.hypot(it["x1"] - it["x0"], it["y1"] - it["y0"])
                ux, uy = (it["x1"] - it["x0"]) / n, (it["y1"] - it["y0"]) / n
                pos = 0.0
                while pos < n:
                    end = min(pos + dash, n)
                    d.line([(px(it["x0"] + ux * pos), px(it["y0"] + uy * pos)),
                            (px(it["x0"] + ux * end), px(it["y0"] + uy * end))], 0, lw(it["w"]))
                    pos += dash + gap
            else:
                d.line([(px(it["x0"]), px(it["y0"])), (px(it["x1"]), px(it["y1"]))], 0, lw(it["w"]))
        elif t == "rect":
            d.rectangle([px(it["x0"]), px(it["y0"]), px(it["x1"]), px(it["y1"])], None, 0, lw(it["w"]))
        elif t == "circle":
            d.ellipse([px(it["cx"] - it["r"]), px(it["cy"] - it["r"]), px(it["cx"] + it["r"]),
                       px(it["cy"] + it["r"])], None, 0, lw(it["w"]))
        elif t == "arc":
            d.arc([px(it["cx"] - it["r"]), px(it["cy"] - it["r"]), px(it["cx"] + it["r"]),
                   px(it["cy"] + it["r"])], it["a0"], it["a1"], 0, lw(it["w"]))
        elif t == "poly":
            pts = [(px(x), px(y)) for x, y in it["pts"]]
            if it["fill"]:
                d.polygon(pts, 0)
            else:
                d.line(pts + [pts[0]], 0, lw(it["w"]), joint="curve")
        elif t == "text":
            d.text((px(it["x"]), px(it["y"])), it["s"], 0, font(it["size"] * k), anchor=it["anchor"])
    return big.resize((w, h), Image.LANCZOS)


def text_bbox(item: dict) -> list[int]:
    img = Image.new("L", (4, 4))
    box = ImageDraw.Draw(img).textbbox((item["x"], item["y"]), item["s"], font=font(item["size"]),
                                       anchor=item["anchor"])
    return [round(v) for v in box]


# ----------------------------------------------------------------------------------------
# Writers
# ----------------------------------------------------------------------------------------


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def serialize_pdf(objects: list[bytes], catalog_id: int) -> bytes:
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def raster_pdf(img: Image.Image) -> bytes:
    """One page, MediaBox = pixel size (1 px = 1 pt), the raster as a FlateDecode gray image."""
    w, h = img.size
    compressed = zlib.compress(img.tobytes(), 9)
    image_obj = (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray "
                 f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>\n").encode() \
        + b"stream\n" + compressed + b"\nendstream"
    content = f"q\n{w} 0 0 {h} 0 0 cm\n/Im1 Do\nQ\n".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] /Resources << /XObject << /Im1 5 0 R >> >> "
         f"/Contents 4 0 R >>").encode(),
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"endstream",
        image_obj,
    ]
    return serialize_pdf(objects, 1)


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def vector_pdf(sheet: Sheet) -> bytes:
    """Vector-only PDF (no image) for probe P-VEC. ASCII text only (built-in Helvetica)."""
    h = sheet.height
    ops = ["0 g 0 G"]
    for it in sheet.items:
        t = it["t"]
        if t == "line":
            ops.append(f"{it['w']:.2f} w {it['x0']:.2f} {h - it['y0']:.2f} m {it['x1']:.2f} {h - it['y1']:.2f} l S")
        elif t == "rect":
            ops.append(f"{it['w']:.2f} w {it['x0']:.2f} {h - it['y1']:.2f} {it['x1'] - it['x0']:.2f} "
                       f"{it['y1'] - it['y0']:.2f} re S")
        elif t == "circle":
            cx, cy, r, c = it["cx"], h - it["cy"], it["r"], 0.5523 * it["r"]
            ops.append(f"{it['w']:.2f} w {cx + r:.2f} {cy:.2f} m "
                       f"{cx + r:.2f} {cy + c:.2f} {cx + c:.2f} {cy + r:.2f} {cx:.2f} {cy + r:.2f} c "
                       f"{cx - c:.2f} {cy + r:.2f} {cx - r:.2f} {cy + c:.2f} {cx - r:.2f} {cy:.2f} c "
                       f"{cx - r:.2f} {cy - c:.2f} {cx - c:.2f} {cy - r:.2f} {cx:.2f} {cy - r:.2f} c "
                       f"{cx + c:.2f} {cy - r:.2f} {cx + r:.2f} {cy - c:.2f} {cx + r:.2f} {cy:.2f} c S")
        elif t == "arc":
            pts = [(it["cx"] + it["r"] * math.cos(math.radians(a)), h - (it["cy"] + it["r"] * math.sin(math.radians(a))))
                   for a in [it["a0"] + (it["a1"] - it["a0"]) * i / 12 for i in range(13)]]
            ops.append(f"{it['w']:.2f} w {pts[0][0]:.2f} {pts[0][1]:.2f} m "
                       + " ".join(f"{x:.2f} {y:.2f} l" for x, y in pts[1:]) + " S")
        elif t == "poly":
            pts = [(x, h - y) for x, y in it["pts"]]
            path = f"{pts[0][0]:.2f} {pts[0][1]:.2f} m " + " ".join(f"{x:.2f} {y:.2f} l" for x, y in pts[1:]) + " h"
            ops.append(f"{it['w']:.2f} w {path} {'f' if it['fill'] else 'S'}")
        elif t == "text":
            s = it["s"]
            assert s.isascii(), "P-VEC is built from an ASCII-only drawing"
            width = font(it["size"]).getlength(s)
            x = it["x"] - (width / 2 if it["anchor"][0] == "m" else width if it["anchor"][0] == "r" else 0)
            y = h - it["y"] - (it["size"] * 0.35 if it["anchor"][1] == "m" else 0)
            ops.append(f"BT /F1 {it['size']:.1f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({_esc(s)}) Tj ET")
    content = "\n".join(ops).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {sheet.width} {sheet.height}] "
         f"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>").encode(),
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    return serialize_pdf(objects, 1)


def svg(sheet: Sheet) -> str:
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{sheet.width}" height="{sheet.height}" '
           f'viewBox="0 0 {sheet.width} {sheet.height}">',
           f'<rect width="{sheet.width}" height="{sheet.height}" fill="#ffffff"/>',
           '<g fill="none" stroke="#000000" stroke-linecap="butt">']
    anchor = {"l": "start", "m": "middle", "r": "end"}
    base = {"s": "alphabetic", "m": "central"}
    texts = []
    for it in sheet.items:
        t = it["t"]
        if t == "line":
            dash = f' stroke-dasharray="{it["dash"][0]} {it["dash"][1]}"' if it.get("dash") else ""
            out.append(f'<line x1="{it["x0"]:.2f}" y1="{it["y0"]:.2f}" x2="{it["x1"]:.2f}" y2="{it["y1"]:.2f}" '
                       f'stroke-width="{it["w"]}"{dash}/>')
        elif t == "rect":
            out.append(f'<rect x="{it["x0"]}" y="{it["y0"]}" width="{it["x1"] - it["x0"]}" '
                       f'height="{it["y1"] - it["y0"]}" stroke-width="{it["w"]}"/>')
        elif t == "circle":
            out.append(f'<circle cx="{it["cx"]}" cy="{it["cy"]}" r="{it["r"]}" stroke-width="{it["w"]}"/>')
        elif t == "arc":
            a0, a1 = math.radians(it["a0"]), math.radians(it["a1"])
            p0 = (it["cx"] + it["r"] * math.cos(a0), it["cy"] + it["r"] * math.sin(a0))
            p1 = (it["cx"] + it["r"] * math.cos(a1), it["cy"] + it["r"] * math.sin(a1))
            out.append(f'<path d="M {p0[0]:.2f} {p0[1]:.2f} A {it["r"]} {it["r"]} 0 0 1 {p1[0]:.2f} {p1[1]:.2f}" '
                       f'stroke-width="{it["w"]}"/>')
        elif t == "poly":
            pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in it["pts"])
            if it["fill"]:
                out.append(f'<polygon points="{pts}" fill="#000000" stroke="none"/>')
            else:
                out.append(f'<polygon points="{pts}" stroke-width="{it["w"]}"/>')
        elif t == "text":
            s = it["s"].replace("&", "&amp;").replace("<", "&lt;")
            texts.append(f'<text x="{it["x"]:.2f}" y="{it["y"]:.2f}" font-size="{it["size"]}" '
                         f'text-anchor="{anchor[it["anchor"][0]]}" dominant-baseline="{base[it["anchor"][1]]}">{s}</text>')
    out.append("</g>")
    out.append('<g fill="#000000" font-family="sans-serif">')
    out.extend(texts)
    out.append("</g></svg>")
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------------------
# Grammar and intent
# ----------------------------------------------------------------------------------------


def parser_patterns():
    sys.path.insert(0, str(REPO_ROOT))
    from backend.interoperability import pdf_drawing as pd  # read-only static import

    return pd._DIMENSION_TOKEN_PATTERN, pd._DIMENSION_TOLERANCE_PATTERN


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).replace("\n", " ").split())


def authoring_intent(sheet: Sheet, token_re, tol_re) -> dict:
    items = []
    n = 0
    for it in sheet.items:
        if it["t"] != "text":
            continue
        n += 1
        text = normalize(it["s"])
        items.append({
            "intent_id": f"{sheet.qual_id}-I{n:03d}",
            "printed_text": it["s"],
            "drawn_as": it["tag"],
            "group": it["group"],
            "text_bbox_px": text_bbox(it),
            "matches_deterministic_dimension_token_grammar": bool(token_re.fullmatch(text)),
            "matches_deterministic_tolerance_grammar": bool(tol_re.fullmatch(text)),
        })
    return {
        "qual_id": sheet.qual_id,
        "record_type": "AUTHORING_INTENT",
        "frozen_ground_truth": False,
        "note": ("What was deliberately drawn, written by the generator. This is NOT the scored "
                 "ground truth: ground truth is independently reviewed and frozen in a later task."),
        "image_px": [sheet.width, sheet.height],
        "text_items": items,
        "graphics": {k: sum(1 for i in sheet.items if i["t"] == k) for k in ("line", "rect", "circle", "arc", "poly")},
    }


# ----------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------


def dump(path: Path, obj) -> bytes:
    data = (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")
    path.write_bytes(data)
    return data


def write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256(data)


def png_bytes(img: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=9, optimize=False)
    return buf.getvalue()


DIRS = ("sources", "raster", "pdf", "provenance", "authoring_intent")


def provenance(qual_id, title, *, creation_method, source_file, raster_file, pdf_file, h_src, h_ras, h_pdf,
               created_for, derived_from=None, extra=None):
    rec = {
        "record_type": "PROVENANCE",
        "qual_id": qual_id,
        "title": title,
        "author_type": "SELF_AUTHORED",
        "source_origin": "MachiningPro AI qualification fixture",
        "license_status": "PROJECT_AUTHORED_INTERNAL_QUALIFICATION_ASSET",
        "customer_data": "NO",
        "proprietary_external_data": "NO",
        "personal_data": "NO",
        "creation_method": creation_method,
        "source_file": source_file,
        "raster_file": raster_file,
        "pdf_file": pdf_file,
        "sha256_source": h_src,
        "sha256_raster": h_ras,
        "sha256_pdf": h_pdf,
        "created_for": created_for,
        "authored_on": AUTHORED_ON,
        "generator": f"docs/qualification/fixtures/generate_fixtures.py v{GENERATOR_VERSION}",
        "toolchain": {"python": ".".join(map(str, sys.version_info[:3])), "pillow": PIL.__version__},
        "derived_from": derived_from,
        "drawing_author": {"identifier": None, "date": None, "status": "PENDING"},
        "ground_truth_reviewer": {"identifier": None, "date": None, "status": "PENDING"},
        "provenance_approver": {"identifier": None, "date": None, "status": "PENDING"},
        "role_overlap_note": None,
        "author_signoff": "PENDING",
        "provenance_approval": "PENDING",
        "provenance_status": "AUTHORED_PENDING_SIGNOFF",
    }
    if extra:
        rec.update(extra)
    return rec


def main() -> None:
    token_re, tol_re = parser_patterns()
    for d in DIRS:
        (HERE / d).mkdir(exist_ok=True)
    manifest = []

    sheets = {q: b() for q, b in BUILDERS.items()}
    rasters: dict[str, Image.Image] = {}
    for q, sheet in sheets.items():
        src = {"qual_id": q, "title": sheet.title, "width": sheet.width, "height": sheet.height,
               "generator_version": GENERATOR_VERSION, "items": sheet.items}
        h_src = sha256(dump(HERE / "sources" / f"{q}.drawing.json", src))
        write(HERE / "sources" / f"{q}.svg", svg(sheet).encode("utf-8"))
        img = render_raster(sheet)
        rasters[q] = img
        h_ras = write(HERE / "raster" / f"{q}.png", png_bytes(img))
        h_pdf = write(HERE / "pdf" / f"{q}.pdf", raster_pdf(img))
        dump(HERE / "authoring_intent" / f"{q}.authoring_intent.json", authoring_intent(sheet, token_re, tol_re))
        rec = provenance(
            q, sheet.title,
            creation_method="Generated from a primitive drawing description; rasterised with Pillow at "
                            f"{SUPERSAMPLE}x supersampling; embedded as an 8-bit DeviceGray FlateDecode image",
            source_file=f"sources/{q}.drawing.json", raster_file=f"raster/{q}.png", pdf_file=f"pdf/{q}.pdf",
            h_src=h_src, h_ras=h_ras, h_pdf=h_pdf, created_for="REAL_DRAWING_DEMO_QUALIFICATION")
        h_prov = sha256(dump(HERE / "provenance" / f"{q}.provenance.json", rec))
        manifest.append({"id": q, "kind": "DRAWING", "image_px": [sheet.width, sheet.height],
                         "sha256_source": h_src, "sha256_raster": h_ras, "sha256_pdf": h_pdf,
                         "provenance_record": f"provenance/{q}.provenance.json"})

    # ---- probes ------------------------------------------------------------------------
    def probe(pid, title, derived_from, method, h_src, raster_file, pdf_file, img, pdf_bytes, extra=None):
        h_ras = write(HERE / "raster" / raster_file, png_bytes(img)) if raster_file else None
        h_pdf = write(HERE / "pdf" / pdf_file, pdf_bytes)
        rec = provenance(pid, title, creation_method=method, source_file=f"sources/{derived_from}.drawing.json",
                         raster_file=f"raster/{raster_file}" if raster_file else None, pdf_file=f"pdf/{pdf_file}",
                         h_src=h_src, h_ras=h_ras, h_pdf=h_pdf, created_for="QUALIFICATION_PROBE",
                         derived_from=derived_from, extra=extra)
        dump(HERE / "provenance" / f"{pid}.provenance.json", rec)
        manifest.append({"id": pid, "kind": "PROBE", "derived_from": derived_from, "sha256_raster": h_ras,
                         "sha256_pdf": h_pdf, "provenance_record": f"provenance/{pid}.provenance.json"})

    src_hash = {m["id"]: m["sha256_source"] for m in manifest}
    probe("P-VEC_Q01", "Q01 as a vector-only PDF (probe P-VEC)", "Q01",
          "Same primitives as Q01 written as PDF drawing operators with built-in Helvetica; no image",
          src_hash["Q01"], None, "P-VEC_Q01_vector.pdf", None, vector_pdf(sheets["Q01"]),
          {"expected_probe_behaviour": "AI job refused with INVALID_REGION; deterministic result still shown"})
    big = render_raster(sheets["Q10"], scale=1.3)
    probe("P-OVER_Q10", "Q10 re-rendered at 1.3x above the R3D limits (probe P-OVER)", "Q10",
          "Same primitives as Q10 with every coordinate, font size and line width multiplied by 1.3",
          src_hash["Q10"], "P-OVER_Q10_oversize.png", "P-OVER_Q10_oversize.pdf", big, raster_pdf(big),
          {"image_px": list(big.size), "expected_probe_behaviour":
           "job FAILED with INVALID_REGION before any model inference; deterministic result still shown"})
    q9 = rasters["Q09"]
    boxes = {"c1": (0, 0, 900, 650), "c2": (900, 0, 1800, 650), "c3": (0, 650, 900, 1300),
             "c4": (900, 650, 1800, 1300)}
    for name, box in boxes.items():
        crop = q9.crop(box)
        probe(f"P-CROP_Q09_{name}", f"Q09 quadrant {name} (probe P-CROP)", "Q09",
              f"Exact crop of the Q09 raster at pixel box {list(box)} (zone boundaries lie in blank gutters)",
              src_hash["Q09"], f"P-CROP_Q09_{name}.png", f"P-CROP_Q09_{name}.pdf", crop, raster_pdf(crop),
              {"crop_box_px": list(box), "image_px": list(crop.size)})

    dump(HERE / "manifest.json", {"record_type": "FIXTURE_MANIFEST", "generator_version": GENERATOR_VERSION,
                                  "toolchain": {"python": ".".join(map(str, sys.version_info[:3])),
                                                "pillow": PIL.__version__},
                                  "entries": manifest})
    print(f"generated {len(manifest)} fixtures")


if __name__ == "__main__":
    main()
