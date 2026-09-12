"""Convert between stored circuit attributes (JSON) and the screen engine's Circuit."""

from dataclasses import fields
from decimal import Decimal
from typing import Any, get_args

from app.domains.interconnection.models import CircuitModel
from app.domains.interconnection.screens.types import Circuit, InterconnectionType, PrimaryLineType, ProtectiveDevice

CIRCUIT_FIELDS = {f.name for f in fields(Circuit)} - {"synthetic_fields"}
_ENUMS = {"primary_line_type": PrimaryLineType, "interconnection_type": InterconnectionType}


def _is_decimal(name: str) -> bool:
    ann = next(f.type for f in fields(Circuit) if f.name == name)
    return Decimal in get_args(ann) or ann is Decimal


def validate_attributes(attributes: dict[str, Any], synthetic_fields: list[str]) -> None:
    unknown = set(attributes) - CIRCUIT_FIELDS
    if unknown:
        raise ValueError(f"unknown circuit attributes: {sorted(unknown)}")
    stray = set(synthetic_fields) - CIRCUIT_FIELDS
    if stray:
        raise ValueError(f"synthetic_fields names unknown attributes: {sorted(stray)}")


def to_circuit(model: CircuitModel) -> Circuit:
    validate_attributes(model.attributes, model.synthetic_fields)
    kwargs: dict[str, Any] = {}
    for name, value in model.attributes.items():
        if value is None:
            kwargs[name] = None
        elif name == "protective_devices":
            kwargs[name] = tuple(ProtectiveDevice(d["name"], Decimal(str(d["interrupting_rating_a"])),
                                                  Decimal(str(d["existing_fault_duty_a"]))) for d in value)
        elif name in _ENUMS:
            kwargs[name] = _ENUMS[name](value)
        elif _is_decimal(name):
            kwargs[name] = Decimal(str(value))
        else:
            kwargs[name] = value
    return Circuit(**kwargs, synthetic_fields=frozenset(model.synthetic_fields))


def to_attributes(circuit: Circuit) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in sorted(CIRCUIT_FIELDS):
        value = getattr(circuit, name)
        if value is None:
            continue
        if name == "protective_devices":
            out[name] = [{"name": d.name, "interrupting_rating_a": str(d.interrupting_rating_a),
                          "existing_fault_duty_a": str(d.existing_fault_duty_a)} for d in value]
        elif isinstance(value, Decimal):
            out[name] = str(value)
        elif hasattr(value, "value"):
            out[name] = value.value
        else:
            out[name] = value
    return out
