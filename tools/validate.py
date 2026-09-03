#!/usr/bin/env python3
"""Validate canonical OBDentic knowledge deterministically and fail closed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path("schema/knowledge-v1.schema.json")
KNOWLEDGE_ROOTS = (Path("standards"), Path("manufacturers"), Path("semantic"))
ECU_IDENTIFICATION_SET = "uds.standard.ecu_identification"
VIN_SEMANTIC = "vehicle.vin"
VIN_DID = "0xF190"


class ValidationError(RuntimeError):
    pass


def _knowledge_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for relative_root in KNOWLEDGE_ROOTS:
        directory = root / relative_root
        if not directory.exists():
            continue
        files.extend(directory.rglob("*.yaml"))
        files.extend(directory.rglob("*.yml"))
    return sorted(files, key=lambda path: path.as_posix())


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: schema root must be an object")
    return data


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: knowledge document root must be a mapping")
    return data


def _format_jsonschema_error(path: Path, error: Any) -> str:
    location = ".".join(str(part) for part in error.absolute_path)
    prefix = f"{path}:{location}" if location else str(path)
    return f"{prefix}: {error.message}"


def validate_repository(root: Path) -> list[str]:
    schema_path = root / SCHEMA_PATH
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    files = _knowledge_files(root)
    if not files:
        raise ValidationError("no canonical knowledge YAML files found")

    errors: list[str] = []
    definition_ids: dict[str, Path] = {}
    semantic_ids: dict[str, Path] = {}
    sets: dict[str, tuple[Path, dict[str, Any]]] = {}
    definitions: dict[str, tuple[Path, dict[str, Any]]] = {}

    for path in files:
        document = _load_yaml(path)
        schema_errors = sorted(
            validator.iter_errors(document),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
        errors.extend(_format_jsonschema_error(path, error) for error in schema_errors)
        if schema_errors:
            continue

        for definition in document["definitions"]:
            definition_id = definition["id"]
            semantic_id = definition["semantic"]
            if definition_id in definition_ids:
                errors.append(
                    f"{path}: duplicate definition id {definition_id!r}; first seen in {definition_ids[definition_id]}"
                )
            else:
                definition_ids[definition_id] = path
                definitions[definition_id] = (path, definition)

            # V1 intentionally rejects semantic shadowing. Applicability-aware
            # conflict resolution is introduced explicitly by knowledge issue #3.
            if semantic_id in semantic_ids:
                errors.append(
                    f"{path}: duplicate semantic id {semantic_id!r}; first seen in {semantic_ids[semantic_id]}"
                )
            else:
                semantic_ids[semantic_id] = path

        for definition_set in document.get("sets", []):
            set_id = definition_set["id"]
            if set_id in sets:
                errors.append(f"{path}: duplicate set id {set_id!r}; first seen in {sets[set_id][0]}")
            else:
                sets[set_id] = (path, definition_set)

    for set_id, (path, definition_set) in sorted(sets.items()):
        semantic_to_definition = {
            definition["semantic"]: definition
            for _, definition in definitions.values()
        }
        for member in definition_set["members"]:
            if member not in semantic_to_definition:
                errors.append(f"{path}: set {set_id!r} references unknown semantic {member!r}")

    if ECU_IDENTIFICATION_SET in sets:
        path, definition_set = sets[ECU_IDENTIFICATION_SET]
        semantic_to_definition = {
            definition["semantic"]: definition
            for _, definition in definitions.values()
        }
        for member in definition_set["members"]:
            definition = semantic_to_definition.get(member)
            if definition is None:
                continue
            operation = definition["operation"]
            if operation["type"] != "uds.read_data_by_identifier":
                errors.append(
                    f"{path}: {ECU_IDENTIFICATION_SET} member {member!r} is not a UDS ReadDataByIdentifier operation"
                )
            if operation.get("identifier", "").upper() == VIN_DID or member == VIN_SEMANTIC:
                errors.append(
                    f"{path}: {ECU_IDENTIFICATION_SET} must not include VIN/F190; vehicle identity is separate"
                )

    return sorted(errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args()

    try:
        errors = validate_repository(args.root.resolve())
    except (OSError, json.JSONDecodeError, yaml.YAMLError, ValidationError) as exc:
        print(f"ERROR: {exc}")
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    files = _knowledge_files(args.root.resolve())
    print(f"validated {len(files)} knowledge file(s) deterministically")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
