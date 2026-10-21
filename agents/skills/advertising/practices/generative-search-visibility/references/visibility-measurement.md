# GEO 可见度测量

## 样本设计

先选能代表真实客户任务的一组提示/查询，避免只搜品牌名：

- **发现**：用户描述问题、需求或品类，但尚未选方案。
- **比较**：用户比较方案、供应商、功能、价格或适用条件。
- **决策**：用户询问某品牌/产品是否适合具体场景。
- **使用与信任**：用户询问证据、限制、风险、替代品或操作方法。

按目标市场保留原始语言和措辞。记录纳入/排除规则，避免结果出来后才挑选有利查询。每次观测至少
记录：系统及界面、查询原文、日期/时间与地区、登录/个性化条件（已知时）、结果/答案链接、
提及与引用证据、来源域名、引用上下文、结果状态和采样人员/方法。

## 分层指标

| 层级 | 例子 | 不应误读为 |
|---|---|---|
| 抓取/资格 | robots、访问响应、已知索引/页面资格证据 | 已有 AI 引用 |
| 答案可见性 | 样本中品牌/产品被提及的比例、正负或错误上下文 | 稳定市场份额或完整全网覆盖 |
| 来源引用 | 自有页面是否被明确引用、被引用页面和上下文 | 页面获得普通搜索排名或引用带来点击 |
| 流量 | 已观测 referral、落地页会话、`utm_source` 等来源标记 | 所有 AI 系统都能提供完整来源 |
| 业务结果 | 经定义的转化、激活、收入和质量 | 单凭归因触点证明增量 |

把分母写清楚，例如“某日期、某市场、固定 30 个查询、2 个系统的 60 次观测”；记录空结果、
访问失败与缺失样本，不能当作未提及。不同系统和个性化会话分开报告，避免把答案频率称作官方
排名。若没有对照组、基线和稳健归因，只报告相关性或观测变化，不宣称 SEO/GEO 改动造成增量。
Google AI Overviews/AI Mode 的网站搜索表现被计入 Search Console Performance 的整体 `Web`
搜索类型；它可用于分析 Google Search 流量，但不是跨平台的 AI 答案/引用数据库。

## 搜索机器人控制

- Google AI Overviews/AI Mode 的站点指南强调既有 SEO 技术资格、搜索政策和有帮助、可靠、以人为先
  的内容；可见资格不保证抓取、收录或展示。
- OpenAI 文档将 `OAI-SearchBot`（搜索发现）与 `GPTBot`（训练用途控制）作为独立 robots.txt
  设置。是否允许各爬虫由站点所有者决定，不能为了提高可见性而擅自修改。
- 页面被拦截可能发生在 robots.txt、认证、CDN/WAF、反机器人、速率限制或渲染层；没有服务端日志
  与授权访问证据时，不断言具体阻断位置。
- 对新的 AI 系统先查该系统的官方站点文档；不要把一家平台的规则泛化成所有系统的要求。

## 官方参考

- Google AI features and your website: https://developers.google.com/search/docs/appearance/ai-features
- Google SEO Starter Guide: https://developers.google.com/search/docs/fundamentals/seo-starter-guide
- OpenAI crawler documentation: https://developers.openai.com/api/docs/bots
- Search Console Search Analytics API: https://developers.google.com/webmaster-tools/v1/searchanalytics/query
- IndexNow documentation: https://www.indexnow.org/documentation

官方参考复核日期：2026-10-21。Search Console API 是需 OAuth 和属性权限的站点搜索数据接口，
不是跨平台 AI 答案引用数据库。IndexNow 是站点所有者证明域名控制权后主动提交 URL 的协议；
提交代表通知已被接收，不代表 URL 一定收录。仅在用户授权、站点控制权与受控写入流程明确后再
考虑 Tool 集成。
