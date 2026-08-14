# DV360 集成模式与最佳实践（与其他 GMP 工具集成 / API 设计模式）

> **领域**: 广告投放 / 系统集成
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, integration, gmp, api-design, google-ads, campaign-manager, bigquery
> **更新时间**: 2026-08-14
> **类型**: 深度文档

---

> **文档定位**：本文以「系统集成」为核心视角，聚焦 DV360（Display & Video 360）如何与 Google Marketing Platform（GMP）家族其它产品——Google Ads、Campaign Manager 360（CM360）、Search Ads 360（SA360）、Google Ad Manager（GAM）、BigQuery、Ads Data Hub（ADH）——协作，并系统讲解 DV360 API 的设计模式（资源层级、分页 Token、字段选择、限流配额、重试退避、幂等与批次、Webhook 事件通知）。与已有的《dv360-marketing-api-deep.md》（API 端点实战与认证授权）、《dv360-architecture-deep.md》（账户架构与程序化购买）、《dv360-creative-brand-safety-deep.md》《dv360-measurement-attribution-deep.md》互补：本文不重复罗列端点，而是把 DV360 放在「GMP 数据与投放协作网络」中讲解，并给出可直接落地的 Python / Go 客户端工程实现。

---

## 一、核心概念与架构

### 1.1 GMP（Google Marketing Platform）产品矩阵与 DV360 的位置

Google Marketing Platform 是 Google 面向企业级广告主的整合营销技术栈，2018 年由 DoubleClick Digital Marketing（DDM）与 Google Analytics 360 合并而来。它不是一个单体产品，而是一组既可独立使用、又可深度互联的产品。要理解 DV360 的集成价值，必须先把整个 GMP 地图看清楚。

**GMP 核心产品矩阵**：

| 产品 | 全称 | 核心职责 | 一句话定位 |
|------|------|----------|-----------|
| DV360 | Display & Video 360 | 程序化展示、视频、音频、电视、DOOH 媒体购买 | 「买媒体」的 DSP |
| CM360 | Campaign Manager 360 | 广告投放管理、Floodlight 测量、归因、创意投放 | 「测转化」的 Ad Server / 测量中心 |
| SA360 | Search Ads 360 | 跨搜索引擎（Google、Bing、雅虎日本）搜索广告管理 | 「管搜索」的搜索管理平台 |
| Google Ads | Google Ads | Google 站内搜索、Display Network、YouTube、Discover、Performance Max | Google 自有的广告投放平台 |
| GAM | Google Ad Manager | 发布方 Ad Server + 广告交易（Exchange） | 「卖媒体」的 SSP/Ad Server |
| BigQuery | BigQuery | 企业级无服务器数仓 + 分析 | 「存数据」的数仓 |
| ADH | Ads Data Hub | 隐私安全的联合归因与分析沙箱 | 「安全算」的联合分析平台 |
| Analytics 360 | GA360 | 网站/App 行为分析 | 站内行为数据 |

> 记忆口诀：**买媒体用 DV360，卖媒体用 GAM，测转化用 CM360，管搜索用 SA360，Google 自有量用 Google Ads，出数据用 BigQuery，做隐私归因用 ADH。**

DV360 的「位置」不只是「一个 DSP」，而是 GMP 的**中枢数据协调点**：它向上承接 GA360 / BigQuery 的受众与转化数据，横向与 CM360 共享 Floodlight 测量与创意，与 Google Ads 共享第一方受众与竞价信号，向下通过 GAM 的授权交易 Access 私有库存。理解这个位置，才知道为什么集成模式如此重要。

### 1.2 GMP 产品之间的数据流向总览

```
                        ┌──────────────────────────────────────────────────────────┐
                        │                 Google Marketing Platform                 │
                        └──────────────────────────────────────────────────────────┘
    ┌───────────────┐       受众/转化         ┌──────────────────┐
    │  GA360 /      │ ────────────────────▶  │                  │
    │  App+Web 分析 │                        │                  │
    └───────────────┘                        │                  │
                                            │     DV360 DSP     │───────▶ 展示/视频/音频/CTV/DOOH 媒体
    ┌───────────────┐   Floodlight 转化      │  (媒体购买中枢)   │
    │  CM360        │ ────────────────────▶  │                  │
    │  Ad Server    │ ◀────────────────────  │                  │
    └───────────────┘   广告投放/素材         └───────┬──────────┘
                                                     │
                受众种子(seed) / 排除列表             │ 授权交易(Authorized Buyers / 私有市场)
    ┌───────────────┐  ────────────────────▶         │
    │  Google Ads   │                               ▼
    │ (自有量/PMax) │                   ┌───────────────────┐
    └───────────────┘                   │     GAM 发布方     │
                                        │  Ad Server/Exchange│
    ┌───────────────┐   曝光/点击/转化   └───────────────────┘
    │   ADH         │ ◀────────────────────
    │  联合分析沙箱  │
    └───────────────┘
```

这张图是全文的「向导图」：几乎所有集成模式都能在这张网上找到对应的一条边。后面的各章节会逐条把每条边展开成「原理 + 代码 + 踩坑」。

### 1.3 DV360 与各 GMP 工具的集成关系

#### 1.3.1 DV360 ↔ CM360（Campaign Manager 360）

CM360 是 DV360 在「测量与归因」层面的强绑定伙伴。二者的关系：

- **Floodlight** 由 CM360 统一管理，DV360 通过 `dv360_list_floodlight_configs` 读取广告主关联的 Floodlight 配置组（floodlightConfiguration）、活动（floodlightActivities）与转化（conversions），用于 DV360 站内的转化优化（conversion optimization）与报表归因。
- **创意共享**：DV360 可引用 CM360 中审批通过的 Creative，`dv360_list_creatives` 返回的 creative 可能 `source="CAMPAIGN_MANAGER_360"`。
- **归因统一**：广告主的曝光 / 点击 / 转化最终由 CM360 的 Floodlight 计数并写入 CM360 报表，DV360 需拉取 CM360 报表（而非自身报表明细）才能与 GA360 打通后链路。

集成关键点：**测量以 CM360 为准，投放以 DV360 为准**。做数据仓库时必须把 DV360 的投放明细与 CM360 的转化明细按 `campaignId / placementId / creativeId / floodlight` 维度 join。

#### 1.3.2 DV360 ↔ Google Ads

Google Ads 与 DV360 分属「站内」与「程序化采买」两个世界，但它们共享若干资产：

- **受众共享**：Google Ads 的第一方数据受众（网站访问者、目标客户匹配 Customer Match）可同步到 DV360，用于定向与排除；反之 DV360 的 `dv360_sync_advertiser` 侧也需要把受众变更广播出去。
- **媒体信号**：Performance Max 与 Discovery 广告虽然跑在 Google Ads 里，但 DV360 可读取其转化信号做跨渠道优化。
- **账号打通**：通过 `dv360_list_partner_links` / `dv360_create_partner_link` 管理 DV360 与 Google Ads 之间的关联（Partner Link），把「Google Ads > Display & Video 360」链路接上。

#### 1.3.3 DV360 ↔ SA360（Search Ads 360）

SA360 管理搜索；DV360 管理展示与视频。二者集成通常是「**营销活动协同**」而非数据深耦合：

- 通过**统一归因**把搜索的点击与展示的曝光拉到同一个测量框架（通常由 CM360 / GA360 承接）。
- SA360 的 remarketing 名单可部分共享给 DV360 作为展示再营销种子。

在 API 层面，SA360 与 DV360 并非同一套认证体系，集成点主要在报表层的跨系统汇总，而不是对象层的互调。

#### 1.3.4 DV360 ↔ GAM（Google Ad Manager）

GAM 是**发布方**（Publisher）侧的产品，DV360 是**广告主**（Advertiser）侧。二者的集成主要是「库存 / 交易」方向：

- DV360 作为买方，通过 GAM 的 **Authorized Buyers（授权买方）**机制参与 GAM Exchange 上的私有市场（PMP）与公开竞价。
- 存量对接参考《dv360-dfp-deep.md》的 **SDC（Sellers.json / 供应链透明度）**与交易设置。
- 若你的公司同时是广告主与发布方，需要在 DV360 与 GAM 两侧分别维护交易 ID 的映射表，避免两侧 ID 体系混乱。

#### 1.3.5 DV360 ↔ BigQuery（数据导出）

这是「投放 + 数仓」的**标准集成模式**：

- DV360 的明细数据（impression / click / conversion 明细，或按 lineItem / creative / insertionOrder 维度聚合的报表）通过 **BigQuery 数据迁移 / BigQuery 导出**落仓。
- 路径有两条：**API 拉取**（`dv360_get_report` / `dv360_sync_report` 把报表写到 BigQuery）与 **Google 官方导出**（DV360 报表可直接配到 BigQuery 表）。
- 落仓后用于：ROI 核算、跨渠道归因、异常检测、预测、BI 看板。

集成要点：**维度主键（lineItemId / creativeId / advertiserId / date）必须在 BigQuery 里建模为主键**，否则多次落地会重复。

#### 1.3.6 DV360 ↔ ADH（Ads Data Hub）

ADH 是**隐私安全的联合分析沙箱**：广告主不能直接拿 Google 的用户级数据，但可以拿自己的第一方数据在 ADH 里与 Google 聚合数据做「安全 join」，输出**聚合统计**（不含用户级明细）。

- 典型用途：**增量归因 / 跨设备归因 / 排除验证**——把 DV360 的曝光/点击（在 ADH 内以映射后的 key 表示）与广告主自己的转化明细 join，算 lift（增量提升）。
- ADH 输出只允许聚合数字与「/30（分母至少 30）」掩码，防止反推个体。
- DV360 侧只负责把 seed 数据（广告主第一方 ID）上传到 ADH，ADH 内部做匹配与计算。

> 此模式是 GDPR / 隐私沙箱（Privacy Sandbox）时代投放集成的“正统答案”，值得单独建文档深挖，本文只给定位与原理串讲。

### 1.4 GMP 工具职责对照表（集成视角）

以下表格从「系统集成工程师」的视角，把各工具按「能调用什么 API、出什么数据、跟谁对接」归类：

| 系统 | 官方 API | 数据出口 | 主要对接方 | 集成难度 |
|------|----------|----------|-----------|---------|
| DV360 | Display & Video 360 API（`display-video`，v4） | 投放明细、报表、受众、Floodlight 配置 | CM360 / Google Ads / GAM / BigQuery / ADH | 高 |
| CM360 | Campaign Manager 360 API（`dfareporting`） | Floodlight 转化、报表 | DV360 / GA360 / BigQuery | 中高 |
| SA360 | Search Ads 360 API | 搜索报表、出价 | DV360(协同) / GA360 | 中 |
| Google Ads | Google Ads API（gRPC，`googleads`） | 广告/关键词/转化/报表 | DV360(受众) / BigQuery | 高 |
| GAM | Google Ad Manager API（SOAP + REST） | 库存、订单、交易 | DV360(买方接入) / 发布方系统 | 高 |
| BigQuery | BigQuery REST API | 表/查询 | 所有上游 | 低 |
| ADH | Ads Data Hub API | 聚合结果 | DV360 / GA360 / CM360 | 极高 |

**一个关键洞察**：DV360 集成往往是「多对多」的——同一条投放记录要同步到 BigQuery 做数仓、转换信号要回流到投放做优化、受众要在 Google Ads 与 DV360 之间双向同步。因此**好的集成架构不是「点对点脚本」，而是「围绕统一数据模型 + 统一客户端 + 统一任务调度」的平台**。第三章会给出完整落地。

### 1.5 DV360 集成架构总览（平台视角）

把一个 DV360 集成平台拆成七层，各层之间通过明确的接口（Interface）解耦：

```
┌─────────────────────────────────────────────────────────────────────┐
│  L7 应用层    BI 看板 · ROI 报表 · 决策建议 · 告警通知               │
├─────────────────────────────────────────────────────────────────────┤
│  L6 入库层    BigQuery 表建模 · 增量/全量策略 · 主键去重 · 分区       │
├─────────────────────────────────────────────────────────────────────┤
│  L5 编排层    任务调度(airflow/cron) · DAG · 水位(watermark) · 重跑   │
├─────────────────────────────────────────────────────────────────────┤
│  L4 数据层    统一数据模型 · 七层单元映射 · ID 映射表 · 缓存           │
├─────────────────────────────────────────────────────────────────────┤
│  L3 客户端层  DV360Client · 统一 BaseClient · 重试/限流/分页中间件   │
├─────────────────────────────────────────────────────────────────────┤
│  L2 接入层    OAuth/Service Account · Token 管理 · 凭证轮换           │
├─────────────────────────────────────────────────────────────────────┤
│  L1 平台层    GMP API (DV360/CM360/Google Ads/GAM) · BigQuery · ADH │
└─────────────────────────────────────────────────────────────────────┘
```

后面章节的代码与工程实践，都围绕这七层展开：第二章讲透 L1~L3 的「原理」（REST 设计模式、认证、限流、重试、幂等、Webhook、外部工具集成原理），第三章给出 L2~L6 的「实战」（从零搭平台、统一客户端、批次操作、配额调优、踩坑）。

---

## 二、深度原理解析

### 2.1 DV360 REST API 设计模式

DV360 API 遵循 Google 的统一 REST 风格（与 Google Ads 的 gRPC 风格、Meta 的 Graph API 风格不同），理解它的「设计契约」，是写出健壮客户端的前提。下面逐条展开。

#### 2.1.1 资源层级（Resource Hierarchy）

DV360 API 的资源是**嵌套的树状结构**，URL 即表达层级：

```
/partners/{partnerId}
/advertisers
/advertisers/{advertiserId}
/advertisers/{advertiserId}/campaigns
/advertisers/{advertiserId}/campaigns/{campaignId}
/advertisers/{advertiserId}/insertionOrders
/advertisers/{advertiserId}/insertionOrders/{insertionOrderId}
/advertisers/{advertiserId}/lineItems
/advertisers/{advertiserId}/lineItems/{lineItemId}
/advertisers/{advertiserId}/creatives
/advertisers/{advertiserId}/creatives/{creativeId}
/partners/{partnerId}/targetingTypes/{targetingTypeId}/assignedTargetingOptions
```

层级关系：**Partner（合作伙伴）⊃ Advertiser（广告主）⊃ Campaign（广告系列）⊃ Insertion Order（订单项）⊃ Line Item（线条项目）⊃ Creative（创意）**。

这带来两个工程含义：
1. **绝大多数写操作必须携带完整的父级路径**（如更新 LineItem 需要 `advertiserId + lineItemId`），设计客户端时不能只传叶子 ID。
2. 我们的 `ad_platform_api.py` 正是这样封装的——例如 `dv360_get_line_item(advertiser_id, line_item_id)`、`dv360_get_advertiser(advertiser_id)`、`dv360_list_campaigns(customer_id)` 都把父 ID 作为显式参数。

#### 2.1.2 List 类接口：分页 Token（Page Token）

DV360 的 List 接口使用**游标分页（offset-less cursor pagination）**，而不是页码分页：

```
GET /advertisers/{advertiserId}/lineItems?pageSize=100&pageToken=<token>
```

- `pageSize`：每页条数，上限由服务端限定（通常 100~1000 之间，视资源而定）。
- 响应体带 `nextPageToken`：非空说明还有下一页，把它作为下一次请求的 `pageToken` 参数传入。
- **没有 `nextPageToken` 或为空** = 已到最后一页。
- 没有 `totalCount` / 总页数概念——必须「边拉边判」直到 nextPageToken 为空。

**游标分页的坑**：
- 它**不支持跳页**（不能直接翻到第 5 页），只能串行拉取；
- 高并发下若数据持续变化，分页可能产生**轻微重复或遗漏**（弱一致性），对「全量拉取」场景建议加时间去重；
- 必须**严格按 nextPageToken 顺序消费**，不要并发请求多个 pageToken。

`dv360_client.py` 的 `list_line_items` 只拉一页，生产级的 `paginate` 封装见 2.5 节的 Go 实现。

#### 2.1.3 字段选择（Field Selection / partial response）

Google 系 API 支持 `fields` 参数做**部分响应（partial response）**，只返回你需要的字段：

```
GET /advertisers/{advertiserId}/lineItems?fields=lineItems(lineItemId,displayName,entityStatus,budget)
```

好处：
1. **降低传输量**：LineItem 对象动辄几十个字段，只要几个能省 80%+ 的 payload；
2. **降低解析失败风险**：字段被服务端移除（breaking change）时，只请求必要的字段，改动面小；
3. **更清晰的可读性**：JSON 里只有关心的字段，便于调试。

相应地，客户端工具 `dv360_get_report` / `dv360_list_line_items` 应支持 `fields` 透传。不到万不得已不要 `select *` 全量字段。

#### 2.1.4 过滤（Filter）与排序（Order By）

List 接口通常支持：
- **filter**：`filter="entityStatus='ENTITY_STATUS_ACTIVE' AND lineItemType='LINE_ITEM_TYPE_DISPLAY_DISPLAY'"`
- **orderBy**：`orderBy="updateTime desc"`
- **filter 语法**：Google 标准 AIP-160 filter 语法，支持 `=`、`!=`、`AND` / `OR`、括号分组、`IN` / `NOT IN` 集合判断（形如 `y IN (1, 2, 3)`）。
- **空 filter**：很多接口 filter 为空表示返回全部，务必确认接口文档；有的接口（如某些 targeting 查询）filter 为空会返回空集。

工程要点：**把 filter / orderBy 视为「编译期」配置而非运行时拼接**，尽量避免把用户输入拼进 filter（防注入与语法错误）。

#### 2.1.5 字段命名与枚举约定

- 时间字段多为 **micros（微秒，1 秒 = 1_000_000 微秒）**：如 `flight.startTime`、`budget.budgetAmountMicros`、`lineItem.updateTime`。读文档时不要把秒当微秒，否则预算会差 10^6 倍（这是经典事故）。
- 状态枚举以大写蛇形命名：`ENTITY_STATUS_ACTIVE`、`ENTITY_STATUS_PAUSED`、`ENTITY_STATUS_ARCHIVED`。
- 金额单位：`budgetMicros`（DV360 用 `Micros` 表示美元的小数，1 USD = 1_000_000 micros）。报表里 `SPEND` 通常直接是美元，而对象字段是 micros，**两条线单位不一致**，入库前必须统一。

#### 2.1.6 写入类接口：Post / Patch / 幂等与批次

DV360 写接口分两类：
- **创建**：`POST /advertisers/{advertiserId}/lineItems`，body 为 LineItem 对象。
- **更新**：`PATCH /advertisers/{advertiserId}/lineItems/{lineItemId}?updateMask=budget.budgetAmountMicros`，body 只传要更新的字段，配合 `updateMask` 精确指定变更字段（这是 Google 的标准 patch 行为，避免整对象覆盖）。

**批量**：DV360 提供 `batch` 语义：
- `POST /advertisers/{advertiserId}/lineItems:batchUpdate` —— 对应我们的 `dv360_batch_update_line_items(updates)`。
- 批量接口把多个单对象请求打包成一次 RPC，**显著减少请求数**、降低限流命中概率、提高吞吐。
- 批量接口内部仍是「逐条执行、逐条返回结果」——**部分成功是常态**，必须解析响应里的逐条状态（per-item status），不能因为整批返回 200 就认为全成功。

我们封装时 `dv360_batch_update_line_items` 接收 `updates: List[Dict]`，其设计意图就是让调用方批量提交并拿到逐条结果。

### 2.2 认证与授权（Authentication & Authorization）

DV360 认证走 **Google OAuth2**，有两种主流方式：

#### 2.2.1 Service Account + JWT（服务账号，适合服务端自动化）

这是**后端集成平台**的主流方式，`dv360_client.py` 实现了完整流程：

```
1. 创建 Google Cloud 项目，启用 Display & Video 360 API
2. 创建 Service Account，下载 JSON 密钥（含 private_key / private_key_id / client_email）
3. 在 DV360 UI 中，把 Service Account 的 client_email 授权为 Partner/Advertiser 用户
4. 用私钥把 JWT 断言编码（RS256）
5. POST 到 https://oauth2.googleapis.com/token ，grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
6. 拿到 access_token，之后请求头 Authorization: Bearer <token>
```

`refresh_access_token()` 的关键实现逻辑：

```python
def refresh_access_token(self) -> bool:
    # 1) 若 token 未到期，直接复用（节省 RPC）
    if self.access_token and time.time() < self.token_expiry - 60:
        return True
    sa_key = self._load_service_account()
    now = int(time.time())
    header = {"typ": "JWT", "alg": "RS256", "kid": sa_key['private_key_id']}
    payload = {
        "iss": sa_key['client_email'],   # 签发者
        "sub": sa_key['client_email'],   # 主体 = 服务账号
        "aud": self.TOKEN_URL,           # audience = token 端点
        "iat": now,
        "exp": now + 3600,
        "scope": " ".join(self.config.get('scopes', [])),
    }
    jwt_token = pyjwt.encode(payload, sa_key['private_key'],
                             algorithm='RS256', headers={'kid': sa_key['private_key_id']})
    data = {'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': jwt_token}
    result = requests.post(self.TOKEN_URL, data=data, timeout=30).json()
    if 'access_token' in result:
        self.access_token = result['access_token']
        self.token_expiry = now + result.get('expires_in', 3600)
        return True
    return False
```

要点：
- **JWT 有效期通常 1 小时**，服务账号刷新是无状态的（不看 refresh_token，直接再签一个 JWT），所以长任务不会因 refresh token 过期而中断——这比「用户授权型 OAuth」更省心。
- `exp : now + 3600` 是服务账号 JWT 的推荐值；不要签太短（会频繁刷新）也不要太长（超过 Google 上限会被拒）。
- `scopes` 至少包含 `https://www.googleapis.com/auth/display-video`。
- 生产环境**不要把私钥写死在代码**，用 KMS / Secret Manager 管理。

#### 2.2.2 用户授权型 OAuth2（适合 UI / 模拟人工）

- 走标准 OAuth2 授权码流程：用户点同意 → 拿 authorization code → 换取 access_token + refresh_token。
- **refresh_token 有过期/失效风险**（用户撤销授权、策略变更），需要监控 `dv360_validate_credentials` 或捕获 `401` 重新授权。
- 相比服务账号，用户授权型对「模拟真人操作」「访问多个账号」更合适，但运维成本更高（要处理 refresh token 刷新与失效）。
- `dv360_auth` 与 `dv360_validate_credentials` 两个工具即服务于这一流程：前者发起/完成授权，后者校验当前凭证是否仍然有效（例如拿凭证去 ping 一个轻量 API）。

#### 2.2.3 凭证生命周期管理（工程实践）

无论哪种方式，「凭证状态」都需要被监控：
- `dv360_validate_credentials()`：返回凭证是否有效（能成功通过某次轻量调用）。
- `dv360_get_customer(customer_id)` / `dv360_list_customers()`：枚举当前可用账号，用于权限审计。
- `dv360_list_permission_users(advertiser_id)` / `dv360_add_permission_user` / `dv360_remove_permission_user`：管理广告主下的 API 用户权限——新增服务账号授权后，若没配好权限，会统一回 403，这类问题排障见第四章。

**授权矩阵（谁有什么权限）建议做成一张表**，与 `dv360_list_audit_logs` 审计日志按月核对，防止「幽灵权限」与「权限漂移」。

### 2.3 限流与配额（Rate Limits & Quota）

DV360 对每个 API 调用有**配额（Quota）**与**速率（Rate）**双层限制。工程上必须理解「配额」≠「速率」。

#### 2.3.1 读这三个工具

我们的工具库里已有现成的观测工具：
- `dv360_get_quota(advertiser_id)`：查询当前账号的**配额使用情况**（每天/每分钟允许多少，用掉多少）。
- `dv360_list_usage_stats(advertiser_id)`：查询**用量统计**（按时间维度的调用次数、被限流次数）。
- `dv360_list_rate_limits()`：查询当前**速率限制**配置（每分钟多少请求、每次并发多少等）。

#### 2.3.2 429 的语义

当请求超限时，返回 **HTTP 429 Too Many Requests**，通常响应头带：
- `Retry-After`：建议等待的秒数。
- `X-RateLimit-*` 系列头：剩余配额 / 重置窗口。
- `Quota exceeded for metric ...`：指明是哪个配额指标被突破（如 `displayvideo.googleapis.com/default_read_requests`）。

工程要点：
1. **429 是可以重试的**（transient），但要**尊重 Retry-After**，不能疯狂重试（会把问题放大成互相踩踏的「重试风暴」）。
2. **区分 429（限流）与 4xx 业务错误（参数错、权限错）**：429 才重试，400 / 403 / 404 重试也没用。
3. 报 429 时先看 `dv360_get_quota`：是「天配额耗尽」还是「分钟速率超标」。前者要等窗口重置或申请提额；后者只要降速（jitter + backoff）即可。

#### 2.3.3 配额分配（Quota Allocation）

Google Cloud 控制台可对 DV360 API 设置配额策略，包含：
- **每日配额（daily quota）**：如「每天 N 次读取」。
- **每分钟配额（per-minute quota）**：如「每分钟 N 次」，决定突发能力。
- **按项目 / 按账号**维度分配。

**工程话术**：配额是「预算」，速率是「水龙头」。预算决定一天能拉多少，水龙头决定瞬间能放多少。两者都要规划才能支撑「批量拉全量 + 高峰增量」的混合流量。

#### 2.3.3（补充）如何优雅应对 429：退避重试

通用策略：
- 首退避 200~500ms，指数增长（×2），上限 30~60s，抖动（jitter ± 20%）避免「惊群」。
- 重试上限 4~6 次；超过即放弃并**进死信队列 + 告警**。
- 尊重 `Retry-After`（若 > 上限，等待更合理）。

这一策略会以其在 Go 中的完整实现呈现在 2.5.2 节。

### 2.4 幂等与批次操作（Idempotency & Batch）

#### 2.4.1 幂等

「幂等」指**同一请求执行多次，结果与执行一次相同**。DV360 写接口的幂等性分两层：

- **天然的幂等**：`PATCH` 配合 `updateMask` 是幂等的——把预算改为 $100，执行 10 次还是 $100。
- **创建类不幂等**：`POST /lineItems` 创建 10 次会产生 10 个 LineItem！**这正是重试导致「重复创建」事故的根源**。

工程对策：
- 需要「建了就不重复建」的场景，**先查再建**（先 list 判断是否已存在同名/同指纹，或用幂等键语义自己维护映射表）。
- 图数据同步任务里，建议维护 `externalRef → lineItemId` 的映射表，避免重复创建。

#### 2.4.2 批次（Batch）

`dv360_batch_update_line_items(updates)` 的响应**必须逐条解析**：

```json
{
  "lineItems": [
    {"lineItemId": "li_1", "entityStatus": "ENTITY_STATUS_ACTIVE"},
    {"lineItem": {"lineItemId": "li_2"}, "error": {"code": 400, "message": "非法预算"}}
  ]
}
```

- 第 2 条失败不会影响第 1 条成功——**部分成功是常态**。
- 客户端要返回**逐条结果**（成功列表 / 失败列表 + 失败原因），便于调用方重试失败子集。
- 批次大小有上限（如一次最多 N 条），超出需分片。

#### 2.4.3 批次创建与「先查再建 + 批次」的组合套路

第三章会给出完整示例：先 list 存量 → 对比目标集合 → 差集用批量创建 → 交集用批量更新 → 多余项可选批量暂停。这套「**diff 驱动**」的模式是 DV360 投放集成里最常用的幂等套路。

### 2.5 Webhook 与事件通知（Event Notification）

DV360 的实时事件（如 LineItem 状态变更、审批状态更新、报表就绪）通常通过 **Webhook** 或**轮询**两种方式获得。

#### 2.5.1 相关工具

- `dv360_list_webhooks(advertiser_id)`：列出已注册的 Webhook。
- `dv360_create_webhook(advertiser_id, ...)`：注册一个新的 Webhook（配置：回调 URL、事件类型、密钥/签名密钥）。
- `dv360_test_webhook(webhook_id)`：手动触发一次测试事件，验证回调端点是否可达、签名是否正确。
- `dv360_delete_webhook(webhook_id)`：删除 Webhook。

#### 2.5.2 Webhook 可靠性问题（重要踩坑）

Webhook 天然是「尽力而为（best-effort）」的，**不保证不丢**：
- 回调端点宕机期间的事件会丢（除非平台有重投机制）。
- 网络抖动、消息体过大、回调超时会导致投递失败。
- 事件可能**乱序 / 重复**（at-least-once 语义下会重复）。

**工程对策**：
1. 把 Webhook 当作「唤醒信号」而非「数据源」：收到事件后，**用事件里的实体 ID 主动 GET 拉最新状态**，以拉到的状态为准。这样即使事件丢了一半、重复发了几倍，最终状态仍一致（最终一致）。
2. 回调端点要**幂等**：同一事件处理多次无副作用。
3. 验证签名：`dv360_test_webhook` 返回的签名密钥用于校验回调 payload 的 `X-...-Signature` 头，防止伪造。
4. 兜底轮询：对关键实体（审批状态、报表就绪）保留「定期全量/增量轮询」兜底，因为 Webhook 会丢。

#### 2.5.3 审计与活动日志（Ops 数据源）

除了业务事件，运维层面有：
- `dv360_list_audit_logs(advertiser_id)`：**审计日志**——谁在什么时候改了什么（创建/更新/删除、操作者、IP）。适合合规审计。
- `dv360_list_activity_logs(advertiser_id)`：**活动日志**——平台侧的关键活动。

这两类日志是「集成平台的可观测性底座」：排障「是谁把预算改了 / 谁停了 LineItem」时，直接查审计日志即可定位，无需盲猜。

### 2.6 与具体目标系统的集成原理

#### 2.6.1 与 CM360 Floodlight 的集成原理

```
DV360 投放广告 ──▶ 用户点击/曝光 ──▶ 落地页埋有 Floodlight 标签
                                                  │
          CM360(CM360 API) 记录 floodlightConversion ──▶ 归因到 campaign/creative
```

- DV360 通过 `dv360_list_floodlight_configs(advertiser_id)` 拉取广告主的 Floodlight 配置（配置组 / 活动 / 转化计数）。
- 转化数据真正权威来源是 CM360 API（`dfareporting.floodlightActivities` / `conversions`），DV360 只消费它做站内优化。
- 集成正确做法：**转化以 CM360 为准**，DV360 报表里如需转化，往往也是 CM360 回灌的。
- 归因窗口（如 1 天 / 7 天 / 28 天）+ 归因模型（last click、data-driven）在 CM360 侧配置，DV360 不重复归因。

#### 2.6.2 与 GAM（Google Ad Manager）的集成原理

- GAM 是发布方 Ad Server + Exchange。
- DV360 作为买方参与 GAM Exchange 上的交易：公开竞价（Open Auction）、私有市场（Private Market Place, PMP）、程序化保量（PG）。
- 相关对象：**Deal（交易）** 由 GAM 发布方创建，DV360 买方接受（`dv360_accept_proposal` / `dv360_reject_proposal` 对应 DV360 侧的 proposal / deal 流程）。
- **SDC/sellers.json**：供应链透明度（Supply Chain Transparency）要求买卖双方传递完整的供应链信息；DV360 作为买方要读取并校验发布方传递的供应链数据（详见《dv360-dfp-deep.md》）。
- 集成落点：广告主自己的系统需要在 DV360 侧维护「接受哪些交易 / 竞价策略 / 目标 CPM」，与 GAM 侧的库存定价联动。

#### 2.6.3 与 BigQuery 导出的集成原理

- **路径 A（API 拉取落仓）**：用 `dv360_get_report` 定义报表查询（维度 + 指标 + 日期范围），把结果（逐行数据）写进 BigQuery 表。`dv360_sync_report` 则可作为「定义报表 + 触发落地」的一体化封装。
- **路径 B（Google 官方导出）**：DV360 UI 里把报表 query 直接配到某个 BigQuery 数据集，Google 在每天定时把结果落到指定表（替换式/增量式可配）。
- **BigQuery 侧的建模要求**：
  - 主键：`(advertiser_id, date, lineItem_id, creative_id, …)`；
  - 分区：按 `date` 分区，成本与查询性能双赢；
  - 去重：多次落地时按主键 `UPSERT` 或先 TRUNCATE 当天分区再写（避免累积重复）。

#### 2.6.4 与 ADH（Ads Data Hub）的集成原理

- ADH 是「隐私安全联合分析」：广告主的第一方转化明细（含自己的 user ID）与 Google 侧的暴露数据（DV360 曝光/点击，以 key 形式）在 ADH 内 join，只输出聚合统计。
- 集成流程：**上传 seed（广告主第一方 ID 名单）→ ADH 里写 QUERY（join + 聚合）→ 读取聚合结果（/30 掩码）**。
- DV360 在 ADH 场景只贡献「投放侧数据」，业务逻辑全在 ADH 查询里。
- 隐私阈值：结果要求「每个聚合分桶分母 ≥ 30」，否则不输出——这是为了防推断。
- **用途**：增量（lift）测算、跨设备归因、排除验证（看哪些转化其实没看过广告）。

### 2.7 Go 实现：通用 API 客户端（重试中间件 / 限流器 / 分页封装）

生产级集成的工程语言，Go 是很好的选择（强类型、并发、部署简单）。下面给出一个「可复用」的 DV360 / 通用 GMP 客户端骨架，包含三大件：**重试中间件、滑动窗口限流器、游标分页封装**。

#### 2.7.1 统一 ApiResponse 与 BaseClient

先定义统一的响应与错误封装（与 Python 侧 `api_common.py` 的 `ApiResponse` 对应）：

```go
package gmpclient

import (
	"encoding/json"
	"fmt"
	"time"
)

// ApiResponse 统一响应封装，对应 scripts/api_common.py 的 ApiResponse
type ApiResponse struct {
	Success   bool            `json:"success"`
	Data      json.RawMessage `json:"data,omitempty"`
	Error     string          `json:"error,omitempty"`
	RateLimit map[string]int  `json:"rate_limit,omitempty"`
}

// APIError 统一错误，区分「可重试」与「不可重试」
type APIError struct {
	Code       int           // HTTP 状态码
	Message    string
	Retryable  bool          // 429/5xx 为 true
	RetryAfter time.Duration // 来自 Retry-After 头（429 时）
}

func (e *APIError) Error() string {
	return fmt.Sprintf("gmp api error: status=%d msg=%s", e.Code, e.Message)
}
```

#### 2.7.2 重试中间件（Retry Middleware）

```go
// RetryConfig 指数退避 + 抖动配置
type RetryConfig struct {
	MaxAttempts int           // 最多尝试次数
	InitialWait time.Duration // 首次退避
	MaxWait     time.Duration // 退避上限
	Jitter      float64       // 抖动比例，0~1
}

func DefaultRetryConfig() RetryConfig {
	return RetryConfig{MaxAttempts: 5, InitialWait: 300 * time.Millisecond,
		MaxWait: 30 * time.Second, Jitter: 0.2}
}

// retry 包装任意返回 *APIError 的调用
func retry[T any](cfg RetryConfig, fn func() (T, *APIError)) (T, error) {
	wait := cfg.InitialWait
	var lastErr error
	for attempt := 1; attempt <= cfg.MaxAttempts; attempt++ {
		result, aerr := fn()
		if aerr == nil {
			return result, nil
		}
		lastErr = aerr
		if !aerr.Retryable { // 非可重试错误直接返回
			return result, lastErr
		}
		if aerr.RetryAfter > 0 && aerr.RetryAfter > wait {
			wait = aerr.RetryAfter // 尊重 Retry-After
		}
		time.Sleep(wait + time.Duration(float64(wait)*jitter()))
		wait *= 2
		if wait > cfg.MaxWait {
			wait = cfg.MaxWait
		}
	}
	var zero T
	return zero, lastErr
}

// jitter 返回 [0, config 抖动] 内的随机比例
func jitter() float64 { return randomFloat() } // 演示：rand.Float64()
```

要点：
- **只有 `Retryable`（429 / 5xx）才重试**；401/403/400 重试无用，直接失败。
- **尊重 Retry-After**，且退避指数增长 + 抖动，避免「重试风暴」（thundering herd）。
- 超过 MaxAttempts 后返回最后一次错误，由调用方决定是否进死信队列。

#### 2.7.3 滑动窗口限流器（Sliding Window Rate Limiter）

DV360 是对**特定账号**限速的。客户端侧做一个按 key（如 advertiser_id）维度的滑动窗口限流器，配合服务端速率：

```go
import "sync"

// SlidingWindowLimiter 每窗口(如 1s)允许 limit 次的滑动窗口限流器
type SlidingWindowLimiter struct {
	mu     sync.Mutex
	limit  int
	window time.Duration
	events []time.Time // 各事件发生时刻
}

func NewSlidingWindowLimiter(limit int, window time.Duration) *SlidingWindowLimiter {
	return &SlidingWindowLimiter{limit: limit, window: window, events: []time.Time{}}
}

// Allow 返回是否放行；若放行则记录本次事件
func (l *SlidingWindowLimiter) Allow() bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := time.Now()
	cutoff := now.Add(-l.window)
	keep := l.events[:0]
	for _, t := range l.events {
		if t.After(cutoff) {
			keep = append(keep, t)
		}
	}
	l.events = keep
	if len(l.events) >= l.limit {
		return false
	}
	l.events = append(l.events, now)
	return true
}
```

用法：每个 advertiser 一个 limiter（用 map[key]*Limiter），请求前 `Allow()`，不放行就 sleep 一小段再试，把「突发」削平。

#### 2.7.4 游标分页封装（Cursor Pagination）

```go
// Page 一次分页的原始结果
type Page struct {
	Items    []json.RawMessage
	Next     string // nextPageToken
}

// PageFunc 真实用户的「取一页」函数：给定 pageToken 返回一页 + 下一个 token
type PageFunc func(pageToken string) (Page, *APIError)

// PaginateAll 串行拉取所有页（游标分页不支持跳页）
func PaginateAll(fn PageFunc) ([]json.RawMessage, error) {
	token := ""
	var all []json.RawMessage
	for {
		page, aerr := fn(token)
		if aerr != nil {
			return nil, aerr
		}
		all = append(all, page.Items...)
		if page.Next == "" { // 无 nextPageToken = 到底
			break
		}
		token = page.Next
	}
	return all, nil
}
```

要点：
- **必须在拿到 nextPageToken 后才发起下一页**，串行消费；
- 循环终止条件是 **nextPageToken 为空**，不要依赖 totalCount；
- 全量拉取 + 弱一致性时，必要时对结果按实体 ID 做去重。

#### 2.7.5 组合成客户端

```go
// DV360Client 把限流 + 重试 + 认证组合成统一入口
type DV360Client struct {
	baseURL   string
	tokenFn   func() (string, *APIError) // 取当前有效 token（含自动刷新）
	limiter   *SlidingWindowLimiter
	retryCfg  RetryConfig
	transport *http.Client
}

func (c *DV360Client) do(ctx context.Context, method, path string,
	params map[string]string, body any) (json.RawMessage, *APIError) {
	// 1. 限流：不放行则稍微等待
	for !c.limiter.Allow() {
		time.Sleep(100 * time.Millisecond)
	}
	// 2. token
	token, aerr := c.tokenFn()
	if aerr != nil {
		return nil, aerr
	}
	// 3. 构造请求
	req, _ := http.NewRequestWithContext(ctx, method, c.baseURL+path, bodyJSON(body))
	req.Header.Set("Authorization", "Bearer "+token)
	// 4. 通过 retry 包装发送 + 解析 429/5xx 为 Retryable
	return retry(c.retryCfg, func() (json.RawMessage, *APIError) {
		resp, err := c.transport.Do(req)
		if err != nil {
			return nil, &APIError{Code: 0, Message: err.Error(), Retryable: true}
		}
		defer resp.Body.Close()
		var raw json.RawMessage
		_ = json.NewDecoder(resp.Body).Decode(&raw)
		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			return raw, nil
		}
		retryable := resp.StatusCode == 429 || resp.StatusCode >= 500
		return nil, &APIError{Code: resp.StatusCode, Retryable: retryable}
	})
}
```

这个 `do` 已经涵盖：**限流 → 认证 → 重试**三级防护。任何上层资源方法（`ListLineItems` / `GetReport` / `BatchUpdateLineItems`）都复用它，保证全客户端行为一致。


---

## 三、生产环境实战

### 3.1 从零搭建 DV360 集成平台（客户端封装 → 认证 → 拉取/写入 → 报表入库 → 监控）

本节以一个「品牌广告主的 DV360 投放数据平台」为案例，完整走一遍从零到一的搭建。目标：**每天自动把 DV360 的投放对象（LineItem / Creative / 预算）与报表数据同步进 BigQuery，并对异常（预算超支、投放暂停、配额用尽）报警**。

#### 3.1.1 阶段一：凭证与基础客户端（L1~L2）

**1. 准备凭证**（`config/ad_platform_credentials.json`，模板源自 `ad_platform_api.py` 的 `CREDENTIALS_FILE`）：

```json
{
  "dv360": {
    "service_account_file": "config/dv360_service_account.json",
    "partner_id": "123456",
    "customer_id": "987654",
    "scopes": ["https://www.googleapis.com/auth/display-video"]
  }
}
```

**2. 编写薄封装**（在 `dv360_client.py` 之上再包一层「应用语义」，让业务代码不直接碰 HTTP）：

```python
# integration_client.py —— DV360 集成专用客户端（业务语义层）
from dv360_client import DV360Client

class Dv360IntegrationClient:
    """面向业务的 DV360 客户端：把页面级方法转成业务方法"""

    def __init__(self, config: dict):
        self._raw = DV360Client(config)   # 底层客户端：refresh_access_token/_make_request

    # ---- 拉取侧 ----
    def list_active_line_items(self, advertiser_id: str, page_size: int = 100):
        """业务：列出广告主下所有 ACTIVE 的 LineItem（带分页）"""
        endpoint = f"/advertisers/{advertiser_id}/lineItems"
        params = {"pageSize": page_size, "filter": "entityStatus='ENTITY_STATUS_ACTIVE'"}
        page_token = ""
        result = []
        while True:
            if page_token:
                params["pageToken"] = page_token
            resp = self._raw._make_request("GET", endpoint, params=params)
            if not resp:
                break
            result.extend(resp.get("lineItems", []))
            page_token = resp.get("nextPageToken", "")
            if not page_token:
                break
        return result

    # ---- 写入侧 ----
    def batch_pause_line_items(self, advertiser_id: str, line_item_ids: list) -> dict:
        """批量暂停：返回 {success: [...], failed: [...]}"""
        updates = [
            {"lineItemId": lid,
             "entityStatus": "ENTITY_STATUS_PAUSED",
             "updateMask": "entityStatus"} for lid in line_item_ids
        ]
        resp = self._raw._make_request(
            "POST",
            f"/advertisers/{advertiser_id}/lineItems:batchUpdate",
            data={"lineItems": updates, "lineItemIds": line_item_ids},
        )
        # 解析部分成功
        ok, failed = [], []
        for item in (resp or {}).get("lineItems", []):
            if item.get("error"):
                failed.append((item.get("lineItem", {}).get("lineItemId"), item["error"]))
            else:
                ok.append(item.get("lineItem", {}).get("lineItemId"))
        return {"success": ok, "failed": failed}
```

要点：**业务层永远不出现裸 URL**；URI、分页、filter 全部收进这一层，方便测试 OR 隔离（mock 这个类即可）。

#### 3.1.2 阶段二：报表拉取 + BigQuery 入库（L4~L6）

**3. 报表 Query 的定义与执行**（对应 `dv360_get_report` / `dv360_sync_report`）：

```python
# scripts/report_ingest.py —— 报表入库
import datetime
from google.cloud import bigquery

REPORT_DIMENSIONS = ["LINE_ITEM_ID", "LINE_ITEM_NAME", "CREATIVE_ID", "DATE"]
REPORT_METRICS = ["IMPRESSIONS", "CLICKS", "TOTAL_CONVERSIONS", "TOTAL_MEDIA_COST_AMOUNT_MICROS"]

def build_report_query(advertiser_id: str, start: str, end: str) -> dict:
    """构造 DV360 报表 Query 对象（对应 dv360_get_report 语义）"""
    return {
        "kind": "displayvideo#query",
        "metadata": {"title": f"daily-{advertiser_id}",
                     "dateRange": {"startDate": {"year": int(start[:4]), "month": int(start[5:7]), "day": int(start[8:10])},
                                   "endDate":   {"year": int(end[:4]),   "month": int(end[5:7]),   "day": int(end[8:10])}}},
        "params": {
            "groupBys": REPORT_DIMENSIONS,
            "metrics": REPORT_METRICS,
            "filters": [{"type": "FILTER_TYPE_ADVERTISER", "value": advertiser_id}],
        },
    }

def ingest_report_to_bigquery(client, advertiser_id: str, start: str, end: str,
                              project: str, dataset: str, table: str) -> int:
    """拉取报表并 UPSERT 进 BigQuery（主键去重）。返回写入行数。"""
    rows = run_report(client, advertiser_id, start, end)   # 内部用 dv360_get_report 拉全量行
    bq = bigquery.Client(project=project)
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",   # 当天分区先清空再写，保证幂等
        schema=[
            bigquery.SchemaField("date", "DATE"),
            bigquery.SchemaField("advertiser_id", "STRING"),
            bigquery.SchemaField("line_item_id", "STRING"),
            bigquery.SchemaField("creative_id", "STRING"),
            bigquery.SchemaField("impressions", "INT64"),
            bigquery.SchemaField("clicks", "INT64"),
            bigquery.SchemaField("conversions", "FLOAT"),
            bigquery.SchemaField("cost_micros", "INT64"),
        ],
    )
    normalized = normalize_rows(rows, advertiser_id)        # 单位统一：micros→保留，不转
    job = bq.load_table_from_json(normalized, f"{dataset}.{table}", job_config=job_sql)
    job.result()
    return len(normalized)
```

这里踩过的坑先预告（详见 3.5）：
- **单位陷阱**：`TOTAL_MEDIA_COST_3_AMOUNT_MICROS` 是微美元；下游金额字段若按「美元」存，必须先 ÷1_000_000，否则看板数字差 10^6。
- **分区截断**：`WRITE_TRUNCATE` 之于「分区表」必须在分区级做，别 TRUNCATE 全表（会把历史给清了）。

#### 3.1.3 阶段三：定时调度与水位（L5）

用「水位（watermark）」驱动增量同步：记录「上次成功同步到哪天」，今天只拉水位后的数据。

```python
# scheduler 伪代码：airflow / cron 每日 06:30 执行
def daily_sync(advertiser_id: str):
    watermark = read_watermark(advertiser_id)            # 比如 2026-08-13
    today = yesterday_date()                              # 2026-08-14
    if watermark >= today:
        log.info("水位已到最新，跳过")
        return
    # 1) 对象同步：LineItem/Creative/IO 全量 diff（见 3.3）
    sync_objects(advertiser_id)
    # 2) 报表同步：增量天范围
    ingest_report_to_bigquery(advertiser_id, start=watermark, end=today)
    # 3) 推进水位
    write_watermark(advertiser_id, today)
```

水位失败重跑语义：**只有当 ingest 完全成功才推进水位**，否则明早会从旧水位重跑（天然补偿）。

#### 3.1.4 阶段四：监控与告警

监控点清单：

| 监控项 | 数据源 | 触发条件 | 动作 |
|--------|--------|----------|------|
| 配额水位 | `dv360_get_quota` | 当日用量 > 80% | 提前告警，调整批次大小 |
| 429 频率 | `dv360_list_usage_stats` | 全时段 429 总数异常上升 | 降并发 / 加退避 |
| 同步任务失败 | 任务日志 | ingest 异常 | 重试 + PagerDuty/Slack |
| 写入失败子集 | 批次返回值 | failed 非空 | 死信表 + 次日重放 |
| 凭证过期 | `dv360_validate_credentials` | 返回 false | 立即 Rotate 凭证 |
| 报表水位停滞 | watermark | 连续 2 天未推进 | 人工介入 |

### 3.2 跨平台统一客户端（dv360 / meta / google / tiktok）

真实广告主几乎不可能只投 DV360。`ad_platform_api.py` 与 `api_common.py` 的工程智慧在于：**把四家平台的客户端收敛到同一个「形」上**，业务层写一份，四处跑。

#### 3.2.1 Python 统一客户端模式（基于 api_common.py）

```python
# api_common.py 已定义：
#   ApiResponse(success, data, error, rate_limit)   —— 统一返回壳
#   BaseAdPlatformClient(credentials, platform, base_url, token, token_expiry)
#       ├─ get_token()    —— 各平台各自实现
#       └─ request(method, endpoint, **kwargs) —— 各平台各自实现

# google_ads_api.py 实现（Google Ads）：
class GoogleAdsApiClient(BaseAdPlatformClient):
    def get_token(self) -> str:
        return self.credentials["access_token"]

    def request(self, method, endpoint, **kwargs) -> ApiResponse:
        """底层用 GoogleAdsService.SearchStream；这里统一成 request(method, endpoint)"""
        ...  # 返回 ApiResponse(success=..., data=..., error=...)

    def search(self, customer_id, query) -> ApiResponse:
        # GAQL: SELECT campaign.id, ... FROM campaign WHERE ..."
        ...

# meta_api.py 实现（Meta Graph API）：
class MetaApiClient(BaseAdPlatformClient):
    def get_token(self) -> str:
        return self.credentials["access_token"]

    def get_insights(self, account_id, levels, date_preset, fields) -> ApiResponse:
        ...
```

统一客户端的设计要诀：
1. **统一返回壳** `ApiResponse(success, data, error, rate_limit)`：上层只判断 `success`，不用三家各自的异常类型。
2. **统一分页语义**：尽管三家分页机制不同（DV Flow 的 pageToken、Meta 的 cursor、Google Ads 的 page_size + offset），收敛成统一的「迭代器」接口：
3. **统一端点命名**：`list_campaigns(customer_id)` 在 Google Ads 与 Meta 各实现各的，但**签名形态一致**。

```python
def sync_campaigns(client, account_id: str):
    """跨平台「同一份业务代码」：不同平台客户端共享此函数"""
    resp = client.list_campaigns(account_id)
    if not resp.success:
        raise RuntimeError(f"list_campaigns failed: {resp.error}")
    for camp in resp.data:
        upsert_campaign(platform=client.platform, payload=camp)
```

再加一层「平台路由」：

```python
# 路由表：把业务动作映射到平台客户端
CLIENTS = {
    "dv360": Dv360IntegrationClient,
    "google": GoogleAdsApiClient,
    "meta": MetaApiClient,
    "tiktok": TikTokApiClient,
}

def client_for(platform: str):
    return CLIENTS[platform](load_credentials(platform))
```

这样「双十一全渠道投放同步」「跨渠道报告汇总看板」这类业务只需写一份代码对四家平台。

#### 3.2.2 Go 下的同构设计

Go 侧对应思路：所有平台实现同一个 `PlatformClient` 接口：

```go
type PlatformClient interface {
	GetToken() (string, error)
	Request(ctx context.Context, method, resource string, params map[string]string,
		body any) (json.RawMessage, error)
}

type DV360Client struct { ... }   // 实现 PlatformClient
type GoogleAdsClient struct { ... }
type MetaClient struct { ... }
```

业务层只依赖接口，「换平台＝换实现」，测试时用 mock 实现，这套「依赖抽象」让 CI 里的集成测试几乎无成本。

### 3.3 批次创建 LineItem（批量落地模板）

「从广告主的排期表（Media Plan）批量创建多个 LineItem」是 DV360 集成里最典型的写入场景。这里给一个生产级 P0 模板：

```python
# scripts/bulk_create_line_items.py —— 排期表 → DV360 批量创建
import csv, time
from ad_platform_api import dv360_create_line_item

def parse_plan(path: str) -> list[dict]:
    """读排期表 CSV → 标准化 dict 列表"""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "name": r["LI_名称"],
                "budget_micros": int(float(r["预算美元"]) * 1_000_000),
                "start_micros": to_micros(r["开始时间"]),   # "2026-08-01" → 微秒
                "end_micros":   to_micros(r["结束时间"]),
                "targeting_geo": r["地域"].split(","),
            })
    return rows

def create_in_batches(client, advertiser_id, plan_rows, batch_size=50):
    """按批次创建；记录每个 batch 的逐条结果；失败子集进入重试队列"""
    total_ok, total_fail = 0, []
    for i in range(0, len(plan_rows), batch_size):
        chunk = plan_rows[i:i + batch_size]
        # 构造 DV360 批量创建所需 payload
        line_items = [to_line_item_payload(r) for r in chunk]
        resp = client.dv360_batch_update_line_items(...) if False else create_batch(client, advertiser_id, line_items)
        # 逐条解析
        for item in resp.get("lineItems", []):
            if item.get("error"):
                total_fail.append(item)
            else:
                total_ok += 1
        log.info(f"batch {i // batch_size}: ok={total_ok} fail={len(total_fail)}")
        time.sleep(1)   # 主动削峰，降低 429 概率
    return total_ok, total_fail
```

关键细节（全部来自实战踩坑）：

1. **预算单位换算一次性函数** `budget_micros = 美元 × 1_000_000`，后续统一 micros。
2. **批次大小控制**：DV360 单次 batch 上限存在（一般数十个），先用 50/批起步，观测 429 后下调或加 sleep。
3. **逐条结果必须解析**：batch 部分成功是常态，**重试要重试失败的子集**，不要整批重放（否则已成功的会重复/覆盖）。
4. **幂等**：如果平台创建无幂等键，批次前先 `list` 找出已存在的同名项做跳过或复用（diff 模式，见 3.5.2）。
5. **时区**：flight 时间 micros 用哪个时区？DV360 内部按账号时区；跨时区排期务必显示换算，否则预算圆落地全靠猜。

### 3.4 配额与限流调优（Quota & Rate 调优实战）

#### 3.4.1 配额模型要「分而治之」

DV360 配额矩阵：**Partner 配额 / 项目配额 / 每分钟并发**。实战调优遵循三原则：

1. **先测量、后调参**：上线 2 周只爬 `dv360_list_usage_stats`，把「每天总调用量 / 每分钟峰值 / 被限流次数」画出来后决定限流器参数，别拍脑袋。
2. **读拉与写分开**：批量读取（报表、列表）用大 pageSize 压次数；写入（create/update）留一部分速率余量，因为写入失败影响业务（预算、暂停）。
3. **按 key 分桶限速**：不同 advertiser 用不同的限流桶（`map[advertiser_id]*Limiter`），防止「一个广告主的突发打爆另一个」—— Go 限流器就是按 key 建桶。

一个典型参数模板（DV360 每账号）：

```text
读：pageSize=200，目标 2 req/s/广告主，重试退避 300ms 起 ×2，上限 30s，最多 5 次
写：单账号并发≤5，batch 大小 20~50，写失败子集延迟 60s 重放
全量拉取：按 advertiser 串行（避免多广告主并发叠加峰值）
```

#### 3.4.2 429 出现后怎么办（SOP）

```
看到 429
   ├─ 检查 dv360_get_quota → 天配额快耗尽？
   │      ├─ 是 → 报错拉最小必要字段、加大 pageSize、或申请提额（改 quota 配置）
   │      └─ 否 → 查 dv360_list_rate_limits → 分钟速率超了？
   │              ├─ 是 → 本地降速（退避 + jitter），别死等窗口
   │              └─ 否 → 查代码：是否有「单次调用内循环请求」的 bug（如分页写错导致死循环）
   └─ 记录 429 上下文（时间、广告主、方法、重试次数），进 usage_stats 统计
```

**关键纪律**：429 不是「程序错误」，是「流量管理事件」；不要因为它改业务逻辑，而是改「发送节奏」。

#### 3.4.3 提额申请

- 在 Google Cloud Console → API & Services → Quotas 里可视化调图，申请每日配额 / 每分钟配额提升通常 1~2 个工作日。
- 举证：提供「实际用量曲线 + 峰值」的截图（来自 `dv360_list_usage_stats`），提额更顺利。

### 3.5 踩坑清单（Production 血泪教训）

#### 3.5.1 坑 1：明明有配额却还 429

**现象**：`dv360_get_quota` 显示每日额度只用 30%，但请求照样 429。
**根因**：撞的不是「日配额」而是「**单账号分钟速率**」或「**并发上限**」——同一 advertiser 短时间轰几百个请求（例如无脑循环 list 单页），分钟速率立刻爆。
**修复**：
1. 本地滑动窗口限流器（2.7.3）把每分钟请求数主动压到官方限制内（留 20% 余量）；
2. list 一次性 pageSize 拉满，**减少往返次数**；
3. 严禁对同一资源「无上限循环拉单页」，永远用 pageToken 续拉。

#### 3.5.2 踩坑 2：分页丢数据（弱一致性）

**现象**：全量同步后 count 与 UI 不符，少了几条 LineItem。
**根因**：游标分页 + 并发写入的**弱一致**：拉第 2 页时，前一页范围内的数据被删除/变更，可能「漏一条」。
**修复**：
1. 同步窗口内**尽量避免并发写**（晚上只拉，白天才写）；
2. 入库后跑「**完整性校验**」：统计 = 各 parent 下对象数之和，与 UI 对账（出入报警）；
3. 对关键表在 BigQuery 侧建 **唯一约束**，重复写入自然被拒/覆盖。

#### 3.5.3 踩坑 3：refresh token 过期（用户授权型）

**现象**：跑了 3 个月的项目，某天突然全面 401。
**根因**：OAuth refresh_token **失效**（用户撤销授权 / token 最长寿命到期 / 客户端配置改动）。
**修复**：
1. 项目初始化时就用 `dv360_validate_credentials` 自检并保存「凭证有效快照」；
2. 监控里对 `401 + "invalid_grant"` 立即告警（而不是等第 3 天用户报告）；
3. 服务账号认证（JWT）不受 refresh token 影响——**能用服务账号就用服务账号**（见 2.2.1）。

#### 3.5.4 踩坑 4：字段变更导致解析失败

**现象**：`KeyError: 'lineItemId'` / `json.decoder.JSONDecodeError` 偶发。
**根因**：DV360 每季度功能上线，**字段会被重命名 / 迁移 / 拆分子对象**（breaking change 有专员通知，但小变化防不胜防）。
**修复**：
1. 请求时用 `fields` 参数（部分响应）**显式点名要的字段**，缩小爆炸半径；
2. 解析器里统一 `get("field")` + **默认值兜底**，避免 KeyError 崩全任务；
3. 每次发布（release）后跑一轮「**字段烟测**」：拉 1 页数据断言关键字段类型，失败即告警。

#### 3.5.5 踩坑 5：webhook 丢失事件

**现象**：审批状态变化没触发回调，等了 3 小时 UI 已通过但系统还是旧状态。
**根因**：回调端点夜里 JVM OOM / 网络分区，事件没投递（webhook 是 best-effort）。
**修复**：
1. 按 2.5.2 的「**唤醒信号**」模型：收到事件只做「拉最新状态」；
2. 把 Webhook 和**定期轮询**双轨运行，水标推到底；
3. `dv360_test_webhook` 每部署后手动跑一次，验证 endpoint 可达性 + 签名校验链是否通。

#### 3.5.6 踩坑 6：账号权限不足（403）

**现象**：API 调用返回 403 PERMISSION_DENIED，但 UI 上明明能看到数据。
**根因**：**API 用户 ≠ 登录用户**。服务账号授权定义在 Partner/广告主用户列表（`dv360_list_permission_users`），员工登录的账户权限高，API 服务账号权限低。
**修复**：
1. 检查 `dv360_list_permission_users(advertiser_id)`，确认服务账号 client_email 在授权名单里且有相应角色；
2. 权限配置后用 `dv360_validate_credentials` + 一个轻量请求（如 `list_advertisers` ）自检；
3. 各广告主账号可能权限不同，**全量遍历时对 403 单独兜底并告警**（不是整个任务失败，而是标记「此账号跳过」）。

#### 3.5.7 踩坑 7：批次「假成功」

**现象**：batch 返回 200，业务以为全成功，结果漏创建了 20%。
**根因**：DV360 batch **部分成功**——响应里每条结果都带 error；只看外层 200 是「假成功」。
**修复**：永远解析 `resp["lineItems"]` 的逐条 error；成功/失败分表；失败子集进重试队列。

#### 3.5.8 踩坑 8：micros 单位错误

**现象**：预算同步后预算写成 $0.0001。
**根因**：把报表层的**美元金额**直接当 `budgetMicros` 传 —— 少了 6 个零。
**修复**：**两套单位彻底分开**：报表字段（美元小数）与对象字段（micros 整数）之间专门写 `usd_to_micros()` / `micros_to_usd()`，注释标注，不让裸的数字代码里到处传。

#### 3.5.9 踩坑 9：时区错位导致报表少一天

**现象**：每日同步总是缺「昨天」的数据。
**根因**：DV360 报表按**广告主时区**（如 Asia/Shanghai）分区，而脚本按 UTC 计算「昨天」，边界对不上。
**修复**：**所有日期边界用广告主所在地时区换算**，仓库里统一 `tz = pytz.timezone(advertiser_timezone)` 后再取 start/end，别用 UTC 直接截断。

#### 3.5.10 踩坑 10：跨系统 ID 映射混乱

**现象**：CM360 里的 campaignId 与 DV360 的 campaignId 混存一列，join 出错的「幽灵数据」。
**根因**：同一「营销活动」在两个系统有**两套 ID**，且时常并不同名。
**修复**：在数据仓库建 **id_map** 表维护 `(platform, external_id, entity_type, local_id)`，**唯一主键 = (platform, external_id, entity_type)**；所有跨系统 join 走它，不留硬编码映射。

CHUNK_END_B_7K2M
EOF
wc -l '/Users/yanping.ma/ryan-personal-knowledge/knowledge/advertising/dv360/dv360-integration-patterns-deep.md'
