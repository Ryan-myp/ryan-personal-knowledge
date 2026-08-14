# 程序化保量采购详解（Day 5）

> **领域**: 广告投放 / 程序化保量
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, programmatic-guaranteed, pg, guaranteed, direct
> **更新时间**: 2026-08-14
> **类型**: 学习笔记

---

## 📌 今日学习重点

今天系统学习 DV360 的程序化保量（Programmatic Guaranteed，简称 PG）采购，覆盖从概念、交易架构、proposal 协商流程、保量算法、SDC 自动对接，到生产环境的直采谈判、库存锁定、保量监测与踩坑复盘。目标是读完本文后，能独立完成一条 PG 交易从「和商家谈价」到「创建 PD/LI 落地投放」再到「监测达标追责」的完整闭环。

本文与现有文档互补：

- `dv360-architecture-deep.md` 侧重 DV360 全平台架构与交易类型总览；
- `dv360-dfp-deep.md` 侧重 DV360 与 GAM 的 SDC / 保量 LI vs RTB 服务端逻辑；
- 本文则聚焦「PG 交易本身的商务与采买落地」，从 proposal 出发，层层拆到 Line Item。

---

## 一、核心概念与架构

### 1.1 什么是程序化保量（PG）？

**程序化保量（Programmatic Guaranteed，PG）** 是 DV360 的一种「直接采买」方式（Guaranteed Buying / Direct Deal），买方（广告主/DSP）与卖方（发布商/SSP/GAM）以**合同形式**约定：在指定库存、指定时间窗口内，**保证交付一定数量的展示量**，并按**谈定的固定价格（CPM）**结算，全程通过程序化接口自动执行，无需人工发送 IO 表格。

一句话：**PG = 程序化的广告位包断，既有直采的确定性（保量、固定价、锁定库存），又有程序化的效率（自动对接、自动匹配创意、自动结算）。**

```
PG 的本质方程：

  保证量（Guaranteed Impressions）
  = 库存（锁定 Inventory）× 时间窗（Flight）× 频控（Frequency）
  计价 = 固定 CPM × 展示量
  结算 = 程序化自动（无需人工对账每张 IO 表）
```

### 1.2 PG 的核心价值

| 价值维度 | 说明 | 适合谁 |
|---------|------|--------|
| **确定性** | 合同保量，承诺展示必达，投放可预期 | 品牌大曝光客户、上市/大促节点 |
| **固定价格** | 提前谈定 CPM，预算可精确规划 | 预算严格的品牌 |
| **锁定库存** | 锁定指定优质库存（首页首屏、特定媒体） | 追求位置与品牌安全的客户 |
| **程序化自动** | 自动对接 GAM、自动派发创意、自动结算 | 减少人工 IO 对账成本的运营 |
| **可监测** | 全程 API/报表可追踪达标率，可追责 | 投放负责人、媒体购买经理 |

### 1.3 PG vs PMP vs 公开竞价（核心对比表）

这是每次汇报都逃不开的一张表，务必背熟：

| 维度 | **PG（程序化保量）** | **PMP（私有市场）** | **公开竞价（Open Auction）** |
|------|---------------------|--------------------|----------------------------|
| 交易方式 | 直接 contract（保量） | 邀请制竞价（非保量） | 开放竞价（非保量） |
| 价格 | **固定 CPM（谈定）** | 底价 + 竞价（可能浮动） | 市场竞价（动态） |
| 展示量 | **合同保证** | 不保证（尽力） | 不保证 |
| 库存 | **锁定指定库存** | 优质但不锁定 | 参差不齐 |
| 结算 | 按展示量固定计费 | 按竞价成交 | 按竞价成交 |
| 适用场景 | 品牌大曝光、必达量 | 优质库存可控采买 | 长尾放量、效果试投 |
| 确定性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 采购成本 | 偏高（溢价买确定性） | 中 | 低 |
| 自动化程度 | 高（SDC 自动对接） | 中 | 高（RTB 全自动） |
| API 侧交易类型 | `PROGRAMMATIC_GUARANTEED` | `PRIVATE_MARKETPLACE` | `OPEN_AUCTION` |

> 补充：三者之外还有 **Preferred Deal（优先交易）**——授予优先购买权但不保量，API 类型为 `PREFERRED_DEAL`。它的定价通常是固定 CPM，可以先于竞价被选择，但不承诺展示。

### 1.4 交易各方角色与权限边界

PG 是一笔「双边 + 平台」的多方协作，先弄清谁说话算数：

```
┌──────────────────────────────────────────────────────────────┐
│                      程序化保量交易全景图                          │
│                                                                │
│  ┌─────────────┐     Negotiation(谈价)     ┌──────────────┐   │
│  │   买方买方    │  ◄───────────────────────► │    卖方卖方    │   │
│  │  (品牌广告主)  │   固定 CPM / 保量 / 库存    │  (发布商/媒体)  │   │
│  └──────┬──────┘                            └──────┬───────┘   │
│         │  采购需求                               ▲ │ 销售库存     │
│         ▼                                        │ ▼            │
│  ┌─────────────┐    提案/协商     ┌─────────────┐ │            │
│  │  DV360 买方   │ ◄────────────► │  GAM 卖方     │◄┘ 管理 Order/LI│
│  │ (DSP/Demand) │   Proposal 提议   │ (SSP/Supply) │              │
│  └──────┬──────┘                 └──────┬──────┘              │
│         │                               │                        │
│         │   SDC 自动对接 / 手动绑定 Deal    │                        │
│         └───────────────┬───────────────┘                        │
│                         ▼                                        │
│              ┌──────────────────────┐                           │
│              │  Ad Exchange (AdX)   │ 托管流量与结算               │
│              └──────────────────────┘                           │
└──────────────────────────────────────────────────────────────────┘
```

**各方职责：**

| 角色 | 实体 | 职责 |
|------|------|------|
| **需求方** | 品牌广告主 / 代理商 | 明确保量目标、预算、受众、频控；拍板价格 |
| **买方平台** | DV360（本笔记主角） | 创建 proposal、协商、创建 IO/LI、绑定 deal、派发创意、报表监测 |
| **卖方平台** | GAM（Google Ad Manager） | 创建 order/LI、报价、接提案、保量扣减与投放 |
| **托管交易** | Ad Exchange | 承接 PG 流量、数据结算、统一拍卖优先级 |
| **生态对接** | SDC（Supply-Domain Connection） | DV360 与 GAM 之间自动化建单/绑定库存 |

### 1.5 PG 在 DV360 数据模型里的位置

PG 不是独立对象，而是贯穿「方案 → IO → Line Item → Flight → Creative」的整套层级中的一个交易类型：

```
广告主 Advertiser
 └─ 方案 Proposal（PG 协商的最上层实体）
     ├─ 卖方 Seller / 媒体
     ├─ 条款 Terms（CPM、保量、Flight、频控、库存）
     └─ 通过协商后 → 生成
 └─ 插入订单 Insertion Order（IO，type = PROGRAMMATIC_GUARANTEED）
     ├─ 预算 Budget、排期
     └─ 一个或多个
 └─ Line Item（type = PROGRAMMATIC_GUARANTEED）
     ├─ 绑定 Deal ID（来自 GAM 的 proposal/deal）
     ├─ 定向、创意关联
     └─ 一个或多个
 └─ Flight（投放周期，定义 start/end 与目标量）
     └─ 创意 Creative（横幅/视频/原生）
```

> 关键点：PG 的「保量」本质体现在 **Deal** 上。DV360 的 Line Item 通过绑定一个「Guaranteed Deal」获得保量承诺。这个 Deal 要么由 DV360 通过 SDC 在 GAM 侧自动创建，要么由 GAM 销售手动创建后提供给 DV360 绑定。

---


## 二、深度原理解析

### 2.1 PG Proposal 生命周期：创建 → 协商 → 接受

PG 交易的落地绕不开 **Proposal（方案）**。Proposal 是 DV360 与 GAM 之间协商一笔交易的载体，承载了价格、保量、库存、排期等全部商业条款。完整生命周期如下：

```
                         PG Proposal 生命周期
┌───────────────────────────────────────────────────────────────────┐
│ 1. 发起方创建 Proposal                                              │
│    卖方(GAM) 或 买方(DV360) 都可发起，填写：                        │
│      - 卖方 Seller / 指定媒体                                        │
│      - 交易类型 = PROGRAMMATIC_GUARANTEED                          │
│      - 保量 Impressions / 固定 CPM / 排期 Flight / 频控 / 库存        │
│            │                                                        │
│            ▼                                                        │
│ 2. 协商 Negotiation（来回修改条款，可多次迭代）                       │
│    DRAFT ──修改──► DRAFT ──修改──► ...（价格/保量拉锯）               │
│            │                                                        │
│            ▼                                                        │
│ 3. 一方提交（送审） Send for Approval                               │
│    DRAFT → PENDING_REVIEW（对方 + Google 审核条款合规性）            │
│            │                                                        │
│            ▼                                                        │
│ 4. 对方接受 Accept  /  打回 Reject                                   │
│    PENDING_REVIEW → ACCEPTED（正式成交，进入生效流程）                │
│                       → REJECTED（重新协商或终止）                   │
│            │                                                        │
│            ▼                                                        │
│ 5. 生成 Deal 并自动推送                                             │
│    ACCEPTED → 生成 Guaranteed Deal → SDC 同步到 GAM/DV360           │
│            │                                                        │
│            ▼                                                        │
│ 6. 创建 IO + LI 绑定 Deal → 派发创意 → 开始投放                     │
└───────────────────────────────────────────────────────────────────┘
```

**状态机核心（务必掌握）：**

| 状态 | 含义 | 谁可操作 | 能否修改条款 |
|------|------|---------|------------|
| `DRAFT` | 草稿，未提交 | 发起方 | ✅ 可改 |
| `PENDING_REVIEW` | 已提交待对方/Google 审核 | 对方 | ❌ 需退回 |
| `ACCEPTED` | 对方接受，条款生效 | 双方 | ❌ 需新提案 |
| `REJECTED` | 被驳回/过期 | 发起方 | ✅ 改后重提 |
| `CANCELED` | 主动取消 | 双方 | ❌ |

### 2.2 固定价格与保量算法（保证展示 vs 竞价）

PG 最核心的两个机制：**固定价格** 与 **保量（保证展示）**。

#### 2.2.1 固定价格（Fixed CPM）

PG 不参与拍卖竞价，而是以谈定的固定 CPM 结算。因此在 DV360 侧配置 Line Item 时，**出价模式是「固定 CPM」而非「自动出价」**，且不设置竞价上限竞争（因为没有竞争，价格就是谈定的值）。

```
PG 计价 = 固定 CPM × 实际/承诺展示量

例：CPM = $30，保量 1,000,000 次展示
    预算上限 = $30 × 1000 = $30,000（若按承诺量）
实际结算按「实际投放展示量 × CPM」，通常接近承诺量（100%）或超量（>100%）。
```

#### 2.2.2 保量（Guaranteed Impressions）

保量是「卖方对买方的承诺」，但不是「机器强行塞量」——它依赖 GAM 侧 Giveback 与 DV360 侧投放节奏的配合：

```
保量实现的双侧协作：

[ DV360 买方侧 ]
  - Line Item type = PROGRAMMATIC_GUARANTEED
  - 目标量 = guaranteed_impressions（承诺展示）
  - 按 Flight 平均分配每日目标（Pacing）
  - 每日尽量消耗目标量，避免前松后紧

[ GAM 卖方侧 ]
  - Order/LI 标记为 Guaranteed（保量）
  - 流量分配时「保量 LI 优先于竞价」
  - 承诺展示未达到时进入 Giveback/补量逻辑
```

**保证展示 vs 竞价的数据流对比：**

```
                   公开竞价（RTB）                          PG（保证展示）
  请求到达 AdX ──► 拍卖（bidder 竞价）         请求到达 AdX ──► 检查保量 LI
                              │                                   │
                 最高出价获胜 ──┴── 展示          命中保量 LI 且配额足够 ──┴── 展示（固定价）
                 不保证展示量                        保证：配额不足时才走竞价
```

**关键差异：**

| 方面 | RTB/竞价 | PG/保证展示 |
|------|---------|------------|
| 定价 | 出价（动态） | 固定 CPM |
| 竞争 | 拍卖（可输） | 无竞争（保量优先） |
| 展示保证 | 无 | 有（承诺量） |
| 输单风险 | 高（赢不到量） | 低（保量配额） |
| 流量优先级 | 低 | 高（GAM 优先给保量） |
| 溢量处理 | 无法控制 | 可设 cap/允许 overdelivery |
| 计费模型 | 第二价格/自定义 | 固定 CPM |

#### 2.2.3 保量 Pacing 与欠量/溢量

- **均匀 Pacing（Even Pacing）**：把承诺量按投放周期均匀分配到每一天，如 30 天 300 万展示 → 每天约 10 万。PG 默认偏向均匀，避免前热后凉导致的"钱花不完 / 量不够"。
- **前加载（Front-load）**：大促/首发选择在窗口早期多投，如 60% 分配在前半段。
- **Underdelivery（欠量）**：到结束仍未投满承诺量。处理见 3.4 节。
- **Overdelivery（溢量）**：投放超过承诺量。GAM 侧会尝试把溢量转给竞价；DV360 侧可配置是否允许 overdelivery 及上限，避免超预算。

### 2.3 Deal 绑定库存：锁定「指定媒体/位置」

PG 的「锁库存」本质是 **Deal 与库存的绑定**。一个 Guaranteed Deal 会在条款里限定：

```
Deal 绑定库存的三个维度：
  1. 媒体/App（Domain / App）        → 锁定指定站点或应用
  2. 位置/广告单元（Placement）      → 可锁首页首屏、特定广告位
  3. 受众/定向（Targeting）          → 锁定人群（与 politics 无涉时用）

示例：北京商报财经频道 - 首屏横幅 1000x300 - 25-44 岁
```

**绑定方式：**

| 方式 | 说明 | 适用 |
|------|------|------|
| **SDC 自动绑定** | DV360 通过 SDC 在 GAM 建单时自动把 Deal 关联到库存 | 首选，正规媒体 |
| **手动绑定 Deal ID** | GAM 销售给到 Deal ID，DV360 手动输入到 LI | GAM 手动 deal、中小媒体 |
| **域级（Domain）锁定** | 只对指定域名/App 生效 | 单媒体独家采买 |

> ⚠️ 绑定失败最常见原因：`deal.inventory_source` / 定向范围与 GAM 方设置的 deal 定向不一致，或媒体未启用该广告位可投（详见第四节 4.3）。

### 2.4 SDC（Supply-Domain Connection）自动对接

SDC 是 DV360 与 GAM 之间的「自动建单 + 自动绑定库存」通道，是 PG 流程自动化的基石（与 `dv360-dfp-deep.md` 中服务端逻辑互补，此处侧重采买侧视角）。

```
SDC 自动对接流程：

DV360 侧                          SDC 通道                     GAM 侧
┌──────────┐   创建 SDC 订单    ┌──────────┐   自动创建   ┌──────────────┐
│ 创建 IO    │ ───────────────► │  SDC     │ ──────────► │ Order [SDC] X │
│ type=PG   │                  │  校验域名  │             │ LI Guaranteed │
│ 指定媒体   │                  │  配置库存  │             │ Deal 生成并回写│
└──────────┘                  └──────────┘             └──────────────┘
        ▲                                                   │ Deal ID
        └────────── DV360 拿到 Guaranteed Deal ─────────────┤
```

**SDC 前置条件：**

1. 商家（卖方）已启用 GAM **SDC 功能**；
2. DV360 与 GAM 已建立 **Partner 级关联**（partner link）；
3. 媒体域名/App 已在 GAM **合法添加并通过验证**；
4. 双方账户具备 SDC 权限与操作审计权限。

**SDC 的优势：**

| 优势 | 说明 |
|------|------|
| 零手工建单 | IO/LI 自动在 GAM 生成对应 Order/LI |
| Deal 自动回写 | DV360 直接拿到 Guaranteed Deal ID，无需人工搬运 |
| 库存自动绑定 | 域名/广告位自动关联 |
| 减少人为错误 | 避免手动填错 IO 表导致的库存绑定失败 |

### 2.5 Native / 横幅 / 视频 PG 各自要点

PG 的保量机制相同，但不同创意格式在 DV360 侧有不同配置差异：

| 格式 | 关键配置 | 特有注意 |
|------|---------|---------|
| **横幅（Banner）** | 尺寸（300x250/728x90 等）、静态/HTML5 素材 | 注意富媒体（Rich Media）需模板支持；GP 投放前需验证素材尺寸与广告位匹配 |
| **原生（Native）** | 标题、描述、图（图标+大图）、CTA | 原生素材需符合 App/Web 原生模板；标题长度有上限，超长会被截断影响 CTR |
| **视频（Video）** | 时长、格式（MP4/VAST）、前贴/中贴 | 视频需接 VAST/第三方验证（DV/Moat）；保量结合 `VIDEO_PREROLL_AD`/`VIDEO_MIDROLL_AD`；注意 skip 与 viewability |

**跨格式通用项：** 无论哪种格式，PG 都要求该创意**未过审不可量投**（详见踩坑 3.5.3），因此上线前务必先审批创意。

### 2.6 Python 创建/接受 PG Proposal 与 Line Item 代码示例

结合项目脚本（`dv360_api.py` 与 `ad_platform_api.py`），给出可直接落地的示例。脚本中的相关方法：

| 方法 | 来源脚本 | 作用 |
|------|---------|------|
| `get_transaction_type_options()` | `dv360_api.py` | 返回交易类型（含 `PROGRAMMATIC_GUARANTEED`） |
| `list_insertion_orders()` / `create_insertion_order()` | `dv360_api.py` | 列出/创建 IO |
| `create_line_item(advertiser_id, io_id, line_item)` | `dv360_api.py` | 在 IO 下创建 LI（含 `type`） |
| `request(method, endpoint)` | `dv360_api.py` | 底层请求封装（proposal 走 REST） |
| `dv360_list_proposals()` | `ad_platform_api.py` | 列出提案 |
| `dv360_accept_proposal(proposal_id)` | `ad_platform_api.py` | 接受提案 |
| `dv360_reject_proposal(proposal_id)` | `ad_platform_api.py` | 拒绝提案 |
| `dv360_create_line_item(type=PROGRAMMATIC_GUARANTEED)` | `ad_platform_api.py` | 创建保量 LI |
| `dv360_list_flights` / `dv360_list_sellers` / `dv360_estimate_reach` | `ad_platform_api.py` | 排期/卖方/预估 |

**示例 1：确认交易类型选项（拿 PG 的 code）**

```python
from dv360_api import DV360Client

client = DV360Client(credentials)
options = client.get_transaction_type_options()

for opt in options:
    print(opt)
# [{'code': 'PROGRAMMATIC_GUARANTEED', 'name': '程序化保量', ...},
#  {'code': 'PRIVATE_MARKETPLACE', ...},
#  {'code': 'PREFERRED_DEAL', ...},
#  {'code': 'OPEN_AUCTION', ...}]
```

**示例 2：拉取未接受提案并接受（协商后的动作）**

```python
from ad_platform_api import AdPlatformAPI

api = AdPlatformAPI(credentials)

# 1. 列出当前所有提案
proposals = api.dv360_list_proposals(advertiser_id='123456')
for p in proposals:
    print(p['proposalId'], p['name'], p.get('status'))

# 2. 手动挑出待接受的一条（trusted partner 已达成的 PG）
target_id = 'proposal_98765'   # 例如从列表里筛出已完成谈判的 proposal
confirm = input(f"确认接受提案 {target_id}？[y/n] ")
if confirm.lower() == 'y':
    api.dv360_accept_proposal(proposal_id=target_id)
    print(f"提案 {target_id} 已接受，开始生成 Deal")
else:
    api.dv360_reject_proposal(proposal_id=target_id)
    print("已拒绝，回到协商")
```

**示例 3：创建 PG 类型 Line Item（绑定保量）**

```python
from ad_platform_api import AdPlatformAPI

api = AdPlatformAPI(credentials)
advertiser_id = '123456'

# 交易类型设为 PG（保量）
line_item = api.dv360_create_line_item(
    advertiser_id=advertiser_id,
    name='Brand_Launch_PG_HKTop',
    type='PROGRAMMATIC_GUARANTEED',
    deal_id='deal_8888',              # 已接受的 Guaranteed Deal
    flight={
        'start_time_micros': 1756684800000000,   # 2026-09-01
        'end_time_micros':   1761955200000000,   # 2026-11-01
    },
    # 保量目标与固定价
    guaranteed_impressions=1_000_000,
    fixed_cpm_micros=30000000,         # $30 CPM
    status='DRAFT',
)
print(line_item)
```

**示例 4：用底层 REST 直接操作 Proposal（`DV360Client.request`）**

```python
from dv360_api import DV360Client
client = DV360Client(credentials)

# 新建一条 PG proposal（seller 发起权由 GAM 决定，此处示意）
proposal = {
    'name': 'PG Demo - Q4',
    'advertiserId': '123456',
    'seller': {'sellerId': 'SELLER_X'},
    'programmaticGuaranteed': {
        'targetedAdvertiserId': '123456',
        'targetedNetworkId': 'NET_Y',
        'cpm': {'amountMicros': 30000000, 'currencyCode': 'USD'},
        'impressions': 1000000,
        'flightDuration': {
            'startTimeMicros': 1756684800000000,
            'endTimeMicros':   1761955200000000,
        },
    },
}
resp = client.request('POST', f'advertisers/123456/proposals', data=proposal)
print(resp.data)
```

**示例 5：排期与卖方前置调研（投产前必做）**

```python
from ad_platform_api import AdPlatformAPI
api = AdPlatformAPI(credentials)

# 查有哪些卖家（媒体）可做 PG
sellers = api.dv360_list_sellers()
print([s['sellerId'] for s in sellers][:10])

# 查目标 LI 的 flight 是否已生成（保量都要落到 flight）
flights = api.dv360_list_flights(advertiser_id='123456', line_item_id='li_7788')
for f in flights:
    print(f['name'], f.get('status'))

# 评估定向触达，判断保量目标是否现实
est = api.dv360_estimate_reach(
    advertiser_id='123456',
    targeting_id='target_aud_50',      # 25-44 + 财经兴趣
)
print("预估触达:", est.get('reach'))
```

> 💡 先 `dv360_list_sellers()` + `dv360_estimate_reach()` 确认：
> 1. 目标媒体是否在 seller 列表（是否有 PG 资质）；
> 2. 定向人群触达是否足够支撑保量目标（触达不够 → 保量必欠，早谈判）。

---


## 三、生产环境实战

### 3.1 直采大曝光品牌客户 PG 案例（完整闭环）

**背景：** 某品牌客户（运动服饰）Q4 新品首发，要求"必达"量：头部财经/体育媒体首屏横幅曝光 200 万次，CPM 预算上限 $28，投放期 2026-09-01 至 2026-10-31。

**完整流程（照着走）：**

```
Step 0  前置调研
  ├─ dv360_list_sellers() 确认目标媒体可做 PG
  ├─ dv360_estimate_reach() 确认人群触达 ≥ 保量目标
  └─ 确认 SDC 通道可用（否则走手动 Deal ID）
Step 1  商务谈判（见 3.2）
  ├─ 商家报价 → 谈价 → 谈定 CPM=$26、保量 200 万
  └─ 锁定库存（首屏横幅、频控 1 次/用户/天）
Step 2  Proposal 落地
  ├─ GAM/DV360 创建 proposal（type=PROGRAMMATIC_GUARANTEED）
  ├─ 提交送审 → 双方确认条款 → ACCEPTED
  └─ SDC 自动生成 Guaranteed Deal
Step 3  创建 IO + LI
  ├─ create_insertion_order()（type=PG）
  ├─ create_line_item(type=PROGRAMMATIC_GUARANTEED,
  │                   deal_id, guaranteed_impressions=2M,
  │                   fixed_cpm=$26)
  └─ dv360_list_flights() 核对 flight 已生成
Step 4  创意审批（先批后投！）
  ├─ 上传横幅创意 → 等审批通过
  └─ 未过审的创意量投 = 保量必欠（见踩坑 3.5.3）
Step 5  投放与监测
  ├─ 每日看报表：展示/CPM/达标率
  ├─ 前 3 天未达标 → 查 pacing/库存/创意审批（见 3.4）
  └─ 结束前 7 天做「补量/追责」预案
Step 6  结案
  ├─ 对账：实际展示 vs 承诺 200 万
  ├─ 达标 → 结案报告；欠量 → 追责 + 补偿方案
  └─ 沉淀复盘（价格、库存、流程耗时）
```

**关键数字（示例结算）：**

| 项目 | 值 |
|------|-----|
| 承诺保量 | 2,000,000 次展示 |
| 谈定 CPM | $26.00 |
| 预算上限 | $52,000（2,000 × $26） |
| 实际展示 | 2,012,000（100.6%） |
| 实际成本 | ≈ $52,312（超 0.6% 在容差内） |
| 达标率 | 100.6% ✅ |

### 3.2 商家谈价与库存锁定（谈判桌上的实操）

谈 PG 价格，本质是「确定性溢价」的博弈。以下是真实谈判中的关键抓手：

#### 3.2.1 价格锚点：先给"市场价区间"，再谈"打包价"

```
谈价公式（买方视角）：
  可接受 CPM = 历史成交 CPM × 量级折扣 × 库存溢价系数

  例：目标媒体公开竞价历史 CPM = $12
      PG 确定性溢价系数 ≈ 1.8~2.5（媒体强势时更高）
      保量 200 万量级折扣 ≈ 0.9
      → 可接受 CPM ≈ $12 × 2.2 × 0.9 ≈ $23.8
```

**谈判要点：**

| 抓手 | 话术/做法 | 效果 |
|------|----------|------|
| 量大 | "200 万起量，按量给阶梯价" | 压单价 |
| 排期灵活 | 错峰（避开大促旺季）给折扣 | 换价 |
| 长单锁价 | 签年框/多季，锁固定 CPM | 防涨价 |
| 素材现成 | 已有过审素材，立即可投 | 减少对方交付成本 |
| 数据背书 | 引用历史 CTR/填充率证明值这个价 | 防止被抬价 |
| 竞品报价 | 透明给另一媒体报价单 | 制造竞争 |

#### 3.2.2 库存锁定：把"口头答应"变成"deal 定向"

```
锁定清单（谈完立刻写进 proposal）：
  □ 媒体（域名/App）固定（写死，不允许替换）
  □ 广告位（首页首屏/栏目内页）固定
  □ 尺寸（如 1000x300 / 300x250）
  □ 频控（1 次/用户/天 或 3 次/用户/周期）
  □ 时段（全时段 / 仅 8-24 点）
  □ 受众（如 25-44 财经兴趣）
  □ 是否允许 overdelivery 及上限（默认 +10% 内）
```

**锁定方式对比：**

| 方式 | 可靠性 | 代价 | 何时用 |
|------|--------|------|--------|
| SDC 自动绑定 | ⭐⭐⭐⭐⭐ | 需双方配 SDC | 正规媒体、长期合作 |
| 手动 Deal ID | ⭐⭐⭐⭐ | 易填错、依赖人工 | GAM 手动 deal |
| 仅域名锁定 | ⭐⭐⭐ | 无法锁具体广告位 | 保量要求不苛刻 |

> ⚠️ 谈判红线：**"保量"不等于"保证位置"**。如果对方只承诺"全站保量"而不锁首屏，要在合同里写明位置权重（如首屏 ≥ 50%），否则媒体会用长尾流量凑量，CTR 和品牌安全双双难看。

#### 3.2.3 谈崩了怎么办（价格谈崩的 4 个退路）

1. **降量不降价**：保量从 200 万降到 100 万，CPM 不变或略降；
2. **换库存**：首屏换二屏，或换同集团次级媒体；
3. **转 PMP**：价格谈不拢但库存认可 → 转非保量 PMP，用竞价拿量；
4. **换周期**：从旺季挪到淡季，用时间换价格。

### 3.3 保量监测：是否达标 + Underdelivery 处理

#### 3.3.1 达标率监控表（每日看）

```
达标率 = 已投展示 / (承诺展示 × 已过天数占比)

示例（承诺 200 万 / 61 天）：
  第 10 天应达 ≈ 200 万 × (10/61) ≈ 32.8 万
  若实际仅 25 万 → 达标率 76% → 触发预警（见下）
```

**监控节奏：**

| 节点 | 动作 |
|------|------|
| 每日 10:00 | 拉昨日报表，算达标率，记录趋势 |
| 前 3 天 | 重点看「起量是否正常」（启动慢是常态，但 3 天仍低于 50% 必查） |
| 每周五 | 汇总周达标率，与商家同步风险 |
| 最后 10 天 | 启动补量预案：协商后段加量 / 延长期限 / 补偿 |
| 结束后 3 天 | 最终对账、出结案报告 |

**达标率分级：**

| 区间 | 判定 | 动作 |
|------|------|------|
| ≥ 98% | ✅ 达标 | 正常结案 |
| 90%~98% | 🟡 微欠 | 记录原因，谈补偿或忽略（容差内） |
| 70%~90% | 🟠 明显欠量 | 立即找商家补量/延期限，启动追责 |
| < 70% | 🔴 严重欠量 | 升级处理：停投止损、商务追责、保留证据 |

#### 3.3.2 Underdelivery（欠量）处理 SOP

```
发现欠量 ──► 判断原因（四查）：
  1. 查创意：是否过审？是否因审核被打回导致 0 展示
  2. 查库存：媒体是否给了足够流量？（Ask 对方给库存报告）
  3. 查定向：是否收太窄？（频控太严/受众太小）
  4. 查排期：是否前松后紧？（pacing 不均）

根据原因处理：
  ├─ 创意问题 → 修素材 → 补审 → 加速起量
  ├─ 库存问题 → 找商家 → 要求补量 / 换库存 / 顺延
  ├─ 定向问题 → 放宽频控/受众（需客户同意）
  └─ 排期问题 → 后段加预算节奏 / 延长 flight

最后 7 天仍未达标 → 商务追责：
  ├─ 要求补量（延长 7~14 天补足承诺量）
  ├─ 要求按实际量打折结算
  └─ 影响下次合作（记入媒体评分）
```

#### 3.3.3 Overdelivery（溢量）控制

- 默认建议设置 **+10% 溢量上限**，防止超预算；
- 品牌客户若预算刚性，直接**禁止溢量**（cap = 100%）；
- 溢量发生时 GAM 会优先转给竞价流量，但 DV360 侧也要核对账单，防止按溢量多收。

### 3.4 保量监测的 API 自动化（用脚本做日报）

```python
# 每日达标率日报（示意）
from ad_platform_api import AdPlatformAPI

api = AdPlatformAPI(credentials)
advertiser_id = '123456'

report = api.dv360_get_report(
    advertiser_id=advertiser_id,
    dimensions=['LINE_ITEM'],
    metrics=['IMPRESSIONS', 'SPEND'],
    date_range={'start': '2026-09-01', 'end': '2026-09-10'},
)

for row in report.get('rows', []):
    impressions = row['metrics']['IMPRESSIONS']
    target_today = 2_000_000 * (10 / 61)   # 承诺量按天折算
    rate = impressions / target_today * 100
    print(f"{row['dimensions']['LINE_ITEM']}: {impressions:,} "
          f"达标率 {rate:.1f}%")
    if rate < 80:
        print("  ⚠️ 触发预警：立即排查")
```

### 3.5 踩坑记录（真实经验，句句带血）

#### 3.5.1 坑一：Proposal 卡在审核，错过投放窗口

**现象：** 提前 2 周创建 proposal，临上线发现状态仍是 `PENDING_REVIEW`，无人处理。

**根因：** PG proposal 提交后需要对方（或 Google 侧）审核，但业务上没人盯状态流转；协商期间的条款修改不会自动触发重新审核，谁改了条款、谁该点提交没人负责。

**教训与对策：**

```
✅ 对策清单：
  □ 明确 proposal owner：发起方提交后，设日历提醒对方 48h 内审核
  □ 用脚本轮询状态（dv360_list_proposals + status 过滤），变更即告警
  □ 把「proposal ACCEPTED」设为上线前提的硬闸门（未接受不允许建 LI）
  □ 留足 5~7 个工作日 buffer（谈判来回 2~3 轮是常态）
```

#### 3.5.2 坑二：库存不足，保量目标根本喂不满

**现象：** 谈定 200 万保量，媒体实际日均可供流量只有 1.5 万/天，61 天最多 91 万，**结构性欠量 45%**。

**根因：** 谈判时只谈价格没核实库存供给；媒体夸大库存或把竞价流量也算了进去。

**预防（谈判期必做）：**

```
□ 索要媒体「库存报告」：分广告位的日均填充可用量
□ 用 dv360_estimate_reach() 校验：定向受众触达 ≥ 保量 × 2（频控余量）
□ 合同中写明：若媒体库存不足以交付承诺量，责任在卖方
□ 大保量分多媒体组合，单媒体保量 ≤ 其历史最高供给的 80%
```

#### 3.5.3 坑三：创意未过审就量投，保量直接归零

**现象：** LI 状态 ACTIVE，但展示为 0；查发现创意 `PENDING` 审批未通过，保量 deal 不派发未过审创意。

**根因：** 流程上「先建 LI 后传创意」，且没做审批前置检查；PG 对创意审批尤其严格（品牌安全 + 合规）。

**对策：**

```
✅ 流程改造：
  1. 创意先上传审批（dv360_get_creative_approval 轮询）
  2. APPROVED 后才允许把创意关联到 PG LI
  3. 上线前 checklist：创意审批 = 硬性 Gate
  4. 预留审批时间：图片 1~2 天，视频 2~5 天（大促前更久）
```

#### 3.5.4 坑四：价格谈崩后硬上，CPM 高于客户预算

**现象：** 客户预算 CPM ≤ $25，媒体死守 $30；为赶上线直接按 $30 建单，结果超预算 20%，客户拒付差价。

**教训：**

```
□ 谈不拢绝不硬上：价格红线在 proposal 创建前就必须和客户对齐
□ 用 3.2.3 的退路降级（降量/换位/转 PMP/换周期）
□ 任何改价都要留书面确认（邮件/IM 记录）
□ 建单前 double check：fixed_cpm_micros × 承诺量 ≤ 客户预算
```

#### 3.5.5 坑五：保量未达标后的「追责无证据」

**现象：** 结束欠量 15%，商家不认账，因为没有投放期间的达标率留痕。

**对策：**

```
✅ 证据链建设：
  □ 每日自动拉报表存档（CSV/数据库）
  □ 每周发商家「达标率周报」，要求对方确认
  □ 欠量预警邮件带时间戳，作为商务追责依据
  □ 合同里写明：欠量补偿条款（延长/折扣/赔偿）
```

#### 3.5.6 坑六：把 PG 当 RTB 用，定向收得太死

**现象：** 保量 200 万但定向收成「25-44 岁 + 财经兴趣 + 首屏 + 频控 1 次」，实际供给撑不起，前期看似达标后期断崖。

**对策：** PG 定向宜宽不宜窄——保量是"卖方凑量"，定向越窄卖方越难交付。核心人群定向 + 少量排除即可，精细定向交给 RTB/PMP。

#### 3.5.7 坑七：代发（Agency 代采）场景下，Deal 绑错账号

**现象：** 代理商代发时，把 A 客户谈的 deal 绑到了 B 客户（同 Partner 下的不同 Advertiser）的 LI 上，导致投放报错或量计错。

**根因：** PG deal 有 `targetedAdvertiserId` 约束，跨 advertiser 使用会被拒绝。

**对策：** 建单前校验 `deal.targetedAdvertiserId == advertiser_id`，不一致直接拒绝创建；多客户代发用脚本批量校验（见下）。

```python
# 代发场景：批量校验 deal 归属
from ad_platform_api import AdPlatformAPI
api = AdPlatformAPI(credentials)

deal_target_map = {
    'deal_8888': 'advertiser_AAA',
    'deal_9999': 'advertiser_BBB',
}
for deal_id, owner in deal_target_map.items():
    if owner != 'advertiser_AAA':
        print(f"❌ deal {deal_id} 不属于 advertiser_AAA，禁止绑定")
```

---


## 四、常见问题与排查

### 4.1 FAQ 主表

| # | 问题 | 可能原因 | 排查路径 | 解决 |
|---|------|---------|---------|------|
| 1 | PG 不出量（0 展示） | 创意未过审 / deal 未生效 / 未绑定库存 | 查创意审批状态 → 查 deal 状态 → 查绑定 | 过审创意 / 接受 proposal / 绑定 deal |
| 2 | Deal 无效 | proposal 未 ACCEPTED / deal 过期 / 跨 advertiser | `dv360_list_proposals` 查状态 / 校验 targetedAdvertiserId | 走完接受流程 / 续约 / 换正确账号 |
| 3 | 保量未达（欠量） | 库存不足 / 定向过窄 / 排期不均 / 创意被拒 | 四查（创意/库存/定向/排期） | 见 3.4 Underdelivery SOP |
| 4 | 价格不平（账单超预算） | 溢量无 cap / CPM 用错 / 计费口径差异 | 查 overdelivery 设置 / CPM 配置 / 对账 | 设 +10% cap / 修正 CPM / 对账追回 |
| 5 | 绑定库存失败 | SDC 未配 / 域名未验证 / 广告位不匹配 | 查 SDC 状态 / GAM 域名 / 尺寸匹配 | 开 SDC / 补验证 / 对齐广告位 |
| 6 | Proposal 卡审核 | 无人盯状态 / 条款改动未重提 | 轮询状态 / 查 owner | 设提醒 / 脚本告警 |
| 7 | 素材未过审 | 违规 / 格式不符 / 审核中 | `dv360_get_creative_approval` | 修素材重传 / 预留审批时间 |
| 8 | 显示 ACTIVE 但无量 | LI 未绑 deal / flight 未起 | 查 LI.deal / flight | 绑定 deal 再启 |
| 9 | 跨账号签错 deal | 代发绑定错 advertiser | 校验 targetedAdvertiserId | 禁止跨账绑定 |
| 10 | 达标率波动大 | 媒体库存波动 / 竞价挤占 | 要库存报告 / 看 pacing | 协商补量 |

### 4.2 问题 1 详解：PG 不出量排查树

```
PG 不出量（展示=0）
   │
   ├─ 1. 创意审批了吗？
   │     └─ NO → 先批创意（dv360_get_creative_approval）
   │
   ├─ 2. Deal 生效了吗？
   │     └─ proposal 未 ACCEPTED / deal 过期 → 走接受流程
   │
   ├─ 3. LI 绑定 deal 了吗？
   │     └─ NO → 补绑 deal_id，再激活
   │
   ├─ 4. Flight 起了吗？
   │     └─ 检查 start/end 与 HTTP 时间
   │
   └─ 5. 库存有供给吗？
         └─ 向媒体确认供给，防结构性欠量
```

### 4.3 问题 5 详解：绑定库存失败的 4 类原因

| 类别 | 表现 | 根因 | 解决 |
|------|------|------|------|
| SDC 未启用 | 自动建单失败 | 商家 GAM 未开 SDC | 让媒体开通 SDC 功能 |
| 域名未验证 | 媒体报"库存不可用" | 域名未在 GAM 验证 | 媒体完成域名/App 认证 |
| 广告位不匹配 | 尺寸/格式对不上 | deal 定向与 LI 定向不一致 | 对齐 inventory_source 与 placement |
| 权限不足 | API 报 403/权限 | Partner 未关联 / 无 SDC 权限 | 建立 partner link / 授予权限 |

```python
# 用脚本快速定位「绑定库存失败」
from ad_platform_api import AdPlatformAPI
api = AdPlatformAPI(credentials)

try:
    li = api.dv360_get_line_item(advertiser_id='123456', line_item_id='li_7788')
    print("deal:", li.get('deal'))
    print("inventory:", li.get('inventorySource'))
    # 若 deal 为空 → 未绑定；inventory 为空 → 库存未指定
except Exception as e:
    print("查询失败，可能权限或账户问题:", e)
```

### 4.4 问题 3 详解：欠量根因优先级

```
欠量根因发生频率（经验排序）：
  1. 创意审批拖延未过审          （低频但致命，量归零）
  2. 定向过窄 / 频控过严         （中频，慢性失血）
  3. 媒体库存供给不足 / 夸大      （中频，结构性欠量）
  4. 排期前松后紧 / pacing 不均   （高频，最后期冲不上去）
  5. 溢量被 GAM 当竞价转走        （低频，多发生在旺季）

排查顺序建议：先查 1（创意）→ 2（定向）→ 4（pacing），再要库存报告（3）。
```

### 4.5 保量达标的 fine-tune 检查清单

```
□ 承诺量与供给/触达匹配（estimate_reach ≥ 保量 × 2）
□ 定向宽度合理（核心人群 + 少量排除，别收死）
□ 频控设置不为 0（否则重复刷量撑不起真实人群）
□ 排期 pacing 均匀 / 按需 front-load
□ overdelivery cap 已设（默认 +10%）
□ 创意全部 APPROVED 且与 deal 关联
□ deal 已 ACCEPTED 且 targetedAdvertiserId 匹配
□ SDC / 手动绑定库存已生效
□ 日报自动存档（追责证据）
□ 最后 7 天补量预案已就绪
```

---

## 五、自测题

### 题 1：概念判断
PG（程序化保量）与 PMP 的最本质区别是什么？请从「价格、展示量、库存」三个维度说明。

<details>
<summary>查看答案</summary>

| 维度 | PG | PMP |
|------|-----|-----|
| 价格 | 固定 CPM（谈定） | 底价 + 竞价（可浮动） |
| 展示量 | 合同保证（承诺量必达） | 不保证（尽力） |
| 库存 | 锁定指定库存 | 优质但不锁定 |

本质：PG 是「合同契约式的确定性采买」（保量+固定价+锁库存），PMP 是「邀请制竞价式采买」（非保量）。
</details>

### 题 2：流程判断
一条 PG 交易从发起到可投放，proposal 必须经过哪些关键状态？在哪个状态下可以修改条款？

<details>
<summary>查看答案</summary>

必经状态：`DRAFT`（草稿）→ 提交送审 → `PENDING_REVIEW`（待审核）→ 对方接受 → `ACCEPTED`（生效）。之后生成 Guaranteed Deal，创建 IO/LI 完成投放。

可修改条款：**`DRAFT` 和 `REJECTED`** 状态可改；`PENDING_REVIEW` 和 `ACCEPTED` 不能直接改条款（须退回/新建提案）。
</details>

### 题 3：排错
PG Line Item 显示 ACTIVE 但展示为 0，请按优先级列出排查步骤。

<details>
<summary>查看答案</summary>

按优先级：
1. 创意审批状态——未过审则 0 展示（最高频致命项）；
2. Deal 是否 ACCEPTED 且绑定到该 LI（deal_id 是否生效）；
3. LI 是否真的绑定了 deal / inventory 是否指定；
4. Flight 起止时间是否正确；
5. 媒体库存是否有供给。

一句话口诀：**先批创意 → 再看 deal → 后看绑定 → 再看 flight → 最后查库存**。
</details>

### 题 4：计算
承诺保量 200 万展示、投放 61 天，第 10 天末实际展示 24 万。请计算当日达标率并判断是否需要预警。

<details>
<summary>查看答案</summary>

应达 = 200 万 × (10/61) ≈ 327,869 次展示。
达标率 = 240,000 / 327,869 × 100% ≈ **73.2%**。

按本笔记标准分级，73.2% 落在 70%~90% 的 🟠「明显欠量」区间，需**立即排查**（创意/定向/pacing）并启动补量与商家沟通。前 3 天起量慢可容忍，但第 10 天仍不足 80% 必须动起来。
</details>

### 题 5：策略
客户 CPM 预算 $25，媒体坚持 $30。你有哪些不违约、能推进的备选方案？

<details>
<summary>查看答案</summary>

四个退路（按优先级）：
1. **降量不降价**：保量 200 万 → 100 万，维持 $30 或谈到 $28；
2. **换库存**：首屏换二屏 / 换同集团次级媒体，价格下探；
3. **转 PMP**：库存认可但价谈不拢 → 改非保量 PMP，用竞价拿量；
4. **换周期**：旺季挪淡季，用时间换更低 CPM。

⚠️ 绝对禁止：在价格未对齐客户预算时硬上 $30 建单——会导致超预算 20% 且客户拒付（见踩坑 3.5.4）。
</details>

---

## 附：本文引用的真实 API 方法（速查）

| 方法 | 来源 | 用途 |
|------|------|------|
| `get_transaction_type_options()` | `dv360_api.py` | 返回含 `PROGRAMMATIC_GUARANTEED` 的交易类型 |
| `list_insertion_orders()` / `create_insertion_order()` | `dv360_api.py` | IO 列表/创建 |
| `create_line_item()` | `dv360_api.py` | IO 下创建 LI |
| `request(method, endpoint)` | `dv360_api.py` | 底层 REST（proposal 等） |
| `dv360_list_proposals()` | `ad_platform_api.py` | 列提案、查状态 |
| `dv360_accept_proposal()` / `dv360_reject_proposal()` | `ad_platform_api.py` | 接受/拒绝提案 |
| `dv360_create_line_item(type=PROGRAMMATIC_GUARANTEED)` | `ad_platform_api.py` | 创建保量 LI |
| `dv360_list_flights()` / `dv360_list_sellers()` | `ad_platform_api.py` | 排期/卖方前置调研 |
| `dv360_estimate_reach()` | `ad_platform_api.py` | 触达预估（校验保量可行性） |
| `dv360_get_line_item()` / `dv360_get_report()` | `ad_platform_api.py` | 详情查询/达标率日报 |
| `dv360_get_creative_approval()` | 技能 `dv360-expert` | 创意审批状态 |

> 关联阅读：`dv360-architecture-deep.md`（交易类型总览）、`dv360-dfp-deep.md`（SDC/保量 vs RTB 服务端逻辑）、`dsp-core-flow-deep.md`（广义 DSP 侧程序化采买）。

