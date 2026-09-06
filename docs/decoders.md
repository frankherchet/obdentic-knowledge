# Canonical decoder contracts

Canonical Knowledge decoders are deterministic representation rules. They translate response payload bytes only as explicitly declared by a versioned Knowledge definition; they do not infer vehicle meaning from plausibility, responder order, VIN, or surrounding observations.

The executable decoder vocabulary is closed by the versioned schema. Unknown decoder types or fields fail validation.

## `opaque_bytes`

`opaque_bytes` preserves the validated payload as bytes. It makes no text, numeric, padding, or identity claim.

A consumer must not reinterpret an `opaque_bytes` payload as ASCII, UTF-8, hexadecimal identity text, a number, or another fingerprint merely because the bytes look plausible.

The generic standardized UDS ECU-identification definitions intentionally use `opaque_bytes` unless payload encoding is independently justified.

## `ascii`

An ASCII decoder has the form:

```yaml
decoder:
  type: ascii
  trim: none | space | nul | space_and_nul
```

The decoder operates on the payload **after** the definition's protocol/response contract has validated service, identifier echo and payload length.

### Character domain

Every byte that remains after the declared trailing-padding removal must be 7-bit ASCII (`0x00..0x7f`). Bytes greater than `0x7f` are invalid.

Remaining ASCII control characters are invalid for normalized identity text: `0x00..0x1f` and `0x7f`. Printable ASCII therefore means `0x20..0x7e` after trimming.

The decoder does not case-fold, parse numbers, normalize punctuation, collapse whitespace, choose substrings, or apply plausibility filtering.

### `trim` means trailing padding only

`trim` removes only the maximal **trailing** run authorized by the selected policy:

| Policy | Trailing bytes removed |
| --- | --- |
| `none` | none |
| `space` | `0x20` only |
| `nul` | `0x00` only |
| `space_and_nul` | any trailing run consisting only of `0x20` and/or `0x00` |

Leading bytes are never removed by `trim`. Interior bytes are never removed by `trim`.

This is intentional: padding removal is a representation rule, not an identity heuristic. If a future format requires leading trimming or another transformation, it needs a separately modeled decoder contract rather than a broader interpretation of `trim`.

### Examples

The examples below show the payload bytes presented to the ASCII decoder and the resulting normalized text or error.

| Policy | Input bytes | Result |
| --- | --- | --- |
| `none` | `41 42 43` | `ABC` |
| `space` | `41 42 43 20 20` | `ABC` |
| `nul` | `41 42 43 00 00` | `ABC` |
| `space_and_nul` | `41 42 43 20 00 20` | `ABC` |
| `space` | `20 41 42 43 20` | ` ABC` — leading space is preserved |
| `nul` | `00 41 42 43 00` | error — leading NUL is not trimmed and remains a control byte |
| `space` | `41 20 42 20` | `A B` — interior space is preserved |
| `space_and_nul` | `41 00 42 20` | error — interior NUL is not trimmed |
| `none` | `41 80` | error — `0x80` is not 7-bit ASCII |

For consumers that use decoded text as an ECU fingerprint/applicability fact, an empty result after trimming is invalid. Missing or invalid normalization remains unresolved; it is never replaced by a guessed value.

## `linear_integer`

`linear_integer` is a closed numeric decoder with explicit width, endianness, signedness, scale and offset. Those fields define numeric decoding only.

A numeric result does not automatically define a canonical ECU fingerprint string. If an applicability field needs a textual representation of a numeric value, that representation requires an explicit separately reviewed contract rather than implementation-local formatting.

## Provenance and validation

Decoder success does not promote provenance or hardware-validation state. `VERIFIED`, `COMMUNITY`, `INFERRED`, and `EXPERIMENTAL` remain independent classifications, and hardware validation remains a separate dimension.

A consumer should bind decoding to the exact pinned Knowledge repository revision and definition identity/version that declared the decoder. Re-decoding under a different Knowledge revision is a new deterministic interpretation of the preserved evidence, not a mutation of the original observation.
