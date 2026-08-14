# DV360 媒体购买全流程深度解析（IO / LineItem / 创意 / 出价 / 排期 / 预算）

> **领域**: 广告投放 / 媒体购买
> **深度**: ⭐⭐⭐⭐⭐ 实战级指南
> **标签**: dv360, media-buying, insertion-order, line-item, flight, budget
> **更新时间**: 2026-08-14
> **类型**: 深度文档

---

本文将 DV360（Display & Video 360）从 "媒体购买" 的角度做一次端到端的拆解。与同目录下其它文档的分工如下：

| 文档 | 侧重点 | 与本文的关系 |
|------|--------|--------------|
| `dv360-architecture-deep.md` | 平台概述、RTB 生态、账户层级、Go 广告请求引擎 | 本文聚焦媒体购买全流程，架构图更细到 "可执行" |
| `dv360-optimization-deep.md` | 投放策略、预算分配、智能出价优化 | 本文补充预算模型 / pacing / 排期的机制层细节 |
| `dv360-marketing-api-deep.md` | API 端点、认证、客户端封装 | 本文给出可直接复刻的 Python/Go 源码客户端 |
| `dv360-creative-brand-safety-deep.md` | 创意格式、品牌安全、可见性 | 本文只讲创意与 LineItem 的关联、上传与审批流转 |
| `dv360-measurement-attribution-deep.md` | 归因、转化追踪 | 本文不展开归因，只引用 floodlight 配置 |
| **本文** | **媒体购买全流程** | **IO → LineItem → Creative → 出价 → 排期 → 预算的完整闭环** |

核心问题贯穿全文：**"一笔钱怎么按结构、按时间、按节奏精确地花出去，并且能被 API 完整地创建、查询、暂停、恢复和排错。"**

---

## 一、核心概念与架构

### 1.1 媒体购买的完整层级图

DV360 的账户树从上到下依次是：Partner → Advertiser → Campaign → Insertion Order → Line Item → Creative。每一个层级都有严格的生命周期和归属约束，任何一次 API 调用都必须携带正确的父级 ID 才能定位实体。先用一张 ASCII 图把全貌铺开：

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Partner (合作伙伴)                           │
│   拥有多重货币、时区、出价结算属性；是整个账户树的根                    │
├──────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    Advertiser (广告主)                          │  │
│  │   计费主体：人民币/美元/欧元；拥有自己的 floodlight 配置          │  │
│  │   API 资源路径: /advertisers/{advertiserId}                    │  │
│  │                                                                │  │
│  │  ├── Campaign (广告系列)                                      │  │
│  │  │    业务目标容器：曝光、转化、品牌                                          │  │
│  │  │    API: /advertisers/{adv}/campaigns/{campaignId}           │  │
│  │  │                                                                │  │
│  │  │  └── Insertion Order (IO, 订单项 / 媒体采购单)              │  │
│  │  │       花钱的"合同"，含总预算、排期窗口、预算分配、灵活性      │  │
│  │  │        API: /advertisers/{adv}/insertionOrders/{ioId}       │  │
│  │  │                                                              │  │
│  │  │        └── Line Item (线条项目 / 媒体购买)                  │  │
│  │  │             真正参与竞价的最小逻辑单元，含出价、定向、排期     │  │
│  │  │              API: /advertisers/{adv}/insertionOrders/{io}/   │  │
│  │  │                    lineItems/{lineItemId}                    │  │
│  │  │                                                              │  │
│  │  │              └── Creative (创意)                            │  │
│  │  │                    通过 LineItem 关联上传的素材，参与审批      │  │
│  │  │                     API: /advertisers/{adv}/creatives/       │  │
│  │  │                          {creativeId}                        │  │
│  │  │                                                              │  │
│  │  │  Flight (投放周期) = 是 LineItem 的"时间段 + 预算" 视图      │  │
│  │  │        在 DV360 中 LineItem 可以拆成多个 flight 排期         │  │
│  │  └── Floodlight / Audiences / Placements / 定向数据源          │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 官方 API 资源路径 vs. 常见误区

很多初学者把 "IO" 和 "Campaign" 混为一谈。这里给一张对照表，并标注对应的真实 API 方法名（来自 `dv360_api.py` 的 `DV360Client` 类与 `ad_platform_api.py` 的 `dv360_*` 系列）：

| 层级 | 语义 | 所属父级 | 关键字段 | dv360_api.py | ad_platform_api.py |
|------|------|----------|----------|--------------|--------------------|
| Partner | 合作伙伴/代理商账户 | 无（根） | 默认货币/时区 | `list_advertisers(partner_id)` | `dv360_list_advertisers` |
| Advertiser | 广告主（计费主体） | Partner | currency_code, partner_id | `get_advertiser` | `dv360_get_advertiser`, `dv360_validate_advertiser` |
| Campaign | 广告系列（业务目标） | Advertiser | goal, budget | `list_campaigns`, `create_campaign`, `pause_campaign` | `dv360_list_campaigns` 系列 |
| IO | 订单项/媒体采购单（花钱合同） | Advertiser | budget, frequency_cap, targeting | `list_insertion_orders`, `create_insertion_order` | `dv360_list_insertion_orders`, `dv360_list_insertion_order_flexibility` |
| Line Item | 线条项目/媒体购买（竞价单元） | IO | type, flight, bid, targeting | `list_line_items`, `create_line_item` | `dv360_create_line_item`, `dv360_update_line_item`, `dv360_get_pacing_rate` |
| Creative | 创意素材 | Line Item | format, media_file | `list_creatives`, `create_creative` | `dv360_create_creative`, `dv360_list_creatives` |

**要点**：Campaign 与 IO 是一对多；IO 与 Line Item 是一对多；Line Item 与 Creative 是一对多（但 Creative 先在 advertiser 级创建，再挂到 LineItem 上）。

### 1.3 IO 与 Line Item 的关系 —— 谁是"合同"，谁是"执行"

这是媒体购买中最容易混淆的一层，也是团队里 PM（媒介采购）与优化师最容易吵架的分界：

- **IO（Insertion Order）** 是**合同 / 下单层面**的实体：它定义了一笔媒体购买的**总预算**、**排期窗口（start/end）**、**频率上限**、**预算分配的灵活性（flexibility）**。它自己**不直接竞价**，只是把一笔钱"框"起来。
- **Line Item（线条项目）** 是**执行 / 竞价层面**的实体：它定义**用什么类型的库存**（PG/PMP/Open Auction）、**出价策略与出价金额**、**定向**、以及**具体的 flight 时间段与预算**。真正进拍卖的是 Line Item，不是 IO。
- **Flight** 是 Line Item 的**拆段投放**：同一个 Line Item 可以有多个 flight，每个 flight 各有一段时间窗口与一份预算，从而把总量按阶段切分（例如预热期 / 爆发期 / 收尾期）。

用一张 "谁负责什么" 的表：

| 维度 | IO 负责 | Line Item 负责 | Flight 负责 |
|------|---------|----------------|-------------|
| 预算 | 总预算（IO level） | 每个 Line Item 的预算上限 | 每个 flight 的段预算 |
| 时间 | IO 起止日期（整体窗口） | Line Item 起止 | flight 的细分起止 |
| 竞价 | 不竞价 | 出价策略 + 出价金额 | 只切时间，不切竞价 |
| 定向 | 很少放（一般留空给子级） | 核心定向全在这 | 无定向 |
| 频率 | frequency_cap（IO 级跨 LineItem） | 可另设 | 无 |

### 1.4 交易类型与媒体购买类型（transaction type）

Line Item 的 `type`（交易类型）决定了它如何获取库存。下面的枚举来自 `dv360_api.py` 的 `get_transaction_type_options()`：

```
PROGRAMMATIC_GUARANTEED  →  程序化保量（保证量 + 固定 CPM，直接与 publisher 谈）
PRIVATE_MARKETPLACE     →  私有市场（邀请制优质库存，竞价但排除开放竞争）
PREFERRED_DEAL          →  优先交易（publisher 优先给 DV360 选择权，非保量）
OPEN_AUCTION            →  公开竞价（Google AdX 及开放式交易所，动态出价）
```

| 类型 | 保量？ | 计价 | 适用场景 | 特点 / 坑 |
|------|--------|------|----------|-----------|
| PROGRAMMATIC_GUARANTEED | ✅ 保证 | 固定 CPM | 大促保量、品牌曝光、重点 Deal | 剂量必须精确，否则要么赔钱要么量不足 |
| PRIVATE_MARKETPLACE | ❌（但竞争小） | 动态 CPM | 品牌安全优先、优质库存 | 流跌价快，pacing 容易跟不上 |
| PREFERRED_DEAL | 🟡 优先权 | 动态 CPM | 优质位置优先测试 | 非保量，可能饿死 |
| OPEN_AUCTION | ❌ | 动态 CPM | 效果投放、量大便宜 | pacing 波动大，需广告主合理出价 |

### 1.5 预算模型：三层预算谁说了算

DV360 的预算有明确的层级与优先级。理解这条链，是避免 "预算超支 / 少投" 的关键：

```
IO 总预算（Budget of Insertion Order）
   ↓ 约束下属
Line Item 预算（每个 LineItem 各有 budget）
   ├── 总预算（无 flight 拆分时）  ← 最常见
   └── 按 flight 拆分：flight1 预算 + flight2 预算 = LineItem 预算上限
```

**预算优先级（谁能 limit 谁）**：

1. **IO 预算** 是所有子 Line Item 的**总上限**——即使所有 Line Item 单独设了大预算，IO 一收紧，整体就被卡住。
2. **Line Item 预算** 是单条 Line Item 的独立上限。
3. **Flight 预算** 是 Line Item 在某一段时间的上限。

> 实务坑：很多团队只调 Line Item 预算而忘了 IO 预算没放大，导致 "看起来预算加满了但整体就是放不出来"，这就是经典的 **IO 预算成为隐性瓶颈**。

### 1.6 排期模型：单一窗口 vs. flight 拆段

Line Item 有**两种时间模型**，媒体购买团队必须一开始就定好，因为中途改窗口会影响 pacing 与预算均摊：

| 模型 | 说明 | 典型场景 | 风险 |
|------|------|----------|------|
| 单一窗口 | LineItem 一个 start/end，预算在整个窗口均摊 | 常规月投放 | pacing 波动会集中在收尾 |
| 多 flight | 一个 LineItem 多个 flight，各自窗口+预算 | 双11预热/爆发/返场 | flight 之间衔接断层、重复计费 |

flight 的时间与预算拆分的 ASCII 示意：

```
LineItem: "双11 大促全量"
├── Flight 1 预热   : 11-01 ~ 11-09  预算 30%   (探量、蓄水)
├── Flight 2 爆发   : 11-10 ~ 11-11  预算 50%   (主战场，高 COP)
└── Flight 3 返场   : 11-12 ~ 11-15  预算 20%   (清尾、再营销)
```

至此我们建立了整个媒体购买的骨架：**IO 管钱，Line Item 管竞价，Flight 切时间，Creative 提供素材，Budget/Pacing 决定钱怎么花，出价策略决定花多少钱换多少量。** 下一章深入每个机制的原理与可执行代码。

---
## 二、深度原理解析

### 2.1 IO（Insertion Order）的创建 / 更新 / 暂停 / 恢复生命周期与状态机

IO 是媒体购买的第一层落地对象。它的状态机比表面看上去复杂：**创建时的默认状态、暂停 / 恢复的语义、以及 "已过去排期" 与 "未开始" 的边界处理**，是 API 排错的高发区。

#### 2.1.1 IO 状态机总览

```
                 ┌──────────────────────────────────────────┐
                 │                                          │
   create()      │   ACTIVE（活动）                          │
 ───────────────▶│   - 可被下属 LineItem 消耗预算            │
                 │   - pacing 正常启动                       │
                 │                                          │
                 └──────────────┬───────────────────────────┘
                                │ pause() / resume()
              ┌─────────────────┴──────────────────┐
              │                                    │
              ▼                                    ▼
   ┌───────────────────┐                ┌───────────────────┐
   │     PAUSED        │ ◀─────────────▶│     ACTIVE        │
   │  - 旗下 LineItem   │   resume()     │                   │
   │    停止竞价         │                │                   │
   │  - 保存预算不消耗   │                │                   │
   └───────────────────┘                └───────────────────┘
              │
              │ 排期结束（end 时间到达）
              ▼
   ┌───────────────────┐
   │   过去（Past）      │  只读，不能再激活
   │  - 不可 resume      │
   └───────────────────┘
```

**状态机规则**：
- 新创建的 IO 默认是 `DRAFT` 或 `ACTIVE`，取决于底层实现是否直接带上排期/预算；实务中为避免误花钱，通常先建 `DRAFT`，配置齐了再切 `ACTIVE`。
- `PAUSED` 状态下，旗下所有 Line Item 立即停止出价，但**已产生的历史花费不回滚**、**排期窗口仍计时**（只是不消耗）。
- 当 IO 的 end 时间点已过，它进入 "过去" 的只读态，**任何试图 resume 的调用都会被拒绝或忽略**——这是"排期结束但想加量"时报错的根因。

#### 2.1.2 IO 创建的真实代码

以 `dv360_api.py` 的 `DV360Client` 为基底，写一个完整的 IO 创建封装。注意层次方法的实际签名：IO 属于 **Advertiser**（不是 Campaign 的子级），所以路径是 `advertisers/{adv}/insertionOrders`：

```python
# -*- coding: utf-8 -*-
"""
IO 生命周期封装：基于 dv360_api.py 的 DV360Client 扩展。
关键方法名对齐项目脚本：list_insertion_orders / create_insertion_order
"""

import time
from typing import Dict, List


class InsertionOrderService:
    """IO 服务：负责 IO 的构建、创建、暂停、恢复、状态查证。"""

    def __init__(self, client):
        self.client = client  # DV360Client 实例

    def build_insertion_order(
        self,
        name: str,
        advertiser_id: str,
        start_time_micros: int,
        end_time_micros: int,
        budget_micros: int,
        currency_code: str = "CNY",
    ) -> Dict:
        """
        构造一个标准 IO 请求体。
        注意 DV360 API 的时间字段是"微秒"级别（micros），
        很多踩坑都来自把毫秒当微秒、或把秒当微秒。
        """
        return {
            "name": name,
            "advertiserId": advertiser_id,
            "entityStatus": "ENTITY_STATUS_ACTIVE",
            "budget": {
                "budgetUnit": "BUDGET_UNIT_CURRENCY",  # 记账单位：货币
                "maxAmountMicros": budget_micros,       # 单位：微单位（1 元 = 1_000_000）
                "currencyCode": currency_code,
                # 可选：按天等额（EVEN）/ 前置（FRONT_LOADED）等，
                # 见 2.4 预算分配机制
            },
            "pacing": {
                # pacing 枚举：PACING_MODE_EVEN / PACING_MODE_ASAP
                # 见 2.4 节
            },
            "schedule": {
                "startDate": self._micros_to_date(start_time_micros),
                "endDate": self._micros_to_date(end_time_micros),
            },
        }

    def _micros_to_date(self, micros: int) -> Dict:
        """DV360 的 schedule 用 {year,month,day} 结构，而不是 ISO 字符串。"""
        import datetime
        dt = datetime.datetime.fromtimestamp(micros // 1_000_000)
        return {"year": dt.year, "month": dt.month, "day": dt.day}

    def create(self, advertiser_id: str, io: Dict) -> Dict:
        """对标 list_insertion_orders / create_insertion_order。"""
        resp = self.client.create_insertion_order(advertiser_id, io)
        if not resp.success:
            raise RuntimeError(f"IO 创建失败: {resp.error}")
        return resp.data

    def pause(self, advertiser_id: str, io_id: str) -> Dict:
        """暂停 IO。暂停是"软"操作，通过更新 entityStatus 实现。"""
        return self.client.update_io_status(advertiser_id, io_id, "ENTITY_STATUS_PAUSED")

    def resume(self, advertiser_id: str, io_id: str) -> Dict:
        """恢复 IO。若 IO 排期已结束，此调用应被上层拦截。"""
        return self.client.update_io_status(advertiser_id, io_id, "ENTITY_STATUS_ACTIVE")

    def is_expired(self, io: Dict, now_micros: int) -> bool:
        """判断 IO 是否已过期（排期 end 早于当前时间）。"""
        end = io["schedule"]["endDate"]
        end_micros = (end["year"] * 365 + end["month"] * 31 + end["day"]) * 86_400 * 1_000_000
        # 简化估算：精确判断需用 datetime 相减，这里示意逻辑
        return end_micros < now_micros
```

> **设计要点**：项目脚本里没有 `update_io_status` 方法，但 `create_insertion_order` 接受完整的 IO dict；所以"暂停/恢复 IO"的正确姿势是**用 `create_insertion_order`（实际是 upsert 语义）把整个 IO 重新提交一遍**，把 `entityStatus` 改成目标值。DV360 API 的 `insertionOrders.create` 对已存在 ID 是覆盖更新，这是它和传统 REST 的一个显著差异——**没有单独的 PATCH，只有全量 PUT 式提交**。

#### 2.1.3 为什么推荐"全量 upsert"而不是字段级更新

很多从其它广告平台转来的工程师习惯字段级更新。DV360 的 create/update 对 IO 与 LineItem 是**全量提交**：你提交的 dict 会被当作该实体的完整期望状态。这意味着：

1. 漏传字段 = 该字段被**清空/重置**为默认，而不是保持原值。
2. 所以安全的做法是：**先 GET 当前状态 → 修改目标字段 → 全量 PUT**，即"读-改-写"（read-modify-write）模式。

```
安全更新流程：
  1) dv360_list_insertion_orders()  查当前对象（或直接 get）
  2) 复制返回的 dict
  3) 修改 {entityStatus / budget / schedule}
  4) create_insertion_order(advertiser_id, 改后的完整 dict)
```

下面给一个 Go 版本的 read-modify-write 帮助函数，便于生产服务使用：

```go
package mediabuying

import "fmt"

// InsertionOrder 对齐 DV360 API 的 IO 结构（节选关键字段）。
type InsertionOrder struct {
	Name        string `json:"name"`
	AdvertiserID string `json:"advertiserId"`
	EntityStatus string `json:"entityStatus"`
	Budget      Budget `json:"budget"`
	Schedule    Schedule `json:"schedule"`
}

type Budget struct {
	BudgetUnit    string `json:"budgetUnit"`
	MaxAmountMicros int64 `json:"maxAmountMicros"`
	CurrencyCode  string `json:"currencyCode"`
}

type Schedule struct {
	StartDate Date `json:"startDate"`
	EndDate   Date `json:"endDate"`
}

type Date struct {
	Year  int `json:"year"`
	Month int `json:"month"`
	Day   int `json:"day"`
}

// UpdateInsertionOrderStatus 用"读-改-写"方式安全地暂停/恢复 IO。
// getIO 与 putIO 分别是 GET/PUT 的抽象；项目里对应基于
// dv360_api.py DV360Client 或 dv360_client.py DV360Client 的调用。
func UpdateInsertionOrderStatus(
	getIO func(advertiserID, ioID string) (*InsertionOrder, error),
	putIO  func(advertiserID, ioID string, io *InsertionOrder) error,
	advertiserID, ioID, desiredStatus string,
) (*InsertionOrder, error) {
	io, err := getIO(advertiserID, ioID)
	if err != nil {
		return nil, fmt.Errorf("get IO: %w", err)
	}
	if io.EntityStatus == "" {
		return nil, fmt.Errorf("IO %s has no entityStatus; cannot patch", ioID)
	}
	io.EntityStatus = desiredStatus
	if err := putIO(advertiserID, ioID, io); err != nil {
		return nil, fmt.Errorf("put IO: %w", err)
	}
	return io, nil
}
```

**状态机总结表**（排错对照）：

| 期望操作 | 当前状态 | 推荐动作 | 可能被拒/报错的原因 |
|----------|----------|----------|---------------------|
| 暂停 | ACTIVE / DRAFT | entityStatus → PAUSED | 无（正常） |
| 恢复 | PAUSED | entityStatus → ACTIVE | 排期已过（past），拒绝 |
| 删除 | 任意 | DELETE | 有活跃 LineItem 时若级联配置未开则报错 |
| 追加预算 | ACTIVE/PAUSED | maxAmountMicros 调大 | 超过 Partner 层级配额被拒 |

---
### 2.2 Line Item 类型与配置字段 JSON 结构

Line Item 是真正的竞价单元，也是媒体购买 API 中被调用最多、字段最复杂的对象。项目里对它有一整套封装：`dv360_create_line_item` / `dv360_update_line_item` / `dv360_get_line_item` / `dv360_pause_line_item` / `dv360_resume_line_item` / `dv360_delete_line_item` / `dv360_batch_update_line_items`。

#### 2.2.1 Line Item 的 `type`：媒体购买类型

与 1.4 的交易类型不同，Line Item 还有一个更粗的 `type` 字段，用来区分**展示 / 视频**等大类别，再叠加交易类型（PG/PMP/OpenAuction）才构成完整画像：

```
DISPLAY   → 展示广告（banner / native）
VIDEO     → 视频广告（in-stream / out-stream）
AUDIO     → 音频广告
```

| LineItem type | 主要 Creative 格式 | 用到的交易类型偏好 |
|---------------|-------------------|--------------------|
| DISPLAY | BANNER_AD / NATIVE_AD / HTML5_AD | PMP / Open Auction / PG |
| VIDEO | VIDEO_PREROLL_AD / VIDEO_MIDROLL_AD | PG / PMP（品牌） |
| AUDIO | 音频前贴片 | PMP / Open Auction |

#### 2.2.2 一个可提交的完整 Line Item JSON

下面是一个覆盖大部分关键字段的 Line Item 请求体。用字段注释说明每个部分在媒体购买流程里的含义——这份 JSON 是理解"排期/预算/出价/定向如何拼装"的最佳入口：

```json
{
  "name": "双11-爆发期-DISPLAY-PMP-华东-高意向人群",
  "entityStatus": "ENTITY_STATUS_ACTIVE",
  "advertiserId": "123456789",
  "campaignId": "987654321",
  "insertionOrderId": "111222333",
  "type": "DISPLAY",
  "integrationType": "INVENTORY_SOURCE_OPEN_DIRECT", 
  "lineItemType": "LINE_ITEM_TYPE_DISPLAY_DEFAULT",
  "flight": {
    "plannedStartDate": { "year": 2026, "month": 11, "day": 10 },
    "plannedEndDate":   { "year": 2026, "month": 11, "day": 11 },
    "effectiveStartDate": { "year": 2026, "month": 11, "day": 10 },
    "effectiveEndDate":   { "year": 2026, "month": 11, "day": 11 }
  },
  "budget": {
    "budgetUnit": "BUDGET_UNIT_CURRENCY",
    "maxAmountMicros": 500000000,            // 5,000,000 ? 即 500 units * 1e6
    "currencyCode": "CNY",
    "pacingType": "PACING_MODE_ASAP"
  },
  "bidStrategy": {
    "type": "BID_STRATEGY_TYPE_FIXED_CPM",
    "fixedBid": { "amountMicros": 12000000 }  // CPM = 12 元（千次展示）
  },
  "targeting": {
    "inventorySource": { "sourceIds": ["inventory_pmp_404"] },
    "geo": { "targetingOptions": ["geo_hangzhou", "geo_shanghai"] },
    "audience": { "targetingOptions": ["audience_high_intent"] },
    "deviceType": { "targetingOptions": ["DEVICE_TYPE_MOBILE", "DEVICE_TYPE_DESKTOP"] },
    "frequencyCap": { "maxImpressions": 3, "timeUnit": "TIME_UNIT_DAY" }
  },
  "measurement": {
    "conversionTracking": {
      "floodlightConfigId": "floodlight_5566",
      "floodlightActivityId": "floodlight_act_7788"
    }
  },
  "creativeIds": ["creative_99001", "creative_99002"]
}
```

字段到媒体购买流程的映射：

| JSON 字段 | 所属流程 | 说明 |
|-----------|----------|------|
| `type` / `lineItemType` | 购买类型 | 展示/视频 + 默认类型 |
| `flight.plannedStartDate / plannedEndDate` | 排期 | 计划窗口 |
| `flight.effectiveStartDate / effectiveEndDate` | 排期 | 实际生效窗口（系统计算） |
| `budget.budgetUnit / maxAmountMicros / currencyCode` | 预算 | 钱的上限与币种 |
| `budget.pacingType` | pacing | EVEN（均匀）/ ASAP（尽快） |
| `bidStrategy.type / fixedBid` | 出价 | 固定 CPM 或其它策略 |
| `targeting.*` | 定向 | 库存/地域/受众/设备 |
| `targeting.frequencyCap` | 频控 | 同一用户曝光上限 |
| `measurement.conversionTracking` | 归因 | floodlight 挂接 |
| `creativeIds` | 创意 | 关联已上传的创意 |

#### 2.2.3 创建 Line Item 的 Python 封装

直接用项目里的 `dv360_create_line_item` 语义做一层业务封装，把"业务参数"翻译成"API 字段"：

```python
# -*- coding: utf-8 -*-
from typing import Dict, Optional


class LineItemBuilder:
    """把媒介采购需求翻译成 DV360 Line Item 请求体。"""

    TIME_UNIT_DAY = "TIME_UNIT_DAY"

    def __init__(self, client):
        self.client = client  # ad_platform_api.get_client('dv360') 或自封装

    def build_line_item(
        self,
        advertiser_id: str,
        io_id: str,
        name: str,
        line_item_type: str,
        currency_code: str,
        budget_micros: int,
        cpm_micros: int,
        pacing: str = "PACING_MODE_EVEN",
        start: Optional[Dict] = None,
        end: Optional[Dict] = None,
    ) -> Dict:
        """生成一个 DISPLAY / VIDEO LineItem 请求体。
           参数均为业务层语义，函数内部做字段名翻译。"""
        return {
            "name": name,
            "advertiserId": advertiser_id,
            "insertionOrderId": io_id,
            "entityStatus": "ENTITY_STATUS_ACTIVE",
            "type": "DISPLAY" if line_item_type == "display" else "VIDEO",
            "flight": {
                "plannedStartDate": start or {"year": 2026, "month": 1, "day": 1},
                "plannedEndDate": end   or {"year": 2026, "month": 1, "day": 31},
            },
            "budget": {
                "budgetUnit": "BUDGET_UNIT_CURRENCY",
                "maxAmountMicros": budget_micros,
                "currencyCode": currency_code,
                "pacingType": pacing,
            },
            "bidStrategy": {
                "type": "BID_STRATEGY_TYPE_FIXED_CPM",
                "fixedBid": {"amountMicros": cpm_micros},
            },
            "targeting": {
                # 定向在 create 之后单独创建 / 关联，避免一次提交失败回滚整个 LineItem
            },
        }

    def create(self, advertiser_id: str, io_id: str, body: Dict) -> Dict:
        """对标 dv360_create_line_item(advertiser_id, name, **kwargs)。"""
        # 项目方法 dv360_create_line_item 以 name 为首参，其余字段进 kwargs；
        # 这里采用更贴近业务的分层写法，等价逻辑。
        return self.client.dv360_create_line_item(
            advertiser_id=advertiser_id,
            name=body["name"],
            **{k: v for k, v in body.items() if k != "name"},
        )

    def update(self, advertiser_id: str, line_item_id: str, patch: Dict) -> Dict:
        """对标 dv360_update_line_item(advertiser_id, line_item_id, **kwargs)。
           记住 DV360 是全量语义：调用前应先把 patch 合并进 GET 结果。"""
        return self.client.dv360_update_line_item(
            advertiser_id=advertiser_id,
            line_item_id=line_item_id,
            **patch,
        )

    def pause(self, advertiser_id: str, line_item_id: str) -> Dict:
        """对标 dv360_pause_line_item。"""
        return self.client.dv360_pause_line_item(advertiser_id, line_item_id)

    def resume(self, advertiser_id: str, line_item_id: str) -> Dict:
        """对标 dv360_resume_line_item。"""
        return self.client.dv360_resume_line_item(advertiser_id, line_item_id)

    def get_pacing_rate(self, advertiser_id: str, line_item_id: str) -> Dict:
        """对标 dv360_get_pacing_rate —— 查看 LineItem 的 pacing 命中率。"""
        return self.client.dv360_get_pacing_rate(advertiser_id, line_item_id)
```

#### 2.2.4 批量创建与批量更新

大促场景（如双11）一次要建几十上百个 Line Item，逐条调 create 既不高效也容易被限流。DV360 提供批量路径，项目里对应 `dv360_batch_update_line_items(updates)` 与批量创建语义：

```python
def batch_create_line_items(client, advertiser_id: str, io_id: str, specs: list):
    """
    specs: List[dict]，每个 dict 是 build_line_item 的输出。
    批量创建原则：
      1. 先全量 build，再统一提交，避免逐条失败重试。
      2. 幂等：为每个 LineItem 生成稳定 name/键，失败重跑不产生重复。
    """
    payloads = []
    for sp in specs:
        payloads.append(client.dv360_create_line_item(
            advertiser_id=advertiser_id,
            name=sp["name"],
            **{k: v for k, v in sp.items() if k != "name"},
        ))
    # 批量接口返回各条结果，这里统一收集；失败条目单独记入 retry 列表
    results = {"created": [], "failed": []}
    return results
```

> **批量创建的实务约束**：DV360 对同一 advertiser 的 concurrency 有限制（尤其大促前大批量并发创建）。建议**串行 + 指数退避**，或用批量端点一次提交 100 条以内，避免触发 429 / QUOTA_EXCEEDED。批量更新同理：`dv360_batch_update_line_items(updates)` 适合"把十个 LineItem 统一调大预算 / 统一换出价"这类做批量，而不是把大而全的对象塞进去。

---
### 2.3 预算分配机制与 pacing（均匀 / 加速）

预算 "怎么花、花多快" 是媒体购买的灵魂。DV360 把这套能力拆成**预算分配（budget allocation）** 与 **pacing（投放速率）** 两个概念，项目里分别有 `dv360_list_budget_allocations` / `dv360_update_budget_allocation` 与 `dv360_get_pacing_rate`。

#### 2.3.1 预算分配（Budget Allocation）

预算分配描述的是**同一份预算在多个实体（IO 之间、或 LineItem 之间）如何切分**。例如一个品牌在多个 IO 之间分配总盘子。项目里的 `dv360_list_budget_allocations(advertiser_id)` 返回当前各处的分配，`dv360_update_budget_allocation(allocation_id, ...)` 用来调整。

两个最常见**分配维度**：

| 维度 | 含义 | 典型用法 | API |
|------|------|----------|-----|
| 时间维度分配 | 预算按天数/小时在 IO 生命周期的分布 | 探索期少投、爆发期多投 | `insertion_order.budget` 里选 PACING_MODE |
| 结构维度分配 | 预算在多个 IO / LineItem 之间拆分 | 双11五个 IO 各 20% | `dv360_list_budget_allocations` / `update` |

#### 2.3.2 Pacing：均匀（EVEN）vs 加速（ASAP）

Pacing 决定预算在**排期窗口内消耗的节奏**。这是媒体购买里最常被误解、也最常出问题的地方：

```
PACING_MODE_EVEN  均匀消耗
  - 目标：预算在窗口内均匀花完
  - 每天预算 ≈ 总预算 / 天数
  - 优点：稳定、可控、不容易超支
  - 缺点：遇到优质流量高峰仍被"平均"约束，可能浪费窗口

PACING_MODE_ASAP  尽快消耗
  - 目标：在预算允许下尽快花完，抢量
  - 适合：大促短窗、急性抢量
  - 缺点：可能早上就把当天预算烧完，下午没量；容易超支
```

用一张时间-消耗曲线表理解两者差异：

| 时间点（窗口内） | EVEN 累计花费 | ASAP 累计花费 |
|------------------|---------------|---------------|
| 20% | ~20% | ~45% |
| 50% | ~50% | ~75% |
| 80% | ~80% | ~92% |
| 100% | ~100% | 100%（可能提前） |

> **核心认知**：EVEN 是"按比例分配"，ASAP 是"速度优先"。两者**都要在窗口内花完预算**，区别只是"花得快不快"。如果预算设得比能消化的大，即使 EVEN 也会有多少花多少；如果预算设小，EVEN 也会提前花完然后停投。

#### 2.3.3 Pacing 命中率（pacing rate）与"放量不足"

`dv360_get_pacing_rate(advertiser_id, line_item_id)` 返回当前 pacing 状态。实务中最关心的就是 **pacing 命中率**：实际花费 vs 该时刻应花的比例。

```
pacing_rate = 实际已花费 / 应花费(按时间比例) × 100%
```

| pacing_rate | 含义 | 处理动作 |
|-------------|------|----------|
| ~100% | 节奏完美，按计划花 | 不动 |
| > 100% | 花快了（可能超支） | 转向 EVEN / 收窄定向 / 降出价 |
| < 80% | 花慢了（可能少投） | 转 ASAP / 放开定向 / 提价 / 检查库存与审批 |
| = 0% 但 LineItem ACTIVE | 完全没量 | 查：审批未过 / 无库存 / 出价过低 / IO 已暂停 |

Go 实现一个 pacing 监控器（后台轮询各 LineItem 的 pacing rate 并告警），这是生产环境最常见的媒体购买运维组件：

```go
package mediabuying

import (
	"fmt"
	"log"
	"time"
)

// PacingSnapshot 是 dv360_get_pacing_rate 的返回值的业务视图。
type PacingSnapshot struct {
	LineItemID          string  `json:"lineItemId"`
	ExpectedSpendMicros int64   `json:"expectedSpendMicros"`
	ActualSpendMicros   int64   `json:"actualSpendMicros"`
	PacingRate          float64 `json:"pacingRate"` // 0~2 之间，1 为理想
}

// MonitorPacing 周期性采集每个 LineItem 的 pacing rate，低于阈值告警。
// fetch 是需要注入的取数函数，对应 dv360_get_pacing_rate。
func MonitorPacing(
	fetch func(advertiserID, lineItemID string) (*PacingSnapshot, error),
	advertiserID string,
	lineItemIDs []string,
	threshold float64,
	interval time.Duration,
	stop <-chan struct{},
) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-stop:
			log.Println("pacing monitor stopped")
			return
		case <-ticker.C:
			for _, id := range lineItemIDs {
				snap, err := fetch(advertiserID, id)
				if err != nil {
					log.Printf("fetch pacing %s: %v", id, err)
					continue
				}
				if snap.PacingRate < threshold {
					// 低于阈值：少投告警，人工/自动放量
					log.Printf("⚠️ 少投  %s  pacing=%.2f  expected=%d actual=%d",
						id, snap.PacingRate, snap.ExpectedSpendMicros, snap.ActualSpendMicros)
				} else if snap.PacingRate > 1.2 {
					// 高于阈值：超支风险告警
					log.Printf("⚠️ 超支  %s  pacing=%.2f", id, snap.PacingRate)
				}
			}
		}
	}
}

// 使用示例：每 10 分钟检查一次，低于 0.7 告警
// go MonitorPacing(rawFetch, "123456789", ids, 0.7, 10*time.Minute, stopCh)
```

### 2.4 Flight 排期与时间段

Flight 是 Line Item 内部的时间切段。DV360 里一个 Line Item 可含多个 flight，每个 flight 拥有自己的 `plannedStartDate / plannedEndDate` 与预算，从而把总量按阶段拆开（这正是双11 预热/爆发/返场拆段的基础）。

```
LineItem: "双11"
   budget = 100 万
   ├── Flight A  预热 2026-11-01~11-09  预算 30 万  pacing EVEN
   ├── Flight B  爆发 2026-11-10~11-11  预算 55 万  pacing ASAP
   └── Flight C  返场 2026-11-12~11-15  预算 15 万  pacing EVEN
```

flight 关键字段与坑位：

| 字段 | 语义 | 常见坑 |
|------|------|--------|
| `plannedStartDate/EndDate` | 计划的窗口 | 时区不同导致一天偏差 |
| `effectiveStartDate/EndDate` | 实际生效窗口 | 由系统根据审批/状态计算 |
| flight 预算 | 该段可花上限 | 各段预算合计可能 ≠ LineItem 总预算，注意口径 |
| 相邻 flight 衔接 | A 结束与 B 开始 | 若留缝（gap）会导致断投；若重叠会双份计费 |

**flight 时间类型**：DV360 的日期字段是 `<Date>{year,month,day}` 结构（不是 ISO 字符串），递归嵌套在 `targeting.frequencyCap` 等很多字段里会再次出现时间单位，务必注意单位是 `TIME_UNIT_DAY` / `TIME_UNIT_HOUR`。

Python 工具：把业务层的 "2026-11-10" 字符串转成 DV360 需要的 Date 结构：

```python
def to_dv360_date(yyyy_mm_dd: str) -> dict:
    """'2026-11-10' -> {'year':2026,'month':11,'day':10}"""
    y, m, d = yyyy_mm_dd.split("-")
    return {"year": int(y), "month": int(m), "day": int(d)}

def to_iso(date: dict) -> str:
    """{'year':2026,'month':11,'day':10} -> '2026-11-10'"""
    return f"{date['year']:04d}-{date['month']:02d}-{date['day']:02d}"
```

### 2.5 创意与 Line Item 的关联

创意（Creative）虽在 **advertiser 级** 创建（`dv360_create_creative` / `list_creatives`），但要真正参与投放，必须**关联到 Line Item**（通过 `creativeIds` 或 LineItem 下的 creative 集合）。项目方法 `list_creatives(advertiser_id, line_item_id)` 在传 LineItemID 时返回该 LineItem 关联的创意。

```
创建顺序（推荐）：
  1) 先在 advertiser 级创建创意（上传素材、填格式）
     → dv360_create_creative(advertiser_id, name, ...)
  2) 等创意审批通过（APPROVED）
  3) 把 creativeIds 挂到 LineItem
     → dv360_update_line_item(advertiser_id, line_item_id, creativeIds=[...])
  4) 激活 LineItem 开始投放
```

**审批状态机**（对排期影响极大）：

```
创建(PENDING_APPROVAL) → 审批通过(APPROVED) → 可投放
                     ↘ 审批拒绝(REJECTED) → 修改重提
                     ↘ 中止(WITHDRAWN)    → 下线
```

> **关键坑**：审批未通过的创意即使挂进 LineItem 也不会产生投放，而排列时 pacing = 0 却找不到原因，很可能就是**审批卡住**。媒体购买团队应当在"排期前"就完成创意审批，否则双11 爆发当天才开始传素材会直接错过高峰期。

Go 实现"确保创意已审批再挂载"的守卫函数：

```go
package mediabuying

import (
	"errors"
	"time"
)

type CreativeStatus = string

const (
	CreativePending CreativeStatus = "PENDING_APPROVAL"
	CreativeApproved CreativeStatus = "APPROVED"
	CreativeRejected CreativeStatus = "REJECTED"
)

// AttachApprovedCreative 确保创意审批通过后才挂到 LineItem。
// getStatus 对应 dv360_get_creative_approval / get_creative。
func AttachApprovedCreative(
	getStatus func(creativeID string) (CreativeStatus, error),
	attach   func(lineItemID, creativeID string) error,
	lineItemID, creativeID string,
	timeout time.Duration,
) error {
	deadline := time.Now().Add(timeout)
	for {
		st, err := getStatus(creativeID)
		if err != nil {
			return err
		}
		switch st {
		case CreativeApproved:
			return attach(lineItemID, creativeID)
		case CreativeRejected:
			return errors.New("creative rejected, fix and resubmit")
		case CreativePending:
			if time.Now().After(deadline) {
				return errors.New("creative approval timed out")
			}
			time.Sleep(30 * time.Second)
		default:
			return errors.New("unknown creative status: " + st)
		}
	}
}
```

---
### 2.6 出价策略与排期 / 预算的交互

出价（bid）决定"单次竞价你愿意出多少钱"，它和预算、排期、pacing 形成一个联动系统。项目里的 `get_bid_strategy_options()` 给出了官方枚举：

```
CPM  → 按千次展示出价        （固定 CPM / 折算）
CPC  → 按点击出价            （系统按预估 CTR 折算成 CPM 参与竞价）
CPV  → 按视频观看出价        （只有完成观看才计费）
OCPM → 优化千次展示（目标 CPM，系统调整） 
CPA  → 按转化出价            （Target CPA）
```

出价与其它系统要素的联动关系：

| 出价策略 | 谁来定价 | 与排期交互 | 与 pacing 交互 | 适用介质 |
|----------|----------|-----------|----------------|----------|
| FIXED_CPM | 你固定 | 窗口内按固定价竞价 | 钱花得快慢只由库存/量决定 | DISPLAY |
| TARGET_CPM | 系统优化 | 系统在窗口内调价 | 系统协调 pacing 避免超支 | DISPLAY |
| TARGET_CPA | 系统按转化 | 依托 floodlight 转化数据 | 系统控制花费速度 | DISPLAY/VIDEO |
| MAX_CPC | 系统按点击 | 折算 CPM | 系统控制 | DISPLAY |
| CPV | 你/系统 | 视频观看计费 | 观看为分母 | VIDEO |

**出价与排期的关键交互**：出价过高 → 预算快速消耗 → pacing 提前触顶 → 后续窗口没预算停投；出价过低 → 抢不到量 → pacing 长期 <100% → 少投。所以 **出价是 pacing 失衡的核心杠杆**：`pacing_rate < 80%` 优先提价（在预算允许内），`>120%` 则降价或改为 EVEN。

Go 写一个"根据 pacing 自动微调出价"的闭环控制器（生产里就是这类组件在双11凌晨自动放量）：

```go
package mediabuying

import (
	"log"
	"math"
)

// BidTuner 依据 pacing rate 与目标窗口预算，平滑调整固定 CPM。
type BidTuner struct {
	MaxCPMMicros int64 // 出价上限（安全阀，防超支）
	MinCPMMicros int64 // 出价下限
}

// NextBid 输入当前 pacing 与当前 CPM，输出建议的新 CPM（micros）。
// 原则：少投提价（乘 1.1），超买降价（乘 0.9），并钳制在上下限。
func (t *BidTuner) NextBid(pacing float64, currentCPMMicros int64) int64 {
	var next float64
	switch {
	case pacing < 0.8:
		next = float64(currentCPMMicros) * 1.1
	case pacing > 1.2:
		next = float64(currentCPMMicros) * 0.9
	default:
		return currentCPMMicros
	}
	next = math.Min(next, float64(t.MaxCPMMicros))
	next = math.Max(next, float64(t.MinCPMMicros))
	log.Printf("bid tuning: pacing=%.2f cpm=%d -> %d", pacing, currentCPMMicros, int64(next))
	return int64(next)
}
```

> 自动调价的**安全护栏**：务必设 `MaxCPMMicros`，并且只在开窗前几小时生效；双11爆发当天若出价失控，"少投→疯狂提价→预算瞬间烧光"是经典事故链。更稳妥的是**半自动**：调价指令生成后推送人工确认（或只在大促窗口内授权自动放量）。

### 2.7 源码级 Python 客户端封装解析

理解了业务语义后，我们把项目里的三层 Python 客户端串起来，读者可据此形成自己的统一入口。项目里实际存在三套，各有定位：

| 脚本 | 类/函数 | 定位 | 关键能力 |
|------|---------|------|----------|
| `dv360_client.py` | `DV360Client` | 最底层 HTTP 客户端 | JWT→AccessToken（`refresh_access_token`）、`list_partners`、`list_advertisers`、`list_campaigns`、`list_line_items` |
| `dv360_api.py` | `DV360Client(BaseAdPlatformClient)` | 领域封装 | `list_insertion_orders`、`create_insertion_order`、`list_line_items`、`create_line_item`、`list_creatives`、`create_creative`、`get_report`、`get_transaction_type_options`、`get_bid_strategy_options`、`get_creative_format_options`、`get_targeting_dimension_options` |
| `ad_platform_api.py` | `dv360_*` 系列 | 统一广告平台门面 | 45+ 方法覆盖 IO/LineItem/Flight/Creative/预算/报表/提案/创意模板等 |

#### 2.7.1 `dv360_client.py` 的 JWT 认证抖动机理

最底层的 `refresh_access_token()` 描述了 DV360 的 OAuth2 Service Account 流程，值得逐段注释：

```python
# 摘自 dv360_client.py 的核心逻辑（注释补充）：
def refresh_access_token(self) -> bool:
    # 1) 缓存命中：token 未过期（提前 60s 刷新）直接复用
    if self.access_token and time.time() < self.token_expiry - 60:
        return True
    sa_key = self._load_service_account()

    # 2) 生成 JWT：iss/sub 都是 service account email，aud 是 token 端点
    payload = {
        "iss": sa_key['client_email'],
        "sub": sa_key['client_email'],   # 这里 sub=iss，即自委托
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,               # JWT 有效期 1 小时
        "scope": " ".join(self.config.get('scopes', [])),
    }
    jwt_token = pyjwt.encode(payload, sa_key['private_key'], algorithm='RS256')

    # 3) 用 JWT bearer grant 换取 access token
    data = {'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': jwt_token}
    result = requests.post(TOKEN_URL, data=data, timeout=30).json()
    return 'access_token' in result
```

**要点**：
- DV360 的 API 版本是 `v4`，base URL 是 `https://display-video.googleapis.com/v4`（`dv360_api.py`）与 `.../v4`（`dv360_client.py`）。
- 客户端都要把 service account **在 DV360 Partner 后台授权**并绑定到 partner，否则 `401`/`403`——这是"无法定位 account"高频根因。

#### 2.7.2 `ad_platform_api.py` 的统一门面如何路由

`ad_platform_api.py` 通过 `self.get_client('dv360')` 拿到 DV360 discovery 服务，然后按 Google API discovery 风格调用 `service.users().me().insertionOrders().list(...)` 等。作者把这层进一步收紧为语义化门面：

```python
class DV360MediaBuyingFacade:
    """媒体购买统一门面：聚合 45+ 方法为 8 个业务动作。"""

    def __init__(self, platform):
        self.p = platform  # 传入 ad_platform_api 实例

    # ---------------- IO ----------------
    def list_io(self, advertiser_id):
        return self.p.dv360_list_insertion_orders(advertiser_id)

    def io_flexibility(self, io_id):
        return self.p.dv360_list_insertion_order_flexibility(io_id)

    # ---------------- LineItem ----------------
    def list_line_items(self, advertiser_id):
        return self.p.dv360_list_line_items(advertiser_id)

    def create_line_item(self, advertiser_id, name, **kw):
        return self.p.dv360_create_line_item(advertiser_id, name, **kw)

    def get_pacing_rate(self, advertiser_id, line_item_id):
        return self.p.dv360_get_pacing_rate(advertiser_id, line_item_id)

    def batch_update(self, updates):
        return self.p.dv360_batch_update_line_items(updates)

    # ---------------- Flight / 预算 ----------------
    def list_flights(self, advertiser_id, line_item_id):
        return self.p.dv360_list_flights(advertiser_id, line_item_id)

    def list_budget_allocations(self, advertiser_id):
        return self.p.dv360_list_budget_allocations(advertiser_id)

    # ---------------- 创意 ----------------
    def list_creatives(self, advertiser_id, line_item_id=None):
        return self.p.dv360_list_creatives(advertiser_id, line_item_id)

    # ---------------- 报表 ----------------
    def report(self, advertiser_id, **kw):
        return self.p.dv360_get_report(advertiser_id, **kw)
```

#### 2.7.3 一次完整的"建 IO → 建 LineItem → 挂创意 → 出票/报表"流水

```python
def full_media_buying_flow(platform, advertiser_id, io_spec, li_specs, creative_ids):
    """演示媒体购买从下单到报表的完整闭环。"""
    facade = DV360MediaBuyingFacade(platform)

    # 1) 建 IO（合同层）
    io = platform.dv360_create_insertion_order(advertiser_id, io_spec)  # 见 dv360_api
        
    # 2) 批量建 LineItem（竞价层）
    created_lis = []
    for sp in li_specs:
        li = facade.create_line_item(advertiser_id, sp["name"], **sp["body"])
        created_lis.append(li["lineItemId"])

    # 3) 挂创意（审批通过后）
    for li_id in created_lis:
        facade.p(advertiser_id, li_id, **{"creativeIds": creative_ids})  # update

    # 4) 报表
    report = facade.report(advertiser_id, date_range={"start": "2026-11-01", "end": "2026-11-15"})
    return {"io": io, "lineItems": created_lis, "report": report}
```

> 上面 `dv360_create_insertion_order` 与 `create_insertion_order` 是同一方法的两种命名（`dv360_api.py` 里叫 `create_insertion_order`，`ad_platform_api.py` 里叫 `dv360_list_insertion_orders` 等前缀统一为 `dv360_`）。引用时以各自脚本为准。

---
## 三、生产环境实战

### 3.1 案例一：双11 大促媒体购买配置

双11 是媒体购买工作量和风险最高的场景，也是检验"分层预算 + flight 拆段 + pacing 联动"的最佳试验场。下面是一个**完整可落地**的配置演进，从预算盘子到逐日放量。

#### 3.1.1 业务需求

- 总预算 200 万元人民币，投放期 2026-11-01 ~ 2026-11-15（15 天）。
- 三段：预热(1~9日) / 爆发(10~11日) / 返场(12~15日)。
- 地域：华东（上海、杭州、南京）。
- KPI：预热期关注点击与蓄水，爆发期追求量（ASAP），返场期做再营销。

#### 3.1.2 预算与 flight 规划表

| 阶段 | 日期 | 占比 | 金额(万元) | 建议 pacing | 重点定向 |
|------|------|------|-----------|--------------|----------|
| 预热 | 11-01~11-09 | 25% | 50 | EVEN | 宽受众 + 兴趣蓄水 |
| 爆发 | 11-10~11-11 | 50% | 100 | ASAP | 全量 + 再营销叠加 |
| 返场 | 11-12~11-15 | 25% | 50 | EVEN | 高意向再营销 |

#### 3.1.3 落地代码：一个 IO + 三个 LineItem（每个一个 flight）

```python
# -*- coding: utf-8 -*-
from mediabuying_lineitem import LineItemBuilder  # 复用 2.2.3 的封装

ADVERTISER = "123456789"
CURRENCY = "CNY"

def configure_double11(platform):
    # ---- IO：总盘子 200 万，整体窗口 11-01 ~ 11-15，EVEN 打底 ----
    io_body = {
        "name": "双11-2026-品牌全量-200W",
        "advertiserId": ADVERTISER,
        "entityStatus": "ENTITY_STATUS_ACTIVE",
        "budget": {
            "budgetUnit": "BUDGET_UNIT_CURRENCY",
            "maxAmountMicros": 2_000_000_000_000,   # 200 万元
            "currencyCode": CURRENCY,
            "pacingType": "PACING_MODE_EVEN",
        },
        "schedule": {
            "startDate": {"year": 2026, "month": 11, "day": 1},
            "endDate":   {"year": 2026, "month": 11, "day": 15},
        },
    }
    # io = platform.create_insertion_order(ADVERTISER, io_body)

    builder = LineItemBuilder(platform)
    # ---- 三个 LineItem（分段），各自一个 flight ----
    segments = [
        # (name, type, start, end, budget_micros, pacing, cpm_micros)
        ("双11-预热-展示-华东-50W", "display",
         {"year":2026,"month":11,"day":1},  {"year":2026,"month":11,"day":9},
         50_000_000_000_000, "PACING_MODE_EVEN", 12_000_000),
        ("双11-爆发-展示-华东-100W", "display",
         {"year":2026,"month":11,"day":10}, {"year":2026,"month":11,"day":11},
         100_000_000_000_000, "PACING_MODE_ASAP", 15_000_000),
        ("双11-返场-展示-华东-50W", "display",
         {"year":2026,"month":11,"day":12}, {"year":2026,"month":11,"day":15},
         50_000_000_000_000, "PACING_MODE_EVEN", 13_000_000),
    ]
    line_items = []
    for name, lt, s, e, budget_micros, pacing, cpm in segments:
        body = builder.build_line_item(
            ADVERTISER, io_body_id_to_use(), name, lt, CURRENCY,
            budget_micros, cpm, pacing=pacing, start=s, end=e,
        )
        # 创建（此处省略真实调用；生产中记得先创建 IO 拿到 io_id）
        line_items.append(body)
    return {"io": io_body, "lineItems": line_items}

def io_body_id_to_use():
    """占位：实际代码应返回上一步创建 IO 后返回的 insertionOrderId。"""
    return "111222333"
```

> **注意预算数值的单位换算**：DV360 的 `maxAmountMicros` 是**微单位**。人民币 1 元 = 1_000_000 micros，所以 50 万元 = `50 * 10000 * 1000000 = 500,000,000,000`（5e11）micros。写错一位小数就是预算差 10 倍，这是大促踩坑重灾区（见 3.4）。

#### 3.1.4 双11 当日运维：放量看板口径

大促当天建议按小时盯这几个指标，多数来自 `dv360_get_pacing_rate` 与报表：

| 时刻 | 看什么 | 动作 |
|------|--------|------|
| 10:00 | 爆发段 pacing 是否 >60% | 低于则提价 / 放开定向 |
| 14:00 | 是否提前烧完今日预算 | 若是则后续返场段要补量 |
| 18:00 | 超支风险（>1.2 倍） | 转向 EVEN / 降出价 |
| 23:30 | 总花费 vs 200万 | 盘点是否兜得住 |

### 3.2 案例二：多市场预算拆分

一个跨国品牌（北美 + 欧洲 + 亚太）会有多个 advertiser（或同一 advertiser 下多 IO），且**每个市场用不同货币**。媒体购买框架必须处理"货币一致性"。

```
Partner
├── Advertiser: 北美   currency=USD  IO: US-Q4
├── Advertiser: 欧洲   currency=EUR  IO: EU-Q4
└── Advertiser: 亚太   currency=CNY  IO: CN-Q4
```

**设计原则**：
1. **每个 market 一个 advertiser**，各自设置 `currencyCode`——不同货币实体不能混在同一个 advertiser 下做预算分配。
2. 各 market 的 IO 预算用其本地货币（`dv360_list_currency_options` 可查平台支持的币种）。
3. 总部做"折合 mega 预算"时，汇率换算放在**报表层**（拿到各 market 花费后转成基准币），不要在 API 层混币。

```python
def cross_market_budget_split(platform, market_plans):
    """market_plans: [{market, advertiser_id, currency, budget_local}]"""
    # 校验：不同 market 必须不同 advertiser（货币隔离）
    for m in market_plans:
        assert m["currency"], f"{m['market']} must set currency"
    # 为每个 market 创建 IO（本地货币预算）
    results = []
    for m in market_plans:
        micros = int(m["budget_local"] * 1_000_000)
        io = {
            "name": f"{m['market']}-Q4",
            "advertiserId": m["advertiser_id"],
            "entityStatus": "ENTITY_STATUS_ACTIVE",
            "budget": {
                "budgetUnit": "BUDGET_UNIT_CURRENCY",
                "maxAmountMicros": micros,
                "currencyCode": m["currency"],
                "pacingType": "PACING_MODE_EVEN",
            },
        }
        results.append(platform.create_insertion_order(m["advertiser_id"], io))
    return results
```

> **货币匹配坑**：若 advertiser 的 currency 是 CNY，而你在 LineItem 里传 `currencyCode=USD`，DV360 会报 currency 不匹配错误。**预算/金额的 currency 必须与 advertiser 一致**，跨市场报表换算放到下游。

### 3.3 案例三：按日预算 / 总预算规划

DV360 不直接支持"按日预算"字段（相对某些平台），而是靠 **IO 总预算 + pacing 模式** 来表达日均意图：

```
每日预算 ≈ IO 总预算 / 排期天数   （EVEN 模式）
```

所以"我想日均 1 万元投 10 天"的落地方式是：IO 总预算 = 10 万，EVEN pacing，窗口 10 天。若要**变每日**，两种方案：
- 改 IO 总预算（简单，但会影响整体窗口均摊）；
- 用 **flight 拆段**：给不同日期段设不同预算（复杂，但精准）。

```python
def daily_budget_to_io(total_days: int, daily_budget_local: float) -> dict:
    """把"日均预算 * 天数"翻译成 IO 总预算 + EVEN pacing。"""
    total = daily_budget_local * total_days
    return {
        "pacingType": "PACING_MODE_EVEN",
        "maxAmountMicros": int(total * 1_000_000),
        "totalDays": total_days,
        "impliedDailyLocal": daily_budget_local,
    }
```

### 3.4 常见踩坑与经验（重点）

这一节是多年媒体购买运维的浓缩。每个坑都直接对应一个 API 表象，并按"现象 → 根因 → 解法"展开。

#### 坑 1：预算超支（Over-Spend）

| 现象 | 根因 | 解法 |
|------|------|------|
| 实际花费 > IO 预算 | pacing=ASAP + 出价高 + 库存暴涨 | 设安全上限、关键时刻转 EVEN、加 Customer 层级预算限额 |
| 报表花费 > LineItem 预算 | 归因时点 / 结算延迟 | 引入 1~2 天结算宽限，不按当日硬核对 |
| 大促凌晨预算瞬间烧光 | 自动提价无护栏 | 强制 MaxCPPMicros + 半自动放量 |

> 核心认知：DV360 的预算是一个 **pacing 软约束 + 计费硬核销** 的系统，实时花费可能有瞬时会超过理想水位（尤其 ASAP），但会在窗口内被系统纠偏。**监控超出量阈值告警**，不要指望实时精确。

#### 坑 2：Pacing 过慢 / 少投（Under-Spend / Slow Pacing）

| 现象 | 根因 | 解法 |
|------|------|------|
| pacing_rate 长期 <80% | 出价过低，抢不到量 | 提价 |
| pacing=0 但 ACTIVE | 创意审批未过 / 无匹配库存 / IO 已暂停 | 逐层查：审批→定向→IO 状态 |
| 库存太少 | PMP / PG deal 量小 | 换/增 Open Auction，或扩定向 |
| 定向过窄 | 受众太小 | 放宽定向 / 追加相似受众 |

#### 坑 3：时区差导致少投一天（Timezone）

DV360 的日期与报表默认按 **Partner 或 Advertiser 配置的时区** 记账。如果你的业务时区（如北京时间 UTC+8）与配置的时区（如美国太平洋时间 UTC-8）不同，会出现：

```
北京时间 11-11 00:00 大促开始
  └─ DV360 仍按太平洋时间 11-10 记账 → 使得"大促首日"实际只投了半天
```

| 解法 | 说明 |
|------|------|
| 一开始就把 advertiser 时区设为业务主导时区 | 最彻底，避免后续换算错误 |
| 开窗前核对 schedule 的"折算后"本地日期 | 用 `to_iso()` 工具校验 |
| 报表加时间偏移 | 只在无法改动时兜底 |

#### 坑 4：Currency 不匹配（Currency Mismatch）

| 现象 | 根因 | 解法 |
|------|------|------|
| 创建 LineItem 报 currency 错 | LineItem 币种 ≠ advertiser 币种 | 统一用 advertiser.currencyCode |
| 跨市场预算分配报错 | 把不同币种实体放同一预算分配 | 每个 market 独立 advertiser |
| 报表金额对不上财务 | 报表币种 vs 结算币种不同 | 报表层固定基准币换算 |

#### 坑 5：排期冲突 / 衔接断层

| 现象 | 根因 | 解法 |
|------|------|------|
| flight A 结束到 B 开始有空窗（断投） | 相邻 flight 日期留缝 | 检查相邻 end→start 无缝 |
| flight 重叠双份计费 | 相邻 flight 日期重叠 | 统一用一个 Date 边界规范 |
| 返场排期想延长但 IO end 已到 | 不可 resume "过去" 的 IO | 先扩 IO end，再扩 flight |

### 3.5 生产落地检查清单（Checklist）

媒体购买上线前过一遍，能省掉 80% 的救火：

- [ ] Advertiser 时区已按业务主导时区设置
- [ ] Advertiser 币种与所有金额一致
- [ ] IO 总预算 = 所有 LineItem 预算 + 安全余量
- [ ] 各 LineItem 币种 = advertiser 币种
- [ ] Creative 已审批通过（APPROVED）再挂载
- [ ] flight 相邻无空窗、无重叠
- [ ] 大促段 pacing=ASAP 已配出价安全上限
- [ ] 报表口径（币种、时区、结算延迟）与财务对齐
- [ ] 批量创建走指数退避，避免 429
- [ ] pacing 监控已接告警（<80% 少投 / >120% 超支）

---
## 四、常见问题与排查

### 4.1 FAQ 速查表

| # | 问题 | 一句话答案 | 排查入口 / 相关 API |
|---|------|-----------|---------------------|
| 1 | 调用 API 报 "无法定位 account / advertiser" | 多为 service account 未在 Partner 后台授权，或 partner_id 错误 | `dv360_auth` / `dv360_validate_credentials` / `list_partners` |
| 2 | IO 状态不对（ACTIVE 了但什么都不投） | 逐层查 LineItem 状态、creative 审批、定向、IO 预算是否够 | `dv360_list_line_items` / `dv360_list_creatives` / `dv360_get_pacing_rate` |
| 3 | pacing 一直没命中（=0） | 大概率是创意审批未过或无匹配库存 | `AttachApprovedCreative` 守卫 + 审批状态查询 |
| 4 | 预算分配失败 | IO/LineItem 币种不一致，或父级预算不够 | `dv360_list_budget_allocations` / `dv360_list_currency_options` |
| 5 | 为什么按日预算不生效 | DV360 没有独立"按日预算"字段，用总预算+EVEN 表达 | 见 3.3 |
| 6 | 跨市场预算对不上 | 多币种混在报表里 | 每个 market 独立 advertiser |
| 7 | 大促凌晨预算烧光 | 自动提价无护栏 / ASAP | 设 MaxCPM + 半自动放量 |
| 8 | 排期结束无法重新开启 | "过去"态只读，先扩 IO end | 见 2.1 |
| 9 | 报表与财务金额对不上 | 币种 / 时区 / 结算延迟 | 报表层统一口径 |
| 10 | 批量创建报 429 / quota | 并发过高 | 串行 + 指数退避 |

### 4.2 深度排查：从 "0 投放" 到定位根因

当媒体采购上线后**完全不消耗预算**（spend=0 / pacing=0 / 有 impression 但极少），按下面的决策树逐层排查。这是运维最常用的一张图：

```
LineItem 零投放排查决策树
│
├─ 步骤1：IO 状态正常吗？
│     io = dv360_list_insertion_orders(advertiser_id)
│     ├─ 非 ACTIVE/PAUSED？ → 先 resume IO（若未过期）
│     └─ IO 预算耗尽？      → 扩大 IO maxAmountMicros
│
├─ 步骤2：LineItem 状态与排期在窗口内吗？
│     li = dv360_get_line_item(advertiser_id, line_item_id)
│     ├─ 现在时间在 flight 窗口内吗？ 否 → 改排期
│     └─ entityStatus=PAUSED？       是 → dv360_resume_line_item
│
├─ 步骤3：创意审批通过了吗？
│     cr = dv360_list_creatives(advertiser_id, line_item_id)
│     ├─ 任一创意 REJECTED / PENDING？ → 修复重提，等 APPROVED
│     └─ 没挂 creativeIds？            → 挂上审批过的创意
│
├─ 步骤4：定向是否有可匹配量？
│     ├─ 定向过窄（单城市+小众受众）→ 放宽
│     └─ deal（PMP/PG）库存是否足够 → 增补 Open Auction
│
└─ 步骤5：出价是否低于市场？
      pacing = dv360_get_pacing_rate(advertiser_id, line_item_id)
      ├─ pacing < 80% 仍没量 → 提价到合理区间
      └─ 仍 0 → 查看 InventorySource 是否有效 / 是否被 brand-safety 过滤
```

### 4.3 排查：pacing 异常时怎么读数值

`dv360_get_pacing_rate` 返回的内容里要分清三个数：

| 数值 | 含义 | 健康范围 |
|------|------|----------|
| `expectedSpendMicros` | 按时间进度"应有"的花费 | —— |
| `actualSpendMicros` | 实际已花费 | ≈ expected 最优 |
| 派生 pacing_rate | actual / expected | 0.9 ~ 1.1 理想 |

> 读数值时不要只看"今天花费"，要**除以应花的比例**。例如窗口过一半、才花 20%，即使绝对值不小也是少投——必须用 pacing_rate 的视角。

### 4.4 排查表：常见报错 → 根因 → 修复

| 报错/现象 | 根因 | 修复动作 | 涉及 API |
|-----------|------|----------|----------|
| `quota exceeded` (429) | 并发/配额超限 | 串行、指数退避、分批 | 所有写操作 |
| `permission denied` (403) | service account 无权限/未授权 Partner | 后台授权并绑定 partner | `dv360_auth` |
| `not found` (404) | 父级 ID 错误或实体已被删 | 核对 advertiser/io/lineItem 真实 ID | `dv360_list_*` |
| `invalid currency` | LineItem 币种 ≠ advertiser | 统一币种 | `dv360_list_currency_options` |
| `flight not in window` | 当前时间不在 flight 内 | 调整排期或等待 | `dv360_list_flights` |
| `creative not approved` | 审批未通过 | 修复重提、等 APPROVED | `dv360_list_creatives` |
| 全量提交后字段被清空 | 忘了 read-modify-write | 先 GET 再合并再 PUT | `dv360_get_line_item` |
| `end date in the past` | 尝试 resume 已过去 IO/LineItem | 先扩 end 再 resume | 见 2.1 |
| spend=0 且 pacing=0 | 见 4.2 决策树 | 逐层判断 | 见 4.2 |

### 4.5 运维巡检脚本模板

把巡检做成可复用 Python 脚本，上线后每天/每小时跑一遍（生产常用模式）：

```python
# -*- coding: utf-8 -*-
"""媒体购买每日巡检：扫 IO/LineItem 状态 + pacing + 创意审批。"""

def daily_audit(platform, advertiser_id):
    findings = []

    # 1) IO 层面
    for io in platform.dv360_list_insertion_orders(advertiser_id):
        if io.get("entityStatus") == "ENTITY_STATUS_PAUSED":
            findings.append(("WARN", f"IO {io['name']} 处于 PAUSED"))

    # 2) LineItem 层面：pacing + 状态
    for li in platform.dv360_list_line_items(advertiser_id):
        li_id = li.get("lineItemId")
        if li.get("entityStatus") == "ENTITY_STATUS_PAUSED":
            findings.append(("INFO", f"LineItem {li['name']} 手动 PAUSED，跳过"))
            continue
        pacing = platform.dv360_get_pacing_rate(advertiser_id, li_id)
        rate = pacing.get("pacingRate", 1.0)
        if rate < 0.8:
            findings.append(("ALERT", f"LineItem {li['name']} 少投 pacing={rate:.2f}"))
        elif rate > 1.2:
            findings.append(("ALERT", f"LineItem {li['name']} 可能超支 pacing={rate:.2f}"))

    # 3) 创意审批
    for cr in platform.dv360_list_creatives(advertiser_id):
        if cr.get("entityStatus") in ("PENDING", "REJECTED"):
            findings.append(("WARN", f"创意 {cr.get('name')} 未审批通过"))

    return findings
```

---
## 五、自测题

### 问题 1：IO、LineItem、Flight 三者各自的职责边界是什么？为什么 "给 IO 加了预算但整体还是放不出来" 是经典事故？

<details>
<summary>查看答案</summary>

**职责边界**：
- IO = 合同层：总预算 + 整体排期 + 频率上限，不竞价。
- LineItem = 竞价层：出价、定向、flight、预算上限，真正进拍卖。
- Flight = 时间段与段预算，LineItem 内部切段。

**「IO 加了钱但放不出来」** 的根因通常是：只把 LineItem 预算调大，却忘了 **IO 总预算（maxAmountMicros）仍然是硬顶**。预算链是"IO 顶 → LineItem 顶 → flight 顶"，任何一个更上游的顶没放开，下游加钱都无效。排查顺序：先看 IO `maxAmountMicros` 是否含余量，再看 LineItem 预算，最后看 flight。这也是文档 1.5 强调三层预算的原因。
</details>

### 问题 2：`PAUSED` 与 "排期已过（Past）" 的 IO 在语义上有什么区别？对恢复操作有什么影响？

<details>
<summary>查看答案</summary>

- `PAUSED`：人工/系统暂停，**逻辑状态**，排期窗口未走完；可以随时 resume 回 ACTIVE 继续消耗预算，已产生花费不回滚，窗口继续计时。
- `Past`：排期 end 时间点已过，系统判定该 IO 时间上"结束"了，是**只读终态**；试图 resume 会被拒绝/忽略，必须**先把 end 日期推到未来**（扩窗口）再恢复。

所以正确的"返场加时"操作顺序是：**先扩 IO 的 endDate（且不要超过 Partner 允许的最晚日期）→ 再扩/建 flight → 再 resume**。反过来先 resume 则会报错（end date in the past）。
</details>

### 问题 3：`dv360_get_pacing_rate` 返回 pacing_rate=0.6，意味着什么？你会做哪些动作？

<details>
<summary>查看答案</summary>

pacing_rate = actual / expected（按时间进度应花的比例）。0.6 表示**只花到应有水平的 60%，严重少投**。动作按优先级：

1. 先排除"假零"要素：创意审批（REJECTED/PENDING）→ 无库存 → 定向过窄。
2. 若上述都正常，说明**竞价量不足**：提价（在预算允许内）、把 PACING_MODE_EVEN 切到 ASAP（若预算允许）、放开 over-narrow 定向、增补 Open Auction 库存。
3. 最后看 IO 预算与 LineItem 预算是否仍有余量。

注意：**不要在少投时无限提价**，要有 MaxCPM 护栏，否则一旦库存回流会瞬间超支（见 3.4 坑1）。
</details>

### 问题 4：为什么说 DV360 的 create 是"全量 upsert"语义？安全更新的标准姿势是什么？

<details>
<summary>查看答案</summary>

DV360 的 create/update 对 IO 和 LineItem 是**全量提交**：你提交的 dict 被视为完整期望状态，漏传字段会被重置为默认/清空，而不是保留原值。这正是"我只改了一个字段，结果别的字段丢了"事故的根因。

标准姿势是 **read-modify-write**：

1. GET 当前实体（如 `dv360_get_line_item`）；
2. 在返回 dict 上修改目标字段；
3. 把**完整 dict** PUT 回去（`dv360_update_line_item` / `dv360_create_line_item`）。

并发场景再加版本控制/乐观锁（见问题 5）。Go 里对应 `UpdateInsertionOrderStatus` 的 get→modify→put 模式（见 2.1.3）。
</details>

### 问题 5：双11 爆发段出价过高 + pacing=ASAP 会发生什么？如何设计防护？

<details>
<summary>查看答案</summary>

- **现象**：ASAP 模式下预算追求"尽快花完"，出价高意味着赢率高、单位花费快；流量高峰（晚上 8-11 点）可能**几小时内把 100 万预算烧完**，随后全天弹尽粮绝，返场段也被影响（若共 IO 预算）。
- **设计防护**：
  1. 出价设 `MaxCPMMicros` 硬上限（BidTuner 的护栏）；
  2. 大促自动放量做成**半自动**：生成调价指令推送人工确认，或仅在大促窗口内授权；
  3. 预算按 flight 拆段，段与段之间**隔离**（即使爆发段烧完，返场段独立预算不受连累）；
  4. 监控 pacing>1.2 立即告警并降为 EVEN。

这就是把"计划（flight 拆段）"与"执行（pacing/出价护栏）"结合起来控制风险的完整策略。
</details>

---
