from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.validate import validate_repository


VALID_V1_DOCUMENT = """\
schema_version: 1
namespace: test.uds
sets:
  - id: uds.standard.ecu_identification
    version: 1
    members:
      - ecu.software_version
definitions:
  - id: test.f189.software_version
    semantic: ecu.software_version
    version: 1
    operation:
      type: uds.read_data_by_identifier
      identifier: "0xF189"
    response:
      positive_service: "0x62"
      identifier_echo: true
    decoder:
      type: opaque_bytes
    provenance:
      classification: VERIFIED
      confidence: high
      sources:
        - kind: standard
          citation: ISO 14229-1
    hardware_validation:
      status: not_applicable
"""

VALID_V2_DOCUMENT = """\
schema_version: 2
namespace: test.manufacturer
definitions:
  - id: test.engine_rpm.variant
    semantic: engine.rpm
    version: 1
    applicability:
      kind: ecu_fingerprint
      predicates:
        - field: ecu.manufacturer_software_number
          equals: 03L906022
        - field: ecu.manufacturer_software_version
          equals: "9980"
      provenance:
        classification: EXPERIMENTAL
        confidence: high
        sources:
          - kind: research
            citation: synthetic fixture
    operation:
      type: uds.read_data_by_identifier
      identifier: "0x1234"
    response:
      positive_service: "0x62"
      identifier_echo: true
    decoder:
      type: opaque_bytes
    provenance:
      classification: EXPERIMENTAL
      confidence: medium
      sources:
        - kind: research
          citation: synthetic fixture
    hardware_validation:
      status: not_validated
"""


class ValidatorTests(unittest.TestCase):
    def make_repo(self, documents: list[tuple[str, str]] | str) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp_dir)
        (temp_dir / "schema").mkdir(parents=True)
        for name in ("knowledge-v1.schema.json", "knowledge-v2.schema.json"):
            shutil.copy(Path("schema") / name, temp_dir / "schema" / name)

        if isinstance(documents, str):
            documents = [("standards/uds/test.yaml", documents)]
        for relative_path, document in documents:
            path = temp_dir / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(document, encoding="utf-8")
        return temp_dir

    def test_v1_document_remains_valid(self) -> None:
        self.assertEqual(validate_repository(self.make_repo(VALID_V1_DOCUMENT)), [])

    def test_v2_document_with_exact_applicability_passes(self) -> None:
        self.assertEqual(validate_repository(self.make_repo(VALID_V2_DOCUMENT)), [])

    def test_unknown_schema_version_fails(self) -> None:
        document = VALID_V1_DOCUMENT.replace("schema_version: 1", "schema_version: 99")
        errors = validate_repository(self.make_repo(document))
        self.assertTrue(any("unsupported schema_version 99" in error for error in errors), errors)

    def test_v2_requires_explicit_applicability(self) -> None:
        document = VALID_V2_DOCUMENT.replace(
            """    applicability:
      kind: ecu_fingerprint
      predicates:
        - field: ecu.manufacturer_software_number
          equals: 03L906022
        - field: ecu.manufacturer_software_version
          equals: "9980"
      provenance:
        classification: EXPERIMENTAL
        confidence: high
        sources:
          - kind: research
            citation: synthetic fixture
""",
            "",
        )
        errors = validate_repository(self.make_repo(document))
        self.assertTrue(any("applicability" in error for error in errors), errors)

    def test_v2_rejects_vin_as_applicability_field(self) -> None:
        document = VALID_V2_DOCUMENT.replace(
            "ecu.manufacturer_software_number", "vehicle.vin"
        )
        errors = validate_repository(self.make_repo(document))
        self.assertTrue(any("vehicle.vin" in error for error in errors), errors)

    def test_v2_rejects_duplicate_predicate_fields(self) -> None:
        document = VALID_V2_DOCUMENT.replace(
            """        - field: ecu.manufacturer_software_version
          equals: "9980"
""",
            """        - field: ecu.manufacturer_software_number
          equals: 03L906023
""",
        )
        errors = validate_repository(self.make_repo(document))
        self.assertTrue(
            any("repeats an applicability predicate field" in error for error in errors),
            errors,
        )

    def test_raw_request_field_fails_closed(self) -> None:
        document = VALID_V1_DOCUMENT.replace(
            'identifier: "0xF189"',
            'identifier: "0xF189"\n      raw_request: "27 01"',
        )
        errors = validate_repository(self.make_repo(document))
        self.assertTrue(any("raw_request" in error for error in errors), errors)

    def test_unknown_operation_fails_closed(self) -> None:
        document = VALID_V1_DOCUMENT.replace(
            'type: uds.read_data_by_identifier\n      identifier: "0xF189"',
            'type: uds.security_access\n      identifier: "0xF189"',
        )
        errors = validate_repository(self.make_repo(document))
        self.assertTrue(errors)

    def test_multiple_generic_definitions_for_same_semantic_are_rejected(self) -> None:
        second = VALID_V1_DOCUMENT.replace(
            "test.f189.software_version", "test.f188.software_version"
        ).replace('"0xF189"', '"0xF188"')
        errors = validate_repository(
            self.make_repo(
                [
                    ("standards/uds/first.yaml", VALID_V1_DOCUMENT),
                    ("standards/uds/second.yaml", second),
                ]
            )
        )
        self.assertTrue(
            any("multiple generic definitions" in error for error in errors), errors
        )

    def test_generic_plus_specific_same_semantic_is_allowed(self) -> None:
        specific = VALID_V2_DOCUMENT.replace(
            "semantic: engine.rpm", "semantic: ecu.software_version"
        ).replace('identifier: "0x1234"', 'identifier: "0xF189"')
        self.assertEqual(
            validate_repository(
                self.make_repo(
                    [
                        ("standards/uds/generic.yaml", VALID_V1_DOCUMENT),
                        ("manufacturers/test/specific.yaml", specific),
                    ]
                )
            ),
            [],
        )

    def test_identical_specific_applicability_is_rejected(self) -> None:
        second = VALID_V2_DOCUMENT.replace(
            "test.engine_rpm.variant", "test.engine_rpm.variant_duplicate"
        )
        errors = validate_repository(
            self.make_repo(
                [
                    ("manufacturers/test/first.yaml", VALID_V2_DOCUMENT),
                    ("manufacturers/test/second.yaml", second),
                ]
            )
        )
        self.assertTrue(
            any("identical applicability" in error for error in errors), errors
        )

    def test_vin_f190_is_excluded_from_ecu_identification_set(self) -> None:
        document = VALID_V1_DOCUMENT.replace(
            "ecu.software_version",
            "vehicle.vin",
        ).replace("0xF189", "0xF190")
        errors = validate_repository(self.make_repo(document))
        self.assertTrue(any("must not include VIN/F190" in error for error in errors), errors)

    def test_validation_errors_are_deterministically_sorted(self) -> None:
        document = VALID_V2_DOCUMENT.replace(
            "classification: EXPERIMENTAL", "classification: UNKNOWN", 1
        )
        repo = self.make_repo(document)
        first = validate_repository(repo)
        second = validate_repository(repo)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
