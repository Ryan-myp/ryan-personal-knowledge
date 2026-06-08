# 广告系统架构 — 竞价、排序、流量分配

> 标签: `#广告系统` `#竞价` `#RTB` `#广告排序` `#流量分配` `#oCPX`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. 广告系统整体架构

### 1.1 广告请求全流程

```
用户打开页面/App
    │
    ▼
请求广告位 (Ad Slot Request)
    │
    ├──→ ① 广告位验证 (Slot Validation)
    │      - 广告位有效性、频控、黑名单
    │      - 返回：广告位 ID + 页面上下文
    │
    ├──→ ② 用户画像检索 (User Profiling)
    │      - 用户 ID、设备 ID、兴趣标签、历史行为
    │      - 从 Redis 缓存加载用户特征
    │
    ├──→ ③ 广告预筛选 (Pre-filter)
    │      - 定向条件过滤：地域、年龄、兴趣、设备
    │      - 频控过滤：用户今日已展示次数、转化次数
    │      - 黑名单过滤：已转化用户、竞品广告
    │      - 输出：候选广告集 (Candidate Ads)
    │
    ├──→ ④ 粗排 (Pre-ranking)
    │      - 快速特征提取 + 轻量模型
    │      - 从百万级候选广告中筛选 Top-K (K≈1000)
    │      - 策略：倒排索引 + 规则匹配
    │
    ├──→ ⑤ 精排 (Ranking)
    │      - 深度模型预测 pCTR / pCVR / pCTC
    │      - 多目标排序融合
    │      - 输出：排序分数 + eCPM
    │
    ├──→ ⑥ 竞价策略 (Bidding)
    │      - 根据 pCTR × pCVR 计算出价
    │      - oCPX 目标转化出价
    │      - 预算 Pacing 控制
    │
    ├──→ ⑦ 流量分配 (Allocation)
    │      - 广告位混排：自然内容 vs 广告
    │      - 广告间混排：竞价广告 vs 保量广告
    │
    └──→ ⑧ 返回广告列表 (Ad Response)
           - 返回广告素材 + 追踪 URL + 竞价 ID (Bid ID)
```

### 1.2 核心架构组件

```
┌──────────────────────────────────────────────────────────────┐
│                      Ad Request Pipeline                     │
│                                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │ Pre-    │  │ Pre-    │  │ Rank-   │  │ Bid &   │         │
│  │ filter  │──│ ranking │──│ ing     │──│ Pacing  │──→ Ad   │
│  │ (ms级)  │  │ (10ms级)│  │ (50ms级)│  │ (5ms级) │   List  │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │
│       │             │             │             │             │
│       ▼             ▼             ▼             ▼             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │ 用户画像│  │ 候选广告│  │ 排序模型│  │ 出价策略│         │
│  │ Redis   │  │ 倒排索引│  │ 深度学习│  │ 预算控制│         │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Feature Store (实时特征计算)              │    │
│  │  用户特征 │ 广告特征 │ 上下文特征 │ 交叉特征           │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 核心指标

| 指标 | 公式 | 说明 |
|------|------|------|
| **eCPM** | pCTR × pCVR × bid × 1000 | 千次展示期望收入 |
| **CTR** | 点击数 / 展示数 | 点击率 |
| **CVR** | 转化数 / 点击数 | 转化率 |
| **oCPM** | eCPM 基于转化出价 | 广告主付转化费，平台按转化计算 eCPM |
| **RoAS** | 广告收入 / 广告花费 | 投资回报率 |

---

## 2. 竞价系统 (RTB)

### 2.1 实时竞价流程

```
Step 1: 广告请求到达 SSP/Ad Server
         │
         ▼
Step 2: 构造 Bid Request
         {
           "imp": [{"id": "imp1", "w": 300, "h": 250}],
           "user": {"id": "user123", "demographics": {...}},
           "device": {"ua": "...", "ip": "..."},
           "site": {"id": "site456", "cat": ["BUS", "TECH"]},
           "at": 2,           // 拍卖类型(1=第一价格, 2=第二价格)
           "tmax": 100,     // 超时 100ms
           "bidfloor": 0.5  // 底价
         }
         │
         ▼
Step 3: 发送给 Bidder (广告主/DSP)
         POST /openrtb/bid HTTP/1.1
         {"source": "...", "seatbid": [...]}
         │
         ▼
Step 4: Bidder 返回竞价决策
         {
           "id": "bid-req-001",
           "seatbid": [{
             "bid": [{
               "id": "bid-001",
               "impid": "imp1",
               "price": 2.5,
               "adid": "ad-789",
               "adm": "<creative>"
             }]
           }]
         }
         │
         ▼
Step 5: 选出 Winner（最高价 ≥ bidfloor）
         Winner: Bidder A (price=2.5)
         Price: 第二价格 (≈ Bidder B 的价格)
         │
         ▼
Step 6: 返回广告 + 发送 Win/Loss Notification
         Win: POST /notify/win {bidId: "bid-001"}
         Loss: POST /notify/loss {bidId: "bid-002"}
```

### 2.2 出价公式

#### 基础出价（cCPM）

```
bid = bid_cap  // 广告主直接出价（CPC/CPM/CPT）
```

#### oCPX 出价（核心公式）

广告主按转化出价（CPC/CPA/CPA），平台需要将其转为 CPM 竞价：

```
qCPM = qCTR × qCVR × bid

其中：
  qCTR = 模型预测的点击概率
  qCVR = 模型预测的转化概率
  bid  = 广告主设定的单次转化出价（如 oCPC=5元/点击）

实际竞价时：
  bid = qCTR × qCVR × oCPA × β

  β = 出价系数（可调参数，控制激进/保守程度）
      β > 1  → 激进出价，抢占更多流量
      β < 1  → 保守出价，控制成本
```

#### pCTR 模型演进

```
阶段 1: LR (逻辑回归)
  pCTR = σ(w0 + w1·x1 + w2·x2 + ... + wn·xn)
  优点：简单、快速
  缺点：无法捕捉非线性特征交互

阶段 2: GBDT + LR (Facebook/Facebook 早期)
  GBDT 自动做特征选择 → 离散化 → 输入 LR
  优点：效果好，工业界经典
  缺点：特征工程依赖人工

阶段 3: DeepFM (滴滴/Google)
  FM 层自动捕捉一阶/二阶特征交叉
  Deep 层捕捉高阶特征交互
  pCTR = sigmoid(Dense_output × FM_output)

阶段 4: DIN (Deep Interest Network, 阿里)
  引入 Attention 机制建模用户兴趣
  候选广告 vs 用户历史行为序列
  pCTR = DIN_model(user_history, candidate_ad, context)

阶段 5: 多塔模型 + 实时特征
  Tower 结构：User Tower / Ad Tower / Context Tower
  实时特征：用户最近1分钟行为、实时搜索词
  多目标：同时预测 pCTR / pCVR / pShare / pWatch
```

### 2.3 拍卖机制

| 类型 | 机制 | 广告主出价 | 实际支付 | 适用场景 |
|------|------|-----------|---------|---------|
| **第一价格** | 最高价中标 | bid | bid | 程序化直接购买 |
| **第二价格** | 最高价中标 | bid | 第二高价 | 传统 RTB（逐渐淘汰） |
| **广义第二价格 (GSP)** | 按排序位置定价 | bid | 下一位出价 × 质量分 | Google Ads 主流 |
| **VCG** | Vickrey-Clarke-Groves | bid | 外部性损失 | 理论最优，少用 |

**GSP 实际定价公式**：

```
假设广告位按 eCPM 排序：
  Ad1: eCPM1 = pCTR1 × bid1 = 5.0
  Ad2: eCPM2 = pCTR2 × bid2 = 3.0
  Ad3: eCPM3 = pCTR3 × bid3 = 2.0

Ad1 实际支付 = (eCPM2 / pCTR1) + ε
  = (3.0 / pCTR1) + ε

Ad2 实际支付 = (eCPM3 / pCTR2) + ε
  = (2.0 / pCTR2) + ε

ε = 最小竞价单位（如 0.000001 元）
```

---

## 3. 广告排序

### 3.1 多目标排序公式

```
综合得分 = α·pCTR + β·pCVR·CPA + γ·engagement + δ·广告主出价·RoAS_constraint

实际排序时（eCPM 排序）：
  eCPM = pCTR × pCVR × bid × 1000

多目标融合（双塔 + 多任务）：
  Score = w1·pCTR + w2·pCVR + w3·pEngagement + w4·bid_normalized

其中权重 w1~w4 通过多任务学习 (MMoE / PleM) 自动优化。
```

### 3.2 双塔模型结构

```
                  ┌─────────────┐
                  │   Query     │
                  │   Tower     │
                  │             │
                  │ User Profile│──→ User Embedding (128-dim)
                  │ User History│
                  │ Interests   │
                  └─────────────┘
                          │
                          ▼
                  ┌─────────────┐
                  │  Similarity │
                  │  Computation│
                  │  (Dot Prod) │
                  └─────────────┘
                          │
                          ▼
                  ┌─────────────┐
                  │   Key       │
                  │   Tower     │
                  │             │
                  │ Ad Profile  │──→ Ad Embedding (128-dim)
                  │ Ad Category │
                  │ Bid Price   │
                  └─────────────┘

  Score = UserEmbedding · AdEmbedding = Σ(ui × ai)
```

### 3.3 特征工程体系

```
特征类别        示例                                    来源
─────────────────────────────────────────────────────────────
用户特征       年龄、性别、城市、设备型号               用户画像 DB
              近7天点击/转化行为                        行为日志
              兴趣标签 (电商/游戏/汽车)                 兴趣模型
              LTV 预估                                 用户价值模型

广告特征       广告主 ID、行业、出价、素材类型           广告数据库
              广告创意 embedding                        素材模型
              广告历史 CTR/CVR                          统计特征
              广告时长/曝光天数                          投放设置

上下文特征     时间 (时/日/周)、地理位置                 请求上下文
              页面类型/内容分类                         页面上下文
              网络环境 (WiFi/4G/5G)                    设备信息

交叉特征       用户年龄 × 广告行业                     人工构造
              用户历史 × 广告创意 embedding             模型自动学习
              城市等级 × 广告类型                       人工构造
```

### 3.4 排序系统性能优化

```
目标：RTB 场景下，广告排序 P99 延迟 < 100ms

优化策略：
1. 粗排：倒排索引 + 规则过滤，从 100 万候选 → Top 1000 (1ms)
2. 精排：
   - 模型蒸馏：大模型 → 小模型（100层 Transformer → 12层）
   - 特征采样：只使用 Top-K 最重要特征（减少特征数 80%）
   - 模型缓存：热门广告/用户对的预测结果缓存 (Redis)
   - 量化：INT8 量化模型，推理速度提升 3-5x
3. 并行化：
   - 用户特征、广告特征、上下文特征并行提取
   - 多个子模型并行推理
4. 分布式：
   - 特征服务：Redis 分布式特征缓存
   - 模型服务：TF Serving / ONNX Runtime 分布式部署
```

---

## 4. 流量分配

### 4.1 广告位分配策略

```
广告位场景: 信息流中插入广告

策略 A: 纯竞价 (Pure Bidding)
  所有广告位 → 竞价排序 → 选出最高 eCPM 的广告
  优点：平台收益最大化
  缺点：用户体验下降（广告太多）

策略 B: 固定比例 (Fixed Ratio)
  每 N 条内容插入 1 条广告
  优点：用户体验可控
  缺点：收益可能不是最优

策略 C: 混合模式 (Hybrid) ⭐ 推荐
  - 竞价广告位：80% 的广告位参与竞价
  - 保量广告位：20% 的广告位用于保量客户
  - 广告/内容混排：每隔 3-5 条内容插入广告
  - 广告间混排：竞价广告按 eCPM 排序插入
```

### 4.2 预算 Pacing 控制

```
问题：广告主预算有限，需要在整个投放期内均匀消耗

方法 1: 全局 Pacing
  pacing_factor = min(1.0, budget_spent / (budget_total × time_elapsed / time_total))
  effective_bid = original_bid × pacing_factor

  优点：简单
  缺点：忽略不同时间段的流量价值差异

方法 2: 基于期望的 Pacing (Optimal Pacing)
  optimal_bid(t) = bid_base × (1 - F(t)) / f(t)

  其中：
    F(t) = 到时间 t 为止的预算消耗比例
    f(t) = 时间段 t 的流量密度函数
    bid_base = 广告基础出价

  优点：在流量高峰期提高出价，低峰期降低出价
  缺点：需要准确预测流量分布

方法 3: 强化学习 Pacing (RL-based)
  State: (剩余预算, 剩余时间, 当前流量, 历史消耗曲线)
  Action: 出价系数 β ∈ [0.1, 1.0]
  Reward: - |实际消耗 - 目标消耗| + RoAS 奖励

  优点：自适应，能处理流量波动
  缺点：需要大量训练数据和复杂实现
```

### 4.3 公平性 vs 收益最大化

```
问题：竞价系统如何平衡广告主公平性和平台收益？

方案：引入多样性约束 (Diversity Constraint)

  目标函数：
    max Σ (eCPM_i × x_i)  -- 收益最大化
    s.t.  Σ x_i ≤ k       -- 每轮最多展示 k 个广告
          diversity(x) ≥ D  -- 多样性约束
          budget_pacing(x) ≤ B  -- 预算消耗约束

  Diversity 度量：
    diversity(x) = 1 - Σ (ad_category_i 的广告占比)²
    -- 避免同一行业/广告主占据所有广告位
```

---

## 5. 广告平台 API 对比

### 5.1 Google Ads API

```
架构: RESTful + gRPC
端点: https://googleads.googleapis.com/v16/customers/{customer_id}

认证: OAuth2 + Developer Token
限流: 1000 RPM per customer
数据回流: Conversion Upload API

核心资源:
  - Campaign: 广告系列
  - AdGroup: 广告组
  - Ad: 广告创意
  - Keyword: 关键词
  - BidStrategy: 出价策略
  - CustomerClient: 代理商结构

示例查询 (GraphQL):
  GET /customers/123/report
  {
    "query": """
      SELECT campaign.name, metrics.clicks, metrics.costMicros
      FROM campaign
      WHERE segments.date DURING LAST_30_DAYS
    """
  }

特点:
  ✅ 功能最全，覆盖所有广告产品
  ✅ 支持 PMax (Performance Max) 自动化
  ✅ 数据粒度细（可下到关键词级别）
  ❌ API 限制严格（1000 RPM）
  ❌ 学习曲线陡峭
```

### 5.2 Meta Marketing API

```
架构: RESTful
端点: https://graph.facebook.com/v18.0/
认证: OAuth2 (Page Access Token)
限流: 基于 app 的 Rate Limit

核心资源:
  - ad_account: 广告账户
  - campaign: 广告系列
  - ad_set: 广告组
  - ad: 广告创意
  - conversion_event: 转化事件
  - pixel: 像素追踪

Advantage+ 投放 API:
  POST /v18.0/{ad_account_id}/campaigns
  {
    "name": "Advantage+ Shopping Campaign",
    "objective": "SALES",
    "special_ad_categories": [],
    "promotion_status": "ACTIVE",
    "daily_budget": 5000,  // 单位: 最小货币单位
    "campaign_group_status": "ACTIVE",
    "special_ad_category": "NONE"
  }

事件追踪:
  - 基础事件: PageView, ViewContent, AddToCart, Purchase
  - 自定义事件: 通过 Conversion API 上报
  - 转化窗口: 7天点击 / 1天浏览

特点:
  ✅ Advantage+ 自动化投放效果好
  ✅ 社交属性强，适合品牌广告
  ❌ 隐私政策变化影响数据质量 (iOS ATT)
  ❌ Conversion API 配置复杂
```

### 5.3 TikTok Ads API

```
架构: RESTful
端点: https://business-api.tiktok.com/portal/
认证: OAuth2 (Access Token + App Secret)
限流: 50 RPS per app

核心资源:
  - ad_account: 广告账户
  - campaign: 广告系列
  - adgroup: 广告组
  - creative: 创意素材
  - event: 事件追踪

Spark Ads (达人广告):
  POST /open_api/v2/spark/ad/
  {
    "ad_account_id": 123456,
    "campaign_id": 789012,
    "adgroup_id": 345678,
    "creator_ids": [987654],
    "creative_type": "SPARK"
  }

事件追踪 (TikTok Pixel + SDK):
  - 基础事件: PageVisit, Search, ProductView, AddToCart, CheckoutStart, Purchase
  - 自定义参数: 商品 ID、金额、分类
  - 归因窗口: 7天点击 / 1天浏览

特点:
  ✅ 短视频内容原生性强
  ✅ 年轻用户群体
  ❌ API 文档更新慢
  ❌ 数据延迟较高（2-4 小时）
```

### 5.4 DV360 (Google Display & Video 360)

```
架构: OAuth2 + RTB
端点: DV360 API + OpenRTB 2.5
认证: OAuth2 (Service Account)

核心功能:
  - Programmatic 程序化购买
  - RTB 竞价 (OpenRTB)
  - 私有交易市场 (PMP/PPI)
  - 保底购买 (Guarified)
  - 跨屏投放
  - 品牌安全 (品牌视图)

OpenRTB Bid Response 示例:
  {
    "id": "bid-response-123",
    "seatbid": [{
      "bid": [{
        "id": "bid-001",
        "impid": "imp-001",
        "price": 3.5,
        "cur": "USD",
        "crid": "creative-123",
        "adm": "<iframe>...</iframe>",
        "api": 2,
        "protocol": 2,
        "ext": {
          "dv360": {
            "buyerBidCreativeId": "dv-creative-123",
            "lineItemId": "dv-line-456"
          }
        }
      }]
    }],
    "bidid": "bid-id-789"
  }

特点:
  ✅ 企业级程序化购买平台
  ✅ 覆盖全球 Ad Exchange
  ✅ 品牌安全工具链完整
  ❌ 需要 Google 代理商认证
  ❌ 学习成本极高
```

### 5.5 API 对比总结

| 维度 | Google Ads | Meta | TikTok | DV360 |
|------|-----------|------|--------|-------|
| **认证方式** | OAuth2 + Dev Token | OAuth2 | OAuth2 | OAuth2 + Service Account |
| **限流** | 1000 RPM | App 级 | 50 RPS | 根据配额 |
| **数据粒度** | 关键词级 | 广告组级 | 广告组级 | RTB 级 |
| **归因窗口** | 30天点击/7天浏览 | 28天点击/1天浏览 | 7天点击/1天浏览 | 可自定义 |
| **自动化** | PMax | Advantage+ | Smart Bidding | 算法优化 |
| **最适合** | 搜索/搜索展示 | 社交/品牌 | 短视频/年轻用户 | 程序化购买 |

---

*本文档基于广告行业通用知识整理，适用于有基础的工程师*
