# MMM Data Readiness

Use this checklist before recommending a media-mix model or interpreting a budget allocation as an MMM result. Meridian guidance is a practical reference, not a universal pass/fail rule for every MMM implementation.

## Minimum Dataset Shape

- Build a continuous panel by time, preferably weekly, and by geography when available.
- Use a summable business KPI such as revenue, units, or conversions. Do not sum rates such as CTR, CPA, or ROAS.
- For each paid channel, include media spend and a summable exposure metric such as impressions or clicks. Spend can proxy exposure only when physical delivery data is unavailable; disclose that price fluctuations may confound the proxy.
- Add time-aligned control variables that capture plausible causes of both KPI changes and media planning. Record definitions, sources, and transformations.
- Include sufficient pre-period media history for the configured carryover/max-lag window.
- Make the geo/time panel complete. Treat confirmed inactive media as zero; investigate and justify imputation for KPI and controls rather than replacing missing values with zero.

## History and Model Complexity

Google Meridian's general rule of thumb is at least two years of weekly data for geo-level models, three years for national-level models, and three years when using monthly observations. These are directional starting points, not guarantees or universal minimums.

Assess history together with:

- Number of media channels, controls, treatments, time effects/knots, and other estimated effects.
- Variation in media spend/exposure and outcome; many flat or highly correlated channels are difficult to separate.
- Geo count and whether geo-level pooling is plausible.
- Data-to-parameter diagnostics, exploratory checks, convergence, posterior sensitivity, and credible intervals.
- Whether important confounders and experimental calibration evidence are available.

Meridian generally targets channel-level effects. Campaign-level reporting should be aggregated by channel and period for MMM; campaign-level optimization is a different, more granular question.

## Decision Labels

- **Not ready**: Only a short window, non-summable KPIs, missing media/control periods, no comparable channel definitions, or no credible outcome source. Do not claim an MMM estimate.
- **Preparation only**: The minimum panel is being assembled or key controls, geographies, mature outcomes, or lag history are missing. Produce a data-gap plan, not a budget optimum.
- **Candidate for modeling**: Dataset shape and history look plausible. This only authorizes a modeling/EDA review; it does not prove identifiability, convergence, causal validity, or reliable ROI.

## Advertising Agent Boundary

The cross-channel budget Tool is not an MMM. It computes a bounded historical-efficiency heuristic from caller-supplied weekly reports, blocks immature/non-live/incomparable inputs, and cannot independently verify report provenance. Label its output directional; do not call average historical ROAS marginal ROAS or causal lift.

References:

- Google Meridian, [Collect and organize your data](https://developers.google.com/meridian/docs/pre-modeling/collect-data)
- Google Meridian, [Amount of data needed](https://developers.google.com/meridian/docs/pre-modeling/amount-data-needed)
