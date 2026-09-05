"""Pure reference semantics for canonical Knowledge applicability.

This module has no vehicle I/O and no protocol execution. It exists so the
versioned data contract can be tested independently from the Rust consumer.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

GENERIC = "generic"
ECU_FINGERPRINT = "ecu_fingerprint"

MATCH_GENERIC = "generic"
MATCH_EXACT = "exact_match"
MATCH_PARTIAL = "partial_candidate"
MATCH_NONE = "no_match"

RESOLVED_GENERIC = "resolved_generic"
RESOLVED_SPECIFIC = "resolved_specific"
AMBIGUOUS = "ambiguous"
INSUFFICIENT_IDENTITY = "insufficient_identity"
NO_MATCH = "no_match"


def applicability_key(schema_version: int, definition: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return a deterministic structural key for static duplicate detection."""
    if schema_version == 1:
        return (GENERIC,)

    applicability = definition["applicability"]
    kind = applicability["kind"]
    if kind == GENERIC:
        return (GENERIC,)
    if kind != ECU_FINGERPRINT:
        raise ValueError(f"unsupported applicability kind: {kind!r}")

    predicates = tuple(
        sorted(
            (predicate["field"], predicate["equals"])
            for predicate in applicability["predicates"]
        )
    )
    return (ECU_FINGERPRINT, predicates)


def predicate_fields_are_unique(definition: Mapping[str, Any]) -> bool:
    applicability = definition.get("applicability")
    if not applicability or applicability.get("kind") != ECU_FINGERPRINT:
        return True
    fields = [predicate["field"] for predicate in applicability["predicates"]]
    return len(fields) == len(set(fields))


def evaluate(
    schema_version: int,
    definition: Mapping[str, Any],
    observed_facts: Mapping[str, str],
) -> tuple[str, int]:
    """Evaluate one definition against already-normalized observed facts.

    Exact string comparison is intentional. Normalization belongs upstream in
    observed-inventory construction; applicability never performs fuzzy
    matching, case folding, regex matching, range matching, or plausibility
    scoring.
    """
    if schema_version == 1:
        return MATCH_GENERIC, 0

    applicability = definition["applicability"]
    kind = applicability["kind"]
    if kind == GENERIC:
        return MATCH_GENERIC, 0

    predicates = applicability["predicates"]
    missing = False
    for predicate in predicates:
        field = predicate["field"]
        expected = predicate["equals"]
        if field not in observed_facts:
            missing = True
        elif observed_facts[field] != expected:
            return MATCH_NONE, len(predicates)

    if missing:
        return MATCH_PARTIAL, len(predicates)
    return MATCH_EXACT, len(predicates)


def resolve_semantic(
    definitions: Iterable[tuple[int, Mapping[str, Any]]],
    observed_facts: Mapping[str, str],
) -> dict[str, Any]:
    """Resolve candidates for one semantic deterministically.

    Conservative rule: a partial specific candidate blocks fallback to generic
    knowledge because the missing identity could prove that the specific
    definition supersedes the generic one.
    """
    ordered = sorted(definitions, key=lambda item: item[1]["id"])
    evaluated: list[dict[str, Any]] = []
    for schema_version, definition in ordered:
        match, specificity = evaluate(schema_version, definition, observed_facts)
        evaluated.append(
            {
                "id": definition["id"],
                "match": match,
                "specificity": specificity,
            }
        )

    exact = [item for item in evaluated if item["match"] == MATCH_EXACT]
    if exact:
        maximum = max(item["specificity"] for item in exact)
        finalists = [item for item in exact if item["specificity"] == maximum]
        if len(finalists) == 1:
            return {
                "state": RESOLVED_SPECIFIC,
                "selected": finalists[0]["id"],
                "candidates": evaluated,
            }
        return {"state": AMBIGUOUS, "selected": None, "candidates": evaluated}

    partial = [item for item in evaluated if item["match"] == MATCH_PARTIAL]
    if partial:
        return {
            "state": INSUFFICIENT_IDENTITY,
            "selected": None,
            "candidates": evaluated,
        }

    generic = [item for item in evaluated if item["match"] == MATCH_GENERIC]
    if len(generic) == 1:
        return {
            "state": RESOLVED_GENERIC,
            "selected": generic[0]["id"],
            "candidates": evaluated,
        }
    if len(generic) > 1:
        return {"state": AMBIGUOUS, "selected": None, "candidates": evaluated}

    return {"state": NO_MATCH, "selected": None, "candidates": evaluated}


def resolve_catalog(
    definitions: Iterable[tuple[int, Mapping[str, Any]]],
    observed_facts: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}
    for schema_version, definition in definitions:
        grouped.setdefault(definition["semantic"], []).append(
            (schema_version, definition)
        )
    return {
        semantic: resolve_semantic(grouped[semantic], observed_facts)
        for semantic in sorted(grouped)
    }
