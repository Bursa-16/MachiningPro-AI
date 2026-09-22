"""Strict low-level IGES parser tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.interoperability.iges_parser import (
    IgesLimits,
    IgesParseError,
    parse_iges_bytes,
)
from tests.unit.interoperability.iges_fixtures import EntitySpec, hollerith, make_iges


@pytest.mark.parametrize(
    ("newline", "final_newline"),
    [(b"\n", True), (b"\r\n", True), (b"\n", False)],
)
def test_accepts_exact_fixed_records_with_supported_line_endings(
    newline: bytes,
    final_newline: bool,
) -> None:
    model = parse_iges_bytes(
        make_iges(newline=newline, final_newline=final_newline)
    )

    assert model.section_counts == {"S": 1, "G": 3, "D": 2, "P": 1, "T": 1}


def test_accepts_standard_space_padded_section_sequences() -> None:
    data = make_iges().replace(b"S0000001", b"S      1", 1)

    model = parse_iges_bytes(data)

    assert model.section_counts["S"] == 1


def test_parses_global_units_scale_tolerance_and_version() -> None:
    model = parse_iges_bytes(
        make_iges(
            model_scale="2.5",
            unit_flag=1,
            unit_name="IN",
            minimum_resolution="2.5D-5",
            maximum_coordinate="9.75D3",
        )
    )

    global_section = model.global_section
    assert global_section.parameter_delimiter == ","
    assert global_section.record_delimiter == ";"
    assert global_section.model_scale == Decimal("2.5")
    assert global_section.unit_flag == 1
    assert global_section.unit_name == "IN"
    assert global_section.millimetres_per_model_unit == Decimal("25.4")
    assert global_section.minimum_resolution == Decimal("2.5E-5")
    assert global_section.maximum_coordinate == Decimal("9.75E3")
    assert global_section.version == 11
    assert global_section.file_name == "fixture.igs"
    assert global_section.native_system_id == "MachiningPro"
    assert global_section.preprocessor_version == "IGES parser tests"
    assert global_section.creation_timestamp == "20260921.120000"
    assert global_section.author == "OpenAI"
    assert global_section.organization == "MachiningPro"
    assert global_section.drafting_standard == 0
    assert global_section.modified_timestamp == "20260921.120000"


def test_converts_microinches_to_exact_millimetres() -> None:
    model = parse_iges_bytes(make_iges(unit_flag=11, unit_name="UIN"))

    assert model.global_section.millimetres_per_model_unit == Decimal("0.0000254")


def test_hollerith_payload_may_contain_parameter_and_record_delimiters() -> None:
    model = parse_iges_bytes(
        make_iges(
            sender_product_id="comma,value",
            receiver_product_id="semi;colon-ok",
        )
    )

    assert model.global_section.sender_product_id == "comma,value"
    assert model.global_section.receiver_product_id == "semi;colon-ok"


def test_parses_custom_parameter_and_record_delimiters() -> None:
    model = parse_iges_bytes(
        make_iges(
            (EntitySpec(110, "110|1|2|3|4|5|6!"),),
            parameter_delimiter="|",
            record_delimiter="!",
        )
    )

    assert model.global_section.parameter_delimiter == "|"
    assert model.global_section.record_delimiter == "!"
    assert model.entities[0].parameters == (
        110,
        Decimal("1"),
        Decimal("2"),
        Decimal("3"),
        Decimal("4"),
        Decimal("5"),
        Decimal("6"),
    )


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda data: data.replace(b"S0000001", b"S0000002", 1), "sequence"),
        (lambda data: data.replace(b"D0000001", b"P0000001", 1), "section order"),
        (lambda data: data.replace(b"S      1", b"S      2", 1), "Terminate"),
        (lambda data: data[:-2] + b"\xff\n", "ASCII"),
    ],
)
def test_rejects_malformed_physical_or_section_structure(mutator, message: str) -> None:
    with pytest.raises(IgesParseError, match=message):
        parse_iges_bytes(mutator(make_iges()))


@pytest.mark.parametrize("delta", [-1, 1])
def test_rejects_non_80_column_record(delta: int) -> None:
    records = make_iges().splitlines()
    records[0] = records[0][:-1] if delta < 0 else records[0] + b"X"

    with pytest.raises(IgesParseError, match="80 bytes"):
        parse_iges_bytes(b"\n".join(records) + b"\n")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"model_scale": "0"}, "model scale"),
        ({"model_scale": "1E999999"}, "exponent"),
        ({"unit_flag": 3, "unit_name": "MM"}, "unit flag"),
        ({"unit_flag": 1, "unit_name": "MM"}, "unit"),
    ],
)
def test_rejects_invalid_global_numeric_or_unit_data(kwargs, message: str) -> None:
    with pytest.raises(IgesParseError, match=message):
        parse_iges_bytes(make_iges(**kwargs))


def test_enforces_file_and_record_limits_at_boundary_plus_one() -> None:
    data = make_iges()
    record_count = len(data.splitlines())

    assert parse_iges_bytes(
        data,
        limits=IgesLimits(max_file_bytes=len(data), max_records=record_count),
    )
    with pytest.raises(IgesParseError, match="file byte limit"):
        parse_iges_bytes(
            data,
            limits=IgesLimits(max_file_bytes=len(data) - 1),
        )
    with pytest.raises(IgesParseError, match="record limit"):
        parse_iges_bytes(
            data,
            limits=IgesLimits(max_records=record_count - 1),
        )


def test_enforces_entity_parameter_byte_and_parameter_count_limits() -> None:
    data = make_iges()

    assert parse_iges_bytes(
        data,
        limits=IgesLimits(
            max_entities=1,
            max_parameter_bytes_per_entity=64,
            max_parameters_per_entity=7,
        ),
    )
    with pytest.raises(IgesParseError, match="entity limit"):
        parse_iges_bytes(data, limits=IgesLimits(max_entities=0))
    with pytest.raises(IgesParseError, match="parameter byte limit"):
        parse_iges_bytes(
            data,
            limits=IgesLimits(max_parameter_bytes_per_entity=63),
        )
    with pytest.raises(IgesParseError, match="parameter count limit"):
        parse_iges_bytes(
            data,
            limits=IgesLimits(max_parameters_per_entity=6),
        )


def test_parses_directory_pair_and_multiline_parameter_data() -> None:
    note = "parameter continuation crosses the sixty-four byte record boundary"
    model = parse_iges_bytes(
        make_iges(
            (
                EntitySpec(
                    212,
                    f"212,{hollerith(note)};",
                    form_number=7,
                    status_number="01010000",
                    label="POINT-A",
                ),
            )
        )
    )

    entity = model.entities_by_pointer[1]
    assert entity.directory.de_pointer == 1
    assert entity.directory.parameter_data_pointer == 1
    assert entity.directory.parameter_line_count == 2
    assert entity.directory.form_number == 7
    assert entity.directory.status_number == "01010000"
    assert entity.parameters == (212, note)


def test_rejects_directory_type_mismatch() -> None:
    data = make_iges().replace(b"     110       0", b"     100       0", 1)

    with pytest.raises(IgesParseError, match="different entity types"):
        parse_iges_bytes(data)


def test_rejects_parameter_entity_type_mismatch() -> None:
    with pytest.raises(IgesParseError, match="does not match Directory"):
        parse_iges_bytes(make_iges((EntitySpec(110, "100,0,0,0,1,2,3;"),)))


@pytest.mark.parametrize(
    "parameter",
    ["110,RAW_PRIVATE_PAYLOAD_ABC,0,0,1,2,3;", f"110,{('9' * 1000)},0,0,1,2,3;"],
)
def test_malformed_parameter_tokens_are_bounded_and_do_not_echo_source(
    parameter: str,
) -> None:
    with pytest.raises(IgesParseError) as exc_info:
        parse_iges_bytes(make_iges((EntitySpec(110, parameter),)))

    message = str(exc_info.value)
    assert "RAW_PRIVATE_PAYLOAD_ABC" not in message
    assert "99999999999999999999" not in message


def test_rejects_dangling_directory_transform_reference() -> None:
    with pytest.raises(IgesParseError, match="dangling.*transform.*3"):
        parse_iges_bytes(
            make_iges(
                (EntitySpec(110, "110,0,0,0,1,2,3;", transform_pointer=3),)
            )
        )


def test_rejects_dangling_directory_structure_reference() -> None:
    with pytest.raises(IgesParseError, match="dangling.*999.*structure"):
        parse_iges_bytes(
            make_iges(
                (
                    EntitySpec(
                        110,
                        "110,0,0,0,1,2,3;",
                        structure_pointer=999,
                    ),
                )
            )
        )


def test_rejects_wrong_analytic_surface_reference_type() -> None:
    with pytest.raises(IgesParseError, match="location.*incompatible.*110"):
        parse_iges_bytes(
            make_iges(
                (
                    EntitySpec(110, "110,0,0,0,1,2,3;"),
                    EntitySpec(123, "123,0,0,1;"),
                    EntitySpec(192, "192,1,3,2.5;"),
                )
            )
        )


def test_rejects_cyclic_directory_transform_references() -> None:
    transform = "124,1,0,0,0,1,0,0,0,1,0,0;"
    with pytest.raises(IgesParseError, match="cyclic.*reference"):
        parse_iges_bytes(
            make_iges(
                (
                    EntitySpec(124, transform, transform_pointer=3),
                    EntitySpec(124, transform, transform_pointer=1),
                )
            )
        )


def test_rejects_dangling_schema_specific_boundary_reference() -> None:
    with pytest.raises(IgesParseError, match="DE 1.*142.*99"):
        parse_iges_bytes(make_iges((EntitySpec(142, "142,0,99,0,0,1;"),)))


def test_plain_integer_curve_parameters_are_not_treated_as_references() -> None:
    model = parse_iges_bytes(
        make_iges((EntitySpec(110, "110,101,103,105,107,109,111;"),))
    )

    assert model.entities[0].parameters[1:] == (101, 103, 105, 107, 109, 111)


def test_enforces_control_point_and_reference_depth_limits() -> None:
    bspline = (
        "126,2,1,0,0,1,0,0,0,1,2,3,3,1,1,1,"
        "0,0,0,1,0,0,2,0,0,0,1,0,0,1;"
    )
    with pytest.raises(IgesParseError, match="control point limit"):
        parse_iges_bytes(
            make_iges((EntitySpec(126, bspline),)),
            limits=IgesLimits(max_control_points=2),
        )

    transform = "124,1,0,0,0,1,0,0,0,1,0,0;"
    with pytest.raises(IgesParseError, match="reference depth limit"):
        parse_iges_bytes(
            make_iges(
                (
                    EntitySpec(124, transform, transform_pointer=3),
                    EntitySpec(124, transform, transform_pointer=5),
                    EntitySpec(124, transform),
                )
            ),
            limits=IgesLimits(max_reference_depth=1),
        )


def test_reference_depth_limit_is_independent_of_directory_order() -> None:
    transform = "124,1,0,0,0,1,0,0,0,1,0,0;"

    with pytest.raises(IgesParseError, match="reference depth limit"):
        parse_iges_bytes(
            make_iges(
                (
                    EntitySpec(124, transform),
                    EntitySpec(124, transform, transform_pointer=1),
                    EntitySpec(124, transform, transform_pointer=3),
                )
            ),
            limits=IgesLimits(max_reference_depth=1),
        )
