# Attribution Reconciliation and Method Selection

This operational checklist complements the repository Wiki. It does not connect to analytics, CRM, MMP, or ad-platform systems.

## Reconciliation Table

| Source | Number and definition | Window/date basis | Deduplication and maturity | Known limitations |
|---|---|---|---|---|
| Ad platform | Platform-attributed conversions/value | Click/view windows, account time zone | Platform event and model status | Self-credit, modeled data, overlapping platform claims |
| Analytics | Observed sessions/events and configured attribution | Property time zone and attribution settings | Consent, identity and event deduplication | Lost referrers, cross-device gaps, modeled behavior |
| Backend/CRM/finance | Business outcome and value | Business event timestamp and accounting rules | Canonical transaction/lead key, cancellations/refunds | Missing campaign linkage or manually entered source |
| Survey | Respondent-reported discovery or influence | Survey point and response period | Sampling and non-response | Recall and response bias |

Do not force these columns to match. First align definitions, scope, time, currency, filters and maturity; then report the remaining gap and its plausible causes. Keep platform credit separate from deduplicated business outcomes.

## Choose the Method for the Decision

| Decision | Candidate evidence | Main limitation to disclose |
|---|---|---|
| Day-to-day platform optimization | Mature platform reporting, optionally path analysis | Directional, platform-specific credit; not causal lift |
| Journey contribution | MTA or rule-based path view | Only observed and successfully linked touches are represented |
| Portfolio allocation across channels | MMM when suitable historical variation and outcome data exist | Aggregate, specification-dependent, slow-moving estimate |
| Whether a channel/tactic caused additional outcomes | Randomized holdout or defensible quasi-experiment | Contamination, power, spillover and external changes |
| Long-term customer value | Mature cohort outcomes joined to business value | Requires follow-up time and does not alone prove media causality |

## Incrementality Readout

Report the treatment/control definition, assignment unit, exposure and contamination checks, period, primary outcome, uncertainty, sample adequacy, external events, and analysis method. Distinguish measured lift from platform-attributed conversions. When the design cannot support a causal claim, label it observational or inconclusive and state the next evidence needed.
