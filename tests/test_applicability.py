from __future__ import annotations

import unittest

from tools.applicability import (
    AMBIGUOUS,
    INSUFFICIENT_IDENTITY,
    NO_MATCH,
    RESOLVED_GENERIC,
    RESOLVED_SPECIFIC,
    resolve_catalog,
    resolve_semantic,
)


def provenance() -> dict:
    return {
        "classification": "EXPERIMENTAL",
        "confidence": "high",
        "sources": [{"kind": "research", "citation": "synthetic test fixture"}],
    }


def definition(
    definition_id: str,
    semantic: str,
    *,
    predicates: list[tuple[str, str]] | None,
) -> dict:
    applicability = (
        {"kind": "generic", "provenance": provenance()}
        if predicates is None
        else {
            "kind": "ecu_fingerprint",
            "predicates": [
                {"field": field, "equals": value} for field, value in predicates
            ],
            "provenance": provenance(),
        }
    )
    return {
        "id": definition_id,
        "semantic": semantic,
        "applicability": applicability,
    }


class ApplicabilityTests(unittest.TestCase):
    def test_exact_specific_match_beats_generic(self) -> None:
        definitions = [
            (2, definition("generic.rpm", "engine.rpm", predicates=None)),
            (
                2,
                definition(
                    "specific.rpm",
                    "engine.rpm",
                    predicates=[
                        ("ecu.manufacturer_software_number", "03L906022"),
                        ("ecu.manufacturer_software_version", "9980"),
                    ],
                ),
            ),
        ]
        result = resolve_semantic(
            definitions,
            {
                "ecu.manufacturer_software_number": "03L906022",
                "ecu.manufacturer_software_version": "9980",
            },
        )
        self.assertEqual(result["state"], RESOLVED_SPECIFIC)
        self.assertEqual(result["selected"], "specific.rpm")
        self.assertEqual(
            [candidate["id"] for candidate in result["candidates"]],
            ["generic.rpm", "specific.rpm"],
        )

    def test_incomplete_specific_candidate_blocks_generic_fallback(self) -> None:
        definitions = [
            (2, definition("generic.rpm", "engine.rpm", predicates=None)),
            (
                2,
                definition(
                    "specific.rpm",
                    "engine.rpm",
                    predicates=[
                        ("ecu.manufacturer_software_number", "03L906022"),
                        ("ecu.manufacturer_software_version", "9980"),
                    ],
                ),
            ),
        ]
        result = resolve_semantic(
            definitions,
            {"ecu.manufacturer_software_number": "03L906022"},
        )
        self.assertEqual(result["state"], INSUFFICIENT_IDENTITY)
        self.assertIsNone(result["selected"])

    def test_different_software_version_can_resolve_differently(self) -> None:
        definitions = [
            (
                2,
                definition(
                    "variant.9978",
                    "dpf.differential_pressure",
                    predicates=[
                        ("ecu.manufacturer_software_number", "03L906022"),
                        ("ecu.manufacturer_software_version", "9978"),
                    ],
                ),
            ),
            (
                2,
                definition(
                    "variant.9980",
                    "dpf.differential_pressure",
                    predicates=[
                        ("ecu.manufacturer_software_number", "03L906022"),
                        ("ecu.manufacturer_software_version", "9980"),
                    ],
                ),
            ),
        ]
        first = resolve_semantic(
            definitions,
            {
                "ecu.manufacturer_software_number": "03L906022",
                "ecu.manufacturer_software_version": "9978",
            },
        )
        second = resolve_semantic(
            definitions,
            {
                "ecu.manufacturer_software_number": "03L906022",
                "ecu.manufacturer_software_version": "9980",
            },
        )
        self.assertEqual(first["selected"], "variant.9978")
        self.assertEqual(second["selected"], "variant.9980")

    def test_equal_specificity_matches_remain_ambiguous(self) -> None:
        definitions = [
            (
                2,
                definition(
                    "by.software",
                    "engine.rpm",
                    predicates=[("ecu.manufacturer_software_number", "03L906022")],
                ),
            ),
            (
                2,
                definition(
                    "by.hardware",
                    "engine.rpm",
                    predicates=[("ecu.manufacturer_hardware_number", "03L907309")],
                ),
            ),
        ]
        result = resolve_semantic(
            definitions,
            {
                "ecu.manufacturer_software_number": "03L906022",
                "ecu.manufacturer_hardware_number": "03L907309",
            },
        )
        self.assertEqual(result["state"], AMBIGUOUS)
        self.assertIsNone(result["selected"])

    def test_more_specific_exact_match_wins_deterministically(self) -> None:
        definitions = [
            (
                2,
                definition(
                    "family",
                    "engine.rpm",
                    predicates=[("ecu.manufacturer_software_number", "03L906022")],
                ),
            ),
            (
                2,
                definition(
                    "variant",
                    "engine.rpm",
                    predicates=[
                        ("ecu.manufacturer_software_number", "03L906022"),
                        ("ecu.manufacturer_software_version", "9980"),
                    ],
                ),
            ),
        ]
        result = resolve_semantic(
            definitions,
            {
                "ecu.manufacturer_software_number": "03L906022",
                "ecu.manufacturer_software_version": "9980",
            },
        )
        self.assertEqual(result["state"], RESOLVED_SPECIFIC)
        self.assertEqual(result["selected"], "variant")

    def test_nonmatching_specific_allows_generic(self) -> None:
        definitions = [
            (1, {"id": "v1.generic", "semantic": "engine.rpm"}),
            (
                2,
                definition(
                    "specific",
                    "engine.rpm",
                    predicates=[("ecu.manufacturer_software_version", "9980")],
                ),
            ),
        ]
        result = resolve_semantic(
            definitions,
            {"ecu.manufacturer_software_version": "9978"},
        )
        self.assertEqual(result["state"], RESOLVED_GENERIC)
        self.assertEqual(result["selected"], "v1.generic")

    def test_no_candidates_matching_is_no_match(self) -> None:
        result = resolve_semantic(
            [
                (
                    2,
                    definition(
                        "specific",
                        "engine.rpm",
                        predicates=[("ecu.manufacturer_software_version", "9980")],
                    ),
                )
            ],
            {"ecu.manufacturer_software_version": "9978"},
        )
        self.assertEqual(result["state"], NO_MATCH)

    def test_catalog_resolution_is_input_order_independent(self) -> None:
        definitions = [
            (2, definition("z.generic", "vehicle.speed", predicates=None)),
            (
                2,
                definition(
                    "b.specific",
                    "engine.rpm",
                    predicates=[("ecu.manufacturer_software_version", "9980")],
                ),
            ),
            (2, definition("a.generic", "engine.rpm", predicates=None)),
        ]
        observed = {"ecu.manufacturer_software_version": "9980"}
        first = resolve_catalog(definitions, observed)
        second = resolve_catalog(list(reversed(definitions)), observed)
        self.assertEqual(first, second)
        self.assertEqual(list(first), ["engine.rpm", "vehicle.speed"])


if __name__ == "__main__":
    unittest.main()
