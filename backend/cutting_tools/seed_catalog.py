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
    "Walter Tools / Titex (walter-tools.com); "
    "OSG Corporation (osg.co.jp). "
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
        "tool_type_code",
        "tool_material", "substrate_grade", "substrate_material_code",
        "coating", "coating_type", "coating_brand",
        "iso_insert_designation", "insert_shape", "insert_shape_code",
        "insert_ic_mm", "insert_thickness_mm", "nose_radius_mm",
        "clearance_angle_deg", "insert_tolerance_class", "insert_hand",
        "cutting_diameter_mm", "shank_diameter_mm", "overall_length_mm",
        "cutting_length_mm", "flute_length_mm", "number_of_flutes",
        "helix_angle_deg", "corner_radius_mm", "point_angle_deg",
        "shank_interface", "through_coolant", "max_rpm",
        "compatible_holder_interface", "arbor_interface",
        "max_ap_mm", "max_ae_mm",
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

    # ── Sandvik Coromant — Reamers ───────────────────────────────────────────

    _make(
        stable_id="sandvik-835b-0801-a1-mf-1024",
        manufacturer="Sandvik Coromant",
        product_family="CoroReamer 835",
        product_name="835.B-0801-A1-MF 1024",
        catalog_code="835.B-0801-A1-MF 1024",
        tool_category="Solid Carbide Reamer",
        tool_category_code="REAMER",
        tool_subcategory="Solid Carbide Reamer Cylindrical Shank",
        supported_operations=["reaming"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="1024 PVD TiAlN",
        coating_type="PVD",
        cutting_diameter_mm=8.01,
        shank_diameter_mm=8.0,
        overall_length_mm=100.0,
        flute_length_mm=64.0,
        cutting_length_mm=16.0,
        number_of_flutes=6,
        through_coolant=True,
        max_rpm=1907,
        shank_interface="Straight (DIN 6535 HA)",
        source_note=(
            "coromant.sandvik.com/en-gb/product-details?c=835.B-0801-A1-MF1024. "
            "Maximum rotational speed 1907 rpm per official product page. "
            "Grade 1024 PVD TiAlN; cylindrical shank DIN6535-HA 8 mm; "
            "cutting diameter 8.01 mm; overall length 100 mm."
        ),
    ),

    # ── Sandvik Coromant — Boring Bars ────────────────────────────────────────

    _make(
        stable_id="sandvik-a25t-sducr-11",
        manufacturer="Sandvik Coromant",
        product_family="CoroTurn 107",
        product_name="A25T-SDUCR 11",
        catalog_code="A25T-SDUCR 11",
        tool_category="Boring Bar",
        tool_category_code="BORING_BAR",
        tool_subcategory="Indexable Boring Bar Steel",
        supported_operations=["boring"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        shank_diameter_mm=25.0,
        overall_length_mm=300.0,
        through_coolant=True,
        shank_interface="Round Shank (25 mm)",
        compatible_holder_interface="Boring Bar Shank (25 mm)",
        source_note=(
            "coromant.sandvik.com/en-us/product-details?c=A25T-SDUCR+11. "
            "25 mm round-shank steel boring bar; minimum bore 32 mm; "
            "internal coolant; CoroTurn 107 insert system (SDUCR, D55 insert). "
            "ISO P/M/K steel and cast iron primary application."
        ),
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
        tool_type_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        number_of_flutes=4,
        helix_angle_deg=38.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── EPIC-03 NEW: Grooving Inserts ─────────────────────────────────────────

    _make(
        stable_id="sandvik-n123g2-0300-0002-cr-1125",
        manufacturer="Sandvik Coromant",
        product_family="CoroCut 1-2",
        product_name="N123G2-0300-0002-CR 1125",
        catalog_code="N123G2-0300-0002-CR 1125",
        tool_category="Grooving Insert",
        tool_category_code="GROOVING_INSERT",
        tool_type_code="GROOVING_INSERT",
        tool_subcategory="Parting / Grooving — 3 mm width",
        supported_operations=["grooving", "parting"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="GC1125 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="GC1125",
        substrate_material_code="CARBIDE",
        coating_brand="Inveio",
        iso_insert_designation="N123G2-0300-0002-CR",
        insert_tolerance_class="M",
        nose_radius_mm=0.2,
        compatible_holder_interface="CoroCut QB N123 blade holder",
    ),

    _make(
        stable_id="sandvik-n123g2-0400-0002-cr-1125",
        manufacturer="Sandvik Coromant",
        product_family="CoroCut 1-2",
        product_name="N123G2-0400-0002-CR 1125",
        catalog_code="N123G2-0400-0002-CR 1125",
        tool_category="Grooving Insert",
        tool_category_code="GROOVING_INSERT",
        tool_type_code="GROOVING_INSERT",
        tool_subcategory="Parting / Grooving — 4 mm width",
        supported_operations=["grooving", "parting"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="GC1125 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="GC1125",
        substrate_material_code="CARBIDE",
        coating_brand="Inveio",
        iso_insert_designation="N123G2-0400-0002-CR",
        insert_tolerance_class="M",
        nose_radius_mm=0.2,
        compatible_holder_interface="CoroCut QB N123 blade holder",
    ),

    _make(
        stable_id="iscar-gtn-3-ic354",
        manufacturer="Iscar",
        product_family="GTN",
        product_name="GTN-3 IC354",
        catalog_code="GTN-3 IC354",
        tool_category="Grooving Insert",
        tool_category_code="GROOVING_INSERT",
        tool_type_code="GROOVING_INSERT",
        tool_subcategory="Parting / Grooving — 3 mm width",
        supported_operations=["grooving", "parting"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="IC354 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="IC354",
        substrate_material_code="CARBIDE",
        iso_insert_designation="GTN-3",
        insert_tolerance_class="M",
        nose_radius_mm=0.2,
    ),

    _make(
        stable_id="kennametal-kgmr-3-kc5010",
        manufacturer="Kennametal",
        product_family="Top Notch",
        product_name="KGMR 3 KC5010",
        catalog_code="KGMR 3 KC5010",
        tool_category="Grooving Insert",
        tool_category_code="GROOVING_INSERT",
        tool_type_code="GROOVING_INSERT",
        tool_subcategory="Parting / Grooving — 3 mm width",
        supported_operations=["grooving", "parting"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="KC5010 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="KC5010",
        substrate_material_code="CARBIDE",
        insert_tolerance_class="M",
        nose_radius_mm=0.2,
    ),

    # ── EPIC-03 NEW: Face Mill Inserts ────────────────────────────────────────

    _make(
        stable_id="sandvik-r245-12t308m-ph-4325",
        manufacturer="Sandvik Coromant",
        product_family="CoroMill 245",
        product_name="R245-12T308M-PH 4325",
        catalog_code="R245-12T308M-PH 4325",
        tool_category="Face Mill Insert",
        tool_category_code="FACE_MILL_INSERT",
        tool_type_code="FACE_MILL_INSERT",
        tool_subcategory="Square Shoulder / Face Milling",
        supported_operations=["face milling", "milling"],
        iso_material_groups=["P", "M"],
        tool_material="carbide",
        coating="GC4325 CVD Al₂O₃+TiCN",
        coating_type="CVD",
        substrate_grade="GC4325",
        substrate_material_code="CARBIDE",
        coating_brand="Inveio",
        iso_insert_designation="R245-12T308",
        insert_ic_mm=12.7,
        nose_radius_mm=0.8,
        insert_tolerance_class="M",
        compatible_holder_interface="CoroMill 245 R245 arbor body",
    ),

    _make(
        stable_id="kennametal-snma-120416-kc5025",
        manufacturer="Kennametal",
        product_family="KC5025",
        product_name="SNMA 120416 KC5025",
        catalog_code="SNMA 120416 KC5025",
        tool_category="Face Mill Insert",
        tool_category_code="FACE_MILL_INSERT",
        tool_type_code="FACE_MILL_INSERT",
        tool_subcategory="Face Milling",
        supported_operations=["face milling", "milling"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="KC5025 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="KC5025",
        substrate_material_code="CARBIDE",
        iso_insert_designation="SNMA 12 04 16",
        insert_shape="S — 90° square",
        insert_shape_code="S",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=1.6,
        clearance_angle_deg=0.0,
        insert_tolerance_class="M",
    ),

    _make(
        stable_id="walter-helx-11t308r57-wxp45",
        manufacturer="Walter Tools",
        product_family="Tiger·tec Gold WXP45",
        product_name="HELX 11T308R-J57 WXP45",
        catalog_code="HELX 11T308R-J57 WXP45",
        tool_category="Face Mill Insert",
        tool_category_code="FACE_MILL_INSERT",
        tool_type_code="FACE_MILL_INSERT",
        tool_subcategory="Face Milling",
        supported_operations=["face milling", "milling"],
        iso_material_groups=["P", "M"],
        tool_material="carbide",
        coating="WXP45 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="WXP45",
        substrate_material_code="CARBIDE",
        coating_brand="Tiger·tec Gold",
        insert_ic_mm=11.0,
        nose_radius_mm=0.8,
        insert_tolerance_class="M",
        compatible_holder_interface="Walter M4001 face mill body",
    ),

    # ── EPIC-03 NEW: Taps (manufacturer: OSG) ────────────────────────────────

    _make(
        stable_id="osg-a-tap-sft-m6x1p0",
        manufacturer="OSG",
        product_family="A-TAP",
        product_name="A-TAP SFT M6×1.0",
        catalog_code="A-TAP SFT M6×1.0",
        tool_category="Tap",
        tool_category_code="TAP",
        tool_type_code="TAP",
        tool_subcategory="Spiral Flute — Blind Hole",
        supported_operations=["tapping"],
        iso_material_groups=["P", "M", "K"],
        tool_material="HSS-E-PM",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="HSS_PM",
        cutting_diameter_mm=6.0,
        shank_diameter_mm=6.0,
        overall_length_mm=66.0,
        number_of_flutes=3,
        through_coolant=False,
        shank_interface="Square drive (ISO 529)",
    ),

    _make(
        stable_id="osg-a-tap-sft-m8x1p25",
        manufacturer="OSG",
        product_family="A-TAP",
        product_name="A-TAP SFT M8×1.25",
        catalog_code="A-TAP SFT M8×1.25",
        tool_category="Tap",
        tool_category_code="TAP",
        tool_type_code="TAP",
        tool_subcategory="Spiral Flute — Blind Hole",
        supported_operations=["tapping"],
        iso_material_groups=["P", "M", "K"],
        tool_material="HSS-E-PM",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="HSS_PM",
        cutting_diameter_mm=8.0,
        shank_diameter_mm=8.0,
        overall_length_mm=80.0,
        number_of_flutes=3,
        through_coolant=False,
        shank_interface="Square drive (ISO 529)",
    ),

    _make(
        stable_id="osg-a-tap-sft-m10x1p5",
        manufacturer="OSG",
        product_family="A-TAP",
        product_name="A-TAP SFT M10×1.5",
        catalog_code="A-TAP SFT M10×1.5",
        tool_category="Tap",
        tool_category_code="TAP",
        tool_type_code="TAP",
        tool_subcategory="Spiral Flute — Blind Hole",
        supported_operations=["tapping"],
        iso_material_groups=["P", "M", "K"],
        tool_material="HSS-E-PM",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="HSS_PM",
        cutting_diameter_mm=10.0,
        shank_diameter_mm=10.0,
        overall_length_mm=90.0,
        number_of_flutes=3,
        through_coolant=False,
        shank_interface="Square drive (ISO 529)",
    ),

    _make(
        stable_id="osg-a-tap-sft-m12x1p75",
        manufacturer="OSG",
        product_family="A-TAP",
        product_name="A-TAP SFT M12×1.75",
        catalog_code="A-TAP SFT M12×1.75",
        tool_category="Tap",
        tool_category_code="TAP",
        tool_type_code="TAP",
        tool_subcategory="Spiral Flute — Blind Hole",
        supported_operations=["tapping"],
        iso_material_groups=["P", "M", "K"],
        tool_material="HSS-E-PM",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="HSS_PM",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        overall_length_mm=100.0,
        number_of_flutes=3,
        through_coolant=False,
        shank_interface="Square drive (ISO 529)",
    ),

    # ── EPIC-03 NEW: Thread Mills ─────────────────────────────────────────────

    _make(
        stable_id="sandvik-n327-08-1505-b-1040",
        manufacturer="Sandvik Coromant",
        product_family="CoroMill 327",
        product_name="N327.08-1505-B 1040",
        catalog_code="N327.08-1505-B 1040",
        tool_category="Thread Mill",
        tool_category_code="THREAD_MILL",
        tool_type_code="THREAD_MILL",
        tool_subcategory="Indexable Thread Mill Body",
        supported_operations=["thread milling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="GC1040 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="GC1040",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=8.0,
        shank_diameter_mm=8.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    _make(
        stable_id="osg-wmf-m8x1p25",
        manufacturer="OSG",
        product_family="WMF-M",
        product_name="WMF-M8×1.25",
        catalog_code="WMF-M8×1.25",
        tool_category="Thread Mill",
        tool_category_code="THREAD_MILL",
        tool_type_code="THREAD_MILL",
        tool_subcategory="Solid Carbide Thread Mill — M8",
        supported_operations=["thread milling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── EPIC-03 NEW: Additional End Mills ────────────────────────────────────

    _make(
        stable_id="sandvik-r216-33-10045-ac16p-1620",
        manufacturer="Sandvik Coromant",
        product_family="CoroMill Plura R216",
        product_name="R216.33-10045-AC16P 1620",
        catalog_code="R216.33-10045-AC16P 1620",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_type_code="END_MILL",
        tool_subcategory="Ball Nose Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N", "S"],
        tool_material="carbide",
        coating="1620 PVD AlCrN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        substrate_grade="GC1620",
        cutting_diameter_mm=10.0,
        shank_diameter_mm=10.0,
        overall_length_mm=72.0,
        flute_length_mm=16.0,
        number_of_flutes=2,
        helix_angle_deg=30.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    _make(
        stable_id="kennametal-ecs-d12-4fl",
        manufacturer="Kennametal",
        product_family="ECS",
        product_name="ECS 12 mm 4-Flute Solid Carbide End Mill",
        catalog_code=None,
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_type_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        number_of_flutes=4,
        helix_angle_deg=35.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    _make(
        stable_id="iscar-ecf-d10-4fl",
        manufacturer="Iscar",
        product_family="EC-F",
        product_name="EC-F 10 mm 4-Flute Solid Carbide End Mill IC900",
        catalog_code=None,
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_type_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="IC900 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="IC900",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=10.0,
        shank_diameter_mm=10.0,
        number_of_flutes=4,
        helix_angle_deg=35.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    _make(
        stable_id="walter-b2219a-d12-4fl",
        manufacturer="Walter Tools",
        product_family="B2219",
        product_name="B2219.A12-11",
        catalog_code="B2219.A12-11",
        tool_category="End Mill",
        tool_category_code="END_MILL",
        tool_type_code="END_MILL",
        tool_subcategory="Square End Solid Carbide",
        supported_operations=["milling"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        number_of_flutes=4,
        helix_angle_deg=38.0,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── EPIC-03 NEW: Additional Drills ────────────────────────────────────────

    _make(
        stable_id="sandvik-860-1-1200-056a1-pm",
        manufacturer="Sandvik Coromant",
        product_family="CoroDrill 860",
        product_name="860.1-1200-056A1-PM 4234",
        catalog_code="860.1-1200-056A1-PM 4234",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_type_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="4234 PVD TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        substrate_grade="GC4234",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    _make(
        stable_id="kennametal-b221a-1200-cfh",
        manufacturer="Kennametal",
        product_family="B221A",
        product_name="B221A 12.000 CF H",
        catalog_code="B221A 12.000 CF H",
        tool_category="Solid Carbide Drill",
        tool_category_code="DRILL",
        tool_type_code="DRILL",
        tool_subcategory="Through-Coolant Solid Carbide Drill",
        supported_operations=["drilling"],
        iso_material_groups=["P", "M", "K", "N"],
        tool_material="carbide",
        coating="TiAlN",
        coating_type="PVD",
        substrate_material_code="CARBIDE",
        cutting_diameter_mm=12.0,
        shank_diameter_mm=12.0,
        number_of_flutes=2,
        point_angle_deg=140.0,
        through_coolant=True,
        shank_interface="Straight (DIN 6535 HA)",
    ),

    # ── EPIC-03 NEW: Additional Turning Inserts ───────────────────────────────

    _make(
        stable_id="sandvik-dcmt-11t304-pf-1105",
        manufacturer="Sandvik Coromant",
        product_family="CoroTurn 107",
        product_name="DCMT 11T304-PF 1105",
        catalog_code="DCMT 11T304-PF 1105",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_type_code="TURNING_INSERT",
        tool_subcategory="Precision Finishing Turning",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "M", "K"],
        tool_material="carbide",
        coating="GC1105 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="GC1105",
        substrate_material_code="CARBIDE",
        coating_brand="Inveio",
        iso_insert_designation="DCMT 11 T3 04",
        insert_shape="D — 55° rhombic diamond",
        insert_shape_code="D",
        insert_ic_mm=11.0,
        insert_thickness_mm=3.97,
        nose_radius_mm=0.4,
        clearance_angle_deg=7.0,
        insert_tolerance_class="M",
        compatible_holder_interface="SDJCR/L, SDNCR/L",
    ),

    _make(
        stable_id="iscar-wnmg-080408-m-ic8250",
        manufacturer="Iscar",
        product_family="IC8250",
        product_name="WNMG 080408-M IC8250",
        catalog_code="WNMG 080408-M IC8250",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_type_code="TURNING_INSERT",
        tool_subcategory="Roughing — Stainless and High-Alloy",
        supported_operations=["turning", "facing"],
        iso_material_groups=["M", "S"],
        tool_material="carbide",
        coating="IC8250 PVD TiAlN",
        coating_type="PVD",
        substrate_grade="IC8250",
        substrate_material_code="CARBIDE",
        iso_insert_designation="WNMG 08 04 08",
        insert_shape="W — 80° trigon",
        insert_shape_code="W",
        insert_ic_mm=12.7,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.8,
        clearance_angle_deg=0.0,
        insert_tolerance_class="M",
        compatible_holder_interface="PWLNR/L, MWLNR/L",
    ),

    _make(
        stable_id="walter-vnmg-160404-nf4-wpp20c",
        manufacturer="Walter Tools",
        product_family="WPP20C",
        product_name="VNMG 160404-NF4 WPP20C",
        catalog_code="VNMG 160404-NF4 WPP20C",
        tool_category="Turning Insert",
        tool_category_code="TURNING_INSERT",
        tool_type_code="TURNING_INSERT",
        tool_subcategory="Finishing — Steel",
        supported_operations=["turning", "facing"],
        iso_material_groups=["P", "K"],
        tool_material="carbide",
        coating="WPP20C CVD Al₂O₃",
        coating_type="CVD",
        substrate_grade="WPP20C",
        substrate_material_code="CARBIDE",
        coating_brand="Tiger·tec Silver",
        iso_insert_designation="VNMG 16 04 04",
        insert_shape="V — 35° rhombic",
        insert_shape_code="V",
        insert_ic_mm=16.5,
        insert_thickness_mm=4.76,
        nose_radius_mm=0.4,
        clearance_angle_deg=0.0,
        insert_tolerance_class="M",
        compatible_holder_interface="SVJBR/L",
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


def get_substrate_codes() -> list[str]:
    return sorted({r.substrate_material_code for r in _RECORDS if r.substrate_material_code})


def get_coating_types() -> list[str]:
    return sorted({r.coating_type for r in _RECORDS if r.coating_type})
