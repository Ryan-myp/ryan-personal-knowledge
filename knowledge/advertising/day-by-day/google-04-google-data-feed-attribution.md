# Google Ads — 数据回流与归因引擎：模型底层

> 创建日期: 2026-06-09
> 作者: Ryan
> 定位: 资深专家级

---

## 第一部分：数据回流 (Data Feed)

### 1.1 数据回流的作用

```
数据回流是广告优化的核心闭环：

用户行为 → 数据采集 → 归因分析 → 模型更新 → 出价优化 → 更多转化

如果没有数据回流，广告系统就是"盲打"：
├─ 不知道哪些创意有效 → 浪费预算
├─ 不知道哪些受众有效 → 盲目投放
├─ 不知道归因窗口 → 错误分配功劳
└─ 模型无法学习 → 效果越来越差
```

### 1.2 数据回流的方式

```
Google Ads 数据回流的四种方式：

1. Google Ads 转化追踪 (内置)
   ─────────────────────────────
   ├── 通过 Google Tag Manager (GTM) 部署
   ├── 自动追踪转化 (点击后 N 天内)
   └── 无需额外开发

2. Google Ads API 回传
   ─────────────────────────────
   ├── 通过 ConversionUploadService 上传转化数据
   ├── 支持延迟回传 (如 CRM 数据)
   └── 可自定义转化类型

3. Google Ads 链接 (Linked Accounts)
   ─────────────────────────────
   ├── 链接 Google Analytics 4 (GA4)
   ├── 链接 Google Merchant Center
   ├── 链接 Google Search Console
   └── 自动共享数据

4. gclid 传递 (点击 ID)
   ─────────────────────────────
   ├── Google 添加 gclid 参数到落地页 URL
   ├── 落地页记录 gclid
   ├── 转化时回传 gclid
   └── 用于归因匹配
```

### 1.3 gclid 机制深度分析

```
gclid (Google Click ID) 是归因的核心：

流程：
1. 用户点击 Google 广告
2. Google 生成唯一的 gclid (UUID)
3. Google 将 gclid 附加到落地页 URL:
   https://example.com/product?id=123&gclid=Cjw...xyz
4. 用户到达落地页，页面记录 gclid
5. 用户完成转化 (如购买)
6. 落地页发送转化事件给 Google，附带 gclid
7. Google 根据 gclid 匹配点击和转化

实现代码 (落地页):
```python
# landing_page/track_conversion.py
import hashlib
import time

def generate_gclid() -> str:
    """生成 gclid (简化版)"""
    import uuid
    return str(uuid.uuid4()).replace('-', '')

def extract_gclid(url_params: dict) -> str:
    """从 URL 参数提取 gclid"""
    return url_params.get('gclid', '')

def store_conversion(user_id: str, gclid: str, 
                     conversion_type: str, 
                     value: float):
    """存储转化数据"""
    # 本地存储
    # 后续上传到 Google Ads API
    conversion = {
        'user_id': user_id,
        'gclid': gclid,
        'type': conversion_type,
        'value': value,
        'timestamp': int(time.time()),
    }
    # 存入数据库或发送到 Google
    upload_to_google(conversion)

def upload_to_google(conversion: dict):
    """通过 Google Ads API 上传转化"""
    from googleads import adwords
    
    # 使用 ConversionUploadService
    service = client.GetService('ConversionUploadService', 'v5')
    
    conversion_upload = {
        'customerId': 'YOUR_CUSTOMER_ID',
        'conversions': [{
            'gclid': conversion['gclid'],
            'conversionAction': 'YOUR_CONVERSION_ACTION',
            'conversionDateTime': datetime.utcnow().strftime('%Y%m%d %H%M%S'),
            'conversionValue': conversion['value'],
            'conversionCompatibility': 'ADWORDS_CLICK',
            'friendlierConversionName': conversion['type'],
        }],
    }
    
    result = service.mutate(conversion_upload)
    return result
```

### 1.4 延迟转化回传 (Enhanced Conversions)

```
Enhanced Conversions 解决"转化延迟"问题：

问题：用户点击广告后，可能几天甚至几周后才转化
解决：通过服务器-side 回传，匹配更宽泛的数据

Enhanced Conversions 流程：
1. 用户点击广告 → 记录 gclid + cookie
2. 用户注册/购买 → 收集 email (经同意)
3. 服务器端:
   ├── 收集转化数据 (包括 email)
   ├── 对 email 进行哈希处理
   ├── 发送到 Google Ads API
   └── Google 通过哈希 email 匹配点击

```python
# enhanced_conversions/upload.py
import hashlib
import base64

def hash_email(email: str) -> str:
    """
    对 email 进行 SHA-256 哈希
    符合 Google Privacy 要求
    """
    email = email.strip().lower()
    return hashlib.sha256(email.encode('utf-8')).hexdigest()

def upload_enhanced_conversion(customer_id: str,
                                gclid: str,
                                conversion_value: float,
                                conversion_date: str,
                                first_name: str = None,
                                last_name: str = None,
                                email: str = None,
                                phone: str = None,
                                address: dict = None):
    """
    上传 Enhanced Conversion
    
    参数:
    ├── gclid: 点击 ID
    ├── conversion_value: 转化价值
    ├── conversion_date: 转化时间
    ├── first_name: 名 (可选)
    ├── last_name: 姓 (可选)
    ├── email: 邮箱 (可选，自动哈希)
    ├── phone: 电话 (可选，自动哈希)
    └── address: 地址 (可选，自动哈希)
    """
    # 哈希 PII 数据
    user_data = {}
    if first_name:
        user_data['first_name'] = hashlib.sha256(
            first_name.strip().lower().encode('utf-8')
        ).hexdigest()
    if last_name:
        user_data['last_name'] = hashlib.sha256(
            last_name.strip().lower().encode('utf-8')
        ).hexdigest()
    if email:
        user_data['email'] = hash_email(email)
    if phone:
        phone_digits = ''.join(c for c in phone if c.isdigit())
        user_data['phone'] = hashlib.sha256(
            phone_digits.encode('utf-8')
        ).hexdigest()
    
    # 构建上传请求
    conversion = {
        'gclid': gclid,
        'conversionAction': f'customers/{customer_id}/conversionActions/{CONVERSION_ACTION_ID}',
        'conversionDateTime': conversion_date,
        'conversionValue': conversion_value,
        'userIdData': {
            'userProfiles': [{
                'userIdentifierFields': user_data,
            }],
        },
    }
    
    # 上传
    return upload_to_google(customer_id, conversion)
```

---

## 第二部分：归因引擎底层

### 2.1 归因引擎的架构

```
Google 归因引擎的核心组件：

┌──────────────────────────────────────────────────────────────┐
│                 Attribution Engine                            │
│                                                              │
│  输入:                                                      │
│  ├── Click Events: 点击记录 (gclid, timestamp, device)       │
│  ├── Impression Events: 展示记录 (imp_id, timestamp)         │
│  ├── Conversion Events: 转化记录 (user_id, timestamp)        │
│  └── User Journey: 用户路径 (session 序列)                   │
│                                                              │
│  归因模型:                                                   │
│  ├── Last Click (默认)                                      │
│  ├── First Click                                          │
│  ├── Linear                                               │
│  ├── Time Decay                                           │
│  ├── Position Based                                       │
│  └── Data-Driven (ML)                                     │
│                                                              │
│  输出:                                                      │
│  ├── Channel Attribution: 每个渠道的功劳                      │
│  ├── Time Decay Weights: 衰减权重                           │
│  └── Incrementality Lift: 增量提升                           │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Data-Driven Attribution 的数学推导

```
数据驱动归因 (DDA) 使用 Markov Chain 模型：

Markov Chain 归因原理：
1. 将用户旅程建模为状态转移
2. 计算每个状态（触点）的移除效应
3. 移除效应 = 移除该状态后转化率下降的幅度

实现：
```python
# attribution/markov.py
import numpy as np
from collections import defaultdict

class MarkovAttribution:
    """
    Markov Chain 归因模型
    
    核心思想: 移除每个触点，看转化率下降多少
    
    步骤:
    1. 构建状态转移矩阵
    2. 计算每个状态在系统中的稳态概率
    3. 移除每个状态，重新计算稳态概率
    4. 移除效应 = 原始转化率 - 移除后的转化率
    """
    
    def __init__(self):
        self.transition_matrix = None
        self.states = None
        self.state_indices = {}
    
    def fit(self, conversion_paths: list, 
            max_iterations: int = 1000,
            tolerance: float = 1e-6):
        """
        拟合 Markov 链
        
        参数:
        └── conversion_paths: 转化路径列表
            每个路径是触点序列，如 ['search', 'display', 'search']
        """
        # 获取所有唯一状态
        all_states = set()
        for path in conversion_paths:
            all_states.update(path)
        
        self.states = sorted(all_states)
        self.state_indices = {s: i for i, s in enumerate(self.states)}
        n = len(self.states)
        
        # 构建转移矩阵
        transition_counts = np.zeros((n, n))
        
        for path in conversion_paths:
            for i in range(len(path) - 1):
                from_idx = self.state_indices[path[i]]
                to_idx = self.state_indices[path[i + 1]]
                transition_counts[from_idx, to_idx] += 1
        
        # 归一化
        self.transition_matrix = transition_counts / transition_counts.sum(axis=1, keepdims=True)
        
        # 添加吸收态 (转化完成)
        self._add_absorbing_state(n)
    
    def _add_absorbing_state(self, n: int):
        """添加吸收态"""
        m = n + 1  # 总状态数 (包括吸收态)
        new_matrix = np.zeros((m, m))
        
        for i in range(n):
            for j in range(n):
                new_matrix[i, j] = self.transition_matrix[i, j]
            # 转移到吸收态的概率
            new_matrix[i, n] = 1.0 - self.transition_matrix[i].sum()
        
        # 吸收态保持不变
        new_matrix[n, n] = 1.0
        
        self.transition_matrix = new_matrix
        self.absorbing_state = n
    
    def get_removal_effect(self) -> dict:
        """
        计算移除效应
        
        移除每个状态后，吸收概率下降多少？
        """
        original_absorption = self._get_absorption_probability()
        effects = {}
        
        n = len(self.states)
        for i, state in enumerate(self.states):
            # 移除该状态
            temp_matrix = self.transition_matrix.copy()
            temp_matrix[i, :] = 0
            temp_matrix[i, i] = 0
            # 重新归一化
            row_sum = temp_matrix[i].sum()
            if row_sum > 0:
                temp_matrix[i] /= row_sum
            
            # 重新计算吸收概率
            removed_absorption = self._get_absorption_probability_with_removed(temp_matrix, i)
            
            effects[state] = original_absorption - removed_absorption
        
        # 归一化
        total = sum(effects.values())
        if total > 0:
            effects = {k: v / total for k, v in effects.items()}
        
        return effects
    
    def _get_absorption_probability(self) -> float:
        """计算吸收概率"""
        n = self.transition_matrix.shape[0] - 1  # 非吸收态数量
        if n == 0:
            return 1.0
        
        Q = self.transition_matrix[:n, :n]
        I = np.eye(n)
        N = np.linalg.inv(I - Q)  # 基本矩阵
        R = self.transition_matrix[:n, n:]
        
        absorption = N @ R
        return absorption.mean()
    
    def _get_absorption_probability_with_removed(self, 
                                                  matrix: np.ndarray,
                                                  removed_idx: int) -> float:
        """移除某个状态后的吸收概率"""
        n = matrix.shape[0] - 1
        if n == 0:
            return 0.0
        
        Q = matrix[:n, :n].copy()
        Q[:, removed_idx] = 0
        Q[removed_idx, :] = 0
        Q[removed_idx, removed_idx] = 0
        
        # 重新归一化
        row_sums = Q.sum(axis=1)
        row_sums[row_sums == 0] = 1.0
        Q = Q / row_sums[:, np.newaxis]
        
        I = np.eye(n)
        try:
            N = np.linalg.inv(I - Q)
            R = matrix[:n, n:]
            absorption = N @ R
            return absorption.mean()
        except np.linalg.LinAlgError:
            return 0.0


# 使用示例
markov = MarkovAttribution()
paths = [
    ['search', 'display', 'search'],
    ['search', 'search'],
    ['display', 'search'],
    ['search', 'email', 'search'],
]
markov.fit(paths)
effects = markov.get_removal_effect()
print("移除效应:")
for state, effect in effects.items():
    print(f"  {state}: {effect:.4f}")
```

---

## 第三部分：增量测量 (Incrementality)

### 3.1 增量测量的核心

```
增量测量回答的核心问题：
"如果没有投放广告，用户还会转化吗？"

Incrementality = Treatment_Conversions - Control_Conversions

其中:
├─ Treatment: 暴露于广告的用户
└─ Control: 未暴露于广告的用户（对照组）

Google 使用的增量测量方法：
1. Geo Experiments (地理实验)
   └─ 将市场分为 Treatment 和 Control 组
   └─ 比较两组之间的差异

2. Holdout (人群保留)
   └─ 随机选择一小部分用户不参与广告
   └─ 自然对照

3. Lift Studies (提升研究)
   └─ Survey-based: 询问用户是否看到过广告
   └─ 比较看到和没看到广告的用户之间的差异
```

### 3.2 Lift Study 实现

```python
# attribution/lift_study.py
class LiftStudy:
    """
    Lift Study (提升研究)
    
    测量广告的真实提升效果
    """
    
    def design_study(self, total_users: int, 
                     sample_size: int = 10000) -> dict:
        """
        设计提升研究
        
        参数:
        ├── total_users: 总用户数
        └── sample_size: 样本量
        """
        return {
            'treatment_group': int(sample_size * 0.5),
            'control_group': int(sample_size * 0.5),
            'survey': {
                'question': 'Have you seen an ad for [brand] in the past 7 days?',
                'options': ['Yes', 'No'],
            },
        }
    
    def analyze_lift(self, treatment_data: dict,
                     control_data: dict) -> dict:
        """
        分析提升效果
        
        参数:
        ├── treatment_data: 实验组数据
        └── control_data: 对照组数据
        """
        # 计算转化率
        treatment_rate = treatment_data['conversions'] / max(
            treatment_data['total'], 1)
        control_rate = control_data['conversions'] / max(
            control_data['total'], 1)
        
        # 绝对提升
        absolute_lift = treatment_rate - control_rate
        
        # 相对提升
        relative_lift = (treatment_rate / max(control_rate, 0.001)) - 1
        
        # 统计显著性 (Z-test)
        z_stat = self._z_test(
            treatment_data['conversions'], treatment_data['total'],
            control_data['conversions'], control_data['total'],
        )
        
        p_value = self._p_value_from_z(z_stat)
        
        return {
            'absolute_lift': absolute_lift,
            'relative_lift': relative_lift,
            'z_statistic': z_stat,
            'p_value': p_value,
            'significant': p_value < 0.05,
        }
    
    def _z_test(self, n1: int, n2: int, x1: int, x2: int) -> float:
        """Z-test for two proportions"""
        p1 = x1 / max(n1, 1)
        p2 = x2 / max(n2, 1)
        p_pool = (x1 + x2) / max(n1 + n2, 1)
        
        se = np.sqrt(p_pool * (1 - p_pool) * (1/max(n1,1) + 1/max(n2,1)))
        
        if se == 0:
            return 0.0
        
        return (p1 - p2) / se
    
    def _p_value_from_z(self, z: float) -> float:
        """从 Z 值获取 p 值"""
        # 正态分布 CDF
        from scipy import stats
        return 2 * (1 - stats.norm.cdf(abs(z)))
```

---

## 第四部分：归因实战

### 4.1 归因配置策略

```
Google Ads 归因配置最佳实践：

1. 转化窗口设置:
   ├── Click-Through Window: 30 天 (默认)
   ├── View-Through Window: 7 天 (默认)
   └── 建议: 保持默认，不要随意修改

2. 归因模型选择:
   ├── Last Click: 简单，但偏向转化前触点
   ├── Data-Driven: 推荐，自动优化
   └── 建议: 使用 Data-Driven，让 Google 自动优化

3. 跨设备归因:
   ├── Google 自动追踪跨设备行为
   ├── 需要 Google Ads 账号登录
   └── 建议在 GTM 中启用跨设备追踪

4. 自定义转化:
   ├── 关键转化 (Value): 计入归因
   ├── 非关键转化 (Non-Value): 不计入归因
   └── 建议: 只有最终转化是关键转化
```

### 4.2 归因排障

```
归因问题排查清单：

1. 转化数量突然下降
   ── 检查: 转化追踪代码是否正常工作
   ── 检查: gclid 是否正确传递
   ── 检查: 归因窗口是否变更

2. 某些渠道转化归因异常
   ── 检查: 是否启用了跨渠道归因
   ── 检查: 归因模型是否切换
   ── 检查: 是否有重复转化

3. Data-Driven 归因不可用
   ── 检查: 每月是否有 15+ 转化
   ── 检查: 是否使用了多个广告系列
   ── 检查: 数据是否完整
```

---

## 自测题

### 问题 1
gclid 在归因中起什么作用？

<details>
<summary>查看答案</summary>

- gclid 是 Google 生成的唯一点击 ID
- 它将点击事件和转化事件关联起来
- 落地页通过 URL 参数接收 gclid
- 转化时回传 gclid，Google 据此匹配
</details>

### 问题 2
Markov Chain 归因的核心思想是什么？

<details>
<summary>查看答案</summary>

- 将用户旅程建模为状态转移
- 计算移除每个触点后的转化率变化（移除效应）
- 移除效应越大，该触点的价值越高
- 无需假设固定的归因权重
</details>

### 问题 3
为什么需要增量测量？

<details>
<summary>查看答案</summary>

- 归因模型可能会高估广告效果
- 增量测量测量"如果没有广告，用户还会转化吗"
- 通过实验设计 (A/B test) 获得真实增量
- 指导预算分配，避免浪费
</details>

---

## 动手验证

### 4.1 Markov 归因

```python
from attribution.markov import MarkovAttribution

markov = MarkovAttribution()
paths = [
    ['search', 'display', 'search'],
    ['search', 'search'],
    ['display', 'search'],
    ['search', 'email', 'search'],
]
markov.fit(paths)
effects = markov.get_removal_effect()

for state, effect in effects.items():
    print(f"{state}: 移除效应 = {effect:.4f}")
```

---

### 数据回流归因的 Go 实现

```go
// 数据回流归因: Markov Chain + 增量归因引擎 Go 实现
package attribution

import (
	"fmt"
	"math"
	"sort"
	"time"
)

// Channel 广告渠道
type Channel struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

// ChannelImpact 渠道影响值
type ChannelImpact struct {
	ChannelID       string  `json:"channel_id"`
	OriginalValue   float64 `json:"original_value"`
	RemovalValue    float64 `json:"removal_value"`
	AttributionValue float64 `json:"attribution_value"`
	ConversionRate  float64 `json:"conversion_rate"`
	RemovalImpact   float64 `json:"removal_impact"`
}

// MarkovAttribution Markov 链归因引擎
type MarkovAttribution struct {
	channels    map[string]*Channel
	transitions map[string]map[string]float64 // from -> to -> count
	conversions map[string]float64             // channel -> conversion count
}

// NewMarkovAttribution 创建归因引擎
func NewMarkovAttribution() *MarkovAttribution {
	return &MarkovAttribution{
		channels:    make(map[string]*Channel),
		transitions: make(map[string]map[string]float64),
		conversions: make(map[string]float64),
	}
}

// AddChannel 注册渠道
func (m *MarkovAttribution) AddChannel(ch *Channel) {
	m.channels[ch.ID] = ch
}

// AddPath 添加转化路径
func (m *MarkovAttribution) AddPath(path []string, converted bool) {
	for i := 0; i < len(path); i++ {
		from := path[i]
		if m.transitions[from] == nil {
			m.transitions[from] = make(map[string]float64)
		}
		if i+1 < len(path) {
			to := path[i+1]
			m.transitions[from][to]++
		}
	}
	if converted {
		if last := path[len(path)-1]; last != "" {
			m.conversions[last]++
		}
	}
}

// ComputeImpact 计算各渠道影响值
func (m *MarkovAttribution) ComputeImpact() []*ChannelImpact {
	impacts := make([]*ChannelImpact, 0, len(m.channels))
	totalConversions := 0.0
	for _, c := range m.conversions {
		totalConversions += c
	}

	for chID := range m.channels {
		originalCR := m.calcConversionRate()
		removalCR := m.calcConversionRateWithChannel(chID, true)

		attribution := 0.0
		if totalConversions > 0 {
			attribution = (originalCR - removalCR) / totalConversions * totalConversions
		}
		impact := originalCR - removalCR

		impacts = append(impacts, &ChannelImpact{
			ChannelID:        chID,
			OriginalValue:    originalCR,
			RemovalValue:     removalCR,
			AttributionValue: attribution,
			ConversionRate:   originalCR,
			RemovalImpact:    impact,
		})
	}

	sort.Slice(impacts, func(i, j int) bool {
		return impacts[i].AttributionValue > impacts[j].AttributionValue
	})
	return impacts
}

func (m *MarkovAttribution) calcConversionRate() float64 {
	totalTransitions := 0.0
	for _, targets := range m.transitions {
		for _, count := range targets {
			totalTransitions += count
		}
	}
	if totalTransitions == 0 {
		return 0
	}
	return float64(len(m.conversions)) / totalTransitions
}

func (m *MarkovAttribution) calcConversionRateWithChannel(removeCh string, remove bool) float64 {
	// 简化计算: 移除该渠道的转移概率
	// 实际实现需要做马尔可夫链求解
	baseRate := m.calcConversionRate()
	if !remove {
		return baseRate
	}
	return baseRate * 0.8 // 简化: 移除一个渠道降低 20% 转化率
}

// IncrementalROI 增量 ROI 计算
type IncrementalROI struct {
	GroupControl   *TestGroup
	Treatment      *TestGroup
	IncrementalConv float64
	IncrementalROI  float64
}

type TestGroup struct {
	Users    int
	Convs    int
	Spend    float64
	Revenue  float64
}

// CalculateIncrementalROI 计算增量 ROI
func CalculateIncrementalROI(control, treatment *TestGroup) *IncrementalROI {
	controlCR := float64(control.Convs) / float64(control.Users)
	treatmentCR := float64(treatment.Convs) / float64(treatment.Users)
	incrementalCR := treatmentCR - controlCR
	incrementalConv := incrementalCR * float64(treatment.Users)
	incrementalCost := treatment.Spend - control.Spend
	incrementalRev := treatment.Revenue - control.Revenue
	incrementalROI := 0.0
	if incrementalCost > 0 {
		incrementalROI = incrementalRev / incrementalCost - 1
	}

	return &IncrementalROI{
		GroupControl:    control,
		Treatment:       treatment,
		IncrementalConv: incrementalConv,
		IncrementalROI:  incrementalROI,
	}
}

// ==================== 使用示例 ====================

func main() {
	// 1. Markov 归因
	attribution := NewMarkovAttribution()
	attribution.AddChannel(&Channel{ID: "tiktok", Name: "TikTok"})
	attribution.AddChannel(&Channel{ID: "meta", Name: "Meta"})
	attribution.AddChannel(&Channel{ID: "google", Name: "Google"})

	// 添加转化路径
	paths := [][]string{
		{"tiktok", "meta", "google", ""},
		{"meta", "google", ""},
		{"google", ""},
		{"tiktok", "google", ""},
		{"meta", ""},
	}
	for _, p := range paths {
		attribution.AddPath(p, true)
	}

	impacts := attribution.ComputeImpact()
	fmt.Println("=== Markov 归因结果 ===")
	for _, imp := range impacts {
		fmt.Printf("  %s: 归因 %.2f, 转化率 %.4f\n",
			imp.ChannelID, imp.AttributionValue, imp.ConversionRate)
	}

	// 2. 增量 ROI
	control := &TestGroup{Users: 10000, Convs: 50, Spend: 5000, Revenue: 15000}
	treatment := &TestGroup{Users: 10000, Convs: 80, Spend: 8000, Revenue: 24000}
	roi := CalculateIncrementalROI(control, treatment)
	fmt.Printf("\n=== 增量 ROI ===\n")
	fmt.Printf("  增量转化: %.0f, 增量 ROI: %.2f\n",
		roi.IncrementalConv, roi.IncrementalROI)
}
*答不出自测题？回去重读对应章节。*
