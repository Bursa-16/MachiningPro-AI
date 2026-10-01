"""Test-only IGES fixed-record builders.

The helpers serialize caller-provided IGES parameters. They intentionally do
not derive canonical geometry or expected values.
"""

from __future__ import annotations

from dataclasses import dataclass


def record(payload: str, section: str, sequence: int) -> bytes:
    assert len(section) == 1
    assert len(payload) <= 72
    encoded = f"{payload:<72}{section}{sequence:07d}".encode("ascii")
    assert len(encoded) == 80
    return encoded


def join_records(
    *records: bytes,
    newline: bytes = b"\n",
    final_newline: bool = True,
) -> bytes:
    body = newline.join(records)
    return body + newline if final_newline else body


def hollerith(value: str) -> str:
    return f"{len(value)}H{value}"


@dataclass(frozen=True, slots=True)
class EntitySpec:
    entity_type: int
    parameters: str
    form_number: int = 0
    transform_pointer: int = 0
    structure_pointer: int = 0
    status_number: str = "00000000"
    label: str = ""


def _chunks(value: str, width: int) -> list[str]:
    return [value[index : index + width] for index in range(0, len(value), width)]


def _field(value: int | str) -> str:
    return f"{value:>8}"


def make_iges(
    entities: tuple[EntitySpec, ...] = (
        EntitySpec(110, "110,0,0,0,1,2,3;", label="LINE"),
    ),
    *,
    model_scale: str = "1",
    unit_flag: int = 2,
    unit_name: str = "MM",
    minimum_resolution: str = "0.001",
    maximum_coordinate: str = "1000",
    sender_product_id: str = "MachiningPro test",
    receiver_product_id: str = "IGES receiver",
    parameter_delimiter: str = ",",
    record_delimiter: str = ";",
    start_record_count: int = 1,
    newline: bytes = b"\n",
    final_newline: bool = True,
) -> bytes:
    assert len(parameter_delimiter) == 1
    assert len(record_delimiter) == 1
    global_values = (
        hollerith(parameter_delimiter),
        hollerith(record_delimiter),
        hollerith(sender_product_id),
        hollerith("fixture.igs"),
        hollerith("MachiningPro"),
        hollerith("IGES parser tests"),
        "32",
        "38",
        "6",
        "308",
        "15",
        hollerith(receiver_product_id),
        model_scale,
        str(unit_flag),
        hollerith(unit_name),
        "1",
        "1",
        hollerith("20260921.120000"),
        minimum_resolution,
        maximum_coordinate,
        hollerith("OpenAI"),
        hollerith("MachiningPro"),
        "11",
        "0",
        hollerith("20260921.120000"),
    )
    global_stream = parameter_delimiter.join(global_values) + record_delimiter
    g_records = [
        record(chunk, "G", index)
        for index, chunk in enumerate(_chunks(global_stream, 72), start=1)
    ]

    directory_records: list[bytes] = []
    parameter_records: list[bytes] = []
    next_parameter_sequence = 1
    for entity_index, entity in enumerate(entities):
        de_pointer = entity_index * 2 + 1
        parameter_chunks = _chunks(entity.parameters, 64)
        first_fields = (
            entity.entity_type,
            next_parameter_sequence,
            entity.structure_pointer,
            0,
            0,
            0,
            entity.transform_pointer,
            0,
            entity.status_number,
        )
        second_fields = (
            entity.entity_type,
            0,
            0,
            len(parameter_chunks),
            entity.form_number,
            0,
            0,
            entity.label[:8],
            0,
        )
        directory_records.append(
            record("".join(_field(value) for value in first_fields), "D", de_pointer)
        )
        directory_records.append(
            record("".join(_field(value) for value in second_fields), "D", de_pointer + 1)
        )
        for chunk in parameter_chunks:
            payload = f"{chunk:<64}{de_pointer:>8}"
            parameter_records.append(
                record(payload, "P", next_parameter_sequence)
            )
            next_parameter_sequence += 1

    start_records = [
        record(f"IGES parser test fixture {index}", "S", index)
        for index in range(1, start_record_count + 1)
    ]
    terminate = record(
        f"S{len(start_records):>7}G{len(g_records):>7}D{len(directory_records):>7}"
        f"P{len(parameter_records):>7}",
        "T",
        1,
    )
    return join_records(
        *start_records,
        *g_records,
        *directory_records,
        *parameter_records,
        terminate,
        newline=newline,
        final_newline=final_newline,
    )
