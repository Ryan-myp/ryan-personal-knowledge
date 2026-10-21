# Conversion Tracking QA Runbook

Use this runbook to verify a tracking path with sanitized, scoped evidence. It is a review and test plan, not an external-system connector.

## Evidence by Stage

| Stage | Minimum evidence | Common failure class |
|---|---|---|
| Business event | Reproducible action, expected event count, canonical transaction/lead state | Trigger is absent, too early, or repeated on refresh |
| Client/server capture | Test-only event name or flag, required properties present, consent state handled | Tag/SDK not fired, blocked request, app lifecycle gap |
| Transport receipt | Sanitized request status, provider receipt/error category, batch/test identifier | Network failure, invalid schema, scope or permission rejection |
| Deduplication and matching | Stable event key behavior and aggregate match/dedup status | Client/server keys differ, keys are reused, eligible identifiers omitted |
| Attribution | Campaign/linkage fields, attribution setting and observation window | Click/link ID lost, incompatible window, consent or identity gap |
| Reporting | Query level, date basis, time zone, refresh timestamp and maturity | Late arrival, report filter mismatch, modeled/backfilled data |
| Business outcome | Deduplicated CRM/order counts, cancellations/refunds and value basis | Test traffic mixed into production, lead status mismatch, refund lag |

Mark each stage `pass`, `fail`, or `unknown`. A successful browser event or API receipt is not evidence that downstream matching, attribution, reporting, or business reconciliation succeeded.

## Triage Order

1. Fix the question and expected outcome: which event, population, date basis, platform, and business source are being checked?
2. Confirm the issue with a small, repeatable test that is isolated from production optimization and reporting.
3. Compare expected and observed aggregate counts at each stage; preserve event-time and receipt-time separately.
4. Classify the first failing stage. Check schema/permissions before retrying; check stable idempotency before replaying; do not resend an entire batch when only some records failed.
5. Make one minimal correction in the owning system, repeat the test, and read back the downstream state.
6. Resume optimization only after the signal is valid, deduplicated, sufficiently mature, and mapped to the intended optimization event.

## Failure Patterns

| Symptom | Check first | Do not infer |
|---|---|---|
| Business outcomes exist but platform events fall | Trigger coverage, consent, transport errors, SDK/CAPI/MMP health and event-time lag | That media performance fell |
| Platform events exceed business outcomes | Test traffic, repeated triggers, retries, duplicate keys, cancellations/refunds | A fixed percentage of platform conversions is false |
| Event is received but not attributed | Event mapping, click/link continuity, time window, eligible match state and consent | That the event was not received |
| Event appears in diagnostics but not report | Report level/filter, time zone, reporting delay, backfill and maturity | That a successful test event is a production conversion |
| Value is missing or implausible | Amount units, currency, gross/net/refund basis, source transaction and event mapping | That the platform should infer a missing value |
| Client and server both report success | Same business-event definition, stable shared event key, dedup response/status | That deduplication occurred merely because both requests succeeded |

## QA Record

Record the event name/version, sanitized test case, expected and observed aggregate counts, test/production separation, timestamps and time zones, provider status/error category, report refresh time, privacy review, first failing stage, change owner, retest result, and rollback condition. Keep secrets and user-level identifiers out of the record.

If the connected platform has no authorized diagnostic Tool, state which evidence is unavailable and give the user a safe manual verification path. Never claim the configuration was changed or the live event path passed based only on a proposed plan.
