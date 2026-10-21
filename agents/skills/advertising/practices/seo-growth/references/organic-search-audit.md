# 自然搜索审计检查表

按页面类型抽样并保留 URL、取样方法、日期和证据；发现必须能回到实际页面、代码、日志或数据。

## 抓取与索引

- 页面是否返回预期 HTTP 状态，重定向目标是否稳定且最终 URL 正确？
- robots.txt、页面级 `noindex`、响应头和登录/地区/同意墙是否阻止目标搜索引擎访问？
- canonical 是否指向预期规范页；内部链接、站点地图与 canonical 是否一致？
- 重要页面是否能从可抓取的内部链接到达；是否存在孤立页、分页、参数 URL 或重复版本？
- 客户端渲染后是否存在主要文本、链接和元数据？仅凭源码或搜索摘要无法确认渲染结果。
- 迁移/URL 变更是否保留对应重定向、规范关系和重要入口？不得只凭流量变化猜测迁移故障。

## 内容与页面关系

- 每类页面服务哪个明确用户任务、查询意图和阶段？是否有真实的一手信息、经验或可信证据？
- 标题、摘要、正文与页面承诺是否一致？答案是否清晰、完整且不隐藏关键条件？
- 多个 URL 是否在回答近似意图；是否需要整合、区分或建立清晰的主题/分类结构？
- 作者、更新时间、来源、产品细节和商业主张是否准确？过期内容是否有实际更新理由？
- 结构化数据是否与用户可见页面一致并遵守对应类型的官方规范？标记本身不保证搜索展示。

## 查询与效果

- Search Console 数据要记录：property、search type、日期范围、时区、query/page/device/country
  等维度、筛选、aggregation、数据状态和返回行/分页完整度。
- 观察 clicks、impressions、CTR 和 average position 的变化时，同时检查查询/页面组合、品牌与非品牌、
  设备、地区、季节性和数据延迟；平均位置不是每位用户看到的固定排名。
- Search Console 的搜索表现数据不能单独证明增量、转化质量或收入；需要授权的分析/CRM/业务结果数据。
- 关键词规划器中的广告竞争指数和 bid estimate 不是自然搜索难度、排名概率或实际自然访问量。

## 发现记录格式

| 级别 | 证据与范围 | 发现/假设 | 置信度 | 建议 | 验证/回归检查 |
|---|---|---|---|---|---|
| Blocker / High / Medium / Low | URL、数据窗、来源及限制 | 区分直接观察与可能原因 | 高 / 中 / 低 | 写出具体、可逆或分阶段的动作 | 明确复查数据和成功条件 |

优先级同时考虑影响范围、证据置信度、实现成本和是否阻断抓取/索引。缺少证据时降级为
待验证问题，不用固定行业阈值或保证性排名作结论。

## 官方参考

- Google SEO Starter Guide: https://developers.google.com/search/docs/fundamentals/seo-starter-guide
- Google Search developer guide: https://developers.google.com/search/docs/fundamentals/get-started-developers
- PageSpeed Insights API: https://developers.google.com/speed/docs/insights/v5/get-started
- Search Console Search Analytics API: https://developers.google.com/webmaster-tools/v1/searchanalytics/query
- Search Console API prerequisites: https://developers.google.com/webmaster-tools/v1/prereqs

Search Console API 的站点数据需要 OAuth 2.0 与对应属性权限；返回结果有平台数据范围限制，
不能假定一次请求就是完整数据集。PageSpeed Insights API 可用于按需测量单个公开 URL；
官方文档允许请求不带 key，但匿名配额仍可能限流；服务支持用 `GOOGLE_PAGESPEED_API_KEY`
配置限制到 PageSpeed Insights API 的 key。频繁自动化应使用 key 并遵守配额。它不提供搜索查询/
排名数据，也不等于完整站点爬取；API 文档已说明未来计划停止将 CrUX 字段数据整合在 PSI
响应中，因此依赖现场用户体验数据时应接入独立的 CrUX API（需要 API key）或其他授权来源。
