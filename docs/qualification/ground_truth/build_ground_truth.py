"""Derive and freeze the qualification ground truth (REAL_DRAWING_QUALIFICATION_03).

INDEPENDENCE: this script reads ONLY
    * docs/qualification/REAL_DRAWING_DEMO_QUALIFICATION.md        (frozen spec)
    * docs/qualification/fixtures/manifest.json and provenance/*   (fixture index and hashes)
    * docs/qualification/fixtures/sources/*.drawing.json           (self-authored fixture source)
    * docs/qualification/fixtures/authoring_intent/*.json          (what was deliberately drawn)
It never opens a model, OCR, R3B, job, review or run-log artifact, and it imports no VLM, OCR or
provider module. The only backend import is the parser's accepted-grammar constants, used as a
static readback of which authored strings the grammar accepts (no parsing of any drawing).

Usage (repository root):  python docs/qualification/ground_truth/build_ground_truth.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIX = HERE.parent / "fixtures"
sys.path.insert(0, str(REPO))

from backend.interoperability import pdf_drawing as _grammar  # noqa: E402  (grammar constants only)
from backend.interoperability.drawing import DrawingGdtCharacteristic  # noqa: E402
from backend.interoperability.gdt_drawing import _TOLERANCE_PATTERN as GDT_TOLERANCE  # noqa: E402

VERSION = "1.0"
FROZEN_ON = "2026-10-08"
COORD = "FIXTURE_RASTER_PX_TOP_LEFT"
SOURCE_BASIS = ["SELF_AUTHORED_FIXTURE_SOURCE", "AUTHORING_INTENT", "VISIBLE_FIXTURE_CONTENT", "FROZEN_SPEC"]
REVIEW = {
    "role": "GROUND_TRUTH_REVIEWER",
    "performed_by": "ROLE_ONLY_AUTOMATED_DERIVATION_FROM_FIXTURE_SOURCES",
    "named_reviewer": None,
    "named_human_review": "NOT_RECORDED",
    "signoff": "FROZEN",
    "note": "No named reviewer is assigned for the initial internal qualification (ROLE_SEPARATION_REQUIRED = NO). "
            "The role is recorded; no identity is asserted.",
}

TOKEN_RE = _grammar._DIMENSION_TOKEN_PATTERN
TOL_RE = _grammar._DIMENSION_TOLERANCE_PATTERN
ALLOWED_CHARACTERISTICS = {c.value for c in DrawingGdtCharacteristic}
TOLERANCE_TEXT = re.compile(
    r"^(?P<nom>\d+(?:\.\d+)?)\s*(?:±\s*(?P<sym>\d+(?:\.\d+)?)|\+(?P<up>\d+(?:\.\d+)?)/-?(?P<lo>\d+(?:\.\d+)?))"
    r"\s*(?P<unit>mm|in)$")
SIMPLE = re.compile(r"^(?:(?P<prefix>DIA|R)\s*)?(?P<val>\d+(?:\.\d+)?)\s*(?:(?P<deg>°)|(?P<unit>mm|MM|in))$")
ALIAS = {"PART NAME": "part_name", "DRAWING NO": "drawing_number", "MATERIAL": "material", "SCALE": "scale",
         "SHEET": "sheet", "REV": "revision", "DATE": "date", "UNITS": "unit"}
UNIT = {"mm": "mm", "MM": "mm", "in": "inch"}
CORE = ["Q01", "Q02", "Q05", "Q06", "Q07"]
EXT_GATE = ["Q09", "Q10"]
EXT = ["Q03", "Q04", "Q08"]
DRAWINGS = [f"Q{n:02d}" for n in range(1, 11)]
CROPS = {"c1": (0, 0, 900, 650), "c2": (900, 0, 1800, 650), "c3": (0, 650, 900, 1300), "c4": (900, 650, 1800, 1300)}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canon(obj) -> bytes:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"


def dec(text: str) -> str:
    return format(Decimal(text).normalize(), "f")


def norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


# ----------------------------------------------------------------------------------------
# Item derivation
# ----------------------------------------------------------------------------------------


def classify(entry: dict) -> dict:
    """Map one authored text item to ground-truth fields. Authored text is preserved verbatim."""
    text = entry["printed_text"]
    tag = entry["drawn_as"]
    out = {"expected_text": text, "feature_type": "GENERAL_TEXT", "expected_value": None, "expected_unit": None,
           "expected_normalized_value": None, "expected_normalized_unit": None}
    if tag == "TITLE_FIELD":
        label, value = text.split(": ", 1)
        out.update(feature_type="TITLE_BLOCK_TEXT", field_label=label, field_value=value, field_key=ALIAS[label],
                   expected_value=value)
        return out
    if tag == "DATUM_LABEL":
        out.update(feature_type="GDT_TRANSCRIPTION", gdt_role="DATUM_LABEL", expected_value=text)
        return out
    if tag in ("NOTE",):
        return out
    if tag == "LABEL":
        m = re.fullmatch(r"HOLE (\d+) MM", text)
        if m:
            out.update(feature_type="HOLE_CALLOUT", expected_value=m.group(1), expected_unit="mm",
                       expected_normalized_value=dec(m.group(1)), expected_normalized_unit="mm")
        return out
    if tag == "DIMENSION":
        tol = TOLERANCE_TEXT.match(text)
        if tol:
            unit = UNIT[tol.group("unit")]
            if tol.group("sym") is not None:
                plus = minus = tol.group("sym")
                kind = "SYMMETRIC"
            else:
                plus, minus = tol.group("up"), tol.group("lo")
                kind = "UNILATERAL" if Decimal(plus) == 0 or Decimal(minus) == 0 else "BILATERAL"
            out.update(feature_type="TOLERANCE", expected_value=tol.group("nom"), expected_unit=unit,
                       expected_normalized_value=dec(tol.group("nom")), expected_normalized_unit=unit,
                       tolerance={"kind": kind, "plus": dec(plus), "minus": dec(minus), "unit": unit})
            return out
        m = SIMPLE.match(text)
        assert m, f"unclassified dimension text: {text!r}"
        if m.group("deg"):
            out.update(feature_type="ANGLE", expected_value=m.group("val"), expected_unit="degree",
                       expected_normalized_value=dec(m.group("val")), expected_normalized_unit="degree")
        else:
            unit = UNIT[m.group("unit")]
            prefix = m.group("prefix")
            ftype = "DIAMETER" if prefix == "DIA" else "RADIUS" if prefix == "R" else "LINEAR_DIMENSION"
            out.update(feature_type=ftype, expected_value=m.group("val"), expected_unit=unit,
                       expected_normalized_value=dec(m.group("val")), expected_normalized_unit=unit)
            if prefix:
                out["prefix"] = prefix
        return out
    raise AssertionError(f"unexpected authored tag {tag}")


def deterministic_expectation(item: dict, entry: dict | None, cells: list[str] | None) -> tuple[str, bool]:
    """Static expectation derived from the parser GRAMMAR and the authored text only (no parsing run)."""
    ft = item["feature_type"]
    if ft in ("LINEAR_DIMENSION", "DIAMETER", "RADIUS", "ANGLE", "TOLERANCE"):
        text = norm(item["expected_text"])
        ok = bool(TOKEN_RE.fullmatch(text) or TOL_RE.fullmatch(text))
        return ("DIMENSION_GRAMMAR_ACCEPTED", True) if ok else ("DIMENSION_GRAMMAR_NOT_ACCEPTED", True)
    if ft == "TITLE_BLOCK_TEXT":
        return "TITLE_FIELD_ALIAS_ACCEPTED", True
    if ft == "GDT_TRANSCRIPTION" and cells is not None:
        allowed = norm(cells[0]).upper() in ALLOWED_CHARACTERISTICS
        return ("GDT_FRAME_ALLOWLISTED", True) if allowed else ("GDT_FRAME_UNSUPPORTED_CHARACTERISTIC", True)
    return "NONE", False


def demo_required(qid: str, item: dict) -> bool:
    ft, text = item["feature_type"], item["expected_text"]
    val = item.get("expected_normalized_value")
    unit = item.get("expected_normalized_unit")
    if qid in ("Q01", "Q02", "Q03", "Q04", "Q07"):
        return ft not in ("GENERAL_TEXT",)
    if qid == "Q05":
        return text in {"140 mm", "80 mm", "40 mm", "DIA 14 mm", "R6 mm"}
    if qid == "Q06":
        return ft == "LINEAR_DIMENSION" or item.get("field_key") in {"part_name", "drawing_number", "material"}
    if qid == "Q08":
        return ft == "LINEAR_DIMENSION" or (ft == "GDT_TRANSCRIPTION" and item.get("gdt_role") == "FEATURE_CONTROL_FRAME"
                                            and item["characteristic_allowlisted"])
    if qid == "Q09":
        return text in {"100 mm", "4.000 in", "80 ±0.2 mm"} or ft == "DIAMETER"
    if qid == "Q10":
        return text in {"120 mm", "DIA 12 mm", "DIA 18 mm", "R8 mm", "45°"}
    raise AssertionError(qid)


def build_recognition(qid: str, entries: dict, intent: dict, prov: dict) -> dict:
    items: list[dict] = []
    seq = 0
    groups: dict[str, list[dict]] = {}
    for t in intent["text_items"]:
        if t["drawn_as"] == "GDT_CELL":
            groups.setdefault(t["group"], []).append(t)
    emitted_groups: set[str] = set()
    for t in intent["text_items"]:
        if t["drawn_as"] == "GDT_CELL":
            if t["group"] in emitted_groups:
                continue
            emitted_groups.add(t["group"])
            cells = groups[t["group"]]
            texts = [c["printed_text"] for c in cells]
            first = norm(texts[0]).upper()
            allowed = first in ALLOWED_CHARACTERISTICS
            seq += 1
            item = {
                "item_id": f"{qid}-T{seq:03d}",
                "feature_type": "GDT_TRANSCRIPTION",
                "gdt_role": "FEATURE_CONTROL_FRAME",
                "expected_text": " | ".join(texts),
                "cells": texts,
                "characteristic": texts[0],
                "characteristic_allowlisted": allowed,
                "expected_value": None, "expected_unit": None,
                "expected_normalized_value": None, "expected_normalized_unit": None,
            }
            tol_cell = next((c for c in texts[1:] if GDT_TOLERANCE.fullmatch(norm(c))), None)
            if tol_cell:
                m = GDT_TOLERANCE.fullmatch(norm(tol_cell))
                u = "inch" if m.group("unit").lower() in ("in", "inch", "inches") else "mm"
                item.update(expected_value=m.group("value"), expected_unit=u,
                            expected_normalized_value=dec(m.group("value")), expected_normalized_unit=u,
                            diameter_modifier=bool(m.group("diameter")))
            region = union([c["text_bbox_px"] for c in cells])
            expectation, det = deterministic_expectation(item, None, texts)
            item["negative_case"] = not allowed
            note = ("Frame transcription only; no engineering meaning is added. "
                    + ("NEGATIVE CASE: the characteristic is not on the deterministic allowlist; the deterministic path "
                       "must not produce a frame for it." if not allowed else
                       "Allowlisted characteristic."))
        else:
            seq += 1
            item = {"item_id": f"{qid}-T{seq:03d}"}
            item.update(classify(t))
            region = t["text_bbox_px"]
            expectation, det = deterministic_expectation(item, t, None)
            note = {"HOLE_CALLOUT": "Authored label; the numeric part is 20 mm; diameter or depth is not stated.",
                    }.get(item["feature_type"], "")
            if item["feature_type"] == "TOLERANCE":
                note = "Tolerance notation transcribed as authored."
        item["expected_region"] = {"page": 1, "coordinate_system": COORD, "px": region, "reference_only": True,
                                   "note": "ground-truth reference region; never a model box"}
        item["required_for_demo"] = demo_required(qid, item)
        item["scoreable"] = True
        item["deterministic_expectation"] = expectation
        item["deterministic_scoreable"] = det
        item["notes"] = note
        items.append(item)
    return {"items": items}


def build_probe(pid: str, entry: dict | None, gt_q09: dict | None) -> dict:
    base = {"record_type": "PROBE_EXPECTATION", "scored_as_recognition": False, "ai_inference_expected": False}
    if pid == "P-VEC_Q01":
        base.update(fixture_class="STRUCTURAL_EXPECTATION", derived_from="Q01",
                    expected_behavior="Upload is accepted and the deterministic result is shown; starting the AI analysis "
                                      "is refused because the page has no embedded raster image; no job is created.",
                    expected_error_or_gate="INVALID_REGION (HTTP 422 at analysis start)",
                    notes="Vector-only PDF with no embedded image. No recognition ground truth is defined for it; "
                          "its text is authored from Q01 and is not scored.")
    elif pid == "P-OVER_Q10":
        base.update(fixture_class="STRUCTURAL_EXPECTATION", derived_from="Q10",
                    expected_behavior="Upload is accepted; the analysis job starts and then fails during request "
                                      "preparation because the whole-image region exceeds the R3D limits; the deterministic "
                                      "result remains shown; the model is never called.",
                    expected_error_or_gate="job FAILED with INVALID_REGION (R3D CROP_EDGE_LIMIT / CROP_PIXEL_LIMIT)",
                    notes="2600x1820 raster: longest edge above 2048 px and pixel count above 4,194,304. No recognition "
                          "ground truth is defined for it.")
    elif pid == "P-DOWN":
        base.update(fixture_class="STRUCTURAL_EXPECTATION", derived_from=None,
                    expected_behavior="With the local AI service stopped, an explicitly started analysis job ends FAILED; "
                                      "the UI shows a safe failure state; the deterministic panel stays usable; no automatic "
                                      "retry occurs.",
                    expected_error_or_gate="job FAILED with OLLAMA_UNAVAILABLE",
                    fixture_binding="ANY_RECOGNITION_FIXTURE (suggested carrier: Q01); no dedicated fixture file",
                    notes="Behavioural probe without a fixture file. No recognition ground truth is defined for it.")
    else:
        name = pid.split("_")[-1]
        box = CROPS[name]
        contained, local = [], {}
        for it in gt_q09["items"]:
            x0, y0, x1, y1 = it["expected_region"]["px"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if box[0] <= cx < box[2] and box[1] <= cy < box[3]:
                contained.append(it["item_id"])
                local[it["item_id"]] = [x0 - box[0], y0 - box[1], x1 - box[0], y1 - box[1]]
        base.update(fixture_class="PROBE_EXPECTATION", derived_from="Q09", scored_as_recognition=True,
                    ai_inference_expected=True,
                    expected_behavior="A normal analysis job on the crop; its findings are scored only against the Q09 "
                                      "ground-truth items that lie inside this crop.",
                    expected_error_or_gate="none (crop is within the R3D limits)",
                    crop_box_px_in_q09=list(box), parent_qual_id="Q09", contained_item_ids=contained,
                    contained_item_crop_regions_px=local,
                    notes="References Q09 items by id; no text or dimension ground truth is duplicated here. Each Q09 item "
                          "lies in exactly one crop (zone boundaries are blank gutters).")
    return base


# ----------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------


def finalize(record: dict) -> bytes:
    body = {k: v for k, v in record.items() if k != "record_sha256"}
    record["record_sha256"] = sha_bytes(canon(body))
    return canon(record)


def main() -> None:
    manifest = load(FIX / "manifest.json")
    entries = {e["id"]: e for e in manifest["entries"]}
    manifest_hash = sha_file(FIX / "manifest.json")
    spec_hash = sha_file(REPO / "docs/qualification/REAL_DRAWING_DEMO_QUALIFICATION.md")
    out_manifest = []
    records: dict[str, dict] = {}

    def common(qid, fixture_class, record_type, src_ids):
        e = entries.get(qid)
        rec = {
            "qual_id": qid,
            "fixture_class": fixture_class,
            "record_type": record_type,
            "ground_truth_version": VERSION,
            "ground_truth_status": "FROZEN",
            "frozen_on": FROZEN_ON,
            "source_basis": SOURCE_BASIS,
            "spec_sha256": spec_hash,
            "fixture_manifest_sha256": manifest_hash,
            "source_sha256": e.get("sha256_source") if e else None,
            "raster_sha256": e.get("sha256_raster") if e else None,
            "pdf_sha256": e.get("sha256_pdf") if e else None,
            "ground_truth_review": REVIEW,
        }
        return rec

    def write(rec: dict, file_name: str):
        data = finalize(rec)
        (HERE / "records").mkdir(exist_ok=True)
        (HERE / "records" / file_name).write_bytes(data)
        out_manifest.append({
            "qual_id": rec["qual_id"], "record_file": f"records/{file_name}", "record_type": rec["record_type"],
            "fixture_class": rec["fixture_class"],
            "item_count": len(rec.get("items", [])),
            "source_sha256": rec["source_sha256"], "raster_sha256": rec["raster_sha256"], "pdf_sha256": rec["pdf_sha256"],
            "record_sha256": rec["record_sha256"], "record_file_sha256": sha_bytes(data),
            "ground_truth_status": rec["ground_truth_status"],
        })

    for qid in DRAWINGS:
        intent_path = FIX / "authoring_intent" / f"{qid}.authoring_intent.json"
        intent = load(intent_path)
        rec = common(qid, "RECOGNITION_GROUND_TRUTH", "RECOGNITION_GROUND_TRUTH", None)
        rec["derived_from_files"] = {
            "source": f"fixtures/sources/{qid}.drawing.json",
            "authoring_intent": f"fixtures/authoring_intent/{qid}.authoring_intent.json",
            "authoring_intent_sha256": sha_file(intent_path),
        }
        rec["demo_class"] = "CORE" if qid in CORE else "EXT-GATE" if qid in EXT_GATE else "EXT"
        rec["image_px"] = intent["image_px"]
        rec["coordinate_system"] = COORD
        rec.update(build_recognition(qid, entries, intent, None))
        records[qid] = rec
        write(rec, f"{qid}.ground_truth.json")

    for pid in ["P-VEC_Q01", "P-OVER_Q10", "P-CROP_Q09_c1", "P-CROP_Q09_c2", "P-CROP_Q09_c3", "P-CROP_Q09_c4", "P-DOWN"]:
        probe = build_probe(pid, entries.get(pid), records["Q09"])
        rec = common(pid, probe["fixture_class"], "PROBE_EXPECTATION", None)
        rec.update({k: v for k, v in probe.items() if k not in ("fixture_class", "record_type")})
        rec["derived_from_files"] = ({"provenance": f"fixtures/provenance/{pid}.provenance.json"} if pid in entries else {})
        records[pid] = rec
        write(rec, f"{pid}.probe_expectation.json")

    index = {
        "record_type": "GROUND_TRUTH_INDEX",
        "ground_truth_version": VERSION,
        "ground_truth_status": "FROZEN",
        "frozen_on": FROZEN_ON,
        "spec_sha256": spec_hash,
        "fixture_manifest_sha256": manifest_hash,
        "coordinate_system": COORD,
        "records": out_manifest,
    }
    (HERE / "manifest.json").write_bytes(canon(index))
    print(f"wrote {len(out_manifest)} records, {sum(r['item_count'] for r in out_manifest)} items")


if __name__ == "__main__":
    main()
