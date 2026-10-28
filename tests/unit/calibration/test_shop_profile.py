"""Tests for shop calibration profile — EPIC_04F.

CUSTOMER_CALIBRATION_DATA_COMMITTED=NO (runtime store only)
"""

import pytest

from backend.calibration.models import CalibrationSource
from backend.calibration.shop_profile import ShopCalibrationProfile, ShopProfileStore


@pytest.fixture
def store():
    return ShopProfileStore()


@pytest.fixture
def sample_profile():
    return ShopCalibrationProfile(
        label="Test profile",
        machine_id="VF2SS",
        atc_time_sec=3.5,
        setup_time_sec=1800.0,
    )


class TestShopProfileStore:
    def test_create_and_get(self, store, sample_profile):
        created = store.create(sample_profile)
        fetched = store.get(created.profile_id)
        assert fetched is not None
        assert fetched.label == "Test profile"

    def test_get_nonexistent_returns_none(self, store):
        assert store.get("nonexistent-id") is None

    def test_list_empty_store(self, store):
        assert store.list() == []

    def test_list_returns_created(self, store, sample_profile):
        store.create(sample_profile)
        profiles = store.list()
        assert len(profiles) == 1

    def test_list_filter_by_machine_id(self, store):
        p1 = ShopCalibrationProfile(label="A", machine_id="VF2SS")
        p2 = ShopCalibrationProfile(label="B", machine_id="INTEGREX")
        store.create(p1); store.create(p2)
        result = store.list(machine_id="VF2SS")
        assert len(result) == 1
        assert result[0].label == "A"

    def test_list_filter_by_site_id(self, store):
        p1 = ShopCalibrationProfile(label="A", site_id="SITE1")
        p2 = ShopCalibrationProfile(label="B", site_id="SITE2")
        store.create(p1); store.create(p2)
        result = store.list(site_id="SITE1")
        assert len(result) == 1

    def test_update_increments_revision(self, store, sample_profile):
        created = store.create(sample_profile)
        updated = store.update(created.profile_id, {"label": "Updated"})
        assert updated is not None
        assert updated.revision == 2
        assert updated.label == "Updated"

    def test_update_nonexistent_returns_none(self, store):
        result = store.update("bad-id", {"label": "x"})
        assert result is None

    def test_delete_removes_profile(self, store, sample_profile):
        created = store.create(sample_profile)
        assert store.delete(created.profile_id) is True
        assert store.get(created.profile_id) is None

    def test_delete_nonexistent_returns_false(self, store):
        assert store.delete("bad-id") is False

    def test_source_default_shop_validated(self, store, sample_profile):
        created = store.create(sample_profile)
        assert created.source == CalibrationSource.SHOP_VALIDATED

    def test_profile_id_auto_generated(self):
        p = ShopCalibrationProfile(label="auto")
        assert len(p.profile_id) == 36  # uuid4 format
