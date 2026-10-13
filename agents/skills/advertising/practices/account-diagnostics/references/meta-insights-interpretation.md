# Meta Insights Report Interpretation

Use this reference for Meta Campaign, Ad Set, Ad, and Insights report questions. The current registered Tool schema and exact returned fields are authoritative; this guide does not promise support for every Marketing API report parameter.

## Current Agent Query Boundary

In the current repository contract:

- Campaign reporting accepts campaign IDs, a date preset, and a row limit.
- Ad Set and Ad reporting accept their resource IDs, a date range, requested fields, and a row limit.
- The report Tools do not expose `breakdowns`, `action_breakdowns`, `time_increment`, or configurable attribution windows. Do not claim the Agent queried age, placement, device, action-type breakdowns, or a custom attribution window through these Tools. Analyze a user-provided/exported breakdown only when its source and query settings are identified.
- The report response limit is a maximum. If the returned row count reaches that limit, treat completeness as Unknown unless the response proves the result was complete; narrow the scope or request a suitable export.
- Offline fallback data is marked `data_status: offline_no_client` and `simulated: true`; it is not evidence from the user's Meta account.

These boundaries describe this repository's current Tool contract, not all capabilities of Meta's API.

## Fix the Report Grain

Before comparing results, capture the ad account, resource level (Campaign, Ad Set, or Ad), IDs, date range, account timezone if available, currency, requested fields, filters, retrieval time, and source status. Compare like-for-like levels and windows. A Campaign total and a sum of child Ad Set or Ad rows can differ because of scope, delivery changes, missing children, row limits, or different query definitions; do not silently reconcile them.

The report client defaults to delivery and outcome fields including impressions, clicks, CTR, CPC, spend, purchase ROAS, cost per result, actions, and action values. Defaults can change with the Tool contract. State which fields were actually returned; absence of a field is not a zero.

## Read Action Metrics Carefully

- `actions` and `action_values` can contain multiple event/action types. Identify the exact `action_type` before describing a generic action as a purchase, lead, registration, or app event.
- Keep event count, attributed result, and value distinct. An attributed result is not necessarily incremental, and platform-attributed values from separate channels must not be added into a business total.
- Preserve the report's aggregation grain. Do not sum reach, frequency, or overlapping audience rows as if they were mutually exclusive.
- If the returned result omits action-type or demographic/placement breakdowns, do not infer that those categories had no activity.

## Diagnose Before Recommending

1. Check whether the response is live, simulated/offline, failed, partial, capped, or missing provenance.
2. Verify that resource level, date range, timezone, currency, fields, and account scope match the comparison being made.
3. Separate delivery metrics (impressions, clicks, spend) from action counts and attributed value; state definitions and denominators for calculated rates.
4. Check whether action names, account goals, attribution settings, event deduplication, and conversion maturity are known. If the Tool response does not provide them, mark them Unknown rather than guessing.
5. Compare windows of equal length and note known campaign/ad set changes. Do not infer a cause from a trend alone.
6. If a required breakdown, attribution setting, change history, or conversion-source reconciliation is not available through the current Tool, list it as an evidence/capability gap. Do not substitute a similar-looking metric.

Meta Insights level, fields, breakdown compatibility, and attribution behavior can vary with API version and request settings. Current Tool schemas and official platform documentation must be checked before treating a field or combination as supported.
