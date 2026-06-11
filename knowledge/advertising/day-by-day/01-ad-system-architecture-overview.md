# 广告系统全景架构：从 SSP 到 DSP 到 RTB

> 创建日期: 2026-06-10
> 作者: Ryan
> 定位: 资深专家级 — 广告系统核心架构

---

## 第一部分：程序化广告发展史

### 1.1 广告交易方式的演进

```
广告交易经历了四个主要阶段：

Stage 1: 传统直接交易 (1994-2005)
────────────────────────────────────────
├─ 方式: 广告主直接与 Publisher 交易
├─ 形式: 固定位广告 (Banner/Full Page)
├─ 特点:
│   ├── 提前预订，固定位置
│   ├── CPM 固定价格
│   ├── 无法精准定向
│   └─ 效率低下，大量库存浪费
├─ 缺点:
│   ├── 价格不透明
│   ├── 中小 Publisher 库存难卖
│   └─ 广告主无法精准触达目标人群

Stage 2: 程序化直接购买 (2005-2010)
────────────────────────────────────────
├─ 方式: Guaranteed Inventory + PMP (Private Marketplace)
├─ 技术: 引入 Head Exchange (OpenX/AppNexus)
├─ 特点:
│   ├── 仍保证展示量 (Guaranteed)
│   ├── PMP 私密拍卖
│   └─ Price Floor 保护 Publisher
├─ 进步:
│   ├── 价格更透明
│   ├── 支持 Targeting
│   └─ 中小 Publisher 开始受益

Stage 3: Real-Time Bidding (2010-2018)
────────────────────────────────────────
├─ 方式: Open Marketplace + RTB
├─ 技术: IAB OpenRTB 标准
├─ 特点:
│   ├── 每次展示实时竞价
│   ├── 毫秒级竞价 (<100ms)
│   ├── 精准定向 (Data-driven)
│   └─ 库存利用率最大化
├─ 参与者:
│   ├── DSP (Demand Side Platform)
│   ├── SSP (Supply Side Platform)
│   ├── Ad Exchange (AdX)
│   └─ DMP (Data Management Platform)
├─ 里程碑:
│   ├── 2010: AdX 与 AdSense 整合
│   ├── 2012: 展示广告 50% 程序化
│   └─ 2015: 程序化超过传统购买

Stage 4: AI-Driven Programmatic (2018-Present)
────────────────────────────────────────
├─ 方式: ML-Powered + Privacy-First
├─ 技术: Deep Learning + On-Device Processing
├─ 特点:
│   ├── 自动出价 (Smart Bidding)
│   ├── 自动创意 (Dynamic Creative)
│   ├── 预测性定向 (Predictive Targeting)
│   └─ 隐私保护 (Cookieless/On-Device)
├─ 关键趋势:
│   ├── Privacy Sandbox (Google)
│   ├── SKAdNetwork (Apple)
│   ├── Clean Rooms (Shared Data)
│   └─ First-Party Data 重要性上升
```

### 1.2 关键术语速查表

```
┌──────────────────────┬──────────────────────────────────────────┐
│ 术语                 │ 定义                                     │
├──────────────────────┼──────────────────────────────────────────┤
│ DSP                  │ Demand Side Platform (需求方平台)         │
│ SSP                  │ Supply Side Platform (供给方平台)         │
│ Ad Exchange          │ 广告交易平台                               │
│ DMP                  │ Data Management Platform (数据管理平台)    │
│ CDP                  │ Customer Data Platform (客户数据平台)      │
│ PMP                  │ Private Marketplace (私密市场)             │
│ PMP                  │ Preferred Deal (优先交易)                  │
│ RTB                  │ Real-Time Bidding (实时竞价)               │
│ GDN                  │ Google Display Network (展示网络)          │
│ PDB                  │ Programmatic Direct (程序化直接购买)       │
│ Open Auction         │ 公开竞价                                   │
│ CPM                  │ Cost Per Mille (千次展示费用)              │
│ CPC                  │ Cost Per Click (单次点击费用)              │
│ CPA/CPI              │ Cost Per Action/Install                   │
│ ROAS                 │ Return on Ad Spend (广告回报率)            │
│ Fill Rate            │ 填充率 (成功展示的库存比例)                │
│ eCPM                 │ effective CPM (每次展示有效收入)            │
│ Win Back Rate        │ 中标回传率                                │
│ Latency              │ 竞价延迟 (ms)                              │
└──────────────────────┴──────────────────────────────────────────┘
```

---

## 第二部分：核心参与者深度解析

### 2.1 SSP (Supply Side Platform)

```
SSP 是 Publisher (内容发布者) 侧的平台，帮助管理广告库存:

┌──────────────────────────────────────────────────────────────┐
│                  SSP 架构                                     │
│                                                              │
│  Publisher (发布商)                                           │
│  └─ 网站/APP 拥有广告位                                        │
│     ├── 网站: 博客/新闻/电商/门户                               │
│     └─ APP: 游戏/工具/社交/视频                                │
│                                                              │
│  SSP (供给方平台)                                             │
│  ├── 管理广告库存 (Inventory Management)                       │
│  │   ├── 定义库存规格 (Ad Size/Format)                        │
│  │   ├── 设置底价 (Price Floor/Reserve Price)                 │
│  │   ├── 库存分类 (Segmentation)                              │
│  │   └─ 频次控制 (Frequency Capping)                          │
│  ├── 竞价管理 (Bidding Management)                             │
│  │   ├── 请求多个 DSP (Bid Request)                           │
│  │   ├── 收集竞价 (Bid Responses)                             │
│  │   ├── 执行竞价决策 (Winner Selection)                      │
│  │   └─ 返回中标广告 (Win Notice)                             │
│  ├── 收入优化 (Revenue Optimization)                           │
│  │   ├── Header Bidding (头部竞价)                            │
│  │   ├── Yield Optimization (收益优化)                         │
│  │   └─ Floor Price Optimization (底价优化)                   │
│  └─ 报告与分析 (Reporting & Analytics)                         │
│                                                              │
│  主流 SSP:                                                   │
│  ├── Google Ad Manager ( GAM) — 市场领导者                     │
│  ├── OpenX                                                   │
│  ├── PubMatic                                                │
│  ├── AppNexus (现 Xandr/Microsoft)                           │
│  ├── Magnite                                                 │
│  └─ TruAxis                                                 │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 DSP (Demand Side Platform)

```
DSP 是 Advertiser (广告主) 侧的平台，管理广告投放:

┌──────────────────────────────────────────────────────────────┐
│                  DSP 架构                                     │
│                                                              │
│  Advertiser (广告主)                                          │
│  └─ 品牌/电商/应用开发者                                       │
│                                                              │
│  DSP (需求方平台)                                             │
│  ├── 投放管理 (Campaign Management)                            │
│  │   ├── 创建广告系列                                         │
│  │   ├── 设置预算 (Daily/Lifetime)                            │
│  │   ├── 设置出价 (Bid Strategy)                              │
│  │   └─ 设置定向 (Targeting)                                  │
│  ├── 竞价引擎 (Bid Engine)                                    │
│  │   ├── 接收 Bid Request                                    │
│  │   ├── 计算 pCVR/pCTR (预测转化/点击率)                      │
│  │   ├── 计算 Optimal Bid (最优出价)                           │
│  │   │   └─ Bid = pCTR × pCVR × Target CPA × Beta            │
│  │   ├── 提交竞价 (Bid Response)                              │
│  │   └─ 监控 Win Rate (中标率)                                │
│  ├── 数据引擎 (Data Engine)                                   │
│  │   ├── DMP 集成                                             │
│  │   ├── 人群画像 (Audience Profiling)                         │
│  │   ├── 实时重定向 (Retargeting)                             │
│  │   └─ Lookalike 建模                                       │
│  ├── 创意引擎 (Creative Engine)                                │
│  │   ├── 动态创意优化 (DCO)                                   │
│  │   ├── 创意轮替 (Ad Rotation)                               │
│  │   └─ 创意 A/B 测试                                         │
│  └─ 报告与分析 (Reporting & Analytics)                         │
│                                                              │
│  主流 DSP:                                                   │
│  ├── Google Marketing Platform (GM) — Display/Video          │
│  ├── The Trade Desk                                           │
│  ├── Xandr (Microsoft)                                        │
│  ├── Amazon DSP                                               │
│  ├── DV360 (Display & Video 360)                             │
│  ├── MediaMath                                                │
│  ├── FreeWheel                                                │
│  └─ Criteo                                                   │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 Ad Exchange (Ad Exchange)

```
Ad Exchange 是连接 SSP 和 DSP 的交易平台:

┌──────────────────────────────────────────────────────────────┐
│                  Ad Exchange 架构                             │
│                                                              │
│  Ad Exchange (广告交易平台)                                     │
│  ├── 核心功能:                                                │
│  │   ├── 撮合 SSP 的库存和 DSP 的需求                         │
│  │   ├── 执行 RTB 竞价                                        │
│  │   ├── 确保竞价公平性 (Fairness)                            │
│  │   └─ 处理结算 (Settlement)                                 │
│  ├── 竞价流程:                                                │
│  │   ├── SSP 发送 Bid Request                               │
│  │   ├── Ad Exchange 广播给所有 DSP                           │
│  │   ├── DSP 返回 Bid Response                               │
│  │   ├── Ad Exchange 选择中标者 (Win/Lose)                    │
│  │   └─ Ad Exchange 通知 SSP 中标广告                          │
│  ├── 竞价类型:                                                │
│  │   ├── Open Auction (公开竞价)                               │
│  │   ├── PMP (Private Marketplace)                           │
│  │   ├── PMP + Preferred Deal                                │
│  │   └─ PDB (Programmatic Direct)                             │
│  ├── 收入分成 (Revenue Share):                                │
│  │   ├── Publisher: 50-70%                                    │
│  │   ├── SSP: 10-20%                                        │
│  │   └─ Ad Exchange: 10-15%                                 │
│  └─ 数据流转 (Data Flow):                                    │
│      ├── Bid Request → 用户/页面/库存信息                     │
│      ├── Bid Response → 出价/广告ID                           │
│      └─ Win Notice → 中标广告URL/结算信息                     │
│                                                              │
│  主流 Ad Exchange:                                           │
│  ├── Google AdX (Ad Manager) — 最大                          │
│  ├── Magnite Exchange                                       │
│  ├── OpenX Exchange                                         │
│  ├── PubMatic Exchange                                      │
│  └─ Xandr Exchange                                          │
└──────────────────────────────────────────────────────────────┘
```

### 2.4 DMP (Data Management Platform)

```
DMP 管理用户数据，用于精准定向:

┌──────────────────────────────────────────────────────────────┐
│                  DMP 架构                                     │
│                                                              │
│  DMP (数据管理平台)                                           │
│  ├── 数据收集 (Data Collection):                              │
│  │   ├── First-Party Data (一方数据):                         │
│  │   │   ├── CRM 数据                                           │
│  │   │   ├── 网站行为 (Pixel/SDK)                             │
│  │   │   └─ App 行为 (SDK)                                    │
│  │   ├── Second-Party Data (二方数据):                         │
│  │   │   └─ Partner 共享数据                                   │
│  │   └─ Third-Party Data (三方数据):                           │
│  │       ├── 数据提供商 (LiveRamp/Oracle/Adobe)               │
│  │       └─ Cookie 数据 (正在淘汰)                             │
│  ├── 数据处理 (Data Processing):                              │
│  │   ├── 数据清洗 (Cleaning)                                   │
│  │   ├── 数据标准化 (Standardization)                          │
│  │   ├── 数据关联 (Identity Resolution)                       │
│  │   └─ 数据合并 (Merge)                                      │
│  ├── 受众构建 (Audience Building):                            │
│  │   ├── 人群细分 (Segmentation)                               │
│  │   ├── Lookalike 建模                                       │
│  │   └─ 受众列表 (Audience Lists)                             │
│  ├── 数据分发 (Data Activation):                              │
│  │   ├── 发送到 DSP (用于定向)                                 │
│  │   ├── 发送到 SSP (用于出价)                                 │
│  │   └─ 发送到 Ad Exchange (用于竞价)                          │
│  └─ 合规 (Compliance):                                       │
│      ├── GDPR (欧洲)                                           │
│      ├── CCPA (加州)                                           │
│      └─ TCF (Transparency & Consent Framework)               │
│                                                              │
│  主流 DMP:                                                   │
│  ├── Google Campaign Manager 360                             │
│  ├── Adobe Audience Manager                                   │
│  ├── Oracle BlueKai                                          │
│  ├── LiveRamp                                                │
│  └─ ZEDO                                                      │
└──────────────────────────────────────────────────────────────┘
```

---

## 第三部分：RTB 实时竞价流程

### 3.1 完整竞价时间线

```
一次 RTB 竞价的标准流程 (总延迟 < 100ms):

┌──────────────────────────────────────────────────────────────────────────┐
│                   RTB 竞价时序图                                           │
│                                                                          │
│  用户 → Publisher 网站/APP                                                 │
│  │                                                                        │
│  │ 1. 页面加载 (0ms)                                                      │
│  │ └─ 检测广告位                                                           │
│  │                                                                        │
│  │ 2. SSP 请求广告 (0-5ms)                                                 │
│  │ └─ 检查本地库存/频次控制                                                 │
│  │                                                                        │
│  │ 3. Header Bidding (5-15ms)                                            │
│  │ ├── 同时请求 Top DSP (Google/Amazon/TTDK/Magnite)                       │
│  │ ├── 各 DSP 返回预竞价 (Pre-bid)                                         │
│  │ └─ 确定底价 (Highest Pre-bid → Price Floor)                             │
│  │                                                                        │
│  │ 4. Bid Request → Ad Exchange (15-25ms)                                 │
│  │ └─ 发送 OpenRTB 请求                                                    │
│  │   {                                                                   │
│  │     "id": "abc123",                                                 │
│  │     "imp": [{"id": "1", "banner": {"w": 300, "h": 250}}],           │
│  │     "site": {"domain": "example.com", "page": "..."},               │
│  │     "device": {"ua": "...", "ip": "..."},                           │
│  │     "user": {"id": "...", "ext": {"segments": ["A12", "B34"]}},    │
│  │     "at": 1,  // 竞价类型: 1=VCG, 2=SecondPrice                        │
│  │     "tmax": 100  // 最大竞价时间 (ms)                                  │
│  │   }                                                                   │
│  │                                                                        │
│  │ 5. Ad Exchange 广播 (25-30ms)                                          │
│  │ └─ 通知所有连接的 DSP                                                    │
│  │                                                                        │
│  │ 6. DSP 竞价计算 (30-80ms)                                              │
│  │ ├── 分析 Bid Request                                                   │
│  │ ├── 查询 DMP 获取用户画像                                               │
│  │ ├── 计算 pCTR (预估点击率)                                              │
│  │ ├── 计算 pCVR (预估转化率)                                              │
│  │ ├── 计算 Optimal Bid (最优出价)                                         │
│  │ │   └─ Bid = pCTR × pCVR × Target CPA × β                             │
│  │ ├── 检查预算 (Budget Check)                                             │
│  │ ├── 检查频次 (Frequency Cap)                                            │
│  │ └─ 返回 Bid Response (Bid + Ad ID + URL)                               │
│  │                                                                        │
│  │ 7. 竞价决策 (80-85ms)                                                   │
│  │ ├── 比较所有 Bid Response                                              │
│  │ ├── 选择最高 Bid (或按 Score 排序)                                       │
│  │ └─ 确定中标者 (Winner)                                                  │
│  │                                                                        │
│  │ 8. 返回广告 (85-95ms)                                                   │
│  │ ├── Ad Exchange → SSP 返回中标广告                                       │
│  │ └─ SSP → Publisher 返回广告                                             │
│  │                                                                        │
│  │ 9. 展示广告 (95-100ms)                                                  │
│  │ └─ 广告渲染到页面                                                        │
│  │                                                                        │
│  │ 10. 追踪回调 (Post-Render, 100ms+)                                     │
│  │ ├── Impression Tracking (曝光追踪)                                       │
│  │ ├── Click Tracking (点击追踪)                                           │
│  │ └─ Conversion Tracking (转化追踪)                                       │
│                                                                          │
│  总延迟: ~100ms                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 OpenRTB 协议详解

```
OpenRTB 2.5+ Bid Request 完整结构:

{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",  // 唯一请求ID
  "tmax": 100,  // 最大响应时间 (毫秒)
  "at": 2,  // 竞价类型: 1=FirstPrice, 2=SecondPrice
  "imp": [  // 广告位列表
    {
      "id": "imp_001",
      "banner": {
        "w": 300,  // 宽度
        "h": 250,  // 高度
        "btype": ["banner"],  // 广告类型
        "pos": "above_fold"  // 广告位置
      },
      "instl": 0,  // 是否是插屏广告 (0=页面, 1=插屏)
      "tagid": "banner_300x250_top",
      "secure": 1,  // 是否安全 (HTTPS)
      "bidfloor": 1.00,  // 底价 (美元)
      "bidfloorcur": "USD"  // 底价货币
    }
  ],
  "site": {  // 网站信息 (APP 用 app 字段)
    "domain": "example.com",
    "page": "https://example.com/article/123",
    "name": "Example Article",
    "cat": ["IAB19", "IAB19-1"],  // 内容分类 (IAB)
    "sectioncat": ["IAB19-1"],
    "pagecat": ["IAB19"],
    "ref": "https://google.com",  // 来源页面
    "search": "keyword",  // 搜索词
    "mobile": 1,  // 是否是移动端
    "privacypolicy": 1  // 是否有隐私政策
  },
  "app": {  // APP 信息 (与 site 互斥)
    "id": "com.example.app",
    "name": "Example App",
    "domain": "example.com",
    "cat": ["IAB18"],
    "bundle": "com.example.app"
  },
  "device": {
    "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0...)",
    "ip": "192.168.1.1",
    "ifa": "a1b2c3d4-e5f6-7890",  // IDFV/AAID
    "make": "Apple",
    "model": "iPhone 13",
    "os": "iOS",
    "osv": "15.0",
    "h": 844,  // 屏幕高度
    "w": 390,  // 屏幕宽度
    "carrier": "Verizon",
    "language": "en",
    "dnt": 0,  // Do Not Track
    "lmt": 0  // Limit Ad Tracking
  },
  "user": {
    "id": "user_12345",  // 用户ID (一方数据)
    "buyeruid": "dsp_user_12345",  // DSP 的用户ID
    "yob": 1990,  // 出生年份
    "gender": "m",  // 性别: m/f/n
    "ext": {
      "segments": ["A12", "B34", "C56"]  // 人群标签 (来自 DMP)
    }
  },
  "regs": {  // 法规 (GDPR/CCPA)
    "ext": {
      "gdpr": 1,  // 1=GDPR 适用
      "consent": "CO_xxxxxxxxxx"  // TCF Consent String
    }
  },
  "ext": {  // 扩展字段
    "prebid": {
      "bidder": ["appnexus", "rubicon", "indexexchange"]
    }
  }
}

OpenRTB Bid Response:

{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "seatbid": [
    {
      "seat": "dsp_001",  // 出价方ID
      "bid": [
        {
          "id": "bid_123",  // 出价ID (用于回传)
          "impid": "imp_001",  // 对应的广告位ID
          "price": 2.50,  // 出价 (CPC/CPM)
          "adm": "<html>...</html>",  // 广告HTML
          "adid": "ad_456",  // 广告ID
          "adomain": ["example.com"],  // 广告主域名
          "bundle": "com.example.app",
          "catt": ["IAB19"],
          "cid": "campaign_001",  // 广告系列ID
          "crid": "creative_001",  // 创意ID
          "attr": [1, 2, 3],  // 广告属性
          "api": 2,  // API框架: 2=VPAID
          "mimes": ["text/html"],
          "w": 300,  // 宽
          "h": 250,  // 高
          "exp": 50,  // 广告过期时间 (秒)
          "lurl": "https://dsp.com/win_notice",  // 中标通知URL
          "burl": "https://dsp.com/click",  // 点击通知URL
          "durl": "https://dsp.com/impression",  // 展示通知URL
          "iurl": "https://dsp.com/click_tracking"  // 点击追踪
        }
      ]
    }
  ],
  "cur": "USD"  // 货币
}
```

### 3.3 OpenRTB 的 Go 实现（生产级）

```go
// OpenRTB: 广告竞价请求与响应的 Go 实现
// 生产级实现：覆盖 BidRequest/BidResponse 核心结构
package openrtb

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// ==================== BidRequest ====================

// BidRequest 对应 OpenRTB 2.5+ 协议
type BidRequest struct {
	ID            string           `json:"id"`
	TMax          int              `json:"tmax,omitempty"`
	Ate           int              `json:"at"`
	Imp           []Impression     `json:"imp"`
	Site          *Site            `json:"site,omitempty"`
	App           *App             `json:"app,omitempty"`
	Device        *Device          `json:"device"`
	User          *User            `json:"user,omitempty"`
	Regs          *Regs            `json:"regs,omitempty"`
	Ext           json.RawMessage  `json:"ext,omitempty"`
}

// Impression 广告位
type Impression struct {
	ID        string   `json:"id"`
	BidFloor  float64  `json:"bidfloor"`
	Banner    *Banner  `json:"banner,omitempty"`
	Video     *Video   `json:"video,omitempty"`
	TagID     string   `json:"tagid,omitempty"`
	Secure    int      `json:"secure,omitempty"`
	Instl     int      `json:"instl,omitempty"`
}

// Banner 横幅广告
type Banner struct {
	W     int    `json:"w,omitempty"`
	H     int    `json:"h,omitempty"`
	Pos   string `json:"pos,omitempty"`
	BType []string `json:"btype,omitempty"`
}

// Video 视频广告
type Video struct {
	MIMEs []string `json:"mimes"`
	W     int      `json:"w"`
	H     int      `json:"h"`
	MinD  int      `json:"minduration"`
	MaxD  int      `json:"maxduration"`
	Protos []int   `json:"protocols,omitempty"`
}

// Site 网站信息
type Site struct {
	Domain      string   `json:"domain"`
	Page        string   `json:"page"`
	CAT         []string `json:"cat"`
	SectionCAT  []string `json:"sectioncat"`
	Mobile      int      `json:"mobile,omitempty"`
}

// App APP 信息
type App struct {
	ID   string   `json:"id"`
	Name string   `json:"name"`
	CAT  []string `json:"cat"`
}

// Device 设备信息
type Device struct {
	UA      string `json:"ua"`
	IP      string `json:"ip"`
	IFA     string `json:"ifa"`
	Make    string `json:"make"`
	Model   string `json:"model"`
	OS      string `json:"os"`
	OSV     string `json:"osv"`
	H       int    `json:"h"`
	W       int    `json:"w"`
	Language string `json:"language"`
	DNT     int    `json:"dnt,omitempty"`
	LMT     int    `json:"lmt,omitempty"`
}

// User 用户信息
type User struct {
	ID       string   `json:"id,omitempty"`
	BuyerUID string   `json:"buyeruid,omitempty"`
	Gender   string   `json:"gender,omitempty"`
	Ext      json.RawMessage `json:"ext,omitempty"`
}

// Regs 法规信息
type Regs struct {
	Ext json.RawMessage `json:"ext,omitempty"`
}

// ==================== BidResponse ====================

// BidResponse RTB 竞价响应
type BidResponse struct {
	ID      string        `json:"id"`
	BidID   string        `json:"bidid,omitempty"`
	Cur     string        `json:"cur"`
	SeatBid []SeatBid     `json:"seatsbid"`
}

// SeatBid 席位出价
type SeatBid struct {
	Bid  []Bid         `json:"bid"`
	Seat string        `json:"seat,omitempty"`
	Grup int           `json:"grp,omitempty"`
}

// Bid 单次出价
type Bid struct {
	ID        string  `json:"id"`
	ImpID     string  `json:"impid"`
	Price     float64 `json:"price"`
	NURL      string  `json:"nurl,omitempty"`  // 通知URL
	BIDMeta   *BIDMeta `json:"meta,omitempty"`
	AdM       string  `json:"adm,omitempty"`     // 广告创意
	ADID      string  `json:"adid,omitempty"`
	Adomain   []string `json:"adomain,omitempty"`
}

// BIDMeta 广告元数据
type BIDMeta struct {
	AdTypeID int      `json:"adtype"`
	Adomain  []string `json:"adomain,omitempty"`
}

// ==================== BidEngine ====================

// BidEngine 竞价引擎核心：在 50ms 内完成竞价决策
type BidEngine struct {
	// pCTR 预测模型（通过 gRPC 调用）
	PCTRClient PCTRServiceClient
	// pCVR 预测模型
	PCVRClient PCVRServiceClient
	// 预算管理器
	BudgetMgr *BudgetManager
	// 频率限制
	FreqCap *FreqCapService
	// Beta 探索参数
	Beta float64
}

// BidDecision 竞价决策结果
type BidDecision struct {
	ShouldBid bool
	BidPrice  float64
	AdID      string
	Rejection string // 未出价原因
}

// Bid 执行竞价决策
func (e *BidEngine) Bid(req *BidRequest) (*BidResponse, error) {
	// 1. 预筛：频率限制
	imp := req.Imp[0]
	if e.FreqCap.ShouldBlock(req.User.ID, imp.ID) {
		return nil, nil // 不出价
	}

	// 2. 并行调用 pCTR 和 pCVR 模型 (p50 < 5ms)
	pctr, err := e.PCTRClient.Predict(req, imp)
	if err != nil {
		pctr = 0.001 // 回退默认值
	}
	pcvr, err := e.PCVRClient.Predict(req, imp)
	if err != nil {
		pcvr = 0.02 // 回退默认值
	}

	// 3. 计算最优出价: Bid = pCTR × pCVR × TargetCPA × β
	targetCPA := 10.0 // 可从预算管理器获取
	bidPrice := pctr * pcvr * targetCPA * e.Beta

	// 4. 底价保护
	if bidPrice < imp.BidFloor {
		return nil, nil
	}

	// 5. 预算检查
	if !e.BudgetMgr.HasBudget(bidPrice) {
		return nil, nil
	}

	// 6. 构造 BidResponse
	decision := &BidDecision{
		ShouldBid: true,
		BidPrice:  bidPrice,
	}

	resp := &BidResponse{
		ID:  req.ID,
		BidID: generateUUID(),
		Cur: "USD",
		SeatBid: []SeatBid{{
			Bid: []Bid{{
				ID:      generateUUID(),
				ImpID:   imp.ID,
				Price:   bidPrice,
				AdM:     `<html><body><img src="creative.jpg"/></body></html>`,
				ADID:    "ad_12345",
				Adomain: []string{"advertiser.com"},
				BIDMeta: &BIDMeta{AdTypeID: 1},
			}},
		}},
	}

	return resp, nil
}

// ==================== gRPC Client ====================

// PCTRServiceClient pCTR 模型服务客户端
type PCTRServiceClient interface {
	Predict(req *BidRequest, imp Impression) (float64, error)
}

// PCVRServiceClient pCVR 模型服务客户端
type PCVRServiceClient interface {
	Predict(req *BidRequest, imp Impression) (float64, error)
}

// ==================== 辅助组件 ====================

// BudgetManager 预算管理器
type BudgetManager struct {
	dailyBudget  float64
	spentToday  float64
}

func (b *BudgetManager) HasBudget(bid float64) bool {
	return b.spentToday+bid <= b.dailyBudget
}

// FreqCapService 频率限制服务
type FreqCapService struct{}

func (f *FreqCapService) ShouldBlock(userID, adID string) bool {
	// 检查: 同一用户 24h 内看到同一广告不超过 3 次
	return false // 简化实现
}

// ==================== 工具函数 ====================

func generateUUID() string {
	return fmt.Sprintf("%d", time.Now().UnixNano())
}

func marshalRequest(req *BidRequest) ([]byte, error) {
	return json.Marshal(req)
}

func unmarshalRequest(data []byte) (*BidRequest, error) {
	req := &BidRequest{}
	err := json.Unmarshal(data, req)
	return req, err
}

// ==================== 使用示例 ====================

func ExampleBidEngine() {
	engine := &BidEngine{
		Beta: 0.95, // 保守探索
		BudgetMgr: &BudgetManager{
			dailyBudget: 1000.0,
			spentToday: 500.0,
		},
	}

	// 构造 BidRequest
	req := &BidRequest{
		ID:   "req-001",
		TMax: 100,
		Ate:  2,
		Imp: []Impression{{
			ID:       "imp-001",
			BidFloor: 1.00,
			Banner:   &Banner{W: 300, H: 250, Pos: "above_fold"},
		}},
		Device: &Device{UA: "Mozilla/5.0...", IP: "192.168.1.1"},
	}

	resp, _ := engine.Bid(req)
	fmt.Printf("BidPrice=%.2f, Cur=%s\n", resp.SeatBid[0].Bid[0].Price, resp.Cur)
}
```

---

## 第四部分：Header Bidding

### 4.1 Header Bidding 架构

```
Header Bidding 的演进:

GPT (Google Publisher Tag) → Google Auction → SSP → DSP
```

### 4.2 无头竞价 (Unified Auction)

```
现在的主流趋势是 "Unified Auction":

┌──────────────────────────────────────────────────────────────┐
│              Unified Auction (GAM + Header Bidding)           │
│                                                              │
│  传统方式 (SSP → GAM → DSP):                                  │
│  ├── SSP 竞价完成后再请求 GAM                                   │
│  └─ GAM 可能覆盖 SSP 的预竞价                                  │
│                                                              │
│  Unified Auction 方式:                                        │
│  ├── Header Bidding 预竞价先完成                               │
│  ├── GAM 将预竞价结果作为 Floor 参与竞价                         │
│  ├── GAM 自身的 AdSense/AdX 也参与竞价                        │
│  └─ 统一选择最高 Bid                                          │
│                                                              │
│  优势:                                                       │
│  ├── Publisher 获得最高收入                                     │
│  ├── 减少广告浪费                                              │
│  └─ 竞价更公平                                                │
│                                                              │
│  实现方式:                                                    │
│  ├── GMAD (Google Marketing Ad)                              │
│  ├── Prebid.js (开源)                                        │
│  ├── Prebid Server (服务端)                                   │
│  └─ Waterfall (传统级联方式 — 逐渐淘汰)                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 第五部分：广告系统数据流

### 5.1 端到端数据流

```
广告系统的端到端数据流:

┌──────────────────────────────────────────────────────────────┐
│                  端到端数据流                                   │
│                                                              │
│  数据收集 (Data Collection):                                  │
│  ├── 用户点击/展示 → Tracking Pixel/SDK                      │
│  ├── 事件日志 → 实时流 (Kafka/PubSub)                        │
│  └─ 日志聚合 → Data Warehouse (BigQuery/S3)                  │
│                                                              │
│  数据处理 (Processing):                                       │
│  ├── 实时: Flink/Spark Streaming → 实时竞价                   │
│  ├── 离线: Spark/Hadoop → 模型训练/报表                      │
│  └─ 流批一体: Flink CDC → 统一处理                           │
│                                                              │
│  数据应用 (Application):                                     │
│  ├── 实时: 竞价引擎 (pCTR/pCVR预测)                          │
│  ├── 离线: 归因模型/受众画像                                   │
│  └─ 批量: 报表/预算监控                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 第六部分：竞价类型详解

### 6.1 First Price vs Second Price

```
竞价价格机制:

1. First Price (第一价格竞价):
   ├── 中标者支付自己出价的价格
   ├── 广告主有动机压低出价 (避免多付)
   ├── 适合: 程序化直接购买
   └─ 当前趋势: Google AdX 2020 转向 First Price

2. Second Price (第二价格竞价 / VCG):
   ├── 中标者支付第二高出价 + 最小增量
   ├── 广告主有动机出真实估值 (Truthful Bidding)
   ├── 适合: 公开竞价
   └─ 优点: 减少 Bid Shading 博弈

3. Bid Shading (出价衰减):
   ├── 在 First Price 下，广告主需要预测第二高价
   ├── 出价 = min(真实估值, 预估第二高价)
   ├── 核心算法: 
   │   ├── 统计模型 (历史竞价分布)
   │   ├── 机器学习 (竞价预测模型)
   │   └─ 优化目标: Maximize (估值 - 出价) × P(中标)
   └─ Bid Shading 是 DSP 的核心竞争力
```

### 6.2 竞价策略对比

```
┌──────────────────────────────────────────────────────────────┐
│              竞价策略对比                                       │
│                                                              │
│  | 策略           | 适用场景           | 效果          |
│  |---------------|------------------|-------------|
│  | Manual CPM    | 品牌曝光            | 完全控制      |
│  | vCPM          | 展示广告            | 按可见展示计费  |
│  | Target CPA    | 转化优化            | 目标CPA       |
│  | Target ROAS   | ROI导向            | 目标ROAS      |
│  | Max Conv      | 最大化转化量         | 最大转化      |
│  | Bid Shading   | First Price 竞价    | 优化出价      |
│  | Auto Bid      | 自动化              | 系统最优      |
└──────────────────────────────────────────────────────────────┘
```

---

## 第七部分：广告系统的核心指标

### 7.1 Publisher 侧指标

```
Publisher 关注:

┌──────────────────────────────────────────────────────────────┐
│              Publisher 核心指标                                 │
│                                                              │
│  库存指标:                                                   │
│  ├── Impressions Available (可用展示)                          │
│  ├── Impressions Filled (已填充展示)                           │
│  ├── Fill Rate = Filled / Available (填充率)                  │
│  └─ Ad Load (广告加载率) — 平衡用户体验                        │
│                                                              │
│  收入指标:                                                   │
│  ├── Revenue (总收入)                                         │
│  ├── RPM (Revenue Per Mille = Revenue/Impressions*1000)      │
│  ├── eCPM (effective CPM)                                    │
│  └─ Price Floor (底价)                                       │
│                                                              │
│  质量指标:                                                   │
│  ├── Viewability (可见率)                                     │
│  ├── CTR (点击率)                                            │
│  └─ Invalid Traffic (无效流量)                                │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 Advertiser 侧指标

```
Advertiser 关注:

┌──────────────────────────────────────────────────────────────┐
│              Advertiser 核心指标                               │
│                                                              │
│  展示指标:                                                   │
│  ├── Impressions (展示次数)                                    │
│  ├── Reach (触达人数)                                         │
│  ├── Frequency (频次) = Impressions / Reach                   │
│  └─ Viewability (可见率)                                     │
│                                                              │
│  点击指标:                                                   │
│  ├── Clicks (点击次数)                                        │
│  ├── CTR = Clicks / Impressions (点击率)                      │
│  └─ CPC = Cost / Clicks (平均CPC)                            │
│                                                              │
│  转化指标:                                                   │
│  ├── Conversions (转化次数)                                    │
│  ├── CPA = Cost / Conversions (每次转化成本)                   │
│  ├── CVR = Conversions / Clicks (转化率)                      │
│  └─ ROAS = Revenue / Cost (广告回报率)                        │
│                                                              │
│  预算指标:                                                   │
│  ├── Budget Run Rate (预算消耗速率)                            │
│  ├── Budget Pacing (预算分配)                                 │
│  └─ Burn Rate (消耗率)                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 第八部分：广告系统技术栈

### 8.1 关键技术组件

```
广告系统技术栈:

┌──────────────────────────────────────────────────────────────┐
│              广告系统技术栈                                     │
│                                                              │
│  实时竞价层 (Real-Time Layer):                                │
│  ├── 协议: OpenRTB 2.5+                                     │
│  ├── 消息队列: Kafka / Pulsar                                │
│  ├── 实时计算: Flink / Spark Streaming                       │
│  ├── 缓存: Redis / Memcached                                 │
│  ├── 数据库: MySQL / PostgreSQL (元数据)                      │
│  └─ 搜索: Elasticsearch (受众/创意搜索)                       │
│                                                              │
│  预测层 (Prediction Layer):                                  │
│  ├── 特征工程: Flink / Spark                                 │
│  ├── 模型训练: TensorFlow / PyTorch / XGBoost                 │
│  ├── 模型服务: TensorFlow Serving / Triton / KServe           │
│  ├── 特征存储: Redis / Hopsworks / Feast                     │
│  └─ 模型 registry: MLflow / TensorBoard                      │
│                                                              │
│  数据层 (Data Layer):                                        │
│  ├── 数据仓库: BigQuery / Snowflake / Redshift               │
│  ├── 数据湖: S3 / HDFS                                      │
│  ├── 批处理: Spark / Hive                                    │
│  └─ 流处理: Flink / Kafka Streams                            │
│                                                              │
│  基础设施层 (Infrastructure):                                │
│  ├── 容器: Kubernetes / Docker                               │
│  ├── 服务网格: Istio / Linkerd                               │
│  ├── CDN: CloudFront / Fastly (广告素材分发)                 │
│  ├── 监控: Prometheus / Grafana                              │
│  └─ 日志: ELK / Loki                                        │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 高性能要求

```
广告系统对性能的要求:

┌──────────────────────────────────────────────────────────────┐
│              性能要求                                           │
│                                                              │
│  延迟:                                                     │
│  ├── 端到端竞价: < 100ms                                    │
│  ├── DSP 计算 pCTR/pCVR: < 50ms                             │
│  ├── 数据库查询: < 5ms                                       │
│  └─ 缓存查询: < 1ms                                          │
│                                                              │
│  吞吐量:                                                   │
│  ├── 竞价请求: 100K+ RPS                                     │
│  ├── 日志处理: 10M+ events/s                                 │
│  └─ 模型推理: 1M+ req/s                                      │
│                                                              │
│  可用性:                                                   │
│  ├── 99.99% SLA                                             │
│  ├── 多区域部署                                               │
│  └─ 故障自动切换                                              │
│                                                              │
│  一致性:                                                   │
│  ├── 预算实时扣减                                              │
│  ├── 频次数实时更新                                              │
│  └─ 竞价结果强一致                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 第九部分：隐私与合规

### 9.1 Cookie 淘汰的影响

```
隐私监管对广告系统的影响:

┌──────────────────────────────────────────────────────────────┐
│              Cookie 淘汰                                       │
│                                                              │
│  背景:                                                     │
│  ├── Safari: ITP (Intelligent Tracking Prevention)           │
│  ├── Firefox: ETP (Enhanced Tracking Prevention)             │
│  ├── Chrome: Chrome Privacy Sandbox (2024 起逐步弃用)          │
│  └─ 法规: GDPR / CCPA / LGPD                                │
│                                                              │
│  应对方案:                                                   │
│  ├── First-Party Data (一方数据)                              │
│  │   ├── 用户登录 (Login)                                     │
│  │   ├── CRM 数据                                             │
│  │   └─ 服务端事件 (Server-Side Events)                       │
│  ├── Contextual Targeting (上下文定向)                         │
│  │   ├── 页面内容分析                                          │
│  │   ├── 关键词匹配                                          │
│  │   └─ 语义分析 (NLP)                                       │
│  ├── Clean Rooms (干净房间)                                   │
│  │   ├── Google Marketing Platform Clean Room                │
│  │   ├── Facebook Clean Room                                │
│  │   └─ Oracle Clean Room                                   │
│  ├── On-Device Processing (设备端处理)                        │
│  │   ├── Apple SKAdNetwork                                   │
│  │   ├── Google Privacy Sandbox (Topics/FLEDGE)              │
│  │   └─ Meta Privacy-First Targeting                          │
│  └─ Federated Learning (联邦学习)                             │
│      ├── 模型在设备端训练                                     │
│      └─ 只共享模型参数 (非原始数据)                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 第十部分：自测题

### 问题 1
一次 RTB 竞价的端到端延迟要求是多少？

<details>
<summary>查看答案</summary>

< 100ms。其中：DSP 计算 < 50ms，数据库查询 < 5ms，缓存查询 < 1ms。
</details>

### 问题 2
Header Bidding 和 Unified Auction 的区别是什么？

<details>
<summary>查看答案</summary>

- Header Bidding: SSP 先竞价，再请求 GAM
- Unified Auction: Header Bidding 预竞价结果作为 GAM Floor，GAM 自己的 AdSense 也参与竞价，统一选择最高 Bid
- Unified Auction 让 Publisher 获得更高收入
</details>

### 问题 3
First Price 和 Second Price 竞价的区别？广告主该如何应对？

<details>
<summary>查看答案</summary>

- First Price: 支付自己的出价，需要 Bid Shading (出价衰减)
- Second Price: 支付第二高出价 + 最小增量，最优策略是出真实估值
- 广告主在 First Price 下应预测第二高价并降低出价
</details>

### 问题 4
OpenRTB Bid Request 中 "at" 字段是什么意思？

<details>
<summary>查看答案</summary>

"at" = auction type
- 1 = First Price (第一价格竞价)
- 2 = Second Price (第二价格竞价)
</details>

### 问题 5
Go 的 `BidEngine.Bid` 方法中，为什么 pCTR/pCVR 调用失败时用固定默认值而不是 panic？

<details>
<summary>查看答案</summary>

1. RTB 是硬实时系统，p50 要求 < 50ms，panic 会导致整个请求失败，浪费广告位
2. 默认值作为 fallback：pCTR=0.001, pCVR=0.02 会让出价极低，几乎不会中标，这是安全的保守策略
3. 实际生产中还会记录错误指标用于监控和告警
</details>

### 问题 6
Bid = pCTR × pCVR × TargetCPA × β 这个公式中，β 的作用是什么？为什么通常设为 0.95？

<details>
<summary>查看答案</summary>

β 是探索参数（exploration factor），作用：
1. 保守出价：pCTR×pCVR 是估值，直接出全额容易被对手利用（winner's curse）
2. 0.95 意味着出估值的 95%，留出 5% 的安全边际
3. β 可以通过 Bandit 算法在线学习优化：初期 0.8 多探索，后期 0.98 收敛
4. 如果系统发现经常输竞价 → 调高 β；经常超 CPA → 降低 β
</details>

### 问题 7
Go 中 BidRequest 的 `json:"..."` tag 里 `omitempty` 的作用是什么？

<details>
<summary>查看答案</summary>

omitempty 表示当字段为零值时不包含在 JSON 序列化结果中：
1. 减少请求体积：RTB 每次传输都按字节计费，去掉 nil 字段可以节省 10-20%
2. 保持协议兼容：不同 SSP 的 BidRequest 字段不同，不传 nil 字段避免解析错误
3. 例如 `*Site` 在 APP 广告中是 nil（用 *App 代替），加上 omitempty 就不会序列化出 `"site": null`
</details>

---

*今天花 90 分钟：系统掌握广告系统全景架构*
*答不出自测题？回去重读对应章节。*
