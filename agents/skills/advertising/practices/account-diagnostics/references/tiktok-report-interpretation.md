---
reference_scope: [TikTok, Tik Tok]
---

# TikTok 报表解读

本参考只解释当前 Tool 返回的证据，不授予新查询能力。先确认可信
advertiser、日期与时区、币种、`data_status`、`report_context` 和返回
行数；未返回的维度、指标和归因设置都标为 Unknown。

## 当前 Tool 边界

- `tiktok_get_report` 提供有界的 `BASIC` / `AUCTION` 查询，可指定
  `AUCTION_CAMPAIGN`、`AUCTION_ADGROUP` 或 `AUCTION_AD`、
  `dimensions`、`metrics`、日期和 Campaign 过滤。实际维度/指标组合
  仍要经 Provider 校验；不能因为输入接受字符串就声称任意组合有效。
- `tiktok_get_campaign_report` 与 `tiktok_get_adgroup_report` 是另两个
  查询契约。Ad Group 报表需要父 `campaign_id`；不要以同名 Campaign
  推断父级，按可信账户读取资源 ID。
- 当前 Tool 不能保证创意级、商品级或受众级任意 breakdown；
  查询不支持时说明缺口，勿捏造数据。方法背景见 Wiki
  `tiktok-reporting-dimensions-and-budget-diagnostics`。

## 诊断顺序

1. 先核对查询是否成功、是否模拟、范围与日期是否一致；`empty`
   是零行而不是零花费，`possibly_truncated` 要缩小范围或分页。

2. 若花费为零，逐项读取 Campaign / Ad Group / Ad 自身状态，
   区分 Smart+ Ad 的 `operation_status=DISABLE` 与关联 Creative
   的状态；再看审核、排期、预算、定向、素材/身份和事件资格。

3. 若花费上升而业务结果下降，核对事件回传/去重、归因延迟、
   订单或 MMP cohort，并拆解日期、层级和可用版位维度；
   不将不同 objective 的“转化”相加。

4. 输出事实、假设、缺失证据和最小下一次只读查询。未收到
   当前账户的真实报表时，不给出确定的暂停、加预算或疲劳结论。
