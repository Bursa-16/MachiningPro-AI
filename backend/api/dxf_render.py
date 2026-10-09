"""DXF geometry renderer — pure Python + Pillow, no ezdxf required.

Parses LINE, CIRCLE, ARC, LWPOLYLINE, and POINT entities from the DXF ENTITIES
section, computes a bounding box, and renders them to a PNG using Pillow
(already in project deps).  Returns None on any failure so callers can fall back
gracefully without crashing.

The rendered PNG can be wrapped in a minimal single-page PDF via
`png_to_single_page_pdf`.  That PDF is accepted by the existing drawing-analysis
pipeline (/api/drawings) because it passes the %PDF- magic-bytes check.

Constraints enforced here:
  - LOCAL_ONLY: only Pillow (installed), no network, no ezdxf
  - AI_AUTHORITY=ADVISORY: this module only renders geometry for display /
    VLM input; it never writes back to the DXF source
  - SOURCE_DXF_OVERWRITE_ALLOWED=NO: input bytes are never mutated
"""

from __future__ import annotations

import io

# ---------------------------------------------------------------------------
# DXF entity parser
# ---------------------------------------------------------------------------

def _parse_dxf_entities(text: str) -> list[dict]:
    """Extract geometry entities from the DXF ENTITIES section.

    Returns a list of dicts.  Each dict has at minimum a 'type' key.
    LWPOLYLINE dicts also carry a 'vertices' key: list of [x, y] pairs.
    Numeric group codes are stored as float values.

    Blank lines are filtered before pairing so the parser is robust to any
    leading/trailing whitespace or CRLF line endings.
    """
    # DXF strictly alternates: even-indexed line = group code integer,
    # odd-indexed line = value.  Stripping blank lines first keeps alignment
    # intact regardless of leading whitespace or Windows CRLF endings.
    raw = [ln.strip() for ln in text.splitlines() if ln.strip()]
    n = len(raw)

    entities: list[dict] = []
    i = 0
    in_entities = False
    current: dict | None = None
    poly_verts: list[list[float]] = []
    poly_mode = False

    while i < n - 1:
        gc_str = raw[i]
        val = raw[i + 1]
        i += 2

        # Detect the ENTITIES section
        if gc_str == "0" and val == "SECTION":
            if i < n - 1 and raw[i] == "2":
                sname = raw[i + 1].upper()
                i += 2
                in_entities = sname == "ENTITIES"
            continue

        if gc_str == "0" and val in ("ENDSEC", "EOF"):
            if current is not None:
                if poly_mode:
                    current["vertices"] = poly_verts[:]
                entities.append(current)
                current = None
            poly_mode = False
            poly_verts = []
            in_entities = False
            continue

        if not in_entities:
            continue

        if gc_str == "0":
            # Flush previous entity
            if current is not None:
                if poly_mode:
                    current["vertices"] = poly_verts[:]
                entities.append(current)
            etype = val.upper()
            current = {"type": etype}
            poly_mode = etype == "LWPOLYLINE"
            poly_verts = []
        elif current is not None:
            try:
                code = int(gc_str)
            except ValueError:
                continue

            if poly_mode and code == 10:
                try:
                    poly_verts.append([float(val), 0.0])
                except ValueError:
                    poly_verts.append([0.0, 0.0])
            elif poly_mode and code == 20:
                if poly_verts:
                    try:
                        poly_verts[-1][1] = float(val)
                    except ValueError:
                        pass
            elif code not in current:
                try:
                    current[code] = float(val)
                except ValueError:
                    if code == 1:  # TEXT / MTEXT content string
                        current[code] = val

    return entities


# ---------------------------------------------------------------------------
# Bounding box
# ---------------------------------------------------------------------------

def _collect_points(entities: list[dict]) -> tuple[list[float], list[float]]:
    """Return (all_x, all_y) collected from the entity list."""
    xs: list[float] = []
    ys: list[float] = []
    for e in entities:
        etype = e.get("type", "")
        try:
            if etype == "LINE":
                xs += [e[10], e[11]]
                ys += [e[20], e[21]]
            elif etype in ("CIRCLE", "ARC"):
                cx, cy, r = e.get(10, 0.0), e.get(20, 0.0), e.get(40, 0.0)
                xs += [cx - r, cx + r]
                ys += [cy - r, cy + r]
            elif etype == "LWPOLYLINE":
                for vx, vy in e.get("vertices", []):
                    xs.append(vx)
                    ys.append(vy)
            elif etype == "POINT":
                xs.append(e.get(10, 0.0))
                ys.append(e.get(20, 0.0))
        except (KeyError, TypeError):
            pass
    return xs, ys


# ---------------------------------------------------------------------------
# PNG renderer
# ---------------------------------------------------------------------------

def render_dxf_to_png(text: str, max_w: int = 1600, max_h: int = 1200) -> bytes | None:
    """Render DXF entity geometry to a PNG using Pillow.

    Returns PNG bytes, or None if the geometry is empty or any error occurs.
    The resulting image has a light background and dark lines — suitable as
    a VLM / AI drawing input.

    Handled entity types: LINE, CIRCLE, ARC, LWPOLYLINE, POINT.
    Text entities (TEXT/MTEXT) are skipped to avoid font dependency.
    """
    try:
        from PIL import Image, ImageDraw  # noqa: PLC0415
    except ImportError:
        return None

    try:
        entities = _parse_dxf_entities(text)
        xs, ys = _collect_points(entities)

        if not xs or not ys:
            return None

        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)

        if (xmax - xmin) < 1e-9 or (ymax - ymin) < 1e-9:
            return None

        # Add 5% margin on each side
        mx = (xmax - xmin) * 0.05
        my = (ymax - ymin) * 0.05
        xmin -= mx
        xmax += mx
        ymin -= my
        ymax += my

        # Choose image dimensions preserving the drawing's aspect ratio
        ratio = (xmax - xmin) / (ymax - ymin)
        if ratio >= max_w / max_h:
            W, H = max_w, max(1, int(max_w / ratio))
        else:
            W, H = max(1, int(max_h * ratio)), max_h
        W, H = max(W, 64), max(H, 64)

        # Light-grey engineering background, dark-navy lines
        img = Image.new("RGB", (W, H), "#f4f6fb")
        draw = ImageDraw.Draw(img)
        INK = "#1a2040"

        # Coordinate transforms: model → pixel
        def tx(x: float) -> float:
            return (x - xmin) / (xmax - xmin) * (W - 1)

        def ty(y: float) -> float:
            # Y-flip: DXF Y up → screen Y down
            return (H - 1) - (y - ymin) / (ymax - ymin) * (H - 1)

        for e in entities:
            etype = e.get("type", "")
            try:
                if etype == "LINE":
                    draw.line(
                        [int(tx(e[10])), int(ty(e[20])),
                         int(tx(e[11])), int(ty(e[21]))],
                        fill=INK, width=1,
                    )

                elif etype == "CIRCLE":
                    cx, cy, r = e.get(10, 0.0), e.get(20, 0.0), e.get(40, 1.0)
                    px, py = tx(cx), ty(cy)
                    # Convert radius from model units to pixels
                    rx = max(1.0, r / (xmax - xmin) * W)
                    ry = max(1.0, r / (ymax - ymin) * H)
                    draw.ellipse(
                        [px - rx, py - ry, px + rx, py + ry],
                        outline=INK, width=1,
                    )

                elif etype == "ARC":
                    cx, cy, r = e.get(10, 0.0), e.get(20, 0.0), e.get(40, 1.0)
                    sa, ea = e.get(50, 0.0), e.get(51, 360.0)
                    px, py = tx(cx), ty(cy)
                    rx = max(1.0, r / (xmax - xmin) * W)
                    ry = max(1.0, r / (ymax - ymin) * H)
                    # Y-flip reverses CCW DXF arcs to CW PIL arcs.
                    # Map: PIL start = -(DXF end), PIL end = -(DXF start)
                    pil_start = (-ea) % 360.0
                    pil_end = (-sa) % 360.0
                    draw.arc(
                        [px - rx, py - ry, px + rx, py + ry],
                        start=pil_start, end=pil_end, fill=INK, width=1,
                    )

                elif etype == "LWPOLYLINE":
                    verts = e.get("vertices", [])
                    if len(verts) >= 2:
                        pts = [(int(tx(vx)), int(ty(vy))) for vx, vy in verts]
                        draw.line(pts, fill=INK, width=1)
                        # Close if flag bit 1 is set
                        flags = int(e.get(70, 0))
                        if flags & 1:
                            draw.line([pts[-1], pts[0]], fill=INK, width=1)

                elif etype == "POINT":
                    px, py = int(tx(e.get(10, 0.0))), int(ty(e.get(20, 0.0)))
                    draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=INK)

            except Exception:  # noqa: BLE001
                pass  # never let a single broken entity crash the whole render

        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# PNG → single-page PDF wrapper
# ---------------------------------------------------------------------------

def png_to_single_page_pdf(png_bytes: bytes) -> bytes:
    """Wrap a PNG image in a minimal single-page PDF using Pillow.

    The resulting PDF passes the %PDF- magic-bytes check and is accepted by
    pdfplumber, so it flows through the existing /api/drawings pipeline.
    Resolution is set to 72 DPI so 1 pixel = 1 point.
    """
    from PIL import Image  # noqa: PLC0415

    img = Image.open(io.BytesIO(png_bytes))
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=72.0)
    return buf.getvalue()
