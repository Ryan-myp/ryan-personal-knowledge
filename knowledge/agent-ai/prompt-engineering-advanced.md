# AI 实战：Prompt Engineering 技巧

> Prompt 设计/ Few-shot/CoT/ReAct/结构化输出

---

## 第一部分：入门引导（5 分钟速览）

### 为什么需要 Prompt Engineering？

广告平台用 LLM 做：
- **创意生成**：批量生成广告文案
- **意图识别**：理解用户搜索意图
- **分类打标**：广告分类、内容审核
- **问答系统**：广告策略智能问答

### Prompt 设计原则

```
❌ 差的 Prompt：
"帮我写个广告文案"

✅ 好的 Prompt：
你是一名广告文案专家。请为以下产品生成3条广告文案：
产品：运动鞋
目标受众：25-35岁男性
特点：轻便、透气、减震
语气：活力、专业
限制：每条不超过20字
```

---

## 第二部分：Few-shot Learning

### 2.1 Few-shot 示例

```
用户意图识别 Prompt：

请识别用户搜索意图，分类为：购买、浏览、比较、技术支持

示例：
搜索："iPhone 15 多少钱"
意图：购买

搜索："iPhone 15 和 14 区别"
意图：比较

搜索："iPhone 15 哪里买"
意图：购买

搜索："iPhone 15 防水吗"
意图：技术支持

用户搜索："运动鞋推荐"
意图：？
```

### 2.2 Go 实现 Few-shot

```go
package prompt

import (
    "strings"
)

type FewShotPrompt struct {
    template string
    examples []Example
}

type Example struct {
    Input  string
    Output string
}

func (p *FewShotPrompt) Build(input string) string {
    sb := strings.Builder{}
    
    // 添加模板
    sb.WriteString(p.template)
    sb.WriteString("\n\n")
    
    // 添加示例
    for _, ex := range p.examples {
        sb.WriteString(fmt.Sprintf("输入: %s\n输出: %s\n\n", ex.Input, ex.Output))
    }
    
    // 添加当前输入
    sb.WriteString(fmt.Sprintf("输入: %s\n输出: ", input))
    
    return sb.String()
}
```

---

## 第三部分：Chain of Thought (CoT)

### 3.1 CoT 原理

```
传统 Prompt：
问题：10个苹果，吃掉3个，又买了5个，现在有几个？
答案：12

CoT Prompt：
问题：10个苹果，吃掉3个，又买了5个，现在有几个？
思考过程：
1. 原有 10 个苹果
2. 吃掉 3 个，剩下 7 个
3. 又买了 5 个，现在有 12 个
答案：12
```

### 3.2 Go 实现 CoT

```go
type CoTPrompt struct {
    question string
}

func (p *CoTPrompt) Build() string {
    return fmt.Sprintf(`请逐步思考以下问题：

问题: %s

思考过程:
1. 

请按照以上格式回答问题。`, p.question)
}

// 广告竞价 CoT 示例
func BidCoTPrompt(req *BidRequest) string {
    return fmt.Sprintf(`请逐步思考竞价策略：

用户: %s
预算: %.2f
历史CTR: %.4f
历史CVR: %.4f

思考过程:
1. 分析用户价值...
2. 评估广告相关性...
3. 计算期望出价...

最终出价: `, req.UserID, req.Budget, req.CTR, req.CVR)
}
```

---

## 第四部分：ReAct 模式

### 4.1 ReAct 原理

```
ReAct = Reason + Act

Thought: 我需要查找这个用户的广告历史
Action: search_ad_history(user_id=123)
Observation: 用户最近点击了3个运动品牌广告
Thought: 用户可能对运动品牌感兴趣
Action: generate_creative(category=sports)
Observation: 生成了3条运动品牌创意
Thought: 创意生成完成
Final Answer: 推荐运动品牌创意
```

### 4.2 Go 实现 ReAct

```go
package react

import (
    "context"
)

type ReActEngine struct {
    llm       *LLMClient
    tools     []Tool
    maxSteps  int
}

type Tool struct {
    Name        string
    Description string
    Execute     func(context.Context, string) (string, error)
}

type ReActStep struct {
    Thought    string
    Action     string
    Observation string
}

func (eng *ReActEngine) Solve(ctx context.Context, query string) (string, error) {
    steps := make([]ReActStep, 0)
    
    for i := 0; i < eng.maxSteps; i++ {
        // 构建 prompt
        prompt := eng.buildReActPrompt(query, steps)
        
        // LLM 生成下一步
        response, err := eng.llm.Generate(ctx, prompt)
        if err != nil {
            return "", err
        }
        
        // 解析响应
        step, err := eng.parseStep(response)
        if err != nil {
            return "", err
        }
        
        steps = append(steps, step)
        
        // 检查是否是最终答案
        if step.Action == "Final Answer" {
            return step.Observation, nil
        }
        
        // 执行工具
        result, err := eng.executeTool(step.Action)
        if err != nil {
            return "", err
        }
        
        step.Observation = result
    }
    
    return "", fmt.Errorf("max steps reached")
}
```

---

## 第五部分：结构化输出

### 5.1 JSON Schema 约束

```
请根据以下 Schema 生成 JSON：

{
  "type": "object",
  "properties": {
    "campaign_name": {"type": "string"},
    "budget": {"type": "number"},
    "target_audience": {"type": "array", "items": {"type": "string"}},
    "creatives": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "headline": {"type": "string"},
          "body": {"type": "string"},
          "url": {"type": "string"}
        }
      }
    }
  },
  "required": ["campaign_name", "budget", "creatives"]
}

产品：运动鞋
目标：生成广告方案
```

### 5.2 Go 解析

```go
type AdCampaign struct {
    CampaignName  string   `json:"campaign_name"`
    Budget        float64  `json:"budget"`
    TargetAudience []string `json:"target_audience"`
    Creatives     []Creative `json:"creatives"`
}

type Creative struct {
    Headline string `json:"headline"`
    Body     string `json:"body"`
    URL      string `json:"url"`
}

func parseAdCampaign(response string) (*AdCampaign, error) {
    var campaign AdCampaign
    err := json.Unmarshal([]byte(response), &campaign)
    return &campaign, err
}
```

---

## 第六部分：自测题

### 问题 1
Few-shot Learning 为什么有效？

<details>
<summary>查看答案</summary>

1. **模式学习**：LLM 从示例中学习模式
2. **上下文窗口**：现代 LLM 支持大量上下文
3. **泛化能力**：少量示例即可泛化
4. **广告场景**：意图识别、分类打标
5. **Go 实现**：FewShotPrompt.Build()

</details>

### 问题 2
CoT 相比直接回答有什么优势？

<details>
<summary>查看答案</summary>

1. **推理能力**：逐步推理提高准确性
2. **可解释性**：可以看到思考过程
3. **复杂问题**：适合多步推理
4. **广告场景**：竞价策略、预算分配
5. **Limitation**：增加 token 消耗

</details>

### 问题 3
ReAct 相比纯 Prompt 有什么优势？

<details>
<summary>查看答案</summary>

1. **工具调用**：可以调用外部工具
2. **观察反馈**：根据观察调整策略
3. **复杂任务**：适合多步骤任务
4. **广告场景**：创意生成 + 审核
5. **Go 实现**：ReActEngine

</details>

---

*本文档基于 AI Prompt 工程整理。*