"""In-memory ManufacturingPlanStore — CRUD + approve/review.

AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime

from backend.manufacturing_plan.models import (
    ChangeDriver,
    ManufacturingPlan,
    ManufacturingPlanStatus,
    PlanRevisionEntry,
)


class PlanNotFoundError(KeyError):
    pass


class PlanApprovalError(ValueError):
    pass


class ManufacturingPlanStore:
    """Thread-unsafe in-memory store (single-process dev/demo use)."""

    def __init__(self) -> None:
        self._plans: dict[str, ManufacturingPlan] = {}

    # ------------------------------------------------------------------ CRUD

    def save(self, plan: ManufacturingPlan) -> ManufacturingPlan:
        updated = dataclasses.replace(plan, updated_at=datetime.utcnow())
        self._plans[plan.plan_id] = updated
        return updated

    def get(self, plan_id: str) -> ManufacturingPlan:
        try:
            return self._plans[plan_id]
        except KeyError:
            raise PlanNotFoundError(plan_id)

    def list_all(self) -> list[ManufacturingPlan]:
        return list(self._plans.values())

    def delete(self, plan_id: str) -> None:
        if plan_id not in self._plans:
            raise PlanNotFoundError(plan_id)
        del self._plans[plan_id]

    # ---------------------------------------------------------------- Actions

    def mark_engineer_reviewed(self, plan_id: str, engineer_note: str = "") -> ManufacturingPlan:
        plan = self.get(plan_id)
        if plan.status not in (ManufacturingPlanStatus.DRAFT, ManufacturingPlanStatus.REJECTED):
            raise PlanApprovalError(
                f"Cannot mark ENGINEER_REVIEWED from status {plan.status}"
            )
        entry = PlanRevisionEntry(
            revision_id=str(uuid.uuid4()),
            revision_number=len(plan.revision_history) + 1,
            change_driver=ChangeDriver.ENGINEER_EDIT,
            previous_plan_id=None,
            new_plan_id=plan_id,
            changed_fields=["status"],
            engineer_note=engineer_note,
        )
        updated = dataclasses.replace(
            plan,
            status=ManufacturingPlanStatus.ENGINEER_REVIEWED,
            revision_history=[*plan.revision_history, entry],
            updated_at=datetime.utcnow(),
        )
        self._plans[plan_id] = updated
        return updated

    def approve(self, plan_id: str, engineer_note: str = "") -> ManufacturingPlan:
        """
        AUTO_GENERATED_PLAN_MARKED_APPROVED=NO.
        Only ENGINEER_REVIEWED plans may be approved.
        """
        plan = self.get(plan_id)
        if plan.AUTO_GENERATED_PLAN_MARKED_APPROVED:
            raise PlanApprovalError(
                "AUTO_GENERATED_PLAN_MARKED_APPROVED=True — approval not permitted"
            )
        if plan.status != ManufacturingPlanStatus.ENGINEER_REVIEWED:
            raise PlanApprovalError(
                f"Cannot approve plan in status {plan.status}; "
                "must be ENGINEER_REVIEWED first"
            )
        entry = PlanRevisionEntry(
            revision_id=str(uuid.uuid4()),
            revision_number=len(plan.revision_history) + 1,
            change_driver=ChangeDriver.ENGINEER_EDIT,
            previous_plan_id=None,
            new_plan_id=plan_id,
            changed_fields=["status"],
            engineer_note=engineer_note,
        )
        updated = dataclasses.replace(
            plan,
            status=ManufacturingPlanStatus.APPROVED,
            revision_history=[*plan.revision_history, entry],
            updated_at=datetime.utcnow(),
        )
        self._plans[plan_id] = updated
        return updated

    def reject(self, plan_id: str, engineer_note: str = "") -> ManufacturingPlan:
        plan = self.get(plan_id)
        if plan.status not in (
            ManufacturingPlanStatus.DRAFT,
            ManufacturingPlanStatus.ENGINEER_REVIEWED,
        ):
            raise PlanApprovalError(f"Cannot reject plan in status {plan.status}")
        entry = PlanRevisionEntry(
            revision_id=str(uuid.uuid4()),
            revision_number=len(plan.revision_history) + 1,
            change_driver=ChangeDriver.ENGINEER_EDIT,
            previous_plan_id=None,
            new_plan_id=plan_id,
            changed_fields=["status"],
            engineer_note=engineer_note,
        )
        updated = dataclasses.replace(
            plan,
            status=ManufacturingPlanStatus.REJECTED,
            revision_history=[*plan.revision_history, entry],
            updated_at=datetime.utcnow(),
        )
        self._plans[plan_id] = updated
        return updated

    def supersede(self, old_plan_id: str, new_plan: ManufacturingPlan) -> ManufacturingPlan:
        old = self.get(old_plan_id)
        superseded = dataclasses.replace(
            old,
            status=ManufacturingPlanStatus.SUPERSEDED,
            updated_at=datetime.utcnow(),
        )
        self._plans[old_plan_id] = superseded
        return self.save(new_plan)

    # ----------------------------------------------------------------- Query

    def find_by_drawing(self, drawing_number: str) -> list[ManufacturingPlan]:
        return [p for p in self._plans.values() if p.drawing_number == drawing_number]

    def find_by_source(self, source_id: str) -> list[ManufacturingPlan]:
        return [p for p in self._plans.values() if p.source_id == source_id]


# Module-level singleton
_store = ManufacturingPlanStore()


def get_store() -> ManufacturingPlanStore:
    return _store
