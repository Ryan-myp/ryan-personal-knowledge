# Google Ads Report Interpretation

Use this reference for Google Ads search-term, conversion, or campaign-report questions. The current registered Tool schema and the exact returned fields remain authoritative; this is not a promise that every report type is available through the application.

## Search terms are incomplete evidence

Google states that some search terms with insufficient query activity may be omitted from the Search terms report for privacy. Therefore, visible terms are not automatically a complete or representative sample of all searches.

- Do not infer that an absent query received no impressions or clicks.
- If both the search-term report and a compatible campaign-level total are available, compare them only for the same account, campaign scope, date basis, and compatible metric definition. You may report disclosed-click coverage as `visible search-term clicks / compatible campaign clicks`; label it as report coverage, not as the share of all query intent.
- If either denominator or compatible query is unavailable, state that coverage is Unknown. Do not estimate omitted query themes.
- Confirm which campaign types the queried report covers. Google Ads exposes distinct report resources, and the standard `search_term_view` does not cover Performance Max; do not use its absence as evidence about PMax search demand.
- Search-term report rows can be segmented. Preserve the requested grain and avoid double-counting when aggregating.

## Conversion columns are different measures

`Conversions` and `All conversions` are not interchangeable. Google describes `All conversions` as including actions not included in the main `Conversions` column. Check the conversion actions and account/campaign goal semantics before describing a generic conversion as a purchase, qualified lead, or install.

When a report is segmented by conversion action, state that the row grain changed. Google documents that rows with all-zero metrics, including new conversion actions, may not be returned. An absent row is therefore not sufficient proof that the action does not exist or that it had no activity.

Conversion reporting may lag. Separate report date basis from conversion date: use a `by_conversion_date` metric when the question is explicitly about conversion occurrence date and the current query supports it. Do not silently compare click-date and conversion-date series.

## Check the report before explaining performance

Before interpreting a change:

1. Confirm account, campaign type, object level, date range, timezone, filters, metrics, and any segments.
2. Check whether the response is live, simulated/offline, failed, partial, or missing provenance. A simulated response is not current account evidence.
3. Separate true zero values from empty rows, omitted rows, query errors, incomplete pages, and unavailable fields.
4. Check whether campaign names are being mistaken for actual targeting or settings; verify the relevant returned resource fields.
5. Compare equal windows and note changes to campaign configuration. If change history or experiment metadata is unavailable, do not invent a cause.
6. Include sample sizes and data maturity. There is no universal number of clicks or conversions that makes every account conclusive.

If the current Tool cannot query the required search-term, conversion-action, experiment, landing-page, or change-history evidence, list it as a capability/evidence gap. Do not claim that the audit covered it.
