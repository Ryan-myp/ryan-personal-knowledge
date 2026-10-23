# 报告上下文契约

`report_context` 描述了报告 Tool 所请求的内容以及有界响应中包含的内容。它是证据元数据，不能替代提供商账户设置，也不保证提供商没有额外的行。

## 字段

| 字段 | 含义 |
|---|---|
| `provider` | 生成该报告的已注册提供商命名空间 |
| `resource_level` | 报告粒度，例如 campaign、ad group、ad、asset 或 asset-group asset |
| `period.value` | 来自 Tool 输入的显式日期范围/预设值，或该 Tool 使用的提供商默认值 |
| `period.source` | `tool_input` 或 `provider_default`；预设值不会静默转换为具体日期 |
| `account_timezone` | 当账户元数据 Tool 返回时，为该账户时区；否则为 `value: null`，`status: unknown` |
| `account_currency` | 当账户元数据 Tool 返回时，为该账户货币；否则为 `value: null`，`status: unknown` |
| `attribution` | 当已授权的设置/报告 Tool 返回时，为该归因设置；否则为 `value: null`，`status: not_returned_by_tool` |
| `completeness.returned_rows` | 响应负载中的行数 |
| `completeness.row_limit` | Tool 所知的有效有界结果限制 |
| `completeness.may_be_truncated` | 当返回的行数达到有效限制时为 True |
| `completeness.status` | `empty`、`possibly_truncated` 或 `within_limit` |

## 解释

- `empty` 表示提供商针对此请求未返回任何报告行。这并不意味着请求的指标等于零。
- `possibly_truncated` 要求在做出完整性声明之前，缩小日期/资源范围或使用可用的分页路径。
- `within_limit` 仅表示此响应未触及已知的行边界。它不认证数据源的新鲜度、隐私阈值覆盖率或提供商端完整性。
- 除非当前已授权的 Tool 结果提供了这些信息，否则时区、货币和归因设置默认为未知。不要从不同的账户、旧报告或模型记忆中推断它们。
- 可以通过一个针对同一受信任账户范围的独立读取 Tool 来收集账户元数据。如果该查找不可用、失败或模糊不清，请保留未知值。
- 平台归因转化保留其平台特定性。不要将它们加总为去重后的业务总数，也不要将其解释为增量结果。
- 仅当货币已知且一致时，支出和收入才可合并。当账户时区不同时，共享的日期字符串不足以保证一致性。

## 读取项

报告提供商、资源粒度、请求的时期及其来源、返回的行数/限制、截断状态、账户时区/货币、归因设置以及数据新鲜度。将缺失的上下文标记为 Unknown，并说明其如何限制结论。
