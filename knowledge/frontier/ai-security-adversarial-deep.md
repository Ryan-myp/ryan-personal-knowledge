# AI 安全与对抗攻击深度实战

## 一、AI 安全威胁全景

### 1.1 主要攻击类型

**对抗样本攻击 (Adversarial Attacks):**

```
攻击原理:
├── 在输入数据中添加微小扰动
├── 扰动人眼不可见但对模型有影响
└── 导致模型做出错误预测

攻击方式:
├── FGSM (Fast Gradient Sign Method)
│   └── 单步攻击，计算梯度符号
├── PGD (Projected Gradient Descent)
│   └── 多步攻击，更强效果
└── CW (Carlini-Wagner)
    └── 优化攻击，最难防御

防御方法:
├── 对抗训练 (Adversarial Training)
│   └── 在训练中加入对抗样本
├── 输入预处理
│   └── 去噪、平滑
└── 检测模型
    └── 识别对抗样本
```

**数据投毒 (Data Poisoning):**

```
攻击原理:
├── 在训练数据中注入恶意样本
├── 污染模型学习过程
└── 导致模型行为异常

攻击方式:
├── 标签翻转 (Label Flipping)
│   └── 修改训练数据标签
├── 后门攻击 (Backdoor Attack)
│   └── 植入触发器，特定输入触发恶意行为
└── 梯度投毒 (Gradient Poisoning)
    └── 在联邦学习中污染梯度

防御方法:
├── 数据清洗
│   └── 检测异常数据
├── 鲁棒聚合
│   └── 联邦学习中过滤恶意梯度
└── 异常检测
    └── 识别投毒样本
```

**模型窃取 (Model Stealing):**

```
攻击原理:
├── 通过大量查询获取模型输出
├── 训练替代模型模仿目标模型
└── 窃取模型知识产权

攻击方式:
├── 查询攻击 (Query Attack)
│   └── 发送查询获取 logits
├── 成员推断 (Membership Inference)
│   └── 判断数据是否在训练集中
└── 属性推断 (Attribute Inference)
    └── 推断训练数据属性

防御方法:
├── 查询限制
│   └── 限制 API 调用频率
├── 输出扰动
│   └── 添加噪声保护隐私
└── 差分隐私
    └── 训练时添加噪声
```

### 1.2 广告平台安全威胁

**广告作弊 (Ad Fraud):**

| 类型 | 说明 | 影响 |
|------|------|------|
| 机器人流量 | 虚假点击/曝光 | 预算浪费 |
| 点击农场 | 人工点击 | 数据失真 |
| 流量劫持 | 拦截广告请求 | 收入损失 |
| 归因欺诈 | 伪造转化 | 错误优化 |

**防御策略：**

```
检测维度:
├── 设备指纹
│   ├── 模拟器检测
│   ├── Root/越狱检测
│   └── 设备一致性检查
├── 行为分析
│   ├── 点击频率异常
│   ├── 交互模式异常
│   └── 时间分布异常
├── 网络分析
│   ├── IP 信誉
│   ├── 代理/VPN 检测
│   └── 地理位置验证
└── 机器学习
    ├── 异常检测模型
    ├── 聚类分析
    └── 图神经网络
```

## 二、安全架构设计

### 2.1 纵深防御体系

```
Layer 1: 网络层
├── WAF (Web 应用防火墙)
├── DDoS 防护
└── 入侵检测

Layer 2: 应用层
├── 输入验证
├── 身份认证
└── 授权控制

Layer 3: 数据层
├── 加密存储
├── 访问控制
└── 审计日志

Layer 4: 模型层
├── 对抗训练
├── 模型水印
└── 输出监控
```

### 2.2 监控与告警

```go
type SecurityMonitor struct {
	alerts     chan Alert
	thresholds map[string]float64
	mu         sync.RWMutex
}

type Alert struct {
	Metric string
	Score  float64
	Time   time.Time
}

func (m *SecurityMonitor) Check(anomalyScore float64, metric string) {
	m.mu.RLock()
	threshold, exists := m.thresholds[metric]
	m.mu.RUnlock()
	
	if exists && anomalyScore > threshold {
		m.alerts <- Alert{
			Metric: metric,
			Score:  anomalyScore,
			Time:   time.Now(),
		}
	}
}
```

## 三、对抗攻击实战

### 3.1 FGSM 攻击实现

```go
package adversarial

import (
	"math"
	"math/rand"
)

// FGSM Fast Gradient Sign Method
func FGSM(model Model, input Tensor, epsilon float64) Tensor {
	// 计算梯度
	gradients := model.ComputeGradients(input)
	
	// 取梯度符号
	sign := gradients.Sign()
	
	// 添加扰动
	adversarial := input.Add(sign.Multiply(epsilon))
	
	// 裁剪到有效范围
	return adversarial.Clip(0, 1)
}

// PGD Projected Gradient Descent
func PGD(model Model, input Tensor, epsilon float64, steps int, alpha float64) Tensor {
	current := input.Copy()
	
	for i := 0; i < steps; i++ {
		gradients := model.ComputeGradients(current)
		sign := gradients.Sign()
		
		current = current.Add(sign.Multiply(alpha))
		current = current.Clip(input.Sub(epsilon), input.Add(epsilon))
	}
	
	return current
}
```

### 3.2 对抗训练

```go
type AdversarialTrainer struct {
	model       Model
	epsilon     float64
	stepsPerGen int
}

func (t *AdversarialTrainer) TrainStep(data Tensor, labels Tensor) error {
	// 生成对抗样本
	adversarial := PGD(t.model, data, t.epsilon, t.stepsPerGen, t.epsilon/2)
	
	// 联合训练原始样本和对抗样本
	loss1 := t.model.Loss(data, labels)
	loss2 := t.model.Loss(adversarial, labels)
	
	// 最小化联合损失
	totalLoss := loss1.Add(loss2).Divide(2)
	return t.model.Backward(totalLoss)
}
```

## 四、广告反作弊系统

### 4.1 实时检测架构

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  数据采集    │───>│  实时检测    │───>│  处置       │
│             │    │             │    │             │
│ 点击日志    │    │  规则引擎    │    │  拦截       │
│ 设备指纹    │    │  异常检测    │    │  降权       │
│ 行为序列    │    │  图分析      │    │  封禁       │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 4.2 Go 实现实时检测

```go
package antifraud

import (
	"context"
	"time"
)

type ClickEvent struct {
	ClickID  string
	UserID   string
	DeviceID string
	IP       string
	AdID     string
	Timestamp time.Time
}

type Detector struct {
	ruleEngine  *RuleEngine
	anomalyModel *AnomalyModel
	graphEngine  *GraphEngine
}

func (d *Detector) Detect(ctx context.Context, event ClickEvent) (bool, float64) {
	// 规则引擎检测
	if score := d.ruleEngine.Evaluate(event); score > 0.8 {
		return true, score
	}
	
	// 异常检测模型
	anomalyScore := d.anomalyModel.Score(event)
	if anomalyScore > 0.7 {
		return true, anomalyScore
	}
	
	// 图分析
	graphScore := d.graphEngine.Analyze(event)
	if graphScore > 0.6 {
		return true, graphScore
	}
	
	return false, 0
}
```

## 五、自测题

1. 对抗样本攻击的原理是什么？
2. 如何防御数据投毒攻击？
3. 广告作弊的检测维度有哪些？
4. 对抗训练如何提高模型鲁棒性？

## 六、动手验证

```bash
# 1. 实现对抗训练
# 2. 部署异常检测
# 3. 配置告警规则
# 4. 测试防御效果
```
