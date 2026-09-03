# Contributing canonical knowledge

`obdentic-knowledge` contains reviewed, reusable Vehicle/ECU Knowledge for OBDentic. It is not a dump of values observed on one private vehicle and it is not an executable diagnostic scripting repository.

## Required evidence chain

Every new or changed definition must make the evidence chain reviewable:

```text
source / owned hardware evidence
  -> deterministic protocol definition
  -> response validation
  -> decoder rationale
  -> semantic fact
  -> applicability
  -> provenance + confidence + hardware-validation status
```

A plausible decoded value is never sufficient evidence by itself.

## Provenance vocabulary

Use one of the schema classifications and state confidence independently:

- `VERIFIED`: backed by a normative/authoritative source or independently reviewed evidence sufficient for the exact claim being made.
- `COMMUNITY`: supported by community material but not independently established to VERIFIED quality.
- `INFERRED`: a reasoned inference from evidence; the inference must be stated explicitly.
- `EXPERIMENTAL`: candidate knowledge retained for bounded validation and not authoritative by default.

Changing a definition's location or representation does not promote its provenance.

## Hardware validation

Hardware validation is separate from provenance. A standards-defined DID can be `VERIFIED` as a standardized identifier while support on a concrete ECU remains runtime evidence.

Use:

- `not_validated` when a vehicle-/ECU-specific definition still requires real-hardware validation;
- `validated` only with a reviewable evidence reference;
- `not_applicable` for definitions where hardware validation of the canonical meaning itself is not the relevant claim (for example a standards-defined identification DID whose per-ECU support is observed at runtime).

Do not mark a decoder validated solely because one idle value looked plausible.

## Safety boundary

Knowledge may only instantiate the operation and decoder primitives explicitly allowed by the versioned schema and the OBDentic core.

Never add fields or mechanisms for:

- raw CAN frames;
- arbitrary UDS payloads or service IDs;
- arbitrary ELM commands;
- coding/adaptation/basic settings;
- actuator/output tests;
- DTC clearing;
- SecurityAccess;
- ECU reset;
- arbitrary RoutineControl;
- executable code or arbitrary formulas.

Unknown fields, operation types and decoder primitives must fail validation. A Knowledge DB change cannot expand the executable safety capability of OBDentic.

## Privacy

Do not commit private per-vehicle inventory by default. In particular, do not publish:

- real VIN-indexed vehicle inventories;
- ECU serial numbers tied to a private vehicle;
- full private captures when a minimal sanitized fixture is sufficient;
- adapter credentials/authentication material.

Discovery output is local evidence first. Promotion into canonical knowledge is an explicit reviewed act.

## Clean-room rule

External projects may be used as research leads only unless their license and data terms explicitly permit reuse and the project intentionally accepts that dependency. For OBDium, retain the existing clean-room rule: do not copy code, datasets, fixtures or tables.

## Pull request checklist

A knowledge PR should state:

- [ ] Goal and scope are bounded.
- [ ] Source/provenance for every claim is present.
- [ ] Confidence is explicit.
- [ ] Hardware-validation state is explicit where applicable.
- [ ] Applicability is no broader than the evidence supports.
- [ ] No private identity/evidence was unintentionally committed.
- [ ] No arbitrary/raw/mutating operation surface was introduced.
- [ ] `python tools/validate.py .` passes.
- [ ] `python -m unittest discover -s tests -v` passes.

## Promotion workflow

The intended lifecycle is:

```text
private raw evidence
  -> deterministic local normalization
  -> observed vehicle/ECU inventory
  -> sanitized candidate knowledge
  -> review
  -> EXPERIMENTAL / INFERRED / COMMUNITY or VERIFIED as justified
  -> optional later hardware validation/promotion
```

There is deliberately no automatic `discover -> VERIFIED` path.
