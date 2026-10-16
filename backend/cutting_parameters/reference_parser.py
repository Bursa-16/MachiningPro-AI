"""Parser for the MachiningPro cutting-parameter reference report (Markdown).

Source document
---------------
``Programlar/MachiningPro AI için Kesici Takımlar, Takım Tutucular ve
Talaşlı İmalat Kesme Parametreleri Araştırma Raporu.md``

The source explicitly states (section "Genel endüstri kesme parametreleri"):

    "Bu rapordaki sayısal kesme parametreleri spesifik bir takım kodunun
    üretici katalog değerleri değildir … bunlar MachiningPro AI'nin ilk veri
    tabanı/ön seçim katmanında kullanılabilecek genel endüstri başlangıç
    zarflarıdır."

    ("The numerical cutting parameters in this report are NOT manufacturer
    catalog values for a specific tool code … they are general industry
    starting envelopes suitable for MachiningPro AI's initial database /
    pre-selection layer.")

Therefore ALL records produced by this parser carry EvidenceStatus.REFERENCE_ONLY.
They MUST NOT be used as authoritative production NC parameters.

Four operation tables are parsed: TURNING, MILLING, DRILLING, REAMING.
The BROACHING table is excluded: the source itself flags it as "especially
low-confidence general engineering envelopes" (düşük güven seviyeli).

Record-ID scheme
----------------
``REF_{OPERATION}_{ISO_SUB}_{PARAM}``

Examples: REF_TURN_P_VC, REF_MILL_S_TI_FZ, REF_DRILL_N_FN, REF_REAM_S_F
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from backend.cutting_parameters.models import (
    ApplicabilityScope,
    CuttingParameterRecord,
    EvidenceStatus,
    ParameterType,
    QuantityRange,
)
from backend.domain.base import Provenance
from backend.domain.enums import (
    IsoMaterialGroup,
    OperationType,
    ProvenanceType,
    ToolMaterial,
)
from backend.domain.units import Quantity, Unit

__all__ = ["parse_reference_report"]

# ---------------------------------------------------------------------------
# Source description (used as provenance.source_reference)
# ---------------------------------------------------------------------------

_SOURCE_REFERENCE = (
    "MachiningPro AI Kesici Takımlar Araştırma Raporu "
    "(genel endüstri başlangıç zarfları; Sandvik/Kennametal/ISO kaynaklı "
    "araştırma sentezi — REFERENCE_ONLY, üretim NC parametresi değil)"
)


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _tr_decimal(s: str) -> Decimal:
    """Convert Turkish/source decimal string to Decimal.

    Strips trailing ``*`` (grade-dependent note) and ``+`` (potentially
    higher) markers.  Replaces Turkish decimal comma with period.
    """
    cleaned = s.strip().rstrip("*+ \t").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Cannot convert to Decimal: {s!r}") from exc


def _parse_range(cell: str) -> tuple[Decimal, Decimal]:
    """Parse a ``min–max`` range cell to (min_val, max_val).

    Accepts en-dash (U+2013), em-dash (U+2014), and ASCII hyphen as range
    separator.  Trailing ``*`` or ``+`` markers are stripped before parsing.
    """
    s = cell.strip().rstrip("*+ \t")
    for dash in ("–", "—"):  # en-dash, em-dash
        if dash in s:
            lo, hi = s.split(dash, 1)
            return _tr_decimal(lo), _tr_decimal(hi)
    # ASCII hyphen — must not be a leading minus sign on the first token
    m = re.match(r"^(\d[\d,\.]*)\s*-\s*(\d[\d,\.]*)$", s)
    if m:
        return _tr_decimal(m.group(1)), _tr_decimal(m.group(2))
    raise ValueError(f"Cannot parse range from cell: {cell!r}")


def _quantity_range(lo: Decimal, hi: Decimal, unit: Unit) -> QuantityRange:
    return QuantityRange(
        min_value=Quantity(lo, unit),
        max_value=Quantity(hi, unit),
    )


# ---------------------------------------------------------------------------
# Table-row parsing helpers
# ---------------------------------------------------------------------------

def _parse_table_rows(lines: list[str]) -> list[list[str]]:
    """Return data rows (not the header or separator) from a markdown table.

    Each element is a list of stripped cell strings.
    """
    rows: list[list[str]] = []
    header_seen = False
    separator_seen = False
    for line in lines:
        cells = [c.strip() for c in line.split("|")]
        # drop the leading and trailing empty cells from ``| a | b |``
        cells = [c for c in cells if c != ""]
        if not cells:
            continue
        if not header_seen:
            header_seen = True
            continue  # skip header
        if not separator_seen:
            # separator row: all cells are like ``---`` or ``:---:``
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                separator_seen = True
                continue
        rows.append(cells)
    return rows


def _identify_table(header_line: str) -> str | None:
    """Return table type tag from the header row, or None if unrecognised."""
    h = header_line
    if "fz" in h:
        return "MILLING"
    if "fn" in h:
        return "DRILLING"
    if "Radyal" in h or "radyal" in h:
        return "REAMING"
    # Turning header contains the unique phrase "Tercih edilen" or has both
    # "f, mm" and "ap"
    if "Tercih" in h or ("ap" in h and "f, mm" in h):
        return "TURNING"
    return None


# ---------------------------------------------------------------------------
# Material-group mapping
# ---------------------------------------------------------------------------

def _map_material_cell(
    raw: str,
    operation: str,
) -> tuple[IsoMaterialGroup, str, str | None]:
    """Map a raw material cell to (IsoMaterialGroup, id_sub, note).

    ``id_sub`` is the stable component used in record IDs.
    ``note`` carries sub-group disambiguation text.
    """
    t = raw.strip()
    t_lower = t.lower()

    # --- ISO S sub-groups (must be checked before generic 'S') ---
    if "s ti" in t_lower or "s  ti" in t_lower or (
        "iso s ti" in t_lower
    ):
        return IsoMaterialGroup.S, "S_TI", "Titanium alloys (ISO S sub-group)"
    if "s ni" in t_lower or "s  ni" in t_lower or (
        "iso s ni" in t_lower
    ):
        return IsoMaterialGroup.S, "S_NI", "Ni/Co HRSA alloys (ISO S sub-group)"
    if "ni-hrsa" in t_lower or "ni hrsa" in t_lower:
        return IsoMaterialGroup.S, "S_NI", "Ni/Co HRSA alloys (ISO S sub-group)"
    # titanium standalone (drilling table)
    if t_lower in ("ti", "iso s ti") or t_lower.startswith("ti ") or t_lower.startswith("iso s ti"):
        return IsoMaterialGroup.S, "S_TI", "Titanium alloys (ISO S sub-group)"

    # --- ISO N sub-groups ---
    if "n al-si" in t_lower or "n  al-si" in t_lower or "iso n al-si" in t_lower:
        return IsoMaterialGroup.N, "N_ALSI", "High-Si aluminium alloys (ISO N)"
    if (
        "n al" in t_lower or "n  al" in t_lower
        or "iso n al" in t_lower
        or "al demir dışı" in t_lower
    ):
        return IsoMaterialGroup.N, "N_AL", "Aluminium alloys (ISO N)"

    # --- Generic ISO groups ---
    for group_char, id_sub, note in [
        ("iso p", "P", "Steel (ISO P group)"),
        ("iso m", "M", "Stainless steel (ISO M group)"),
        ("iso k", "K", "Cast iron (ISO K group)"),
        ("iso n", "N", "Non-ferrous metals (ISO N group)"),
        ("iso s", "S", "Ti/HRSA alloys (ISO S group)"),
        ("iso h", "H", "Hardened materials (ISO H group)"),
    ]:
        if group_char in t_lower:
            grp = IsoMaterialGroup(id_sub[0] if id_sub in ("P","M","K","N","S","H") else id_sub)
            return grp, id_sub, note

    # Single-letter headings (milling/drilling/reaming tables)
    single = {"p": ("P", "Steel (ISO P group)"),
               "m": ("M", "Stainless steel (ISO M group)"),
               "k": ("K", "Cast iron (ISO K group)"),
               "n": ("N", "Non-ferrous metals (ISO N group)"),
               "s": ("S", "Ti/HRSA alloys (ISO S group)"),
               "h": ("H", "Hardened materials (ISO H group)")}
    # strip "iso " prefix and extra words, then check first char
    stripped = t_lower.replace("iso ", "").strip()
    first_letter = stripped[0] if stripped else ""
    if first_letter in single:
        sub, note = single[first_letter]
        return IsoMaterialGroup(first_letter.upper()), sub, note

    raise ValueError(
        f"Cannot map material cell to ISO group: {raw!r} (operation={operation})"
    )


# ---------------------------------------------------------------------------
# Tool-material mapping
# ---------------------------------------------------------------------------

def _map_tool_material(raw: str) -> ToolMaterial | None:
    """Map raw tool-material cell text to ToolMaterial enum."""
    t = raw.strip().lower()
    if "pcd" in t and "karbür" in t:
        return ToolMaterial.CARBIDE  # primary; note indicates PCD variant too
    if "pcd" in t:
        return ToolMaterial.PCD
    if "cbn" in t and "karbür" in t:
        return ToolMaterial.CARBIDE  # primary; note indicates CBN variant
    if "cbn" in t:
        return ToolMaterial.CBN
    if "sialon" in t or "whisker" in t or "seramik" in t or "ceramic" in t:
        return ToolMaterial.CERAMIC
    if "karbür" in t or "carbide" in t:
        return ToolMaterial.CARBIDE
    if "hss" in t:
        return ToolMaterial.HSS
    return None


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------

def _make_provenance(source_document: str, section: str) -> Provenance:
    return Provenance(
        source_type=ProvenanceType.LITERATURE,
        source_reference=_SOURCE_REFERENCE,
        source_document=source_document,
        page_section=section,
    )


def _make_record(
    record_id: str,
    parameter_type: ParameterType,
    lo: Decimal,
    hi: Decimal,
    unit: Unit,
    operation: OperationType,
    iso_group: IsoMaterialGroup,
    tool_material: ToolMaterial | None,
    provenance: Provenance,
    notes: str | None = None,
) -> CuttingParameterRecord:
    return CuttingParameterRecord(
        record_id=record_id,
        parameter_type=parameter_type,
        value_range=_quantity_range(lo, hi, unit),
        applicability=ApplicabilityScope(
            operation_type=operation,
            iso_material_group=iso_group,
            tool_material=tool_material,
            notes=notes,
        ),
        provenance=provenance,
        evidence_status=EvidenceStatus.REFERENCE_ONLY,
    )


# ---------------------------------------------------------------------------
# Per-operation table parsers
# ---------------------------------------------------------------------------

def _parse_turning_table(
    rows: list[list[str]], provenance: Provenance
) -> list[CuttingParameterRecord]:
    """Parse turning table rows.

    Expected column order (0-based after splitting by |):
        0: Malzeme  1: Tool  2: Vc  3: f(mm/rev)  4: ap
    """
    records: list[CuttingParameterRecord] = []
    op = OperationType.TURNING

    # Turning has two S-Ni rows distinguished by tool material (carbide vs ceramic)
    ni_carbide_seen = False

    for cells in rows:
        if len(cells) < 5:
            continue
        mat_raw = cells[0]
        tool_raw = cells[1]
        vc_raw = cells[2]
        f_raw = cells[3]
        ap_raw = cells[4]

        try:
            iso_group, iso_sub, note = _map_material_cell(mat_raw, "TURNING")
        except ValueError:
            continue  # skip unrecognised rows

        tool_mat = _map_tool_material(tool_raw)

        # For S_NI distinguish carbide from ceramic via tool_mat
        if iso_sub == "S_NI":
            if tool_mat == ToolMaterial.CERAMIC:
                iso_sub = "S_NI_SER"
                note = "Ni/Co HRSA alloys — ceramic (SiAlON/whisker)"
            else:
                if ni_carbide_seen:
                    iso_sub = "S_NI_C"
                    note = "Ni/Co HRSA alloys — carbide"
                else:
                    ni_carbide_seen = True
                    iso_sub = "S_NI_C"
                    note = "Ni/Co HRSA alloys — carbide"

        prov = provenance

        try:
            vc_lo, vc_hi = _parse_range(vc_raw)
            f_lo, f_hi = _parse_range(f_raw)
            ap_lo, ap_hi = _parse_range(ap_raw)
        except (ValueError, InvalidOperation):
            continue

        prefix = f"REF_TURN_{iso_sub}"
        records.append(_make_record(
            f"{prefix}_VC", ParameterType.CUTTING_SPEED,
            vc_lo, vc_hi, Unit.M_MIN, op, iso_group, tool_mat, prov, note,
        ))
        records.append(_make_record(
            f"{prefix}_F", ParameterType.FEED_PER_REV,
            f_lo, f_hi, Unit.MM_REV, op, iso_group, tool_mat, prov, note,
        ))
        records.append(_make_record(
            f"{prefix}_AP", ParameterType.AXIAL_DEPTH_OF_CUT,
            ap_lo, ap_hi, Unit.MM, op, iso_group, tool_mat, prov, note,
        ))

    return records


def _parse_milling_table(
    rows: list[list[str]], provenance: Provenance
) -> list[CuttingParameterRecord]:
    """Parse milling table rows.

    Expected column order: 0: Malzeme  1: Tool  2: Vc  3: fz  4: ap
    """
    records: list[CuttingParameterRecord] = []
    op = OperationType.MILLING

    for cells in rows:
        if len(cells) < 5:
            continue
        mat_raw, tool_raw, vc_raw, fz_raw, ap_raw = (
            cells[0], cells[1], cells[2], cells[3], cells[4]
        )

        try:
            iso_group, iso_sub, note = _map_material_cell(mat_raw, "MILLING")
            tool_mat = _map_tool_material(tool_raw)
            vc_lo, vc_hi = _parse_range(vc_raw)
            fz_lo, fz_hi = _parse_range(fz_raw)
            ap_lo, ap_hi = _parse_range(ap_raw)
        except (ValueError, InvalidOperation):
            continue

        prefix = f"REF_MILL_{iso_sub}"
        records.append(_make_record(
            f"{prefix}_VC", ParameterType.CUTTING_SPEED,
            vc_lo, vc_hi, Unit.M_MIN, op, iso_group, tool_mat, provenance, note,
        ))
        records.append(_make_record(
            f"{prefix}_FZ", ParameterType.FEED_PER_TOOTH,
            fz_lo, fz_hi, Unit.MM_TOOTH, op, iso_group, tool_mat, provenance, note,
        ))
        records.append(_make_record(
            f"{prefix}_AP", ParameterType.AXIAL_DEPTH_OF_CUT,
            ap_lo, ap_hi, Unit.MM, op, iso_group, tool_mat, provenance, note,
        ))

    return records


def _parse_drilling_table(
    rows: list[list[str]], provenance: Provenance
) -> list[CuttingParameterRecord]:
    """Parse drilling table rows.

    Expected column order: 0: Malzeme  1: Vc  2: fn  [3: note (ignored)]

    The source header says "6–12 mm solid carbide drill" → ToolMaterial.CARBIDE.
    No ap column: depth is L/D-governed, not a fixed ap range (Hard Rule 12).
    """
    records: list[CuttingParameterRecord] = []
    op = OperationType.DRILLING

    for cells in rows:
        if len(cells) < 3:
            continue
        mat_raw, vc_raw, fn_raw = cells[0], cells[1], cells[2]

        try:
            iso_group, iso_sub, note = _map_material_cell(mat_raw, "DRILLING")
            vc_lo, vc_hi = _parse_range(vc_raw)
            fn_lo, fn_hi = _parse_range(fn_raw)
        except (ValueError, InvalidOperation):
            continue

        prefix = f"REF_DRILL_{iso_sub}"
        records.append(_make_record(
            f"{prefix}_VC", ParameterType.CUTTING_SPEED,
            vc_lo, vc_hi, Unit.M_MIN, op, iso_group, ToolMaterial.CARBIDE, provenance, note,
        ))
        records.append(_make_record(
            f"{prefix}_FN", ParameterType.FEED_PER_REV,
            fn_lo, fn_hi, Unit.MM_REV, op, iso_group, ToolMaterial.CARBIDE, provenance, note,
        ))

    return records


def _parse_reaming_table(
    rows: list[list[str]], provenance: Provenance
) -> list[CuttingParameterRecord]:
    """Parse reaming table rows.

    Expected column order: 0: Malzeme  1: Vc  2: f(mm/rev)  3: Radyal (ignored)

    The 4th column ("Radyal işleme payı") is a radial stock allowance, NOT ap.
    Hard Rule 12: no ap records for reaming from this source.
    """
    records: list[CuttingParameterRecord] = []
    op = OperationType.REAMING

    for cells in rows:
        if len(cells) < 3:
            continue
        mat_raw, vc_raw, f_raw = cells[0], cells[1], cells[2]

        try:
            iso_group, iso_sub, note = _map_material_cell(mat_raw, "REAMING")
            vc_lo, vc_hi = _parse_range(vc_raw)
            f_lo, f_hi = _parse_range(f_raw)
        except (ValueError, InvalidOperation):
            continue

        prefix = f"REF_REAM_{iso_sub}"
        records.append(_make_record(
            f"{prefix}_VC", ParameterType.CUTTING_SPEED,
            vc_lo, vc_hi, Unit.M_MIN, op, iso_group, None, provenance, note,
        ))
        records.append(_make_record(
            f"{prefix}_F", ParameterType.FEED_PER_REV,
            f_lo, f_hi, Unit.MM_REV, op, iso_group, None, provenance, note,
        ))

    return records


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_reference_report(
    path: Path,
) -> tuple[CuttingParameterRecord, ...]:
    """Parse the cutting-parameter reference report and return all records.

    Reads the Markdown file at *path*, extracts the four operation tables
    (TURNING, MILLING, DRILLING, REAMING), and returns one
    :class:`~backend.cutting_parameters.models.CuttingParameterRecord` per
    (operation, ISO group, parameter-type) combination.

    All returned records carry ``EvidenceStatus.REFERENCE_ONLY``.

    Args:
        path: Absolute path to the Markdown research report.

    Returns:
        Tuple of CuttingParameterRecord in deterministic record-ID order.

    Raises:
        FileNotFoundError: when *path* does not exist.
        ValueError: when fewer than 2 operation tables are parsed
                    (likely a format change in the source file).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Reference report not found: {path}")

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    source_doc = str(path)

    # Collect consecutive | lines into table blocks
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            current.append(stripped)
        else:
            if len(current) >= 3:
                blocks.append(current)
            current = []
    if len(current) >= 3:
        blocks.append(current)

    all_records: list[CuttingParameterRecord] = []
    parsed_ops: set[str] = set()

    for block in blocks:
        if not block:
            continue
        header = block[0]
        table_type = _identify_table(header)
        if table_type is None:
            continue
        if table_type in parsed_ops:
            continue  # skip duplicates (e.g. tool-material compat matrix)
        parsed_ops.add(table_type)

        rows = _parse_table_rows(block)
        prov = _make_provenance(source_doc, f"{table_type.title()} table")

        if table_type == "TURNING":
            all_records.extend(_parse_turning_table(rows, prov))
        elif table_type == "MILLING":
            all_records.extend(_parse_milling_table(rows, prov))
        elif table_type == "DRILLING":
            all_records.extend(_parse_drilling_table(rows, prov))
        elif table_type == "REAMING":
            all_records.extend(_parse_reaming_table(rows, prov))

    if len(parsed_ops) < 2:
        raise ValueError(
            f"Expected at least 2 operation tables; got {parsed_ops!r}. "
            "The reference report may have changed format."
        )

    return tuple(sorted(all_records, key=lambda r: r.record_id))
