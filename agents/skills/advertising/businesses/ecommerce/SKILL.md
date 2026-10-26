---
business:
  name: ecommerce
  version: "1.1.0"
  description: "电商广告增长：商品源、利润口径、转化信号与跨渠道投放诊断"
  business_rules:
    focus_metrics: [Contribution_Margin, ROAS, CAC, Refund_Rate]
---

# 电商业务技能

本 Skill 指导电商广告的规划和诊断，不是渠道白名单或平台参数目录。
Google Shopping/PMax、Meta Catalog、TikTok Product Sales 等场景须分别核对
当前 Registry、蓝图、Tool schema、账户资格和素材/商品前置资源；
能查询父级不代表能创建 Ad，更不代表可以启用投放。DV360 等渠道是否适用
由业务目标和当前可用工具决定，不因业务名称自动禁止。

## 决策顺序

1. 明确目标：新客贡献利润、复购、库存周转或短期收入；确认订单、退款、
   税费、物流与优惠券的归属，避免只以平台 ROAS 判断真实收益。
2. 核对商品身份链：Feed/Catalog、商品 ID、价格、库存、落地页和地区是否一致；
   Product Set 等动态资源必须按账户只读查询，不凭名称或历史模板猜 ID。
3. 选择渠道与目标：比较需求意图、素材供给、商品资格和转化事件质量；
   使用对应渠道当前的原生 Campaign 类型及其父子层级，不使用跨平台通用枚举。
4. 拆解数据：区分曝光、点击、到站、加购、购买、退款和复购；
   平台归因收入、实际订单与增量结果分别呈现，注明窗口、币种及数据成熟度。
5. 提议动作：给出当前证据、待验证假设、最小测试、保护指标和回退条件。
   改预算、换商品集或创建广告都只能交由注册 Tool，默认 dry-run。

## 常见场景

- 新品：先确认 Feed 上架资格、页面库存与价格、广告素材承诺、转化回传；
  再根据市场与账户能力确定 Search、Shopping、Catalog 或 Product Sales 路径。
- 促销：明确毛利和可承受 CAC、活动日期与结算窗口；不套统一预算倍数。
- 再营销：确认受众来源、隐私授权、排除购买用户的规则和事件延迟；
  没有有效数据源时只输出方案，不伪称已创建 Audience。

## 当前测试记忆与边界

TikTok Product Sales 测试账号已完成暂停 Campaign 和 Ad Group 的创建、
更新与回读；Ad 被 Provider 以 `Invalid product selection` 拒绝，
对应 Catalog 的 Product Set 只读结果为空。不能把这一案例说成
“TikTok 电商不支持”，也不能把父级通过说成全层级成功。
恢复时先读取 `provider-live-e2e-memory` 和当前机器账本，仅续建缺失子级；
本 Skill 不授权写 Catalog/Product Set。

预算没有跨账户、跨币种的固定人民币下限。币种、最低预算、格式、目标和
可修改字段以当前 Tool schema、账户/地区校验及 Provider 返回为准；
真实写入仍需权限、测试白名单、确认、幂等和审计。
