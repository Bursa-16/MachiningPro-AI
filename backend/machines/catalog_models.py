"""Pydantic models for the Machine Catalog API (MACHINE_CATALOG_DATA_INTEGRATION_01).

Separate from backend.domain.machine.Machine (constraint validation).
This module provides a richer, discovery-oriented record for the browse UI.

All numeric capability fields are Optional — missing values are preserved
as None, never substituted with zero or fabricated.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["MachineCatalogRecord", "MachineCatalogSummary"]


class MachineCatalogRecord(BaseModel):
    """One machine entry in the curated catalog."""

    # --- Identity ---
    stable_id: str
    manufacturer: str
    model: str
    family: str | None = None
    machine_type: str        # e.g. "Vertical Machining Center"
    machine_type_code: str   # short code: "VMC", "LATHE", "5AXIS", "MILL_TURN"

    # --- Capability ---
    supported_processes: list[str]
    axis_count: int
    simultaneous_axis_count: int | None = None
    turning_capable: bool
    milling_capable: bool
    drilling_capable: bool

    # --- Spindle ---
    spindle_max_rpm: int | None = None
    spindle_min_rpm: int | None = None
    spindle_power_kw: float | None = None
    spindle_power_continuous_kw: float | None = None
    spindle_power_peak_kw: float | None = None
    spindle_torque_nm: float | None = None
    spindle_torque_continuous_nm: float | None = None
    spindle_torque_peak_nm: float | None = None
    spindle_torque_at_rpm: int | None = None
    spindle_interface: str | None = None   # e.g. "CAT-40", "HSK-A63"
    spindle_interfaces_supported: list[str] = Field(default_factory=list)

    # --- Axes & kinematics ---
    axis_summary: str | None = None
    kinematics_type: str | None = None

    # --- Workspace ---
    travel_x_mm: float | None = None
    travel_y_mm: float | None = None
    travel_z_mm: float | None = None
    table_length_mm: float | None = None
    table_width_mm: float | None = None
    table_load_kg: float | None = None
    max_turning_diameter_mm: float | None = None
    max_turning_length_mm: float | None = None
    bar_capacity_mm: float | None = None

    # --- Tool system ---
    tool_magazine_capacity: int | None = None
    tool_magazine_type: str | None = None
    tool_interface: str | None = None
    max_tool_diameter_mm: float | None = None
    max_tool_diameter_adj_mm: float | None = None
    max_tool_length_mm: float | None = None
    atc_chip_to_chip_sec: float | None = None
    atc_tool_to_tool_sec: float | None = None

    # --- Dynamics ---
    rapid_traverse_mpm: float | None = None
    rapid_x_mpm: float | None = None
    rapid_y_mpm: float | None = None
    rapid_z_mpm: float | None = None
    max_cutting_feed_mm_min: float | None = None

    # --- Coolant & process support ---
    through_spindle_coolant: bool | None = None
    coolant_pressure_bar: float | None = None
    mql_support: bool | None = None
    flood_coolant: bool = True
    chip_conveyor: bool | None = None

    # --- Machine features (boolean flags) ---
    has_subspindle: bool = False
    has_y_axis: bool = False
    has_live_tooling: bool = False
    has_b_axis: bool = False
    has_pallet_changer: bool = False

    # --- Process capabilities ---
    capable_tapping: bool | None = None
    capable_boring: bool | None = None
    capable_threading: bool | None = None
    capable_reaming: bool | None = None
    capable_5axis_simultaneous: bool | None = None
    capable_3plus2: bool | None = None

    # --- Control ---
    controller_family: str | None = None
    controller_model: str | None = None
    controller_generation: str | None = None
    nc_dialect: str | None = None

    # --- Accuracy ---
    positioning_accuracy_um: float | None = None
    repeatability_um: float | None = None

    # --- Envelope ---
    machine_weight_kg: float | None = None

    # --- Lineage ---
    year_introduced: int | None = None
    year_discontinued: int | None = None
    country_of_origin: str | None = None

    # --- Evidence ---
    source_title: str
    evidence_status: str   # "MANUFACTURER_DATASHEET"
    source_note: str | None = None
    missing_fields: list[str]  # field names that carry None in this record


class MachineCatalogSummary(BaseModel):
    """Aggregate statistics for the catalog."""

    machine_count: int
    manufacturer_count: int
    machine_type_count: int
    manufacturers: list[str]
    machine_types: list[str]
    source_title: str
    evidence_status: str
