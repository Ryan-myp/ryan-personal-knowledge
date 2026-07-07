# 在线广告系统深度实战：从架构到算法

## 一、在线广告发展简史

### 1.1 广告演进历程

```
传统广告时代 (1990s以前):
├── 报纸/杂志/广播/电视
├── 固定时段/版面
└── 单向传播，无法追踪效果

互联网广告时代 (1990s-2000s):
├── Banner广告
├── 搜索广告 (Google AdWords 2000)
├── 按展示/点击付费
└── 初步的效果追踪

程序化广告时代 (2010s至今):
├── RTB实时竞价
├── 精准定向
├── 智能出价
└── 全链路自动化
```

### 1.2 关键时间节点

| 年份 | 事件 | 影响 |
|------|------|------|
| 1994 | HotWired推出首个Banner广告 | 在线广告诞生 |
| 2000 | Google推出AdWords | 搜索广告时代 |
| 2005 | YouTube上线 | 视频广告兴起 |
| 2007 | Facebook IPO | 社交广告时代 |
| 2010 | RTB技术成熟 | 程序化购买爆发 |
| 2012 | Mobile Growth | 移动广告崛起 |
| 2016 | AI in Advertising | 智能出价/创意 |

## 二、广告系统架构流程

### 2.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                        Ad Request                           │
│                  (用户访问网页/App)                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ad Server (广告服务器)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ 用户画像  │  │ 上下文   │  │ 库存查询  │                  │
│  │ (User    │  │ 分析     │  │ (Inventory│                  │
│  │ Profile) │  │ (Context)│  │ Check)   │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 Ad Exchange (广告交换平台)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Real-Time Bidding (RTB)                │    │
│  │                                                     │    │
│  │  DSP1 ◄─────────────────────────────────────────►  │    │
│  │  DSP2 ◄─────────────────────────────────────────►  │    │
│  │  DSP3 ◄─────────────────────────────────────────►  │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ad Delivery (广告展示)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ 创意渲染  │  │ 追踪埋点  │  │ 数据上报  │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 关键流程详解

**1. 广告请求 (Ad Request):**
```
请求包含:
├── 用户信息: UserID, DeviceID, Location
├── 页面信息: URL, Category, Content
├── 广告位: SlotID, Width, Height, Position
└── 时间: Timestamp, Timezone
```

**2. 用户画像匹配 (User Profiling):**
```go
type UserProfile struct {
    UserID      string
    Demographics map[string]interface{}
    Interests   []string
    Behaviors   []BehaviorEvent
    Lookalike   []string
}

type BehaviorEvent struct {
    EventType string
    Timestamp time.Time
    Context   map[string]interface{}
}
```

**3. 实时竞价 (RTB):**
```
竞价流程 (毫秒级):
1. Ad Exchange 发送 Bid Request
2. DSP 获取用户画像和上下文
3. DSP 计算出价 (基于 CTR/CVR 预测)
4. Ad Exchange 选择最高出价
5. 返回 Winner Ad
6. 广告展示 + 追踪
```

## 三、品牌广告 vs 效果广告

### 3.1 品牌广告 (Brand Ads)

**特点：**
- 目标：品牌曝光、认知度提升
- 计费：CPM (千次展示)
- 创意：高质量视频/图文
- 定向：兴趣、人口统计

**典型场景：**
- 新品发布
- 品牌形象塑造
- 市场份额争夺

### 3.2 效果广告 (Performance Ads)

**特点：**
- 目标：转化、销售、留资
- 计费：CPC/CPA/CPI
- 创意：直接、行动导向
- 定向：行为、意图

**典型场景：**
- 电商促销
- App下载
- 线索收集

## 四、用户数据和定向算法

### 4.1 用户画像构建

```
用户画像数据来源:
├── 第一方数据 (First-party)
│   ├── 用户注册信息
│   ├── 浏览行为
│   ├── 购买历史
│   └── 互动数据
├── 第二方数据 (Second-party)
│   ├── 合作伙伴数据
│   └── 平台共享数据
└── 第三方数据 (Third-party)
    ├── DMP数据
    ├── 数据经纪公司
    └── 公开数据
```

### 4.2 定向策略

| 定向类型 | 说明 | 示例 |
|----------|------|------|
| 人口统计 | 年龄、性别、地域 | 25-34岁女性，一线城市 |
| 兴趣标签 | 用户兴趣分类 | 科技、时尚、美食 |
| 行为定向 | 浏览/购买行为 | 最近30天浏览过手机 |
| 再营销 | 曾互动过的用户 | 网站访客、App用户 |
| 类似受众 | 相似特征的用户 | 高价值用户相似人群 |
| 上下文定向 | 页面内容相关 | 科技文章旁投放数码广告 |

## 五、点击率预估与推荐算法

### 5.1 CTR预估模型演进

```
LR (逻辑回归) → Factorization Machines → DeepFM → DIN → MMOE
```

**各阶段特点：**

| 模型 | 年份 | 特点 | 适用场景 |
|------|------|------|----------|
| LR | 早期 | 线性模型，简单高效 | 基线模型 |
| FM | 2010 | 特征交叉，稀疏数据 | 推荐系统 |
| DeepFM | 2017 | 深度+因子分解 | 点击率预估 |
| DIN | 2018 | 注意力机制 | 用户行为序列 |
| MMOE | 2018 | 多任务学习 | 多目标优化 |

### 5.2 Go 实现简易 CTR 预估

```go
package ctr

import (
	"math"
	"sort"
)

// Feature 特征
type Feature struct {
	Name  string
	Value float64
}

// UserFeatures 用户特征
type UserFeatures struct {
	Demographics map[string]interface{}
	Interests    []string
	Behaviors    []Behavior
}

// AdFeatures 广告特征
type AdFeatures struct {
	Category   string
	Brand      string
	CreativeID string
}

// ContextFeatures 上下文特征
type ContextFeatures struct {
	Placement string
	Device    string
	Location  string
}

// CTRPredictor CTR 预测器
type CTRPredictor struct {
	weights map[string]float64
	bias    float64
}

func NewCTRPredictor() *CTRPredictor {
	return &CTRPredictor{
		weights: map[string]float64{
			"user_age":    0.1,
			"user_gender": 0.05,
			"ad_category": 0.2,
			"placement":   0.15,
		},
		bias: 0.02,
	}
}

func (p *CTRPredictor) Predict(user, ad, context interface{}) float64 {
	// 简化实现，实际应使用训练好的模型
	score := p.bias
	
	// 用户特征权重
	if uf, ok := user.(UserFeatures); ok {
		if age, hasAge := uf.Demographics["age"]; hasAge {
			if age == "25-34" {
				score += p.weights["user_age"] * 0.8
			}
		}
	}
	
	// 广告特征权重
	if af, ok := ad.(AdFeatures); ok {
		if af.Category == "electronics" {
			score += p.weights["ad_category"] * 0.9
		}
	}
	
	// 上下文特征权重
	if cf, ok := context.(ContextFeatures); ok {
		if cf.Placement == "feed" {
			score += p.weights["placement"] * 0.7
		}
	}
	
	// Sigmoid 激活
	return 1.0 / (1.0 + math.Exp(-score*10))
}
```

## 六、在线匹配与机制设计

### 6.1 广告匹配策略

```
匹配流程:
1. 候选集召回 (Candidate Retrieval)
   ├── 基于用户兴趣召回
   ├── 基于广告分类召回
   └── 基于协同过滤召回

2. 粗排 (Pre-ranking)
   └── 快速筛选 Top-K

3. 精排 (Ranking)
   └── 精确 CTR/CVR 预估

4. 重排 (Re-ranking)
   ├── 多样性控制
   ├── 频次控制
   └── 业务规则
```

### 6.2 拍卖机制

| 机制 | 说明 | 特点 |
|------|------|------|
| 第一价格拍卖 | 最高出价者按出价支付 | 简单，但策略复杂 |
| 第二价格拍卖 | 最高出价者按第二高出价支付 | VCG机制， truthful |
| GSP | 广义第二价格 | Google/Facebook使用 |
| VCG | Vickrey-Clarke-Groves | 理论最优，实现复杂 |

## 七、低质量和敏感控制

### 7.1 广告质量评估

```
质量维度:
├── 相关性 (Relevance)
│   ├── 广告与用户兴趣匹配度
│   └── 广告与页面内容匹配度
├── 创意质量 (Creative Quality)
│   ├── 图片/视频清晰度
│   └── 文案吸引力
├── 落地页体验 (Landing Page)
│   ├── 加载速度
│   ├── 移动端适配
│   └── 转化率
└── 用户体验 (User Experience)
    ├── 广告密度
    ├── 广告类型
    └── 打扰程度
```

### 7.2 反作弊策略

```
作弊类型:
├── 流量作弊 (Traffic Fraud)
│   ├── 机器人流量
│   ├── 点击农场
│   └── 设备农场
├── 归因作弊 (Attribution Fraud)
│   ├── 非法归因
│   └── 点击注入
└── 创意作弊 (Creative Fraud)
    ├── 盗用创意
    └── 恶意链接

防御策略:
├── 设备指纹
├── IP信誉
├── 行为分析
├── 机器学习检测
└── 人工审核
```

## 八、实验架构和调参

### 8.1 A/B 测试框架

```
实验设计:
1. 假设提出 (Hypothesis)
2. 样本量计算 (Sample Size)
3. 随机分组 (Randomization)
4. 实验运行 (Experiment)
5. 结果分析 (Analysis)
6. 决策 (Decision)

关键指标:
├── 统计显著性 (Statistical Significance)
├── 效应量 (Effect Size)
├── 置信区间 (Confidence Interval)
└── 多重检验校正 (Multiple Testing Correction)
```

### 8.2 Go 实现简易 A/B 测试

```go
package abtest

import (
	"math"
	"math/rand"
	"time"
)

type ABTest struct {
	Name        string
	Variants    []string
	Weights     []float64
	Experiment  *Experiment
}

type Experiment struct {
	GroupA []UserMetric
	GroupB []UserMetric
}

type UserMetric struct {
	UserID    string
	Converted bool
	Value     float64
}

func (t *ABTest) Assign(userID string) string {
	// 确定性分配
	hash := hash(userID)
	normalized := float64(hash%1000) / 1000.0
	
	cumulative := 0.0
	for i, weight := range t.Weights {
		cumulative += weight
		if normalized < cumulative {
			return t.Variants[i]
		}
	}
	return t.Variants[len(t.Variants)-1]
}

func (t *ABTest) Analyze() (float64, bool) {
	// 计算转化率
	convertedA := countConverted(t.Experiment.GroupA)
	totalA := len(t.Experiment.GroupA)
	convertedB := countConverted(t.Experiment.GroupB)
	totalB := len(t.Experiment.GroupB)
	
	ctrA := float64(convertedA) / float64(totalA)
	ctrB := float64(convertedB) / float64(totalB)
	
	// Z-test
	zScore := calculateZScore(convertedA, totalA, convertedB, totalB)
	pValue := 2 * (1 - normalCDF(math.Abs(zScore)))
	
	significant := pValue < 0.05
	return pValue, significant
}

func countConverted(metrics []UserMetric) int {
	count := 0
	for _, m := range metrics {
		if m.Converted {
			count++
		}
	}
	return count
}

func calculateZScore(convA, totalA, convB, totalB int) float64 {
	p1 := float64(convA) / float64(totalA)
	p2 := float64(convB) / float64(totalB)
	p := float64(convA + convB) / float64(totalA + totalB)
	
	se := math.Sqrt(p * (1 - p) * (1.0/float64(totalA) + 1.0/float64(totalB)))
	if se == 0 {
		return 0
	}
	return (p1 - p2) / se
}

func normalCDF(x float64) float64 {
	// 近似正态分布 CDF
	return 0.5 * (1.0 + erf(x/math.Sqrt(2)))
}

func erf(x float64) float64 {
	// 近似误差函数
	a1 := 0.254829592
	a2 := -0.284496736
	a3 := 1.421413741
	a4 := -1.453152027
	a5 := 1.061405429
	p := 0.3275911
	
	sign := 1.0
	if x < 0 {
		sign = -1
	}
	x = math.Abs(x)
	
	t := 1.0 / (1.0 + p*x)
	y := 1.0 - (((((a5*t+a4)*t)+a3)*t+a2)*t+a1)*t*math.Exp(-x*x)
	
	return sign * y
}

func hash(s string) uint32 {
	h := uint32(0)
	for _, c := range s {
		h = 31*h + uint32(c)
	}
	return h
}
```

## 九、数据监测和效果衡量

### 9.1 关键指标

| 指标 | 公式 | 意义 |
|------|------|------|
| CTR | 点击数/展示数 | 广告吸引力 |
| CVR | 转化数/点击数 | 落地页效果 |
| CPC | 花费/点击数 | 获客成本 |
| CPA | 花费/转化数 | 转化成本 |
| ROAS | 收入/花费 | 投资回报率 |
| eCPM | (花费/展示数)*1000 | 千次展示收益 |

### 9.2 归因模型

```
归因模型对比:
├── Last Click
│   └── 最后点击获得100% credit
├── First Click
│   └── 首次点击获得100% credit
├── Linear
│   └── 所有触点平分 credit
├── Time Decay
│   └── 越接近转化 credit 越高
├── Position Based
│   └── 首尾各40%，中间平分20%
└── Data-Driven
    └── 基于实际数据分配 credit
```

## 十、在线广告发展趋势

### 10.1 技术趋势

```
未来方向:
├── AI/ML 驱动
│   ├── 智能出价
│   ├── 创意生成
│   └── 受众预测
├── 隐私保护
│   ├── 无Cookie时代
│   ├── 联邦学习
│   └── 差分隐私
├── 跨屏投放
│   ├── 移动端优先
│   ├── OTT/CTV
│   └── 智能家居
└── 新兴平台
    ├── 短视频广告
    ├── 直播电商
    └── 元宇宙广告
```

### 10.2 业务趋势

```
业务变化:
├── 从流量思维到留量思维
├── 从单次交易到用户生命周期价值
├── 从粗放投放到精细化运营
└── 从人工优化到AI自动化
```

## 十一、自测题

1. 在线广告系统的核心组件有哪些？
2. CTR预估模型经历了哪些演进？
3. 如何进行有效的A/B测试？
4. 常见的归因模型有哪些？各有什么优缺点？

## 十二、动手验证

```bash
# 1. 实现简易CTR预测器
# 2. 实现A/B测试分析
# 3. 实现归因分析
# 4. 使用真实数据训练模型
```
