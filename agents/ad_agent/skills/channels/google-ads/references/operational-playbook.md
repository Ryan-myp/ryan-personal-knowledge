# Google Ads 操作清单

## 创建前 Preflight

```text
principal/customer scope
  -> campaign type + objective
  -> parent resource / dynamic IDs
  -> budget + bidding dependencies
  -> ad format schema + asset minimums
  -> Tool permissions + dry-run/live gate
  -> idempotency + readback plan
```

逐项记录：customer、账户币种、Campaign 类型、父级资源、必填字段、动态 lookup 来源、
当前 Tool contract version、是否支持 dry-run、是否支持 live、readback 和失败恢复方式。

## 广告类型检查表

| 类型 | 先确认 | 典型阻塞 |
|---|---|---|
| Search | AdGroup、关键词、匹配类型、RSA 资产、落地页 | 关键词/文案缺失、目标不兼容 |
| Shopping | Merchant Center、feed、商品分组、国家 | 没有商品源或商品集 |
| Video | YouTube 视频 ID、格式、CPV/CPM | 把视频 URL 当资源 ID |
| App | App ID、操作系统、应用目标 | App 设置缺失 |
| PMax | AssetGroup、文本/图片/Logo、final URL | 资产不完整或误走 AdGroup |
| Experiment | 基础 Campaign、流量、时间和指标 | 用 Campaign 更新代替实验生命周期 |

## 报表检查表

- 明确 customer 时区下的日期边界和归因窗口。
- 先确定资源粒度，再选择兼容的 metrics/segments。
- 记录币种、数据延迟、分页、过滤条件和分母。
- 派生 CTR、CPC、CPA、ROAS 时保留计算公式和不可用原因。
- 查询失败区分权限、参数、配额、暂态网络和数据未就绪。

## 变更后回查

写操作即使返回成功也要按当前 Tool 声明的 readback 关系回查；未知状态不得重放。回查结果
要区分请求已接受、资源状态已更新和报表数据尚未反映三种状态。
