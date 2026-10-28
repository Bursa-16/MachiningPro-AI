"""Shop calibration profile — EPIC_04F.

SHOP_CALIBRATION_PROFILE_IMPLEMENTED=YES
CUSTOMER_CALIBRATION_DATA_COMMITTED=NO
FABRICATED_SETUP_TIME=NO
FABRICATED_TOOL_CHANGE_TIME=NO
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from backend.calibration.models import CalibrationConfidence, CalibrationSource

__all__ = [
    "ShopCalibrationProfile",
    "ShopProfileStore",
    "PROFILE_STORE",
]


class ShopCalibrationProfile(BaseModel):
    """Shop-validated calibration profile for a site/machine/operation context.

    All timing/capability fields are optional.
    None = not measured, not estimated.
    FABRICATED_SETUP_TIME=NO
    FABRICATED_TOOL_CHANGE_TIME=NO
    """

    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str
    site_id: str | None = None
    machine_id: str | None = None
    operation_family: str | None = None
    material_iso_group: str | None = None
    tool_family: str | None = None
    feature_type: str | None = None

    atc_time_sec: float | None = None
    setup_time_sec: float | None = None
    load_unload_time_sec: float | None = None
    probing_time_sec: float | None = None
    inspection_time_sec: float | None = None

    validated_it_grade_min: int | None = None
    validated_ra_um: float | None = None

    source: CalibrationSource = CalibrationSource.SHOP_VALIDATED
    confidence: CalibrationConfidence = CalibrationConfidence.HIGH
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    revision: int = 1


class ShopProfileStore:
    """In-memory store for shop calibration profiles.

    CUSTOMER_CALIBRATION_DATA_COMMITTED=NO — runtime state only.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, ShopCalibrationProfile] = {}

    def create(self, profile: ShopCalibrationProfile) -> ShopCalibrationProfile:
        self._profiles[profile.profile_id] = profile
        return profile

    def get(self, profile_id: str) -> ShopCalibrationProfile | None:
        return self._profiles.get(profile_id)

    def update(self, profile_id: str, updates: dict) -> ShopCalibrationProfile | None:
        existing = self._profiles.get(profile_id)
        if existing is None:
            return None
        data = existing.model_dump()
        data.update(updates)
        data["updated_at"] = datetime.now(UTC)
        data["revision"] = existing.revision + 1
        updated = ShopCalibrationProfile(**data)
        self._profiles[profile_id] = updated
        return updated

    def list(
        self,
        site_id: str | None = None,
        machine_id: str | None = None,
        operation_family: str | None = None,
    ) -> list[ShopCalibrationProfile]:
        result = list(self._profiles.values())
        if site_id:
            result = [p for p in result if p.site_id == site_id]
        if machine_id:
            result = [p for p in result if p.machine_id == machine_id]
        if operation_family:
            result = [p for p in result if p.operation_family == operation_family]
        return result

    def delete(self, profile_id: str) -> bool:
        return self._profiles.pop(profile_id, None) is not None


PROFILE_STORE = ShopProfileStore()
