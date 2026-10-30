# 三渠道创建能力补齐与验证口径

本轮沿用单 Agent Runtime、已注册 Tool 和版本化 Blueprint，补齐通用预设、字段合同、
版本升级和验证展示。没有新增渠道 Router、第二套执行链路或 Provider 直连入口。

## 目录覆盖

| 渠道 | Provider Tools | 最新 Blueprint | 当前内置模板 | 通用起步预设 |
|---|---:|---:|---:|---:|
| Google Ads | 110 | 14 | 20 | 14 |
| Meta | 81 | 8 | 14 | 10 |
| TikTok | 87 | 9 | 15 | 11 |
| 三渠道合计 | 278 | 31 | 49 | 35 |

每个最新三渠道 Blueprint 都有不绑定账号的起步预设。TikTok Lead 拆分原生表单和
网站表单；Meta Lead 与 TikTok Traffic 保留不同素材类型的入口。目录另保留
2 条 DV360 模板及 5 条隐藏历史记录，因此整个文件为 56 条记录、51 条当前记录。
用户自建模板单独持久化，不包含在这些数量中。

新增的 11 个预设覆盖 Google App、Performance Max、Shopping，Meta App Promotion、
Catalog Sales、网站转化、Traffic，以及 TikTok App Promotion、Lead 原生表单、
Lead 网站表单、Product Sales。仅预填类型、暂停状态及适用的基础配置，不内置账号、
素材 ID、追踪链接或凭证。Google App 的 Ad 按既有合同为 ENABLED，父级仍为 PAUSED。
Google App 明确 MULTI_CHANNEL；Shopping 明确 SHOPPING_PRODUCT_ADS 和可修改的
MAXIMIZE_CLICKS 预设，避免继承普通 Search 默认值。

这些数字表示当前系统的声明式合同覆盖，不代表平台所有广告变体均可 live 创建。
现有 Google Local Services/旧 Expanded Text、TikTok TopView/Brand Takeover 等
限制没有伪装成可用能力。Google 账号资源、TikTok 商品选择与 Lead Ad 等实测缺口
仍需在具备前置资源、授权和明确测试计划后验证。

## 字段合同

TikTok `tiktok_smart_plus_create_ad` 合同从 1.9.0 升到 2.0.0：

- `music_info` 及 creative_list 中对应对象明确包含 `music_id`。
- `ad_configuration` 增加 `product_ids`、`product_display_field_list`、
  `catalog_creative_toggle` 和 `utm_params`。
- 删除无有效子字段定义的 `product_info`、`catalog_creative_info` 占位入口。
  Client 对旧别名在 HTTP 前拒绝，并说明应使用的配置字段，不默默丢弃。
- 集合和字符串有应用侧大小限制，UTM 项必须同时提供 key/value；这些是本系统的
  有界输入约束，不宣称是 TikTok 官方最大值或可选性要求。
- 音乐 ID 和商品字段有人工录入来源说明；没有凭空宣称存在音乐或商品字段查询接口。

依据为 TikTok 官方 SDK 的三个模型文档：

- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/SmartPlusAdCreateBodyCreativeInfoMusicInfo.md
- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/SmartPlusAdCreateBodyAdConfiguration.md
- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/SmartPlusAdCreateBodyAdConfigurationUtmParams.md

创建审计现在阻断缺少通用预设、不可用的结构化占位字段、无效预设值及合并默认值后的
参数冲突。6 处原有结构化占位缺口归零；11 处有明确人工来源的高级开放 payload
继续保留高级编辑入口，不猜测未确认的子字段。

## 验证与版本

`CreationVerificationCatalog` 只读取已有两份实测账本，不重写原始证据。按渠道、账号、
模板 key、Blueprint ID/version 和参数 SHA256 精确匹配；仅历史版本记录不能证明
当前模板通过。即使上层声明已验证，操作列表中有 not_run、失败或未知状态时，也不能
显示为完整通过。用户副本和通用预设不继承实测状态。读取证据失败时按未验证展示。

模板详情及向导的“参数概览与说明”显示可折叠的验证记录。记录只对应保存的参数，
不授予权限，也不证明当前编辑值或全部广告类型通过。

新增接口：

| 接口 | 权限 | 行为 |
|---|---|---|
| `GET /creation-blueprints/{id}?version=...` | `ads.read` | 读取精确版本；不存在返回 404，不回退到最新版 |
| `POST /creation-templates/{id}/upgrade-preview` | `ads.plan` | 只读比较，返回新增/删除/变化/缺失/无效字段和独立草稿 |

身份来自可信 principal；模板升级预览校验租户、用户和账号范围。升级必须另存新模板，
PATCH 不能原地换版本；新副本不继承 ID、默认模板标志或验证证据。对象/数组参数使用
注册 Tool schema 校验，仍保留原值供修正。资源选择凭据清空，提交仍重新走原有门禁。

模板查看、编辑和刷新均保持固定版本。快速切换时丢弃过期响应，字段评估不再取消正常
模板加载；升级副本打开保存面板时保留建议名称及原有说明。

## 安全、恢复与回滚

- 默认 dry_run；测试账号读写、其余账号只读的配置不变。live 开关、权限、账号范围、
  确认、幂等、审计和暂停约束未放宽。
- 无数据库 schema 变更，不迁移或覆盖用户模板、会话、定时任务，不改写历史验证账本。
- 升级预览和读取失败不落库；用户可返回原模板继续使用或修正升级副本。
- 旧占位字段无法迁移为真实 API 字段，需按新合同重填；不能自动推测商品资源。
- 回滚只回滚本轮代码与目录，不恢复整库。保留已被用户模板引用的 Blueprint 版本；
  不应通过降级重新开放已确认无效的字段。
- 沿用既有运行审计和错误接口，本轮无需新增观察性基础设施。

## 验证记录

验证只使用内存库、模拟 HTTP 和阻断外网的测试环境；浏览器 API 全部由离线 fixture
响应，未调用广告或模型接口。

- `make ad-agent-check` 最终通过：3716 项 Python 测试、278 项前端测试；编译、
  329 个 Tool 合同快照、创建能力审计、知识库质量检查和 `git diff --check` 全部通过。
- 三个新增核心模块的定向语句覆盖率为 92%（157/171）；34 项定向用例通过。
- 桌面 1440px、手机 390px 的升级预览、验证折叠和音乐字段输入检查通过，共 6 张截图；
  无页面脚本错误或横向溢出。浏览器没有请求真实 Provider 或模型。
- 全仓 qguard 扫描仍有 4988 项既有发现，门禁未通过；本轮增量扫描无新增告警，
  未降低阈值，也没有把增量通过误称为全仓通过。
- 原服务已按同一配置、同一数据库重启并监听 `0.0.0.0:8766`，健康检查通过。
  516 个会话、14 个用户模板、5 个定时任务的数量和完整 ID 集合重启前后相同。
- 原服务 HTTP 检查确认：33 个蓝图、49 个当前可见内置模板、35 个通用预设、
  355 个注册工具；Smart+ Ad 合同为 2.0.0，旧 Meta Lead 1.0.0 可读取并预览升级到
  1.1.0。检查没有保存用户模板或触发广告执行。

结构化结果：`agents/evals/advertising/evidence/creation-completion-20261030.json`。
