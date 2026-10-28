"""Tests for ManufacturingPlanStore."""
import pytest
from backend.manufacturing_plan.store import ManufacturingPlanStore, PlanNotFoundError, PlanApprovalError
from backend.manufacturing_plan.builder import build_manufacturing_plan
from backend.manufacturing_plan.models import ManufacturingPlanStatus


def _plan(**kwargs):
    return build_manufacturing_plan("src1", None, None, **kwargs)


class TestStoreCRUD:
    def test_save_and_get(self):
        store = ManufacturingPlanStore()
        plan = _plan()
        store.save(plan)
        retrieved = store.get(plan.plan_id)
        assert retrieved.plan_id == plan.plan_id

    def test_get_missing_raises(self):
        store = ManufacturingPlanStore()
        with pytest.raises(PlanNotFoundError):
            store.get("nonexistent")

    def test_list_all(self):
        store = ManufacturingPlanStore()
        p1 = _plan()
        p2 = _plan()
        store.save(p1)
        store.save(p2)
        result = store.list_all()
        assert len(result) == 2

    def test_delete(self):
        store = ManufacturingPlanStore()
        plan = _plan()
        store.save(plan)
        store.delete(plan.plan_id)
        with pytest.raises(PlanNotFoundError):
            store.get(plan.plan_id)

    def test_delete_missing_raises(self):
        store = ManufacturingPlanStore()
        with pytest.raises(PlanNotFoundError):
            store.delete("nonexistent")


class TestStoreActions:
    def test_mark_reviewed(self):
        store = ManufacturingPlanStore()
        plan = _plan()
        store.save(plan)
        updated = store.mark_engineer_reviewed(plan.plan_id, "reviewed ok")
        assert updated.status == ManufacturingPlanStatus.ENGINEER_REVIEWED

    def test_approve_requires_reviewed(self):
        store = ManufacturingPlanStore()
        plan = _plan()
        store.save(plan)
        with pytest.raises(PlanApprovalError):
            store.approve(plan.plan_id)

    def test_approve_after_reviewed(self):
        store = ManufacturingPlanStore()
        plan = _plan()
        store.save(plan)
        store.mark_engineer_reviewed(plan.plan_id)
        approved = store.approve(plan.plan_id)
        assert approved.status == ManufacturingPlanStatus.APPROVED

    def test_auto_approved_flag_blocks_approval(self):
        store = ManufacturingPlanStore()
        import dataclasses
        plan = _plan()
        plan_flagged = dataclasses.replace(
            plan,
            AUTO_GENERATED_PLAN_MARKED_APPROVED=True,
            status=ManufacturingPlanStatus.ENGINEER_REVIEWED,
        )
        store.save(plan_flagged)
        with pytest.raises(PlanApprovalError):
            store.approve(plan_flagged.plan_id)

    def test_reject(self):
        store = ManufacturingPlanStore()
        plan = _plan()
        store.save(plan)
        rejected = store.reject(plan.plan_id)
        assert rejected.status == ManufacturingPlanStatus.REJECTED

    def test_supersede(self):
        store = ManufacturingPlanStore()
        old = _plan()
        store.save(old)
        new = _plan()
        store.supersede(old.plan_id, new)
        old_retrieved = store.get(old.plan_id)
        assert old_retrieved.status == ManufacturingPlanStatus.SUPERSEDED

    def test_revision_history_appended(self):
        store = ManufacturingPlanStore()
        plan = _plan()
        store.save(plan)
        store.mark_engineer_reviewed(plan.plan_id, "ok")
        updated = store.get(plan.plan_id)
        assert len(updated.revision_history) == 1


class TestStoreQuery:
    def test_find_by_drawing(self):
        store = ManufacturingPlanStore()
        p1 = build_manufacturing_plan("src1", None, None, drawing_number="DWG-001")
        p2 = build_manufacturing_plan("src2", None, None, drawing_number="DWG-002")
        store.save(p1)
        store.save(p2)
        result = store.find_by_drawing("DWG-001")
        assert len(result) == 1
        assert result[0].drawing_number == "DWG-001"

    def test_find_by_source(self):
        store = ManufacturingPlanStore()
        p1 = build_manufacturing_plan("src-xyz", None, None)
        p2 = build_manufacturing_plan("src-abc", None, None)
        store.save(p1)
        store.save(p2)
        result = store.find_by_source("src-xyz")
        assert len(result) == 1
