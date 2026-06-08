# 广告数据分析深度 — A/B Test、LTV/CAC、归因模型、ROI优化、多触点归因

> 标签: `#广告数据分析` `#A/B Test` `#LTV` `#CAC` `#归因模型` `#多触点` `#MTA` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. A/B Test — 统计原理与实现

### 1.1 统计原理

```python
# A/B Test 核心统计
import numpy as np
from scipy import stats

class ABTest:
    def __init__(self, alpha=0.05, power=0.8):
        self.alpha = alpha  # 显著性水平（犯第一类错误的概率）
        self.power = power  # 统计功效（1 - 犯第二类错误的概率）
    
    def calculate_sample_size(self, baseline_conversion, mde, alpha=0.05, power=0.8):
        """
        计算样本量
        baseline_conversion: 基准转化率（如 2%）
        mde: 最小可检测效应（如 10%，即期望检测到从 2% 到 2.2% 的变化）
        """
        p1 = baseline_conversion
        p2 = baseline_conversion * (1 + mde)
        
        # 使用正态近似
        z_alpha = stats.norm.ppf(1 - alpha/2)
        z_beta = stats.norm.ppf(power)
        
        numerator = (z_alpha * np.sqrt(2 * p1 * (1 - p1)) + 
                     z_beta * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
        denominator = (p1 - p2) ** 2
        
        n = numerator / denominator
        return int(np.ceil(n))
    
    def run_test(self, group_a_conversions, group_a_exposures, 
                 group_b_conversions, group_b_exposures):
        """
        运行 A/B Test 检验
        """
        # 计算转化率
        p_a = group_a_conversions / group_a_exposures
        p_b = group_b_conversions / group_b_exposures
        
        # 合并方差
        p_pool = (group_a_conversions + group_b_conversions) / (
            group_a_exposures + group_b_exposures)
        
        # 标准误差
        se = np.sqrt(p_pool * (1 - p_pool) * (1/group_a_exposures + 1/group_b_exposures))
        
        # Z 分数
        z = (p_b - p_a) / se
        
        # p 值（双尾检验）
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        
        # 置信区间
        ci_lower = (p_b - p_a) - 1.96 * se
        ci_upper = (p_b - p_a) + 1.96 * se
        
        return {
            'conversion_a': p_a,
            'conversion_b': p_b,
            'lift': (p_b - p_a) / p_a if p_a > 0 else 0,
            'z_score': z,
            'p_value': p_value,
            'ci_95': (ci_lower, ci_upper),
            'significant': p_value < self.alpha
        }
    
    def sequential_test(self, data_series, alpha=0.05, peeking_corrected=True):
        """
        序贯检验（允许中途检查）
        使用 O'Brien-Fleming 边界校正 peeking
        """
        n = len(data_series)
        adjusted_alpha = alpha  # 基础 alpha
        
        results = []
        for i in range(2, n + 1):
            # O'Brien-Fleming 边界
            t = i / n  # 信息分数
            boundary = stats.norm.ppf(1 - adjusted_alpha / (2 * np.sqrt(t)))
            
            z = self._calculate_z(data_series[:i])
            results.append({
                'sample_size': i,
                'z_score': z,
                'boundary': boundary,
                'significant': abs(z) > boundary
            })
            
            if results[-1]['significant']:
                return results  # 提前停止
        
        return results
```

### 1.2 多变量 A/B Test

```java
// 多变量测试（MVT）: 同时测试多个维度
// 如: 测试 3 个广告创意 × 2 种定价 = 6 种组合
// 
// 实验设计:
// - Full Factorial: 2³ = 8 种组合（创意1/创意2 × 定价1/定价2 × 位置1/位置2）
// - Fractional Factorial: 2^(k-p) 种组合（p = 分数度）
// - Taguchi Design: 正交设计，减少实验次数
//
class MultivariateTest {
    // 正交数组: 用最小实验次数覆盖最大组合
    // 如 L4(2³): 4 个实验覆盖 3 个因素各 2 水平
    
    public MVTResult run(MVTDesign design) {
        // 1. 分配实验单元到各组
        List<ExperimentGroup> groups = design.generateGroups();
        
        // 2. 执行实验，收集数据
        Map<String, List<DataPoint>> results = new HashMap<>();
        for (ExperimentGroup group : groups) {
            List<DataPoint> data = experimentService.run(group);
            results.put(group.getId(), data);
        }
        
        // 3. 方差分析（ANOVA）
        ANOVATable anova = this.anova(results);
        
        // 4. 交互效应分析
        Map<String, Double> interactions = this.analyzeInteractions(results);
        
        // 5. 多重检验校正（Bonferroni / Benjamini-Hochberg）
        List<Double> pValues = extractPValues(anova);
        List<Double> adjustedPValues = bonferroniCorrection(pValues, pValues.size());
        
        return new MVTResult(anova, interactions, adjustedPValues);
    }
    
    // Bonferroni 校正:
    // adjusted_p = min(p × m, 1)
    // 其中 m = 比较次数
    private List<Double> bonferroniCorrection(List<Double> pValues, int m) {
        return pValues.stream()
            .map(p -> Math.min(p * m, 1.0))
            .collect(Collectors.toList());
    }
    
    // Benjamini-Hochberg 校正（控制 FDR）:
    // 1. 排序 p 值
    // 2. 计算 adjusted_p = p_i × m / i
    // 3. 从大到小调整
    private List<Double> benjaminiHochbergCorrection(List<Double> pValues, int m) {
        List<Double> sorted = new ArrayList<>(pValues);
        Collections.sort(sorted);
        
        List<Double> adjusted = new ArrayList<>();
        for (int i = 0; i < sorted.size(); i++) {
            double adj = sorted.get(i) * m / (i + 1);
            adjusted.add(Math.min(adj, 1.0));
        }
        
        // 从大到小调整
        for (int i = adjusted.size() - 2; i >= 0; i--) {
            adjusted.set(i, Math.max(adjusted.get(i), adjusted.get(i + 1)));
        }
        
        return adjusted;
    }
}
```

---

## 2. LTV/CAC — 用户价值分析

### 2.1 LTV 计算

```python
# LTV (LifeTime Value) 计算
class LTVCalculator:
    def __init__(self, cohort_data):
        """
        cohort_data: 按月份分组的用户数据
        {
            '2024-01': {'users': 10000, 'revenue': [10000, 5000, 3000, ...]},  # 每月收入
            '2024-02': {'users': 12000, 'revenue': [12000, 6000, 3600, ...]},
        }
        """
        self.cohort_data = cohort_data
    
    def calculate_retention(self, cohort_revenues):
        """
        计算留存率
        """
        initial_users = len(cohort_revenues)
        if initial_users == 0:
            return []
        
        retention = []
        for i, revenue in enumerate(cohort_revenues):
            retention.append(revenue / cohort_revenues[0] if cohort_revenues[0] > 0 else 0)
        
        return retention
    
    def calculate_ltv(self, monthly_arpu, retention_curve, discount_rate=0.1):
        """
        LTV = Σ (ARPU_m × Retention_m) / (1 + r)^m
        考虑货币时间价值
        """
        ltv = 0
        for m, retention in enumerate(retention_curve):
            # 折现因子
            discount = (1 + discount_rate) ** m
            ltv += (monthly_arpu * retention) / discount
        
        return ltv
    
    def calculate_cohort_ltv(self, cohort_id):
        """
        按 cohort 计算 LTV
        """
        cohort = self.cohort_data[cohort_id]
        users = cohort['users']
        revenues = cohort['revenue']
        
        # 计算月度 ARPU
        monthly_arpu = revenues[0] / users  # 首月 ARPU
        
        # 计算留存曲线
        retention = self.calculate_retention(revenues)
        
        # 计算 LTV
        ltv = self.calculate_ltv(monthly_arpu, retention)
        
        return {
            'cohort': cohort_id,
            'users': users,
            'monthly_arpu': monthly_arpu,
            'ltv': ltv,
            'retention_curve': retention
        }
```

### 2.2 CAC 与 ROI

```python
# CAC (Customer Acquisition Cost) 计算
class CACCalculator:
    def __init__(self, marketing_data):
        """
        marketing_data:
        {
            'channel': 'Facebook',
            'spend': 10000,
            'impressions': 1000000,
            'clicks': 10000,
            'signups': 500,
            'pays': 100
        }
        """
        self.marketing_data = marketing_data
    
    def calculate_cac(self):
        """
        CAC = Total Marketing Spend / Number of New Customers
        """
        total_spend = self.marketing_data['spend']
        new_customers = self.marketing_data.get('pays', self.marketing_data.get('signups', 0))
        
        return total_spend / new_customers if new_customers > 0 else 0
    
    def calculate_roi(self, ltv, cac):
        """
        ROI = (LTV - CAC) / CAC
        LTV:CAC ratio >= 3 被认为是健康的
        """
        if cac == 0:
            return float('inf')
        
        roi = (ltv - cac) / cac
        ratio = ltv / cac
        
        return {
            'roi': roi,
            'ltv_cac_ratio': ratio,
            'healthy': ratio >= 3.0  # 行业健康标准
        }
    
    def calculate_payback_period(self, monthly_arpu, cac):
        """
        回本周期（月）
        Payback Period = CAC / (ARPU × Gross Margin)
        """
        gross_margin = 0.7  # 假设毛利率 70%
        if monthly_arpu * gross_margin == 0:
            return float('inf')
        
        return cac / (monthly_arpu * gross_margin)
```

### 2.3 多触点归因模型（MTA）

```python
# 多触点归因（Multi-Touch Attribution）
class MultiTouchAttribution:
    def __init__(self, conversion_paths):
        """
        conversion_paths: 转化路径
        [
            ['impression:facebook', 'click:google', 'conversion'],
            ['impression:twitter', 'click:facebook', 'conversion'],
            ...
        ]
        """
        self.paths = conversion_paths
    
    def last_click(self):
        """
        最后点击归因: 100% 归因于最后一次点击
        """
        attribution = {}
        for path in self.paths:
            # 找到最后一次点击
            last_click = None
            for touchpoint in path:
                if touchpoint.startswith('click:'):
                    last_click = touchpoint.split(':')[1]
            
            if last_click:
                attribution[last_click] = attribution.get(last_click, 0) + 1
        
        return self._normalize(attribution)
    
    def first_click(self):
        """
        首次点击归因: 100% 归因于第一次点击
        """
        attribution = {}
        for path in self.paths:
            first_touch = path[0] if path.startswith('click:') else None
            if first_touch:
                channel = first_touch.split(':')[1]
                attribution[channel] = attribution.get(channel, 0) + 1
        
        return self._normalize(attribution)
    
    def linear(self):
        """
        线性归因: 所有触点平均分配
        """
        attribution = {}
        for path in self.paths:
            clicks = [t for t in path if t.startswith('click:')]
            if clicks:
                credit = 1.0 / len(clicks)
                for click in clicks:
                    channel = click.split(':')[1]
                    attribution[channel] = attribution.get(channel, 0) + credit
        
        return self._normalize(attribution)
    
    def time_decay(self, half_life=7):
        """
        时间衰减归因: 越接近转化的触点获得越高权重
        weight = 2^(-distance / half_life)
        """
        attribution = {}
        for path in self.paths:
            clicks = [(i, t) for i, t in enumerate(path) if t.startswith('click:')]
            if clicks:
                total_weight = 0
                weighted = []
                for i, click in clicks:
                    distance = len(path) - 1 - i
                    weight = 2 ** (-distance / half_life)
                    weighted.append((click.split(':')[1], weight))
                    total_weight += weight
                
                for channel, weight in weighted:
                    attribution[channel] = attribution.get(channel, 0) + weight / total_weight
        
        return self._normalize(attribution)
    
    def position_based(self, first_weight=0.4, last_weight=0.4):
        """
        位置归因: 首次和最后各占 40%，中间平均分配 20%
        """
        attribution = {}
        for path in self.paths:
            clicks = [t for t in path if t.startswith('click:')]
            if clicks:
                if len(clicks) == 1:
                    channel = clicks[0].split(':')[1]
                    attribution[channel] = attribution.get(channel, 0) + 1
                else:
                    # 首次
                    first_channel = clicks[0].split(':')[1]
                    attribution[first_channel] = attribution.get(first_channel, 0) + first_weight
                    # 最后
                    last_channel = clicks[-1].split(':')[1]
                    attribution[last_channel] = attribution.get(last_channel, 0) + last_weight
                    # 中间
                    middle_credit = (1 - first_weight - last_weight) / (len(clicks) - 2)
                    for click in clicks[1:-1]:
                        channel = click.split(':')[1]
                        attribution[channel] = attribution.get(channel, 0) + middle_credit
        
        return self._normalize(attribution)
    
    def shapley_value(self):
        """
        夏普利值归因（Shapley Value）: 考虑所有可能的触点组合
        最公平但计算复杂度 O(2^n)
        """
        attribution = {}
        
        for path in self.paths:
            clicks = [t.split(':')[1] for t in path if t.startswith('click:')]
            n = len(clicks)
            
            if n == 0:
                continue
            
            # 计算所有子集的边际贡献
            from itertools import combinations
            
            total_credit = 0
            for i in range(n):
                for subset in combinations(clicks[:-1], i):
                    subset_size = len(subset)
                    # 夏普利权重: 1 / (n * C(n-1, i))
                    weight = 1.0 / (n * math.comb(n-1, i))
                    
                    # 包含当前触点的子集贡献
                    coalition_with = set(subset) | {clicks[-1]}
                    coalition_without = set(subset)
                    
                    # 边际贡献
                    marginal = self._value(coalition_with, path) - self._value(coalition_without, path)
                    
                    total_credit += weight * marginal
            
            # 分配到各触点
            for channel in clicks:
                attribution[channel] = attribution.get(channel, 0) + total_credit / n
        
        return self._normalize(attribution)
    
    def _value(self, coalition, path):
        """
        计算子集的转换概率
        """
        coalition_set = set(coalition)
        for touchpoint in path:
            if touchpoint.startswith('click:'):
                channel = touchpoint.split(':')[1]
                if channel in coalition_set:
                    return 1.0
        return 0.0
    
    def _normalize(self, attribution):
        """
        归一化
        """
        total = sum(attribution.values())
        if total > 0:
            return {k: v / total for k, v in attribution.items()}
        return attribution
```

---

## 3. 归因模型对比

```
┌──────────────┬───────────┬───────────┬───────────┬──────────────┬──────────────┐
│   归因模型    │  公平性   │  计算复杂度│  适用场景  │  优点        │  缺点        │
├──────────────┼───────────┼───────────┼───────────┼──────────────┼──────────────┤
│ Last Click   │  低       │  O(n)     │  简单漏斗  │  实现简单    │  忽略其他触点│
│ First Click  │  低       │  O(n)     │  品牌认知  │  发现获客渠道│  忽略转化触点│
│ Linear       │  中       │  O(n)     │  全渠道    │  公平分配    │  不区分触点价值│
│ Time Decay   │  中       │  O(n)     │  长决策链  │  重视近期触点│  参数敏感    │
│ Position     │  中       │  O(n)     │  关键触点  │  重视首末触点│  参数主观    │
│ Shapley Value│  高       │  O(2^n)   │  精确归因  │  数学上公平  │  计算复杂    │
└──────────────┴───────────┴───────────┴───────────┴──────────────┴──────────────┘

选择建议:
1. 快速迭代: 使用 Last Click 或 First Click
2. 全渠道分析: 使用 Linear 或 Time Decay
3. 关键触点分析: 使用 Position-Based
4. 高精度归因: 使用 Shapley Value（大数据量时用 Monte Carlo 近似）
```

---

## 4. ROI 优化

### 4.1 预算分配优化

```python
# 预算分配优化（多臂老虎机问题）
import numpy as np
from scipy.optimize import minimize

class BudgetOptimizer:
    def __init__(self, channels):
        """
        channels: 各渠道的数据
        [
            {'name': 'facebook', 'spend': 10000, 'conversions': 500},
            {'name': 'google', 'spend': 15000, 'conversions': 750},
            {'name': 'tiktok', 'spend': 8000, 'conversions': 400},
        ]
        """
        self.channels = channels
    
    def calculate_roas(self):
        """
        计算各渠道 ROAS
        """
        for channel in self.channels:
            roas = channel['conversions'] / channel['spend'] if channel['spend'] > 0 else 0
            channel['roas'] = roas
        return self.channels
    
    def optimize_budget(self, total_budget, beta_params=None):
        """
        优化预算分配（使用 Beta-Binomial 模型）
        
        目标: max Σ (channel[i] × p_i × v_i) - Σ (channel[i] × c_i)
        约束: Σ channel[i] <= total_budget
        
        使用 Bayesian A/B Testing 估计各渠道的转化率
        """
        if beta_params is None:
            beta_params = [
                {'alpha': 1, 'beta': 1} for _ in self.channels
            ]
        
        def objective(x):
            """
            负目标函数（最小化）
            x: 各渠道预算分配比例
            """
            total_value = 0
            for i, channel in enumerate(self.channels):
                budget = x[i] * total_budget
                p = beta_params[i]['alpha'] / (beta_params[i]['alpha'] + beta_params[i]['beta'])
                value = budget * p * channel.get('value_per_conversion', 10)
                total_value -= value  # 负号因为 minimize 是最小化
            
            return total_value
        
        # 约束: 总和 = total_budget
        constraints = [{'type': 'eq', 'fun': lambda x: sum(x) - 1}]
        
        # 边界: 0 <= x[i] <= 1
        bounds = [(0, 1) for _ in self.channels]
        
        # 初始解: 按 ROAS 比例
        roas = [c.get('roas', 0) for c in self.channels]
        x0 = [r / sum(roas) if sum(roas) > 0 else 1/len(roas) for r in roas]
        
        result = minimize(objective, x0, method='SLSQP', 
                         bounds=bounds, constraints=constraints)
        
        if result.success:
            allocation = {
                self.channels[i]['name']: result.x[i] * total_budget
                for i in range(len(self.channels))
            }
            return allocation
        else:
            # 回退: 按 ROAS 比例
            return self._roas_based_allocation(total_budget)
    
    def _roas_based_allocation(self, total_budget):
        """
        基于 ROAS 的比例分配
        """
        roas = [c.get('roas', 0) for c in self.channels]
        total_roas = sum(roas)
        
        allocation = {}
        for i, channel in enumerate(self.channels):
            allocation[channel['name']] = (roas[i] / total_roas * total_budget 
                                          if total_roas > 0 else total_budget / len(self.channels))
        
        return allocation
```

### 4.2 出价优化

```python
# 出价优化（oCPX）
class BidOptimizer:
    def __init__(self, model):
        self.model = model  # pCTR × pCVR 模型
    
    def calculate_optimal_bid(self, ad, user, context, target_cpa):
        """
        oCPX 最优出价计算
        
        目标: max E[revenue] = pCTR × pCVR × bid
        
        在给定目标 CPA 下，最优出价为:
        bid = target_cpa × pCVR × confidence
        
        其中 confidence 是模型预测的置信度（0-1）
        """
        # 预测 pCTR 和 pCVR
        p_ctr = self.model.predict_ctr(ad, user, context)
        p_cvr = self.model.predict_cvr(ad, user, context)
        
        # 模型置信度（基于训练数据量和特征覆盖度）
        confidence = self.model.get_confidence(ad, user, context)
        
        # 出价 = target_cpa × pCVR × confidence
        bid = target_cpa * p_cvr * confidence
        
        # 预算约束
        bid = self._apply_budget_constraint(bid, ad)
        
        # 竞价策略调整
        bid = self._apply_bidding_strategy(bid, ad.strategy, ad.history)
        
        return {
            'bid': bid,
            'p_ctr': p_ctr,
            'p_cvr': p_cvr,
            'expected_cpa': target_cpa / confidence if confidence > 0 else target_cpa,
            'confidence': confidence
        }
    
    def _apply_budget_constraint(self, bid, ad):
        """
        应用预算约束
        """
        daily_budget = ad.daily_budget
        avg_bid = ad.avg_bid
        
        if daily_budget and avg_bid:
            # 如果预算紧张，降低出价
            remaining_budget = daily_budget - ad.spent_today
            if remaining_budget < 0:
                return bid * 0.5  # 严重超预算，降低 50%
            elif remaining_budget < daily_budget * 0.2:
                return bid * 0.8  # 预算紧张，降低 20%
        
        return bid
    
    def _apply_bidding_strategy(self, bid, strategy, history):
        """
        根据竞价策略调整
        """
        if strategy == 'AGGRESSIVE':
            return bid * 1.2  # 激进出价，高出 20%
        elif strategy == 'CONSERVATIVE':
            return bid * 0.8  # 保守出价，低出 20%
        elif strategy == 'OPTIMIZED':
            # 基于历史 CPA 动态调整
            historical_cpa = history.get('avg_cpa', 0)
            if historical_cpa > bid:
                return bid * 0.9  # 历史 CPA 偏高，降低出价
            else:
                return bid * 1.1  # 历史 CPA 偏低，提高出价
        
        return bid
```

---

*本文档基于广告数据分析原理整理，覆盖 A/B Test、LTV/CAC、归因模型、ROI 优化*
