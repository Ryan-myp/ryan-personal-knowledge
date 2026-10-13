# Event Measurement Contract

Use this template to produce an implementation-ready review artifact. It is a specification only; it does not configure a provider or analytics platform.

## Event Dictionary

| Field | Required description |
|---|---|
| Business event | Stable business meaning and decision it supports |
| Event name/version | Canonical name plus provider-specific mapping, if verified |
| Trigger | Exact user or system condition; include exclusions |
| Event unit/key | Source of uniqueness, scope, generation owner, and deduplication window |
| Properties | Minimum required fields, type, allowed values, null behavior, and sensitive-data classification |
| Value | Amount, currency, gross/net/refund basis, if applicable |
| Source and owner | Client/server/system of record and accountable team |
| Time | Event timestamp, account/property time zone, expected latency, and late-arrival handling |
| Consent/retention | Applicable consent state, purpose, retention, deletion, and access constraints |
| Validation | Test method, expected count/value, duplicate/missing checks, and evidence |

## Validation Matrix

| Check | Evidence to capture |
|---|---|
| Correct trigger and exclusions | Reproducible test path and expected event count |
| Required properties and types | Sanitized event sample and contract validation |
| Duplicate protection | Repeated-submit/retry test and dedup key behavior |
| Cross-domain/app handoff | Entry identity and downstream continuity, where permitted |
| Client/server parity | Event IDs and provider receipt status without exposing personal data |
| Currency/value semantics | Source transaction compared to the documented value basis |
| Delay and maturity | Event-time versus receipt/report-time observation |
| Privacy | Consent state, field allowlist, redaction and retention checks |

Use test traffic clearly separated from production. Do not place raw emails, phone numbers, access tokens, advertising identifiers, or other direct identifiers in a Skill, prompt, ordinary log, or report. Hashing alone does not establish that collection or sharing is permitted.

## UTM Governance

Define one canonical owner and registry for `source`, `medium`, `campaign`, `content`, and `term`; document case normalization, separators, reserved values, platform mapping, and version changes. Avoid putting names, email addresses, account secrets, or other personal/sensitive values in URLs. A UTM label describes a link; it does not prove a conversion or causality.
