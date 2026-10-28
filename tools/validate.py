#!/usr/bin/env python3
"""Validate canonical OBDentic knowledge deterministically and fail closed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

if __package__:
    from .applicability import applicability_key, predicate_fields_are_unique
else:
    from applicability import applicability_key, predicate_fields_are_unique

SCHEMA_PATHS = {
    1: Path("schema/knowledge-v1.schema.json"),
    2: Path("schema/knowledge-v2.schema.json"),
    3: Path("schema/knowledge-v3.schema.json"),
}
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


def _validators(root: Path) -> dict[int, Draft202012Validator]:
    validators: dict[int, Draft202012Validator] = {}
    for version, relative_path in SCHEMA_PATHS.items():
        schema = _load_json(root / relative_path)
        validators[version] = Draft202012Validator(
            schema, format_checker=FormatChecker()
        )
    return validators


def _ecu_target_errors(path: Path, document: dict[str, Any]) -> list[str]:
    """Repository-level invariants for schema v3 ecu_targets documents."""
    errors: list[str] = []
    seen: dict[str, set[str]] = {"id": set(), "request": set(), "response": set()}
    for target in document["ecu_targets"]:
        addressing = target["addressing"]
        request_id, response_id = addressing["request_id"], addressing["response_id"]
        for kind, value in (
            ("id", target["id"]),
            ("request", request_id),
            ("response", response_id),
        ):
            if value in seen[kind]:
                errors.append(f"{path}: duplicate target {kind} {value!r}")
            seen[kind].add(value)
        expected = 8 if addressing["response_id_rule"] == "iso15765_plus_8" else 0x6A
        if int(response_id, 16) - int(request_id, 16) != expected:
            errors.append(
                f"{path}: target {target['id']!r} response id {response_id} does not "
                f"follow rule {addressing['response_id_rule']}"
            )
        for source in target["provenance"]["sources"]:
            count, total = source.get("profile_count"), source.get("profile_total")
            plain = source.get("plain_read_profile_count")
            if count is not None and total is not None and count > total:
                errors.append(f"{path}: target {target['id']!r} profile_count > profile_total")
            if plain is not None and count is not None and plain > count:
                errors.append(
                    f"{path}: target {target['id']!r} plain_read_profile_count > profile_count"
                )
    overlap = seen["request"] & seen["response"]
    if overlap:
        errors.append(f"{path}: request/response id overlap {sorted(overlap)}")
    return errors


def validate_repository(root: Path) -> list[str]:
    validators = _validators(root)

    files = _knowledge_files(root)
    if not files:
        raise ValidationError("no canonical knowledge YAML files found")

    errors: list[str] = []
    definition_ids: dict[str, Path] = {}
    semantic_definitions: dict[
        str, list[tuple[Path, int, dict[str, Any]]]
    ] = {}
    sets: dict[str, tuple[Path, dict[str, Any]]] = {}
    target_roles: set[str] = set()
    referenced_roles: list[tuple[Path, str, str]] = []

    for path in files:
        document = _load_yaml(path)
        schema_version = document.get("schema_version")
        if type(schema_version) is not int or schema_version not in validators:
            errors.append(
                f"{path}: unsupported schema_version {schema_version!r}; "
                f"supported versions are {sorted(validators)}"
            )
            continue

        schema_errors = sorted(
            validators[schema_version].iter_errors(document),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
        errors.extend(_format_jsonschema_error(path, error) for error in schema_errors)
        if schema_errors:
            continue

        if schema_version == 3:
            errors.extend(_ecu_target_errors(path, document))
            target_roles.update(t["logical_role"]["value"] for t in document["ecu_targets"])
            continue

        for definition in document["definitions"]:
            role = definition["operation"].get("ecu_role")
            if role is not None:
                referenced_roles.append((path, definition["id"], role))
            definition_id = definition["id"]
            semantic_id = definition["semantic"]
            if definition_id in definition_ids:
                errors.append(
                    f"{path}: duplicate definition id {definition_id!r}; "
                    f"first seen in {definition_ids[definition_id]}"
                )
            else:
                definition_ids[definition_id] = path

            if not predicate_fields_are_unique(definition):
                errors.append(
                    f"{path}: definition {definition_id!r} repeats an applicability "
                    "predicate field"
                )

            semantic_definitions.setdefault(semantic_id, []).append(
                (path, schema_version, definition)
            )

        for definition_set in document.get("sets", []):
            set_id = definition_set["id"]
            if set_id in sets:
                errors.append(
                    f"{path}: duplicate set id {set_id!r}; "
                    f"first seen in {sets[set_id][0]}"
                )
            else:
                sets[set_id] = (path, definition_set)

    if target_roles:
        for path, definition_id, role in referenced_roles:
            if role not in target_roles:
                errors.append(
                    f"{path}: definition {definition_id!r} references ecu_role "
                    f"{role!r} that no ecu_targets entry declares"
                )

    for semantic_id, candidates in sorted(semantic_definitions.items()):
        if len(candidates) < 2:
            continue

        keys: dict[tuple[Any, ...], tuple[Path, str]] = {}
        generic: tuple[Path, str] | None = None
        for path, schema_version, definition in sorted(
            candidates, key=lambda item: item[2]["id"]
        ):
            key = applicability_key(schema_version, definition)
            definition_id = definition["id"]
            if key[0] == "generic":
                if generic is not None:
                    errors.append(
                        f"{path}: semantic {semantic_id!r} has multiple generic "
                        f"definitions {generic[1]!r} and {definition_id!r}"
                    )
                else:
                    generic = (path, definition_id)
            if key in keys:
                first_path, first_id = keys[key]
                errors.append(
                    f"{path}: semantic {semantic_id!r} has identical applicability "
                    f"for definitions {first_id!r} and {definition_id!r}; "
                    f"first seen in {first_path}"
                )
            else:
                keys[key] = (path, definition_id)

    for set_id, (path, definition_set) in sorted(sets.items()):
        for member in definition_set["members"]:
            if member not in semantic_definitions:
                errors.append(
                    f"{path}: set {set_id!r} references unknown semantic {member!r}"
                )

    if ECU_IDENTIFICATION_SET in sets:
        path, definition_set = sets[ECU_IDENTIFICATION_SET]
        for member in definition_set["members"]:
            for _, _, definition in semantic_definitions.get(member, []):
                operation = definition["operation"]
                if operation["type"] != "uds.read_data_by_identifier":
                    errors.append(
                        f"{path}: {ECU_IDENTIFICATION_SET} member {member!r} "
                        "is not a UDS ReadDataByIdentifier operation"
                    )
                if (
                    operation.get("identifier", "").upper() == VIN_DID
                    or member == VIN_SEMANTIC
                ):
                    errors.append(
                        f"{path}: {ECU_IDENTIFICATION_SET} must not include VIN/F190; "
                        "vehicle identity is separate"
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
