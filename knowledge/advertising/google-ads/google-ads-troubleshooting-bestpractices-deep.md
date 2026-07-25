# Google Ads 生产排障与最佳实践手册

## 一、常见投放异常与解决方案

### 1.1 展示量异常

**症状：** 展示量突然下降 50%+

**排查流程：**

```
Step 1: 检查预算
├── 每日预算是否耗尽？
│   ├── 是 → 提高预算或降低出价
│   └── 否 → 继续排查
└── 月度预算是否封顶？
    ├── 是 → 等待下月或提高月预算
    └── 否 → 继续排查

Step 2: 检查广告状态
├── 广告是否被拒绝？
│   ├── 是 → 查看拒绝原因，修改后重新提交
│   └── 否 → 继续排查
├── 广告系列是否暂停？
│   ├── 是 → 启用广告系列
│   └── 否 → 继续排查
└── 广告组是否暂停？
    ├── 是 → 启用广告组
    └── 否 → 继续排查

Step 3: 检查出价
├── 出价是否低于市场水平？
│   ├── 是 → 提高出价 10-20%
│   └── 否 → 继续排查
└── 质量评分是否下降？
    ├── 是 → 优化广告文案和落地页
    └── 否 → 继续排查

Step 4: 检查定向
├── 地理位置是否过于狭窄？
│   ├── 是 → 扩大地理范围
│   └── 否 → 继续排查
├── 受众是否过于小众？
│   ├── 是 → 扩大受众范围
│   └── 否 → 继续排查
└── 排期设置是否正确？
    ├── 是 → 保持
    └── 否 → 调整排期
```

**实际案例：**

```
案例：电商客户展示量下降 70%
├── 现象：
│   ├── 展示量从 10 万/天下降到 3 万/天
│   └── 花费从 $500/天下降到 $150/天
├── 排查：
│   ├── Step 1: 预算未耗尽 ✓
│   ├── Step 2: 广告状态正常 ✓
│   ├── Step 3: 出价未调整 ✓
│   └── Step 4: 发现质量评分从 8 降到 4
├── 根因：
│   ├── 落地页加载时间从 2 秒增加到 5 秒
│   └── 竞品提高了出价，挤压了展示空间
├── 解决方案：
│   ├── 优化落地页加载速度 (启用 CDN、图片压缩)
│   ├── 提高核心关键词出价 15%
│   └── 更新广告文案，提高 CTR
└── 结果：
    ├── 3 天后质量评分恢复到 7
    ├── 展示量恢复到 8 万/天
    └── 花费恢复到 $450/天
```

### 1.2 CTR 异常

**症状：** CTR 突然下降 30%+

**可能原因：**

| 原因 | 识别方法 | 解决方案 |
|------|----------|----------|
| 创意疲劳 | 同一广告运行 >30 天 | 更新创意 |
| 竞争加剧 | 竞品推出新广告 | 优化差异化 |
| 匹配变宽 | 广泛匹配引入不相关流量 | 添加否定关键词 |
| 位置变化 | 广告展示位置下降 | 提高出价或质量评分 |

**创意疲劳检测与应对：**

```
创意疲劳指标：
├── CTR 下降 >20% (对比 30 天平均)
├── CPC 上升 >30%
├── CPA 上升 >25%
└── 广告运行时间 >30 天

应对策略：
├── 更新标题 (更换 30% 标题)
├── 更新描述 (更换 50% 描述)
├── 添加新的附加信息
├── 测试全新创意变体
└── 暂停低效创意
```

### 1.3 CPA 异常

**症状：** CPA 突然上升 50%+

**排查流程：**

```
Step 1: 检查转化追踪
├── Pixel 是否正常？
│   ├── 测试转化事件
│   └── 检查数据回传
├── 转化窗口是否变化？
│   └── 确认设置
└── 是否有新增转化来源？
    └── 检查报告

Step 2: 检查流量质量
├── 搜索词报告是否有低质流量？
│   └── 添加否定关键词
├── 地理位置是否有变化？
│   └── 调整地域出价
└── 设备分布是否变化？
    └── 调整设备出价

Step 3: 检查竞争环境
├── 竞品是否提高出价？
│   └── 分析竞品广告
├── 季节性因素？
│   └── 调整预算和出价
└── 市场变化？
    └── 优化价值主张
```

## 二、审核拒绝处理

### 2.1 常见拒绝原因

**广告文案拒绝：**

| 原因 | 说明 | 解决方法 |
|------|------|----------|
| 误导性内容 | 夸大效果、虚假承诺 | 修改文案、提供证明 |
| 政策违规 | 含受限内容 (烟草、药品等) | 移除违规内容 |
| 格式问题 | 不符合广告格式要求 | 调整格式 |
| 特殊类别 | 就业、住房、信用广告 | 完成特殊类别认证 |

**落地页拒绝：**

| 原因 | 说明 | 解决方法 |
|------|------|----------|
| 页面无法访问 | 404、服务器错误 | 修复页面 |
| 内容不符 | 落地页与广告承诺不一致 | 更新落地页 |
| 功能不完整 | 表单无法提交、按钮无效 | 修复功能 |
| 隐私政策缺失 | 缺少隐私政策链接 | 添加隐私政策 |

### 2.2 审核申诉流程

```
申诉流程：
1. 查看拒绝原因
   ↓
2. 分析问题根源
   ├── 文案问题 → 修改文案
   ├── 落地页问题 → 修复页面
   └── 政策问题 → 了解政策要求
   ↓
3. 修改内容
   ↓
4. 重新提交审核
   ↓
5. 等待审核 (通常 1-3 天)
   ↓
6. 如仍被拒，使用申诉通道
   └── 提供修改说明和证据
```

## 三、数据异常处理

### 3.1 数据不一致

**广告后台 vs Google Analytics 数据差异：**

| 差异类型 | 可能原因 | 解决方案 |
|----------|----------|----------|
| 点击量差异 | 过滤条件不同 | 统一过滤设置 |
| 转化量差异 | 归因窗口期不同 | 统一归因模型 |
| 展示量差异 | 无效流量过滤 | 检查无效点击过滤 |

**归因模型差异：**

```
不同归因模型的转化计数差异：
├── Last Click: 100 转化
├── First Click: 60 转化
├── Linear: 120 转化
├── Time Decay: 110 转化
├── Position Based: 115 转化
└── Data-Driven: 125 转化

选择建议：
├── 简单业务 → Last Click
├── 新客获取 → First Click
├── 全链路分析 → Linear 或 Data-Driven
├── 短期转化 → Time Decay
└── 品牌 + 转化 → Position Based
```

### 3.2 转化延迟

**转化追踪延迟处理：**

```
延迟原因：
├── 归因窗口期 (默认 30 天)
├── 跨设备转化 (最多延迟 3 天)
├── 点击到转化的时间差
└── 数据回传延迟

处理方法：
├── 等待 24-48 小时再分析
├── 检查转化设置是否正确
├── 验证 Pixel/SDK 是否正常
└── 使用实时报告辅助判断
```

## 四、生产环境最佳实践

### 4.1 账户健康管理

**每日检查清单：**

```
□ 预算消耗是否正常 (80-100%)
□ 是否有广告被拒绝
□ CTR 是否异常波动 (>20%)
□ CPA 是否在目标范围内
□ 转化数据是否正常回传
□ 质量评分是否有大幅下降
```

**每周检查清单：**

```
□ 搜索词报告优化
□ 关键词绩效分析
□ 广告文案 A/B 测试结果
□ 落地页性能检查
□ 竞争对手广告分析
□ 预算分配优化
```

**每月检查清单：**

```
□ 全面账户审计
□ 关键词库清理
□ 否定关键词库更新
□ 受众列表更新
□ 创意库轮换
□ 月度 ROI 分析
□ 下月预算规划
```

### 4.2 性能优化技巧

**快速优化技巧：**

```
10 分钟优化：
├── 检查并暂停 CPA > 目标 200% 的关键词
├── 为 CTR < 0.5% 的广告创建新版本
├── 添加高转化搜索词为关键词
└── 排除零转化高花费搜索词

1 小时优化：
├── 分析搜索词报告，更新否定关键词
├── 调整设备出价 (基于设备表现)
├── 优化广告文案 (更新标题和描述)
└── 检查落地页加载速度

1 天优化：
├── 全面关键词绩效分析
├── A/B 测试广告设计
├── 优化预算分配
├── 更新受众列表
└── 分析竞品广告策略
```

## 五、自测题

1. 展示量骤降的排查流程是什么？
2. 如何检测和应对创意疲劳？
3. CPA 突然上升的可能原因有哪些？
4. 审核拒绝的常见原因和解决方法是什么？
5. 数据不一致如何处理？

## 六、动手验证

```bash
# 1. 设置监控告警
# - 预算消耗告警
# - CPA 阈值告警
# - CTR 异常告警

# 2. 创建优化 SOP
# - 每日检查清单
# - 每周优化流程
# - 每月审计流程

# 3. 测试异常处理
# - 模拟审核拒绝
# - 模拟数据异常
# - 验证排查流程
```

---

## 第七部分：Go 生产级实现

### Google Ads 故障诊断引擎 — Go 源码

```go
package main

import (
	"fmt"
	"strings"
	"time"
)

// DiagnosticResult represents the outcome of a diagnostic check.
type DiagnosticResult struct {
	Check     string
	Status    string // "pass", "warning", "fail"
	Message   string
	Severity  int    // 1-3, 3 = critical
	Remediation string
}

// TroubleshootEngine diagnoses common Google Ads issues.
type TroubleshootEngine struct {
	campaigns map[string]*CampaignData
}

type CampaignData struct {
	ID            string
	Name          string
	Status        string
	ImprShare     float64 // impression share
	SearchLostIS  float64 // search lost IS (rank)
	BudgetLostIS  float64 // budget lost IS
	AvgCPC        float64
	CTR           float64
	QualityScore  int
	LastModified  time.Time
}

func NewTroubleshootEngine() *TroubleshootEngine {
	return &TroubleshootEngine{
		campaigns: make(map[string]*CampaignData),
	}
}

func (e *TroubleshootEngine) Diagnose(campaignID string) []DiagnosticResult {
	data, exists := e.campaigns[campaignID]
	if !exists {
		return []DiagnosticResult{{
			Check:     "campaign_exists",
			Status:    "fail",
			Message:   fmt.Sprintf("Campaign %s not found", campaignID),
			Severity:  3,
		}}
	}

	var results []DiagnosticResult

	// Check 1: Campaign status
	if data.Status != "ENABLED" {
		results = append(results, DiagnosticResult{
			Check:     "campaign_status",
			Status:    "fail",
			Message:   fmt.Sprintf("Campaign is %s, should be ENABLED", data.Status),
			Severity:  3,
			Remediation: "Enable the campaign or create a new one",
		})
	}

	// Check 2: Impression share
	if data.ImprShare < 0.5 {
		results = append(results, DiagnosticResult{
			Check:     "impression_share",
			Status:    "warning",
			Message:   fmt.Sprintf("Impression share is %.1f%% (below 50%%)", data.ImprShare*100),
			Severity:  2,
			Remediation: "Increase bids or budget to improve impression share",
		})
	}

	// Check 3: Budget lost impression share
	if data.BudgetLostIS > 0.2 {
		results = append(results, DiagnosticResult{
			Check:     "budget_constraint",
			Status:    "warning",
			Message:   fmt.Sprintf("Budget lost IS is %.1f%% (>20%%)", data.BudgetLostIS*100),
			Severity:  2,
			Remediation: "Increase daily budget to capture more impressions",
		})
	}

	// Check 4: Rank lost impression share
	if data.SearchLostIS > 0.3 {
		results = append(results, DiagnosticResult{
			Check:     "rank_constraint",
			Status:    "warning",
			Message:   fmt.Sprintf("Rank lost IS is %.1f%% (>30%%)", data.SearchLostIS*100),
			Severity:  2,
			Remediation: "Increase bids or improve Quality Score",
		})
	}

	// Check 5: CTR health
	if data.CTR < 0.02 {
		results = append(results, DiagnosticResult{
			Check:     "ctr_health",
			Status:    "warning",
			Message:   fmt.Sprintf("CTR is %.2f%% (below 2%%)", data.CTR*100),
			Severity:  2,
			Remediation: "Improve ad copy relevance or test new creatives",
		})
	}

	return results
}

// BatchDiagnose runs diagnostics on multiple campaigns.
func (e *TroubleshootEngine) BatchDiagnose(campaignIDs []string) map[string][]DiagnosticResult {
	results := make(map[string][]DiagnosticResult)
	for _, id := range campaignIDs {
		results[id] = e.Diagnose(id)
	}
	return results
}

// GetCriticalIssues returns only severity 3 issues across all campaigns.
func (e *TroubleshootEngine) GetCriticalIssues() []DiagnosticResult {
	var critical []DiagnosticResult
	for id := range e.campaigns {
		for _, r := range e.Diagnose(id) {
			if r.Severity == 3 {
				critical = append(critical, r)
			}
		}
	}
	return critical
}
```

---

## 第八部分：自测题

### 问题 1：诊断引擎中为什么 Impression Share < 50% 标记为 warning 而非 fail？

<details>
<summary>查看答案</summary>

IS < 50% 不一定表示有问题：
1. **预算限制**：小预算 Campaign 可能故意控制展示量
2. **精准定位**：高度定向的关键词可能天然 IS 较低
3. **新 Campaign**：刚启动的 Campaign 还在积累数据

所以用 warning 级别，需要结合 BudgetLostIS 和 SearchLostIS 综合判断。如果 BudgetLostIS > 20% 且 SearchLostIS < 10%，说明是预算问题而非定位问题。

</details>

### 问题 2：BatchDiagnose 和 GetCriticalIssues 的设计区别是什么？

<details>
<summary>查看答案</summary>

BatchDiagnose 返回每个 Campaign 的完整诊断结果，适合详细分析。
GetCriticalIssues 只返回严重问题（severity=3），适合快速告警。

实际生产中应该结合使用：
1. 定时运行 GetCriticalIssues 发送告警
2. 人工查看时运行 BatchDiagnose 获取详细信息

</details>

### 问题 3：为什么诊断检查的顺序很重要？

<details>
<summary>查看答案</summary>

诊断检查应该按严重性和排查逻辑排序：
1. **campaign_status**（最优先）：Campaign 未启用是根本问题
2. **impression_share**：整体展示情况
3. **budget_constraint**：预算是否限制展示
4. **rank_constraint**：出价是否太低
5. **ctr_health**：广告文案质量

如果 Campaign 未启用，后面的检查都没有意义。按优先级排序可以快速定位根因。

</details>
