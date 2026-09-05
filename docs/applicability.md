# Knowledge applicability and ECU fingerprints

Canonical Knowledge describes reusable facts and read-only decoding rules. It does not identify one private vehicle.

The resolution boundary is:

```text
private observed VehicleInstance
  -> observed EcuInstances
     -> normalized identity/topology facts
              +
       canonical Knowledge definitions
              -> applicability matching
              -> effective Vehicle Knowledge
```

VIN remains a private vehicle-instance key for local inventory/cache lookup. It is **not** an applicability field in canonical Knowledge.

## Schema versioning

Applicability is introduced in Knowledge schema **v2**. Schema v1 is intentionally left immutable: existing pinned revisions and captures must continue to validate against the exact contract they were created with.

A v1 definition is interpreted by an applicability-aware resolver as generic knowledge. A v2 definition declares applicability explicitly.

## Applicability kinds

Every v2 definition has one `applicability` object.

Generic knowledge:

```yaml
applicability:
  kind: generic
  provenance:
    classification: VERIFIED
    confidence: high
    sources:
      - kind: standard
        citation: ISO 14229-1
```

ECU-fingerprint-specific knowledge:

```yaml
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
      - kind: hardware_evidence
        citation: sanitized evidence reference
```

Applicability provenance is separate from the definition's own provenance and from `hardware_validation`. Matching an applicability rule does not make the underlying decoder VERIFIED and does not constitute hardware validation.

## Closed fingerprint vocabulary

Schema v2 permits exact predicates only for:

- `vehicle.manufacturer`
- `ecu.logical_role`
- `ecu.addressing_family`
- `ecu.boot_software_identification`
- `ecu.application_software_identification`
- `ecu.manufacturer_spare_part_number`
- `ecu.manufacturer_software_number`
- `ecu.manufacturer_software_version`
- `ecu.system_supplier_identifier`
- `ecu.manufacturer_hardware_number`
- `ecu.system_supplier_hardware_number`
- `ecu.system_supplier_hardware_version`
- `ecu.system_supplier_software_number`
- `ecu.system_supplier_software_version`
- `ecu.system_name`

VIN, ECU serial number and manufacturing date are deliberately excluded as canonical applicability keys. They identify concrete instances more readily than reusable ECU variants and remain private observed inventory unless a future separately reviewed schema change justifies otherwise.

A definition may use each predicate field at most once.

## Exact comparison semantics

Applicability compares **already normalized observed facts** to canonical predicate values by exact string equality.

The applicability layer does not perform:

- case folding
- whitespace guessing
- regex matching
- prefix/suffix matching
- numeric ranges
- semantic-version ranges
- fuzzy similarity
- ML classification
- decoded-value plausibility scoring

Byte-to-fact normalization belongs upstream. If normalization for an identity field is not justified, the resolver must keep identity insufficient rather than invent a match.

## Candidate evaluation

For one ECU and one definition:

- `generic`: no ECU identity predicate is required.
- `exact_match`: every declared fingerprint predicate is observed and equal.
- `partial_candidate`: every observed predicate agrees, but one or more required predicate fields are missing.
- `no_match`: at least one observed predicate conflicts.

A partial candidate is not promoted to an exact match.

## Semantic resolution and specificity

Definitions are grouped by semantic ID.

Resolution is deterministic:

1. Evaluate all candidates.
2. If specific exact matches exist, prefer the greatest number of satisfied exact predicates.
3. If exactly one candidate has that greatest specificity, resolve to it.
4. If multiple candidates tie at greatest specificity, the semantic is `ambiguous`.
5. If no specific exact match exists but at least one specific candidate is partial, the semantic is `insufficient_identity`.
6. Only when all specific candidates are proven non-matches may one generic candidate be selected.
7. With no applicable candidate, the semantic is `no_match`.

The conservative rule in step 5 is important: a partial specific candidate blocks generic fallback because the missing identity fact could prove that the specific definition supersedes the generic definition.

Input file order, ECU enumeration order and definition order must not affect the result.

## Static validation of duplicate semantics

Schema v2 allows multiple definitions for the same semantic so generic and ECU-specific knowledge can coexist.

Repository validation still rejects permanently unsafe duplicate structures:

- more than one generic definition for the same semantic;
- two definitions with the same semantic and identical applicability predicates;
- repeated predicate fields inside one applicability rule.

Different specific predicates may coexist. If an observed ECU satisfies equally specific competing rules, runtime resolution remains explicitly ambiguous.

## Composition and provenance

Conceptually:

```text
generic standards knowledge
        +
manufacturer / ECU-specific knowledge
        =
effective semantic catalog
```

Selecting a more-specific definition does not erase other candidates. Resolvers should preserve candidate definition IDs, versions and applicability/definition provenance so the decision remains inspectable and reproducible.

No definition is selected because its decoded value looks more plausible.

## Safety boundary

Applicability only determines which already-modeled canonical definition is relevant. It cannot add a protocol operation.

The consuming OBDentic core must still:

```text
effective semantic definition
  -> closed typed read-only operation
  -> SafetyPolicy
  -> DiagnosticSession
```

A successful fingerprint match never authorizes raw CAN/UDS/ELM commands, session changes, SecurityAccess, coding, adaptation, actuator execution, DTC clearing or other mutating operations.
