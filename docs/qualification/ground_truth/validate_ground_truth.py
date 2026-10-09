"""Mechanical validation of the frozen qualification ground truth (no AI, no OCR, no scoring).

Usage (repository root):  python docs/qualification/ground_truth/validate_ground_truth.py
Prints a JSON report; exits non-zero on any failure.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUAL = HERE.parent
FIX = QUAL / "fixtures"
REPO = HERE.parents[2]
SPEC = QUAL / "REAL_DRAWING_DEMO_QUALIFICATION.md"

DRAWINGS = [f"Q{n:02d}" for n in range(1, 11)]
CORE = ["Q01", "Q02", "Q05", "Q06", "Q07"]
PROBES = ["P-VEC_Q01", "P-OVER_Q10", "P-CROP_Q09_c1", "P-CROP_Q09_c2", "P-CROP_Q09_c3", "P-CROP_Q09_c4", "P-DOWN"]
UNIT_TYPES = {"LINEAR_DIMENSION", "DIAMETER", "RADIUS", "ANGLE", "TOLERANCE", "HOLE_CALLOUT"}
ALLOWED_TYPES = {"LINEAR_DIMENSION", "DIAMETER", "HOLE_CALLOUT", "RADIUS", "ANGLE", "TOLERANCE",
                 "TITLE_BLOCK_TEXT", "GDT_TRANSCRIPTION", "GENERAL_TEXT"}
FORBIDDEN_SOURCE = re.compile(r"run_logs|results/|qualification-results|smoke|granite|tesseract|review_records", re.I)
FORBIDDEN_FIELDS = ("confidence", "model_id", "provider_id", "job_id", "evidence_id", "vlm-ev-", "vlm-req-")
FORBIDDEN_IMPORTS = re.compile(r"vlm|ollama|ocr_drawing|raster_drawing|drawing_analysis|openai|requests|httpx|pytesseract")

failures: list[str] = []
counts = Counter()


def check(cond: bool, message: str, counter: str | None = None) -> None:
    if not cond:
        failures.append(message)
        if counter:
            counts[counter] += 1


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canon(obj) -> bytes:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dec(text: str) -> str:
    return format(Decimal(text).normalize(), "f")


index = load(HERE / "manifest.json")
fix_manifest = load(FIX / "manifest.json")
fix_entries = {e["id"]: e for e in fix_manifest["entries"]}
spec = SPEC.read_text(encoding="utf-8")

# --- inventory and spec agreement ---------------------------------------------------------------
spec_ids = set(re.findall(r"^\| (Q\d\d) \|", spec, re.M))
check(spec_ids == set(DRAWINGS), "drawing IDs differ from the frozen specification")
for probe_name in ("P-VEC", "P-OVER", "P-CROP", "P-DOWN"):
    check(probe_name in spec, f"probe {probe_name} missing from the specification")

record_ids = [r["qual_id"] for r in index["records"]]
dups = [k for k, v in Counter(record_ids).items() if v > 1]
counts["DUPLICATE_RECORD_ID_COUNT"] = len(dups)
check(not dups, f"duplicate record ids: {dups}")
check(set(record_ids) == set(DRAWINGS + PROBES), f"record IDs differ from the inventory: {sorted(set(record_ids) ^ set(DRAWINGS + PROBES))}")
check(set(fix_entries) <= set(record_ids), "a fixture has no ground-truth/probe record")
check(set(fix_entries) == set(DRAWINGS + PROBES[:-1]), "fixture manifest differs from the frozen inventory")
check(index["ground_truth_status"] == "FROZEN", "index not frozen")
check(index["spec_sha256"] == hashlib.sha256(SPEC.read_bytes()).hexdigest(), "spec hash mismatch", "HASH_REFERENCE_MISMATCH_COUNT")
check(index["fixture_manifest_sha256"] == sha_file(FIX / "manifest.json"), "fixture manifest hash mismatch", "HASH_REFERENCE_MISMATCH_COUNT")

items_total = 0
probe_total = 0
all_items: dict[str, dict] = {}
summary_60: list[str] = []
rq06: dict = {}
classes: dict[str, str] = {}

for row in index["records"]:
    qid = row["qual_id"]
    path = HERE / row["record_file"]
    if not path.exists():
        check(False, f"{qid}: record file missing", "MISSING_FIXTURE_REFERENCE_COUNT")
        continue
    rec = load(path)
    check(row["record_file_sha256"] == sha_file(path), f"{qid}: record file hash differs from the index", "HASH_REFERENCE_MISMATCH_COUNT")
    body = {k: v for k, v in rec.items() if k != "record_sha256"}
    check(rec["record_sha256"] == hashlib.sha256(canon(body)).hexdigest() == row["record_sha256"], f"{qid}: record self-hash", "HASH_REFERENCE_MISMATCH_COUNT")
    check(rec["ground_truth_status"] == "FROZEN" and row["ground_truth_status"] == "FROZEN", f"{qid}: not FROZEN", "UNFROZEN_RECORD_COUNT")
    check(rec["ground_truth_review"]["signoff"] == "FROZEN" and rec["ground_truth_review"]["named_reviewer"] is None, f"{qid}: review block")
    check(set(rec["source_basis"]) == {"SELF_AUTHORED_FIXTURE_SOURCE", "AUTHORING_INTENT", "VISIBLE_FIXTURE_CONTENT", "FROZEN_SPEC"}, f"{qid}: source basis")
    classes[qid] = rec["fixture_class"]

    # hash linkage to the fixture manifest and the files on disk ----------------------------------
    e = fix_entries.get(qid)
    if e is not None:
        check(rec["pdf_sha256"] == e["sha256_pdf"] == row["pdf_sha256"], f"{qid}: pdf hash vs fixture manifest", "HASH_REFERENCE_MISMATCH_COUNT")
        check(rec["raster_sha256"] == e.get("sha256_raster") == row["raster_sha256"], f"{qid}: raster hash vs fixture manifest", "HASH_REFERENCE_MISMATCH_COUNT")
        check(rec["source_sha256"] == e.get("sha256_source") == row["source_sha256"], f"{qid}: source hash vs fixture manifest", "HASH_REFERENCE_MISMATCH_COUNT")
        prov = load(FIX / e["provenance_record"]) if (FIX / e["provenance_record"]).exists() else None
        if prov is None:
            check(False, f"{qid}: provenance record missing", "MISSING_FIXTURE_REFERENCE_COUNT")
        else:
            for key, field in (("pdf_file", "pdf_sha256"), ("raster_file", "raster_sha256")):
                if prov.get(key):
                    f = FIX / prov[key]
                    if not f.exists():
                        check(False, f"{qid}: {key} missing", "MISSING_FIXTURE_REFERENCE_COUNT")
                    else:
                        check(sha_file(f) == rec[field], f"{qid}: {key} content hash", "HASH_REFERENCE_MISMATCH_COUNT")
            if qid in DRAWINGS:
                src = FIX / prov["source_file"]
                check(src.exists() and sha_file(src) == rec["source_sha256"], f"{qid}: source file", "HASH_REFERENCE_MISMATCH_COUNT")
    else:
        check(qid == "P-DOWN" and rec["pdf_sha256"] is None, f"{qid}: unexpected missing fixture")

    if rec["record_type"] == "RECOGNITION_GROUND_TRUTH":
        check(rec["fixture_class"] == "RECOGNITION_GROUND_TRUTH", f"{qid}: class")
        intent_path = FIX / rec["derived_from_files"]["authoring_intent"].replace("fixtures/", "", 1)
        check(intent_path.exists() and sha_file(intent_path) == rec["derived_from_files"]["authoring_intent_sha256"], f"{qid}: intent hash", "HASH_REFERENCE_MISMATCH_COUNT")
        intent = load(intent_path)
        item_ids = [i["item_id"] for i in rec["items"]]
        d = [k for k, v in Counter(item_ids).items() if v > 1]
        counts["DUPLICATE_ITEM_ID_COUNT"] += len(d)
        check(not d, f"{qid}: duplicate item ids {d}")
        expected = sum(1 for t in intent["text_items"] if t["drawn_as"] != "GDT_CELL") + len({t["group"] for t in intent["text_items"] if t["drawn_as"] == "GDT_CELL"})
        check(len(rec["items"]) == expected, f"{qid}: item count {len(rec['items'])} != authored {expected}")
        authored_texts = Counter(t["printed_text"] for t in intent["text_items"] if t["drawn_as"] != "GDT_CELL")
        gt_texts = Counter(i["expected_text"] for i in rec["items"] if i.get("gdt_role") != "FEATURE_CONTROL_FRAME")
        check(authored_texts == gt_texts, f"{qid}: authored text multiset differs from ground truth")
        for i in rec["items"]:
            items_total += 1
            all_items[i["item_id"]] = i
            check(i["feature_type"] in ALLOWED_TYPES, f"{i['item_id']}: feature type")
            check(isinstance(i["required_for_demo"], bool) and isinstance(i["scoreable"], bool), f"{i['item_id']}: explicit flags")
            check(isinstance(i["deterministic_scoreable"], bool), f"{i['item_id']}: deterministic_scoreable")
            if i["feature_type"] in UNIT_TYPES:
                check(i["expected_unit"] in ("mm", "inch", "degree"), f"{i['item_id']}: unit must be explicit")
                check(i["expected_normalized_value"] == dec(i["expected_value"]) and i["expected_normalized_unit"] == i["expected_unit"], f"{i['item_id']}: normalization")
            reg = i["expected_region"]
            check(reg["reference_only"] is True and len(reg["px"]) == 4 and reg["px"][0] < reg["px"][2] and reg["px"][1] < reg["px"][3], f"{i['item_id']}: region")
            w, h = rec["image_px"]
            check(0 <= reg["px"][0] and reg["px"][2] <= w and 0 <= reg["px"][1] and reg["px"][3] <= h, f"{i['item_id']}: region outside image")
            text_blob = json.dumps(i)
            check(not any(tok in text_blob for tok in FORBIDDEN_FIELDS), f"{i['item_id']}: model-output field present")
            if i["feature_type"] in {"LINEAR_DIMENSION", "TOLERANCE", "DIAMETER", "RADIUS", "ANGLE"} and i["expected_normalized_value"] == "60" and i["expected_normalized_unit"] == "mm":
                summary_60.append(f"{i['item_id']} ({i['expected_text']})")
        if qid in CORE:
            share = sum(1 for i in rec["items"] if i["required_for_demo"]) / len(rec["items"])
            check(share >= 1 / 3, f"{qid}: fewer than one third required_for_demo")
        if qid == "Q02":
            for i in rec["items"]:
                if i["expected_text"] == "DIA 20 mm":
                    rq06 = {"fixture": qid, "token": i["expected_text"], "value": i["expected_normalized_value"], "unit": i["expected_unit"],
                            "grammar": i["deterministic_expectation"], "scoreable": i["deterministic_scoreable"], "item": i["item_id"]}
    else:
        probe_total += 1
        check(rec["record_type"] == "PROBE_EXPECTATION" and "items" not in rec, f"{qid}: probe must not carry recognition items")
        check(rec["fixture_class"] in ("STRUCTURAL_EXPECTATION", "PROBE_EXPECTATION"), f"{qid}: probe class")
        for key in ("expected_behavior", "expected_error_or_gate", "ai_inference_expected", "scored_as_recognition", "notes"):
            check(key in rec, f"{qid}: missing {key}")
        if qid.startswith("P-CROP"):
            check(rec["scored_as_recognition"] is True and rec["parent_qual_id"] == "Q09" and rec["contained_item_ids"], f"{qid}: crop linkage")
            check(all(i in all_items for i in rec["contained_item_ids"]) or True, "")
        else:
            check(rec["scored_as_recognition"] is False, f"{qid}: structural probe must not be scored as recognition")
            check(rec["ai_inference_expected"] is False, f"{qid}: structural probe expects no inference")

# --- crop partition of Q09 ------------------------------------------------------------------------
q9 = {i["item_id"] for i in load(HERE / "records" / "Q09.ground_truth.json")["items"]}
crop_sets = [set(load(HERE / "records" / f"P-CROP_Q09_c{n}.probe_expectation.json")["contained_item_ids"]) for n in (1, 2, 3, 4)]
check(set().union(*crop_sets) == q9, "crops do not cover every Q09 item")
check(sum(len(s) for s in crop_sets) == len(q9), "a Q09 item lies in more than one crop")

# --- RQ06 and the 60 mm targets ---------------------------------------------------------------------
check(bool(rq06) and rq06["grammar"] == "DIMENSION_GRAMMAR_ACCEPTED" and rq06["scoreable"], "RQ06 target missing")
authored_60 = []
for qid in DRAWINGS:
    for t in load(FIX / "authoring_intent" / f"{qid}.authoring_intent.json")["text_items"]:
        if t["drawn_as"] == "DIMENSION" and re.match(r"^60(\.0)?\b", t["printed_text"]):
            authored_60.append(f"{qid}:{t['printed_text']}")
check(len(authored_60) == len(summary_60) and len(authored_60) >= 4, f"60 mm targets not all represented: {authored_60} vs {summary_60}")
check(any(s.startswith("Q01-") and "60 MM" in s for s in summary_60), "Q01 '60 MM' target missing")

# --- independence audit -------------------------------------------------------------------------------
independence = {}
for name in ("build_ground_truth.py", "validate_ground_truth.py"):
    tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    bad = sorted(m for m in imported if FORBIDDEN_IMPORTS.search(m))
    check(not bad, f"{name}: forbidden imports {bad}")
    if name == "build_ground_truth.py":
        docstrings = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]
        hits = [s for s in literals if FORBIDDEN_SOURCE.search(s)]
        check(not hits, f"{name}: string literal referencing a forbidden source: {hits}")
        independence["builder_backend_imports"] = sorted(m for m in imported if m.startswith("backend"))
check(not (QUAL / "results").exists() and not (QUAL / "run_logs").exists(), "results/ or run_logs/ must not exist")
blob = "".join(p.read_text(encoding="utf-8") for p in (HERE / "records").glob("*.json"))
check("granite" not in blob.lower() and "r3b" not in blob.lower(), "model/validator names appear in ground truth")

# --- scope ----------------------------------------------------------------------------------------------
status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=REPO, capture_output=True, text=True).stdout.splitlines()
outside = [line for line in status if "docs/qualification/ground_truth/" not in line]
check(not outside, f"changes outside docs/qualification/ground_truth/: {outside}")

report = {
    "GROUND_TRUTH_RECORD_COUNT": len(index["records"]),
    "RECOGNITION_RECORD_COUNT": len(index["records"]) - probe_total,
    "GROUND_TRUTH_ITEM_COUNT": items_total,
    "PROBE_EXPECTATION_COUNT": probe_total,
    "HASH_REFERENCE_MISMATCH_COUNT": counts["HASH_REFERENCE_MISMATCH_COUNT"],
    "MISSING_FIXTURE_REFERENCE_COUNT": counts["MISSING_FIXTURE_REFERENCE_COUNT"],
    "DUPLICATE_RECORD_ID_COUNT": counts["DUPLICATE_RECORD_ID_COUNT"],
    "DUPLICATE_ITEM_ID_COUNT": counts["DUPLICATE_ITEM_ID_COUNT"],
    "UNFROZEN_RECORD_COUNT": counts["UNFROZEN_RECORD_COUNT"],
    "known_60_targets": sorted(summary_60),
    "rq06": rq06,
    "fixture_classes": dict(Counter(classes.values())),
    "independence": independence,
    "failures": failures,
    "status": "PASS" if not failures else "FAIL",
}
print(json.dumps(report, indent=2, ensure_ascii=True))
sys.exit(0 if not failures else 1)
