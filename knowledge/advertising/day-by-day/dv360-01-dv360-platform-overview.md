# DV360 平台全景与核心概念学习笔记

> **领域**: 广告投放 / DV360
> **深度**: ⭐⭐⭐⭐ 进阶学习笔记
> **标签**: dv360, display-video-360, programmatic, gmp
> **更新时间**: 2026-08-14
> **类型**: day-by-day/learning-note

---

## 📌 今日学习重点

今天系统梳理 DV360 的完整知识体系，从平台定位到核心功能模块，为后续深入实践打基础。

---

## 一、DV360 平台定位

### 1.1 什么是 DV360？

**Display & Video 360 (DV360)** 是 Google Marketing Platform (GMP) 的企业级程序化广告平台。

```
GMP 全家桶关系：

Google Marketing Platform
├── Campaign Manager 360 (CM360) — 广告追踪与归因
├── Display & Video 360 (DV360)   — 程序化媒体购买
├── Search Ads 360 (SA360)        — 搜索广告投放
├── Google Analytics 360          — 数据分析
├── Google Ads 360                — 搜索/YouTube 投放
└── Google Ads Data Hub (ADH)     — 跨平台数据融合
```

### 1.2 DV360 的核心价值

| 价值点 | 说明 | 竞品对比 |
|--------|------|---------|
| **跨媒体投放** | 展示、视频、音频、电视、零售媒体一站式 | TTD 类似，Amazon DSP 偏电商 |
| **多 DSP 接入** | 通过 Exchange 连接 100+ DSP | TTD 更开放，Amazon DSP 封闭 |
| **程序化保量** | PG + PMP 保障品牌采购 | 唯一支持 Google 自营库存 |
| **品牌安全** | IAS/DV/Moat 集成 | 行业领先 |
| **数据整合** | ADH + GA4 + GMP 深度打通 | 其他平台难以匹敌 |

### 1.3 DV360 vs 竞品对比

```
程序化广告平台市场份额 (2024):

DV360     ████████████████████████  35%
TTD       ████████████████          25%
Amazon DSP ██████████               15%
Programmatic 其他 ██████████████████ 25%

DV360 优势：
✅ Google 生态整合（YouTube/Shopping/ADH）
✅ 程序化保量（PG）能力唯一
✅ 品牌安全工具链完整
✅ 企业级支持和 SLA

TTD 优势：
✅ 界面友好，学习成本低
✅ 独立 DSP，无平台偏见
✅ OpenRTB 支持完善
✅ 创意优化工具强

Amazon DSP:
✅ 电商数据独占
✅ Amazon 生态整合
✅ 零售媒体增长快
❌ 非 Amazon 平台覆盖弱
```

---

## 二、账户层级结构

### 2.1 官方层级

```
Advertiser (广告主)
├── Insertion Orders (IO，订单项)         ← 预算和排期的容器
│   ├── Flight (航班期)                   ← IO 内的时间段分组
│   │   ├── Line Items (线条项目)         ← 实际购买的单位
│   │   │   ├── Creatives (创意)          ← 广告素材
│   │   │   ├── Targeting (定向)          ← 受众/上下文定向
│   │   │   └── Schedule (排期)           ← 投放时间
│   │   └── Budget (预算)                 ← 该 Flight 的预算
│   ├── Partners (合作伙伴)               ← 代理商/客户授权
│   └── Users (用户)                      ← 账户权限
├── Budgets (预算池)                      ← 可跨 IO 共享预算
├── Custom Channels (自定义频道)           ← 库存组合
├── Placements (投放位置)                 ← 网站/App 定向
├── Targeting Sources (定向源)            ← 受众来源
├── Reports (报表)                        ← 数据分析
└── Tools (工具)                          ← 自动化规则等
```

### 2.2 IO 与 Line Item 的关系

```
IO (Insertion Order) = 法律合同层面的购买协议
├── 定义：广告主与 publishers 之间的采购协议
├── 包含：总价、总展示量承诺、排期范围
└── 多个 Line Item 共享同一个 IO

Line Item (LI) = 技术执行层面的购买单元
├── 定义：具体的出价、定向、预算配置
├── 可以：多个 LI 共享同一个 IO
└── 优先级：同一 IO 内，LI 按 priority 决定展示顺序
```

### 2.3 Priority 机制

```
Line Item 优先级（同一 IO 内）：

Priority 1 (最高) ──▶ 程序化保量 (PG) — 必须满足
Priority 2         ──▶ 私有市场 (PMP)  — 优先购买权
Priority 3         ──▶ 优先交易 (PD)    — 固定价格优先
Priority 4 (最低)   ──▶ 公开竞价 (Open) — 剩余库存

执行逻辑：
1. 每个 Impression Request 到达
2. 按 Priority 从高到低依次出价
3. Priority 1 的 LI 必须满足才能继续
4. 如果 Priority 1 没满，才轮到 Priority 2
5. 以此类推...
```

---

## 三、交易类型详解

### 3.1 四种交易类型

```
┌─────────────────────────────────────────────────────────────────┐
│                     交易类型对比                                 │
├──────────────┬───────────────┬───────────────┬──────────────────┤
│     特性      │   PG (保量)   │   PMP (私有)  │    PD (优先)     │
├──────────────┼───────────────┼───────────────┼──────────────────┤
│ 库存保障      │ ✅ 100%保量    │ ⚠️ 部分保量    │ ❌ 不保量         │
│ 价格         │ 固定/协商      │ 固定/动态      │ 固定价格          │
│ 竞争程度      │ 无竞争        │ 有限竞争       │ 有限竞争          │
│ 适用场景      │ 品牌大额投放   │ 优质库存采购   │ 抢独家资源        │
│ 最小预算      │ $100K+       │ $10K+         │ $5K+             │
│ 灵活性       │ 低            │ 中             │ 高                │
├──────────────┼───────────────┼───────────────┼──────────────────┤
│ 公开竞价      │ ❌            │ ❌            │ ❌                │
│ 实时竞价      │ ⚠️ 部分        │ ✅            │ ✅                │
└──────────────┴───────────────┴───────────────┴──────────────────┘
```

### 3.2 Programmatic Guaranteed (PG) 详解

```
PG 工作流程：

1. 广告主与 Publisher 协商
   ├── 确定展示量承诺 (如 10M impressions)
   ├── 确定 CPM 价格 (如 $15 CPM)
   ├── 确定排期 (如 Q1 2025)
   └── 确定定向要求

2. DV360 创建 IO
   ├── Type: PROGRAMMATIC_GUARANTEED
   ├── Line Item Count: 按需求拆分
   └── Budget: $150,000 (10M × $15)

3. 投放执行
   ├── 每日展示量保证
   ├── 未达标自动补量
   └── 超额展示不计费

4. 报告与对账
   ├── 实时展示报告
   ├── 可见性报告
   └── 最终对账单
```

### 3.3 Private Market Place (PMP) 详解

```
PMP 特权等级：

Premium (黄金) ──── 邀请制，仅受邀买家
Private (白银) ──── 审核制，需申请加入
Open (青铜) ────── 自由加入，先到先得

PMP 定价模式：
├── Fixed CPM: 固定价格，先到先得
├── Auction: 在 PMP 内竞价
└── Hybrid: 固定底价 + 溢价竞价
```

---

## 四、创意管理系统

### 4.1 创意格式

```
DV360 支持的创意格式：

┌──────────────────────────────────────────────────────────────┐
│                      创意格式矩阵                             │
├──────────────┬────────────┬───────────┬──────────────────────┤
│    格式       │  尺寸/规格   │  文件大小  │     适用场景          │
├──────────────┼────────────┼───────────┼──────────────────────┤
│ 静态横幅      │ 多种标准    │ <200KB    │ 品牌曝光、再营销      │
│ HTML5 互动   │ 自适应      │ <200KB    │ 富媒体、交互广告      │
│ 视频 (VAST)  │ 16:9/9:16  │ <50MB     │ 前贴片、中贴片        │
│ 原生广告     │ 自适应      │ 无限制    │ 内容融合广告          │
│ 响应式       │ 自适应      │ 按需      │ 多尺寸自动适配        │
│ 静态图片     │ 多种        │ <150KB    │ 常规展示              │
│ 轮播         │ 自定义      │ 累计<200K │ 多产品展示            │
└──────────────┴────────────┴───────────┴──────────────────────┘
```

### 4.2 创意审批流程

```
创意提交流程：

1. 上传创意
   └── API: POST /creatives

2. 自动预审
   ├── 尺寸检查
   ├── 文件大小检查
   ├── 格式检查
   └── 基础内容检查

3. 人工审核（可能需要）
   ├── 品牌安全审查
   ├── 政策合规审查
   └── 创意质量评估

4. 审批状态
   ├── APPROVED → 可投放
   ├── REJECTED → 需修改后重新提交
   ├── PENDING → 等待审核
   └── UNDER_REVIEW → 审核中

平均审核时间：2-4 小时（工作日）
```

---

## 五、定向系统

### 5.1 定向类型

```
DV360 定向体系：

上下文定向 (Contextual)
├── 关键词定向 (Keyword)
├── 分类定向 (Content Category)
├── 页面 URL 定向 (Page URL)
├── 应用类别定向 (App Category)
└── 放置位置定向 (Placement)

受众定向 (Audience)
├── 第一方受众 (Custom Audience)
│   └── 上传 CSV / CRM 数据
├── Google 受众
│   ├── In-Market Audiences
│   ├── Life Events
│   └── Affinity Audiences
├── 第三方受众
│   ├── DMARx (数据合作方)
│   └── 其他 ID 解决方案
└── 再营销 (Remarketing)
    └── Floodlight 触达历史

设备定向
├── 操作系统 (iOS/Android/Desktop)
├── 设备类型 (Mobile/Tablet/Desktop)
├── 连接类型 (4G/5G/WiFi)
└── 浏览器

地理定向
├── 国家/地区
├── 州/省
├── 城市
├── 邮编
└── GPS 坐标（地理围栏）
```

### 5.2 频率控制

```
频率控制策略：

单 Line Item 频率控制：
├── 每用户每日最大展示次数
├── 每用户每生命周期最大展示次数
└── 跨 Line Item 频率控制（同一 IO 内）

示例配置：
- 每用户每日发布 ≤ 3 次
- 每用户整个 campaign ≤ 15 次
- 避免疲劳度 > 30%

DV360 内置指标：
- Frequency Distribution
- Fatigue Rate
- Effective Frequency (3+ views)
```

---

## 六、测量与归因

### 6.1 Floodlight 活动

```
Floodlight 是 DV360 的核心测量工具：

Floodlight 标签类型：
├── Tag (标准 Floodlight 标签)
│   └── 最简单的转化追踪
├── Counter (计数器)
│   └── 用于累积统计（如页面浏览量）
└── Dynamic (动态 Floodlight)
    └── 用于电商转化（带 order_id, value 等）

Floodlight 配置要素：
- Category: 转化类型分组
- Type: 具体事件类型
- Tag: 唯一标识符
- Attributes: 自定义变量（order_id, revenue 等）
```

### 6.2 第三方测量

```
DV360 支持的第三方测量工具：

品牌安全与可见性：
├── DoubleVerify (DV) — 行业领先
├── Moat (Nielsen) — 品牌安全性
├── Integral Ad Science (IAS) — 广告质量检测
└── Footprint — 品牌安全

受众测量：
├── comScore — 跨屏受众测量
└── Nielsen — 品牌研究

增量测量：
├── Meta Conversion Lift
├── Google Geo Experiments
└── Third-party incrementality vendors
```

---

## 七、自测题

### Q1: PG 和 PMP 的核心区别是什么？

<details>
<summary>点击查看答案</summary>

**PG (Programmatic Guaranteed)**:
- 100% 展示量保证
- 固定价格，提前锁定
- 适合品牌大额投放
- 最低预算通常 $100K+

**PMP (Private Market Place)**:
- 不保证展示量
- 价格可以是固定或竞价
- 适合获取优质库存
- 最低预算较低 ($10K+)
- 有 Premium/Private/Open 三个等级

核心区别：PG 是"买断"，PMP 是"优先购买权"。
</details>

### Q2: DV360 中 Frequency Control 为什么要跨 Line Item 控制？

<details>
<summary>点击查看答案</summary>

因为同一个 IO 内可能有多个 Line Item 面向同一受众：
- LI-1: 品牌 awareness 广告
- LI-2: 再营销转化广告

如果各自独立控制频率，同一用户可能在短时间内看到 6 次广告（LI-1 看 3 次 + LI-2 看 3 次），导致用户体验极差。

跨 LI 频率控制确保用户在 IO 级别看到的总频次不超过设定值。
</details>

### Q3: 为什么 DV360 的品牌安全要求比其他平台高？

<details>
<summary>点击查看答案</summary>

DV360 的主要客户是企业品牌广告主，他们对品牌安全的要求极高：
1. 品牌广告预算大，一次负面关联损失巨大
2. 企业客户有严格的合规要求
3. DV360 的广告位质量普遍较高（主流 publisher）
4. 需要与第三方测量工具（DV/Moat/IAS）深度集成

因此 DV360 提供了：
- 多层级品牌安全分级
- 详细的 site/app 分类
- 实时品牌安全评分
- 自定义排除列表
</details>

---

## 八、今日学习总结

| 模块 | 核心收获 | 下一步 |
|------|---------|--------|
| 平台定位 | DV360 是 GMP 的程序化购买核心 | 对比 TTD 做决策分析 |
| 账户结构 | IO → Flight → LI → Creative 层级 | 动手配置一个 IO |
| 交易类型 | PG/PMP/PD/Open 四种模式 | 了解每种模式的适用场景 |
| 创意管理 | 多种格式 + 审批流程 | 学习创意上传 API |
| 定向系统 | 上下文+受众+设备+地理 | 深入研究 In-Market 受众 |
| 测量归因 | Floodlight + 第三方 | 理解 Floodlight 配置 |

---

## 九、参考资料

- [DV360 官方文档](https://developers.google.com/display-video/api)
- [Google Marketing Platform](https://marketingplatform.google.com/about/display-video-360/)
- [程序化广告白皮书](https://www.iab.com/resources/frameworks/programmatic-advertising/)

---

*学习日期：2026-08-14 | 下一条：IO/LineItem 工作流深度解析*
