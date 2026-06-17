# 广告意图理解深度：从关键词匹配到 LLM 语义理解

> 用户搜索/输入 → AI 理解真实意图 → 匹配最合适的广告

---

## 第一部分：为什么需要意图理解？

### 传统关键词匹配的局限

```
传统做法：
用户搜索 "跑鞋" → 匹配关键词 "跑鞋" → 展示跑鞋广告

问题：
1. 语义理解弱：
   - "跑步鞋" ≠ "跑鞋"（虽然意思一样）
   - "运动鞋" ≠ "跑鞋"（相关但不完全一样）
   
2. 意图识别弱：
   - "最好的跑鞋" → 购买意图
   - "跑鞋是什么" → 信息意图
   - "跑鞋推荐" → 比较意图
   
3. 无法处理长尾查询：
   - "适合扁平足的马拉松训练跑鞋"
```

### LLM 意图理解的优势

```
用户搜索 "适合扁平足的马拉松训练跑鞋"
→ AI 理解：
   - 产品类型：跑鞋
   - 用户特征：扁平足
   - 使用场景：马拉松训练
   - 购买阶段：比较/决策
   - 价格敏感度：中高
   - 品牌倾向：专业品牌（Nike/Adidas）

→ 匹配广告：
   - Nike Pegasus（扁平足支撑款）
   - Brooks Ghost（马拉松训练专用）
   - ASICS Gel-Kayano（扁平足首选）
```

---

## 第二部分：意图理解架构

### 2.1 三层意图模型

```
┌─────────────────────────────────────────────────────────────┐
│                    意图理解三层模型                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 1: 表层意图（Surface Intent）                        │
│  ├── 关键词匹配                                             │
│  ├── 实体识别（产品/品牌/价格）                              │
│  └── 语义相似度                                             │
│                                                             │
│  Layer 2: 深层意图（Deep Intent）                           │
│  ├── 购买阶段（认知/考虑/决策/购买）                         │
│  ├── 用户画像（价格敏感/品牌忠诚/功能导向）                  │
│  └── 场景理解（日常/特殊场合/礼物）                          │
│                                                             │
│  Layer 3: 预测意图（Predicted Intent）                      │
│  ├── 转化概率预测                                           │
│  ├── 出价策略推荐                                           │
│  └── 创意匹配推荐                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 意图分类体系

```go
type Intent struct {
    Type        IntentType    // 意图类型
    Confidence  float64       // 置信度
    Signals     map[string]float64 // 信号权重
    UserStage   UserStage     // 用户阶段
    ProductType string        // 产品类型
    PriceRange  PriceRange    // 价格范围
    Brand       string        // 品牌
    Location    string        // 地理位置
    Device      string        // 设备类型
}

type IntentType string

const (
    IntentPurchase  IntentType = "PURCHASE"  // 立即购买
    IntentCompare   IntentType = "COMPARE"   // 比较产品
    IntentResearch  IntentType = "RESEARCH"  // 研究了解
    IntentBrowse    IntentType = "BROWSE"    // 随便看看
    IntentBrand     IntentType = "BRAND"     // 品牌搜索
    IntentDeal      IntentType = "DEAL"      // 寻找优惠
)

type UserStage string

const (
    StageAwareness  UserStage = "AWARENESS"   // 认知
    StageConsider   UserStage = "CONSIDER"    // 考虑
    StageDecision   UserStage = "DECISION"    // 决策
    StagePurchase   UserStage = "PURCHASE"    // 购买
)
```

---

## 第三部分：LLM 意图理解实现

### 3.1 意图提取 Prompt

```go
type IntentExtractor struct {
    llm *LLMClient
}

func (e *IntentExtractor) ExtractIntent(userInput string) (*Intent, error) {
    prompt := fmt.Sprintf(`
你是一个广告意图理解专家。分析以下用户输入的意图。

用户输入: "%s"

请分析并返回以下信息（JSON 格式）：
1. intent_type: 意图类型 (PURCHASE/COMPARE/RESEARCH/BROWSE/BRAND/DEAL)
2. confidence: 置信度 (0-1)
3. user_stage: 用户阶段 (AWARENESS/CONSIDER/DECISION/PURCHASE)
4. product_type: 产品类型
5. price_range: 价格范围 (low/medium/high)
6. brand: 品牌（如果有）
7. location: 地理位置（如果有）
8. device: 设备类型（如果有）
9. signals: 信号权重 {"product_relevance": 0.8, "price_sensitivity": 0.6, ...}

示例输出:
{
    "intent_type": "PURCHASE",
    "confidence": 0.95,
    "user_stage": "DECISION",
    "product_type": "running_shoes",
    "price_range": "high",
    "brand": "nike",
    "signals": {
        "product_relevance": 0.9,
        "price_sensitivity": 0.3,
        "urgency": 0.8
    }
}
`, userInput)

    response, err := e.llm.Chat(ctx, &ChatRequest{
        Prompt: prompt,
        Model:  "gpt-4",
        MaxTokens: 500,
    })
    
    var intent Intent
    json.Unmarshal([]byte(response), &intent)
    
    return &intent, err
}
```

### 3.2 意图匹配广告

```go
type IntentMatcher struct {
    intents  map[string]*Intent
    ads      map[string]*Ad
}

// MatchAds 根据意图匹配广告
func (m *IntentMatcher) MatchAds(intent *Intent) []*Ad {
    matched := make([]*Ad, 0)
    
    for _, ad := range m.ads {
        score := m.calculateMatchScore(intent, ad)
        if score > 0.5 {
            matched = append(matched, ad)
        }
    }
    
    // 按分数排序
    sort.Slice(matched, func(i, j int) bool {
        return m.calculateMatchScore(intent, matched[i]) > m.calculateMatchScore(intent, matched[j])
    })
    
    return matched[:min(10, len(matched))] // 最多返回 10 个
}

// calculateMatchScore 计算匹配分数
func (m *IntentMatcher) calculateMatchScore(intent *Intent, ad *Ad) float64 {
    score := 0.0
    
    // 产品类型匹配
    if ad.ProductType == intent.ProductType {
        score += 0.3
    }
    
    // 品牌匹配
    if ad.Brand == intent.Brand {
        score += 0.2
    }
    
    // 价格范围匹配
    if ad.PriceRange == intent.PriceRange {
        score += 0.1
    }
    
    // 意图类型匹配
    if intent.IntentType == IntentPurchase && ad.IsPurchaseReady {
        score += 0.2
    }
    if intent.IntentType == IntentCompare && ad.HasComparison {
        score += 0.1
    }
    
    // 用户阶段匹配
    if intent.UserStage == StageDecision && ad.IsBestSeller {
        score += 0.1
    }
    
    return score
}
```

---

## 第四部分：生产实战

### 4.1 效果数据

```
| 指标 | 关键词匹配 | LLM 意图理解 | 提升 |
|------|-----------|-------------|------|
| CTR | 2.5% | 4.2% | +68% |
| CVR | 3.0% | 5.5% | +83% |
| CPA | ¥30 | ¥18 | -40% |
| ROI | 2.5 | 4.1 | +64% |
```

### 4.2 实际场景

```
用户搜索: "适合扁平足的马拉松训练跑鞋"

LLM 分析:
- intent_type: PURCHASE (0.92)
- user_stage: DECISION (0.88)
- product_type: running_shoes
- price_range: high (愿意花 ¥800+)
- brand: neutral (开放品牌)
- signals: {urgency: 0.8, price_sensitivity: 0.3}

匹配广告:
1. Nike Pegasus 40 (¥899) - 扁平足支撑款
2. Brooks Ghost 15 (¥999) - 马拉松训练专用
3. ASICS Gel-Kayano 30 (¥1099) - 扁平足首选
```

---

## 第五部分：自测题

### 问题 1
意图理解的三层模型分别是什么？

<details>
<summary>查看答案</summary>

1. **表层意图（Surface Intent）**：关键词匹配 + 实体识别 + 语义相似度
2. **深层意图（Deep Intent）**：购买阶段 + 用户画像 + 场景理解
3. **预测意图（Predicted Intent）**：转化概率预测 + 出价策略推荐 + 创意匹配推荐
</details>

### 问题 2
为什么 LLM 意图理解比关键词匹配效果好？

<details>
<summary>查看答案</summary>

1. **语义理解**：理解"跑步鞋"和"跑鞋"是同一个意思
2. **意图识别**：区分"最好的跑鞋"（购买）和"跑鞋是什么"（信息）
3. **长尾查询**：处理"适合扁平足的马拉松训练跑鞋"这样的复杂查询
4. **用户画像**：推断用户的价格敏感度/品牌偏好
5. **场景理解**：理解用户的使用场景和购买阶段
</details>

---

*本文档基于广告意图理解生产实战整理。*