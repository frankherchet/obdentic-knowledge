from __future__ import annotations

import unittest
from pathlib import Path

import yaml


EXPECTED = [
    ("ecu.boot_software_identification", "uds.f180.boot_software_identification", "0xF180"),
    ("ecu.application_software_identification", "uds.f181.application_software_identification", "0xF181"),
    ("ecu.manufacturer_spare_part_number", "uds.f187.manufacturer_spare_part_number", "0xF187"),
    ("ecu.manufacturer_software_number", "uds.f188.manufacturer_software_number", "0xF188"),
    ("ecu.manufacturer_software_version", "uds.f189.manufacturer_software_version", "0xF189"),
    ("ecu.system_supplier_identifier", "uds.f18a.system_supplier_identifier", "0xF18A"),
    ("ecu.manufacturing_date", "uds.f18b.manufacturing_date", "0xF18B"),
    ("ecu.serial_number", "uds.f18c.serial_number", "0xF18C"),
    ("ecu.manufacturer_hardware_number", "uds.f191.manufacturer_hardware_number", "0xF191"),
    ("ecu.system_supplier_hardware_number", "uds.f192.system_supplier_hardware_number", "0xF192"),
    ("ecu.system_supplier_hardware_version", "uds.f193.system_supplier_hardware_version", "0xF193"),
    ("ecu.system_supplier_software_number", "uds.f194.system_supplier_software_number", "0xF194"),
    ("ecu.system_supplier_software_version", "uds.f195.system_supplier_software_version", "0xF195"),
    ("ecu.system_name", "uds.f197.system_name", "0xF197"),
]


class StandardUdsMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = yaml.safe_load(
            Path("standards/uds/ecu-identification.yaml").read_text(encoding="utf-8")
        )
        cls.definitions = {
            definition["semantic"]: definition
            for definition in cls.document["definitions"]
        }

    def test_current_canonical_document_is_schema_v2(self) -> None:
        self.assertEqual(self.document["schema_version"], 2)

    def test_bounded_set_order_and_operation_identity_are_unchanged(self) -> None:
        members = self.document["sets"][0]["members"]
        self.assertEqual(members, [semantic for semantic, _, _ in EXPECTED])
        self.assertEqual(len(self.definitions), len(EXPECTED))

        actual = []
        for semantic in members:
            definition = self.definitions[semantic]
            actual.append(
                (
                    semantic,
                    definition["id"],
                    definition["operation"]["identifier"],
                )
            )
            self.assertEqual(
                definition["operation"]["type"], "uds.read_data_by_identifier"
            )
        self.assertEqual(actual, EXPECTED)

    def test_all_standard_definitions_are_explicitly_generic(self) -> None:
        for definition in self.definitions.values():
            applicability = definition["applicability"]
            self.assertEqual(applicability["kind"], "generic")
            self.assertEqual(
                applicability["provenance"]["classification"], "VERIFIED"
            )
            self.assertEqual(applicability["provenance"]["confidence"], "high")

    def test_vin_remains_outside_bounded_ecu_identification(self) -> None:
        for semantic, _, did in EXPECTED:
            self.assertNotEqual(semantic, "vehicle.vin")
            self.assertNotEqual(did.upper(), "0XF190")


if __name__ == "__main__":
    unittest.main()
