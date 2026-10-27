# Campaign hierarchy acceptance, 2026-10-27

## Scope and evidence

- Sequential live E2E through the isolated `/chat` service on `127.0.0.1:8896`; the shared `8766` service was not modified. The test accounts were Google `7574609568`, Meta `2806375919473667`, and TikTok `7397068114548195329`.
- Only Campaign and delivery descendants were eligible for live writes. Other resource checks were reads. Every new Campaign, Ad Group/Ad Set, and Ad was paused (`PAUSED` or `DISABLE`). TikTok creative material itself may be `ENABLE` while all delivery parents and the Ad remain `DISABLE`.
- Local redacted evidence: `outputs/campaign-acceptance-20261027/{cases,provider-http.jsonl,report.json}`. A response or dry-run alone is not a live-write pass: inspect the provider request and subsequent ID readback. Older failed retries remain in the report for diagnosis.

## Current-run result

| Provider | Type | Campaign | Child | Ad | Update/readback |
| --- | --- | --- | --- | --- | --- |
| Google | Shopping | Existing `22121309651` read | Existing `176264241591` read | Existing Ad read | No new write. `google_create_campaign` requires writing a separate CampaignBudget; forbidden by the other-resources-read-only scope. |
| Meta | Traffic | New `120252081636100251`, paused, read | New Ad Set `120252081666680251`, paused, read | New Ad `120252081785900251`, paused, read | Campaign, Ad Set, and Ad names updated live and verified by later ID reads. The initial Campaign turn attempted a duplicate write after a successful provider create; the duplicate was rejected. |
| TikTok | Traffic | New `1880175223694369`, `DISABLE`, read | New Smart+ Ad Group `1880176062367185`, `DISABLE`, read | New Smart+ Ad `1880176502590609`, `DISABLE`, read | All three names updated live and verified by later ID reads. The first Ad media combination failed provider validation (40002); the subsequent attempt used an existing verified video/cover/identity/CTA combination. |

Google PMax and App, Meta Catalog Sales/Conversion/App Promotion, and TikTok Product Sales/App Promotion were **not re-created and updated in this run**. Prior ledger claims are historical evidence, not current-run passes. TikTok Lead is intentionally outside the requested scope.

Representative non-hierarchy live reads: Google CampaignBudget and Asset; Meta image library; TikTok video, image, and identity libraries. No writes were made to these resource types. The report contains 47 attempts, 34 individually verified Tool cases, including old failures and recovery attempts; this is not a percentage of supported ad types.

## Fixes and remaining work

- An explicit singleton Tool allowlist with Tool-named `platform_params` now builds arguments from those exact submitted values through the existing InputBuilder and selection-proof checks. This fixes model omission of TikTok's `objective_type` and Meta confirmation-turn parameter drift; the original schema, account scope, approval fingerprint, idempotency, and audit gates remain in force. Normal natural-language requests without such structured values are unchanged.
- The E2E report now resolves Tool-named nested parameters for update ID matching and readback field comparison.
- Google live creation needs an explicitly approved policy for a fresh CampaignBudget as a dependent Campaign resource, or an approved isolated budget strategy. Do not attach another Campaign's budget or silently broaden the write scope.
- Run each remaining ad type as a separate, low-rate, paused hierarchy against the same test accounts, then update/read by ID. Reconcile any ambiguous partial write before retrying. A generic provider error with no created ID is a failed attempt, not a successful Ad.
- The local regression suite does not call provider APIs. For rollback, revert the argument resolver and report normalization changes; existing provider resources are not automatically deleted. The audit/run trace fields are already present; no new observability integration is required.

## Continued acceptance: one type at a time

The follow-up run used the same isolated `8896` service and the same confirmed
accounts. Its redacted evidence is in
`outputs/campaign-acceptance-20261027-c/`. A new ID, successful Provider
transport, exact-ID readback and paused delivery status are required for a
create pass. An update additionally requires the requested field to match a
later readback. The Google Shopping CampaignBudget was created only as an
atomic dependency of its Campaign; there were no independent writes to
non-hierarchy resources or deletes.

| Channel and type | Live hierarchy | Update and readback | Verdict |
| --- | --- | --- | --- |
| Google Shopping | Campaign `24400901432`, Ad Group `205279468207`, Product Group `293946777986`, Ad `205279468207~829735494206` created and read | Campaign/Ad Group names and Ad pause passed; Product Group CPC changed from 100000 to 110000 micros, but a requested status pause still read `ENABLED` | **Partial**: Product Group status update fails functional readback |
| Google Performance Max | Existing Campaign `24175343007`, Asset Group `6742831520`, assets and seven listing filters read | New paused Campaign rejected with `resourceCountLimitExceededError`; no new hierarchy or update | **Blocked by account resource limit** |
| Google App | Campaign `24406663615` and Ad Group `198765160022` read `PAUSED`; App Ad `198765160022~829612685502` read `ENABLED` as required by Google, while paused parents prevent delivery | Parent names updated and read back; immutable App Ad replacement rejected by account resource limit | **Partial**: create/read and parent updates pass, creative replacement blocked |
| Meta Traffic | Campaign `120252081636100251`, Ad Set `120252081666680251`, Ad `120252081785900251` created and read `PAUSED` in the earlier same-day run | Three names updated and read back; initial duplicate write was rejected by the idempotency gate | **Passed with a duplicate-call defect recorded** |
| Meta Catalog Sales | Campaign `120252082582460251`, Ad Set `120252082613270251`, Ad `120252082630330251` created and read `PAUSED`; Ad Set product set binding was read back | All three names and paused statuses updated and read back | **Passed** |
| Meta Conversion | Campaign `120252082726550251`, Ad Set `120252082752740251`, Ad `120252082828630251` created and read `PAUSED` using Pixel `815121266900148` | All three names and paused statuses updated and read back | **Passed with defects**: Campaign turn attempted a duplicate write; first Ad Set turn claimed creation without a Tool call or Provider request; fresh session recovered |
| Meta App Promotion | Campaign `120252082934500251`, Ad Set `120252082956030251`, Ad `120252082975070251` created and read `PAUSED` using App `1574354049466790` | All three names and paused statuses updated and read back | **Passed** |
| TikTok Traffic | Campaign `1880175223694369`, Ad Group `1880176062367185`, Ad `1880176502590609` created and read `DISABLE` in the earlier same-day run | Campaign/Ad Group names and Ad status updated and read back after replacing a Provider-rejected media combination | **Passed with a recovered creative validation failure** |
| TikTok Product Sales | Existing Campaign `1880083317565154` and Ad Group `1880083336090337` re-read `DISABLE` | Catalog `7598491157655570192` returned zero Product Sets; previous Ad attempt was rejected as `Invalid product selection`; no new orphan hierarchy created | **Blocked by test-account product selection** |
| TikTok App Promotion | Campaign `1880183882927122`, Ad Group `1880183904410818`, Ad `1880183882931474` created from the template and read `DISABLE` | Parent names updated and read back; Ad status update to `DISABLE` read back. Ad text/name are not supported by the Ad update contract | **Passed for supported updates**; synthetic MMP URLs remain demo-only |

The first TikTok App template turn miscopied `ad-site-i18n-sg/...` as
`ad-site-i8n-sg/...` and reported a false permission error. An exact-ID image
read succeeded; explicitly supplying the unchanged template image ID in
structured input let the second template turn create all three paused levels.
The first Meta Pixel default get also failed with `#200` because its default
field set included `owner_ad_account`; a minimal-field read worked. The default
now uses the account-scoped basic fields and the original Pixel ID was
successfully re-read.

## Other channel read Tools

The fixed, serial, test-account-only read suite recorded:

| Channel | Fixed suite | Additional exact-resource reads |
| --- | --- | --- |
| Google `7574609568` | 27 passed, one failed initially, seven skipped; `google_get_experiment` was corrected and passed a separate live retry | Asset Group and asset/filter tree, four report/idea Tools and Keyword Planner read passed |
| Meta `2806375919473667` | 22 passed, one failed, 12 skipped | App, image/video library and Catalog Product Set reads passed. `meta_list_lead_forms` requires a Page Access Token and remains blocked |
| TikTok `7397068114548195329` | 33 passed, zero failed, ten skipped | CTA recommendations, portfolio list and exact App image read passed |

The fixed suite intentionally skips sensitive-data or out-of-scope reads, and
some detail reads have no test-account parent ID. A skipped Tool is not a pass.
The separate live retries are in the `cases/` directory; the original suite
snapshot retains its original failed result, rather than silently rewriting
history. Meta briefly returned upstream `504` on account and campaign reads;
the scan was stopped and resumed as a single-request-per-Tool channel run.
These counts are Tool cases, not a percentage of advertising types.

Reconciled against the registered channel READ Tools (fixed suite plus
individually verified chat cases, including the earlier same-day Traffic
cases), unique Tool coverage is Google **36/39**, Meta **26/36**, and TikTok
**36/45**. Google's remaining three are user-list or manager-scope reads.
Meta's ten include audiences/leads/business/account-list scope, the
Page-Token-blocked Lead Form list, and detail reads without a safe source ID.
TikTok's nine include audience/identity reads and details without Pixel,
Product Set or Creative Portfolio IDs. None of these 22 are silently counted
as passed.

The changed contract surfaces are limited to Meta Pixel default read fields,
Google Experiment GAQL fields, and the isolated E2E guard for a scoped
Keyword Planner read POST. The latter does not relax any write gate. Failed
creates are never retried without reconciling Provider IDs first; rerun only
missing children, not the full hierarchy. Code rollback does not undo
already-created paused test resources. Existing run/turn and Provider transport
evidence is sufficient for this acceptance; no new observability integration
is needed for these fixes.
