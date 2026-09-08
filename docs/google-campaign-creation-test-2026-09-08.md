# Google Ads Campaign 创建能力真实测试记录

测试账号固定为 Google Ads 子账号 `9055507554`，本次只使用该账号，未删除已有资源。

## 结果

| 类型 | Campaign | 下层级 | 状态 |
|---|---:|---|---|
| Performance Max | `24221191602` | AssetGroup `6745721013`，10 个素材关联 | Campaign/AssetGroup `PAUSED` |
| Shopping | `24232139476` | AdGroup `201614104924`，ProductGroup `293946777986` | Campaign/AdGroup `PAUSED`；ProductGroup 状态以 Google 回查为准 |
| App | `24226802801` | AdGroup `199870458893`，AppAd `823804628628` | Campaign/AdGroup `PAUSED`；AppAd `ENABLED` |

## 关键验证

- PMax 通过一个 `customers/{customer_id}/googleAds:mutate` 请求原子创建文本 Asset、AssetGroup 和 AssetGroupAsset 关联，回查覆盖 `HEADLINE`、`LONG_HEADLINE`、`DESCRIPTION`、`MARKETING_IMAGE`、`SQUARE_MARKETING_IMAGE`、`LOGO`、`BUSINESS_NAME`。
- PMax AssetGroup 的有效创建契约要求营销图片、方形营销图片、Logo 和商家名称；缺少这些字段时会在提交前校验或由 Google 返回明确错误，不再生成“看似成功”的结果。
- Shopping 使用 Merchant Center `115791065` 的配置创建，Campaign 和 AdGroup 保持暂停。
- App 使用已存在的暂停 AdGroup 创建文本 AppAd。Google Ads v24 不允许该类 AppAd 关联本身为 `PAUSED`，因此请求暂停时 Provider 实际状态为 `ENABLED`；父 Campaign 和 AdGroup 仍为 `PAUSED`。
- 真实 API 期间没有执行删除操作；读取和回查均限定在 `9055507554`。
