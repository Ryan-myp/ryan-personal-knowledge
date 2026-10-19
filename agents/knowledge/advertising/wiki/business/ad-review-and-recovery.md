---
schema_version: "1"
id: cross-platform-ad-review-and-recovery
title: 跨平台广告审核、拒登诊断与恢复手册
layer: business
knowledge_type: workflow
category: compliance
subcategory: ad-review-and-recovery
platform: all
source: Google Ads Help、Meta Blueprint、TikTok for Business、Display & Video 360 Help
source_ref: "https://support.google.com/google-ads/answer/9338593?hl=en"
version: "1.0.0"
confidence: 0.9
updated_at: "2026-10-19"
tags: [review, disapproval, rejected-ad, appeal, creative-policy, landing-page, recovery]
status: published
source_kind: "official"
authority: "official"
evidence_level: "reviewed"
last_verified_at: "2026-10-19"
---

# 跨平台广告审核、拒登诊断与恢复手册

本手册用于把审核异常转成可核查、可恢复的处理流程，不替代当前平台政策、账户页面或 Tool schema。政策和审核入口会变化；每次处理时都要读取当前对象的状态与平台给出的具体理由，不能仅凭本页推断合规或保证获批。

## 先分清发生了什么

“广告没投出去”不等于“广告被拒登”。先识别对象、审核阶段和影响范围，再选动作。

| 观测状态 | 含义与下一步 |
|---|---|
| Pending / In review | 审核尚未结束。读取对象当前状态和平台预计处理信息；不要把等待误判成拒登，也不要重复创建相同对象。 |
| Approved / Eligible / Servable | 某个审核层级已通过或具备资格，不代表预算、排期、父级状态、库存、受众和追踪都正常，也不保证实际交付。 |
| Limited / Eligible (limited) | 可能存在政策、地域、格式或投放面限制。读取具体标签和适用范围，不把“有限制”简化为通过或拒绝。 |
| Disapproved / Rejected | 找到平台政策标签和具体原因，确认问题属于素材、文案、落地页、商品/行业资格还是配置；按证据修复或提出有依据的复核。 |
| Account / business / asset restriction | 影响范围可能超过单条广告。单条广告编辑不能解除账户或业务资产限制；到当前官方支持入口核对受限主体和可用复核选项。 |
| Exchange / publisher rejection | 在 DV360 等有下游库存方审核的平台，拒绝可能来自某个 Exchange/Publisher，而不是 DV360 自身审核。必须分别检查状态与受影响的库存。 |
| API / query error | 接口错误、权限失败或状态查询失败不是政策判定。保留错误类别并修复查询/权限问题，不能据此建议申诉。 |

同一对象可能同时有多个状态。每次记录 Campaign、Ad Group/Ad Set、Ad、Creative、素材或账户/资产的稳定 ID，以及父级关系；名称不能作为唯一标识。

## 诊断顺序

1. **确定范围**：读取广告、素材、父级和账户/业务资产状态，确认是单条、一个组、一个广告系列还是账户级限制。
2. **保存证据**：记录平台返回的原始政策标签与说明、对象 ID、状态、发生时间、地区/目标市场、文案和素材版本、最终落地页，以及相关 API 错误类别。保存前移除令牌、密钥和不必要的个人信息。
3. **核对受影响组件**：检查广告文案、图片/视频/音频、身份或商品、定向、CTA、追踪参数、最终 URL、重定向和落地页实际内容。不能只检查广告正文而忽略目的地。
4. **对照当前政策**：按平台、产品/行业、目标地区、格式和限制条件查阅当前官方政策。对受监管行业、个人属性、健康/金融承诺、授权或免责声明等高风险内容，缺证据时升级人工复核。
5. **选择恢复路径**：确认有违规则修复具体原因并按平台要求重新审核；有证据认为判定错误时才申请复核。账户级限制走账户/业务资产支持路径。
6. **回读验收**：重新读取审核状态、父级状态、有效地区/库存、预算和排期，再检查是否开始交付及报告是否出现。保存修复版本、复核结果和后续观察结果。

### 素材与落地页 Preflight

| 检查项 | 核对内容 |
|---|---|
| 一致性 | 广告承诺、图片/视频、标题、价格/优惠、CTA 与落地页实际商品和条件一致；价格、期限、资格、附加费用等限制清楚呈现。 |
| 可访问性 | URL 可打开、移动端可用、跳转目标正确，重定向链稳定；检查证书、区域访问、页面错误、登录墙和平台抓取可见性。 |
| 真实性与证据 | 效果、排名、对比、客户评价和收益承诺有可验证依据；避免绝对化、误导性或无法证明的表达。 |
| 身份与权利 | 品牌、音乐、人物、UGC、商标、社交账号和商品使用有适当授权；不把素材上传成功当成拥有广告使用权。 |
| 地区与资格 | 产品/服务、许可、免责声明、年龄条件、特殊广告类别和目标市场要求按地区核实。不能通过改写名称、拆分对象或换账户绕过政策。 |

Preflight 是排查清单，不是自动合规认证。若无法确认具体政策适用，明确标为待核实，不承诺审核通过。

## 修复还是申诉

| 证据情况 | 推荐路径 | 不应做的事 |
|---|---|---|
| 拒登理由明确，素材、文案或落地页确有问题 | 修复被指出的内容，检查关联页面和素材，再按平台流程提交审核 | 只反复点申诉，不改实际违规内容 |
| 平台理由与实际内容明显不符，且有文档、许可、页面或产品证据 | 保存证据并针对具体政策点申请复核；说明判定与事实的差异 | 使用泛化申诉文案，重复提交同一事件 |
| 理由不完整或对象范围不清 | 先读取更多详情、政策标签、通知及受影响对象；必要时向官方支持询问 | 猜原因后批量改素材或暂停大量无关对象 |
| 账户、业务资产或身份受限 | 按限制主体的官方流程处理，核对账户安全、验证和关联资产问题 | 仅编辑一条广告，或创建新账户规避限制 |
| 状态未知、查询失败、写入超时 | 先修复查询或通过稳定 ID 回读，确认状态后再采取动作 | 重复创建、重复申诉或假设请求已经失败 |

申诉不是规避政策的手段。保留原对象及其 ID，避免通过重复创建、微小改名、换身份或隐藏落地页来绕过审核。平台对重复申诉、可申诉次数和审核时长可能有不同限制，应以当下账户界面和官方文档为准。

## 四个平台的审核差异

### Google Ads

- 从 Ads/Assets 状态及 Policy details 查具体标签；Google 官方流程指出，拒登可能来自广告、资产或 destination。
- 修复广告或目的地后保存，平台会重新审核；只有认为初始判定错误时才选择 dispute/appeal。
- 如复核失败或被判为重复，不要机械重复提交；重新核对政策、素材和最终 URL，并读取当前 Policy Manager 的结果。

### Meta Ads

- 先在 Ads Manager 的 Delivery/status 信息里确认对象状态，分别检查文案、视觉素材和落地页。
- 如果确实违反标准，先修复广告和页面；若有依据认为拒绝错误，通过当前 Business Support/账户质量入口查看是否提供复核。
- 单条广告拒绝与 Ad Account、Page、Business 等资产限制是不同问题，分别确认限制对象和影响范围。支持界面名称或入口可能变化，以 Meta 当前界面为准。

### TikTok Ads

- 从 Campaign 中对应 Ad/Ad Group 的拒登详情读取理由，再决定编辑后重审或提出复核。
- TikTok 当前 One Click Appeal 文档说明：在 Ad 或 Ad Group 层提交可能触发整个 Ad Group 重审；提交后审核期间不能编辑该组/广告。提交前检查整个组并保留版本。
- 若账户暂停，当前文档说明需先解除账户暂停才能提交该流程的申诉；入口和资格以当前账户显示为准。

### Display & Video 360

- 在 Creative status 中分别读取 DV360 status 与 Exchange status；下游 Exchange 可执行自己的审核，所以某个 Exchange 拒绝不应被描述成所有库存都拒绝。
- 通过拒登详情定位是内容/格式/目的地问题、Campaign Manager 360 placement/tag 配置，还是 Exchange/Publisher 要求。
- 在 DV360 内修复的 Creative 通常会重新提交审核；在外部 Campaign Manager 360 修复后，可能还需重新提交或触发同步/复审。需回读两类状态与具体投放库存。

## 恢复验收与复盘

审核状态解除后，按以下顺序验收，不能把“获批”当作“已投放”：

1. 拒登/限制标签已清除，且对应审核层级与目标地区/库存符合预期。
2. Campaign 与 Ad Group/Ad Set 的状态、排期、预算、账户权限和父子关联符合计划。
3. 素材、身份、商品/落地页、像素或转化事件可用；追踪参数没有在修复中丢失。
4. 若平台有 Exchange/Publisher 审核，读取具体目标库存状态；如果只在部分库存可用，要明确写出范围。
5. 在合理的数据刷新窗口后查询实际交付和报表；没量时回到资格、预算、竞价、定向、素材和数据链路诊断，不再把已解决的审核问题当作唯一原因。
6. 记录原始原因、采取的修复、复核结果、受影响对象和验证时间。对之后同类问题沉淀可复用的“证据—修复—结果”，不把单一案例升级成跨账户政策结论。

## Agent 回复格式

```text
对象与范围：平台、稳定 ID、对象层级、受影响地区/库存
当前状态：审核中 / 受限 / 拒登 / 查询失败 / 已恢复
平台给出的理由：原始标签与解释；没有证据时标“未确认”
证据缺口：需要读取的字段、页面或平台支持信息
建议路径：修复 / 复核 / 账户支持 / 查询恢复
验收条件：应回读的状态、投放范围、交付与报告
风险边界：是否可能触发重新审核、影响父级或锁定进一步编辑
```

不要声称已申诉、已修复或已恢复，除非对应工具调用和线上回读都提供了证据。实际写操作仍须遵守当前 Tool 权限、确认、幂等和审计要求。

各链接的页面入口和细则可能更新；本页核验日期为 2026-10-19。审核耗时、政策枚举和申诉限额不在此固化为跨平台承诺。

## 官方参考

- [Google Ads：Fix a disapproved ad or appeal a policy decision](https://support.google.com/google-ads/answer/9338593?hl=en)
- [Meta Blueprint：Understanding Meta Advertising Standards，How to troubleshoot ad rejections](https://storage.googleapis.com/understanding_meta_advertising_standards/Understanding_Meta_Advertising_Standards.pdf)
- [TikTok for Business：What to do if your ad or ad group was rejected](https://ads.tiktok.com/resources/help/article/what-to-do-if-your-ad-or-ad-group-was-rejected-on-tiktok)
- [TikTok for Business：Appeal rejected ad with One Click Appeal for Other Ad Types](https://ads.tiktok.com/resources/help/article/one-click-appeal-for-other-ad-types?lang=en)
- [Display & Video 360：Find and fix rejected creatives](https://support.google.com/displayvideo/answer/12726387?hl=en)
- [Display & Video 360：About the creative review process](https://support.google.com/displayvideo/answer/6063030?hl=en)
