---
business:
  name: app
  version: "1.1.0"
  description: "App acquisition and post-install growth guidance"
  business_rules:
    focus_metrics:
      - CPI
      - Activation
      - Retention
      - LTV
---

# App 业务技能

渠道和广告类型不在此 Skill 中静态白名单化。每次以当前 Registry、广告蓝图、
Tool schema、账户可用资产与 API 实际结果判断；不同渠道的 App 目标和平台原生
`campaign_type` 不是同一字段，不能用一个通用 campaign type 列表阻止合法场景。
预算按用户目标、账户币种、可承受获客成本和当前 Tool 约束校验，不套固定金额范围。

## 常用场景

- **应用获取**：按当前渠道能力与账户资格选择安装、应用推广或对应优化目标。
- **安装后激活**：先验证 `first_open`、注册、教程完成等事件的定义、去重和回传质量。
- **留存与价值**：结合 cohort、退款/订阅、广告变现和 LTV 证据评估用户质量，不以 CPI 单独判定素材或渠道胜负。
- **商店转化**：检查广告承诺与 App Store / Google Play 页面信息、截图、视频及地区版本是否一致。

## 工具发现

本业务 Skill 不维护固定 Tool 名称。运行时会根据已注册 Tool Source 发布的
App 广告类型目录和 Tool Schema 动态选择可用的查询、Campaign、素材、出价与报表能力。
没有 App Store / Google Play 页面或 MMP/CRM 数据 Tool 时，只能分析用户提供的页面、
报表或资料，不能声称已读取商店、安装后 cohort 或收入数据。

## 注意

- 本 Skill 提供策略和分析方法，不增加平台权限、账户范围、API 支持或写入能力。
- 新建、更新或暂停广告仍需使用当前注册的 Tool，并服从执行模式、确认、幂等和审计门禁。
- 事件、商店审核规则、可修改字段和优化目标可能随平台及版本变化；使用当下 Tool schema 和官方资料核对。
