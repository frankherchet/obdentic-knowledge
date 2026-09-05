# obdentic-knowledge

Canonical, reviewed, versioned Vehicle/ECU Knowledge for [OBDentic](https://github.com/frankherchet/obdentic).

## Role

This repository owns reusable deterministic knowledge. It is deliberately separate from both OBDentic's executable core and private observations from concrete vehicles.

```text
vehicle
  -> raw transport/responder evidence
  -> protocol normalization
  -> private observed VehicleInstance / EcuInstances
              +
       pinned obdentic-knowledge
              -> effective Vehicle Knowledge
              -> semantic facts / profiles / snapshots
              -> diagnostic reasoning / presentation
```

The three concepts must remain distinct:

- **Evidence / private inventory** — what one OBDentic installation actually observed about a concrete vehicle and its ECUs.
- **Canonical Knowledge** — reviewed reusable definitions in this repository.
- **Profiles** — semantic selection and observation/timing intent; profiles do not contain PID/DID/CAN/UDS/ELM decoder knowledge.

## Repository layout

Current layout:

```text
schema/
  knowledge-v1.schema.json
  knowledge-v2.schema.json
standards/
  uds/
    ecu-identification.yaml
manufacturers/
  ... future reviewed manufacturer/ECU knowledge
semantic/
  ... future cross-protocol semantic definitions
docs/
  applicability.md
tools/
  applicability.py
  validate.py
tests/
```

`manufacturers/` and `semantic/` may be absent until the first definitions are added. The validator enumerates all canonical YAML files in deterministic path order.

## Schema v1

Every v1 canonical YAML document declares:

```yaml
schema_version: 1
namespace: example.namespace
definitions: []
```

Definitions have stable IDs and semantic IDs, a constrained read-only operation, response contract, a decoder chosen from a closed primitive set, provenance/confidence and hardware-validation state.

Schema v1 is immutable. Existing pinned revisions and captures must continue to validate against the exact contract they were created with.

## Schema v2 and applicability

Schema v2 adds explicit applicability without changing the executable operation vocabulary. Every v2 definition declares either generic applicability or an exact ECU-fingerprint predicate set with separate applicability provenance.

A v1 definition is treated as generic by an applicability-aware resolver. A v2 specific definition may coexist with a generic definition for the same semantic. Resolution is conservative and deterministic: exact more-specific matches may supersede generic knowledge, equal-specificity matches remain ambiguous, and an incomplete specific candidate blocks unsafe generic fallback.

VIN is not an applicability key. Matching uses a closed set of normalized vehicle/ECU identity facts and exact string equality only — no regex, ranges, fuzzy matching, ML or decoded-value plausibility.

See [docs/applicability.md](docs/applicability.md) for the complete fingerprint vocabulary, matching states, specificity rules and ambiguity behavior.

Unknown schema versions and unknown fields fail validation.

### Closed operation vocabulary

The schemas currently permit only explicitly modeled read operations such as:

```yaml
operation:
  type: uds.read_data_by_identifier
  identifier: "0xF189"
```

and the initial generic OBD-II Mode 01 PID primitive reserved for staged migration.

The schemas do **not** contain a raw byte/string escape hatch. Canonical knowledge cannot express arbitrary CAN frames, UDS service payloads, ELM commands, session control, SecurityAccess, coding/adaptation, actuator tests, DTC clear or arbitrary RoutineControl.

OBDentic still validates loaded definitions against its own closed Rust operation/decoder types and `SafetyPolicy`. The Knowledge DB cannot expand the executable safety capability of the core.

## Standard UDS ECU identification

`standards/uds/ecu-identification.yaml` defines the bounded standard identification candidate set for already-known/evidenced ECU targets. It currently includes the standardized meanings for:

- `F180` Boot Software Identification
- `F181` Application Software Identification
- `F187` Vehicle Manufacturer Spare Part Number
- `F188` Vehicle Manufacturer ECU Software Number
- `F189` Vehicle Manufacturer ECU Software Version Number
- `F18A` System Supplier Identifier
- `F18B` ECU Manufacturing Date
- `F18C` ECU Serial Number
- `F191` Vehicle Manufacturer ECU Hardware Number
- `F192` System Supplier ECU Hardware Number
- `F193` System Supplier ECU Hardware Version Number
- `F194` System Supplier ECU Software Number
- `F195` System Supplier ECU Software Version Number
- `F197` System Name / Engine Type

The set deliberately excludes `F190` VIN. VIN is vehicle identity/private inventory, while the set above is ECU identification knowledge.

A canonical DID definition does **not** assert that every ECU supports that DID. Runtime support/error/timeout evidence is recorded independently per ECU instance by OBDentic.

Payloads are kept `opaque_bytes` here unless the payload encoding itself is independently justified. Manufacturer-/supplier-specific interpretation belongs in more-specific reviewed knowledge, not in the generic standard definition.

## Validation

Install the small repository-local validation dependencies and run:

```bash
python -m pip install --requirement requirements.txt
python tools/validate.py .
python -m unittest discover -s tests -v
```

CI runs both commands for pull requests and `main`.

The validator additionally checks repository-level invariants that are awkward to express in one JSON Schema document, including duplicate definition IDs, applicability-aware semantic conflicts, duplicate predicate fields, set references and the explicit exclusion of VIN/F190 from the ECU-identification discovery set.

## Provenance and promotion

Research status remains explicit:

- `VERIFIED`
- `COMMUNITY`
- `INFERRED`
- `EXPERIMENTAL`

Confidence, applicability provenance and hardware-validation status are separate metadata dimensions. A plausible value does not make knowledge VERIFIED, an applicability match does not validate a decoder, and a standards-defined DID does not imply support on a concrete ECU.

See [CONTRIBUTING.md](CONTRIBUTING.md) for evidence, privacy, clean-room and promotion rules.

## Privacy

This public canonical repository is not the local vehicle database. Do not commit VIN-indexed private inventory, real ECU serial numbers tied to a private vehicle, adapter credentials or raw private captures by default.

The intended lifecycle is:

```text
private evidence
  -> observed local inventory
  -> sanitized candidate
  -> review
  -> canonical knowledge PR
```

There is no automatic `discover -> VERIFIED` path.

## Pinning from OBDentic

OBDentic is intended to consume an explicit immutable revision of this repository, preferably as a Git submodule or an equivalently deterministic pinned repository dependency.

Normal vehicle/runtime operation must not perform `git pull` or depend on GitHub/network availability. A knowledge update is a reviewed OBDentic dependency update.

Captures should eventually preserve both the OBDentic core revision and exact Knowledge DB revision/definition identity so old evidence can be re-decoded later without overwriting the original interpretation.

## Tracking

Initial Knowledge DB work is tracked by issues #1–#8 in this repository and the discovery/knowledge integration epic `frankherchet/obdentic#22` with implementation slices `#84`–`#90`.
