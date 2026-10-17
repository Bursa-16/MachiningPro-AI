"""Pydantic models for the Machine Catalog API (MACHINE_CATALOG_DATA_INTEGRATION_01).

Separate from backend.domain.machine.Machine (constraint validation).
This module provides a richer, discovery-oriented record for the browse UI.

All numeric capability fields are Optional — missing values are preserved
as None, never substituted with zero or fabricated.
"""

from __future__ import annotations

from pydantic import BaseModel

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
    spindle_power_kw: float | None = None
    spindle_torque_nm: float | None = None
    spindle_interface: str | None = None   # e.g. "CAT-40", "HSK-A63"

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
    tool_interface: str | None = None
    max_tool_diameter_mm: float | None = None
    max_tool_length_mm: float | None = None

    # --- Dynamics ---
    rapid_traverse_mpm: float | None = None

    # --- Envelope ---
    machine_weight_kg: float | None = None

    # --- Control ---
    controller_family: str | None = None

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
