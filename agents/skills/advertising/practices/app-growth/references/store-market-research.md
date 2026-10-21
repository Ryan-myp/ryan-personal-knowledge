# App Store 市场研究数据边界

## 可用来源

`public_app_research_app_store_search` 使用 Apple iTunes Search API 的软件目录查询，
不需要本系统保存 Apple Ads 凭证。输入关键词与两位国家代码，最多返回 5 条经筛选的
公开条目，包括应用名、开发者、Seller、Bundle ID、描述、主分类、公开评分/评分数、
版本更新时间、价格、币种和 App Store 页面链接。

`public_app_research_app_store_lookup` 使用同一 API 按一个精确 App Store ID 或 Bundle ID
查询单个公开条目。两个标识必须且只能提供一个；国家代码用于限定商店区域。

接口来源：Apple iTunes Search API
<https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/>

此数据仅适合发现同市场的公开 iOS 应用、比较商店定位与描述表达、形成后续人工审查对象。
国家商店结果和语言应与客户目标市场对齐；无结果不代表该应用不存在，搜索排序也不代表
市场份额。

## 禁止的推断

- 评分、评分数、价格和版本日期不是广告曝光、点击、安装、收入或留存指标。
- Store description 是应用商店页面文案，不等于广告创意、实际投放素材或广告主张证据。
- App Store 搜索结果不覆盖 Google Play，也不代表完整竞品集合。
- API 没有提供的截图、广告素材、安装量、销售额、受众、竞价或 campaign 归因数据不得补猜。
- 商店元数据会变化；报告必须写明查询国家和获取时间，并链接原始商店页面供复核。

## 其他需授权的数据源

广告库、平台分析和商店后台属于不同数据权限边界。Meta Ad Library、TikTok Commercial
Content、Google Trends API 测试计划、GA4、Merchant API 与 Apple Ads API 只有在对应产品
资格、OAuth scope、应用审核及账户授权满足后才能接入。普通网页可见不代表有权调用 API，
不得用页面抓取、未公开端点或复用不匹配 scope 的 token 替代正式授权。接入前要先记录
授权主体、适用国家/广告类别、可用字段、速率限制和数据留存要求。
