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
