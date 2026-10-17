from pydantic import BaseModel


class CuttingToolCatalogRecord(BaseModel):
    # Identity
    stable_id: str
    manufacturer: str
    product_family: str | None = None
    product_name: str
    catalog_code: str | None = None

    # Classification
    tool_category: str
    tool_category_code: str
    tool_subcategory: str | None = None

    # Application
    supported_operations: list[str]
    iso_material_groups: list[str]

    # Tool material
    tool_material: str | None = None
    coating: str | None = None
    coating_type: str | None = None

    # Insert geometry (indexable tools)
    insert_shape: str | None = None
    insert_shape_code: str | None = None
    insert_ic_mm: float | None = None
    insert_thickness_mm: float | None = None
    nose_radius_mm: float | None = None
    clearance_angle_deg: float | None = None

    # Solid-tool / drill geometry
    cutting_diameter_mm: float | None = None
    shank_diameter_mm: float | None = None
    overall_length_mm: float | None = None
    cutting_length_mm: float | None = None
    flute_length_mm: float | None = None
    number_of_flutes: int | None = None
    helix_angle_deg: float | None = None
    corner_radius_mm: float | None = None
    point_angle_deg: float | None = None

    # Machine interface
    shank_interface: str | None = None
    through_coolant: bool | None = None
    max_rpm: int | None = None

    # Holder compatibility hint (for future TOOL_HOLDER_CATALOG phase)
    compatible_holder_interface: str | None = None

    # Manufacturer-published cutting guidance (None when not explicitly stated)
    vc_min_mpm: float | None = None
    vc_max_mpm: float | None = None
    fz_min_mm: float | None = None
    fz_max_mm: float | None = None
    fn_min_mm: float | None = None
    fn_max_mm: float | None = None
    ap_max_mm: float | None = None

    # Provenance
    source_title: str
    source_authority: str
    evidence_status: str
    source_note: str | None = None
    missing_fields: list[str]


class CuttingToolCatalogSummary(BaseModel):
    tool_count: int
    manufacturer_count: int
    category_count: int
    tool_material_count: int
    manufacturers: list[str]
    categories: list[str]
    tool_materials: list[str]
    iso_material_groups: list[str]
    source_title: str
    evidence_status: str
