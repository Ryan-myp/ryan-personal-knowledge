# Meta Ads 操作清单

## 创建/更新 Preflight

```text
Ad Account scope
  -> Campaign objective / special category
  -> Ad Set budget / schedule / targeting / optimization
  -> Ad identity / creative / tracking
  -> Page, Pixel, Catalog, Product Set, Form dependencies
  -> schema + permission + account whitelist
  -> dry-run + confirmation + idempotency
```

至少保留：账户、对象层级、父级 ID、objective、special ad category、budget mode、
optimization goal、billing event、bid/cost cap、targeting 来源、素材引用和 live/dry-run 状态。

## Insights 检查

- 先锁定对象层级和时间窗口，再选 fields/breakdowns。
- 记录 account timezone、币种、attribution setting、数据拉取时间和分页。
- `actions`/`conversions` 需要说明 action type；不能把所有 action 叠成一个转化数。
- reach/frequency、privacy modeling、事件延迟和 breakdown 限制要在结果中显式说明。

## Pixel/CAPI 检查

- Pixel/CAPI 事件命名、action source、event_time 和 event_id 必须一致。
- user_data 规范化/哈希在 Tool 边界前完成；日志只记录脱敏摘要。
- 联调 test code 与生产配置分离；事件接收成功、去重成功、归因可见是不同状态。

## 失败恢复

创建/更新未知状态先 readback；已存在则转为核对/更新，不重复 create。批量结果逐项保留
成功、失败、重试建议和审计 ID。
