"""
Cutting Tool Catalog seed data.

Source: Public manufacturer technical catalogs and product pages.

Manufacturers referenced:
  Sandvik Coromant (coromant.sandvik.com)
  Kennametal (kennametal.com)
  Iscar (iscar.com)
  Walter Tools (walter-tools.com)

Geometry for indexable inserts is derived from ISO 1832 designation,
which is the public international standard for insert identification.

Evidence status: MANUFACTURER_CATALOG — curated from public product catalogs.

MISSING_VALUE_AS_ZERO=NO  — all unknown fields are None.
SYNTHETIC_SPECIFICATIONS_ADDED=NO — only published geometry/grades included.
SYNTHETIC_CUTTING_PARAMETERS_ADDED=NO — Vc/fz guidance omitted; consult
    manufacturer application guides for material-specific starting values.
"""

from .catalog_models import CuttingToolCatalogRecord

_SOURCE_TITLE = (
    "MachiningPro AI Cutting Tool Catalog — "
    "curated from public manufacturer technical catalogs"
)
_SOURCE_NOTE = (
    "Sandvik Coromant (coromant.sandvik.com); "
    "Kennametal (kennametal.com); "
    "Iscar (iscar.com); "
    "Walter Tools / Titex (walter-tools.com). "
    "Insert geometry derived from ISO 1832 standard designation. "
    "Cutting guidance fields (Vc, fz) are not included; "
    "consult the manufacturer's current application guide for "
    "material-specific recommended starting values."
)
_EVIDENCE = "MANUFACTURER_CATALOG"
_SOURCE_AUTHORITY = "OFFICIAL_MANUFACTURER_CATALOG"


def _missing(record: dict) -> list[str]:
    """Return names of optional numeric/string fields that are None."""
    optional_fields = [
        "product_family", "catalog_code", "tool_subcategory",
        "tool_material", "coating", "coating_type",
        "insert_shape", "insert_shape_code", "insert_ic_mm",
        "insert_thickness_mm", "nose_radius_mm", "clearance_angle_deg",
        "cutting_diameter_mm", "shank_diameter_mm", "overall_length_mm",
        "cutting_length_mm", "flute_length_mm", "number_of_flutes",
        "helix_angle_deg", "corner_radius_mm", "point_angle_deg",
        "shank_interface", "through_coolant", "max_rpm",
        "compatible_holder_interface",
        "vc_min_mpm", "vc_max_mpm", "fz_min_mm", "fz_max_mm",
        "fn_min_mm", "fn_max_mm", "ap_max_mm",
        "source_note",
    ]
    return [f for f in optional_fields if record.get(f) is None]


def _make(
    stable_id: str,
    manufacturer: str,
    product_name: str,
    tool_category: str,
    tool_category_code: str,
    supported_operations: list[str],
    iso_material_groups: list[str],
    **kwargs,
) -> CuttingToolCatalogRecord:
    base = dict(
        stable_id=stable_id,
        manufacturer=manufacturer,
        product_name=product_name,
        tool_category=tool_category,
        tool_category_code=tool_category_code,
        supported_operations=supported_operations,
        iso_material_groups=iso_material_groups,
        source_title=_SOURCE_TITLE,
        source_authority=_SOURCE_AUTHORITY,
        evidence_status=_EVIDENCE,
        source_note=_SOURCE_NOTE,
    )
    base.update(kwargs)
    base["missing_fields"] = _missing(base)
    return CuttingToolCatalogRecord(**base)


# ── Catalog records ──────────────────────────────────────────────────────────
# Ordered: by manufacturer, then by category

_RECORDS: list[CuttingToolCatalogRecord] = [

    # ── Sandvik Coromant — Turning Inserts ───────────────────────────────────

    _make(
        stable_id="sandvik-cnmg-120408-pm-4325",
        manufacturer="Sandvik Coromant",
        product_family="GC4325",
        product_name="CNMG 12 04 08-PM 4325",
        catalog_code="CNMG 12 04 08-PM 4325",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="External Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="GC4325 CVD Al₂O₃+TiCN",
        coating_type="CVD",
        insert_shape="C — 80° rhombic diamond",
        insert_shape_code="C",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PCLNR/L, DCLNR/L",
    ),

    _make(
        stable_id="sandvik-tnmg-160408-mf-4315",
        manufacturer="Sandvik Coromant",
        product_family="GC4315",
        product_name="TNMG 16 04 08-MF 4315",
        catalog_code="TNMG 16 04 08-MF 4315",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="Finishing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="GC4315 PVD TiAlN",
        coating_type="PVD",
        insert_shape="T — 60° triangle",
        insert_shape_code="T",
        insert_ic_mm=16.5,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PTGNR/L, MTGNR/L",
    ),

    _make(
        stable_id="sandvik-dnmg-150608-m-1125",
        manufacturer="Sandvik Coromant",
        product_family="GC1125",
        product_name="DNMG 15 06 08-M 1125",
        catalog_code="DNMG 15 06 08-M 1125",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="Roughing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["M", "S"],
        tool_material="carbide",
        coating="GC1125 PVD TiAlN",
        coating_type="PVD",
        insert_shape="D — 55° rhombic diamond",
        insert_shape_code="D",
        insert_ic_mm=15.875,
        insert_thickness_mm=6.35,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
    ),

    # ── Sandvik Coromant — End Mills ─────────────────────────────────────────

    _make(
        stable_id="sandvik-r216-33-06045-ac10p-1620",
        manufacturer="Sandvik Coromant",
        product_family="CoroMill Plura R216",
        product_name="R216.33-06045-AC10P 1620",
        catalog_code="R216.33-06045-AC10P 1620",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_subcategory="Ball Nose Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N", "S"],
        tool_material="carbide",
        coating="1620 PVD AlCrN",
        coating_type="PVD",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        overall_length_mm=57.0,
        flute_length_mm=10.0,
        number_of_flutes=2,
        helix_angle_deg=30.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    _make(
        stable_id="sandvik-r216-33-16045-ac26p-1620",
        manufacturer="Sandvik Coromant",
        product_family="CoroMill Plura R216",
        product_name="R216.33-16045-AC26P 1620",
        catalog_code="R216.33-16045-AC26P 1620",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_subcategory="Ball Nose Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N", "S"],
        tool_material="carbide",
        coating="1620 PVD AlCrN",
        coating_type="PVD",
        cutting_diameter_mm=16.0,
        shank_diameter_mm=16.0,
        overall_length_mm=92.0,
        flute_length_mm=26.0,
        number_of_flutes=2,
        helix_angle_deg=30.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Sandvik Coromant — Drills ─────────────────────────────────────────────

    _make(
        stable_id="sandvik-860-1-0800-040a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-0800-040A1-PM N1BU",
        catalog_code="860.1-0800-040A1-PM N1BU",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="N1BU PVD TiAlN",
        coating_type="PVD",
        cutting_diameter_mm=8.0,
        shank_diameter_mm=8.0,
        overall_length_mm=79.0,
        cutting_length_mm=28.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Kennametal — Turning Inserts ──────────────────────────────────────────

    _make(
        stable_id="kennametal-cnmg-120408-ms-kc5525",
        manufacturer="Kennametal",
        product_family="KC5525",
        product_name="CNMG 120408 MS KC5525",
        catalog_code="CNMG 120408 MS KC5525",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="External Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="KC5525 CVD TiCN+Al₂O₃+TiN",
        coating_type="CVD",
        insert_shape="C — 80° rhombic diamond",
        insert_shape_code="C",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PCLNR/L, DCLNR/L",
    ),

    _make(
        stable_id="kennametal-tnmg-160408-fp-kc5525",
        manufacturer="Kennametal",
        product_family="KC5525",
        product_name="TNMG 160408 FP KC5525",
        catalog_code="TNMG 160408 FP KC5525",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="Finishing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="KC5525 CVD TiCN+Al₂O₃+TiN",
        coating_type="CVD",
        insert_shape="T — 60° triangle",
        insert_shape_code="T",
        insert_ic_mm=16.5,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PTGNR/L, MTGNR/L",
    ),

    # ── Kennametal — Drills ───────────────────────────────────────────────────

    _make(
        stable_id="kennametal-b221a-0800-cfh",
        manufacturer="Kennametal",
        product_family="B221A",
        product_name="B221A 8.000 CF H",
        catalog_code="B221A 08.000 CF H",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        cutting_diameter_mm=8.0,
        shank_diameter_mm=8.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Kennametal — End Mills ────────────────────────────────────────────────

    _make(
        stable_id="kennametal-4cfl-12mm-solid-carbide",
        manufacturer="Kennametal",
        product_family="Solid Carbide End Mill",
        product_name="4-Flute Solid Carbide End Mill D=12mm",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        number_of_flutes=4,
        helix_angle_deg=35.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Iscar — Turning Inserts ───────────────────────────────────────────────

    _make(
        stable_id="iscar-cnmg-120408-m-ic8250",
        manufacturer="Iscar",
        product_family="IC8250",
        product_name="CNMG 120408-M IC8250",
        catalog_code="CNMG 120408-M IC8250",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="External Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="IC8250 CVD TiCN+Al₂O₃",
        coating_type="CVD",
        insert_shape="C — 80° rhombic diamond",
        insert_shape_code="C",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PCLNR/L, DCLNR/L",
    ),

    _make(
        stable_id="iscar-dnmg-150608-m-ic8250",
        manufacturer="Iscar",
        product_family="IC8250",
        product_name="DNMG 150608-M IC8250",
        catalog_code="DNMG 150608-M IC8250",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="Roughing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="IC8250 CVD TiCN+Al₂O₃",
        coating_type="CVD",
        insert_shape="D — 55° rhombic diamond",
        insert_shape_code="D",
        insert_ic_mm=15.875,
        insert_thickness_mm=6.35,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
    ),

    # ── Iscar — End Mills ─────────────────────────────────────────────────────

    _make(
        stable_id="iscar-ece-b3-c06x21-cf",
        manufacturer="Iscar",
        product_family="ECE-B3",
        product_name="ECE-B3 C06x21 CF-CF",
        catalog_code="ECE-B3 C06x21 CF-CF",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_subcategory="Ball Nose Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N", "S"],
        tool_material="carbide",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        number_of_flutes=3,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Walter Tools — Turning Inserts ────────────────────────────────────────

    _make(
        stable_id="walter-cnmg-120408-nf6-wsm33s",
        manufacturer="Walter Tools",
        product_family="WSM33S",
        product_name="CNMG 120408-NF6 WSM33S",
        catalog_code="CNMG 120408-NF6 WSM33S",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_subcategory="Finishing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="WSM33S PVD TiAlN",
        coating_type="PVD",
        insert_shape="C — 80° rhombic diamond",
        insert_shape_code="C",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        compatible_holder_interface="PCLNR/L, DCLNR/L",
    ),

    # ── Walter / Titex — Drills ───────────────────────────────────────────────

    _make(
        stable_id="walter-titex-dc150-08-08000a1-wj30et",
        manufacturer="Walter Tools",
        product_family="Titex DC150-08",
        product_name="DC150-08-08.000A1-WJ30ET",
        catalog_code="DC150-08-08.000A1-WJ30ET",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="WJ30ET PVD AlTiN",
        coating_type="PVD",
        cutting_diameter_mm=8.0,
        shank_diameter_mm=8.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── Walter — End Mills ────────────────────────────────────────────────────

    _make(
        stable_id="walter-b2219a-d0600",
        manufacturer="Walter Tools",
        product_family="B2219",
        product_name="B2219.A06-11",
        catalog_code="B2219.A06-11",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        number_of_flutes=4,
        helix_angle_deg=38.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),
]


def get_catalog() -> list[CuttingToolCatalogRecord]:
    """Return a copy of the full curated cutting tool catalog."""
    return list(_RECORDS)


def get_manufacturers() -> list[str]:
    return sorted({r.manufacturer for r in _RECORDS})


def get_categories() -> list[str]:
    return sorted({r.tool_category for r in _RECORDS})


def get_category_codes() -> list[str]:
    return sorted({r.tool_category_code for r in _RECORDS})


def get_operations() -> list[str]:
    ops: set[str] = set()
    for r in _RECORDS:
        ops.update(r.supported_operations)
    return sorted(ops)


def get_tool_materials() -> list[str]:
    return sorted({r.tool_material for r in _RECORDS if r.tool_material})


def get_iso_groups() -> list[str]:
    groups: set[str] = set()
    for r in _RECORDS:
        groups.update(r.iso_material_groups)
    return sorted(groups)
