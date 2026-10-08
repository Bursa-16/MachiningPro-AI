"""Mechanical validation of the qualification fixture set (no AI, no OCR, no scoring).

Checks inventory, uniqueness, provenance and authoring-intent coverage, referenced files, SHA-256
hashes, raster-backed PDF structure (via the read-only raster inspector), size policy, probe
labelling, absence of external references and identifying data, the P-CROP gutters, and that the
frozen specification is unchanged. Prints a JSON report and exits non-zero on any failure.

Usage (repository root):  python docs/qualification/fixtures/validate_fixtures.py
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

import pdfplumber  # noqa: E402

from backend.interoperability.raster_drawing import inspect_raster_pdf  # noqa: E402

DRAWINGS = [f"Q{n:02d}" for n in range(1, 11)]
CORE = ["Q01", "Q02", "Q05", "Q06", "Q07"]
EXT_GATE = ["Q09", "Q10"]
EXT = ["Q03", "Q04", "Q08"]
PROBES = ["P-VEC_Q01", "P-OVER_Q10", "P-CROP_Q09_c1", "P-CROP_Q09_c2", "P-CROP_Q09_c3", "P-CROP_Q09_c4"]
PROBE_PDF = {"P-VEC_Q01": "P-VEC_Q01_vector.pdf", "P-OVER_Q10": "P-OVER_Q10_oversize.pdf"}
MAX_EDGE, MAX_PIXELS, MAX_PNG = 2048, 4_194_304, 4 * 1024 * 1024
SPEC = "docs/qualification/REAL_DRAWING_DEMO_QUALIFICATION.md"
ALLOWED_TITLE_VALUES = {"TEST BRACKET", "TEST HOUSING", "QUAL-Q06", "QUAL-Q09", "GENERIC STEEL", "1:1",
                        "1 OF 1", "A", "2026-10-08", "MM"}

failures: list[str] = []


def check(cond: bool, message: str) -> None:
    if not cond:
        failures.append(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pdf_of(pid: str) -> Path:
    return HERE / "pdf" / PROBE_PDF.get(pid, f"{pid}.pdf")


report: dict = {"drawings": {}, "probes": {}}
manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
entries = {e["id"]: e for e in manifest["entries"]}

# --- inventory and uniqueness ---------------------------------------------------------
ids = [e["id"] for e in manifest["entries"]]
check(len(ids) == len(set(ids)), "duplicate IDs in manifest")
check(set(ids) == set(DRAWINGS + PROBES), f"manifest IDs differ from the frozen inventory: {sorted(set(ids) ^ set(DRAWINGS + PROBES))}")

external = re.compile(rb"/URI|/JavaScript|/JS |/Launch|/EmbeddedFile|/OpenAction|https?://|/AA ")
identifying = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|https?://|www\.|CONFIDENTIAL|PROPRIETARY|COPYRIGHT|\(C\)|"
                         r"\bGMBH\b|\bINC\b|\bLTD\b|\bLLC\b|\bCORP\b", re.I)
gutter_x, gutter_y = 900, 650


def prim_boxes(items):
    for it in items:
        t = it["t"]
        if t == "line":
            yield (min(it["x0"], it["x1"]), min(it["y0"], it["y1"]), max(it["x0"], it["x1"]), max(it["y0"], it["y1"]))
        elif t == "rect":
            yield (it["x0"], it["y0"], it["x1"], it["y1"])
        elif t in ("circle", "arc"):
            yield (it["cx"] - it["r"], it["cy"] - it["r"], it["cx"] + it["r"], it["cy"] + it["r"])
        elif t == "poly":
            xs, ys = [p[0] for p in it["pts"]], [p[1] for p in it["pts"]]
            yield (min(xs), min(ys), max(xs), max(ys))


for q in DRAWINGS:
    e = entries.get(q, {})
    src = HERE / "sources" / f"{q}.drawing.json"
    svg = HERE / "sources" / f"{q}.svg"
    png = HERE / "raster" / f"{q}.png"
    pdf = HERE / "pdf" / f"{q}.pdf"
    prov = HERE / "provenance" / f"{q}.provenance.json"
    intent = HERE / "authoring_intent" / f"{q}.authoring_intent.json"
    for f in (src, svg, png, pdf, prov, intent):
        check(f.exists(), f"{q}: missing {f.name}")
    if not all(f.exists() for f in (src, svg, png, pdf, prov, intent)):
        continue
    p = json.loads(prov.read_text(encoding="utf-8"))
    i = json.loads(intent.read_text(encoding="utf-8"))
    check(p["qual_id"] == q and p["author_type"] == "SELF_AUTHORED", f"{q}: provenance identity")
    check(p["license_status"] == "PROJECT_AUTHORED_INTERNAL_QUALIFICATION_ASSET", f"{q}: license status")
    check(p["customer_data"] == p["proprietary_external_data"] == p["personal_data"] == "NO", f"{q}: data flags")
    check(p["author_signoff"] == "PENDING" and p["provenance_approval"] == "PENDING", f"{q}: signoff must be PENDING")
    check(p["sha256_source"] == sha(src) == e["sha256_source"], f"{q}: source hash")
    check(p["sha256_raster"] == sha(png) == e["sha256_raster"], f"{q}: raster hash")
    check(p["sha256_pdf"] == sha(pdf) == e["sha256_pdf"], f"{q}: pdf hash")
    for rel in (p["source_file"], p["raster_file"], p["pdf_file"]):
        check((HERE / rel).exists(), f"{q}: provenance references missing file {rel}")
    check(i["record_type"] == "AUTHORING_INTENT" and i["frozen_ground_truth"] is False, f"{q}: intent flags")
    check(len(i["text_items"]) > 0, f"{q}: empty authoring intent")

    # raster-backed PDF structure ---------------------------------------------------
    raster = inspect_raster_pdf(pdf.read_bytes(), f"upload::{q}.pdf")
    snap = raster.snapshot
    readable, images, pages, rw, rh, kind = False, 0, 0, None, None, None
    try:
        with pdfplumber.open(pdf) as doc:
            readable, pages = True, len(doc.pages)
    except Exception:  # noqa: BLE001
        pass
    if snap is not None and snap.pages:
        images = sum(len(pg.images) for pg in snap.pages)
        kind = snap.pages[0].content_kind.value
        if snap.pages[0].images:
            rw, rh = snap.pages[0].images[0].width, snap.pages[0].images[0].height
    check(readable and pages == 1, f"{q}: PDF unreadable or page count != 1")
    check(images == 1, f"{q}: expected exactly one embedded raster image, found {images}")
    check([rw, rh] == i["image_px"], f"{q}: embedded raster size {rw}x{rh} != intended {i['image_px']}")
    b = pdf.read_bytes()
    check(not external.search(b), f"{q}: external reference or active content in PDF")
    check(b"/Subtype /Image" in b and b"/Type /Font" not in b, f"{q}: PDF must be image-only (no fonts/vector text)")
    check(not re.search(r"https?://(?!www\.w3\.org/2000/svg)|xlink:href|<image", svg.read_text(encoding="utf-8")),
          f"{q}: external reference in SVG")

    # size policy ------------------------------------------------------------------------
    w, h = i["image_px"]
    check(max(w, h) <= MAX_EDGE and w * h <= MAX_PIXELS, f"{q}: exceeds R3D whole-image limits")
    check(png.stat().st_size <= MAX_PNG, f"{q}: PNG larger than the R3D PNG limit")

    # identifying data and grammar ---------------------------------------------------------
    texts = [t["printed_text"] for t in i["text_items"]]
    check(not any(identifying.search(t) for t in texts), f"{q}: identifying text found")
    for t in i["text_items"]:
        if t["drawn_as"] == "TITLE_FIELD":
            check(t["printed_text"].split(": ", 1)[1] in ALLOWED_TITLE_VALUES, f"{q}: unexpected title value {t['printed_text']}")
    dims = [t for t in i["text_items"] if t["drawn_as"] == "DIMENSION"]
    compatible = [t["printed_text"] for t in dims if t["matches_deterministic_dimension_token_grammar"]
                  or t["matches_deterministic_tolerance_grammar"]]
    report["drawings"][q] = {
        "class": "CORE" if q in CORE else "EXT-GATE" if q in EXT_GATE else "EXT",
        "image_px": [w, h], "pdf_bytes": pdf.stat().st_size, "pdf_readable": readable, "pages": pages,
        "embedded_raster_images": images, "raster_width": rw, "raster_height": rh, "content_kind": kind,
        "pixels": w * h, "dimension_texts": len(dims), "grammar_compatible_dimension_texts": len(compatible),
        "text_items": len(texts),
    }
    report["drawings"][q]["_compatible"] = compatible

# --- spot coverage per the frozen matrix ---------------------------------------------------
def intent_of(q):
    return json.loads((HERE / "authoring_intent" / f"{q}.authoring_intent.json").read_text(encoding="utf-8"))["text_items"]


def count(q, pred):
    return sum(1 for t in intent_of(q) if pred(t))


check(count("Q01", lambda t: t["drawn_as"] in ("DIMENSION", "LABEL")) == 3, "Q01 must carry 3 labels")
check(count("Q02", lambda t: t["printed_text"].startswith("DIA ")) == 2, "Q02 must carry 2 diameter callouts")
check(count("Q02", lambda t: t["drawn_as"] == "DIMENSION" and not t["printed_text"].startswith("DIA ")) == 1, "Q02 linear")
check(count("Q03", lambda t: re.fullmatch(r"R\d+ mm", t["printed_text"]) is not None) == 3, "Q03 must carry 3 radii")
check(count("Q04", lambda t: "°" in t["printed_text"]) == 2, "Q04 must carry 2 angular dimensions")
check(count("Q04", lambda t: t["drawn_as"] == "DIMENSION" and "°" not in t["printed_text"]) == 2, "Q04 linear")
check(count("Q05", lambda t: t["drawn_as"] == "DIMENSION") == 8, "Q05 must carry 8 dimensions")
check(count("Q06", lambda t: t["drawn_as"] == "TITLE_FIELD") == 8, "Q06 must carry 8 title-block fields")
check(count("Q06", lambda t: t["drawn_as"] == "DIMENSION") == 2, "Q06 linear")
check(count("Q07", lambda t: t["drawn_as"] == "DIMENSION" and ("±" in t["printed_text"] or "+" in t["printed_text"])) == 6,
      "Q07 must carry 6 toleranced dimensions")
check(len({t["group"] for t in intent_of("Q08") if t["drawn_as"] == "GDT_CELL"}) == 5, "Q08 must carry 5 frames (4 + 1 negative)")
check(count("Q08", lambda t: t["drawn_as"] == "DATUM_LABEL") == 2, "Q08 datum labels")
check(count("Q09", lambda t: t["drawn_as"] == "DIMENSION") >= 25, "Q09 must be dense (25+ dimensions)")
check(count("Q10", lambda t: t["drawn_as"] == "DIMENSION") == 12, "Q10 must carry 12 dimensions")
check(report["drawings"]["Q02"]["grammar_compatible_dimension_texts"] >= 1, "RQ06: Q02 has no grammar-compatible token")

# --- probes ----------------------------------------------------------------------------------
for pid in PROBES:
    e = entries.get(pid, {})
    pdf = pdf_of(pid)
    prov = HERE / "provenance" / f"{pid}.provenance.json"
    check(pdf.exists() and prov.exists(), f"{pid}: missing files")
    if not (pdf.exists() and prov.exists()):
        continue
    p = json.loads(prov.read_text(encoding="utf-8"))
    check(e["kind"] == "PROBE" and p["created_for"] == "QUALIFICATION_PROBE" and p["derived_from"], f"{pid}: not labelled as a probe")
    check(p["sha256_pdf"] == sha(pdf) == e["sha256_pdf"], f"{pid}: pdf hash")
    if p.get("raster_file"):
        check(p["sha256_raster"] == sha(HERE / p["raster_file"]) == e["sha256_raster"], f"{pid}: raster hash")
    raster = inspect_raster_pdf(pdf.read_bytes(), f"upload::{pid}.pdf")
    snap = raster.snapshot
    images = sum(len(pg.images) for pg in snap.pages) if snap else 0
    w = h = None
    if snap and snap.pages and snap.pages[0].images:
        w, h = snap.pages[0].images[0].width, snap.pages[0].images[0].height
    b = pdf.read_bytes()
    check(not external.search(b), f"{pid}: external reference in PDF")
    info = {"pdf_bytes": pdf.stat().st_size, "embedded_raster_images": images, "raster_width": w, "raster_height": h,
            "content_kind": snap.pages[0].content_kind.value if snap and snap.pages else None}
    if pid == "P-VEC_Q01":
        check(images == 0 and b"/Subtype /Image" not in b, "P-VEC must be vector-only")
    elif pid == "P-OVER_Q10":
        check(images == 1 and max(w, h) > MAX_EDGE and w * h > MAX_PIXELS, "P-OVER must exceed both R3D whole-image limits")
    else:
        check(images == 1 and (w, h) == (900, 650), f"{pid}: crop must be a 900x650 raster")
        check(max(w, h) <= MAX_EDGE and w * h <= MAX_PIXELS, f"{pid}: crop exceeds R3D limits")
    report["probes"][pid] = info

# --- P-CROP gutters: nothing may straddle the quadrant boundaries of Q09 -------------------
q9 = json.loads((HERE / "sources" / "Q09.drawing.json").read_text(encoding="utf-8"))["items"]
margin = 20
for (x0, y0, x1, y1) in prim_boxes(q9):
    check(not (x0 < gutter_x + margin and x1 > gutter_x - margin), f"Q09 gutter x crossed by {x0, y0, x1, y1}")
    check(not (y0 < gutter_y + margin and y1 > gutter_y - margin), f"Q09 gutter y crossed by {x0, y0, x1, y1}")
for t in intent_of("Q09"):
    x0, y0, x1, y1 = t["text_bbox_px"]
    check(not (x0 < gutter_x + margin and x1 > gutter_x - margin), f"Q09 text crosses x gutter: {t['printed_text']}")
    check(not (y0 < gutter_y + margin and y1 > gutter_y - margin), f"Q09 text crosses y gutter: {t['printed_text']}")

# --- frozen spec unchanged ---------------------------------------------------------------------
diff = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", SPEC], cwd=REPO).returncode
check(diff == 0, "the frozen qualification specification has changed")

rq06 = {q: report["drawings"][q].pop("_compatible") for q in DRAWINGS}
report["rq06_compatible_tokens"] = {q: v for q, v in rq06.items() if v}
report["failures"] = failures
report["status"] = "PASS" if not failures else "FAIL"
print(json.dumps(report, indent=2, ensure_ascii=True))
sys.exit(0 if not failures else 1)
