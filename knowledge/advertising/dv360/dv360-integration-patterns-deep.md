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

### 3.6 集成模式对比总结（工程选型）

不同的集成需求对应不同「集成模式」，下表帮你在动手前先做对选型。这是本文「集成模式」维度的核心结论表。

| 模式 | 触发方式 | 数据方向 | 实时性 | 一致性保证 | 典型场景 | 推荐程度 |
|------|----------|----------|--------|-----------|----------|----------|
| 直接 API 拉取（对象 + 报表） | 调度/水位 | 读 | 准实时（T+1 为主） | 最终一致（需主键去重） | 对象全量/增量同步、报表落仓 | ⭐⭐⭐⭐⭐ |
| Google 官方 BigQuery 导出 | 平台定时 | 读 | 日级 | 弱一致（替换/增量可配） | 稳定周期报表落仓（免自写拉取） | ⭐⭐⭐⭐ |
| Webhook 事件通知 | 事件驱动 | 读（触发） | 秒级 | best-effort（会丢/重复） | 状态变更提醒、审批通知 | ⭐⭐⭐（需轮询兜底） |
| 批次写（batchUpdate/batchCreate） | 编排 | 写 | 秒级 | 部分成功（逐条解析） | 批量建 LineItem、批量改预算 | ⭐⭐⭐⭐⭐ |
| 审计/活动日志拉取 | 调度 | 读 | 分钟级 | 强一致（平台侧记录） | 合规审计、运维排障 | ⭐⭐⭐⭐ |
| ADH 联合查询 | 手动/编排 | 读（聚合） | 批处理 | 隐私聚合（/30 掩码） | 增量归因、跨设备、排除验证 | ⭐⭐⭐ |
| 跨平台统一客户端 | 同步 | 双向 | 取决平台 | 各自平台基准 | 多渠道投放统一管理 | ⭐⭐⭐⭐⭐ |

**选型口诀**：
- **稳定的周期性数据（报表）→ 尽量用官方导出或水位拉取**，别用实时/Webhook。
- **需要强实时响应（如预算突然清零要立刻停投）→ Webhook 当唤醒，但要配轮询兜底**。
- **批量写入 → 永远批次化 + 逐条解析 + 失败子集重放**。
- **安全归因/隐私 → 用 ADH，不要自己拿用户级数据拼接**。

### 3.7 增量同步 vs 全量同步（数据同步策略）

DV360 对象（LineItem / Creative / IO）与报表的同步策略选择直接决定配额消耗与数据准确性：

| 维度 | 全量同步 | 增量同步 |
|------|----------|----------|
| 数据量 | 每次拉全部 | 只拉变化/新增 |
| 配额消耗 | 高 | 低 |
| 复杂度 | 低（先清后全量写） | 高（要 change log / 水位） |
| 一致性 | 天然完整 | 依赖事件/水位准确性 |
| 适用于 | 首次初始化、低频 | 每日高频增量 |

**工程建议：混合策略**：
1. **首次**：全量拉取 + BigQuery `WRITE_TRUNCATE` 分区；
2. **每日**：按水位增量拉（只拉 `updateTime > watermark` 的对象 + 报表按天范围）；
3. **周期性对账**：每周/每月对全量计数与 UI 对账，发现漂移则触发一次全量重拉。

`dv360_list_audit_logs` / `dv360_list_activity_logs` 在增量场景是极好的「变更信号源」：从审计日志里拿到「某实体被更新过」，再去精确拉取该实体，能大幅省配额、保证不漏。

### 3.8 任务调度与重跑语义（Scheduler & Replay）

集成平台的任务调度要处理「失败重跑」的语义，三条铁律：

1. **幂等重跑**：同一任务的重跑必须产生一致结果。报表用「分区先 TRUNCATE 再写」，「对象」用主键 UPSERT；重跑不产生重复行。
2. **水位只在成功后推进**：`watermark` 推前一定发生在「该天数据全部成功入库」之后；失败则水位停留，下次自动补拉。
3. **死信 + 重试队列**：批次失败的子集、429 超限放弃的请求，统一进死信表（含原始 payload、错误、时间），次日/告警后重放。**重投放进重试队列，而不是回调点重跑主流程**。

一个合理的 DAG（Airflow）设计：

```
daily_dv360_sync
├── 01_check_credentials        # dv360_validate_credentials 自检
├── 02_sync_objects             # 对象增量（LineItem/Creative/IO）
├── 03_ingest_report            # 报表落 BigQuery（水位范围）
│     └── 03a_replay_deadletter # 失败子集重放（幂等）
├── 04_forward_watermark        # 推进水位
├── 05_quota_and_health         # dv360_get_quota / usage_stats / 健康检查
└── 06_alert_if_needed          # 异常告警
```

### 3.9 与 CM360 联合落仓的工程细节

当 DV360（投放）与 CM360（转化测量）联动入库时，最容易出问题的就是「跨系统 join」。一个规范的落地模板：

```python
# scripts/merged_measurement_ingest.py —— DV360 + CM360 联合入库
# 目标：生成“投放×转化”事实表 daily_adx_cm_fact

# 1) DV360 侧：投放明细（impr/click，按 line_item + creative + date）
dv = ingest_report_to_bigquery(client_dv, adv_id, start, end,
                               project, "ads", "dv360_fact")

# 2) CM360 侧：Floodlight 转化（按 placement + floodlight_activity + date）
cm = ingest_cm360_conversions(client_cm, adv_id, start, end,
                              project, "ads", "cm360_fact")

# 3) 合并（在 BigQuery 用 SQL，而不是应用层 join 大表）
#    SELECT ... FROM dv360_fact d
#    LEFT JOIN cm360_fact c ON d.placement_id = c.placement_id AND d.date = c.date
#    注意：转化与曝光不是 1:1，必须先按“归因模型”在 CM 侧聚合，再 join。

# 4) 单位统一 + 主键检查
assert_all_rows_valid(dv, cm)   # 空指针/缺主键校验
```

要点：**合并动作放数据库（BigQuery SQL）做，别在应用层内存 join 上百万行**；且转化先在 CM360 侧按「归因模型 + 窗口」聚合，再与架构层 join，否则 JOIN 爆炸。

### 3.10 面向「规模化」的架构（多广告主 / Register 模式）

当从「1 个广告主」扩展到「几十个广告主」，要引入 **Register 模式 + 分表分桶**：

```python
# registries.py —— 广告主注册表驱动流水线
ADVERTISERS = [
    {"advertiser_id": "A111", "name": "华东品牌", "timezone": "Asia/Shanghai", "enabled": True},
    {"advertiser_id": "B222", "name": "华南品牌", "timezone": "Asia/Shanghai", "enabled": True},
    {"advertiser_id": "C333", "name": "北美业务", "timezone": "America/Los_Angeles", "enabled": True},
    # 启停某个广告主 = 改 enabled 字段，不需要动代码
]

def run_all():
    for adv in [a for a in ADVERTISERS if a["enabled"]]:
        try:
            daily_sync(adv["advertiser_id"], tz=adv["timezone"])
        except PermissionDenied:
            mark_skipped(adv["advertiser_id"])   # 403 单独兜底，不崩全局
            alert(adv["advertiser_id"], "permission_denied")
```

再叠加：
- **分库/分表**：每个广告主独立事实表分区，或用 `advertiser_id` 作为主键第一列 + 分区键。
- **配置驱动**：`timezone / 同步开关 / 拉取 pageSize / 限流桶` 全部进配置，不改代码就能扩新广告主。
- **配额治理**：每个广告主独立限流桶，防止单个广告主突发打爆全局令牌桶。

这一节的核心：**集成平台的生命力取决于「按配置扩展」而非「按代码硬编码」**。把「新广告主接入」从「改代码 + 发版」变成「登记一行配置」，是规模化团队最重要的杠杆。

---
### 3.11 工具方法 ↔ 集成场景映射表（来自 ad_platform_api.py 的真实封装）

下表把 `ad_platform_api.py` 中真实存在的 DV360 封装方法，按「集成场景」归类并标注用途。做技术方案（PRD → 设计）时，直接从这里挑方法，避免「重新发明轮子」。

#### 3.11.1 认证 / 账号 / 权限（对接 L1~L2）

| 方法 | 用途 | 集成场景 |
|------|------|----------|
| `dv360_auth` | 发起/完成 OAuth 认证（取 token） | 首次接入 / token 失效重授权 |
| `dv360_validate_credentials` | 校验凭证是否有效 | 每天任务开头的自检 Step |
| `dv360_get_customer` / `dv360_list_customers` | 读当前可用账号 | 多账号权限审计 |
| `dv360_get_quota` | 查配额使用 | 配额监控 / 提额举证 |
| `dv360_list_usage_stats` | 查用量统计 | 峰值分析与限流调参 |
| `dv360_list_rate_limits` | 查速率限制 | 客户端限流器参数 |
| `dv360_list_api_versions` / `dv360_get_api_version` | 查 API 版本枚举/详情 | 升级前的版本兼容检查 |
| `dv360_list_permission_users` / `dv360_add_permission_user` / `dv360_remove_permission_user` | 管理广告主 API 用户 | 服务账号授权与回收 |
| `dv360_list_partner_links` / `dv360_create_partner_link` / `dv360_delete_partner_link` | 管理 Google Ads↔DV360 关联合约 | 跨产品账号打通 |

#### 3.11.2 对象同步（拉全量 / 增量 / 对账）

| 方法 | 用途 | 集成场景 |
|------|------|----------|
| `dv360_list_advertisers` / `dv360_get_advertiser` | 广告主列表/详情 | 账号注册表初始化 |
| `dv360_sync_advertiser` | 广告主对象同步 | 全量/增量初始化广告主 |
| `dv360_list_line_items` / `dv360_get_line_item` | LineItem 列表/详情 | 投放对象同步 |
| `dv360_list_flights` | Flight 列表 | 投放周期同步 |
| `dv360_list_creatives` | Creative 列表 | 素材同步 / 审批查询 |
| `dv360_list_insertion_orders` | 订单项 IO 列表 | IO 层级同步 |
| `dv360_list_floodlight_configs` | Floodlight 配置组 | CM360 测量联动 |
| `dv360_list_proposals` / `dv360_accept_proposal` / `dv360_reject_proposal` | 交易/提案 | GAM/采购交易管理 |
| `dv360_list_placements` / `dv360_list_placements_by_line_item` | 版位列表 | 版位同步 |

#### 3.11.3 写入 / 批次操作（写侧）

| 方法 | 用途 | 集成场景 |
|------|------|----------|
| `dv360_create_line_item` / `dv360_update_line_item` | 建/改 LineItem | 排期自动建单 |
| `dv360_pause_line_item` / `dv360_resume_line_item` / `dv360_delete_line_item` | 停/启/删 | 预算改为自动停投 |
| `dv360_batch_update_line_items` | 批量更新（部分成功需逐条解析） | 大规模调整 |
| `dv360_batch_create_line_items` | 批量创建 | 排期批量建单（见 3.3） |
| `dv360_create_creative` | 建素材 | 素材自动化上传 |
| `dv360_sync_report` | 定义报表并触发落地 | 报表一体落仓 |

#### 3.11.4 报表 / 数据出口（读侧 + 落仓）

| 方法 | 用途 | 集成场景 |
|------|------|----------|
| `dv360_get_report` | 查询报表（维度+指标+日期） | 报表拉取落 BigQuery |
| `dv360_get_report_metrics` / `dv360_list_report_metrics` | 报表可用指标 | 指标清单（写查询前先看） |
| `dv360_list_report_dimensions` | 报表可用维度 | 维度清单 |
| `dv360_get_breakdown_report` | 分时/细分报表 | 时段、设备、地域细分 |
| `dv360_list_budget_allocations` / `dv360_update_budget_allocation` | 预算分配 | 预算治理 |
| `dv360_get_account_health` | 账号健康度 | 健康监控 |
| `dv360_list_cross_channel_reports` | 跨渠道报表 | 全渠道汇总看板 |

#### 3.11.5 事件 / 运维可观测性

| 方法 | 用途 | 集成场景 |
|------|------|----------|
| `dv360_list_webhooks` / `dv360_create_webhook` / `dv360_delete_webhook` / `dv360_test_webhook` | Webhook 全生命周期管理 | 事件驱动（见 2.5） |
| `dv360_list_audit_logs` | 审计日志 | 合规 / 排障「谁改了」 |
| `dv360_list_activity_logs` | 活动日志 | 平台活动追踪 |
| `dv360_list_notification_preferences` / `dv360_update_notification_preferences` | 通知偏好 | 告警配置 |

#### 3.11.6 定向 / 受众（与 Google Ads 联动）

| 方法 | 用途 | 集成场景 |
|------|------|----------|
| `dv360_list_audiences` / `dv360_list_dynamic_audiences` | 受众列表 | 受众同步 |
| `dv360_list_targetings` / `dv360_list_targeting_units` | 定向单元 | 定向同步 |
| `dv360_create_targeting_unit` / `dv360_update_targeting_unit` / `dv360_delete_targeting_unit` | 定向写操作 | 定向自动化 |
| `dv360_list_keyword_targeting` / 系列 `*_targeting` 变体 | 关键词/地域/设备等定向明细 | 定向维度全量同步 |
| `dv360_list_dimension_values` | 维度值枚举 | 定向值下拉/校验 |

#### 3.11.7 预测 / 优化（决策支持）

| 方法 | 用途 | 集成场景 |
|------|------|----------|
| `dv360_get_pacing_rate` | 投放速率 | 预算执行监控 |
| `dv360_get_performance_forecast` / `dv360_list_budget_forecasts` / `dv360_list_reach_forecasts` | 效果/预算/触达预测 | 排期规划 |
| `dv360_list_bid_recommendations` / `dv360_update_bid_recommendation` | 出价建议 | 优化自动化 |
| `dv360_list_budget_recommendations` / `dv360_update_budget_recommendation` | 预算建议 | 预算优化 |
| `dv360_list_recommendations` / `dv360_apply_recommendation` / `dv360_dismiss_recommendation` | 平台建议管理 | 建议决策工作流 |
| `dv360_get_auction_insights` / `dv360_list_auction_performance` / `dv360_list_bid_performance` | 竞价洞察 | 竞争分析 |

> 用法提示：**方案评审时，先对照本表确认「已有封装可用」，再决定是否要「新写」**。能复用 `dv360_*` 封装就不要裸写 requests，这既是工程效率，也是代码一致性（统一重试/限流/响应封装）。

### 3.12 安全与合规（集成常被忽略的一环）

集成平台权限大、数据敏感，务必落实：

1. **最小权限**：服务账号只给「需要的广告主 + 需要的角色」，别给超级管理员；`dv360_remove_permission_user` 及时回收离职/下线账号。
2. **密钥托管**：Service Account 私钥进 KMS / Secret Manager，代码里零硬编码（`ad_platform_api.py` 从 `config/ad_platform_credentials.json` 读，但生产建议改从 Secret 服务注入）。
3. **审计留存**：所有 API 写操作记录到审计表（操作者、时间、payload 摘要），与 `dv360_list_audit_logs` 双份留痕。
4. **数据脱敏与最小化**：DV360/CM 明细含用户级（Cookie/Device ID）时，入库前做哈希或按业务只需聚合；涉及跨设备/隐私分析走 ADH。
5. **传输安全**：全 HTTPS；token 只在内存/内存缓存，不落日志（日志截断前 50 字符即可，参考 `dv360_client.py` 的 `self.access_token[:50]`）。

---
---

## 四、常见问题与排查

### 4.1 高频错误速查表（先看这张表）

| 错误/现象 | 状态码 | 常见根因 | 快速处置 |
|-----------|--------|----------|----------|
| 401 Unauthorized | 401 | token 过期 / 无效 | 刷新 token；JWT 重签；检查 `dv360_validate_credentials` |
| 403 Permission Denied | 403 | 服务账号未被授权到该广告主/角色不足 | `dv360_list_permission_users` 检查授权；`dv360_list_partner_links` 检查关联合约 |
| 404 Not Found | 404 | 父级 ID 错 / 资源被删 / 层次路径错 | 核对 `advertiserId/lineItemId` 路径；先 `list` 确认真实 ID |
| 429 Too Many Requests | 429 | 日配额耗尽或分钟速率超限 | 尊重 Retry-After；本地退避；查 quota/usage_stats |
| 400 Bad Request | 400 | 参数不合法 / `updateMask` 含只读字段 | 核对 payload 字段；用 `fields`/`updateMask` 收窄；查看错误 message |
| 字段 not found / KeyError | 200 但解析失败 | 字段被迁移/改名（breaking change） | 用 `fields` 部分响应；解析器 get() 兜底；release 后烟测 |
| 分页不全 | 200 但少数据 | 游标弱一致 + 并发写 | 同步窗口别并发写；完整性对账；唯一约束 |
| batch「假成功」 | 200 | 批次部分成功，外层看不出来 | 逐条解析 `lineItems[i].error`；失败子集重放 |
| 创建重复 | 200 | POST 不幂等 + 重试 | 先查再建 + 幂等映射表 |
| 数据不同步 | 看场景 | webhook 丢失 / 水位未推进 / ID 映射错 | 事件后主动 GET 最新；水位失败不推进；查审计/活动日志 |

### 4.2 逐步排查流程（决策树）

#### 4.2.1「API 直接报错」如何定位

```
第一步：确认是认证/权限还是业务
  resp.status_code
   ├─ 401/403  → 凭证层（见 4.3）
   ├─ 429      → 流量层（见 4.4）
   ├─ 400      → 请求参数层（见 4.5）
   └─ 5xx      → 平台侧故障（重试，退避）

第二步：把原始响应完整打印出来
   resp.text[:200]  —— dv360_client.py 已默认打印 Response
   不要只看 status，要读 error message 里的 detail

第三步：定位到代码层
   - 是每次 /set 都能复现？→ 参数/权限问题
   - 是偶发 / 高峰出现？→ 限流 / 弱一致问题
```

#### 4.2.2「任务层面出问题」（报错被吞）

很多线上问题不是 API 报错，而是「数据层面不对劲」。用下面 6 问排查：

1. **水位推了没？** → 若水位停滞，先看 3.5.2（分页丢）+ 3.8（水位语义）。
2. **入库行数与源对得上吗？** → 跑完整性对账 SQL，比 UI count。
3. **是单位错了吗？** → 检查 micros / 美元换算，看金额是否差 10^6。
4. **是时区错了吗？** → 检查日期边界是否用广告主时区。
5. **是 ID 混了吗？** → 查 id_map 主键是否 (platform, external_id, entity_type)。
6. **是权限漂移了吗？** → 查 `dv360_list_permission_users` + 审计日志。

### 4.3 认证/权限类 FAQ

**Q：token 明明刚刷新，还是 401？**
- 检查 scope 是否覆盖 `display-video`；检查 JWT 的 `exp` 别超过服务账号上限；检查请求头 `Authorization: Bearer <token>` 的 token 是否完整（别截断）。
- 服务账号认证下 401 多为「JWT 签名/aud 错误」或「scope 不对」；`dv360_validate_credentials` 可复现。

**Q：UI 能看到数据，API 却 403？**
- 见 3.5.6：**API 用户 ≠ 登录用户**。到 DV360 UI 的 Partner/广告主用户列表，把服务账号 client_email 加进授权名单、给足角色。
- 若是「Google Ads 关联账号」读取，检查 `dv360_list_partner_links` 是否已创建关联合约。

**Q：refresh token 过期怎么办？**
- 用户授权型：走 `dv360_auth` 重新授权（弹 OAuth 同意），并监控 `401 + invalid_grant`。
- 更省心：改服务账号（JWT）认证，不依赖 refresh token。

### 4.4 限流/配额类 FAQ

**Q：为什么有配额还 429？**
- 撞的是「分钟速率」或「单账号并发」，不是日配额（见 3.5.1）。本地滑动窗口限流 + 尊重 Retry-After。

**Q：Retry-After 很长，等还是不等？**
- 若 `Retry-After < 15s`：尊重它，等待后重试（1~2 次）。
- 若很长（分钟级）：说明命中严重限制，**不要原地空等**，改为「登记到重试队列、稍后再放」，避免阻塞整条流水线。

**Q：如何判断要不要申请提额？**
- 连续多天日配额用 > 80%，且 `dv360_get_quota` 显示确实命中 daily limit → 提额；若只是瞬时峰值 429 → 降速即可，不提额。

**Q：429 的 usage_stats 怎么看？**
- `dv360_list_usage_stats` 给出按时间维度的被限流次数。若「被限流集中在同一广告主同一方法」，就是代码里没分桶/没 sleep / 循环拉单页。

### 4.5 数据/字段/解析类 FAQ

**Q：字段 not found / 解析失败怎么办？**
- 用 `fields` 参数显式点名；解析器 `get() + 默认兜底`；每次 release 后跑「字段烟测」（拉 1 页断言类型）。字段迁移是不可控的，只能缩小爆炸半径 + 及时告警。

**Q：分页拉不全怎么办？**
- 确认是用 nextPageToken 串行续拉、没漏页；同步窗口别并发写；入库后跑完整性对账；必要时对结果按实体 ID 去重。

**Q：micros 和美元的坑怎么避？**
- 报表金额字段（美元小数）与对象预算字段（micros 整数）是两套单位；专门写 `usd_to_micros()` / `micros_to_usd()`，不在业务代码里裸传数字。

**Q：入库出现数据不同步 / 对不上？**
- 排查顺序：时区 → 单位 → ID 映射 → 完整性校验 → 审计/活动日志。多数「对不上」是这四类之一。

### 4.6 写入/批次类 FAQ

**Q：批次返回 200 却不全成功？**
- 见 3.5.7：解析 `lineItems[i].error`；把成功/失败分表；失败子集进重试队列。

**Q：创建重复了怎么办？**
- POST 不幂等 + 重试导致的；`dv360_delete_line_item` 清理误建的重复项；上线后「先查再建」。

**Q：updateMask 是什么？不传会不会覆盖整条？**
- `updateMask` 精确定义要 patch 的字段，避免整对象覆盖（把预算外的字段误伤）。批量更新务必带对 `updateMask`。

### 4.7 Webhook/事件类 FAQ

**Q：webhook 没触发怎么办？**
- 先 `dv360_test_webhook(webhook_id)` 测 endpoint 可达性 + 签名；再确认 `dv360_list_webhooks` 里事件类型注册对了；最终用「轮询兜底」保证不漏（webhook 是 best-effort）。

**Q：webhook 事件重复 / 乱序？**
- 回调要幂等（同一事件处理多次无副作用）；状态以「收到事件后主动 GET」为准，不靠事件 payload 里的状态。

**Q：怎么防止伪造回调？**
- 用 `dv360_test_webhook` 返回的签名密钥校验回调头签名；失败丢弃。

### 4.8 排障日志示例（真实形态）

一个典型的「403 → 权限 → 修复」过程的日志形态：

```
[2026-08-14 06:31:01] INFO  daily_dv360_sync started, adv=A111
[2026-08-14 06:31:02] ERROR GET /advertisers/A111/lineItems -> 403
  resp: {"error":{"code":403,"status":"PERMISSION_DENIED",
         "message":"User does not have permission to access advertiser A111"}}
[2026-08-14 06:31:03] INFO  dv360_list_permission_users(A111) -> [user_a, user_b]
  # 发现缺 service-account@project.iam.gserviceaccount.com
[2026-08-14 06:31:04] INFO  dv360_add_permission_user(A111, email=..., role=ADVERTISER_EDITOR)
[2026-08-14 06:31:05] INFO  dv360_validate_credentials -> True
[2026-08-14 06:31:06] INFO  re-run step 02_sync_objects ... OK
```

排障要诀：**每个失败都带「响应原文」+「上下文（广告主/方法/token 前 3 位）」**，可复现、可追责；绝不要只打 "ERROR call failed"。

---
---

## 五、自测题

> 面向「DV360 系统集成工程师」的进阶自测。每题先思考，再点开答案核对。重点考察：分页/限流/幂等/单位/集成边界这些实战能力，而非背端点。

### 5.1 题目

**Q1（限流）**：某全量同步脚本在 `advertiser A` 上连续 500 个请求撞 429，但 `dv360_get_quota` 显示日配额只用了 30%。可能的原因是什么？分别给出根因判断与处置。

**Q2（单位）**：你的看板把 DV360 报表金额字段直接当成预算预算写入 LineItem，结果预算从 $1000 变成了 $0.001。请说明发生了什么，并给出修复与预防方案。

**Q3（分页）**：游标分页（pageToken）为什么不能直接用「页码」跳页？全量拉取时如何防止弱一致性导致的数据遗漏？给出至少两条工程措施。

**Q4（幂等+批次）**：batchUpdate 返回 HTTP 200，但业务发现漏更新了若干 LineItem。请解释为什么，并给出正确的客户端处理方式。

**Q5（集成边界 + Webhook）**：审批状态变更的 Webhook 偶尔丢失，导致系统状态滞后。请设计一个「既低延迟、又不丢最终状态」的接入方案，说明 Webhook 与轮询各承担什么角色。

<details>
<summary>查看 Q1 答案</summary>

撞 429 但日配额没满，几乎可以断定命中**分钟速率（per-minute rate）或单账号并发上限**，而不是每日配额。

- 根因判断路径：
  1. 用 `dv360_list_rate_limits()` 看当前速率限制（每分钟多少次、并发多少）；
  2. 用 `dv360_list_usage_stats(advertiser_id)` 看被限流次数的时间分布——若集中在某几分钟内，就是瞬时突发；
  3. 若本地没有限流器、或者对同一资源「无脑循环拉单页」，就会轰爆分钟速率。
- 处置：
  1. 客户端加**滑动窗口限流器**（按 advertiser_id 分桶），把每分钟请求数主动压到官方限制（留 20% 余量）；
  2. list 一次性把 `pageSize` 拉满，减少往返；
  3. 尊重 `Retry-After`，429 用指数退避 + 抖动，不疯狂重试；
  4. 若确实是日配额瓶颈（这里不是），才申请提额并举证 `dv360_get_quota` 曲线。

> 这段话同时解释了一个工程纪律：**「有配额却 429」多半是速率/并发问题，不是配额问题，处置方式是削峰而不是提额。**
</details>

<details>
<summary>查看 Q2 答案</summary>

发生的是 **micros（微元）与「美元小数」单位混淆**：预算 = $1000 应写入 `budgetMicros = 1_000_000_000`（1000 × 10^6），但你把报表返回的字段（如 `TOTAL_MEDIA_COST` 是美元小数 1000.0）原样写进去，等于把 $1000 当成 1000 micros = $0.001，差了 10^6 倍。

- 立即修复：把写错的 LineItem 预算改回正确值。
- 预防：
  1. 报表侧金额字段（美元小数）与对象侧预算字段（micros 整数）**彻底分开**；
  2. 封装 `usd_to_micros()` / `micros_to_usd()`，业务代码只调函数、不含裸数字；
  3. 入库/写入前做**范围断言**（如预算 micros 必须在合理区间，过小即报警）。

> 教训：DV360 里「金额/时间的 micros」与「报表的美分美元」是两套口径，接口层、数据层必须各自统一并显式换算。
</details>

<details>
<summary>查看 Q3 答案</summary>

游标分页（pageToken）**不强依赖「偏移量」，而是由服务端生成一个代表「当前位置」的不透明 token**，因此无法直接构造「第 5 页」——必须持有上一页返回的 `nextPageToken` 才能请求下一页。页码式跳页在游标语义下不存在。

防止全量拉取时弱一致性导致遗漏的工程措施：
1. **串行消费 pageToken**，不要并发请求多个 token（并发会放大一致性问题）；
2. 同步窗口内**避免并发写**（同一资源被边拉边改即产生漂移），只在低峰只读；
3. 入库后跑**完整性对账**：各父级下对象计数之和 vs UI count，出入即报警；
4. BigQuery 表建**唯一约束 / 主键**，重复写入被去重/覆盖，不产生脏数据；
5. 周期性触发一次全量重拉自愈。

> 核心：游标分页是「最终一致」的消费模型，要用「主键去重 + 完整性校验 + 周期全量」来兜底，而不是假定一次拉取一定完整。
</details>

<details>
<summary>查看 Q4 答案</summary>

batch 接口是**部分成功**语义：HTTP 200 只表示「请求被接受并执行」，不代表每一条都成功。响应体 `lineItems[]` 里**每条都带独立的 `error`**，有 error 的那条就是失败的。

正确处理：
1. **逐条解析** `resp["lineItems"][i].get("error")`，把成功与失败分开；
2. 失败的记入「死信队列」，包含原始 payload + 错误 + 时间；
3. 重试只重放**失败子集**，不要整批重放（否则已成功的会被重复/覆盖）；
4. 上线初期对 batch 结果做「预期成功数 vs 实际成功数」的断言，及时发现「假成功」。

> 教训：看待 batch，永远「逐条看待」，绝不要只信外层 HTTP 状态码。
</details>

<details>
<summary>查看 Q5 答案</summary>

Webhook 是 best-effort、可能丢失；轮询是可靠但延迟高。正确做法是**两者组合、角色分明**：

- **Webhook 只当「唤醒信号」**：收到审批事件后，不信任事件里的状态，而是**用事件里的实体 ID 主动 GET 拉最新真实状态**（`dv360_list_creatives` / 审批查询）。这样即使事件丢、重复、乱序，最终状态都以「拉取到的为准」（最终一致）。
- **回调端点必须幂等**：同一事件处理多次无副作用；
- **定期轮询兜底**：对关键实体（审批、报表就绪）保留水位驱动的增量轮询，防止 Webhook 丢失导致长期滞后；
- **签名校验 + 自检**：`dv360_test_webhook` 部署后验证 endpoint 可达与签名，防止伪造与配置错。

> 核心：在「低延迟」与「最终一致」之间，用「Webhook 触发 + 主动拉取 + 轮询兜底」的策略，既快又不丢。
</details>

---

## 六、动手验证（把知识变成能力）

### 6.1 最小可运行验证链

用现有工具脚本做一轮「读 + 写 + 观测」的自检，确认整套认知落地：

```bash
# 1) 认证自检（必须为 True）
python3 scripts/ad_platform_api.py dv360_validate_credentials

# 2) 拉一个广告主的 LineItem 列表，观察分页与字段
python3 scripts/ad_platform_api.py dv360_list_line_items --advertiser_id A111

# 3) 拉配额与用量，作为限流基线
python3 scripts/ad_platform_api.py dv360_get_quota --advertiser_id A111
python3 scripts/ad_platform_api.py dv360_list_usage_stats --advertiser_id A111

# 4) 查看已注册的 Webhook（若空，可先 create 再 test）
python3 scripts/ad_platform_api.py dv360_list_webhooks --advertiser_id A111

# 5) 报表定义 + 落地（演练 T+1 落仓主链路）
python3 scripts/ad_platform_api.py dv360_sync_report --advertiser_id A111 \
  --date_range_start 2026-08-01 --date_range_end 2026-08-07 \
  --dimensions LINE_ITEM_ID,CREATIVE_ID --metrics IMPRESSIONS,CLICKS

# 6) 审计日志（排障「谁改了」）
python3 scripts/ad_platform_api.py dv360_list_audit_logs --advertiser_id A111
```

> 注意：具体 CLI 参数名以 `ad_platform_api.py` 实际 `argparse` 定义为准（以上为示意）。

### 6.2 演练建议（由易到难）

1. **只读打通**：完成 6.1 的 1~3，理解认证、分页、配额。
2. **写一条 + 回读**：用 `dv360_create_line_item` 建一条测试 LineItem，`dv360_get_line_item` 回读，核对 budgetMicros。
3. **批次 + 部分成功演练**：给批量更新混入一条非法参数，观察「部分成功 + 逐条 error」，写一个处理失败子集的函数。
4. **Webhook ping 通**：注册一个本地回调（可用 webhook.site），`dv360_test_webhook` 测试，验证签名校验。
5. **模拟弱一致**：在拉取 LineItem 全量同时人工暂停一条，观察分页漏/重，跑完整性对账。

### 6.3 交付物 checklist（一套合格的 DV360 集成平台）

- [ ] 统一客户端封装（业务层无裸 URL）
- [ ] 认证自检 + 凭证轮换预案（`dv360_validate_credentials` 接入监控）
- [ ] 限流器（按广告主分桶）+ 429 退避与死信
- [ ] 分页封装（串行消费 pageToken）+ 完整性对账
- [ ] 批次写逐条解析 + 失败子集重放
- [ ] micros/时区/ID 三套统一
- [ ] 水位驱动增量同步 + 幂等重跑
- [ ] 监控：配额 / 429 / 水位 / 凭证 / 字段烟测告警
- [ ] Webhook（唤醒 + 主动拉取）+ 轮询兜底
- [ ] 审计与 id_map 落地
---

## 附录 A：Go 端到端完整实现（DailySync 服务）

把 2.7 的通用客户端 × 3.1 的同步流程，组合成一个**可直接扩展**的 Go DailySync 服务骨架。只依赖标准库 + 极少的仓库客户端，突出「重试/限流/分页/认证/落仓」五大件如何协同。

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"time"
)

// ---------- 1. 统一错误 ----------
type APIError struct {
	Code       int
	Message    string
	Retryable  bool
	RetryAfter time.Duration
}

func (e *APIError) Error() string {
	return fmt.Sprintf("gmp err: %d %s", e.Code, e.Message)
}

// ---------- 2. TokenProvider：JWT → access_token（服务账号） ----------
// 生产环境用 google.golang.org/api/option 或自实现 JWT；这里给流程骨架。
type TokenProvider struct {
	clientEmail string
	privateKey  string
	scope       string
	cache       string   // 缓存的 access_token
	expiry      time.Time
}

func (t *TokenProvider) Valid() bool { return t.cache != "" && time.Now().Before(t.expiry.Add(-60*time.Second)) }

// Refresh 每次在接近过期时由 do() 调用
func (t *TokenProvider) Refresh() (string, error) {
	// 1. 构造 JWT header{pyp:JWT,alg:RS256,kid} + payload{iss,sub,aud,iat,exp,scope}
	// 2. RS256 私钥签名
	// 3. POST https://oauth2.googleapis.com/token  grant_type=jwt-bearer
	// 4. 返回 access_token，缓存 expiry
	return "", nil // 占位：接入真实签名库
}

func (t *TokenProvider) Get() (string, error) {
	if t.Valid() {
		return t.cache, nil
	}
	tok, err := t.Refresh()
	if err != nil {
		return "", err
	}
	t.cache = tok
	return tok, nil
}

// ---------- 3. 限流器（按广告主分桶的滑动窗口） ----------
type limiter struct {
	ch chan struct{} // 简单令牌桶：capacity 个并行槽
}

func newLimiter(concurrency int, period time.Duration) *limiter {
	return &limiter{ch: make(chan struct{}, concurrency)}
}
func (l *limiter) acquire() { l.ch <- struct{}{} }
func (l *limiter) release() { <-l.ch }

// ---------- 4. 游标分页 ----------
type paginateFunc func(token string) (next string, items []json.RawMessage, err error)

func paginateAll(fn paginateFunc) ([]json.RawMessage, error) {
	var all []json.RawMessage
	token := ""
	for {
		next, items, err := fn(token)
		if err != nil {
			return nil, err
		}
		all = append(all, items...)
		if next == "" {
			break
		}
		token = next
	}
	return all, nil
}

// ---------- 5. DV360Client：把 限流→认证→重试→分页 组合 ----------
type DV360Client struct {
	base   string
	tokens *TokenProvider
	lim    *limiter
	httpDo func(ctx context.Context, method, url string, body any, hdr map[string]string) ([]byte, int, error)
}

const baseURL = "https://displayvideo.googleapis.com/v4"

// doRequest 单次请求（带动认证 + 简单重试）
func (c *DV360Client) do(ctx context.Context, method, path string, body any) (json.RawMessage, error) {
	c.lim.acquire()
	defer c.lim.release()

	tok, err := c.tokens.Get()
	if err != nil {
		return nil, err
	}
	url := c.base + path
	var lastErr error
	for attempt := 1; attempt <= 5; attempt++ {
		data, status, herr := c.httpDo(ctx, method, url, body,
			map[string]string{"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
		if herr != nil {
			return nil, herr
		}
		if status >= 200 && status < 300 {
			return data, nil
		}
		retryable := status == 429 || status >= 500
		lastErr = &APIError{Code: status, Retryable: retryable}
		if !retryable {
			return nil, lastErr
		}
		wait := time.Duration(1<<(attempt-1))*300*time.Millisecond + 100*time.Millisecond*time.Duration(attempt)
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(wait):
		}
	}
	return nil, lastErr
}

// ListLineItemsAll 业务方法：分页拉全量 ACTIVE LineItem
func (c *DV360Client) ListLineItemsAll(ctx context.Context, adv string) ([]json.RawMessage, error) {
	return paginateAll(func(token string) (string, []json.RawMessage, error) {
		path := fmt.Sprintf("/advertisers/%s/lineItems?pageSize=200&filter=entityStatus%%3D'ENTITY_STATUS_ACTIVE'", adv)
		if token != "" {
			path += "&pageToken=" + token
		}
		raw, err := c.do(ctx, "GET", path, nil)
		if err != nil {
			return "", nil, err
		}
		var page struct {
			LineItems      []json.RawMessage `json:"lineItems"`
			NextPageToken  string            `json:"nextPageToken"`
		}
		if err := json.Unmarshal(raw, &page); err != nil {
			return "", nil, err
		}
		return page.NextPageToken, page.LineItems, nil
	})
}

// ---------- 6. 落 BigQuery（示意） ----------
func upsertToBigQuery(ctx context.Context, rows []json.RawMessage) error {
	// 生产用 cloud.google.com/go/bigquery：
	//   - 分区表按 date 分区
	//   - 每行含主键(advertiser_id,date,line_item_id,...)
	//   - WriteDisposition=WRITE_TRUNCATE(当天分区) 或 Merge 去重
	log.Printf("ingesting %d rows", len(rows))
	return nil
}

// ---------- 7. 编排 DailySync ----------
func runDailySync(ctx context.Context) error {
	client := &DV360Client{
		base:   baseURL,
		tokens: &TokenProvider{},
		lim:    newLimiter(5, time.Minute), // 并发≤5
		// httpDo: realHTTP, // 生产注入 net/http.Do
	}
	advertisers := []string{"A111", "B222"}
	for _, adv := range advertisers {
		items, err := client.ListLineItemsAll(ctx, adv)
		if err != nil {
			// 403 单独兜底：跳过该广告主并告警，不崩全局
			if ae, ok := err.(*APIError); ok && ae.Code == 403 {
				log.Printf("SKIP adv=%s permission_denied", adv)
				continue
			}
			return err
		}
		if err := upsertToBigQuery(ctx, items); err != nil {
			return err
		}
	}
	return nil
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	if err := runDailySync(ctx); err != nil {
		fmt.Fprintln(os.Stderr, "daily sync failed:", err)
		os.Exit(1)
	}
	log.Println("daily sync done")
}
```

这个骨架把 2.7 的通用件与 3.1 的业务流程串成一条可运行的腿：**限流 → 认证 → 重试 → 分页 → 落仓**，且 403 单独兜底不崩全局。接入真实 `httpDo`、真实 JWT 签名、真实 bigquery 写入即可上生产骨架，后续扩展 `CreateLineItem` / `BatchUpdate` 走同一条 `do()` 通道即可保持行为一致。

---

## 附录 B：DV360 REST 端点 ↔ 封装方法速查表

把「真实 API 路径」与 `ad_platform_api.py` 的封装对应起来，写文档/排障时不必翻官方文档也能定位。

| 资源语义 | REST 路径（v4） | 封装方法（示例） |
|----------|------------------|------------------|
| 列出广告主 | `GET /advertisers` | `dv360_list_advertisers(partner_id)` |
| 广告主详情 | `GET /advertisers/{id}` | `dv360_get_advertiser(advertiser_id)` |
| 列出 LineItem | `GET /advertisers/{id}/lineItems` | `dv360_list_line_items(advertiser_id)` |
| 单 LineItem | `GET /advertisers/{id}/lineItems/{li}` | `dv360_get_line_item(advertiser_id, line_item_id)` |
| 建 LineItem | `POST /advertisers/{id}/lineItems` | `dv360_create_line_item(...)` |
| 批量更新 | `POST /advertisers/{id}/lineItems:batchUpdate` | `dv360_batch_update_line_items(updates)` |
| Flight 列表 | `GET /advertisers/{id}/flights?lineItemId=` | `dv360_list_flights(advertiser_id, line_item_id)` |
| Creative 列表 | `GET /advertisers/{id}/creatives` | `dv360_list_creatives(advertiser_id, line_item_id)` |
| 报表查询 | `GET/POST .../queries` / `queries/{id}:run` | `dv360_get_report` / `dv360_sync_report` |
| Floodlight 配置 | `GET /advertisers/{id}/floodlightGroups` 等 | `dv360_list_floodlight_configs(advertiser_id)` |
| 提案/交易 | `GET /proposals` | `dv360_list_proposals` / `dv360_accept_proposal` |
| 审计日志 | `GET .../auditLogs` | `dv360_list_audit_logs(advertiser_id)` |
| 活动日志 | `GET .../activityLogs` | `dv360_list_activity_logs(advertiser_id)` |
| 配额 | `GET /advertisers/{id}/quota` | `dv360_get_quota(advertiser_id)` |
| 用量统计 | `GET /advertisers/{id}/usageStats` | `dv360_list_usage_stats(advertiser_id)` |
| Webhook 管理 | `GET/POST/DELETE .../webhooks` | `dv360_list_webhooks` / `dv360_create_webhook` / `dv360_test_webhook` |
| 审计用户/权限 | `.../permissionUsers` | `dv360_list_permission_users` / `dv360_add_permission_user` |
| Partner 关联 | `.../partnerLinks` | `dv360_list_partner_links` / `dv360_create_partner_link` |

> 说明：以上路径为语义示意，`ad_platform_api.py` 各自封装对应实现，具体字段与 v4/v3 版本以官方文档为准。升级 API 前用 `dv360_list_api_versions` / `dv360_get_api_version` 核对兼容性。

---

## 附：更新记录与相关文档

| 日期 | 变更 |
|------|------|
| 2026-08-14 | 首次成文：GMP 集成定位、REST/认证/限流/重试/幂等/Webhook 原理、Python/Go 客户端工程、生产踩坑、FAQ、自测题、Go 端到端骨架 |

**参考与关联文档**（形成互补的知识网络）：
- `/knowledge/advertising/dv360/dv360-marketing-api-deep.md` —— API 端点实战与认证授权的端点级细节
- `/knowledge/advertising/dv360/dv360-architecture-deep.md` —— 账户层级与程序化购买架构
- `/knowledge/advertising/dv360/dv360-creative-brand-safety-deep.md` —— 创意与品牌安全
- `/knowledge/advertising/dv360/dv360-measurement-attribution-deep.md` —— 测量与归因
- `/knowledge/advertising/dv360/dv360-optimization-deep.md` —— 投放优化
- 脚本：`scripts/ad_platform_api.py`（dv360_* 统一封装）、`scripts/dv360_client.py`（JWT 客户端）、`scripts/api_common.py`（ApiResponse / BaseAdPlatformClient）、`scripts/google_ads_api.py`、`scripts/meta_api.py`（跨平台统一客户端模式）

> **一句话总结**：DV360 集成的本质是「在 GMP 的投放-测量-数据协作网络里，用一个强一致、可观测、幂等的客户端平台，把投放对象与报表安全地搬到你的数仓」。吃透分页/限流/重试/幂等/单位/认证这套「集成设计模式」，再差的网络与字段变更也拖不垮你的流水线。
---

## 附录 C：跨平台 API 设计模式对比（DV360 / Google Ads / Meta）

既然平台里有 `google_ads_api.py` 与 `meta_api.py`，把它们与 DV360 放在一起对照，能更清楚地看见「集成模式」的共性骨架与平台差异。这张表是「统一客户端」（3.2）之所以可行的底层依据。

| 维度 | DV360（display-video） | Google Ads（googleads v15+） | Meta Marketing API | TikTok Business API |
|------|------------------------|------------------------------|--------------------|---------------------|
| API 形态 | REST/JSON | gRPC + proto（也提供 REST 桥） | Graph API（REST style） | REST/JSON |
| 认证 | Service Account JWT / OAuth2 | OAuth2（refresh token + developer token） | 长期 token + app secret | access_token |
| 查询语言 | filter（AIP-160）+ fields | GAQL（`google_ads_query_language`） | GraphQL-like `fields` 选择 | params + filtering |
| 分页 | `pageToken`（游标） | 默认限额，靠 `LIMIT/OFFSET` 或批量 | `cursor`（Base64） | `page` + `page_size` |
| 限流 | 配额 + 速率 + 429 | 每分钟配额 + 429（含 per-customer） | rate limits + 429 | 频控 + 429 |
| 批次写 | `:batchUpdate`（部分成功） | `Mutate` 批量（逐条结果） | Batch API | 部分支持 |
| 字段选择 | `fields` 参数 | GAQL 显式 SELECT 字段 | `fields` 参数 | 无/少 |
| 部分成功 | 逐条 error | mutateResults 逐条 | 逐条 op result | 逐条 |

结论（对集成平台的启发）：

1. **四家本质都是「REST 或类 REST + token 认证 + 游标/偏移分页 + 5xx/429 可重试」**——所以 2.7 的 Go 客户端（限流→认证→重试→分页）四家都能套，只是参数形状不同。
2. **最需要适配的差异是「认证刷新」**：DV360 是 JWT 无状态刷新，Google Ads 是 refresh_token 刷新（易过期，见 2.2.3），Meta 是长 token + 校验。统一客户端里把 `GetToken()` 抽象出来，四家各实现刷新逻辑即可。
3. **字段选择能力差异大**：Google Ads 强约束（GAQL 必须显式列字段）；DV360 愿意支持 `fields`；Meta 也支持。解析器层面统一「get + 默认兜底」，可同时防四家的字段漂移。
4. **批次部分成功是公共特性**：四家都有「逐条结果」，客户端统一返回 `{success:[], failed:[{id,error}]}` 就能通吃。

### C.1 统一客户端要收敛的「三件套」接口

无论接入几家，统一客户端只需收敛三个抽象，即可获得极高复用率：

```go
// ① token：接入层只认这个接口
type TokenProvider interface {
	Get() (string, error)      // 自动刷新、缓存
}

// ② 请求：所有读/写都过这里（含限流/重试/认证/字段选择）
type Requester interface {
	Do(ctx context.Context, method, resource string, body any, fields []string) (json.RawMessage, error)
}

// ③ 分页：把“游标/偏移/页面”统一成迭代器
type Pager interface {
	Next() ([]json.RawMessage, bool, error)   // items, hasMore, err
}
```

只要这三件套稳定，业务层（同步、落仓、对账）就是「一份代码跑四家平台」。

### C.2 事件溯源（Event Sourcing）作为集成进阶

对「预算被谁改、为什么改、何时回滚」这类审计要求，可以在集成平台里引入**事件溯源**：

```
写操作(create/update/pause)
   → 记录 Event(实体内核，旧值，新值，操作者，时间，requestId)
   → 更新聚合(Aggregate: LineItem 当前状态 = 按序重放事件)
   → 对外读只读聚合
```

好处：
- 天然可审计（每个变更都有事件）（呼应 `dv360_list_audit_logs`）
- 天然可回放 / 可重建（平台侧丢了状态，从事件流重放即可）
- 天然满足「幂等」：按 `requestId` 去重事件，重复投递不产生重复变更

与 DV360 官方事件（Webhook 事件、审计日志）结合：**官方审计日志是「远端事件源」，平台自己的事件流是「本地事件源」**，二者按 requestId/实体 ID 对账，可发现「我方已发但平台未生效」或「平台侧有人手工改」的差异——这是高级集成团队区分「真实投放变更」与「我方预期变更」的手段。

---

## 附录 D：DV360 集成运维手册（Runbook 速查）与术语表

### D.1 日常运维 RACI 与值班清单

| 时段 | 动作 | 负责人 | 工具/数据源 |
|------|------|--------|-------------|
| 每天 09:00 | 查看昨日同步净水位、告警邮箱 | SRE | 调度面板 + 邮件 |
| 每天 09:05 | 核对关键广告主「对象数 + 报表行数」完整性 | 数据工程师 | BigQuery 对账 SQL |
| 每周一 | 检查 `dv360_list_usage_stats` 峰值与 429 汇总 | 集成工程师 | usage_stats |
| 每周五 | 检查 `dv360_validate_credentials` + 订阅到期 | 集成工程师 | 凭证监控 |
| 每月 | 复核用户权限清单与离职账号（`dv360_list_permission_users`） | 安全 | 权限清单 |
| 每季度 | API 版本升级评估（`dv360_list_api_versions`）+ 字段烟测 | 集成工程师 | 沙箱 + 烟测脚本 |

### D.2 常见告警的处理 Runbook

| 告警 | 第一反应 | 升级路径 |
|------|----------|----------|
| QUOTA_AT_80PCT | 查当日用量曲线，判断是峰值型还是日均值型 | 峰值型→本地削峰；日均型→申请提额 |
| SYNC_FAILED | 看 DAG 失败节点与错误原文 | 认证？→修凭证；字段？→烟测改解析；平台 5xx？→重试即可 |
| WATERMARK_STALE | 连 2 天未推进 | 查 3.5.2 分页丢/弱一致；必要时全量重拉一次自愈 |
| BATCH_PARTIAL_FAIL | 看死信表原因分布 | 参数问题→修生成器；平台问题→重放失败子集 |
| WEBHOOK_LOST | 视同「事件缺失」处理 | 回归轮询兜底，核对实体最新状态 |
| 403_NEW_ADV | 新广告主未授权 | 走权限流程：add_permission_user + partner link |

### D.3 DV360 集成术语表（中英对照）

| 术语 | 全称/说明 | 集成含义 |
|------|-----------|----------|
| Partner | 合作伙伴（DV360 账户最上层） | API 权限的归属单元 |
| Advertiser | 广告主 | 资源层级第二层；多数 API 路径的父级 |
| Insertion Order | 订单项 | 预算/排期的管理层级 |
| Line Item | 线条项目 / 媒体购买 | 实际投放单元；定向+预算+创意 |
| Flight | 投放周期 | LineItem 的起止时间窗口 |
| Creative | 创意素材 | 展示素材；审批对象 |
| Floodlight | CM360 转化测量技术 | 转化信号来源 |
| Page Token | 分页令牌 | 游标分页的续页凭据 |
| pageSize | 页大小 | 单页返回上限 |
| fields | 字段选择 | 部分响应，最小化传输 |
| updateMask | 更新掩码 | PATCH 的精确定位字段 |
| batch | 批量接口 | 一次 RPC 处理多条 |
| Retry-After | 重试等待头 | 429 时服务端建议的等待时间 |
| Quota | 配额 | 天/分钟级请求预算 |
| Rate Limit | 速率限制 | 单位时间内的频控 |
| Webhook | 事件回调 | best-effort 事件通知 |
| Watermark | 水位 | 数据同步进度档案 |
| 死信队列 | Dead Letter Queue | 失败子集的暂存队列 |
| SDC | Supply Chain Transparency | 供应链透明度（sellers.json） |
| ADH | Ads Data Hub | 隐私安全联合分析 |

---

## 七、参考资源链接

- Google 官方：Display & Video 360 API（`display-video.googleapis.com`）
- Google 官方：Campaign Manager 360 API（`dfareporting` 系列）
- Google 官方：Google Ads API（gRPC / GAQL）
- Google 官方：Google Ad Manager API
- Google 官方：BigQuery API / Ads Data Hub API
- 知识库内配套脚本：`scripts/ad_platform_api.py`、`scripts/dv360_client.py`、`scripts/api_common.py`、`scripts/google_ads_api.py`、`scripts/meta_api.py`

> 提示：本文的代码示例均为「集成模式演示」，接入生产前请按各平台的当前版本与真实凭证环境做适配与安全评审；尤其注意凭证、密钥与用户级数据的安全处置。

---

## 全文要点回顾（十句话带走）

1. **定位**：DV360 是 GMP 的媒体购买中枢，买媒体用它、测转化靠 CM360、出数靠 BigQuery、隐私归因走 ADH。
2. **资源**：Partner ⊃ Advertiser ⊃ Campaign ⊃ Insertion Order ⊃ Line Item ⊃ Creative，写操作必须带完整父级路径。
3. **分页**：pageToken 游标串行续拉，到 nextPageToken 为空为止；弱一致性靠主键去重 + 完整性对账兜底。
4. **认证**：后端首选服务账号 JWT（无状态刷新），能避开 refresh token 过期；用户授权型要监控 invalid_grant。
5. **限流**：「日配额」与「分钟速率」是两回事；429 是流量问题不是程序问题——削峰 + 尊重 Retry-After，而不是盲目提额。
6. **重试**：只重试 429/5xx，指数退避 + 抖动，尊重 Retry-After，超过上限进死信队列。
7. **批次**：batchUpdate 是部分成功语义，外层 200 不等于全成功；必须逐条解析、失败子集重放。
8. **单位**：报表美元小数 vs 对象 budgetMicros（×10^6）、时间 micros、广告主时区——三套统一，宁封装函数不裸传数字。
9. **Webhook**：best-effort 会丢；「事件只当唤醒，状态以主动 GET 为准，轮询兜底」。
10. **架构**：统一客户端（TokenProvider / Requester / Pager 三件套）+ 水位驱动增量 + 死信重放 + 监控告警，是四家平台通吃的集成平台骨架。

> 记住这十条，你的 DV360 集成平台就从「能跑」进化到「稳跑」。

（全文完）
