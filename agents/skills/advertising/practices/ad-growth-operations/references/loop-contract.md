# Paid Media Loop Contract

Use this checklist before creating or revising a recurring Agent task.

| Contract item | Required definition |
|---|---|
| Purpose | One business outcome and the decision this check informs |
| Principal and scope | The trusted owner, allowed account/platform scope, and exclusions |
| Inputs | Registered read Tools, fields, report window, timezone, freshness, completeness |
| Cadence | Frequency justified by data refresh, conversion delay, and decision latency |
| Decision condition | Evidence needed to produce HOLD, FIX, TEST, or INVESTIGATE |
| Action level | Read-only report, staged proposal, or explicitly approved bounded write |
| Idempotency | Per-occurrence identity plus business-action dedupe/cooldown where needed |
| Stop conditions | Missing data, unknown scope, incomplete pages, tool failure, policy issue, unknown write outcome |
| Recovery | Read back before retrying any potentially successful write |
| Result | Findings, evidence, coverage gaps, actions staged, and run/task reference |

The scheduler's unique run record prevents treating two occurrences as one execution, but it does not
by itself deduplicate a business action repeated across separate runs. If the loop needs durable
cross-run state and no registered storage capability supplies it, keep the loop read-only.

## Safe Default

```text
read current evidence
  -> validate completeness and maturity
  -> compare against the declared decision condition
  -> report evidence and proposed next step
  -> wait for explicit approval before external mutation
```

Do not treat a missing report row, stale result, failed Tool call, or immature conversion window as a
zero value. Do not pause, scale, or rotate campaigns based only on a single noisy metric.
