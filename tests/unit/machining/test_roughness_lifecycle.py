"""Unit tests for roughness lifecycle aggregation foundation (PHYSICS-01F).

Tests deterministic aggregation without empirical fitting.
"""

from decimal import Decimal

import pytest

from backend.machining.roughness_lifecycle import (
    LifecycleRoughnessObservation,
    Quantity,
    RawSpatialReading,
    RoughnessLifecycleError,
    StageObservation,
    StageValidity,
    Unit,
    aggregate_spatial_readings_to_stage_rq,
    aggregate_stages_to_lifecycle_rq,
)


class TestRawSpatialReading:
    """Test RawSpatialReading validation and construction."""

    def test_valid_reading_rq_only(self):
        """Valid reading with Rq only."""
        rq = Quantity(value=Decimal("1.2"), unit=Unit.MM)
        reading = RawSpatialReading(
            location="beginning",
            Rq_value=rq,
            provenance="Mitutoyo SJ-210",
        )
        assert reading.location == "beginning"
        assert reading.Rq_value.value == Decimal("1.2")
        assert reading.Ra_value is None

    def test_valid_reading_rq_and_ra(self):
        """Valid reading with both Rq and Ra."""
        rq = Quantity(value=Decimal("1.2"), unit=Unit.MM)
        ra = Quantity(value=Decimal("0.8"), unit=Unit.MM)
        reading = RawSpatialReading(
            location="middle",
            Rq_value=rq,
            Ra_value=ra,
            provenance="Mitutoyo SJ-210",
        )
        assert reading.Rq_value.value == Decimal("1.2")
        assert reading.Ra_value.value == Decimal("0.8")

    def test_invalid_zero_rq(self):
        """Zero Rq must fail."""
        rq = Quantity(value=Decimal("0"), unit=Unit.MM)
        with pytest.raises(RoughnessLifecycleError):
            RawSpatialReading(location="beginning", Rq_value=rq)

    def test_invalid_negative_rq(self):
        """Negative Rq must fail."""
        rq = Quantity(value=Decimal("-1.0"), unit=Unit.MM)
        with pytest.raises(RoughnessLifecycleError):
            RawSpatialReading(location="beginning", Rq_value=rq)


class TestAggregateSpatialReadingsToStageRq:
    """Test spatial-to-stage aggregation."""

    def test_simple_three_readings_mean_rq(self):
        """Aggregate three readings: [1.0, 1.2, 1.4] → mean 1.2."""
        readings = [
            RawSpatialReading(location="beginning", Rq_value=Quantity(Decimal("1.0"), Unit.MM)),
            RawSpatialReading(location="middle", Rq_value=Quantity(Decimal("1.2"), Unit.MM)),
            RawSpatialReading(location="end", Rq_value=Quantity(Decimal("1.4"), Unit.MM)),
        ]
        stage_rq, stage_ra = aggregate_spatial_readings_to_stage_rq(readings)

        assert stage_rq.value == Decimal("1.2")
        assert stage_rq.unit == Unit.MM
        assert stage_ra is None

    def test_three_readings_with_ra(self):
        """Aggregate three readings with Ra: compute both means."""
        readings = [
            RawSpatialReading(
                location="beginning",
                Rq_value=Quantity(Decimal("1.0"), Unit.MM),
                Ra_value=Quantity(Decimal("0.6"), Unit.MM),
            ),
            RawSpatialReading(
                location="middle",
                Rq_value=Quantity(Decimal("1.2"), Unit.MM),
                Ra_value=Quantity(Decimal("0.8"), Unit.MM),
            ),
            RawSpatialReading(
                location="end",
                Rq_value=Quantity(Decimal("1.4"), Unit.MM),
                Ra_value=Quantity(Decimal("1.0"), Unit.MM),
            ),
        ]
        stage_rq, stage_ra = aggregate_spatial_readings_to_stage_rq(readings)

        assert stage_rq.value == Decimal("1.2")
        assert stage_ra.value == Decimal("0.8")

    def test_mixed_presence_of_ra_skips_ra_aggregation(self):
        """If some readings lack Ra, skip Ra aggregation."""
        readings = [
            RawSpatialReading(
                location="beginning",
                Rq_value=Quantity(Decimal("1.0"), Unit.MM),
                Ra_value=Quantity(Decimal("0.6"), Unit.MM),
            ),
            RawSpatialReading(
                location="middle",
                Rq_value=Quantity(Decimal("1.2"), Unit.MM),
                Ra_value=None,  # Missing Ra
            ),
        ]
        stage_rq, stage_ra = aggregate_spatial_readings_to_stage_rq(readings)

        assert stage_rq.value == Decimal("1.1")
        assert stage_ra is None  # Skipped because not all readings have Ra

    def test_um_to_mm_normalization(self):
        """Normalize µm readings to mm."""
        readings = [
            RawSpatialReading(
                location="beginning",
                Rq_value=Quantity(Decimal("1000") / Decimal(1000), Unit.MM),  # 1000 µm = 1 mm
            ),
            RawSpatialReading(
                location="end",
                Rq_value=Quantity(Decimal("1200") / Decimal(1000), Unit.MM),  # 1200 µm = 1.2 mm
            ),
        ]
        stage_rq, _ = aggregate_spatial_readings_to_stage_rq(readings)

        assert stage_rq.value == Decimal("1.1")  # (1.0 + 1.2) / 2
        assert stage_rq.unit == Unit.MM

    def test_empty_readings_fails(self):
        """Empty readings list must fail."""
        with pytest.raises(RoughnessLifecycleError):
            aggregate_spatial_readings_to_stage_rq([])


class TestStageObservation:
    """Test StageObservation validation and construction."""

    def test_valid_stage_observation(self):
        """Valid stage observation with complete fields."""
        readings = [
            RawSpatialReading(location="beginning", Rq_value=Quantity(Decimal("1.0"), Unit.MM)),
            RawSpatialReading(location="middle", Rq_value=Quantity(Decimal("1.2"), Unit.MM)),
            RawSpatialReading(location="end", Rq_value=Quantity(Decimal("1.4"), Unit.MM)),
        ]
        stage = StageObservation(
            stage_id="stage_0",
            tool_condition="new",
            wear_value=Quantity(Decimal("0"), Unit.MM),
            cutting_time=Quantity(Decimal("0"), Unit.MIN),
            cumulative_mrv=Quantity(Decimal("0"), Unit.MM3),
            pass_count=0,
            Vc=Quantity(Decimal("125"), Unit.M_MIN),
            fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
            ap=Quantity(Decimal("0.70"), Unit.MM),
            ae=Quantity(Decimal("50"), Unit.MM),
            coating_system="TiAlN",
            raw_readings=readings,
            stage_rq=Quantity(Decimal("1.2"), Unit.MM),
        )
        assert stage.stage_id == "stage_0"
        assert stage.validity == StageValidity.VALID
        assert stage.stage_rq.value == Decimal("1.2")

    def test_stage_with_wear_progression(self):
        """Stage with accumulated wear."""
        readings = [
            RawSpatialReading(location="beginning", Rq_value=Quantity(Decimal("1.3"), Unit.MM)),
            RawSpatialReading(location="middle", Rq_value=Quantity(Decimal("1.5"), Unit.MM)),
            RawSpatialReading(location="end", Rq_value=Quantity(Decimal("1.7"), Unit.MM)),
        ]
        stage = StageObservation(
            stage_id="stage_1",
            tool_condition="mid_life_VB_0.15",
            wear_value=Quantity(Decimal("0.15"), Unit.MM),
            cutting_time=Quantity(Decimal("15.5"), Unit.MIN),
            cumulative_mrv=Quantity(Decimal("387.5"), Unit.MM3),
            pass_count=1,
            Vc=Quantity(Decimal("125"), Unit.M_MIN),
            fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
            ap=Quantity(Decimal("0.70"), Unit.MM),
            ae=Quantity(Decimal("50"), Unit.MM),
            coating_system="TiAlN",
            raw_readings=readings,
            stage_rq=Quantity(Decimal("1.5"), Unit.MM),
        )
        assert stage.wear_value.value == Decimal("0.15")
        assert stage.cutting_time.value == Decimal("15.5")

    def test_empty_readings_fails(self):
        """Empty raw_readings must fail."""
        with pytest.raises(RoughnessLifecycleError):
            StageObservation(
                stage_id="stage_0",
                tool_condition="new",
                wear_value=Quantity(Decimal("0"), Unit.MM),
                cutting_time=Quantity(Decimal("0"), Unit.MIN),
                cumulative_mrv=Quantity(Decimal("0"), Unit.MM3),
                pass_count=0,
                Vc=Quantity(Decimal("125"), Unit.M_MIN),
                fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
                ap=Quantity(Decimal("0.70"), Unit.MM),
                ae=Quantity(Decimal("50"), Unit.MM),
                coating_system="TiAlN",
                raw_readings=[],  # Empty
                stage_rq=Quantity(Decimal("1.2"), Unit.MM),
            )


class TestAggregateStagestoLifecycleRq:
    """Test stage-to-lifecycle aggregation."""

    def test_three_stages_mean_lifecycle_rq(self):
        """Aggregate three stages: [1.2, 1.5, 1.8] → mean 1.5."""
        readings_0 = [
            RawSpatialReading(location="beginning", Rq_value=Quantity(Decimal("1.2"), Unit.MM))
        ]
        readings_1 = [
            RawSpatialReading(location="beginning", Rq_value=Quantity(Decimal("1.5"), Unit.MM))
        ]
        readings_2 = [
            RawSpatialReading(location="beginning", Rq_value=Quantity(Decimal("1.8"), Unit.MM))
        ]

        stages = [
            StageObservation(
                stage_id="stage_0",
                tool_condition="new",
                wear_value=Quantity(Decimal("0"), Unit.MM),
                cutting_time=Quantity(Decimal("0"), Unit.MIN),
                cumulative_mrv=Quantity(Decimal("0"), Unit.MM3),
                pass_count=0,
                Vc=Quantity(Decimal("125"), Unit.M_MIN),
                fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
                ap=Quantity(Decimal("0.70"), Unit.MM),
                ae=Quantity(Decimal("50"), Unit.MM),
                coating_system="TiAlN",
                raw_readings=readings_0,
                stage_rq=Quantity(Decimal("1.2"), Unit.MM),
            ),
            StageObservation(
                stage_id="stage_1",
                tool_condition="mid_life",
                wear_value=Quantity(Decimal("0.15"), Unit.MM),
                cutting_time=Quantity(Decimal("15.5"), Unit.MIN),
                cumulative_mrv=Quantity(Decimal("387.5"), Unit.MM3),
                pass_count=1,
                Vc=Quantity(Decimal("125"), Unit.M_MIN),
                fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
                ap=Quantity(Decimal("0.70"), Unit.MM),
                ae=Quantity(Decimal("50"), Unit.MM),
                coating_system="TiAlN",
                raw_readings=readings_1,
                stage_rq=Quantity(Decimal("1.5"), Unit.MM),
            ),
            StageObservation(
                stage_id="stage_2",
                tool_condition="eol_VB_0.30",
                wear_value=Quantity(Decimal("0.30"), Unit.MM),
                cutting_time=Quantity(Decimal("31.0"), Unit.MIN),
                cumulative_mrv=Quantity(Decimal("775"), Unit.MM3),
                pass_count=2,
                Vc=Quantity(Decimal("125"), Unit.M_MIN),
                fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
                ap=Quantity(Decimal("0.70"), Unit.MM),
                ae=Quantity(Decimal("50"), Unit.MM),
                coating_system="TiAlN",
                raw_readings=readings_2,
                stage_rq=Quantity(Decimal("1.8"), Unit.MM),
            ),
        ]

        lifecycle_rq, lifecycle_ra, n_valid = aggregate_stages_to_lifecycle_rq(stages)

        assert lifecycle_rq.value == Decimal("1.5")
        assert lifecycle_rq.unit == Unit.MM
        assert n_valid == 3
        assert lifecycle_ra is None

    def test_exclude_invalid_stages(self):
        """Exclude invalid stages from aggregation."""
        readings = [
            RawSpatialReading(location="beginning", Rq_value=Quantity(Decimal("1.0"), Unit.MM))
        ]

        stages = [
            StageObservation(
                stage_id="stage_0",
                tool_condition="new",
                wear_value=Quantity(Decimal("0"), Unit.MM),
                cutting_time=Quantity(Decimal("0"), Unit.MIN),
                cumulative_mrv=Quantity(Decimal("0"), Unit.MM3),
                pass_count=0,
                Vc=Quantity(Decimal("125"), Unit.M_MIN),
                fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
                ap=Quantity(Decimal("0.70"), Unit.MM),
                ae=Quantity(Decimal("50"), Unit.MM),
                coating_system="TiAlN",
                raw_readings=readings,
                stage_rq=Quantity(Decimal("1.0"), Unit.MM),
                validity=StageValidity.VALID,
            ),
            StageObservation(
                stage_id="stage_1",
                tool_condition="invalid",
                wear_value=Quantity(Decimal("0.15"), Unit.MM),
                cutting_time=Quantity(Decimal("15.5"), Unit.MIN),
                cumulative_mrv=Quantity(Decimal("387.5"), Unit.MM3),
                pass_count=1,
                Vc=Quantity(Decimal("125"), Unit.M_MIN),
                fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
                ap=Quantity(Decimal("0.70"), Unit.MM),
                ae=Quantity(Decimal("50"), Unit.MM),
                coating_system="TiAlN",
                raw_readings=readings,
                stage_rq=Quantity(Decimal("9.9"), Unit.MM),  # Anomalous
                validity=StageValidity.INVALID_REASON_PROVIDED,
                invalid_reason="Sensor malfunction during measurement",
            ),
            StageObservation(
                stage_id="stage_2",
                tool_condition="eol",
                wear_value=Quantity(Decimal("0.30"), Unit.MM),
                cutting_time=Quantity(Decimal("31.0"), Unit.MIN),
                cumulative_mrv=Quantity(Decimal("775"), Unit.MM3),
                pass_count=2,
                Vc=Quantity(Decimal("125"), Unit.M_MIN),
                fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
                ap=Quantity(Decimal("0.70"), Unit.MM),
                ae=Quantity(Decimal("50"), Unit.MM),
                coating_system="TiAlN",
                raw_readings=readings,
                stage_rq=Quantity(Decimal("2.0"), Unit.MM),
                validity=StageValidity.VALID,
            ),
        ]

        lifecycle_rq, _, n_valid = aggregate_stages_to_lifecycle_rq(stages, exclude_invalid=True)

        # Should only aggregate stage_0 (1.0) and stage_2 (2.0) → mean 1.5
        assert lifecycle_rq.value == Decimal("1.5")
        assert n_valid == 2

    def test_empty_stages_fails(self):
        """Empty stages list must fail."""
        with pytest.raises(RoughnessLifecycleError):
            aggregate_stages_to_lifecycle_rq([])

    def test_all_stages_invalid_fails(self):
        """If all stages are invalid, aggregation must fail."""
        readings = [
            RawSpatialReading(location="beginning", Rq_value=Quantity(Decimal("1.0"), Unit.MM))
        ]

        stages = [
            StageObservation(
                stage_id="stage_0",
                tool_condition="invalid",
                wear_value=Quantity(Decimal("0"), Unit.MM),
                cutting_time=Quantity(Decimal("0"), Unit.MIN),
                cumulative_mrv=Quantity(Decimal("0"), Unit.MM3),
                pass_count=0,
                Vc=Quantity(Decimal("125"), Unit.M_MIN),
                fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
                ap=Quantity(Decimal("0.70"), Unit.MM),
                ae=Quantity(Decimal("50"), Unit.MM),
                coating_system="TiAlN",
                raw_readings=readings,
                stage_rq=Quantity(Decimal("1.0"), Unit.MM),
                validity=StageValidity.INVALID_REASON_PROVIDED,
                invalid_reason="Bad data",
            ),
        ]

        with pytest.raises(RoughnessLifecycleError):
            aggregate_stages_to_lifecycle_rq(stages, exclude_invalid=True)


class TestLifecycleRoughnessObservation:
    """Test LifecycleRoughnessObservation validation."""

    def test_valid_lifecycle_observation(self):
        """Valid complete lifecycle observation."""
        readings = [
            RawSpatialReading(location="beginning", Rq_value=Quantity(Decimal("1.2"), Unit.MM))
        ]
        stage = StageObservation(
            stage_id="stage_0",
            tool_condition="new",
            wear_value=Quantity(Decimal("0"), Unit.MM),
            cutting_time=Quantity(Decimal("0"), Unit.MIN),
            cumulative_mrv=Quantity(Decimal("0"), Unit.MM3),
            pass_count=0,
            Vc=Quantity(Decimal("125"), Unit.M_MIN),
            fz=Quantity(Decimal("0.10"), Unit.MM_TOOTH),
            ap=Quantity(Decimal("0.70"), Unit.MM),
            ae=Quantity(Decimal("50"), Unit.MM),
            coating_system="TiAlN",
            raw_readings=readings,
            stage_rq=Quantity(Decimal("1.2"), Unit.MM),
        )

        obs = LifecycleRoughnessObservation(
            replicate_id="rep_01",
            tool_condition_initial="new",
            coating_system="TiAlN",
            cutting_combination="Vc_125_fz_0.10_ap_0.70",
            stages=[stage],
            lifecycle_rq=Quantity(Decimal("1.2"), Unit.MM),
            eol_criterion="VB_max=0.30mm",
            eol_cutting_time=Quantity(Decimal("31.0"), Unit.MIN),
            total_mrv=Quantity(Decimal("775"), Unit.MM3),
            n_stages=1,
            provenance="VP100 Golden Dataset",
        )

        assert obs.replicate_id == "rep_01"
        assert obs.n_stages == 1
        assert obs.lifecycle_rq.value == Decimal("1.2")

    def test_empty_stages_fails(self):
        """Empty stages list must fail."""
        with pytest.raises(RoughnessLifecycleError):
            LifecycleRoughnessObservation(
                replicate_id="rep_01",
                tool_condition_initial="new",
                coating_system="TiAlN",
                cutting_combination="test",
                stages=[],  # Empty
                lifecycle_rq=Quantity(Decimal("1.2"), Unit.MM),
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
