from pydantic import BaseModel


class ToolHolderCatalogRecord(BaseModel):
    # Identity
    stable_id: str
    manufacturer: str
    product_family: str | None = None
    product_name: str
    catalog_code: str | None = None

    # Classification
    holder_category: str        # COLLET_CHUCK, HYDRAULIC_CHUCK, SHRINK_FIT_HOLDER, etc.
    holder_subcategory: str | None = None

    # Machine-side interface
    machine_interface: str      # CAT-40, HSK-A63, SK40, BMT65
    machine_interface_key: str  # normalized form used for compatibility matching
    taper: str | None = None    # e.g. "7:24 (ISO 7388)" for CAT/SK, "1:10 (DIN 69893)" for HSK

    # Tool-side interface
    tool_interface: str         # ER32, ER40, HYDRAULIC, SHRINK_FIT, SHELL_MILL_ARBOR, etc.
    tool_interface_key: str     # normalized
    collet_system: str | None = None              # ER16, ER32, ER40 — None for non-collet holders
    clamping_range_min_mm: float | None = None
    clamping_range_max_mm: float | None = None
    compatible_shank_types: list[str]             # e.g. ["Straight (DIN 6535 HA)"]

    # Geometry
    gauge_length_mm: float | None = None
    projection_mm: float | None = None
    overall_length_mm: float | None = None
    body_diameter_mm: float | None = None
    nose_diameter_mm: float | None = None
    weight_kg: float | None = None

    # Performance
    max_rpm: int | None = None
    balance_grade: str | None = None   # e.g. "G2.5 @ 25000 rpm"
    runout_um: float | None = None
    clamping_force_n: float | None = None
    max_torque_nm: float | None = None

    # Coolant
    through_coolant: bool | None = None
    coolant_pressure_bar: float | None = None

    # Application
    supported_processes: list[str]    # milling, drilling, turning, boring, tapping
    holder_notes: str | None = None

    # Compatibility foundation — keys for future constraint-engine use
    compatible_collet_family: str | None = None
    compatible_tool_shank_family: str | None = None

    # Provenance
    source_title: str
    source_authority: str
    evidence_status: str
    source_note: str | None = None
    missing_fields: list[str]


class ToolHolderCatalogSummary(BaseModel):
    holder_count: int
    manufacturer_count: int
    category_count: int
    machine_interface_count: int
    tool_interface_count: int
    manufacturers: list[str]
    categories: list[str]
    machine_interfaces: list[str]
    tool_interfaces: list[str]
    source_title: str
    evidence_status: str
