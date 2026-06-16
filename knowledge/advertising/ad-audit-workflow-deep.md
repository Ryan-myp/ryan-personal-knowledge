# 广告审核流程深度：AI 初审 + 人工复审 + 质检

> 审核流程设计 + AI 审核模型 + 人工审核系统 + 质检机制

---

## 第一部分：为什么审核这么重要？

### 审核的业务意义

```
1. 合规性：
   → 广告法合规（禁用词/虚假宣传）
   → 行业合规（金融/医疗特殊要求）
   → 平台合规（品牌安全）

2. 用户体验：
   → 避免低质内容
   → 避免骚扰用户
   → 避免误导用户

3. 法律责任：
   → 违规广告可能面临罚款
   → 严重违规可能吊销执照
   → 平台承担连带责任
```

### 审核数据量

```
每天新增创意：10 万个
→ AI 审核：10 万个（自动通过/拒绝）
→ 转人工：1 万个（10%）
→ 人工审核：1 万个
→ 质检抽检：1000 个（10%）

审核时效要求：
→ AI 审核：< 5 秒
→ 人工审核：< 30 分钟
→ 质检：< 1 小时
```

---

## 第二部分：审核架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    广告审核系统                               │
└─────────────────────────────────────────────────────────────┘

                    ┌───────────────────────────────────────┐
                    │       创意上传                          │
                    │  - 图片/视频/文案                       │
                    └──────────────┬────────────────────────┘
                                   │
                    ┌──────────────▼────────────────────────┐
                    │       AI 审核引擎                       │
                    │  - 图片审核（敏感内容/广告法）           │
                    │  - 文案审核（违禁词/语义分析）           │
                    │  - 视频审核（逐帧+音频）                │
                    └──────┬──────────┬──────────┬──────────┘
                           │          │          │
                    ┌──────▼──┐ ┌─────▼────┐ ┌───▼────────┐
                    │ 自动通过 │ │ 转人工审核 │ │ 自动拒绝   │
                    │ (70%)   │ │ (20%)     │ │ (10%)     │
                    └─────────┘ └──────────┘ └────────────┘
                                   │
                    ┌──────────────▼────────────────────────┐
                    │       人工审核系统                      │
                    │  - 审核工作台                           │
                    │  - 审核任务分配                         │
                    │  - 审核历史记录                        │
                    └──────────────┬────────────────────────┘
                                   │
                    ┌──────────────▼────────────────────────┐
                    │       质检系统                          │
                    │  - 抽检审核结果                         │
                    │  - 审核员绩效考核                       │
                    │  - 审核模型持续优化                     │
                    └───────────────────────────────────────┘
```

### 2.2 审核状态机

```
待审核 → AI 审核 → 自动通过 / 转人工 / 自动拒绝
                    ↓
                人工审核 → 通过 / 拒绝
                    ↓
                质检抽检 → 合格 / 不合格
                    ↓
                最终状态：已上线 / 已下架
```

---

## 第三部分：AI 审核引擎

### 3.1 审核类型

```
1. 图片审核：
   → 敏感内容（色情/暴力/政治）
   → 广告法违规（禁用词/夸大宣传）
   → 品牌安全（不适配内容）

2. 文案审核：
   → 违禁词检测
   → 语义分析（虚假宣传）
   → 情感分析（负面内容）

3. 视频审核：
   → 逐帧图片审核
   → 音频审核（敏感词）
   → OCR 文字识别
```

### 3.2 代码实现

```go
package audit

import (
    "context"
)

// AuditEngine 审核引擎
type AuditEngine struct {
    imageAuditor   *ImageAuditor
    textAuditor    *TextAuditor
    videoAuditor   *VideoAuditor
    confidenceThreshold float64 // 置信度阈值
}

type AuditResult struct {
    CreativeID   int64
    Passed       bool     // 是否通过
    Confidence   float64  // 置信度
    Reasons      []string // 拒绝原因
    NeedsManual  bool     // 是否需要人工审核
    Tags         []string // 标签
}

// Audit 审核创意
func (ae *AuditEngine) Audit(ctx context.Context, creative Creative) (*AuditResult, error) {
    switch creative.Type {
    case "image":
        return ae.auditImage(ctx, creative)
    case "text":
        return ae.auditText(ctx, creative)
    case "video":
        return ae.auditVideo(ctx, creative)
    case "mixed":
        return ae.auditMixed(ctx, creative)
    }
    return nil, fmt.Errorf("unknown creative type: %s", creative.Type)
}

// auditImage 审核图片
func (ae *AuditEngine) auditImage(ctx context.Context, creative Creative) (*AuditResult, error) {
    // 1. 敏感内容检测
    sensitiveResult, err := ae.imageAuditor.DetectSensitive(creative.URL)
    if err != nil {
        return nil, err
    }
    
    // 2. 广告法违规检测
    adLawResult, err := ae.imageAuditor.DetectAdLawViolation(creative.URL)
    if err != nil {
        return nil, err
    }
    
    // 3. 品牌安全检测
    brandResult, err := ae.imageAuditor.DetectBrandSafety(creative.URL)
    if err != nil {
        return nil, err
    }
    
    // 4. 综合评分
    score := ae.calculateScore(sensitiveResult, adLawResult, brandResult)
    
    // 5. 判断结果
    result := ae.judgeResult(score)
    
    return result, nil
}

// calculateScore 计算综合评分
func (ae *AuditEngine) calculateScore(sensitive, adLaw, brand *AuditComponent) float64 {
    // 加权平均
    return sensitive.Score*0.5 + adLaw.Score*0.3 + brand.Score*0.2
}

// judgeResult 判断结果
func (ae *AuditEngine) judgeResult(score float64) *AuditResult {
    if score >= 0.9 {
        // 高置信度通过
        return &AuditResult{
            Passed:   true,
            Confidence: score,
            NeedsManual: false,
        }
    } else if score <= 0.3 {
        // 高置信度拒绝
        return &AuditResult{
            Passed:   false,
            Confidence: 1.0 - score,
            Reasons:  []string{"high_risk_content"},
            NeedsManual: false,
        }
    } else {
        // 不确定，转人工
        return &AuditResult{
            Passed:    false,
            Confidence: score,
            NeedsManual: true,
            Reasons:   []string{"uncertain"},
        }
    }
}
```

### 3.3 审核模型

```python
# 图片审核模型（PyTorch）
import torch
import torch.nn as nn
from torchvision import models

class ImageAuditModel(nn.Module):
    def __init__(self, num_classes=3):
        super().__init__()
        # 使用预训练的 ResNet
        self.backbone = models.resnet50(pretrained=True)
        self.backbone.fc = nn.Sequential(
            nn.Linear(2048, 512),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(512, num_classes)
        )
    
    def forward(self, x):
        return self.backbone(x)

# 训练
def train_model(model, train_loader, val_loader, epochs=10):
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    for epoch in range(epochs):
        # 训练
        model.train()
        for images, labels in train_loader:
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
        
        # 验证
        model.eval()
        with torch.no_grad():
            correct = 0
            total = 0
            for images, labels in val_loader:
                outputs = model(images)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
            
            accuracy = correct / total
            print(f"Epoch {epoch+1}, Accuracy: {accuracy:.4f}")
```

---

## 第四部分：人工审核系统

### 4.1 审核工作台

```
审核工作台功能：
1. 任务列表：待审核的创意
2. 审核面板：展示创意详情
3. 审核操作：通过/拒绝/转审
4. 历史记录：审核历史
5. 快捷键：提升审核效率
```

### 4.2 代码实现

```go
// AuditQueue 审核队列
type AuditQueue struct {
    db     *Database
    ws     *WebSocketServer
}

// GetPendingTasks 获取待审核任务
func (aq *AuditQueue) GetPendingTasks(auditorID string, limit int) ([]Creative, error) {
    // 1. 查询待审核的创意
    creatives, err := aq.db.GetPendingCreatives(limit)
    if err != nil {
        return nil, err
    }
    
    // 2. 分配给审核员（负载均衡）
    for _, c := range creatives {
        aq.db.AssignCreative(c.ID, auditorID)
    }
    
    return creatives, nil
}

// SubmitAuditResult 提交审核结果
func (aq *AuditQueue) SubmitAuditResult(auditorID string, result AuditResult) error {
    // 1. 保存审核结果
    err := aq.db.SaveAuditResult(result)
    if err != nil {
        return err
    }
    
    // 2. 通知前端
    aq.ws.NotifyAuditor(auditorID, "task_completed")
    
    // 3. 触发质检（10% 抽检）
    if rand.Float64() < 0.1 {
        aq.qaQueue.Enqueue(result.CreativeID)
    }
    
    return nil
}
```

### 4.3 审核员绩效

```go
// AuditorPerformance 审核员绩效
type AuditorPerformance struct {
    auditorID    string
    totalAudited int       // 总审核数
    correctCount int       // 正确数
    avgTime      float64   // 平均审核时间（秒）
    accuracy     float64   // 准确率
}

// CalculateAccuracy 计算准确率
func (ap *AuditorPerformance) CalculateAccuracy() float64 {
    if ap.totalAudited == 0 {
        return 0
    }
    return float64(ap.correctCount) / float64(ap.totalAudited)
}

// 绩效指标：
// 1. 审核数量：每天 200-500 个
// 2. 准确率：> 95%
// 3. 平均审核时间：< 30 秒
// 4. 质检合格率：> 98%
```

---

## 第五部分：质检系统

### 5.1 质检流程

```
1. 抽检：
   → 自动通过的创意：1% 抽检
   → 人工审核的创意：10% 抽检
   → 拒绝的创意：5% 抽检

2. 质检操作：
   → 通过：确认审核结果
   → 拒绝：推翻审核结果，重新审核

3. 反馈：
   → 审核员绩效更新
   → AI 模型持续优化
```

### 5.2 代码实现

```go
// QAInspector 质检员
type QAInspector struct {
    db *Database
}

// Inspect 质检
func (qi *QAInspector) Inspect(creativeID int64) (*QAResult, error) {
    // 1. 获取审核记录
    auditRecord, err := qi.db.GetAuditRecord(creativeID)
    if err != nil {
        return nil, err
    }
    
    // 2. 重新审核
    newResult, err := qi.reAudit(creativeID)
    if err != nil {
        return nil, err
    }
    
    // 3. 对比结果
    consistent := newResult.Passed == auditRecord.Passed
    
    // 4. 更新审核员绩效
    if !consistent {
        qi.updateAuditorPerformance(auditRecord.AuditorID, false)
    }
    
    return &QAResult{
        CreativeID:  creativeID,
        Original:    auditRecord,
        NewResult:   newResult,
        Consistent:  consistent,
    }, nil
}
```

---

## 第六部分：自测题

### 问题 1
AI 审核和人工审核的比例是多少？

<details>
<summary>查看答案</summary>

1. **AI 审核**：70% 自动通过，10% 自动拒绝
2. **转人工**：20% 不确定
3. **质检抽检**：1-10%
4. **目标**：AI 审核覆盖率 > 90%
5. **人工审核**：处理 AI 不确定的
</details>

### 问题 2
审核员绩效如何评估？

<details>
<summary>查看答案</summary>

1. **审核数量**：每天 200-500 个
2. **准确率**：> 95%
3. **平均审核时间**：< 30 秒
4. **质检合格率**：> 98%
5. **综合评分**：数量 × 准确率 / 时间
</details>

---

*本文档基于广告审核生产实战整理。*