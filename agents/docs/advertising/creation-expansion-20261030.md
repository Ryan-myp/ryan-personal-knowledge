# 三渠道广告工具、蓝图与模板增强

本轮扩展已注册的 Provider Tool 合同和声明式创建配置，未在 Runtime、Parser 或中心
Router 中添加渠道分支。默认 dry_run；账户范围、live、权限、确认、幂等、暂停和审计门禁保留。

## 能力变化

| 渠道 | 工具与参数 | 蓝图与起步模板 |
|---|---|---|
| Meta | `meta_create_lead_ad` 1.6.0 支持 IMAGE / VIDEO、图片 Hash、视频、缩略图 Hash 或 HTTPS 地址；按素材类型组装 link_data / video_data，并保留 Instant Form CTA | `meta.lead_generation` 1.1.0 增加素材、文案与暂停状态；Page 改变后清除旧 Form，素材类型切换后清除不兼容选择；增加图片和视频两个起步预设 |
| Google | 新增 `google_create_demand_gen_ad_group` 1.0.0；Demand Gen 不再发送 Display/Search 类型或默认手动 CPC；旧专属入口同样修正。通用和旧专属 Ad Group 合同升至 1.6.0 | 四种 Demand Gen 蓝图升至 1.1.0，使用专属 Ad Group Tool；移除虚构的 Ad Group type 字段；频道配置可留空使用平台默认 |
| TikTok | Smart+ Ad 合同升至 1.9.0，接受原有 structured creative_list / image_web_uris 能力；图片与轮播不得混入视频，轮播不足两张图片时在素材查询前拒绝 | `tiktok.traffic_video` 3.4.0 提供视频、图片、轮播选择，级联清除旧素材；新增图片、轮播两个流量起步预设 |

Google 频道控制合同同步修正：`channel_config` 为只读字段，不能作为写入输入。
可写的 `channel_strategy` 与 `selected_channels` 二选一；逐项选择时至少启用一个有效频道。
这些检查同时作用于 Tool schema 和 Client，错误不能等到真实 API 请求后才发现。

单独续建 Ad Group 的意图名称也声明在 Provider 元数据中，避免后续对话将 Demand Gen
误选到普通 Search Ad Group。新增意图不需要修改中心路由实现。

Meta 最新 Lead 向导与起步模板预填 `LEAD_GENERATION` / `IMPRESSIONS`，避免继承通用
流量广告默认值后产生初始无效字段。新增模板的表单回归同时检查素材显隐与初始无效字段列表。

## 模板版本与数据

- 当前有33个蓝图 ID，新增6个版本文件，旧版本文件保留。
- 内置模板共有45条版本记录：40条当前目录记录、5条兼容历史记录。其中原有16条账号模板
  的版本和验证声明不变；新增4条不绑定账号的通用起步模板。
- 更新起步预设使用新 key / 新版本。旧预设标记 `catalog_hidden=true`，默认列表隐藏，
  但其原始 ID 仍可读取，避免历史对话引用失效。此标志仅控制目录展示，不改变授权范围。
- 模板的 `ad_format` 是固定蓝图族标识，TikTok 实际素材类型保存在 `ad.ad_format`；
  图片起步模板不会因此错误引用旧的一步图片创建链路。
- 没有数据库 schema 变更，没有覆盖用户创建的模板，也没有改写原有 live 验证账本。
- 老草稿若手工填写了只读的 `channel_config`，需要改用上述可写配置；保留可读版本不等于
  继续接受已确认无效的 Provider 写入字段。
- 测试部署的 live 工具清单增加专属 Demand Gen Ad Group 名称，仍通过原有测试账号白名单、
  权限、确认、幂等和审计；新增批准项本身不触发渠道调用。

## 审计与验证边界

新增 `audit_creation_templates.py`，逐条检查内置模板固定版本、蓝图族、预设字段和必填项，
并检查隐藏的历史版本。该审计只读取数据与已注册 schema，不调用 Provider、不执行广告写入。
`make ad-agent-audit` / `make ad-agent-check` 现在包含完整蓝图和模板审计。

所有新增预设和格式条目均保持 `dry_run_only` 或离线合同口径，不能当成真实创建成功。
TopView、Brand Takeover、Local Services 等仍沿用已声明的缺口或限制；本轮未虚构这些接口。
测试的初始失败用例曾意外使用假凭证发出一次 TikTok 图片查询，返回认证错误；未使用真实
渠道凭证，没有写操作。已增加 HTTP 传输层阻断，后续新增用例不允许真实外连。

## 官方依据

- Google 官方 Demand Gen 创建示例：
  https://github.com/googleads/google-ads-python/blob/1b7e72b9cb185b44dda2f08289180250ff107ca5/examples/advanced_operations/add_demand_gen_campaign.py
- Google Ads v24 AdGroup 类型与 Demand Gen Settings：
  https://github.com/googleapis/googleapis/blob/master/google/ads/googleads/v24/resources/ad_group.proto
  https://github.com/googleapis/googleapis/blob/master/google/ads/googleads/v24/enums/ad_group_type.proto
- Google Ads v24 频道策略枚举：
  https://github.com/googleapis/googleapis/blob/master/google/ads/googleads/v24/enums/demand_gen_channel_strategy.proto
- Meta 官方 LinkData / VideoData 字段：
  https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adcreativelinkdata.py
  https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adcreativevideodata.py

## 失败恢复与回滚

父级已创建、子级失败时继续沿用已有资源 ID，不能重新创建整条层级或宣称外部写入已回滚。
本轮没有新增独立任务执行入口。回滚时须保留被模板引用的新蓝图与对应 Tool，或先迁移引用；
不可通过恢复整库覆盖新会话和用户模板。观察性继续使用既有 Run 事件、调用审计和监控接口。

## 最终验证

- `make ad-agent-check` 通过：3650 项 Python 测试、269 项前端测试，329项 Tool 合同、
  33个最新蓝图及45条内置模板版本记录审计通过。测试部署名单补充后，追加默认安全配置检查通过。
- 新增定向用例30项通过；两个新增独立模块的定向语句覆盖为44/50，88%。
- 增量静态质量检查通过、无新增告警；全仓仍有4994项扫描发现，门禁未通过，未降低阈值。
- 五种新表单在桌面与手机视口检查，共10张截图；无脚本错误或页面横向溢出，浏览器 API 全部阻断。
- 原8766服务已重启，注册355个工具。515个会话、14个用户模板和5个定时任务按 ID 核对无缺失。
  四个新起步模板经 HTTP 目录核验可见，代表性的旧起步模板 ID 仍能读取1.0.0版本。
- 真实渠道创建未验证，未改写既有实测等级。结构化证据：
  `agents/evals/advertising/evidence/creation-expansion-20261030.json`。
