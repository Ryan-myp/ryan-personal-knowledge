# 广告 Agent 深度：AI 优化师/智能投放/自动调参

> LLM Agent 在广告平台中的落地应用 + AutoML + 智能优化

---

## 第一部分：为什么广告需要 Agent？

### 广告运营的痛点

```
传统广告投放：
→ 广告主手动设置定向、出价、预算
→ 需要专业优化师（薪资 15-30K/月）
→ 一个人管 10-20 个广告组
→ 调整不及时，错过最佳时机

AI Agent 投放：
→ 自动设置定向、出价、预算
→ 7×24 小时实时监控和调整
→ 一个人可以管 1000+ 广告组
→ 秒级响应，抓住每一个机会
```

### Agent 的价值

```
1. 降本增效：
   → 减少优化师人力成本 80%
   → 广告主 ROI 提升 20-40%

2. 精准优化：
   → 基于海量数据训练
   → 发现人类看不到的规律
   → 实时调整策略

3. 个性化服务：
   → 每个广告主都有专属 AI 优化师
   → 根据行业/品类/预算定制策略
   → 自动 A/B 测试最佳方案
```

---

## 第二部分：广告 Agent 架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    广告 Agent 平台                            │
└─────────────────────────────────────────────────────────────┘

                    ┌───────────────────────────────────────┐
                    │         LLM API (GPT-4/Claude)        │
                    │  - 自然语言理解                         │
                    │  - 策略生成                             │
                    │  - 报告解读                             │
                    └──────────────┬────────────────────────┘
                                   │
                    ┌──────────────▼────────────────────────┐
                    │       Agent Orchestrator               │
                    │  - 工具调用 (ReAct)                     │
                    │  - 记忆管理                              │
                    │  - 规划 (Planning)                      │
                    └──────┬──────────┬──────────┬──────────┘
                           │          │          │
              ┌────────────▼──┐ ┌─────▼────┐ ┌───▼────────┐
              │  数据分析工具  │ │ 投放工具  │ │ 创意工具   │
              │ - 报表查询    │ │ - 调价   │ │ - 素材生成 │
              │ - 归因分析    │ │ - 定向   │ │ - A/B 测试 │
              │ - 竞品分析    │ │ - 预算   │ │ - 文案生成 │
              └───────────────┘ └──────────┘ └────────────┘
```

### 2.2 Agent 角色设计

```
1. 智能优化师 Agent：
   → 监控广告表现
   → 自动调整出价和预算
   → 发现异常并告警
   → 生成优化建议

2. 创意生成 Agent：
   → 根据产品信息生成文案
   → 自动生成图片/视频素材
   → A/B 测试最佳创意
   → 创意疲劳预警

3. 策略规划 Agent：
   → 制定投放策略
   → 预算分配优化
   → 竞品分析
   → 市场洞察

4. 客户服务 Agent：
   → 回答广告主问题
   → 指导操作流程
   → 处理投诉
   → 培训新手
```

---

## 第三部分：智能优化师 Agent

### 3.1 核心能力

```
1. 实时监控：
   → 每分钟检查所有广告组表现
   → 检测异常（CTR 骤降/CPA 飙升）
   → 自动触发优化动作

2. 自动调参：
   → 根据 CPA 目标自动调整出价
   → 根据预算消耗速度调整投放节奏
   → 根据时段效果调整 bids

3. 预算分配：
   → 自动将预算分配到高效广告组
   → 削减低效广告组预算
   → 预测未来消耗

4. 策略建议：
   → 生成周报/月报
   → 提出优化建议
   → 自动执行 approved 的建议
```

### 3.2 ReAct 模式实现

```go
package agent

import (
    "context"
    "fmt"
    "time"
)

// OptimizerAgent 智能优化师 Agent
type OptimizerAgent struct {
    llm         *LLMClient      // LLM 客户端
    tools       []Tool          // 可用工具
    memory      *MemoryStore    // 记忆存储
    planner     *Planner        // 规划器
}

// Tool 工具接口
type Tool interface {
    Name() string
    Description() string
    Execute(ctx context.Context, args map[string]interface{}) (interface{}, error)
}

// 工具列表
var OptimizerTools = []Tool{
    &GetAdPerformanceTool{},   // 获取广告表现
    &AdjustBidTool{},           // 调整出价
    &AdjustBudgetTool{},        // 调整预算
    &PauseAdTool{},             // 暂停广告
    &GenerateReportTool{},      // 生成报告
    &DetectAnomalyTool{},       // 异常检测
    &GetCompetitorTool{},       // 竞品分析
}

// ReActLoop ReAct 循环
func (a *OptimizerAgent) ReActLoop(ctx context.Context, goal string) error {
    // 初始化
    thought := goal
    iteration := 0
    maxIterations := 10
    
    for iteration < maxIterations {
        iteration++
        
        // 1. Thought: LLM 思考下一步
        response, err := a.llm.Chat(ctx, &ChatRequest{
            Messages: []Message{
                {Role: "system", Content: "你是广告优化师 Agent，使用工具达成目标。"},
                {Role: "user", Content: thought},
            },
            Tools: a.tools,
        })
        if err != nil {
            return err
        }
        
        // 2. Action: 如果有工具调用，执行工具
        if response.ToolCalls != nil {
            for _, call := range response.ToolCalls {
                tool := a.findTool(call.Function.Name)
                if tool == nil {
                    continue
                }
                
                args, _ := parseJSON(call.Function.Arguments)
                result, err := tool.Execute(ctx, args)
                if err != nil {
                    thought = fmt.Sprintf("工具 %s 执行失败: %v", call.Function.Name, err)
                    continue
                }
                
                // 将结果加入对话
                thought = fmt.Sprintf("工具 %s 返回结果: %v", call.Function.Name, result)
            }
        } else {
            // 3. Observation: LLM 根据结果生成下一步思考
            thought = response.Content
        }
        
        // 检查是否完成目标
        if a.isGoalAchieved(thought, goal) {
            fmt.Printf("✅ 目标达成: %s\n", goal)
            return nil
        }
    }
    
    return fmt.Errorf("达到最大迭代次数 %d", maxIterations)
}
```

### 3.3 工具实现

```go
// GetAdPerformanceTool 获取广告表现工具
type GetAdPerformanceTool struct{}

func (t *GetAdPerformanceTool) Name() string {
    return "get_ad_performance"
}

func (t *GetAdPerformanceTool) Description() string {
    return "获取广告组的表现数据，包括展示/点击/转化/消耗等指标"
}

func (t *GetAdPerformanceTool) Execute(ctx context.Context, args map[string]interface{}) (interface{}, error) {
    campaignID := args["campaign_id"].(string)
    days := args["days"].(int)
    
    // 查询数据库
    metrics, err := queryAdMetrics(campaignID, days)
    if err != nil {
        return nil, err
    }
    
    return map[string]interface{}{
        "campaign_id": campaignID,
        "days":        days,
        "impressions": metrics.Impressions,
        "clicks":      metrics.Clicks,
        "conversions": metrics.Conversions,
        "spend":       metrics.Spend,
        "ctr":         metrics.CTR,
        "cpc":         metrics.CPC,
        "cpa":         metrics.CPA,
        "roas":        metrics.ROAS,
    }, nil
}

// AdjustBidTool 调整出价工具
type AdjustBidTool struct{}

func (t *AdjustBidTool) Name() string {
    return "adjust_bid"
}

func (t *AdjustBidTool) Description() string {
    return "调整广告出价，参数：ad_group_id, bid_type, bid_value"
}

func (t *AdjustBidTool) Execute(ctx context.Context, args map[string]interface{}) (interface{}, error) {
    adGroupID := args["ad_group_id"].(string)
    bidType := args["bid_type"].(string) // cpc/cpm/target_roas
    bidValue := args["bid_value"].(float64)
    
    // 执行调价
    err := adjustBid(adGroupID, bidType, bidValue)
    if err != nil {
        return nil, err
    }
    
    return map[string]interface{}{
        "ad_group_id": adGroupID,
        "bid_type":    bidType,
        "bid_value":   bidValue,
        "status":      "success",
    }, nil
}

// DetectAnomalyTool 异常检测工具
type DetectAnomalyTool struct{}

func (t *DetectAnomalyTool) Name() string {
    return "detect_anomaly"
}

func (t *DetectAnomalyTool) Description() string {
    return "检测广告表现异常，如 CTR 骤降、CPA 飙升、消耗异常等"
}

func (t *DetectAnomalyTool) Execute(ctx context.Context, args map[string]interface{}) (interface{}, error) {
    campaignID := args["campaign_id"].(string)
    
    anomalies := make([]Anomaly, 0)
    
    // 检测 CTR 异常
    ctrAnomaly := checkCTRAnomaly(campaignID)
    if ctrAnomaly != nil {
        anomalies = append(anomalies, *ctrAnomaly)
    }
    
    // 检测 CPA 异常
    cpaAnomaly := checkCPAAnomaly(campaignID)
    if cpaAnomaly != nil {
        anomalies = append(anomalies, *cpaAnomaly)
    }
    
    // 检测消耗异常
    spendAnomaly := checkSpendAnomaly(campaignID)
    if spendAnomaly != nil {
        anomalies = append(anomalies, *spendAnomaly)
    }
    
    return map[string]interface{}{
        "campaign_id": campaignID,
        "anomalies":   anomalies,
        "count":       len(anomalies),
    }, nil
}

type Anomaly struct {
    Type        string    `json:"type"`
    Severity    string    `json:"severity"`
    Description string    `json:"description"`
    Suggestion  string    `json:"suggestion"`
    DetectedAt  time.Time `json:"detected_at"`
}
```

---

## 第四部分：AutoML 智能出价

### 4.1 智能出价策略

```
传统出价：
→ 手动设置 CPC/CPM
→ 优化师凭经验调整

AutoML 出价：
→ 基于历史数据训练模型
→ 实时预测每个展示的 CTR/CVR
→ 自动计算最优出价
→ 持续学习和优化
```

### 4.2 出价模型

```python
# 智能出价模型（PyTorch）
import torch
import torch.nn as nn

class BidOptimizer(nn.Module):
    def __init__(self, feature_dim):
        super().__init__()
        
        # 特征输入层
        self.feature_encoder = nn.Sequential(
            nn.Linear(feature_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
        )
        
        # CTR 预测头
        self.ctr_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )
        
        # CVR 预测头
        self.cvr_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )
        
        # 最优出价预测头
        self.bid_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Softplus(),  # 保证出价为正
        )
    
    def forward(self, features):
        encoded = self.feature_encoder(features)
        ctr = self.ctr_head(encoded)
        cvr = self.cvr_head(encoded)
        bid = self.bid_head(encoded)
        
        return {
            'ctr': ctr,
            'cvr': cvr,
            'bid': bid,
            'ecpm': ctr * cvr * bid * 1000,  # eCPM
        }

# 训练
def train_bid_optimizer(model, optimizer, criterion, train_loader, epochs=50):
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for features, targets in train_loader:
            optimizer.zero_grad()
            outputs = model(features)
            
            # 多任务损失
            ctr_loss = criterion(outputs['ctr'], targets['ctr'])
            cvr_loss = criterion(outputs['cvr'], targets['cvr'])
            bid_loss = criterion(outputs['bid'], targets['bid'])
            
            loss = ctr_loss + cvr_loss + bid_loss
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(train_loader):.4f}")
```

### 4.3 强化学习出价

```python
# 基于强化学习的出价优化
import gym
import numpy as np

class BidEnv(gym.Env):
    """出价优化环境"""
    
    def __init__(self, budget, target_cpa, historical_data):
        super().__init__()
        
        self.budget = budget
        self.target_cpa = target_cpa
        self.data = historical_data
        self.current_bid = 0.5  # 初始出价
        self.step_count = 0
        self.max_steps = len(historical_data)
        
        # 状态空间：[当前预算剩余, 当前 CPA, 历史平均 CTR, 时间特征]
        self.observation_space = gym.spaces.Box(
            low=np.array([0, 0, 0, 0]),
            high=np.array([budget, 100, 1, 24]),
            dtype=np.float32
        )
        
        # 动作空间：出价调整 [-0.1, 0.1]
        self.action_space = gym.spaces.Box(
            low=-0.1,
            high=0.1,
            dtype=np.float32
        )
    
    def step(self, action):
        # 执行动作（调整出价）
        self.current_bid += action[0]
        self.current_bid = max(0.01, min(self.current_bid, 10.0))
        
        # 获取当前数据
        data = self.data[self.step_count]
        
        # 模拟竞价结果
        cpm = data['cpm']
        won = np.random.random() < min(1.0, self.current_bid / cpm)
        
        if won:
            cost = self.current_bid
            conversion = np.random.random() < data['cvr']
            reward = 0
            if conversion:
                reward = 1.0  # 转化奖励
            else:
                reward = -cost / self.target_cpa  # 消耗惩罚
        else:
            reward = -0.01  # 未中标轻微惩罚
        
        self.step_count += 1
        
        # 状态更新
        state = self._get_state()
        
        # 是否结束
        done = self.step_count >= self.max_steps or self.budget <= 0
        
        return state, reward, done, {}
    
    def _get_state(self):
        return np.array([
            self.budget,
            self.current_bid,
            self.step_count / self.max_steps,
            np.random.random(),  # 简化：实际应计算历史 CTR
        ])
    
    def reset(self):
        self.step_count = 0
        self.current_bid = 0.5
        return self._get_state()
```

---

## 第五部分：创意 Agent

### 5.1 创意生成 Agent

```go
// CreativeAgent 创意生成 Agent
type CreativeAgent struct {
    llm       *LLMClient
    generator *ContentGenerator
    tester    *ABTester
}

// GenerateCreative 生成创意
func (a *CreativeAgent) GenerateCreative(ctx context.Context, product ProductInfo) (*CreativePortfolio, error) {
    // 1. 分析产品
    analysis, err := a.analyzeProduct(product)
    if err != nil {
        return nil, err
    }
    
    // 2. 生成创意方向
    directions, err := a.llm.Generate(ctx, &ChatRequest{
        Messages: []Message{
            {Role: "system", Content: "你是一个广告创意专家。"},
            {Role: "user", Content: fmt.Sprintf("为产品 '%s' 生成创意方向。分析：%v", product.Name, analysis)},
        },
    })
    if err != nil {
        return nil, err
    }
    
    // 3. 为每个方向生成多个创意
    portfolio := &CreativePortfolio{}
    for _, dir := range directions.Variants {
        // 生成文案
        copies, err := a.generator.GenerateCopies(product, dir)
        if err != nil {
            continue
        }
        
        // 生成图片
        images, err := a.generator.GenerateImages(product, dir)
        if err != nil {
            continue
        }
        
        portfolio.Add(dir, copies, images)
    }
    
    // 4. A/B 测试
    winner := a.tester.RunTest(portfolio)
    
    return winner, nil
}

// analyzeProduct 分析产品
func (a *CreativeAgent) analyzeProduct(product ProductInfo) (*ProductAnalysis, error) {
    // 使用 LLM 分析产品特点和目标受众
    response, err := a.llm.Chat(context.Background(), &ChatRequest{
        Messages: []Message{
            {Role: "system", Content: "分析产品的目标受众、卖点和竞争差异化。"},
            {Role: "user", Content: fmt.Sprintf("产品：%s，卖点：%v，价格：%s", product.Name, product.SellingPoints, product.Price)},
        },
    })
    
    return parseAnalysis(response.Content), nil
}
```

### 5.2 创意疲劳检测

```go
// CreativeFatigueDetector 创意疲劳检测器
type CreativeFatigueDetector struct {
    db *Database
}

// Detect 检测创意疲劳
func (d *CreativeFatigueDetector) Detect(adID string) (*FatigueReport, error) {
    // 获取最近 7 天的 CTR 趋势
    ctrTrend := d.getCTRtrend(adID, 7)
    
    // 计算 CTR 下降幅度
    decline := (ctrTrend[5] - ctrTrend[6]) / ctrTrend[5]
    
    // 判断是否疲劳
    fatigue := false
    if decline > 0.2 { // CTR 下降超过 20%
        fatigue = true
    }
    
    return &FatigueReport{
        AdID:      adID,
        Decline:   decline,
        Fatigue:   fatigue,
        Suggestion: d.generateSuggestion(adID, decline),
    }, nil
}

func (d *CreativeFatigueDetector) generateSuggestion(adID string, decline float64) string {
    if decline > 0.3 {
        return "创意严重疲劳，建议立即更换素材"
    } else if decline > 0.2 {
        return "创意中度疲劳，建议准备新素材替换"
    }
    return "创意表现正常"
}
```

---

## 第六部分：预算分配 Agent

### 6.1 智能预算分配

```go
// BudgetAllocator 预算分配 Agent
type BudgetAllocator struct {
    db       *Database
    optimizer *LinearOptimizer // 线性规划优化器
}

// Allocate 分配预算
func (a *BudgetAllocator) Allocate(campaigns []*Campaign, totalBudget float64) error {
    // 1. 获取每个广告组的预期 ROI
    rois := make([]float64, len(campaigns))
    for i, camp := range campaigns {
        rois[i] = a.getExpectedROI(camp)
    }
    
    // 2. 线性规划优化
    result, err := a.optimizer.Optimize(rois, totalBudget, a.constraints(campaigns))
    if err != nil {
        return err
    }
    
    // 3. 应用分配结果
    for i, camp := range campaigns {
        camp.Budget = result.Allocations[i]
        a.db.UpdateCampaignBudget(camp.ID, camp.Budget)
    }
    
    return nil
}

// getExpectedROI 获取预期 ROI
func (a *BudgetAllocator) getExpectedROI(campaign *Campaign) float64 {
    // 基于历史数据和预测模型
    historicalROA := a.db.GetHistoricalROAS(campaign.ID)
    predictedCTR := a.model.PredictCTR(campaign)
    predictedCVR := a.model.PredictCVR(campaign)
    
    return historicalROA * predictedCTR * predictedCVR
}
```

---

## 第七部分：自测题

### 问题 1
广告 Agent 的核心能力有哪些？

<details>
<summary>查看答案</summary>

1. **实时监控**：每分钟检查广告表现
2. **自动调参**：根据 CPA 目标调整出价
3. **预算分配**：自动分配到高效广告组
4. **创意生成**：自动生成文案和图片
5. **异常检测**：发现 CTR 骤降/CPA 飙升
6. **策略建议**：生成周报和优化建议
</details>

### 问题 2
ReAct 模式在广告 Agent 中如何工作？

<details>
<summary>查看答案</summary>

1. **Thought**: LLM 思考下一步行动
2. **Action**: 调用工具（获取数据/调整出价）
3. **Observation**: 工具返回结果
4. **Repeat**: 重复直到达成目标
5. **最大迭代**: 防止无限循环
</details>

---

*本文档基于广告 Agent 生产实战整理。*