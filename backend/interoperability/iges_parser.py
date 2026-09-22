"""Strict, resource-bounded parser for fixed-record ASCII IGES files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import TypeAlias

__all__ = [
    "IgesDirectoryEntry",
    "IgesEntity",
    "IgesGlobalSection",
    "IgesLimits",
    "IgesModel",
    "IgesParameter",
    "IgesParseError",
    "parse_iges_bytes",
]

IgesParameter: TypeAlias = Decimal | int | str | None

_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_DECIMAL_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?$"
)
_TERMINATE_RE = re.compile(
    r"^S\s*(\d+)G\s*(\d+)D\s*(\d+)P\s*(\d+)\s*$"
)
_SECTION_ORDER = {"S": 0, "G": 1, "D": 2, "P": 3, "T": 4}
_MAX_INTEGER_TOKEN_CHARS = 64
_MAX_DECIMAL_TOKEN_CHARS = 256
_MM_PER_UNIT_FLAG = {
    1: Decimal("25.4"),
    2: Decimal("1"),
    4: Decimal("304.8"),
    5: Decimal("1609344"),
    6: Decimal("1000"),
    7: Decimal("1000000"),
    8: Decimal("0.0254"),
    9: Decimal("0.001"),
    10: Decimal("10"),
    11: Decimal("0.0000254"),
}
_UNIT_NAMES = {
    1: {"IN", "INCH"},
    2: {"MM"},
    4: {"FT", "FOOT"},
    5: {"MI", "MILE"},
    6: {"M"},
    7: {"KM"},
    8: {"MIL"},
    9: {"UM", "MICRON"},
    10: {"CM"},
    11: {"UIN", "MICROINCH"},
}


class IgesParseError(ValueError):
    """Raised when source bytes violate the supported IGES grammar."""

    def __init__(
        self,
        message: str,
        *,
        section: str | None = None,
        sequence: int | None = None,
    ) -> None:
        context = ""
        if section is not None:
            context += f" section={section}"
        if sequence is not None:
            context += f" sequence={sequence}"
        super().__init__(f"{message}{context}")
        self.section = section
        self.sequence = sequence


@dataclass(frozen=True, slots=True)
class IgesLimits:
    max_file_bytes: int = 64 * 1024 * 1024
    max_records: int = 800_000
    max_entities: int = 100_000
    max_parameter_bytes_per_entity: int = 4 * 1024 * 1024
    max_global_parameters: int = 256
    max_parameters_per_entity: int = 1_000_000
    max_control_points: int = 250_000
    max_reference_depth: int = 128


_DEFAULT_LIMITS = IgesLimits()


@dataclass(frozen=True, slots=True)
class IgesGlobalSection:
    parameter_delimiter: str
    record_delimiter: str
    sender_product_id: str
    receiver_product_id: str
    file_name: str | None
    native_system_id: str | None
    preprocessor_version: str | None
    creation_timestamp: str | None
    author: str | None
    organization: str | None
    drafting_standard: int | None
    modified_timestamp: str | None
    model_scale: Decimal
    unit_flag: int
    unit_name: str
    millimetres_per_model_unit: Decimal
    minimum_resolution: Decimal | None
    maximum_coordinate: Decimal | None
    version: int | None


@dataclass(frozen=True, slots=True)
class IgesDirectoryEntry:
    de_pointer: int
    entity_type: int
    parameter_data_pointer: int
    structure_pointer: int
    line_font_pattern: int
    level: int
    view_pointer: int
    transformation_matrix_pointer: int
    label_display_associativity: int
    status_number: str
    line_weight: int
    color_number: int
    parameter_line_count: int
    form_number: int
    entity_label: str
    entity_subscript: int


@dataclass(frozen=True, slots=True)
class IgesEntity:
    directory: IgesDirectoryEntry
    parameters: tuple[IgesParameter, ...]


@dataclass(frozen=True, slots=True)
class IgesModel:
    global_section: IgesGlobalSection
    entities: tuple[IgesEntity, ...]
    entities_by_pointer: MappingProxyType
    section_counts: MappingProxyType


@dataclass(frozen=True, slots=True)
class _PhysicalRecord:
    payload: str
    section: str
    sequence: int


def _split_physical_records(data: bytes, limits: IgesLimits) -> tuple[_PhysicalRecord, ...]:
    if len(data) > limits.max_file_bytes:
        raise IgesParseError("IGES file byte limit exceeded")
    if b"\x00" in data:
        raise IgesParseError("IGES input contains NUL bytes")
    try:
        data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise IgesParseError("IGES input must be ASCII") from exc
    if b"\r" in data.replace(b"\r\n", b""):
        raise IgesParseError("IGES input contains an invalid line terminator")

    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    if not lines:
        raise IgesParseError("IGES input is empty")
    if len(lines) > limits.max_records:
        raise IgesParseError("IGES physical record limit exceeded")

    records: list[_PhysicalRecord] = []
    for physical_number, raw in enumerate(lines, start=1):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        if len(raw) != 80:
            raise IgesParseError(
                f"IGES physical record must be exactly 80 bytes, got {len(raw)}",
                sequence=physical_number,
            )
        section = chr(raw[72])
        sequence_text = raw[73:80].decode("ascii")
        if section not in _SECTION_ORDER:
            raise IgesParseError(
                f"invalid IGES section code {section!r}", sequence=physical_number
            )
        stripped_sequence = sequence_text.strip()
        if not stripped_sequence.isdigit():
            raise IgesParseError(
                "IGES section sequence must contain seven digits",
                section=section,
                sequence=physical_number,
            )
        records.append(
            _PhysicalRecord(
                payload=raw[:72].decode("ascii"),
                section=section,
                sequence=int(stripped_sequence),
            )
        )
    return tuple(records)


def _validate_sections(
    records: tuple[_PhysicalRecord, ...],
) -> dict[str, tuple[_PhysicalRecord, ...]]:
    grouped: dict[str, list[_PhysicalRecord]] = {key: [] for key in _SECTION_ORDER}
    previous_rank = -1
    for record in records:
        rank = _SECTION_ORDER[record.section]
        if rank < previous_rank:
            raise IgesParseError(
                "invalid IGES section order",
                section=record.section,
                sequence=record.sequence,
            )
        previous_rank = rank
        expected_sequence = len(grouped[record.section]) + 1
        if record.sequence != expected_sequence:
            raise IgesParseError(
                f"invalid section sequence: expected {expected_sequence}",
                section=record.section,
                sequence=record.sequence,
            )
        grouped[record.section].append(record)

    missing = [name for name, values in grouped.items() if not values]
    if missing:
        raise IgesParseError(f"missing required IGES section(s): {', '.join(missing)}")
    if len(grouped["T"]) != 1:
        raise IgesParseError("IGES must contain exactly one Terminate record")

    match = _TERMINATE_RE.fullmatch(grouped["T"][0].payload.rstrip())
    if match is None:
        raise IgesParseError("malformed IGES Terminate section", section="T", sequence=1)
    declared = dict(zip(("S", "G", "D", "P"), map(int, match.groups()), strict=True))
    observed = {name: len(grouped[name]) for name in ("S", "G", "D", "P")}
    if declared != observed:
        raise IgesParseError(
            "Terminate section counts do not match records: "
            f"declared={declared}, observed={observed}",
            section="T",
            sequence=1,
        )
    return {name: tuple(values) for name, values in grouped.items()}


def _hollerith_at(value: str, start: int) -> tuple[str, int] | None:
    index = start
    while index < len(value) and value[index].isdigit():
        index += 1
    if index == start or index >= len(value) or value[index] not in "Hh":
        return None
    if index - start > _MAX_INTEGER_TOKEN_CHARS:
        raise IgesParseError("Hollerith length is outside supported bounds")
    try:
        length = int(value[start:index])
    except ValueError as exc:
        raise IgesParseError("Hollerith length is outside supported bounds") from exc
    content_start = index + 1
    content_end = content_start + length
    if content_end > len(value):
        raise IgesParseError("Hollerith length exceeds available parameter data")
    return value[content_start:content_end], content_end


def _tokenize_parameter_stream(
    stream: str,
    parameter_delimiter: str,
    record_delimiter: str,
    max_parameters: int,
) -> tuple[str, ...]:
    tokens: list[str] = []
    token_parts: list[str] = []
    index = 0
    terminated = False
    while index < len(stream):
        char = stream[index]
        if char == parameter_delimiter or char == record_delimiter:
            tokens.append("".join(token_parts).strip())
            token_parts.clear()
            index += 1
            if char == record_delimiter:
                terminated = True
                break
            continue
        if not token_parts and char.isdigit():
            hollerith = _hollerith_at(stream, index)
            if hollerith is not None:
                content, index = hollerith
                token_parts.append(f"{len(content)}H{content}")
                continue
        token_parts.append(char)
        index += 1
    if not terminated:
        raise IgesParseError("parameter stream is missing its record delimiter")
    if stream[index:].strip():
        raise IgesParseError("unexpected data after IGES record delimiter")
    if len(tokens) > max_parameters:
        raise IgesParseError("IGES parameter count limit exceeded")
    return tuple(tokens)


def _parse_decimal(token: str, field_name: str) -> Decimal:
    text = token.strip()
    if len(text) > _MAX_DECIMAL_TOKEN_CHARS:
        raise IgesParseError(f"{field_name} numeric value is outside supported bounds")
    if not _DECIMAL_RE.fullmatch(text):
        raise IgesParseError(f"invalid {field_name} numeric value")
    exponent_match = re.search(r"[EeDd]([+-]?\d+)$", text)
    if exponent_match is not None:
        exponent_text = exponent_match.group(1)
        if len(exponent_text.lstrip("+-")) > 5:
            raise IgesParseError(f"{field_name} exponent is outside supported bounds")
        if abs(int(exponent_text)) > 10_000:
            raise IgesParseError(f"{field_name} exponent is outside supported bounds")
    try:
        value = Decimal(text.replace("d", "E").replace("D", "E"))
    except InvalidOperation as exc:
        raise IgesParseError(f"invalid {field_name} numeric value") from exc
    if not value.is_finite():
        raise IgesParseError(f"{field_name} must be finite")
    return value


def _parse_hollerith(token: str, field_name: str) -> str:
    parsed = _hollerith_at(token, 0)
    if parsed is None or parsed[1] != len(token):
        raise IgesParseError(f"{field_name} must be a Hollerith string")
    return parsed[0]


def _parse_int(token: str, field_name: str) -> int:
    text = token.strip()
    if len(text.lstrip("+-")) > _MAX_INTEGER_TOKEN_CHARS:
        raise IgesParseError(f"{field_name} integer is outside supported bounds")
    if not _INTEGER_RE.fullmatch(text):
        raise IgesParseError(f"{field_name} must be an integer")
    try:
        return int(text)
    except ValueError as exc:
        raise IgesParseError(
            f"{field_name} integer is outside supported bounds"
        ) from exc


def _parse_global(
    records: tuple[_PhysicalRecord, ...], limits: IgesLimits
) -> IgesGlobalSection:
    stream = "".join(record.payload for record in records)
    first = _hollerith_at(stream, 0)
    if first is None or len(first[0]) != 1:
        raise IgesParseError("Global parameter delimiter declaration is invalid", section="G")
    parameter_delimiter = first[0]
    if first[1] >= len(stream) or stream[first[1]] != parameter_delimiter:
        raise IgesParseError("Global parameter delimiter is not self-delimited", section="G")
    second_start = first[1] + 1
    second = _hollerith_at(stream, second_start)
    if second is None or len(second[0]) != 1:
        raise IgesParseError("Global record delimiter declaration is invalid", section="G")
    record_delimiter = second[0]
    tokens = _tokenize_parameter_stream(
        stream,
        parameter_delimiter,
        record_delimiter,
        limits.max_global_parameters,
    )
    if len(tokens) < 23:
        raise IgesParseError("Global section has fewer than 23 required parameters")

    model_scale = _parse_decimal(tokens[12], "model scale")
    if model_scale <= 0:
        raise IgesParseError("model scale must be positive")
    unit_flag = _parse_int(tokens[13], "unit flag")
    if unit_flag not in _MM_PER_UNIT_FLAG:
        raise IgesParseError(f"unsupported unit flag {unit_flag}")
    unit_name = _parse_hollerith(tokens[14], "unit name").strip().upper()
    if unit_name not in _UNIT_NAMES[unit_flag]:
        raise IgesParseError(f"unit name conflicts with unit flag {unit_flag}")
    minimum_resolution = (
        _parse_decimal(tokens[18], "minimum resolution") if tokens[18] else None
    )
    if minimum_resolution is not None and minimum_resolution <= 0:
        raise IgesParseError("minimum resolution must be positive")
    maximum_coordinate = (
        _parse_decimal(tokens[19], "maximum coordinate") if tokens[19] else None
    )
    if maximum_coordinate is not None and maximum_coordinate <= 0:
        raise IgesParseError("maximum coordinate must be positive")
    version = _parse_int(tokens[22], "IGES version") if tokens[22] else None

    def optional_hollerith(index: int, field_name: str) -> str | None:
        if index >= len(tokens) or not tokens[index]:
            return None
        return _parse_hollerith(tokens[index], field_name)

    return IgesGlobalSection(
        parameter_delimiter=parameter_delimiter,
        record_delimiter=record_delimiter,
        sender_product_id=_parse_hollerith(tokens[2], "sender product id"),
        receiver_product_id=_parse_hollerith(tokens[11], "receiver product id"),
        file_name=optional_hollerith(3, "file name"),
        native_system_id=optional_hollerith(4, "native system id"),
        preprocessor_version=optional_hollerith(5, "preprocessor version"),
        creation_timestamp=optional_hollerith(17, "creation timestamp"),
        author=optional_hollerith(20, "author"),
        organization=optional_hollerith(21, "organization"),
        drafting_standard=(
            _parse_int(tokens[23], "drafting standard")
            if len(tokens) > 23 and tokens[23]
            else None
        ),
        modified_timestamp=optional_hollerith(24, "modified timestamp"),
        model_scale=model_scale,
        unit_flag=unit_flag,
        unit_name=unit_name,
        millimetres_per_model_unit=_MM_PER_UNIT_FLAG[unit_flag],
        minimum_resolution=minimum_resolution,
        maximum_coordinate=maximum_coordinate,
        version=version,
    )


def _directory_int(field: str, field_name: str, *, allow_blank: bool = True) -> int:
    text = field.strip()
    if not text and allow_blank:
        return 0
    if not _INTEGER_RE.fullmatch(text):
        raise IgesParseError(f"Directory {field_name} must be an integer")
    return int(text)


def _parse_directory_entries(
    records: tuple[_PhysicalRecord, ...], limits: IgesLimits
) -> tuple[IgesDirectoryEntry, ...]:
    if len(records) % 2:
        raise IgesParseError("Directory section must contain record pairs", section="D")
    if len(records) // 2 > limits.max_entities:
        raise IgesParseError("IGES entity limit exceeded", section="D")
    entries: list[IgesDirectoryEntry] = []
    for index in range(0, len(records), 2):
        first = records[index]
        second = records[index + 1]
        first_fields = [first.payload[offset : offset + 8] for offset in range(0, 72, 8)]
        second_fields = [second.payload[offset : offset + 8] for offset in range(0, 72, 8)]
        first_type = _directory_int(first_fields[0], "entity type", allow_blank=False)
        second_type = _directory_int(second_fields[0], "entity type", allow_blank=False)
        if first_type != second_type:
            raise IgesParseError(
                "Directory record pair repeats different entity types",
                section="D",
                sequence=first.sequence,
            )
        status_number = first_fields[8].strip() or "00000000"
        if len(status_number) != 8 or not status_number.isdigit():
            raise IgesParseError(
                "Directory status number must contain eight digits",
                section="D",
                sequence=first.sequence,
            )
        entries.append(
            IgesDirectoryEntry(
                de_pointer=first.sequence,
                entity_type=first_type,
                parameter_data_pointer=_directory_int(
                    first_fields[1], "parameter data pointer", allow_blank=False
                ),
                structure_pointer=_directory_int(first_fields[2], "structure pointer"),
                line_font_pattern=_directory_int(first_fields[3], "line font pattern"),
                level=_directory_int(first_fields[4], "level"),
                view_pointer=_directory_int(first_fields[5], "view pointer"),
                transformation_matrix_pointer=_directory_int(
                    first_fields[6], "transformation matrix pointer"
                ),
                label_display_associativity=_directory_int(
                    first_fields[7], "label display associativity"
                ),
                status_number=status_number,
                line_weight=_directory_int(second_fields[1], "line weight"),
                color_number=_directory_int(second_fields[2], "color number"),
                parameter_line_count=_directory_int(
                    second_fields[3], "parameter line count", allow_blank=False
                ),
                form_number=_directory_int(second_fields[4], "form number"),
                entity_label=second_fields[7].strip(),
                entity_subscript=_directory_int(second_fields[8], "entity subscript"),
            )
        )
    return tuple(entries)


def _parse_parameter_token(token: str) -> IgesParameter:
    if not token:
        return None
    hollerith = _hollerith_at(token, 0)
    if hollerith is not None and hollerith[1] == len(token):
        return hollerith[0]
    if _INTEGER_RE.fullmatch(token):
        return _parse_int(token, "IGES integer parameter")
    if _DECIMAL_RE.fullmatch(token):
        return _parse_decimal(token, "entity parameter")
    raise IgesParseError("unsupported IGES parameter token")


def _parse_parameter_data(
    records: tuple[_PhysicalRecord, ...],
    directories: tuple[IgesDirectoryEntry, ...],
    global_section: IgesGlobalSection,
    limits: IgesLimits,
) -> tuple[IgesEntity, ...]:
    by_de_pointer: dict[int, list[_PhysicalRecord]] = {}
    for record in records:
        pointer_text = record.payload[64:72].strip()
        if not pointer_text.isdigit():
            raise IgesParseError(
                "Parameter record Directory pointer must be a positive integer",
                section="P",
                sequence=record.sequence,
            )
        by_de_pointer.setdefault(int(pointer_text), []).append(record)

    entities: list[IgesEntity] = []
    directory_pointers = {entry.de_pointer for entry in directories}
    if set(by_de_pointer) - directory_pointers:
        unknown = min(set(by_de_pointer) - directory_pointers)
        raise IgesParseError(f"Parameter record references unknown DE pointer {unknown}")
    for entry in directories:
        entity_records = by_de_pointer.get(entry.de_pointer, [])
        if len(entity_records) != entry.parameter_line_count:
            raise IgesParseError(
                f"Parameter line count mismatch for DE {entry.de_pointer}: "
                f"expected {entry.parameter_line_count}, got {len(entity_records)}"
            )
        if not entity_records or entity_records[0].sequence != entry.parameter_data_pointer:
            raise IgesParseError(
                f"Parameter data pointer mismatch for DE {entry.de_pointer}"
            )
        raw_stream = "".join(record.payload[:64] for record in entity_records)
        if len(raw_stream.encode("ascii")) > limits.max_parameter_bytes_per_entity:
            raise IgesParseError("IGES per-entity parameter byte limit exceeded")
        tokens = _tokenize_parameter_stream(
            raw_stream,
            global_section.parameter_delimiter,
            global_section.record_delimiter,
            limits.max_parameters_per_entity,
        )
        parameters = tuple(_parse_parameter_token(token) for token in tokens)
        if not parameters or parameters[0] != entry.entity_type:
            raise IgesParseError(
                f"Parameter entity type does not match Directory type for DE {entry.de_pointer}"
            )
        entities.append(IgesEntity(directory=entry, parameters=parameters))
    return tuple(entities)


_CURVE_TYPES = {100, 110, 126}
_SURFACE_TYPES = {108, 128, 143, 144, 190, 192, 194, 196, 198}


def _required_int_parameter(
    entity: IgesEntity, index: int, field_name: str
) -> int:
    if index >= len(entity.parameters):
        raise IgesParseError(
            f"DE {entity.directory.de_pointer} entity type "
            f"{entity.directory.entity_type} lacks {field_name}"
        )
    value = entity.parameters[index]
    if isinstance(value, bool) or not isinstance(value, int):
        raise IgesParseError(
            f"DE {entity.directory.de_pointer} entity type "
            f"{entity.directory.entity_type} {field_name} must be an integer"
        )
    return value


def _reference(
    references: list[tuple[str, int, frozenset[int] | None]],
    kind: str,
    pointer: int,
    allowed_types: set[int] | None = None,
) -> None:
    if pointer:
        references.append(
            (kind, pointer, frozenset(allowed_types) if allowed_types is not None else None)
        )


def _schema_references(
    entity: IgesEntity,
) -> tuple[tuple[str, int, frozenset[int] | None], ...]:
    entity_type = entity.directory.entity_type
    references: list[tuple[str, int, frozenset[int] | None]] = []
    directory = entity.directory
    transform_pointer = entity.directory.transformation_matrix_pointer
    _reference(references, "transform", transform_pointer, {124})
    _reference(references, "structure", abs(directory.structure_pointer))
    _reference(references, "view", abs(directory.view_pointer))
    _reference(
        references,
        "label display",
        abs(directory.label_display_associativity),
    )
    if directory.line_font_pattern < 0:
        _reference(references, "line font", abs(directory.line_font_pattern), {304})
    if directory.level < 0:
        _reference(references, "level", abs(directory.level), {406})
    if directory.color_number < 0:
        _reference(references, "color", abs(directory.color_number), {314})

    if entity_type == 116 and len(entity.parameters) > 4:
        _reference(
            references,
            "display symbol",
            _required_int_parameter(entity, 4, "display symbol pointer"),
            {308},
        )
    elif entity_type == 108 and len(entity.parameters) > 5:
        _reference(
            references,
            "plane boundary",
            _required_int_parameter(entity, 5, "boundary pointer"),
            _CURVE_TYPES,
        )
    elif entity_type == 141:
        _reference(
            references,
            "surface",
            _required_int_parameter(entity, 3, "surface pointer"),
            _SURFACE_TYPES,
        )
        curve_count = _required_int_parameter(entity, 4, "curve count")
        if curve_count < 1:
            raise IgesParseError(
                f"DE {entity.directory.de_pointer} type 141 curve count must be positive"
            )
        cursor = 5
        for _ in range(curve_count):
            _reference(
                references,
                "model-space curve",
                _required_int_parameter(entity, cursor, "model-space curve pointer"),
                _CURVE_TYPES,
            )
            parameter_curve_count = _required_int_parameter(
                entity, cursor + 2, "parameter curve count"
            )
            if parameter_curve_count < 0:
                raise IgesParseError(
                    f"DE {entity.directory.de_pointer} type 141 parameter curve "
                    "count must not be negative"
                )
            for offset in range(parameter_curve_count):
                _reference(
                    references,
                    "parameter-space curve",
                    _required_int_parameter(
                        entity, cursor + 3 + offset, "parameter curve pointer"
                    ),
                    _CURVE_TYPES,
                )
            cursor += 3 + parameter_curve_count
    elif entity_type == 142:
        _reference(
            references,
            "surface",
            _required_int_parameter(entity, 2, "surface pointer"),
            _SURFACE_TYPES,
        )
        _reference(
            references,
            "parameter-space curve",
            _required_int_parameter(entity, 3, "parameter-space curve pointer"),
            _CURVE_TYPES,
        )
        _reference(
            references,
            "model-space curve",
            _required_int_parameter(entity, 4, "model-space curve pointer"),
            _CURVE_TYPES,
        )
    elif entity_type == 143:
        _reference(
            references,
            "bounded surface",
            _required_int_parameter(entity, 2, "surface pointer"),
            _SURFACE_TYPES,
        )
        boundary_count = _required_int_parameter(entity, 3, "boundary count")
        if boundary_count < 1:
            raise IgesParseError(
                f"DE {entity.directory.de_pointer} type 143 boundary count must be positive"
            )
        for offset in range(boundary_count):
            _reference(
                references,
                "boundary",
                _required_int_parameter(entity, 4 + offset, "boundary pointer"),
                {141},
            )
    elif entity_type == 144:
        _reference(
            references,
            "trimmed surface",
            _required_int_parameter(entity, 1, "surface pointer"),
            _SURFACE_TYPES,
        )
        outer_flag = _required_int_parameter(entity, 2, "outer boundary flag")
        inner_count = _required_int_parameter(entity, 3, "inner boundary count")
        outer_pointer = _required_int_parameter(
            entity, 4, "outer boundary pointer"
        )
        if outer_flag:
            _reference(
                references,
                "outer boundary",
                outer_pointer,
                {142},
            )
        elif outer_pointer != 0:
            raise IgesParseError(
                f"DE {entity.directory.de_pointer} type 144 natural outer boundary "
                "pointer must be zero"
            )
        for offset in range(inner_count):
            _reference(
                references,
                "inner boundary",
                _required_int_parameter(
                    entity, 5 + offset, "inner boundary pointer"
                ),
                {142},
            )
    elif entity_type == 504:
        edge_count = _required_int_parameter(entity, 1, "edge count")
        cursor = 2
        for _ in range(edge_count):
            _reference(
                references,
                "edge curve",
                _required_int_parameter(entity, cursor, "curve pointer"),
                _CURVE_TYPES,
            )
            _reference(
                references,
                "start vertex list",
                _required_int_parameter(entity, cursor + 1, "start vertex list pointer"),
                {502},
            )
            _reference(
                references,
                "end vertex list",
                _required_int_parameter(entity, cursor + 3, "end vertex list pointer"),
                {502},
            )
            cursor += 5
    elif entity_type == 508:
        member_count = _required_int_parameter(entity, 1, "loop member count")
        cursor = 2
        for _ in range(member_count):
            member_type = _required_int_parameter(entity, cursor, "loop member type")
            allowed = {504} if member_type == 0 else {502} if member_type == 1 else set()
            if not allowed:
                raise IgesParseError(
                    f"DE {entity.directory.de_pointer} type 508 has invalid member type "
                    f"{member_type}"
                )
            _reference(
                references,
                "loop member list",
                _required_int_parameter(entity, cursor + 1, "loop member list pointer"),
                allowed,
            )
            parameter_curve_count = _required_int_parameter(
                entity, cursor + 4, "parameter curve count"
            )
            for parameter_index in range(parameter_curve_count):
                pointer_index = cursor + 6 + parameter_index * 2
                _reference(
                    references,
                    "loop parameter curve",
                    _required_int_parameter(
                        entity, pointer_index, "parameter curve pointer"
                    ),
                    _CURVE_TYPES | {142},
                )
            cursor += 5 + parameter_curve_count * 2
    elif entity_type == 510:
        _reference(
            references,
            "face surface",
            _required_int_parameter(entity, 1, "surface pointer"),
            _SURFACE_TYPES,
        )
        loop_count = _required_int_parameter(entity, 2, "loop count")
        for offset in range(loop_count):
            _reference(
                references,
                "face loop",
                _required_int_parameter(entity, 4 + offset, "loop pointer"),
                {508},
            )
    elif entity_type == 514:
        face_count = _required_int_parameter(entity, 1, "face count")
        for offset in range(face_count):
            _reference(
                references,
                "shell face",
                _required_int_parameter(entity, 2 + offset * 2, "face pointer"),
                {510},
            )
    elif entity_type == 186:
        _reference(
            references,
            "outer shell",
            _required_int_parameter(entity, 1, "outer shell pointer"),
            {514},
        )
        void_count = _required_int_parameter(entity, 3, "void shell count")
        for offset in range(void_count):
            _reference(
                references,
                "void shell",
                _required_int_parameter(entity, 4 + offset * 2, "void shell pointer"),
                {514},
            )
    elif entity_type in {190, 192, 194, 196, 198}:
        _reference(
            references,
            "location",
            _required_int_parameter(entity, 1, "location pointer"),
            {116},
        )
        if entity_type != 196:
            _reference(
                references,
                "axis",
                _required_int_parameter(entity, 2, "axis pointer"),
                {123},
            )
        if entity.directory.form_number == 1:
            reference_indices = {
                190: (2, 3),
                192: (None, 4),
                194: (None, 5),
                196: (3, 4),
                198: (None, 5),
            }
            axis_index, reference_index = reference_indices[entity_type]
            if axis_index is not None:
                _reference(
                    references,
                    "axis",
                    _required_int_parameter(entity, axis_index, "axis pointer"),
                    {123},
                )
            _reference(
                references,
                "reference direction",
                _required_int_parameter(
                    entity, reference_index, "reference direction pointer"
                ),
                {123},
            )
    return tuple(references)


def _validate_entity_resource_counts(
    entities: tuple[IgesEntity, ...], limits: IgesLimits
) -> None:
    for entity in entities:
        entity_type = entity.directory.entity_type
        if entity_type == 126:
            upper_index = _required_int_parameter(entity, 1, "upper index")
            control_point_count = upper_index + 1
        elif entity_type == 128:
            first_upper = _required_int_parameter(entity, 1, "first upper index")
            second_upper = _required_int_parameter(entity, 2, "second upper index")
            control_point_count = (first_upper + 1) * (second_upper + 1)
        else:
            continue
        if control_point_count < 1:
            raise IgesParseError(
                f"DE {entity.directory.de_pointer} has invalid control point count"
            )
        if control_point_count > limits.max_control_points:
            raise IgesParseError(
                f"DE {entity.directory.de_pointer} control point limit exceeded"
            )


def _validate_reference_graph(
    entities_by_pointer: MappingProxyType, limits: IgesLimits
) -> None:
    graph: dict[int, tuple[int, ...]] = {}
    for pointer, entity in entities_by_pointer.items():
        targets: list[int] = []
        for kind, target_pointer, allowed_types in _schema_references(entity):
            if target_pointer <= 0 or target_pointer % 2 == 0:
                raise IgesParseError(
                    f"DE {pointer} entity type {entity.directory.entity_type} has invalid "
                    f"{kind} reference {target_pointer}"
                )
            target = entities_by_pointer.get(target_pointer)
            if target is None:
                qualifier = "transform " if kind == "transform" else ""
                raise IgesParseError(
                    f"DE {pointer} entity type {entity.directory.entity_type} has dangling "
                    f"{qualifier}reference {target_pointer} ({kind})"
                )
            if allowed_types is not None and target.directory.entity_type not in allowed_types:
                raise IgesParseError(
                    f"DE {pointer} entity type {entity.directory.entity_type} {kind} "
                    f"reference {target_pointer} has incompatible entity type "
                    f"{target.directory.entity_type}"
                )
            targets.append(target_pointer)
        graph[pointer] = tuple(targets)

    colors: dict[int, int] = {}
    postorder: list[int] = []
    for root in graph:
        if colors.get(root, 0) == 2:
            continue
        stack: list[tuple[int, int]] = [(root, 0)]
        while stack:
            node, child_index = stack[-1]
            if colors.get(node, 0) == 0:
                colors[node] = 1
            children = graph[node]
            if child_index >= len(children):
                colors[node] = 2
                postorder.append(node)
                stack.pop()
                continue
            child = children[child_index]
            stack[-1] = (node, child_index + 1)
            child_color = colors.get(child, 0)
            if child_color == 1:
                raise IgesParseError(
                    f"cyclic IGES entity reference involving DE {child}"
                )
            if child_color == 0:
                stack.append((child, 0))

    longest_path: dict[int, int] = {}
    for node in postorder:
        depth = max(
            (longest_path[child] + 1 for child in graph[node]),
            default=0,
        )
        if depth > limits.max_reference_depth:
            raise IgesParseError("IGES reference depth limit exceeded")
        longest_path[node] = depth


def parse_iges_bytes(
    data: bytes, *, limits: IgesLimits = _DEFAULT_LIMITS
) -> IgesModel:
    """Parse one complete fixed-record ASCII IGES document."""

    records = _split_physical_records(data, limits)
    sections = _validate_sections(records)
    global_section = _parse_global(sections["G"], limits)
    directories = _parse_directory_entries(sections["D"], limits)
    entities = _parse_parameter_data(
        sections["P"], directories, global_section, limits
    )
    _validate_entity_resource_counts(entities, limits)
    entities_by_pointer = MappingProxyType(
        {entity.directory.de_pointer: entity for entity in entities}
    )
    _validate_reference_graph(entities_by_pointer, limits)
    return IgesModel(
        global_section=global_section,
        entities=entities,
        entities_by_pointer=entities_by_pointer,
        section_counts=MappingProxyType(
            {name: len(section_records) for name, section_records in sections.items()}
        ),
    )
