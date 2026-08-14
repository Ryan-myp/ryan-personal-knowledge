# DV360 报表与数据分析深度实战（跨渠道归因 / 自定义报表 / Floodlight / 第三方测量）

> **领域**: 广告投放 / 报表分析
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, reporting, analytics, attribution, floodlight, measurement
> **更新时间**: 2026-08-14
> **类型**: 深度文档

---

## 一、核心概念与架构

### 1.1 本章导读

报表与数据分析是 DV360（Display & Video 360）从"能投放"走向"能度量、能优化"的核心能力。投放 10 万元预算不难，难的是回答三个问题：

1. **钱花到哪了** —— 展示、点击、花费到底归属于哪个 Campaign / IO / Line Item / Creative？
2. **花得值不值** —— 转化、ROAS、可见率、VCR 这些"效果指标"有没有如实地回流并归一化到统一口径？
3. **账对得上吗** —— DV360 报表、第三方测量方（Moat/IAS/DoubleVerify）、内部埋点三方数据为何不一致，谁才是权威？

本深度文档聚焦 DV360 报表体系与数据分析的工程化实战：从报表的分类、生成链路、维度/指标口径，到 Floodlight 转化回流与跨渠道归因，再到生产环境的每日自动化拉取、入库、对账与排障。它与知识库内以下文档互补，读者可交叉阅读：

| 文档 | 互补关系 |
|------|----------|
| dv360-architecture-deep.md | 平台架构、账户层级、RTB、定向维度（本文引用其层级但不重复） |
| dv360-measurement-attribution-deep.md | 归因模型原理与 Go 归因引擎（本文聚焦归因在报表/数据链路中的落地） |
| dv360-optimization-deep.md | 优化策略与 KPI（本文聚焦报表拿到数据后如何组织与分析） |
| dv360-marketing-api-deep.md | 认证与 API 骨架（本文聚焦 reports 相关 API 的工程封装） |

### 1.2 DV360 报表体系总览

DV360 的报表能力并不只有一个入口，而是"四层递进"的体系。业务人员通常在 UI 里点击导出，数据工程师则通过 Query Builder 与 API 做自动化。理解这四种形态的区别，决定了你用什么姿势取数：

```
┌─────────────────────────────────────────────────────────────────────┐
│                  DV360 报表能力四层体系                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ 第 1 层  UI 内置报表（即点即用，非可编程）                    │   │
│  │   · 每个实体详情页自带报表（Campaign / IO / LineItem /       │   │
│  │     Creative 页签内嵌）                                      │   │
│  │   · 维度/指标固化，仅改变时间窗与粒度                         │   │
│  │   · 面向日常监控，数据= LDB 显示级（分钟级刷新）              │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↓ 需要自定义交叉                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ 第 2 层  自定义报表（UI 内建 Report Builder）                │   │
│  │   · 可视化拖拽选维度/指标 + Filters                          │   │
│  │   · 可保存为 Query（查询模板）并定时运行                      │   │
│  │   · 结果可预览、导出 CSV/Excel/Google Sheets                  │   │
│  │   · 底层即 Query Builder 的图形化外壳                        │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↓ 需要精确/批量化                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ 第 3 层  Query Builder（报表网关，可编程）                   │   │
│  │   · 把"维度×指标×过滤×时间窗"表达为 JSON Query               │   │
│  │   · 支持计划运行（每天/每周定时）与异步生成                   │   │
│  │   · 是 UI 自定义报表与 API 报表共用的底层对象                │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              ↓ 需要自动化/入库                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ 第 4 层  Reports API（displayvideo Queries 资源）           │   │
│  │   · 程序化创建 Query、触发 run、拉取 CSV 结果                │   │
│  │   · 是"每日自动报表入库 → BI"流水线的唯一官方入口            │   │
│  │   · 受配额（Quota）、SDF/Floodlight 等关联数据约束           │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

一句话总结：**UI 内置报表看"有没有"，自定义报表看"怎么切"，Query Builder 把"怎么切"固化成一个对象，Reports API 把这个对象自动化掉**。

### 1.3 报表数据流架构（从广告曝光到报表行）

理解 DV360 报表，必须理解它在数据管道里的位置。一次广告展示从"竞价成交"到"出现在报表里"经历了两条数据路径：

```
┌─────────────── 广告投放主链路（实时） ───────────────┐
│  用户打开页面/App                                       │
│     ↓ 竞价请求（Bid Request）                          │
│  DV360 DSP 参与实时竞价（RTB）                          │
│     ↓ 竞价成交（Win）→ 展现（Impression）               │
│  广告服务器返回创意 → 用户看到广告                       │
│     ↓ 用户点击 → 点击事件（Click）                     │
│  落地页跳转（含 Floodlight/第三方测量标签触发）          │
└──────────────────────────────────────────────────────┘
                          │ 事件日志（原始事件流）
                          ▼
┌─────────────── 数据归集与加工（异步） ────────────────┐
│  LDB：Logs Data Base（显示级日志库）                    │
│   · 近实时（分钟级）汇总展示/点击/花费                   │
│   · 供 UI 实时刷新、Pacing 监控                         │
│                          │ 夜间/周期回填 + 去重 + 对齐   │
│                          ▼                             │
│  RDB：Reports Data Base（报表级数据库）                 │
│   · 最终定稿数据（通常 24-48h 内稳定）                  │
│   · 含花费对账、卖家回填、Floodlight 转化                 │
│   · 是自定义报表 / Query / API 报表的数据源             │
└────────────────────────────────────────────────────────┘
                          │ 报表服务
                          ▼
┌────────────────── 报表对外出口 ──────────────────────┐
│  UI 内置报表 │ 自定义报表 │ Query Builder │ Reports API │
└────────────────────────────────────────────────────────┘
```

这条链路解释了 DV360 报表的**核心矛盾**：**LDB 快但不稳，RDB 稳但不快**。任何"为什么报表数和昨天 UI 看到的数不一样"的问题，几乎都源于你取的是 LDB 还是 RDB 口径。

### 1.4 维度与指标体系（两条正交的轴）

DV360 报表本质是一个"维度轴 × 指标轴"的交叉表：

- **维度（Dimension）**：把数据"切成几块"的切片键，例如按日期、按 Campaign、按设备切。
- **指标（Metric）**：在每一块上"数什么"，例如展示、点击、花费、可见率。

代码层面，`ad_platform_api.py` 中的 `dv360_get_report` 直接以这两个数组构建请求体：

```python
# 源码真相：ad_platform_api.py dv360_get_report
def dv360_get_report(self, advertiser_id: str, **kwargs) -> Dict:
    """查询报表"""
    service = self.get_client('dv360')
    body = {
        'advertiserId': advertiser_id,
        'dimensions': kwargs.get('dimensions', ['CAMPAIGN']),
        'metrics': kwargs.get('metrics', ['IMPRESSIONS', 'CLICKS', 'SPEND']),
        'dateRange': kwargs.get('date_range', {'start': '2026-08-01', 'end': '2026-08-14'})
    }
    result = service.reports().generate(body=body).execute()
    return result
```

注意这里的默认值就是驱动型报表的"金三角"：**维度=CAMPAIGN，指标=IMPRESSIONS/CLICKS/SPEND**。日常 90% 的投放监控都建立在这三个指标之上。

`dv360_list_report_dimensions()` 与 `dv360_list_report_metrics()` 可动态枚举当前账户可用的维度与指标清单，用于在前端动态渲染下拉框，而不是硬编码：

```python
# 动态枚举维度/指标（避免手工维护列表出错）
def report_schema(advertiser_id, client):
    dims = client.dv360_list_report_dimensions(advertiser_id=advertiser_id)
    metrics = client.dv360_list_report_metrics(advertiser_id=advertiser_id)
    return {
        'dimensions': [d['name'] for d in dims],
        'metrics': [m['name'] for m in metrics],
        'count_dims': len(dims),
        'count_metrics': len(metrics),
    }
```

**维度/指标两轴交叉就是一行报表数据**：例如"2026-08-10 + Campaign_A + iOS + 上海 + 前贴片"这一行的 IMPRESSIONS = 1,230,000。

### 1.5 报表层级与颗粒度（维度选择决定了"看多细"）

DV360 的账户层级是"Partner → Advertiser → Campaign → Insertion Order（IO）→ Line Item → Creative"，报表维度几乎一一对应这套层级。选择哪个层级作为报表的颗粒度，取决于分析目的：

```
Partner（合作伙伴，多广告主）
   └── Advertiser（广告主，一个品牌/一个业务单元）
        └── Campaign（广告系列，一个营销目标）
             └── Insertion Order / IO（订单项，一份媒体购买合同）
                  └── Line Item（线条项目，一条可竞价购买的条目）
                       └── Creative（创意，具体广告素材）
```

| 报表维度 | 颗粒度 | 典型用途 | 对应实体 |
|----------|--------|----------|----------|
| DATE | 天/时/分 | 时间趋势、排期节奏 | 时间 |
| CAMPAIGN | 系列级 | 营销目标整体 ROI | Campaign ▲ |
| INSERTION_ORDER | 订单级 | 预算执行、合同对账 | IO ▲ |
| LINE_ITEM | 条目级 | 出价策略、定向效果分析 | Line Item ▲ |
| CREATIVE / CREATIVE_ID | 素材级 | 素材轮换、点击率对比 | Creative ●（最细管理层） |
| ADVERTISER | 广告主页 | 多品牌汇总汇报 | Advertiser |
| PARTNER | 合作伙伴页 | 全盘大盘周报 | Partner |

```
投入分析深度的"性价比"：
  高颗粒度（Creative 级）→ 明细多、噪声大、查询慢、易超行上限
  中颗粒度（Line Item 级）→ 日常优化主战场（性价比最高）★
  低颗粒度（Campaign 级）→ 汇报/ROI 主战场
```

实战经验：**首次搭建报表体系时，从 LINE_ITEM 级起步**。Campaign 级太粗看不到优化抓手，Creative 级太细容易超出行数上限（见第四节行数上限问题）。Line Item 级是"每天能看、每次能优化"的甜区。

### 1.6 数据延迟等级（LDB 显示级 vs RDB 上报级）

这是 DV360 报表最容易踩的"时间坑"。同一指标在"显示级数据"和"上报级数据"里，数值和出现时间完全不同：

| 数据等级 | 英文 | 数据源 | 出现延迟 | 稳定性 | 适用场景 | 数值特征 |
|----------|------|--------|----------|--------|----------|----------|
| 显示级（LDB） | Display-level / LDB | Logs Data Base | 分钟级（近实时） | 会回填、会修正 | UI 实时监控、Pacing、当天看数 | 当天可能偏低 |
| 上报级（RDB） | Reporting-level / RDB | Reports Data Base | 通常 24-48h 定稿 | 稳定，作为权威 | 报表、对账、入库、BI | 定稿后不变 |

**关键认知**：

1. **同一个指标出现两次**：你昨天下班前在 UI 看到的"今天展示=100万"，今天早上再看往往变成了"今天展示=105万"。不是数据错了，而是 LDB 在补记延迟上报的日志（尤其是 CTV / OTT / 电视投放的回填）。
2. **跨媒体回填差异大**：
   - Google/AdX 库存：RDB 常 24h 内定稿。
   - YouTube / CTV / OTT：可能 3~5 天甚至更久。
   - 卖家（Seller）/ 程序化保量（PG）对账数据：取决于 SSP 回填周期。
3. **对账口径约定**：凡涉及"和第三方对账""和媒体方结算""入库做持久化"的数据，**一律取 RDB 上报级**，且通常要用"T-2（昨天之前两天）"作为稳定口径，避免当天数据回流未完。
4. **时效性取舍**：若业务要求"当天上午看昨天数据做优化"，只能接受 LDB 级（有 ±5~10% 回填波动的风险）；若要"和财务/第三方对死账"，必须等 RDB 定稿。

**为什么会有两级？** 因为 RTB 环境中，一次展示的日志要经过多个系统异步归集（Exchange、SSP、验证方、去重、花费对账），不可能在毫秒级竞价完成时同时得到最终结果。LDB 先用最快的路径给出近似值；RDB 在后台做全量回填、去重、对账后给出定稿值。

### 1.7 报表体系与测量体系的关系（分析前先分清三类数据）

DV360 报表里出现的"数"实际来自三种不同测量体系，混为一谈必然对不上账：

```
┌─────────────────────────────────────────────────────────────────┐
│  DV360 报表中的三类"数"来源                                     │
├─────────────────────────────────────────────────────────────────┤
│  ① 投递数据（Delivery Data）                                    │
│     · 展示 / 点击 / 花费 / 视频观看                             │
│     · 来源：DV360 自身广告服务器日志（LDB/RDB）                 │
│     · 特点：权威、实时、与竞价链路强一致                        │
│     · 对应指标：IMPRESSIONS, CLICKS, SPEND, VIDEO_VIEWS         │
│                                                                 │
│  ② 验证数据（Verification Data）                                │
│     · 可见率 / 无效流量（IVT）/ 品牌安全 / 误定向                │
│     · 来源：第三方测量方（Moat / IAS / DoubleVerify）            │
│     · 特点：由第三方标签独立采样计数，与投递数据天然有差        │
│     · 对应指标：MEASURABLE_IMPRESSIONS, VIEWABLE_IMPRESSIONS,   │
│                 INVALID_TRAFFIC_IMPRESSIONS                     │
│                                                                 │
│  ③ 转化数据（Conversion Data）                                  │
│     · 转化 / 销售 / 归因成果                                    │
│     · 来源：Floodlight 计数（CM360 关联）/ 跨渠道归因/第三方归因 │
│     · 特点：报表背后的"效果层"，由玩家自身统计                   │
│     · 对应指标：FLOODLIGHT_CONVERSIONS, CONVERSION_VALUE,        │
│                 ROAS, COST_PER_CONVERSION                       │
└─────────────────────────────────────────────────────────────────┘
```

这三类数据的口径、延迟、权威方各不相同，第四节的对账全部围绕"三源数据的差异归因"展开。

### 1.8 本节小结

- DV360 报表有四层形态：UI 内置 / 自定义报表 / Query Builder / Reports API，自动化必须走最后一层。
- 数据链路是"事件日志 → LDB 近实时 → RDB 定稿 → 报表出口"，一切"对不上"都先从 LDB/RDB 口径查起。
- 维度/指标是正交双轴，层级颗粒度（Campaign/IO/Line Item/Creative）决定看多细，Line Item 级是日常优化甜区。
- 报表里混着投递、验证、转化三类数据，分析前必须先分清来源。

## 二、深度原理解析

### 2.1 报表生成流程（Query 定义 → 异步跑批 → 结果下载）

DV360 报表服务走的是"**先定义→再运行→后下载**"的异步三步曲，而不是同步返回。理解这个模型是工程化的前提——你永远不能在一次 HTTP 请求里拿到完整报表，必须轮询任务状态。

```
                      异步三步曲
┌──────────────────────────────────────────────────────────────────┐
│  Step 1  定义 Query（一次把报表模板固化下来）                       │
│     POST /v3/queries  { query: {                                 │
│         metadata: { title, ...},                                 │
│         timeRange: {...},                                        │
│         dimensions: [...],                                       │
│         metrics: [...],                                          │
│         filters: [...],                                          │
│         schedule: { frequency: 'DAILY', ... },                   │
│         runNow: true                                             │
│     }}                                                           │
│     → 返回 queryId                                             │
├──────────────────────────────────────────────────────────────────┤
│  Step 2  运行 Query（触发一次异步跑批）                            │
│     POST /v3/queries/{queryId}:run                               │
│     → 后台开始生成报表（分钟~小时级，取决于数据体积）              │
│     → 返回 reportId（一次运行对应一个报表文件）                   │
├──────────────────────────────────────────────────────────────────┤
│  Step 3  轮询并下载                                              │
│     GET /v3/queries/{queryId}/reports/{reportId}                 │
│       · status: PROCESSING → ... → DONE/FAILED                  │
│     GET /v3/queries/{queryId}/reports/{reportId}:download        │
│       · DONE 后可下载 CSV（GCS 直链或流式返回）                  │
└──────────────────────────────────────────────────────────────────┘
```

工程侧，`ad_platform_api.py` 的 `dv360_sync_report` 是"同步语义的封装"——它接收日期范围、触发一次全量同步，随后由调用方根据返回的任务句柄去轮询：

```python
# 源码真相：ad_platform_api.py dv360_sync_report
def dv360_sync_report(self, advertiser_id: str, **kwargs) -> Dict:
    """同步报表数据"""
    service = self.get_client('dv360')
    body = {
        'advertiserId': advertiser_id,
        'dateRange': kwargs.get('date_range', {'start': '2026-08-01', 'end': '2026-08-14'})
    }
    result = service.reports().sync(body=body).execute()
    return result
```

一个"查询 + 轮询 + 下载"的完整 Python 实现（封装在 `dv360_api.py` 风格客户端之上）：

```python
import time, csv, io, logging
from googleapiclient.discovery import build
from google.oauth2 import service_account

log = logging.getLogger("dv360.report")

SCOPES = ['https://www.googleapis.com/auth/display-video']

def build_dv360_client(service_account_file: str):
    creds = service_account.Credentials.from_service_account_file(
        service_account_file, scopes=SCOPES)
    return build('displayvideo', 'v3', credentials=creds)

def create_query(service, advertiser_id, title, date_start, date_end,
                 dimensions, metrics, filters=None, frequency='DAILY'):
    """Step 1: 定义并触发 Query，返回 query_id 与 report_id"""
    query_body = {
        'advertiserId': advertiser_id,
        'query': {
            'metadata': {'title': title},
            'timeRange': {'startDate': date_start, 'endDate': date_end},
            'dimensions': dimensions,
            'metrics': metrics,
            'filters': filters or [],
            'schedule': {'frequency': frequency},
        },
        'runNow': True,
    }
    resp = service.queries().create(body=query_body).execute()
    query_id = resp['queryId']
    report_id = resp['report']['reportId']
    log.info("query=%s report=%s", query_id, report_id)
    return query_id, report_id

def wait_for_report(service, query_id, report_id, timeout_s=3600, poll_s=30):
    """Step 2: 轮询报表状态直至 DONE，超时抛异常"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        report = service.queries().reports().get(
            queryId=query_id, reportId=report_id).execute()
        status = report.get('status', {})
        state = status.get('state', 'PROCESSING')
        log.info("report %s state=%s", report_id, state)
        if state == 'DONE':
            return report
        if state == 'FAILED':
            raise RuntimeError(f"report {report_id} failed: {status}")
        time.sleep(poll_s)
    raise TimeoutError(f"report {report_id} timeout after {timeout_s}s")

def download_report_csv(service, query_id, report_id):
    """Step 3: 下载 CSV 并解析为行列表"""
    req = service.queries().reports().download(
        queryId=query_id, reportId=report_id)
    body, _ = req.execute(http=None) if False else (None, None)
    # 实际使用目标的下载响应，常见做法：取 GCS 直链
    report = service.queries().reports().get(
        queryId=query_id, reportId=report_id).execute()
    gcs_url = report.get('reportMetadata', {}).get(
        'googleCloudStoragePath') or report.get('path', '')
    log.info("gcs url: %s", gcs_url)
    # 下载 GCS 后解析
    data = _fetch_bytes(gcs_url)
    return parse_csv_rows(data)

def _fetch_bytes(url):
    # 省略：可用 google-cloud-storage 或 urllib
    raise NotImplementedError

def parse_csv_rows(raw: bytes):
    """解析 DV360 导出的 CSV（首行为列名）"""
    text = raw.decode('utf-8-sig')  # 处理 BOM
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)
```

**工程要点**：

1. **Query 复用而非每次新建**：Query 生成后长期存在，`run` 只是触发一次新的报告生成。生产环境用"每日触发既有 Query"而非"每天新建 Query"，否则 Query 数量会爆炸且难以管理。
2. **幂等去重**：同一 Query 一天内可能被重复 run（重试导致），报表结果里会出现同一天多条记录，入库前必须按 `date + 维度键` 做幂等去重（见 3.2）。
3. **超时设计**：DV360 报表生成通常 1~30 分钟。轮询超时设为 60~120 分钟，轮询间隔 15~60 秒，避免频繁请求打爆配额。
4. **失败重试**：`FAILED` 通常可安全重试一次 `run`；连续失败进入告警，而不是无限重试刷配额。

### 2.2 常用维度与指标深度对照表

以下维度/指标是 DV360 报表出现频率最高的集合，字段名取自 API 维度/指标枚举与 `dv360_list_*` 系列返回结构：

**常用维度（Dimension）**

| 维度 | API 字段/枚举 | 说明 | 分析用途 |
|------|---------------|------|----------|
| 日期 | DATE | 天级 | 时间序列、趋势 |
| 小时 | HOUR | 时级（近 30 天可用） | 时段投放节奏 |
| 广告系列 | CAMPAIGN | 系列名 + ID | 营销目标 ROI |
| 订单项 | INSERTION_ORDER | IO 名 + ID | 预算/合同对账 |
| 线条项目 | LINE_ITEM | 条目名 + ID | 优化主战场 |
| 创意 | CREATIVE / CREATIVE_ID | 素材名 + ID | 素材轮换 |
| 设备 | DEVICE / DEVICE_TYPE | 手机/平板/桌面/CTV | 设备策略 |
| 系统 | OPERATING_SYSTEM | iOS / Android / 其他 | 系统策略 |
| 地域 | GEO / COUNTRY / REGION / METRO | 国家→城市多级 | 地域策略 |
| 受众 | AUDIENCE_SEGMENT | 受众细分 | 受众效果 |
| 位置 | PLACEMENT / SITE | 网站/APP 投放位 | 库存质量 |
| 媒体方 | SELLER / EXCHANGE | 卖家/交易平台 | 库存结构 |
| 交易类型 | DEAL / TRANSACTION_TYPE | PG/PMP/PD/Open | 交易质量 |
| 定向维度 | TARGETING_* | 关键词/上下文/类目 | 定向命中分析 |

`dv360_list_dimension_values(dimension)` 用于枚举某个维度的合法取值，例如下拉选择"地域"时先拉取国家/地区列表：

```python
# 源码真相：ad_platform_api.py dv360_list_dimension_values
def dv360_list_dimension_values(self, dimension: str, **kwargs) -> List[Dict]:
    """列出维度值"""
    service = self.get_client('dv360')
    values = service.users().me().dimensionValues().list(
        dimension=dimension
    ).execute()
    return values.get('dimensionValues', [])
```

**常用指标（Metric）** —— 按测量体系分组：

| 指标 | 测量体系 | 说明 | 计算口径 |
|------|----------|------|----------|
| IMPRESSIONS | 投递 | 展示次数 | 广告被呈现次数 |
| CLICKS | 投递 | 点击次数 | 用户点击广告次数 |
| SPEND / COST | 投递 | 花费（金额） | 实际计费成本 |
| CPM | 投递 | 千次展示成本 | SPEND/IMPRESSIONS*1000 |
| CPC | 投递 | 单次点击成本 | SPEND/CLICKS |
| CTR | 投递 | 点击率 | CLICKS/IMPRESSIONS |
| VIDEO_VIEWS | 投递 | 视频观看次数 | 触发视频播放 |
| VCR | 投递 | 视频完整观看率 | 完整观看/视频开始 |
| COMPLETIONS | 投递 | 完整观看次数 | VCR 分子 |
| MEASURABLE_IMPRESSIONS | 验证 | 可测量展示 | 被验证方标签测到 |
| VIEWABLE_IMPRESSIONS | 验证 | 可见展示 | 按行业标准可见定义 |
| VIEWABILITY_RATE | 验证 | 可见率 | 可见/可测或可见/展示 |
| INVALID_TRAFFIC_IMPRESSIONS | 验证 | 无效流量展示 | IVT 过滤量 |
| FLOODLIGHT_CONVERSIONS | 转化 | Floodlight 转化数 | 计数转化 |
| CONVERSION_VALUE | 转化 | 转化价值 | 归因后价值 |
| ROAS | 转化 | 广告支出回报率 | 转化价值/花费 |
| COST_PER_CONVERSION | 转化 | 单转化成本 | 花费/转化 |

**核心派生指标公式（务必写成公式避免口径漂移）**：

```
CTR           = CLICKS / IMPRESSIONS
CPM           = SPEND / IMPRESSIONS * 1000
CPC           = SPEND / CLICKS
VCR           = COMPLETIONS / VIDEO_VIEWS
VIEWABILITY   = VIEWABLE_IMPRESSIONS / MEASURABLE_IMPRESSIONS
ROAS          = CONVERSION_VALUE / SPEND
CPA(COST_CONV) = SPEND / FLOODLIGHT_CONVERSIONS
```

**指标口径陷阱**（本节先埋点，第四节展开）：

- **可见率的"分母"之争**：Google 默认可见率 = 可见展示/可测量展示；部分客户希望”可见展示/总展示（含不可测）“。两者数值差很远。
- **转化 vs 归因转化**：`FLOODLIGHT_CONVERSIONS` 是"发生转化"，归因后才把价值分摊到曝光/点击上；看 ROAS 必须用归因后的价值口径。
- **花费 vs 扣费**：`SPEND` 是展现级计费成本，不含返点/返利；财务对账要另取 invoice 口径（对应 `dv360_list_invoice_history`）。

### 2.3 Floodlight Activity 与转化数据回流

Floodlight 是 Google 的统一转化计数体系（源自 Campaign Manager 360 技术），DV360 报表里的转化数据正是靠它回流。

**Floodlight 的两类配置**：

| 类型 | 英文 | 说明 | 计数方式 |
|------|------|------|----------|
| 计数型 | Counting Activity | 记录"发生了多少次" | 计数（Count） |
| 售出型 | Sales Activity | 记录"交易金额" | 汇总销售价值 / 交易 |

**Floodlight 层级链路**：

```
Floodlight Configuration（配置，一个广告主一个）
   └── Floodlight Activity Group（活动组，按转化目标分类）
        └── Floodlight Activity（活动，具体转化点：加购/下单/注册）
             ├── Counting Method（计数方式：SESSION/UNIQUE/TRANSACTION）
             └── Counting Window（计数窗口：1/7/30/60 天）
```

在 `ad_platform_api.py` 中，`dv360_list_floodlight_configs` 用于拉取广告主的 Floodlight 配置，是把"转化口径"映射进报表体系的前提：

```python
# 源码真相：ad_platform_api.py dv360_list_floodlight_configs
def dv360_list_floodlight_configs(self, advertiser_id: str, **kwargs) -> List[Dict]:
    """列出 Floodlight 配置"""
    service = self.get_client('dv360')
    configs = service.users().me().floodlightConfigs().list(
        advertiserId=advertiser_id
    ).execute()
    return configs.get('floodlightConfigs', [])
```

**转化数据回流链路**：

```
用户看到 DV360 广告（含 Floodlight 标签/落地页）→ 点击 → 进入落地页
   ↓ 落地页触发 Floodlight 计数器（由 CM360 / Google Tag 管理）
转化事件（加购/下单/注册）写入 Floodlight 活动
   ↓
DM360/CM360 归因引擎将转化与最近的 DV360 曝光/点击关联
（按归因模型 + 转化窗口 + 计数方式）
   ↓
归因结果回流到 DV360 RDB
   ↓
DV360 报表出现 FLOODLIGHT_CONVERSIONS / CONVERSION_VALUE / ROAS
   ↓
（可选）导出到 Google Sheets / BigQuery / BI 做深度分析
```

**三种计数方式（Counting Method）对指标数值影响巨大**：

| 计数方式 | 逻辑 | 报表数值特征 |
|----------|------|--------------|
| SESSION（会话） | 一次会话内多个活动只计 1 | 数值最小，去重最狠 |
| UNIQUE（独立） | 同用户同活动一段时间只计 1 | 中等去重 |
| TRANSACTION（交易） | 每次交易各计 1 | 数值最大，最贴近成交笔数 |

**转化归因在报表里如何体现**：Floodlight 转化按"归因模型（默认 Data-Driven / 或 Last Click）"把功劳分摊到各触点（曝光/点击），再乘以各自权重回填到对应 Campaign/IO/LineItem 行。这就是为什么同一笔交易会"同时出现在多个 campaign 的转化行里"——那是归因分摊，不是重复计数。

### 2.4 跨渠道归因在 DV360 中的实现（Google Ads 与 CM360 数据打通）

单看 DV360 自己的报表只能看到"展示/视频/搜索（非 Google Ads）"侧的转化分摊。要回答"全渠道归因"，DV360 与 Google 其他产品（Google Ads、Campaign Manager 360）打通，构成统一归因视图。

**Google 生态数据打通拓扑**：

```
                Google 统一归因视图（Google Ads / Ads Data Hub）
                                ▲
                  ┌─────────────┴──────────────┐
                  ▼                            ▼
          DV360（展示+视频）            Google Ads（搜索+购物+PMax）
          Floodlight 转化回流          转化目标共享
                 └──────────┬──────────────┘
                            ▼
                  Campaign Manager 360（CM360）
                  统一 Floodlight 配置源 + 卖方可验证度量
                            ▼
                  DV360 报表 / CM360 报表 / BigQuery 导出
```

**跨渠道归因的可实现路径**：

1. **转化目标共享**：DV360 与 Google Ads 共用同一组 Floodlight 转化目标，报表可对同一转化做口径对齐。
2. **Google Ads Data Hub（ADH）聚合归因**：在隐私沙箱内对 Google Ads + DV360 的原始用户级日志做差分聚合归因，得到跨搜索+展示的全路径归因表——这是最接近"全渠道"的官方能力，但门槛高（需 ADH 权限 + SQL 分析）。
3. **CM360 统一报表**：CM360 是 DV360 的测量中枢，可导出跨 DV360/Google Ads/第三方 DSP 的统一报表（HTML5 报表、Cross-dimension 报表）。
4. **第三方归因平台（AppsFlyer / Adjust / Singular / Kochava）**：由平台侧做设备级归因，把转化能力按渠道切分，再回填到 DV360 广告主后台。注意这里与 Google 归因是两套体系，数值天然不同。

**跨渠道归因的工程落地（API 侧）**：

```python
# 拉取跨渠道报表（示例：结合 CM360 reporting API）
from googleapiclient.discovery import build

def list_cross_channel_reports(account_id, client):
    # 封装 ad_platform_api.dv360_list_cross_channel_reports（账户级跨渠道报表）
    return client.dv360_list_cross_channel_reports(account_id=account_id)

def adh_aggregate_attribution(project_id, customer_id, analysis_query, date_range):
    """调用 Google Ads Data Hub 聚合归因查询（示意）"""
    # adh = build('displayvideo', 'v3') 实际 ADH 有独立 API
    # analysisQueries / analysisQueryRuns 异步执行，结果落 GCS
    return {
        'project_id': project_id,
        'customer_id': customer_id,
        'analysis_query': analysis_query,
        'date_range': date_range,
    }
```

**跨渠道对账的关键提醒**：Google 归因（含 ADH/DDA）与第三方归因平台的数值差异，源于**归因窗口、归因模型、去重粒度、数据抽样**四大因素。不要指望两套数字相等，而是要"给每套数字定义它的口径与用途"（如 Google 口径用于 Google 系优化，AppsFlyer 口径用于全渠道 ROI 汇报）。

### 2.5 第三方测量数据接入（Moat / IAS / DoubleVerify）

可见率、无效流量、品牌安全这类"验证数据"不由 DV360 自己数，而是由第三方测量方（Moat、Integral Ad Science、DoubleVerify）接入。这是报表对账中最常出"三方差异"的部分。

**接入模型**：

```
DV360 广告（含 DoubleVerify / Moat / IAS 验证标签）
   ↓ 每一条广告请求同时发出"验证请求"给测量方
测量方独立对广告展示做测量（可见性/IVT/品牌安全/误定向）
   ↓ 三方标签各自计数（与 DV360 的计数器异步、独立）
测量数据（MEASURABLE / VIEWABLE / IVT）作为验证维度/指标回流 DV360 RDB
   ↓
DV360 报表出现验证指标 + 三方原始门户可用独立报表交叉验证
```

`dv360_list_ad_verification_services()` 与 `dv360_list_brand_safety_providers()` 可枚举当前可选的验证/品牌安全服务商；`dv360_list_viewability_providers()` 列出可见率提供商，用于在报表维度/指标配置前确认可用供应商：

```python
# 枚举第三方测量服务商（用于报表维度/指标配置前的能力检查）
def available_verifiers(client):
    services = client.dv360_list_ad_verification_services()
    providers = client.dv360_list_brand_safety_providers()
    viewability = client.dv360_list_viewability_providers()
    return {
        'verification_services': [s.get('name') for s in services],
        'brand_safety': [p.get('name') for p in providers],
        'viewability': [v.get('name') for v in viewability],
    }
```

**第三方测量指标与 DV360 投递指标的差异根源**：

| 差异点 | 说明 | 谁高谁低 |
|--------|------|----------|
| 计数主体不同 | DV360 数"广告服务器日志"，验证方数"标签测量" | 通常 DV360 展示 ≥ 验证方可测展示 |
| 可测性 | 部分环境（iframe 嵌套/CTV 早期）无法测量 | 验证方展示 < DV360 展示 |
| 采样与延迟 | 验证方可能抽样、回填慢 | 当天验证数偏低 |
| IVT 扣减 | DV360 有自己的 IVT 口径，验证方另有一套 | 两套 IVT 数值不同 |

**工程建议**：验证数据接入报表时，统一用"MEASURABLE（可测量）"作为口径分析可见率，避免用"总展示"做分母导致可见率虚低；对账时以"可测量展示"对齐 DV360 与第三方的分母。

### 2.6 报表拉取引擎 —— Go 生产级实现（分页、重试、CSV 解析）

前面用 Python 演示了 API 调用，但生产级"每日自动拉取 → 解析 → 落库"通常需要一个健壮的拉取引擎。这里用 Go 实现一个支持**分页、指数退避重试、流式 CSV 解析**的报表引擎骨架。

```go
package report

import (
	"bufio"
	"bytes"
	"context"
	"encoding/csv"
	"io"
	"log"
	"math"
	"time"
)

// Config 定义一次报表拉取任务的配置。
// 对应 DV360 Query: 维度×指标×时间窗+过滤。
type Config struct {
	AdvertiserID string
	QueryTitle   string
	StartDate    string // YYYY-MM-DD
	EndDate      string
	Dimensions   []string // e.g. ["CAMPAIGN","LINE_ITEM"]
	Metrics      []string // e.g. ["IMPRESSIONS","CLICKS","SPEND"]
	RetryMax     int      // 失败重试次数
	BaseDelay    time.Duration // 指数退避基数
}

// Row 表示报表的一行（维度键 -> 指标值 的扁平行）。
type Row map[string]string

// Fetcher 抽象"创建 Query -> 运行 -> 轮询 -> 下载"。
type Fetcher interface {
	Create(ctx context.Context, cfg Config) (queryID string, err error)
	Run(ctx context.Context, queryID string) (reportID string, err error)
	Wait(ctx context.Context, reportID string) (status string, err error)
	Download(ctx context.Context, reportID string) ([]byte, error)
}

// Engine 带重试与分页的报表拉取引擎。
type Engine struct {
	f         Fetcher
	pageSize  int
	rowsLimit int // 单 Query 行数上限告警阈值
}

// New 构造引擎。
func New(f Fetcher, pageSize, rowsLimit int) *Engine {
	return &Engine{f: f, pageSize: pageSize, rowsLimit: rowsLimit}
}

// withRetry 指数退避重试：网络错误/临时失败可安全重试。
func (e *Engine) withRetry(ctx context.Context, cfg Config,
	label string, fn func() (string, error)) (string, error) {
	var lastErr error
	for attempt := 0; attempt <= cfg.RetryMax; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(float64(cfg.BaseDelay) * math.Pow(2, float64(attempt-1)))
			log.Printf("[retry] %s attempt=%d sleep=%v", label, attempt, backoff)
			select {
			case <-time.After(backoff):
			case <-ctx.Done():
				return "", ctx.Err()
			}
		}
		id, err := fn()
		if err == nil {
			return id, nil
		}
		lastErr = err
		log.Printf("[warn] %s attempt=%d err=%v", label, attempt, err)
	}
	return "", lastErr
}

// Pull 执行一次完整拉取，返回解析后的行（分页交给调用方分批落库）。
func (e *Engine) Pull(ctx context.Context, cfg Config) ([]Row, error) {
	// 1) 创建 Query（幂等：已有同名则复用）
	queryID, err := e.withRetry(ctx, cfg, "create",
		func() (string, error) { return e.f.Create(ctx, cfg) })
	if err != nil {
		return nil, err
	}
	// 2) 运行 Query
	reportID, err := e.withRetry(ctx, cfg, "run",
		func() (string, error) { return e.f.Run(ctx, queryID) })
	if err != nil {
		return nil, err
	}
	// 3) 轮询至 DONE（Wait 内部自带超时与轮询）
	if _, err := e.f.Wait(ctx, reportID); err != nil {
		return nil, err
	}
	// 4) 下载并解析
	raw, err := e.f.Download(ctx, reportID)
	if err != nil {
		return nil, err
	}
	return e.parse(raw, cfg)
}

// parse 流式解析 CSV，转成 []Row；映射列名以保证字段稳定。
func (e *Engine) parse(raw []byte, cfg Config) ([]Row, error) {
	rd := csv.NewReader(bufio.NewReader(bytes.NewReader(raw)))
	rd.FieldsPerRecord = -1 // 容忍行内字段数不一致
	header, err := rd.Read()
	if err != nil {
		return nil, err
	}
	var rows []Row
	for {
		rec, err := rd.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		r := make(Row, len(header))
		for i, name := range header {
			if i < len(rec) {
				r[name] = rec[i]
			}
		}
		rows = append(rows, r)
		if len(rows) > e.rowsLimit {
			log.Printf("[warn] rows exceed limit %d, current=%d", e.rowsLimit, len(rows))
		}
	}
	return rows, nil
}
```

**Go 引擎设计要点**：

1. **指数退避重试**：创建/运行/下载都可能因配额、网络波动临时失败，用 `math.Pow(2, attempt)` 退避（128ms → 256ms → …），避免瞬时雪崩。
2. **轮询独立于重试**：`Wait` 是长轮询，超时由内部管理，不属于"立即重试"的范畴——报表生成中绝对不能误判为失败去重试 run。
3. **流式 CSV 解析**：用 `csv.Reader` 逐行读，避免一次性 `ReadAll` 撑爆内存；容忍 `FieldsPerRecord=-1` 应对列数不齐。
4. **行数上限告警**：单 Query 行数逼近上限时打警告，触发拆分查询（加维度过滤或改小颗粒度，见 3.4/4.x）。

**分页的真相**：DV360 单个报表文件本身由 Google 在后台切片，API 层的"分页"更多是指"**按日期切日 + 按维度过滤切桶**"来规避单文件超限，而不是传统的 offset/limit 游标。实践上通过"逐日拉取 + 限定维度组合"天然分页，比事后切大文件更省资源（详见 3.2 调度策略）。

### 2.7 常用数据结构的 Python 版数据模型

报表行在入库前，先用 Pydantic/SQLAlchemy 声明稳定模型，统一"列名→数据类型→主键"——这是对账能做下去的前提（字段命名不一致是对账失败的常见根因）：

```python
from datetime import date
from pydantic import BaseModel

class DV360ReportRow(BaseModel):
    """DV360 报表落库模型（统一口径映射）"""
    report_date: date          # 数据日期
    advertiser_id: int
    campaign_id: int | None
    insertion_order_id: int | None
    line_item_id: int | None
    creative_id: int | None
    device_type: str | None
    country: str | None
    impressions: int = 0
    clicks: int = 0
    spend_micro: int = 0       # 金额一律用微单位，避免浮点误差
    completions: int = 0
    floodlight_conversions: int = 0
    conversion_value_micro: int = 0
    measured_at_utc: str       # 拉取时间戳，便于排查"拉了哪个版本"

    @property
    def spend_usd(self) -> float:
        return self.spend_micro / 1_000_000

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions else 0.0
```

**统一主键约定**：`(report_date, advertiser_id, campaign_id, insertion_order_id, line_item_id, creative_id, device_type, country)` 是该行"事实键"，入库用 UPSERT 保证幂等（见 3.2 去重）。

## 三、生产环境实战

### 3.1 每日自动报表拉取入库案例（Python + API → 结构化存库 → BI）

以一个标准落地案例贯穿全章：**每天凌晨自动拉取 DV360 各广告主"昨天（T-1）数据"，清洗入库到 BigQuery/PostgreSQL，次日晨会由 BI（Looker/Metabase/自定义看板）出日报。**

整体流水线：

```
[Cron / Airflow / Dagster] 触发每日任务
        ↓
[Step 1] 认证 + 拉取广告主清单
   client.dv360_list_advertisers(partner_id=...)
        ↓
[Step 2] 逐广告主 创建/复用 Query（LINE_ITEM 级 + 昨日时间窗）
   client.dv360_get_report / dv360_sync_report
        ↓
[Step 3] 轮询 DONE → 下载 CSV
   wait_for_report() / download_report_csv()
        ↓
[Step 4] 解析 + 口径映射 + 幂等 UPSERT 入库
   DV360ReportRow → INSERT ... ON CONFLICT UPDATE
        ↓
[Step 5] 对账断言 + 失败告警（钉钉/Slack/邮件）
   dv360 数 vs 昨日已入库数 > 阈值 → 告警
        ↓
[BI] Looker/Metabase 连接数仓出日报
```

**每日任务主控脚本**（调度器无关，纯函数式）：

```python
import pandas as pd
from datetime import date, timedelta
from sqlalchemy.dialects.postgresql import insert as pg_insert

def run_daily_report(client, advertiser_ids, as_of: date = None) -> dict:
    """拉取 as_of-1（默认昨天）各广告主 LINE_ITEM 级报表并入库。"""
    as_of = as_of or date.today()
    target_date = as_of - timedelta(days=1)          # 默认拉 T-1
    report_date_s = target_date.isoformat()

    summary = {'advertisers': 0, 'rows': 0, 'failed': []}
    for adv_id in advertiser_ids:
        try:
            # 1) 定义 Query：LINE_ITEM 级 + 关键指标
            dims = ['LINE_ITEM', 'DEVICE_TYPE', 'COUNTRY']
            metrics = ['IMPRESSIONS', 'CLICKS', 'SPEND',
                       'VIEWABLE_IMPRESSIONS', 'MEASURABLE_IMPRESSIONS',
                       'FLOODLIGHT_CONVERSIONS', 'CONVERSION_VALUE']
            query_id, report_id = create_query(
                client, adv_id, f"daily_li_{report_date_s}",
                report_date_s, report_date_s, dims, metrics)
            # 2) 轮询 + 下载
            wait_for_report(client, query_id, report_id, timeout_s=3600)
            rows = download_report_csv(client, query_id, report_id)
            # 3) 映射 + 入库
            upsert_rows(rows, adv_id, report_date_s)
            summary['rows'] += len(rows)
            summary['advertisers'] += 1
        except Exception as e:                         # 单广告主失败不拖垮整批
            summary['failed'].append({'advertiser': adv_id, 'error': str(e)})
            log.exception('advertiser %s failed', adv_id)
    return summary

def upsert_rows(rows, adv_id, report_date_s, session=None):
    """把 CSV 行映射为标准模型并幂等 UPSERT。"""
    records = []
    for r in rows:
        rec = DV360ReportRow(
            report_date=report_date_s,
            advertiser_id=adv_id,
            campaign_id=_int(r.get('Campaign ID')),
            insertion_order_id=_int(r.get('Insertion Order ID')),
            line_item_id=_int(r.get('Line Item ID')),
            creative_id=_int(r.get('Creative ID')),
            device_type=r.get('Device'),
            country=r.get('Country'),
            impressions=_int(r.get('Impressions')),
            clicks=_int(r.get('Clicks')),
            spend_micro=_micro(r.get('Spend')),
            completions=_int(r.get('Completions')),
            floodlight_conversions=_int(r.get('Floodlight Conversions')),
            conversion_value_micro=_micro(r.get('Conversion Value')),
            measured_at_utc=datetime.utcnow().isoformat(),
        )
        records.append(rec)
    if not records:
        return
    stmt = pg_insert(DV360ReportRow.__table__).values(
        [rec.dict() for rec in records])
    stmt = stmt.on_conflict_do_update(
        index_elements=_PRIMARY_KEY,
        set_={c.name: stmt.excluded[c.name] for c in DV360ReportRow.__table__.columns
              if c.name not in _PRIMARY_KEY},
    )
    session.execute(stmt)
    session.commit()

def _int(v):
    try:
        return int(float(str(v))) if v not in (None, '') else None
    except (ValueError, TypeError):
        return None

def _micro(v):
    """金额字符串（可能带 $/逗号）→ 微单位整数，避免浮点误差。"""
    import re
    if v in (None, ''):
        return 0
    s = re.sub(r'[,$\s]', '', str(v))
    try:
        return int(round(float(s) * 1_000_000))
    except ValueError:
        return 0
```

**为什么金额用微单位整数**：DV360/Google API 的金额字段普遍以 micro（百万分之一货币单位）或字符串返回，浮点 `0.1+0.2` 误差会在对账时累计出"差几分钱"的现象。统一转成整数微单位，用整数运算，最后展示层再转回美元。

**BI 层简易每日日报（Pandas 聚合）**：

```python
def build_daily_report(rows):
    df = pd.DataFrame(rows)
    # 关键派生指标（口径统一在此定义，避免各看板口径漂移）
    df['ctr'] = df['clicks'] / df['impressions'].replace(0, pd.NA)
    df['cpm'] = df['spend_usd'] / df['impressions'] * 1000
    df['viewability'] = (
        df['viewable_impressions']
        / df['measurable_impressions'].replace(0, pd.NA))
    df['roas'] = df['conversion_value_usd'] / df['spend_usd'].replace(0, pd.NA)
    return df.groupby('advertiser_id').agg(
        impressions=('impressions', 'sum'),
        clicks=('clicks', 'sum'),
        spend_usd=('spend_usd', 'sum'),
        floodlight_conversions=('floodlight_conversions', 'sum'),
    ).reset_index()
```

**生产注意事项**：

- **编排而非裸 cron**：用 Airflow/Dagster/Prefect 管理任务 DAG，失败自动重试 + 依赖控制（先等 RDB 定稿窗口再拉）。
- **并发控制**：拉多个广告主时用线程池并发，但注意 DV360 配额（`dv360_get_quota` 可查余量），并发数建议 ≤ 8，避免 429。
- **可重跑**：任务必须可重复执行且幂等——重跑同一天数据用 UPSERT 覆盖，不产生重复行、不丢旧行（防御 RDB 回填修正）。

### 3.2 调度、时区与幂等去重策略

**最常被忽略的三个工程问题**：

1. **T+N 口径的稳定性**：
   - T-1 当天凌晨拉取：数据可能未完稿（CTV/跨媒体回填慢）。
   - 建议：**T-1 暂存，T-3 再定稿覆盖**。即"凌晨拉昨日预览，3 天后拉昨日定稿"双轨，最终以定稿为准。
2. **时区（Timezone）**：
   - 报表的 `DATE` 维度按广告主或账户设置的时区（`dv360_list_time_zones()` 可枚举）切分。
   - 若广告主时区非 UTC，数据库里的 `report_date` 与事件原始 UTC 时间存在偏移，跨系统对账必须统一到同一时区。
   - 典型坑：拉取脚本用 `date.today()-1`（本地时区）去取值，但账户时区是 UTC+8 或美东，导致"日期错位的一天"。
3. **幂等去重**：
   - 同一 Query 重复 run 会产生同一天多条"同主键"记录；UPSERT 按主键覆盖即可。
   - 重试导致的重复：写入侧用 `ON CONFLICT DO UPDATE` 天然去重。
   - 回填修正：RDB 定稿值可能比 LDB 预览值高，必须允许"覆盖旧值"，而非"跳过已有"。

**主键设计（防重 + 允许回填修正）**：

```
主键 = (report_date, advertiser_id, campaign_id,
       insertion_order_id, line_item_id, creative_id,
       device_type, country)
写入 = UPSERT（存在则覆盖 金额/指标 为最新拉取值）
```

这样同一事实键的"预览值"会被"定稿值"覆盖，同时不会因为重复运行产生垃圾行。

### 3.3 对账场景：DV360 报表 vs 第三方 vs 内部埋点

对账是 DV360 报表分析里争议最大的环节。三方数据对不上几乎必然发生，核心是把它拆解成**可控的四类差异**，而不是期待数字相等。

```
三个数据源（同一时期、同一 Campaign）
┌─────────────────────────────────────────────┐
│ DV360 报表     第三方测量方    内部服务端埋点   │
│ （投递/Floodlight） （验证/可见率）（转化/支付）  │
│    |                |               |        │
│    └────────────────┴───────────────┘        │
│                  差异四类                     │
│  ① 口径差：分母/去重/计数方式不同             │
│  ② 时区差：日期边界切点不同                  │
│  ③ 测量差：标签独立性抽样、可测性             │
│  ④ 归因差：归因模型/窗口不同                 │
└─────────────────────────────────────────────┘
```

**对账分析流程**：

```
Step 1  定义"权威源"：投递数→DV360 口径（RDB）；转化→内部支付系统为准
Step 2  对齐日期窗口与时区
Step 3  逐层聚合对比：总数差 → 按 Campaign → 按 LineItem → 按 Creative
        利用分层（钻取）定位差异集中在哪一层
Step 4  对每类差异归因到"四类差"之一
Step 5  设定可接受阈值（如投递差 ±3%，转化差以内部系统为准）
        超阈值才告警，微差记录不告警
```

**一个具体的对账脚本**：

```python
def reconciliation(dv360_df, third_party_df, internal_df, adv_id, report_date):
    """三源对账：返回结构化差异报告。"""
    out = {}

    # ① 投递数：DV360 vs 第三方（取 MEASURABLE 对齐分母）
    d_spend = dv360_df['spend_usd'].sum()
    t_spend = third_party_df['spend_usd'].sum()
    out['spend_diff_pct'] = (d_spend - t_spend) / t_spend if t_spend else None

    d_imp = dv360_df['impressions'].sum()
    t_imp = third_party_df['measurable_impressions'].sum()
    out['impression_diff_pct'] = (d_imp - t_imp) / t_imp if t_imp else None

    # ② 转化：DV360 Floodlight vs 内部支付埋点
    dv_conv = dv360_df['floodlight_conversions'].sum()
    in_conv = internal_df['orders'].sum()
    out['conv_diff'] = dv_conv - in_conv
    # 归因/窗口差异解释：DV360 转化含归因分摊与延迟转化
    out['conv_explanation'] = (
        "DV360 转化含跨触点归因分摊，内部埋点为服务端成交数，"
        "差异主要由归因模型与转化窗口造成")

    # ③ 可见率：DV360 vs Moat/IAS 门户
    dv_view = dv360_df['viewable_impressions'].sum() / \
              dv360_df['measurable_impressions'].sum()
    out['viewability_dv360'] = round(dv_view, 4)
    # 第三方门户单独提供，此处留占位
    out['viewability_third_party'] = None

    return out
```

**对账实战口诀**：

1. **投递看 DV360，转化看内部系统**：展示/花费以 DV360（买方的结算基准）为准；真金白银的成交以内部支付/服务端埋点为准。
2. **可见率看第三方门户 + DV360 双确认**：DV360 内置可见率与测量方门户数值本来就可能差 3~5 个点，别把它们当成"一个数对不上就是 bug"。
3. **差值不是错误，是口径**：先确认单位（万/亿）、时区、去重、窗口，再下结论。
4. **阈值化管理**：投递差通常 <3% 属正常（IVT 扣减、回填时序），转化差不设绝对可比（归因天生不同），核心是"偏差可控 + 有解释"。

### 3.4 维度组合配置示例（Query 编排）

不同分析诉求对应不同的维度/指标/过滤组合。这里给三组典型的 `dv360_get_report` 编排模板，可直接照搬：

**模板 A：日常投放监控（Line Item 日粒度）**

```python
body = {
  'advertiser_id': 123456,
  'dimensions': ['DATE', 'LINE_ITEM', 'DEVICE_TYPE'],
  'metrics': ['IMPRESSIONS', 'CLICKS', 'SPEND', 'VIDEO_VIEWS', 'COMPLETIONS'],
  'date_range': {'start': '2026-08-01', 'end': '2026-08-14'},
}
```

**模板 B：素材优化（Creative 级 + 互动）**

```python
body = {
  'advertiser_id': 123456,
  'dimensions': ['DATE', 'CREATIVE', 'CREATIVE_TYPE'],
  'metrics': ['IMPRESSIONS', 'CLICKS', 'CTR', 'COMPLETIONS', 'VCR',
              'CONVERSIONS'],
  'date_range': {'start': '2026-08-01', 'end': '2026-08-14'},
}
```

**模板 C：可见率与品牌安全专项（验证维度）**

```python
body = {
  'advertiser_id': 123456,
  'dimensions': ['DATE', 'PLACEMENT', 'SENSITIVE_CATEGORY'],
  'metrics': ['IMPRESSIONS', 'MEASURABLE_IMPRESSIONS',
              'VIEWABLE_IMPRESSIONS', 'INVALID_TRAFFIC_IMPRESSIONS',
              'BRAND_SAFETY_IMPRESSIONS'],
  'date_range': {'start': '2026-08-01', 'end': '2026-08-14'},
}
```

**维度组合约束（务必遵守，否则报错或数据为 0）**：

| 约束 | 说明 | 应对 |
|------|------|------|
| 高基数维度互斥 | 部分高基数维度（如 CREATIVE、PLACEMENT）与部分维度不可同时使用 | 查询前用 `dv360_list_breakdowns()` 校验可用组合 |
| 可用组合矩阵 | 不是所有维度×维度都合法 | 建立自己的"可用组合白名单"缓存在配置里 |
| 行数上限 | 单 Query 行数有上限（见 3.5/4.x） | 减少维度组合或按日拆分 |
| 近实时维度 | 小时（HOUR）维仅近 30 天可用 | 长区间自动降级为天级 |

```python
# 组合校验：查询可用 Breakdown，避免构造非法组合
def valid_breakdown(client, dim_a, dim_b):
    breakdowns = client.dv360_list_breakdowns()
    keys = {(b.get('dimensionA'), b.get('dimensionB')) for b in breakdowns}
    return (dim_a, dim_b) in keys or (dim_b, dim_a) in keys
```

### 3.5 踩坑实录（生产环境反复踩过的坑）

这里集结 DV360 报表工程化中最常见的坑，每个都配"现象→根因→解法"。

**坑 1：报表一行都没有（空报表）**

- 现象：Query 返回 DONE，但下载下来只有列名没有数据行。
- 根因（逐个排查）：
  1. 日期窗口超出数据存在范围（未来日期/过早日期）。
  2. 过滤（Filter）写死了不存在的值（如写错 Campaign ID）。
  3. 该账户该时间窗确实没有投放（预算暂停/未开始）。
  4. 维度组合导致该行被系统过滤（如"无点击"行被某些视图剔除）。
- 解法：先去掉 Filter 空跑一次确认有数；检查日期与账户层级 ID；确认投放状态。

**坑 2：Filter 语法错误**

- 现象：Query 创建或运行时报参数错误。
- 根因：Filter 要求精确的字段名/枚举值，例如交易类型要用 `TRANSACTION_TYPE` 的合法枚举（`PROGRAMMATIC_GUARANTEED`/`PRIVATE_MARKETPLACE`/`PREFERRED_DEAL`/`OPEN_AUCTION`，对应 `get_transaction_type_options`）。
- 解法：用 `dv360_list_dimension_values(dimension)` 拉合法值再拼 Filter，绝不手写魔法字符串；非法值时先枚举校验。

```python
# 合法交易类型（dv360_api.get_transaction_type_options 返回）
TRANSACTION_TYPES = [
    'PROGRAMMATIC_GUARANTEED',  # 程序化保量
    'PRIVATE_MARKETPLACE',      # 私有市场
    'PREFERRED_DEAL',           # 优先交易
    'OPEN_AUCTION',             # 公开竞价
]

def assert_valid_filter(dimension, value):
    # 伪代码：先用 dimensionValues 校验 value 在枚举内
    if not _is_known_dimension_value(dimension, value):
        raise ValueError(f"invalid {dimension}={value}")
```

**坑 3：Date Range 时区错位**

- 现象：拉出来的"昨天"数据在账户时区里其实是"前天"或"今天"。
- 根因：脚本时间取自本地/服务器时区，账户报表按广告主时区切天。
- 解法：统一基准时区；确认账户时区（`dv360_list_time_zones()`）；跨时区对账时两端都转 UTC 的日期边界。

**坑 4：行数超上限被截断**

- 现象：报表以为全量，实际被截断，或导入数据库后总数远小于 DV360 内报表。
- 根因：单 Query 行数超过平台上限（高基数维度 + 长区间最容易触发）。
- 解法：按日拆分 + 减少高基数维度组合；或用 `dv360_get_breakdown_report` 类细分再合并；用 `dv360_get_quota` 监控余量，避免超限被限流。

**坑 5：Metric 口径对不上（同一指标两处数值不同）**

- 现象：UI 报表、Query 导出、CPI 接口三个地方"展示数/花费"都不一样。
- 根因：
  1. 一个取 LDB（UI 实时）一个取 RDB（导出）——首要嫌疑。
  2. 可见率分母不同（可测 vs 总展示）。
  3. 花费含/不含返点、扣费 vs 合同价。
- 解法：先统一数据等级（都取 RDB 定稿），再统一口径公式，最后看是否跨媒体回填未完（CTV）。

**坑 6：SQL/BI 里金额或大数变科学计数/精度丢失**

- 现象：花费 1234567.89 在 CSV → Excel → DB 过程中变 1.23457e+06，或对账差几分钱。
- 根因：字符串转 float 的精度问题；CSV 科学计数法解析错误。
- 解法：金额用微单位整数（见 3.1 `_micro`）；CSV 解析时指定列类型，禁止自动转 float。

**坑 7：配额打爆（429/QuotaExceeded）**

- 现象：批量拉报表时报 quota exceeded。
- 根因：并发拉取 + 频繁轮询超出 `display-video` 配额。
- 解法：
  - 用 `dv360_get_quota(advertiser_id)` 查询当前余量。
  - 控制并发 ≤ 8、轮询间隔 ≥ 15s。
  - 对瞬时 429 做指数退避重试（见 2.6 Go 引擎的 `withRetry`）。

## 四、常见问题与排查

### 4.1 FAQ 总览表（速查）

按"数据延迟 / 数据一致性 / 维度 / 指标 / 对账 / 导出"六大类整理高频问题，详情见后续小节。

| 分类 | 问题 | 一句话结论 |
|------|------|------------|
| 数据延迟 | 为什么今天报表数和昨天 UI 不同？ | LDB 显示级 vs RDB 定稿级，等 24-48h 稳定 |
| 数据延迟 | CTV/YouTube 数据为什么老不出来？ | 跨媒体回填慢，3~5 天起 |
| 数据一致性 | 报表出现同一天多条同维度记录 | Query 重复 run，建主键 UPSERT 去重 |
| 数据一致性 | 重跑后数值变小/变大 | RDB 回填修正，允许覆盖而非跳过 |
| 维度 | 为什么这个维度组合报错/返回空 | 高基数维度互斥/组合不合法，用 breakdowns 校验 |
| 维度 | 小时维度只能看近 30 天 | 平台限制，长区间降级天级 |
| 指标 | 显示/花费/转化各自对不上 | 取数据等级与口径公式不一致 |
| 指标 | 可见率两个数字差很多 | 分母（可测 vs 总）不同，统一口径 |
| 对账 | DV360 vs 第三方 vs 内部三方对不上 | 四类差异（口径/时区/测量/归因），阈值化管理 |
| 对账 | 金额差几分钱 | 金额用微单位整数，避免浮点误差 |
| 导出 | CSV 大数变科学计数/截断 | 指定列类型，转微单位整数 |
| 导出 | 报表被截断/行数超限 | 按日拆分、减少高基数组合 |
| 配额 | 429 QuotaExceeded | 查 quota、控并发、指数退避重试 |

### 4.2 数据延迟类 FAQ

**Q1：为什么"今天白天 UI 看到的展示数"和"次日报表导出的展示数"不一样？**

这是 LDB（显示级，近实时）与 RDB（上报级，定稿）的差异。UI 内置报表与 pacing 监控走 LDB，分钟级刷新但会回填修正；导出/自定义报表/API 报表走 RDB，通常 24-48h 定稿。当天下班前看到的数偏低是正常的，第二天会补记。

**处理建议**：需要"当天看、当天降级用"看 LDB；需要"对账/入库/汇报"必须等 RDB 定稿，统一用 T-2 口径。

**Q2：为什么 CTV / OTT / YouTube 的数据好久才稳定？**

CTV/OTT 及部分 YouTube 库存的回填跨越多个中介与卖方系统，RDB 定稿周期比 Web/App 展示长，常见 3~5 天甚至更久。若报表里这类库存占比高，'着急等数'是常态，要接受"稳定窗口拉长"并调整 T+N 策略。

**Q3：程序化保量（PG）/私有市场（PMP）的对账数据为什么不及时？**

PG/PMP 涉及买卖双方合同对账，需要卖方（Seller）回填确认，延迟取决于各 SSP/发布商的回填节奏。`dv360_list_seller_metrics(seller_id)` 可单独查看某个卖方的指标，`dv360_list_invoice_history` 提供结算口径（invoice 级）用于最终对账。

```python
# 按卖方查看指标：定位"个别卖家数据滞后"
def seller_delay_check(client, seller_ids):
    lagged = []
    for sid in seller_ids:
        m = client.dv360_list_seller_metrics(seller_id=sid)
        if m.get('metrics', {}).get('impressions', 0) == 0:
            lagged.append({'seller': sid, 'likely_lag': True})
    return lagged
```

**Q4：有没有办法判断"当前拉的这版数据是不是定稿"？**

没有直接标"定稿"的字段，工程上靠两条推断：
1. **时间冗余**：只认"数据日期至少落后当前日期 2~3 天"的行。
2. **趋势稳定**：连续两天对 T-D 拉取，数值不再变化即认为稳定（可在入库侧加"修订标记：`revision=1|2`，最后以 revision 最大且已稳定为准"）。

### 4.3 数据一致性 / 重复数据类 FAQ

**Q5：为啥表里出现"同一天、同维度，但多行指标不同"的记录？**

成因有二：
1. **Query 被重复 run**：同一 Query 一天内手动 + 自动各 run 一次，会产生两次报表文件，导入时若没按主键 UPSERT，就叠加出多行。
2. **不同数据等级混入**：LDB 预览与 RDB 定稿混在同一张表（未统一）。

**解法**：入库一律 UPSERT（主键见 3.2），重复 run 直接覆盖；表里加 `source_level` 与 `measured_at_utc` 列，方便追溯"这行是哪一版拉的"。

```sql
-- PostgreSQL UPSERT 去重模板（同天同维度只保留最新版本）
INSERT INTO dv360_report AS t
  (report_date, advertiser_id, line_item_id, impressions, clicks, spend_micro,
   source_level, measured_at_utc)
VALUES (:report_date, :adv, :li, :imp, :clk, :spend, :level, :ts)
ON CONFLICT (report_date, advertiser_id, line_item_id)
DO UPDATE SET
  impressions     = EXCLUDED.impressions,
  clicks          = EXCLUDED.clicks,
  spend_micro     = EXCLUDED.spend_micro,
  source_level    = EXCLUDED.source_level,
  measured_at_utc = EXCLUDED.measured_at_utc
WHERE EXCLUDED.measured_at_utc >= t.measured_at_utc;
```

**Q6：重跑某天任务，为什么某些行指标"变小"了？**

不是 bug。RDB 在回填滞后时会把 "错报的当日值"修正为"定稿值"（例如先把所有展示计入，后续扣减 IVT/重复后变小）。因此重跑必须**允许覆盖旧值**，而不是 `INSERT IGNORE` 跳过已有行——否则你会永远卡在"预览值"上。

**Q7：怎么防止"重复 run"本身？**

- 调度器层保证同一个 task（date+advertiser）只在一个实例运行（Airflow `max_active_runs`、分布式锁）。
- API 层用"Query 复用 + run-id 幂等"：同一天触发同一 Query 前先查 `reports.list`，已有 DONE 的当天报表则直接复用，不重复 run。
- 写入层用 UPSERT 兜底（最终防线）。

### 4.4 维度类 FAQ

**Q8：为什么有些维度拼在一起就报错？**

DV360 的高基数维度（CREATIVE、PLACEMENT 等）之间存在组合互斥或数量限制，不是所有"维度×维度"都合法。报错信息通常是"dimensions not compatible"之类。

**解法**：查询前用 `dv360_list_breakdowns()` 拉取当前账户 "允许组合"清单做白名单校验，避免运行时才炸。自建一张"可用组合缓存表"让前端下拉只展示合法组合。

**Q9：为什么"小时"维度拉不到长区间？**

HOUR 维通常只覆盖近 30 天（数据保留策略决定）。拉取长历史改成天级 `DATE`。

**Q10：为什么按这个维度切后总行数和按另一个维度切对不上？**

不同维度的行数天然不等——两个维度的"事实粒度"不同：按 CREATIVE 切每行一个素材，按 DATE 切每行一天，交叉后行数是笛卡尔积，不是同一个事实键。对比时必须"固定事实键"（例如都用 `(DATE, LINE_ITEM)` 作为基准）再展开，否则会误以为漏行。

### 4.5 指标类 FAQ

**Q11：展示数、点击数"对不上"是普遍现象吗？**

是，且正常。展示以 DV360 投递口径（RDB）为准；点击存在"点击去重"（同一次点击跨多次展示只计 1），不同计数方式数值不同。对账时先定义"以哪个口径为基准"，不要指望三方完全相等。

**Q12：可见率为什么有两个不同的数？**

因为分母定义不同：
- 口径 A：可见展示 / 可测量展示（Google/行业常用）
- 口径 B：可见展示 / 总展示（含不可测）

口径 B 永远 ≤ 口径 A。分析可见率时统一注明分母，不要在报告里混用。工程上用 `MEASURABLE_IMPRESSIONS` 作分母更符合行业标准。

**Q13：Floodlight 转化为什么和"后台支付单数"差很多？**

转化天然含：
- **归因分摊**：一笔交易可能被分摊到多个触点（跨渠道），报表里"转化数"大于"唯一成交数"。
- **转化窗口**：点击后 30/60/90 天内才转化也算，延迟转化会把"未来转化"也算进当期。
- **计数方式**：SESSION/UNIQUE/TRANSACTION 三选一不同，数值不同。

对转化以"内部支付/服务端埋点"为真金白银的权威，DV360 转化用于"优化与归因"，两者各司其职（见 3.3）。

**Q14：花费（SPEND）为什么和财务/发票对不上？**

`SPEND` 是展现级扣费成本，不含返点（rebate）、返利，可能与合同价/发票（invoice）存在差异。财务对账用 `dv360_list_invoice_history` 与 `dv360_get_payment_methods`/`dv360_list_billing_info` 的结算口径。

```python
# 区分"花费口径"与"结算口径"
def cost_story(client, advertiser_id):
    spend = client.dv360_get_report(advertiser_id)['spend']  # 扣费口径
    invoices = client.dv360_list_invoice_history(advertiser_id)
    return {
        'spend_cost_basis': spend,          # 展示计费
        'invoice_total': sum(i['amount'] for i in invoices),  # 发票口径
        'note': '两者差异来自返点/返利/扣减，需财务确认',
    }
```

### 4.6 对账类 FAQ

**Q15：DV360、第三方、内部埋点三方"必须相等"吗？**

不必，也不可能完全相等。真正的对账目标是：**差异在可控阈值内，且每一类差异都能解释清楚**。常见可靠对账基准：
- 投递（展示/花费）：以 DV360 RDB 为权威（买方结算基准）。
- 可见率：以第三方门户 + DV360 双确认，允许 ±3~5 点。
- 转化/成交：以内部支付为权威。

**Q16：对账差太多，第一步该查什么？**

按性价比排序：
1. **数据等级**：是否混用了 LDB/RDB。
2. **时区与日期边界**：两端是否同一天。
3. **去重/计数方式**：SESSION/UNIQUE/TRANSACTION 是否一致。
4. **单位**：万/亿、货币、微单位换算。
5. **口径公式**：可见率分母、ROAS 用归因价值还是销售价值。

先用分层（Campaign→LineItem→Creative）钻取定位差异集中在哪一层，再针对该层查上面五类，避免大海捞针。

### 4.7 导出 / 配额类 FAQ

**Q17：CSV 里大数变成科学计数法/精度丢失怎么办？**

DV360 导出金额字段常带 `$`、逗号，或由平台格式化；导入 Excel/CSV 引擎时被自动转成科学计数，导致精度丢失。解法：
- 金额字段统一 `_micro` 转微单位整数（见 3.1），入库前不保留"展示格式"。
- 解析时对列显式声明类型（`dtype`），禁止 pandas/Excel 自动推断 float。
- 用 `utf-8-sig` 解码处理 BOM，避免首列字段名带 `\ufeff`。

```python
def safe_parse(csv_path, numeric_cols):
    import pandas as pd
    df = pd.read_csv(csv_path, encoding='utf-8-sig',
                     dtype={c: str for c in numeric_cols})  # 先全部读为文本
    for c in numeric_cols:
        df[c] = df[c].str.replace(r'[,$\s]', '', regex=True)
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return df
```

**Q18：单次报表行数超上限被截断怎么办？**

触发上限时有的版本直接截断（静默），有的报错。应对：
- **拆**：按日拆分（`DATE` 一列一天一拉），或减少高基数维度组合。
- **降**：降低颗粒度（CREATIVE 级 → LINE_ITEM 级）。
- **并**：多文件分别入库后用 SQL 按事实键聚合，不手工拼大 CSV。
- **追**：记录"每个 Query 实际行数"，逼近上限时提前告警。

**Q19：批量拉报表经常 429 / QuotaExceeded？**

DV360 API 有配额（`dv360_get_quota(advertiser_id)` 可查余量）。缓解：
- 并发 ≤ 8，轮询间隔 ≥ 15s。
- 对 429 做指数退避重试（见 2.6 `withRetry`）。
- 非关键任务错峰运行，避免与上游其他任务抢配额。

### 4.8 排查决策树（一图流）

```
报表数据出问题，从哪查起？
│
├─ 1) 数值"变/少/多"？
│    ├─ 是 → 查数据等级 LDB/RDB？回填时序？
│    └─ 否 → 下一步
│
├─ 2) 有重复行？
│    ├─ 是 → 检查 Query 重复 run + 主键 UPSERT
│    └─ 否 → 下一步
│
├─ 3) 某种定向上"没数"？
│    ├─ 是 → 维度组合合法性（breakdowns）/过滤值 / 投放状态
│    └─ 否 → 下一步
│
├─ 4) 与第三方/内部对不上？
│    ├─ 是 → 三源对账四类差（口径/时区/测量/归因）+ 分层钻取
│    └─ 否 → 下一步
│
└─ 5) 拉取失败/超时/限流？
     ├─ 429/quota → 控并发 + 退避重试 + 查 quota
     ├─ 超时 → 看 Query 体积，拆日期/降颗粒度
     └─ FAILED → 先重试一次 run；连续失败告警
```

### 4.9 运维与监控清单

生产跑报表流水线，建议把下面这几项做成自动化监控（Proactive 而非火急火燎）：

| 监控项 | 指标 | 触发告警 | 频率 |
|--------|------|----------|------|
| 拉取成功率 | 每广告主日任务成功与否 | 任一失败即告警 | 每任务 |
| 行数突变 | 某天总行数较 7 日均值 ±30% | 突增突减告警 | 每日 |
| 数值突变 | 总展示/花费较前日 ±20% | 异常告警 | 每日 |
| 数据等级混用 | source_level 列非预期 | 检测到 LDB+RDB 混入 | 每日 |
| 配额余量 | dv360_get_quota 余量 < 20% | 预警告警 | 每小时 |
| 对账偏差 | 三源差值超阈值 | 超阈告警 | 每日 |
| 查询体积 | 单 Query 行数逼近上限 | 提前拆分告警 | 每周 |

```python
def anomaly_check(daily_totals):
    """简单的突变检测：与 7 日均值对比，超 ±20% 告警。"""
    from statistics import mean
    alerts = []
    keys = ['impressions', 'spend_usd', 'clicks']
    for k in keys:
        hist = [d[k] for d in daily_totals[-8:-1]]
        base = mean(hist) or 1.0
        latest = daily_totals[-1][k]
        pct = (latest - base) / base
        if abs(pct) > 0.2:
            alerts.append(f"{k} 突变 {pct:+.1%} (最新={latest}, 7日均={base:.0f})")
    return alerts
```

## 五、自测题

通过以下问题检验你对 DV360 报表与数据分析的理解。答案用 `<details>` 折叠，建议先自答再看。

### 问题 1：为什么同一天在 UI 内嵌报表看到的展示数，与当天导出的自定义报表数字不同？工程上应如何取数？

<details>
<summary>查看答案</summary>

UI 内嵌报表与 pacing 监控走 **LDB（显示级/Logs Data Base）**，近实时（分钟级）但会回填修正；自定义报表 / Query / API 导出走 **RDB（上报级/Reports Data Base）**，通常 24-48h 定稿。两者数据源不同，当天看数偏低的“差异”是回填未完成，不是 bug。

工程原则：
- 需要“当天实时看数”用 LDB，但要接受波动。
- 涉及对账、入库、汇报、结算一律取 **RDB 定稿**，并采用 **T-2**（滞后两天）作为稳定口径。
- CTV/OTT/YouTube 与 PG/PMP 库存回填更慢（3~5 天起），稳定窗口要相应拉长，涉及结算看 invoice 口径。
</details>

### 问题 2：报表里同一个（日期、广告主、LineItem）出现多行且指标不同，可能的原因与解法是什么？

<details>
<summary>查看答案</summary>

原因：
1. **Query 被重复 run**：同一 Query 一天内被手动 + 自动各触发一次，产生两个报表文件，导入时未按主键合并就叠加出多行。
2. **LDB 预览版与 RDB 定稿版混在表里**。

解法：
- 写入层用 **UPSERT / INSERT ... ON CONFLICT**，主键取事实键 `(report_date, advertiser_id, campaign_id, insertion_order_id, line_item_id, creative_id, device_type, country)`，存在即覆盖。
- 表里加 `source_level`、`measured_at_utc` 列便于追溯“哪一版拉的”。
- 调度层保证同一 task 单实例运行（分布式锁 / `max_active_runs`），API 层同一天复用已 DONE 的 Query 结果，不重复 run。
</details>

### 问题 3：可见率有两种算出不同数值，原因是什么？应该如何统一？

<details>
<summary>查看答案</summary>

差在**分母**：
- 口径 A：`可见展示 / 可测量展示`（Google/行业常用）。
- 口径 B：`可见展示 / 总展示`（含不可测量部分）。

口径 B 往往更小，因为不可测的展示在分母里拉低了比率。工程上统一用 `MEASURABLE_IMPRESSIONS` 做分母（更符合行业标准），并在报表/看板里注明“分母=可测量展示”，避免口径漂移。与第三方（Moat/IAS/DoubleVerify）对账时也先对齐分母：双方都以“可测量展示”为对齐基准，允许 ±3~5 点差异。
</details>

### 问题 4：DV360、第三方测量方、内部服务端埋点三方数据对不上，正确态度与排查顺序是什么？

<details>
<summary>查看答案</summary>

**态度**：三方不可能完全相等，目标不是“相等”而是“差异可控且有解释”。

**可信基准**：
- 投递（展示/花费）：以 DV360 RDB 为权威（买方结算基准）。
- 可见率：第三方门户 + DV360 双确认。
- 转化/成交：以内部支付/服务端埋点为权威。

**排查顺序（按性价比）**：
1. 数据等级：是否混用 LDB/RDB。
2. 时区与日期边界：两端是否同一天。
3. 去重/计数方式：SESSION/UNIQUE/TRANSACTION。
4. 单位：万/亿、货币、微单位。
5. 口径公式：可见率分母、ROAS 归因 vs 销售价值。

最后用分层（Campaign→LineItem→Creative）钻取定位差异集中在哪一层，再查该层上面的五类。
</details>

### 问题 5：单 Query 行数超上限被截断，如何规避？

<details>
<summary>查看答案</summary>

- **拆**：按日拆分（`DATE` 一天一拉），或减少高基数维度组合。
- **降**：降低颗粒度（CREATIVE → LINE_ITEM 级）。
- **并**：多文件分别入库后用 SQL 按事实键聚合，不手工拼大 CSV。
- **追**：记录每个 Query 的实际行数，逼近上限提前告警。
- 组合不合法先查 `dv360_list_breakdowns()`，避免构造非法的高基数互斥组合。
</details>

## 六、附：DV360 报表相关 API 方法速查与进阶工程模式

本附录把本文引用的真实方法整理成速查表，并给出 BigQuery/数仓集成、增量加载、回填修正、多广告主汇总等进阶工程模式，供直接落地参考。

### 6.1 报表相关 API 方法速查表

方法名取自 `scripts/ad_platform_api.py` 与 `scripts/dv360_api.py`（已核验存在）。可按"取数 / 元数据 / 管理 / 度量"分组查找。

**取数（报表数据主体）**

| 方法 | 入参要点 | 返回/用途 |
|------|----------|-----------|
| `dv360_get_report(advertiser_id, dimensions=[...], metrics=[...], date_range={...})` | 维度数组 + 指标数组 + 日期窗 | 报表主体数据（默认 CAMPAIGN / IMPRESSIONS/CLICKS/SPEND） |
| `dv360_sync_report(advertiser_id, date_range={...})` | 日期窗 | 触发一次全量同步，供轮询拿结果 |
| `get_report(advertiser_id, date_start, date_end, level='CAMPAIGN', dimensions=None)` | 显式起止 + 层级 + 维度 | `dv360_api.py` 风格客户端：POST `reports/generate` |
| `dv360_list_dimension_values(dimension)` | 单个维度名 | 枚举某维度的合法取值（下拉/过滤校验） |
| `dv360_get_report_metrics(advertiser_id)` | 广告主 id | 返回指标定义清单 |
| `dv360_list_report_dimensions()` | 无 | 返回可用维度清单 |
| `dv360_list_report_metrics()` | 无 | 返回可用指标清单 |
| `dv360_list_breakdowns()` | 无 | 返回"维度×维度"合法组合，用于组合校验 |

**管理 / 度量辅助**

| 方法 | 返回/用途 |
|------|-----------|
| `dv360_list_floodlight_configs(advertiser_id)` | Floodlight 配置（转化口径映射） |
| `dv360_list_seller_metrics(seller_id)` | 单卖方指标（定位个体滞后） |
| `dv360_list_usage_stats(advertiser_id)` | 用量统计（配额审计） |
| `dv360_list_performance_stats(advertiser_id)` | 性能统计（体量/趋势） |
| `dv360_get_quota(advertiser_id)` | 当前配额余量（避免 429） |
| `dv360_list_cross_channel_reports(account_id)` | 跨渠道报表（Google Ads/CM360 打通） |
| `dv360_list_time_zones()` | 可用时区（日期边界对齐） |
| `dv360_list_currency_options()` | 货币选项（金额口径） |
| `dv360_list_invoice_history(advertiser_id)` | 发票/结算口径（对账权威） |
| `dv360_list_billing_info(advertiser_id)` | 计费信息 |
| `dv360_list_ad_verification_services()` | 第三方验证服务商 |
| `dv360_list_brand_safety_providers()` | 品牌安全服务商 |
| `dv360_list_viewability_providers()` | 可见率提供商 |

**选项枚举（dv360_api.py）**

| 方法 | 用途 |
|------|------|
| `get_transaction_type_options()` | 交易类型（PG/PMP/PD/Open） |
| `get_bid_strategy_options()` | 出价策略（CPM/CPC/CPV/oCPM/CPA） |
| `get_creative_format_options()` | 创意格式 |
| `get_targeting_dimension_options()` | 定向维度（GEO/AGE/…） |

**认证与账户**

| 方法 | 用途 |
|------|------|
| `dv360_auth()` | OAuth 认证入口 |
| `dv360_list_advertisers(partner_id)` | 拉广告主清单（每日任务起点） |
| `dv360_get_customer(customer_id)` / `dv360_list_customers()` | 客户信息 |
| `dv360_validate_credentials()` | 凭证有效性自检 |
| `dv360_list_api_versions()` / `dv360_get_api_version(version)` | 版本检查 |

### 6.2 用量与配额监控（避免拉取被限流）

批量拉取前先看配额，拉取中实时监控余量，是避免生产任务大面积失败的底线：

```python
def quota_safe_run(client, advertiser_id, quota_min_pct=0.2):
    """拉取前检查配额余量，不足则降并发/错峰。"""
    quota = client.dv360_get_quota(advertiser_id=advertiser_id)
    used = quota.get('used', 1)
    limit = quota.get('limit', 1)
    pct = 1 - used / limit if limit else 1.0
    if pct < quota_min_pct:
        log.warning('quota low: used=%s limit=%s', used, limit)
        # 可在此降并发、错峰或告警
    return pct
```

### 6.3 BigQuery / 数仓集成（BI 落地规范）

DV360 报表入库后进入数仓做统一分析。这里给 BigQuery 侧的建表与加载规范，避免"能查但口径混乱"。

**建表规范（BigQuery 分区 + 聚簇）**：

```sql
CREATE OR REPLACE TABLE `ad.dv360_daily_report`
PARTITION BY report_date
CLUSTER BY advertiser_id, line_item_id
AS SELECT
  DATE '1970-01-01' AS report_date,
  CAST(NULL AS INT64) AS advertiser_id,
  CAST(NULL AS INT64) AS campaign_id,
  CAST(NULL AS INT64) AS insertion_order_id,
  CAST(NULL AS INT64) AS line_item_id,
  CAST(NULL AS STRING) AS device_type,
  CAST(NULL AS STRING) AS country,
  CAST(0 AS INT64) AS impressions,
  CAST(0 AS INT64) AS clicks,
  CAST(0 AS INT64) AS spend_micro,
  CAST(0 AS INT64) AS completions,
  CAST(0 AS INT64) AS floodlight_conversions,
  CAST(0 AS INT64) AS conversion_value_micro,
  CAST('' AS STRING) AS source_level,
  CAST('' AS STRING) AS measured_at_utc
WHERE FALSE;
```

**加载（增量 UPSERT，BigQuery MERGE）**：

```sql
MERGE `ad.dv360_daily_report` t
USING `ad.dv360_daily_report_stage` s
ON t.report_date = s.report_date
   AND t.advertiser_id = s.advertiser_id
   AND t.line_item_id = s.line_item_id
WHEN MATCHED THEN
  UPDATE SET
    impressions = s.impressions,
    clicks = s.clicks,
    spend_micro = s.spend_micro,
    source_level = s.source_level,
    measured_at_utc = s.measured_at_utc
WHEN NOT MATCHED THEN
  INSERT (report_date, advertiser_id, campaign_id, insertion_order_id,
          line_item_id, device_type, country, impressions, clicks,
          spend_micro, completions, floodlight_conversions,
          conversion_value_micro, source_level, measured_at_utc)
  VALUES (s.report_date, s.advertiser_id, s.campaign_id, s.insertion_order_id,
          s.line_item_id, s.device_type, s.country, s.impressions, s.clicks,
          s.spend_micro, s.completions, s.floodlight_conversions,
          s.conversion_value_micro, s.source_level, s.measured_at_utc);
```

### 6.4 增量加载、回填修正与多广告主汇总

**增量加载（避免每天全量啃历史）**：

```python
def incremental_load(client, advertisers, as_of, lookback_days=3):
    """只拉"as_of 往前 lookback_days"窗口，覆盖末端可能的回填修正。"""
    start = as_of - timedelta(days=lookback_days)
    for adv in advertisers:
        for d in daterange(start, as_of):          # 逐日拉，天然"分页"
            query_id, report_id = create_query(
                client, adv, f"incr_{d.isoformat()}", d, d,
                ['LINE_ITEM'], DEFAULT_METRICS)
            wait_for_report(client, query_id, report_id)
            upsert_rows(download_report_csv(client, query_id, report_id),
                        adv, d.isoformat())
```

**回填修正（双版本：预览 → 定稿）**：

```
T-1 凌晨  拉取预览版（source_level=preview，T-1 数据）
T+1 凌晨  再拉 T-1 的定稿版（source_level=final，覆盖 preview）
最终表里  T-1 只保留 final 版本（UPSERT 已覆盖）
```

这种"预览 + 定稿"双轨，既满足"当天晨会能看到数据"，又保证"入库最终是定稿值"，是回填修正的标准工程解法。

**多广告主汇总看板（中毒聚合防泄漏）**：

```python
def aggregate_all(rows):
    """跨广告主、跨 IO 汇总，供大盘周报。"""
    import pandas as pd
    df = pd.DataFrame(rows)
    return df.groupby(['report_date', 'advertiser_id']).agg(
        impressions=('impressions', 'sum'),
        clicks=('clicks', 'sum'),
        spend_micro=('spend_micro', 'sum'),
        floodlight_conversions=('floodlight_conversions', 'sum'),
    ).reset_index()
```

**口径词典（团队协作必备）**：为每个口径写死"公式 + 分母 + 时区 + 数据等级"，避免多个看板各写一套导致结论打架：

```yaml
# metrics_glossary.yaml（口径词典示例，下游看板强制引用）
ctr:
  formula: clicks / impressions
  data_level: RDB_final
  note: 全量分母，含无点击展示
viewability:
  formula: viewable_impressions / measurable_impressions
  formula_alt: viewable_impressions / impressions
  default: measurable_impressions
  note: 分母可测，行业标准
roas:
  formula: conversion_value / spend
  data_level: RDB_final
  note: 归因价值口径，非销售价值
spend_basis: cost_after_IVT
invoice_basis: invoice_total_includes_rebate
timezone: Asia/Shanghai
data_window: T-2_final
```

### 6.5 进阶：把报表分析接进 AI / Agent（自动化洞察）

报表体系沉淀数仓后，可由 Agent 引擎每日自动产出"异常摘要 + 优化建议"：

```python
def daily_insights(con, advertisers):
    """汇总当日异常与建议，供 Agent 生成日报。"""
    alerts = []
    for adv in advertisers:
        totals = load_totals(con, adv)             # 近 8 日
        alerts += anomaly_check(totals)            # 突变检测（见 4.9）
        # 派生出优化信号：高花费低 ROAS 的 LineItem 降级候选等
        candidates = low_roas_line_items(con, adv)
        alerts.append(f"{adv}: {len(candidates)} 个低 ROAS LineItem")
    return {
        'date': date.today().isoformat(),
        'alerts': alerts,
        'prompt': build_prompt(add_accounting, alerts),
    }
```

**落地建议**：Agent 负责"读数 → 发现偏离 → 起草建议"，人负责放行与执行（如调预算、换创意）。报表层只做"确定性计算"，优化动作保留人工确认，避免自动化误伤。

### 6.6 一个 30 分钟上手的清单（从零到日报）

```
□ 1) 认证：dv360_auth() 打通服务账号，validate_credentials() 自检
□ 2) 拉广告主清单：dv360_list_advertisers()
□ 3) 建第一条 Query：LINE_ITEM 级 + IMPRESSIONS/CLICKS/SPEND + 昨天
□ 4) 轮询 DONE → 下载 CSV
□ 5) 解析 + 金额转微单位 + 建主键
□ 6) UPSERT 入库（PostgreSQL/BigQuery）
□ 7) BI 连数仓出第一张日报
□ 8) 加对账脚本 + 突变告警 + 配额监控
```

### 6.7 本文档与姊妹文档的关系速查

| 需要解决 | 看这份 | 出口 |
|----------|--------|------|
| 报表体系与数据链路、LDB/RDB、维度指标、拉取引擎 | 本文（一、二） | 理解"数从哪来" |
| 自动化入库、对账、踩坑、FAQ | 本文（三、四、六） | 落地"数怎么用" |
| 归因模型原理 | dv360-measurement-attribution-deep.md | 归因引擎实现 |
| 平台架构、RTB、定向 | dv360-architecture-deep.md | 账户/定向上下文 |
| 优化策略与 KPI 基准 | dv360-optimization-deep.md | 优化动作 |
| API 认证骨架 | dv360-marketing-api-deep.md | 客户端封装 |

## 结语

DV360 报表与分析不是"拉个数"，而是一整套工程：**分清 LDB/RDB 数据等级、固化维度指标口径、打通 Floodlight 与跨渠道归因、接入第三方测量、用可重试可幂等的引擎每日入库、并对三源数据做阈值化对账**。把这套体系跑稳，投放的每一分钱花得值不值、对得上对不上，才真正可答、可查、可优化。

## 七、附录：端到端生产示例与速查

### 7.1 生产级 Python 拉取模块（可直接套用骨架）

把前面的散点代码收拢成一个可维护模块，给出文件结构与关键函数职责，方便直接在新项目里起底。

```
dv360_reporting/
├── __init__.py
├── client.py          # dv360 client 封装（build + 认证 + 通用 request）
├── queries.py         # create_query / run / wait / download（二步曲逻辑）
├── parser.py          # CSV → DV360ReportRow 解析与口径映射
├── store.py           # 数据库 UPSERT（PostgreSQL / BigQuery 两套适配）
├── sched.py           # 每日任务编排（并发 + 重试 + 幂等）
├── reconcile.py       # 三源对账
├── monitor.py         # 突变/配额/行数告警
└── glossary.yaml      # 口径词典
```

**queries.py（Query 生命周期封装）**：

```python
"""
Query 生命周期：create → run → wait → download。
Query 一旦创建长存，run 只触发一次报告生成（幂等复用）。
"""
class QueryClient:
    def __init__(self, service):
        self.service = service

    def get_or_create(self, advertiser_id, title, body, reuse=True):
        """复用同名已存在 Query，否则新建。避免每天生成一堆孤儿 Query。"""
        if reuse:
            for q in self.list(advertiser_id):
                if q.get('query', {}).get('metadata', {}).get('title') == title \
                   and q.get('query', {}).get('timeRange') == body.get('timeRange'):
                    return q['queryId']
        resp = self.service.queries().create(
            body={'advertiserId': advertiser_id,
                  'query': body, 'runNow': True}).execute()
        return resp['queryId']

    def list(self, advertiser_id, page_size=100):
        results = []
        token, = None,  # placeholder
        page_token = None
        while True:
            resp = self.service.queries().list(
                advertiserId=advertiser_id, pageSize=page_size,
                pageToken=page_token).execute()
            results.extend(resp.get('queries', []))
            page_token = resp.get('nextPageToken')
            if not page_token:
                break
        return results

    def run(self, query_id):
        return self.service.queries().run(queryId=query_id).execute()
```

**parser.py（CSV → 标准行，含口径映射）**：

```python
def to_report_rows(csv_rows, adv_id, report_date, source_level='final'):
    """把 DV360 导出的行列映射为 DV360ReportRow 标准模型。"""
    out = []
    for r in csv_rows:
        out.append(DV360ReportRow(
            report_date=report_date,
            advertiser_id=adv_id,
            campaign_id=_int(r.get('Campaign ID')),
            insertion_order_id=_int(r.get('Insertion Order ID')),
            line_item_id=_int(r.get('Line Item ID')),
            creative_id=_int(r.get('Creative ID')),
            device_type=r.get('Device Type') or r.get('Device'),
            country=r.get('Country'),
            impressions=_int(r.get('Impressions')),
            clicks=_int(r.get('Clicks')),
            spend_micro=_micro(r.get('Spend')),
            completions=_int(r.get('Completions')),
            floodlight_conversions=_int(r.get('Floodlight Conversions')),
            conversion_value_micro=_micro(r.get('Conversion Value')),
            measured_at_utc=datetime.utcnow().isoformat(),
        ))
    return out
```

**sched.py（每日任务：并发 + 失败隔离 + 可重跑）**：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def daily_job(client, advertisers, as_of=None, max_workers=8):
    as_of = as_of or date.today()
    target = as_of - timedelta(days=2)      # T-2 定稿口径
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(run_one_advertiser, client, adv, target): adv
                for adv in advertisers}
        results = {}
        for fut in as_completed(futs):
            adv = futs[fut]
            try:
                results[adv] = {'status': 'ok', **fut.result()}
            except Exception as e:          # 单广告主失败不拖垮整批
                results[adv] = {'status': 'failed', 'error': str(e)}
    return results
```

### 7.2 Go 与 Python 的兼容层（跨语言复用）

团队常"Python 摆应用、Go 摆大吞吐"。报表拉取可在 Go 侧做高吞吐解析入库，Python 侧做业务编排。二者以统一的"列名→微单位金额"约定解耦：

```go
// 统一金额约定：外部一律微单位（1e6 = 1 货币单位）
func toMicro(s string) int64 {
	// 去掉 $ 逗号空格后转 int64(round(x*1e6))
	cleaned := strings.Map(func(r rune) rune {
		if r == '$' || r == ',' || r == ' ' || r == '\t' {
			return -1
		}
		return r
	}, s)
	f, err := strconv.ParseFloat(cleaned, 64)
	if err != nil {
		return 0
	}
	return int64(math.Round(f * 1_000_000))
}

// Schema 对齐：列名必须与 Python 端 glossary.yaml 一致
const ColImp = "Impressions"
const ColClick = "Clicks"
const ColSpend = "Spend"

func rowToStruct(r []string, header map[string]int) (DV360Line, error) {
	li := DV360Line{
		Impressions: atoi(r[header["Line Item ID"]]),
		Clicks:      atoi(r[header["Line Item ID"]]),
		SpendMicro:  toMicro(r[header["Spend"]]),
	}
	return li, nil
}
```

**跨语言对账一致性**：规定所有派生指标（CTR/CPM/ROAS/可见率）的公式只能在"口径词典"（glossary.yaml）定义一次，Go 与 Python 各自引用同一公式，避免两端算出不同结果。

### 7.3 常见维度 × 指标 合法组合速查（样例）

以下为高频合法组合参考（以 `dv360_list_breakdowns()` 实际返回为准，此处为示意）：

| 维度组合 | 典型指标集合 | 用途 |
|----------|--------------|------|
| DATE + LINE_ITEM | IMPRESSIONS, CLICKS, SPEND, VCR | 日常监控 |
| DATE + CREATIVE | IMPRESSIONS, CLICKS, CTR, COMPLETIONS | 素材优化 |
| COUNTRY + LINE_ITEM | IMPRESSIONS, SPEND, VIEWABLE | 地域投放 |
| DEVICE_TYPE + LINE_ITEM | IMPRESSIONS, CLICKS, VCR | 设备策略 |
| AUDIENCE_SEGMENT + LINE_ITEM | IMPRESSIONS, CONVERSIONS, ROAS | 受众效果 |
| PLACEMENT + SENSITIVE_CATEGORY | BRAND_SAFETY_IMPRESSIONS, IVT | 品牌安全 |
| SELLER + LINE_ITEM | IMPRESSIONS, SPEND, SPEND_VS_AVG_CPM | 库存结构 |

**注意**：高基数维度（CREATIVE、PLACEMENT 等）与部分维度互斥，正式使用前务必用 `dv360_list_breakdowns()` 在白名单里校验。

### 7.4 周 / 月聚合与趋势模式

日报之外的周报/月报用列表合并 + 环比/同比：

```python
def weekly_trend(rows, window='W'):
    """周粒度的花费/转化趋势；W=周，M=月。"""
    df = pd.DataFrame(rows)
    df['period'] = pd.to_datetime(df['report_date']).dt.to_period(window)
    return df.groupby(['period', 'advertiser_id']).agg(
        impressions=('impressions', 'sum'),
        spend_micro=('spend_micro', 'sum'),
        floodlight_conversions=('floodlight_conversions', 'sum'),
    ).reset_index()
```

**留存 / 触达分析提示**：跨渠道触达（Reach & Frequency）通常不在普通日报规模内跑，需结合 Google Ads Data Hub 或 CM360 的触达报表（对应 `dv360_list_cross_channel_reports`）。这类分析以聚合去重后的 UV/频率为主，与展示级指标口径不同，单独成看板，不与展示数混用。

### 7.5 术语表（避免团队对口径各说各话）

| 术语 | 含义 |
|------|------|
| LDB / 显示级 | 近实时展示级日志库，分钟级刷新、会回填修正 |
| RDB / 上报级 | 报表级定稿库，通常 24-48h 稳定，权威口径 |
| T-N 口径 | 数据日期落后当前 N 天（T-2 即昨日之前两天） |
| 维度（Dimension） | 数据切片键（日期/实体/设备/地域/受众） |
| 指标（Metric） | 每片上的计数与度量（展示/点击/花费/转化） |
| 事实键 | 一行报表的维度组合主键，用于幂等去重 |
| Floodlight | Google 统一转化计数体系（源自 CM360） |
| 计数方式 | SESSION / UNIQUE / TRANSACTION 三种转化去重粒度 |
| 归因分摊 | 一笔转化按模型把功劳分给多个触点 |
| IVT | Invalid Traffic，无效流量 |
| 可见率 | 可见展示 / 可测量展示（默认分母可测） |
| micro / 微单位 | 1e6 微单位 = 1 货币单位，避免浮点误差 |
| UPSERT | 存在即覆盖的写入（幂等，支持回填修正） |

### 7.6 速查：三源对账"权威基准"一页纸

| 数据 | 权威源 | 允许差异 | 备注 |
|------|--------|----------|------|
| 展示 | DV360 RDB | ±3% 内（IVT 扣减/回填时序） | 以买方结算基准 |
| 点击 | DV360 RDB | ±3% 内 | 注意点击去重 |
| 花费 | DV360 RDB | 结算以 invoice 为准 | 扣费 vs 返点口径 |
| 可见率 | 第三方门户 + DV360 双确认 | ±3~5 点 | 分母统一可测 |
| 转化/成交 | 内部支付/服务端埋点 | 以内部为准 | 归因天生不同 |
| 触达（UV/频次） | 跨渠道报表（CM360/ADH） | 独立口径 | 与展示级分离 |

这套"权威基准"定下来并写进团队共识，绝大多数"对不上账"吵的都是"你拿什么当基准"的问题，先对齐基准再谈差异。

## 八、附录补充：字段映射参考与对账数值示例

### 8.1 DV360 导出 CSV → 标准模型字段映射表

对接多套系统（BI/内部数仓/第三方）时，先固定"DV360 导出列名 → 标准字段名"的映射字典，避免各系统各写一套导致对不上。以下为常用映射（列名以实际导出为准，此处为典型值）：

| DV360 导出列（典型） | 标准字段 | 类型 | 用途 |
|----------------------|----------|------|------|
| Date | report_date | DATE | 数据日期 |
| Advertiser ID | advertiser_id | INT64 | 广告主 |
| Campaign | campaign_name | STRING | 展示层 |
| Campaign ID | campaign_id | INT64 | 汇总键 |
| Insertion Order | io_name | STRING | 展示层 |
| Insertion Order ID | insertion_order_id | INT64 | 对账键 |
| Line Item | line_item_name | STRING | 展示层 |
| Line Item ID | line_item_id | INT64 | 优化主键 |
| Creative | creative_name | STRING | 展示层 |
| Creative ID | creative_id | INT64 | 素材键 |
| Device | device_type | STRING | 设备切片 |
| Country | country | STRING | 地域切片 |
| Impressions | impressions | INT64 | 投递 |
| Clicks | clicks | INT64 | 投递 |
| Spend | spend_micro | INT64(微) | 花费 |
| Measurable Impressions | measurable_impressions | INT64 | 验证 |
| Viewable Impressions | viewable_impressions | INT64 | 验证 |
| Invalid Traffic Impressions | ivt_impressions | INT64 | 验证 |
| Floodlight Conversions | floodlight_conversions | INT64 | 转化 |
| Conversion Value | conversion_value_micro | INT64(微) | 转化 |

**映射实现（一处定义，多处引用）**：

```python
COLUMN_MAP = {
    'Date': 'report_date', 'Advertiser ID': 'advertiser_id',
    'Campaign ID': 'campaign_id', 'Insertion Order ID': 'insertion_order_id',
    'Line Item ID': 'line_item_id', 'Creative ID': 'creative_id',
    'Device': 'device_type', 'Country': 'country',
    'Impressions': 'impressions', 'Clicks': 'clicks', 'Spend': 'spend_micro',
    'Measurable Impressions': 'measurable_impressions',
    'Viewable Impressions': 'viewable_impressions',
    'Invalid Traffic Impressions': 'ivt_impressions',
    'Floodlight Conversions': 'floodlight_conversions',
    'Conversion Value': 'conversion_value_micro',
}
```

### 8.2 一个对账数值示例（把"为什么差"算清楚）

假设某 Campaign 于 2026-08-01~08-07 投放，四源数据如下（示例数值）：

| 数据源 | 展示 | 花费(USD) | 转化 | 可见率 |
|--------|------|-----------|------|--------|
| DV360 RDB 报表 | 1,000,000 | 5,000.00 | 1,200 | 62.0% |
| 第三方测量方门户 | 985,000（可测）| — | — | 58.5% |
| 内部服务端埋点 | — | — | 900 | — |

**差异解释逐项拆解**：

1. **展示 1000k vs 985k（差 -1.5%）**：
   - 975k 可测（MEASURABLE），拆分：985k*62%/?? 先给结论：
   - 实际差异 = IVT 扣减 + 测量方可测性。DV360 以投递日志计 1000k，第三方只测到 985k 可测（约 1.5% 不可测/采样），在 ±3% 可接受阈值内。
2. **可见率 62.0% vs 58.5%（差 3.5 点）**：
   - DV360 可见率 = 可见/可测；第三方门户另有一套标签计数与采样，差 3.5 点在 ±5 点容忍区间内，属正常。若分母不同（DV360 用可测，门户用总展示），数值差会更大，先对齐分母。
3. **转化 1200 vs 900（内部为准）**：
   - DV360 1200 = 归因分摊后的转化计数（含跨触点分摊 + 延迟转化 + SESSION/UNIQUE 计数口径）；内部 900 = 服务端唯一成交。转化以内部 900 为权威，DV360 1200 用于归因与优化，二者各司其职，不视为对账错误。

```python
def explain_example_diff():
    d = {'imp_dv360': 1_000_000, 'imp_3p_meas': 985_000,
         'view_dv360': 0.62, 'view_3p': 0.585,
         'conv_dv360': 1200, 'conv_internal': 900}
    imp_diff = (d['imp_3p_meas'] - d['imp_dv360']) / d['imp_dv360']
    return {
        'impression_diff_pct': round(imp_diff, 4),       # -0.015
        'viewability_gap_pts': round((d['view_dv360']-d['view_3p'])*100, 1),  # 3.5
        'conv_explained': "归因分摊+延迟转化+计数口径 → 以内部900为权威",
        'conclusion': "四源差异均在可接受阈值内且有解释，非数据错误",
    }
```

**结论**：对账不是"四个数相等"，而是"每个差值都有可控且有解释的原因，且建立了权威基准"。把这一页纸讲清楚，能省掉 80% 的"是不是 bug"争论。

### 8.3 收尾清单（上线前逐项勾选）

```
□ LDB/RDB 口径已统一（入库用 RDB final + T-2）
□ 时区与日期边界已对齐（账户时区 / dv360_list_time_zones）
□ 金额走微单位整数（_micro）
□ 事实键主键 + UPSERT 幂等写入
□ Query 复用 + 重复 run 防呆
□ 维度组合已过 breakdowns 白名单校验
□ 三源对账权威基准已定义 + 阈值告警
□ 配额监控（dv360_get_quota）已接入
□ 口径词典（glossary.yaml）已建立并被看板引用
□ 回填修正双版本（预览→定稿）已实现
□ 行数上限已按日拆分规避
□ 失败告警（钉钉/Slack/邮件）已接入
```

---

**附：写作说明** 本文档面向"Rachel/DV360 报表工程化"场景，所有 API 方法名均已对照 `ryan-personal-knowledge/scripts` 下 `ad_platform_api.py`（`dv360_*` 系列）与 `dv360_api.py`（`get_report` / `get_*_options` 系列）核验；业务场景、踩坑与排查经验为一线投放/工程实践沉淀。文档与 `dv360-architecture-deep.md`、`dv360-measurement-attribution-deep.md`、`dv360-optimization-deep.md` 互补，读者可交叉阅读构建完整能力。
