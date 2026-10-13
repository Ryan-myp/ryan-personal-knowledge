# Advertising Experiment Design Notes

Use this reference to turn an advertising question into a reviewable design. It supplements the repository Wiki; it is not a statistical calculator or platform-specific implementation guide.

## Design Record

| Field | Record |
|---|---|
| Decision | What action will change if evidence supports the hypothesis? |
| Evidence | Source, date range, account/resource scope, and known limitations |
| Hypothesis | Observation, change, expected mechanism, audience, and outcome |
| Experimental unit | User, account, geography, campaign, or another justified unit |
| Assignment | Randomization or matched/quasi-experimental method; include contamination risks |
| Primary metric | One pre-specified metric with numerator, denominator, and source |
| Guardrails | Business quality, cost, policy, delivery, or user-harm limits |
| Planning inputs | Baseline, minimum worthwhile effect, allocation, variance/model, power and error-rate choices |
| Observation | Start/end rules, attribution window, conversion maturity, and data refresh lag |
| Stop rule | Planned sample/horizon, valid sequential method, or safety stop |

## Advertising-Specific Checks

- Prefer platform-supported randomized experiments when available and suitable; verify actual assignment and exposure before interpreting results.
- Campaigns can interfere through shared budgets, overlapping audiences, auctions, automated delivery, and creative rotation. Record these dependencies and select a unit that limits spillover.
- If a platform allocates delivery adaptively rather than randomly, an observed winner may reflect who received more delivery, not only the creative or setting being tested.
- A before/after comparison is exposed to seasonality, promotions, price, inventory, competition, and product changes. Match or model relevant factors and label remaining uncertainty.
- Align event definitions, account time zone, attribution window, reporting date basis, and conversion maturity before comparing variants.

## Analysis Discipline

Plan sample requirements using the outcome type, baseline and variability, unit of randomization, allocation, minimum worthwhile effect, chosen error control, and practical observation window. Do not reuse generic sample tables as if they were calculated for the current account.

At readout, show per-variant exposure and sample, effect size, uncertainty interval, primary metric, guardrails, missingness, and maturity. Distinguish:

- evidence of a difference under the planned analysis;
- whether the effect is large enough to matter to the business;
- whether the experiment identifies a causal effect for the tested population and period.

Do not translate an ad platform's proprietary confidence label into a p-value unless its documented method supports that interpretation. If the plan was underpowered or execution deviated, report the result as inconclusive or exploratory and state what evidence would resolve it.
