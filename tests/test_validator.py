from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.validate import validate_repository


VALID_DOCUMENT = """\
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
      identifier: \"0xF189\"
    response:
      positive_service: \"0x62\"
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


class ValidatorTests(unittest.TestCase):
    def make_repo(self, document: str) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp_dir)
        (temp_dir / "schema").mkdir(parents=True)
        shutil.copy(
            Path("schema/knowledge-v1.schema.json"),
            temp_dir / "schema/knowledge-v1.schema.json",
        )
        (temp_dir / "standards/uds").mkdir(parents=True)
        (temp_dir / "standards/uds/test.yaml").write_text(document, encoding="utf-8")
        return temp_dir

    def test_valid_document_passes(self) -> None:
        self.assertEqual(validate_repository(self.make_repo(VALID_DOCUMENT)), [])

    def test_unknown_schema_version_fails(self) -> None:
        errors = validate_repository(
            self.make_repo(VALID_DOCUMENT.replace("schema_version: 1", "schema_version: 2"))
        )
        self.assertTrue(any("1 was expected" in error for error in errors), errors)

    def test_raw_request_field_fails_closed(self) -> None:
        document = VALID_DOCUMENT.replace(
            "identifier: \"0xF189\"",
            "identifier: \"0xF189\"\n      raw_request: \"27 01\"",
        )
        errors = validate_repository(self.make_repo(document))
        self.assertTrue(any("raw_request" in error for error in errors), errors)

    def test_unknown_operation_fails_closed(self) -> None:
        document = VALID_DOCUMENT.replace(
            "type: uds.read_data_by_identifier\n      identifier: \"0xF189\"",
            "type: uds.security_access\n      identifier: \"0xF189\"",
        )
        errors = validate_repository(self.make_repo(document))
        self.assertTrue(errors)

    def test_duplicate_semantic_is_rejected(self) -> None:
        duplicate = """\
  - id: test.f188.software_version_duplicate
    semantic: ecu.software_version
    version: 1
    operation:
      type: uds.read_data_by_identifier
      identifier: \"0xF188\"
    response:
      positive_service: \"0x62\"
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
        errors = validate_repository(self.make_repo(VALID_DOCUMENT + duplicate))
        self.assertTrue(any("duplicate semantic id" in error for error in errors), errors)

    def test_vin_f190_is_excluded_from_ecu_identification_set(self) -> None:
        document = VALID_DOCUMENT.replace(
            "ecu.software_version",
            "vehicle.vin",
        ).replace("0xF189", "0xF190")
        errors = validate_repository(self.make_repo(document))
        self.assertTrue(any("must not include VIN/F190" in error for error in errors), errors)

    def test_validation_errors_are_deterministically_sorted(self) -> None:
        document = VALID_DOCUMENT.replace("classification: VERIFIED", "classification: UNKNOWN")
        repo = self.make_repo(document)
        first = validate_repository(repo)
        second = validate_repository(repo)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
