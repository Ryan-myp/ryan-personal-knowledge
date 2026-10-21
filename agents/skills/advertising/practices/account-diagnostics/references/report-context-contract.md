# Report Context Contract

`report_context` describes what a report Tool requested and what the bounded response contained. It is evidence metadata, not a substitute for provider account settings or a guarantee that the provider has no additional rows.

## Fields

| Field | Meaning |
|---|---|
| `provider` | Registered provider namespace that produced the report |
| `resource_level` | Report grain, such as campaign, ad group, ad, asset, or asset-group asset |
| `period.value` | Explicit date range/preset from the Tool input, or the provider default used by that Tool |
| `period.source` | `tool_input` or `provider_default`; a preset is not silently converted into dates |
| `account_timezone` | Account timezone when returned by an account metadata Tool; otherwise `value: null`, `status: unknown` |
| `account_currency` | Account currency when returned by an account metadata Tool; otherwise `value: null`, `status: unknown` |
| `attribution` | Attribution setting when returned by an authorized setting/report Tool; otherwise `value: null`, `status: not_returned_by_tool` |
| `completeness.returned_rows` | Number of rows in the response payload |
| `completeness.row_limit` | Effective bounded result limit known to the Tool |
| `completeness.may_be_truncated` | True when the returned row count reaches the effective limit |
| `completeness.status` | `empty`, `possibly_truncated`, or `within_limit` |

## Interpretation

- `empty` means the provider returned no report rows for this request. It does not mean the requested metric equals zero.
- `possibly_truncated` requires narrowing the date/resource scope or using an available pagination path before making completeness claims.
- `within_limit` means only that this response did not hit its known row bound. It does not certify source freshness, privacy-threshold coverage, or provider-side completeness.
- Timezone, currency, and attribution are deliberately unknown unless the current authorized Tool result supplies them. Do not infer them from a different account, an old report, or model memory.
- Account metadata can be gathered with a separate read Tool scoped to the same trusted account. If that lookup is unavailable, failed, or ambiguous, preserve the unknown value.
- Platform-attributed conversions remain platform-specific. Do not sum them into a deduplicated business total or interpret them as incremental outcomes.
- Spend and revenue may be combined only when currency is known and aligned. A shared date string is not sufficient when account timezones differ.

## Readout

Report provider, resource grain, requested period and its source, returned row count/limit, truncation status, account timezone/currency, attribution setting, and data freshness. Label missing context as Unknown and state how it limits the conclusion.
