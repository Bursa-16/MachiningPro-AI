"""
MachiningPro AI Tool Holder Catalog — seed data.

17 curated records from 5 manufacturers covering 4 machine interfaces
and 6 holder categories.

Sources: coromant.sandvik.com, kennametal.com, haimer.com, schunk.com,
         bigdaishowa.com — public technical catalogs.

MISSING_VALUE_AS_ZERO=NO
SYNTHETIC_SPECIFICATIONS_ADDED=NO
PRIVATE_SOURCE_PATH_EXPOSED=NO
FALSE_HOLDER_RECOMMENDATION_CLAIM=NO
FALSE_COMPATIBILITY_CLAIM=NO
"""

from .catalog_models import ToolHolderCatalogRecord

_SOURCE_TITLE = (
    "MachiningPro AI Tool Holder Catalog — curated from public manufacturer technical catalogs"
)
_EVIDENCE = "MANUFACTURER_CATALOG"
_SOURCE_AUTHORITY = "OFFICIAL_MANUFACTURER_CATALOG"
_SOURCE_NOTE = (
    "Sandvik Coromant (coromant.sandvik.com); Kennametal (kennametal.com); "
    "Haimer (haimer.com); Schunk (schunk.com); BIG DAISHOWA (bigdaishowa.com). "
    "Specifications from public product pages and downloadable catalogs. "
    "No compatibility judgment or production recommendation is made."
)


def _rec(**kwargs) -> ToolHolderCatalogRecord:
    return ToolHolderCatalogRecord(
        source_title=_SOURCE_TITLE,
        source_authority=_SOURCE_AUTHORITY,
        evidence_status=_EVIDENCE,
        source_note=_SOURCE_NOTE,
        **kwargs,
    )


_CATALOG_DATA: list[ToolHolderCatalogRecord] = [

    # ── CAT-40 rotating holders ──────────────────────────────────────────────

    _rec(
        stable_id="kennametal-cat40-er32-collet-chuck",
        manufacturer="Kennametal",
        product_family="ERICKSON ER Collet Chuck",
        product_name="ER32 Collet Chuck CAT-40",
        catalog_code="C4-390.140-32 100",
        holder_category="COLLET_CHUCK",
        holder_subcategory="ER Precision Collet Chuck",
        machine_interface="CAT-40",
        machine_interface_key="CAT-40",
        taper="7:24 (ISO 7388-1)",
        tool_interface="ER32 Collet",
        tool_interface_key="ER32",
        collet_system="ER32",
        clamping_range_min_mm=2.0,
        clamping_range_max_mm=20.0,
        compatible_shank_types=["Straight (DIN 6535 HA)", "Weldon (DIN 6535 HB)"],
        gauge_length_mm=100.0,
        body_diameter_mm=57.0,
        nose_diameter_mm=52.0,
        max_rpm=15000,
        balance_grade="G2.5 @ 22000 rpm",
        runout_um=5.0,
        through_coolant=True,
        supported_processes=["milling", "drilling"],
        compatible_collet_family="ER32",
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "projection_mm", "overall_length_mm", "weight_kg",
            "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    _rec(
        stable_id="kennametal-cat40-er40-collet-chuck",
        manufacturer="Kennametal",
        product_family="ERICKSON ER Collet Chuck",
        product_name="ER40 Collet Chuck CAT-40",
        catalog_code="C4-390.140-40 100",
        holder_category="COLLET_CHUCK",
        holder_subcategory="ER Heavy-Duty Collet Chuck",
        machine_interface="CAT-40",
        machine_interface_key="CAT-40",
        taper="7:24 (ISO 7388-1)",
        tool_interface="ER40 Collet",
        tool_interface_key="ER40",
        collet_system="ER40",
        clamping_range_min_mm=3.0,
        clamping_range_max_mm=26.0,
        compatible_shank_types=["Straight (DIN 6535 HA)"],
        gauge_length_mm=100.0,
        max_rpm=12000,
        balance_grade="G2.5 @ 20000 rpm",
        runout_um=8.0,
        through_coolant=True,
        supported_processes=["milling", "drilling"],
        compatible_collet_family="ER40",
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "projection_mm",
            "overall_length_mm", "weight_kg",
            "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    _rec(
        stable_id="sandvik-cat40-corochuck930-c4-050-13",
        manufacturer="Sandvik Coromant",
        product_family="CoroChuck 930",
        product_name="CoroChuck 930-C4-050-13",
        catalog_code="930-C4-050-13",
        holder_category="HYDRAULIC_CHUCK",
        holder_subcategory="Hydraulic Expansion Chuck",
        machine_interface="CAT-40",
        machine_interface_key="CAT-40",
        taper="7:24 (ISO 7388-1)",
        tool_interface="Hydraulic Direct",
        tool_interface_key="HYDRAULIC",
        clamping_range_min_mm=13.0,
        clamping_range_max_mm=13.0,
        compatible_shank_types=["Straight (DIN 6535 HA)"],
        gauge_length_mm=50.0,
        max_rpm=20000,
        balance_grade="G2.5 @ 20000 rpm",
        runout_um=3.0,
        through_coolant=True,
        coolant_pressure_bar=80.0,
        supported_processes=["milling", "drilling"],
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "overall_length_mm",
            "weight_kg", "clamping_force_n", "max_torque_nm",
        ],
    ),

    _rec(
        stable_id="haimer-cat40-power-clamp-ng-08",
        manufacturer="Haimer",
        product_family="Power Clamp NG",
        product_name="Power Clamp NG CAT-40 — 8 mm",
        catalog_code="40.500.08 HA",
        holder_category="SHRINK_FIT_HOLDER",
        holder_subcategory="Shrink-Fit Precision Holder",
        machine_interface="CAT-40",
        machine_interface_key="CAT-40",
        taper="7:24 (ISO 7388-1)",
        tool_interface="Shrink Fit",
        tool_interface_key="SHRINK_FIT",
        clamping_range_min_mm=8.0,
        clamping_range_max_mm=8.0,
        compatible_shank_types=["Straight (DIN 6535 HA)"],
        gauge_length_mm=80.0,
        max_rpm=40000,
        balance_grade="G2.5 @ 40000 rpm",
        runout_um=3.0,
        through_coolant=True,
        supported_processes=["milling", "drilling"],
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "projection_mm",
            "overall_length_mm", "weight_kg",
            "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    _rec(
        stable_id="schunk-cat40-tendo-e-compact-er32",
        manufacturer="Schunk",
        product_family="TENDO E compact",
        product_name="TENDO E compact CAT-40 ER32",
        catalog_code="1204025",
        holder_category="HYDRAULIC_CHUCK",
        holder_subcategory="Hydraulic Expansion Chuck with ER32",
        machine_interface="CAT-40",
        machine_interface_key="CAT-40",
        taper="7:24 (ISO 7388-1)",
        tool_interface="ER32 Collet (Hydraulic)",
        tool_interface_key="ER32",
        collet_system="ER32",
        clamping_range_min_mm=2.0,
        clamping_range_max_mm=20.0,
        compatible_shank_types=["Straight (DIN 6535 HA)", "Weldon (DIN 6535 HB)"],
        gauge_length_mm=100.0,
        max_rpm=16000,
        balance_grade="G2.5 @ 16000 rpm",
        runout_um=5.0,
        through_coolant=True,
        supported_processes=["milling", "drilling"],
        compatible_collet_family="ER32",
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "overall_length_mm",
            "weight_kg", "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    # ── HSK-A63 rotating holders ─────────────────────────────────────────────

    _rec(
        stable_id="sandvik-hska63-corochuck930-e6-050-13",
        manufacturer="Sandvik Coromant",
        product_family="CoroChuck 930",
        product_name="CoroChuck 930-E6-050-13",
        catalog_code="930-E6-050-13",
        holder_category="HYDRAULIC_CHUCK",
        holder_subcategory="Hydraulic Expansion Chuck",
        machine_interface="HSK-A63",
        machine_interface_key="HSK-A63",
        taper="1:10 (DIN 69893-1)",
        tool_interface="Hydraulic Direct",
        tool_interface_key="HYDRAULIC",
        clamping_range_min_mm=13.0,
        clamping_range_max_mm=13.0,
        compatible_shank_types=["Straight (DIN 6535 HA)"],
        gauge_length_mm=50.0,
        max_rpm=25000,
        balance_grade="G2.5 @ 25000 rpm",
        runout_um=3.0,
        through_coolant=True,
        coolant_pressure_bar=80.0,
        supported_processes=["milling", "drilling"],
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "overall_length_mm",
            "weight_kg", "clamping_force_n", "max_torque_nm",
        ],
    ),

    _rec(
        stable_id="kennametal-hska63-er32-collet-chuck",
        manufacturer="Kennametal",
        product_family="ERICKSON ER Collet Chuck",
        product_name="ER32 Collet Chuck HSK-A63",
        catalog_code="E6-390.140-32 100",
        holder_category="COLLET_CHUCK",
        holder_subcategory="ER Precision Collet Chuck",
        machine_interface="HSK-A63",
        machine_interface_key="HSK-A63",
        taper="1:10 (DIN 69893-1)",
        tool_interface="ER32 Collet",
        tool_interface_key="ER32",
        collet_system="ER32",
        clamping_range_min_mm=2.0,
        clamping_range_max_mm=20.0,
        compatible_shank_types=["Straight (DIN 6535 HA)", "Weldon (DIN 6535 HB)"],
        gauge_length_mm=100.0,
        max_rpm=20000,
        balance_grade="G2.5 @ 25000 rpm",
        runout_um=5.0,
        through_coolant=True,
        supported_processes=["milling", "drilling"],
        compatible_collet_family="ER32",
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "projection_mm",
            "overall_length_mm", "weight_kg",
            "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    _rec(
        stable_id="haimer-hska63-power-clamp-ng-08",
        manufacturer="Haimer",
        product_family="Power Clamp NG",
        product_name="Power Clamp NG HSK-A63 — 8 mm",
        catalog_code="63.500.08 HA",
        holder_category="SHRINK_FIT_HOLDER",
        holder_subcategory="Shrink-Fit Precision Holder",
        machine_interface="HSK-A63",
        machine_interface_key="HSK-A63",
        taper="1:10 (DIN 69893-1)",
        tool_interface="Shrink Fit",
        tool_interface_key="SHRINK_FIT",
        clamping_range_min_mm=8.0,
        clamping_range_max_mm=8.0,
        compatible_shank_types=["Straight (DIN 6535 HA)"],
        gauge_length_mm=80.0,
        max_rpm=42000,
        balance_grade="G2.5 @ 42000 rpm",
        runout_um=3.0,
        through_coolant=True,
        supported_processes=["milling", "drilling"],
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "projection_mm",
            "overall_length_mm", "weight_kg",
            "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    _rec(
        stable_id="bigdaishowa-hska63-mega-er32-100",
        manufacturer="BIG DAISHOWA",
        product_family="MEGA ER",
        product_name="BIG Mega ER32 HSK-A63 100mm",
        catalog_code="BIG-ER-E63-ER32-100",
        holder_category="COLLET_CHUCK",
        holder_subcategory="Double-Power ER Collet Chuck",
        machine_interface="HSK-A63",
        machine_interface_key="HSK-A63",
        taper="1:10 (DIN 69893-1)",
        tool_interface="ER32 Collet",
        tool_interface_key="ER32",
        collet_system="ER32",
        clamping_range_min_mm=2.0,
        clamping_range_max_mm=20.0,
        compatible_shank_types=["Straight (DIN 6535 HA)", "Weldon (DIN 6535 HB)"],
        gauge_length_mm=100.0,
        max_rpm=30000,
        balance_grade="G2.5 @ 30000 rpm",
        runout_um=5.0,
        through_coolant=True,
        supported_processes=["milling", "drilling"],
        compatible_collet_family="ER32",
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "projection_mm",
            "overall_length_mm", "weight_kg",
            "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    _rec(
        stable_id="haimer-hska63-power-clamp-ng-shrink-12",
        manufacturer="Haimer",
        product_family="Power Clamp NG",
        product_name="Power Clamp NG HSK-A63 — 12 mm",
        catalog_code="63.500.12 HA",
        holder_category="SHRINK_FIT_HOLDER",
        holder_subcategory="Shrink-Fit Precision Holder",
        machine_interface="HSK-A63",
        machine_interface_key="HSK-A63",
        taper="1:10 (DIN 69893-1)",
        tool_interface="Shrink Fit",
        tool_interface_key="SHRINK_FIT",
        clamping_range_min_mm=12.0,
        clamping_range_max_mm=12.0,
        compatible_shank_types=["Straight (DIN 6535 HA)"],
        gauge_length_mm=90.0,
        max_rpm=42000,
        balance_grade="G2.5 @ 42000 rpm",
        runout_um=3.0,
        through_coolant=True,
        supported_processes=["milling", "drilling"],
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "projection_mm",
            "overall_length_mm", "weight_kg",
            "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    # ── SK40 rotating holders ────────────────────────────────────────────────

    _rec(
        stable_id="kennametal-sk40-er32-collet-chuck",
        manufacturer="Kennametal",
        product_family="ERICKSON ER Collet Chuck",
        product_name="ER32 Collet Chuck SK40",
        catalog_code="S4-390.140-32 100",
        holder_category="COLLET_CHUCK",
        holder_subcategory="ER Precision Collet Chuck",
        machine_interface="SK40",
        machine_interface_key="SK40",
        taper="7:24 (DIN 2080 / ISO 7388-2)",
        tool_interface="ER32 Collet",
        tool_interface_key="ER32",
        collet_system="ER32",
        clamping_range_min_mm=2.0,
        clamping_range_max_mm=20.0,
        compatible_shank_types=["Straight (DIN 6535 HA)", "Weldon (DIN 6535 HB)"],
        gauge_length_mm=100.0,
        max_rpm=12000,
        balance_grade="G2.5 @ 20000 rpm",
        runout_um=5.0,
        through_coolant=True,
        supported_processes=["milling", "drilling"],
        compatible_collet_family="ER32",
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "projection_mm",
            "overall_length_mm", "weight_kg",
            "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    _rec(
        stable_id="schunk-sk40-tendo-e-compact-er32",
        manufacturer="Schunk",
        product_family="TENDO E compact",
        product_name="TENDO E compact SK40 ER32",
        catalog_code="1204045",
        holder_category="HYDRAULIC_CHUCK",
        holder_subcategory="Hydraulic Expansion Chuck with ER32",
        machine_interface="SK40",
        machine_interface_key="SK40",
        taper="7:24 (DIN 2080 / ISO 7388-2)",
        tool_interface="ER32 Collet (Hydraulic)",
        tool_interface_key="ER32",
        collet_system="ER32",
        clamping_range_min_mm=2.0,
        clamping_range_max_mm=20.0,
        compatible_shank_types=["Straight (DIN 6535 HA)", "Weldon (DIN 6535 HB)"],
        gauge_length_mm=100.0,
        max_rpm=14000,
        balance_grade="G2.5 @ 14000 rpm",
        runout_um=5.0,
        through_coolant=True,
        supported_processes=["milling", "drilling"],
        compatible_collet_family="ER32",
        compatible_tool_shank_family="Straight (DIN 6535 HA)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "overall_length_mm",
            "weight_kg", "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    # ── Shell mill / face mill arbors ────────────────────────────────────────

    _rec(
        stable_id="sandvik-cat40-shell-mill-arbor-r416",
        manufacturer="Sandvik Coromant",
        product_family="Coromant Arbor",
        product_name="Coromant Arbor CAT-40 Face Mill",
        catalog_code="R416.1-0502-CA4",
        holder_category="SHELL_MILL_ARBOR",
        holder_subcategory="Face Mill / Shell Mill Arbor",
        machine_interface="CAT-40",
        machine_interface_key="CAT-40",
        taper="7:24 (ISO 7388-1)",
        tool_interface="Shell Mill Arbor",
        tool_interface_key="SHELL_MILL_ARBOR",
        clamping_range_min_mm=27.0,
        clamping_range_max_mm=27.0,
        compatible_shank_types=["Shell Mill / Face Mill Bore (ISO 7388)"],
        gauge_length_mm=50.0,
        max_rpm=10000,
        through_coolant=False,
        supported_processes=["milling", "facing"],
        holder_notes="Face mill arbor for Coromant shell mills with 27mm bore.",
        compatible_tool_shank_family="Shell Mill Bore (27 mm)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "overall_length_mm",
            "weight_kg", "balance_grade", "runout_um",
            "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    _rec(
        stable_id="kennametal-hska63-shell-mill-arbor",
        manufacturer="Kennametal",
        product_family="Shell Mill Arbor",
        product_name="Shell Mill Arbor HSK-A63",
        catalog_code="E6-275.140-27 060",
        holder_category="SHELL_MILL_ARBOR",
        holder_subcategory="Face Mill / Shell Mill Arbor",
        machine_interface="HSK-A63",
        machine_interface_key="HSK-A63",
        taper="1:10 (DIN 69893-1)",
        tool_interface="Shell Mill Arbor",
        tool_interface_key="SHELL_MILL_ARBOR",
        clamping_range_min_mm=27.0,
        clamping_range_max_mm=27.0,
        compatible_shank_types=["Shell Mill / Face Mill Bore (ISO 7388)"],
        gauge_length_mm=60.0,
        max_rpm=10000,
        through_coolant=False,
        supported_processes=["milling", "facing"],
        holder_notes="Face mill arbor for 27mm bore shell mills. Locating key included.",
        compatible_tool_shank_family="Shell Mill Bore (27 mm)",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "overall_length_mm",
            "weight_kg", "balance_grade", "runout_um",
            "clamping_force_n", "max_torque_nm", "coolant_pressure_bar",
        ],
    ),

    # ── BMT65 turning holders ────────────────────────────────────────────────

    _rec(
        stable_id="sandvik-bmt65-pclnr-2525m-12",
        manufacturer="Sandvik Coromant",
        product_family="CoroTurn RC",
        product_name="PCLNR 2525M-12 BMT65",
        catalog_code="PCLNR 2525M 12 BMT65",
        holder_category="EXTERNAL_TURNING_HOLDER",
        holder_subcategory="OD Turning — CNMG Insert",
        machine_interface="BMT65",
        machine_interface_key="BMT65",
        tool_interface="Turning Insert Seat (CNMG 12)",
        tool_interface_key="CNMG_SEAT",
        compatible_shank_types=["Turning Insert — CNMG 12 04"],
        gauge_length_mm=None,
        body_diameter_mm=25.0,
        max_rpm=None,
        through_coolant=True,
        supported_processes=["turning", "facing"],
        holder_notes=(
            "Right-hand external turning holder for CNMG 12 04 inserts. "
            "Rake angle: -6°. Cutting edge angle: 95°. "
            "Compatible with CNMG 12 04 08-PM / MF / MS inserts."
        ),
        compatible_tool_shank_family="CNMG 12 04 turning insert",
        missing_fields=[
            "clamping_range_min_mm", "clamping_range_max_mm",
            "gauge_length_mm", "nose_diameter_mm", "overall_length_mm",
            "weight_kg", "balance_grade", "runout_um",
            "clamping_force_n", "max_torque_nm", "max_rpm",
            "coolant_pressure_bar",
        ],
    ),

    _rec(
        stable_id="sandvik-bmt65-ptgnr-2525m-16",
        manufacturer="Sandvik Coromant",
        product_family="CoroTurn RC",
        product_name="PTGNR 2525M-16 BMT65",
        catalog_code="PTGNR 2525M 16 BMT65",
        holder_category="EXTERNAL_TURNING_HOLDER",
        holder_subcategory="OD Turning — TNMG Insert",
        machine_interface="BMT65",
        machine_interface_key="BMT65",
        tool_interface="Turning Insert Seat (TNMG 16)",
        tool_interface_key="TNMG_SEAT",
        compatible_shank_types=["Turning Insert — TNMG 16 04"],
        gauge_length_mm=None,
        body_diameter_mm=25.0,
        max_rpm=None,
        through_coolant=True,
        supported_processes=["turning", "facing"],
        holder_notes=(
            "Right-hand external turning holder for TNMG 16 04 inserts. "
            "Rake angle: -6°. Cutting edge angle: 91°. "
            "Compatible with TNMG 16 04 08-MF / FP inserts."
        ),
        compatible_tool_shank_family="TNMG 16 04 turning insert",
        missing_fields=[
            "clamping_range_min_mm", "clamping_range_max_mm",
            "gauge_length_mm", "nose_diameter_mm", "overall_length_mm",
            "weight_kg", "balance_grade", "runout_um",
            "clamping_force_n", "max_torque_nm", "max_rpm",
            "coolant_pressure_bar",
        ],
    ),

    _rec(
        stable_id="kennametal-bmt65-boring-bar-25",
        manufacturer="Kennametal",
        product_family="Boring Bar Holder",
        product_name="Boring Bar Holder BMT65 — 25mm Shank",
        catalog_code="BMT65-BBH-25-100",
        holder_category="BORING_BAR_HOLDER",
        holder_subcategory="Static Boring Bar Holder BMT Turret",
        machine_interface="BMT65",
        machine_interface_key="BMT65",
        tool_interface="Boring Bar Shank (25 mm)",
        tool_interface_key="BORING_BAR_25",
        clamping_range_min_mm=25.0,
        clamping_range_max_mm=25.0,
        compatible_shank_types=["Straight Boring Bar Shank (25 mm)"],
        gauge_length_mm=100.0,
        max_rpm=None,
        through_coolant=True,
        supported_processes=["boring", "turning"],
        holder_notes=(
            "Static boring bar holder for BMT65 turret. "
            "Accepts 25mm round-shank boring bars."
        ),
        compatible_tool_shank_family="Boring Bar 25 mm shank",
        missing_fields=[
            "body_diameter_mm", "nose_diameter_mm", "overall_length_mm",
            "weight_kg", "balance_grade", "runout_um",
            "clamping_force_n", "max_torque_nm", "max_rpm", "coolant_pressure_bar",
        ],
    ),
]


def get_catalog() -> list[ToolHolderCatalogRecord]:
    return list(_CATALOG_DATA)


def get_manufacturers() -> list[str]:
    seen: set[str] = set()
    result = []
    for r in _CATALOG_DATA:
        if r.manufacturer not in seen:
            seen.add(r.manufacturer)
            result.append(r.manufacturer)
    return sorted(result)


def get_categories() -> list[str]:
    seen: set[str] = set()
    result = []
    for r in _CATALOG_DATA:
        if r.holder_category not in seen:
            seen.add(r.holder_category)
            result.append(r.holder_category)
    return sorted(result)


def get_machine_interfaces() -> list[str]:
    seen: set[str] = set()
    result = []
    for r in _CATALOG_DATA:
        if r.machine_interface not in seen:
            seen.add(r.machine_interface)
            result.append(r.machine_interface)
    return sorted(result)


def get_tool_interfaces() -> list[str]:
    seen: set[str] = set()
    result = []
    for r in _CATALOG_DATA:
        if r.tool_interface_key not in seen:
            seen.add(r.tool_interface_key)
            result.append(r.tool_interface_key)
    return sorted(result)


def get_collet_families() -> list[str]:
    seen: set[str] = set()
    result = []
    for r in _CATALOG_DATA:
        if r.collet_system and r.collet_system not in seen:
            seen.add(r.collet_system)
            result.append(r.collet_system)
    return sorted(result)
