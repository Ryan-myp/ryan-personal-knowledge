# 广告数据分析 — A/B Test、LTV/CAC、归因模型、ROI优化

> 标签: `#广告数据分析` `#A/B Test` `#LTV` `#CAC` `#归因模型` `#ROI`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. A/B Test 统计原理

### 1.1 A/B Test 框架

```
A/B Test 目标:
  验证新策略（Treatment）是否显著优于基线（Control）

核心假设:
  H0（原假设）: Treatment 和 Control 无差异
  H1（备择假设）: Treatment 优于/劣于 Control
  
统计检验:
  - 正态检验: Z-test（样本量 > 30）
  - T检验: T-test（样本量 < 30 或方差未知）
  - 卡方检验: Chi-square（分类变量）
  - 非参数检验: Mann-Whitney U（非正态分布）

关键指标:
  - 样本量: 需要多少用户才能检测到显著差异
  - 置信水平（Confidence Level）: 通常 95%
  - 统计功效（Power）: 通常 80%
  - 最小可检测效应（MDE）: 业务上认为有意义的效应大小
  - p-value: 拒绝 H0 的显著性水平
```

### 1.2 样本量计算

```
样本量公式（均值比较）:
  n = 2 * (Z_α/2 + Z_β)² * σ² / δ²
  
  其中:
  - Z_α/2: 置信水平对应的 Z 值（95% → 1.96）
  - Z_β: 功效对应的 Z 值（80% → 0.84）
  - σ: 标准差
  - δ: 最小可检测效应（MDE）

示例:
  基线转化率: 2%
  MDE: 10%（即检测出 2.2% vs 2%）
  置信水平: 95%
  功效: 80%
  
  n = 2 * (1.96 + 0.84)² * p * (1-p) / δ²
  n = 2 * 7.84 * 0.02 * 0.98 / 0.0004
  n ≈ 7683  per group
  
  总样本: ~15,366 用户

多变量 A/B Test:
  - 正交设计: 测试互不影响的维度
  - 分层设计: 将用户分层，分别测试
  - Factorial Design: 多因素同时测试
  - 注意: 避免变量交叉影响
```

### 1.3 显著性检验实战

```python
# Python 示例: 双样本比例检验
from scipy import stats

# 数据
control_conversions = 1536  # 7683 * 2%
control_exposures = 7683

treatment_conversions = 1769  # 7683 * 2.3%
treatment_exposures = 7683

# Z-test 比例检验
z_stat, p_value = stats.proportions_ztest(
    [treatment_conversions, control_conversions],
    [treatment_exposures, control_exposures],
    alternative='two-sided'
)

print(f"Z-statistic: {z_stat:.4f}")
print(f"P-value: {p_value:.6f}")

# 置信区间
from statsmodels.stats.proportion import proportion_confint

ci_lower, ci_upper = proportion_confint(
    treatment_conversions, treatment_exposures, alpha=0.05
)
print(f"95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]")

# 结果解读:
# p-value < 0.05 → 拒绝 H0 → 差异显著
# 置信区间不包含 0 → 差异显著
```

### 1.4 A/B Test 常见陷阱

```
辛普森悖论（Simpson's Paradox）:
  整体趋势 vs 分层趋势相反
  
  示例:
  - 整体: Treatment 转化率更高
  - 分层（iOS/Android）: Control 转化率更高
  - 原因: Treatment 组中低转化渠道（如 Android）用户占比更高
  
  解决: 分层分析（Stratified Analysis）

peeking problem（窥探问题）:
  - 问题: 在测试未结束时频繁检查 p-value
  - 导致: 假阳性率升高
  - 解决: 预先确定样本量，或使用序贯检验（Sequential Testing）

网络效应（Network Effects）:
  - 问题: Treatment 组的用户行为影响 Control 组
  - 示例: 社交网络中，Treatment 组用户被优化，影响 Control 组好友
  - 解决: 吉尔赫斯特抽样（HGT）或地理隔离

新奇效应（Novelty Effect）:
  - 问题: 用户因新奇而暂时改变行为
  - 解决: 测试足够长时间（≥ 2 周）

多重比较问题:
  - 问题: 同时测试多个指标/分组
  - 解决: Bonferroni 校正或 False Discovery Rate (FDR)
```

---

## 2. LTV/CAC 模型

### 2.1 核心指标定义

```
LTV (Lifetime Value):
  用户在整个生命周期内为企业创造的总价值
  
  LTV = ARPU * 平均用户生命周期
  或: LTV = Σ (ARPU_t * P(存活到 t))  for t = 0, 1, 2, ...
  
  ARPU (Average Revenue Per User):
    ARPU = 总收入 / 活跃用户数
    可按日/周/月计算

CAC (Customer Acquisition Cost):
  获取一个用户的成本
  
  CAC = 总营销费用 / 新增用户数
  可按渠道细分: CAC_channel = 渠道费用 / 渠道新增用户

ROI (Return on Investment):
  ROI = (LTV - CAC) / CAC
  或: ROI = LTV / CAC - 1
  
LTV/CAC Ratio:
  - LTV/CAC > 3: 健康
  - LTV/CAC = 1-3: 需优化
  - LTV/CAC < 1: 亏损
  
Payback Period（回本周期）:
  Payback = CAC / 月 ARPU
  - < 6 个月: 优秀
  - 6-12 个月: 可接受
  - > 12 个月: 风险高
```

### 2.2 LTV 建模

```
LTV 建模方法:

1. 简单模型:
   LTV = ARPU * 平均生命周期
   
   示例:
   ARPU = $5/月
   月留存率 = 80%
   平均生命周期 = 1 / (1 - 0.8) = 5 个月
   LTV = $5 * 5 = $25

2. 用户分层 LTV:
   LTV = Σ (Segment_LTV_i * Segment_Users_i) / Total_Users
   
   示例:
   - 高端用户: ARPU=$20, 月留存=90%, LTV=$200, 占比 5%
   - 中端用户: ARPU=$5, 月留存=80%, LTV=$25, 占比 30%
   - 低端用户: ARPU=$1, 月留存=60%, LTV=$2.5, 占比 65%
   LTV = $200*0.05 + $25*0.3 + $2.5*0.65 = $10 + $7.5 + $1.625 = $19.125

3. 留存曲线建模:
   LTV = ARPU * Σ (R_t)  for t = 0, 1, 2, ...
   
   留存曲线拟合:
   R_t = a * t^b + c
   或使用 Kaplan-Meier 估计器

4. 概率模型:
   用户留存服从几何分布: P(留存到 t) = (1-p)^t
   LTV = ARPU * Σ ((1-p)^t) = ARPU / p
   
   或使用生存分析（Survival Analysis）
```

### 2.3 渠道 CAC 分析

```
渠道细分 CAC:
  CAC_total = Σ (Channel_CAC_i * Channel_Users_i) / Total_Users
  
  示例:
  | 渠道     | 费用    | 新增用户 | CAC    |
  |---------|---------|----------|--------|
  | Google  | $50,000 | 10,000   | $5.00  |
  | Facebook | $30,000 | 8,000   | $3.75  |
  | TikTok  | $20,000 | 15,000   | $1.33  |
  | 自然    | $0      | 20,000   | $0.00  |
  
  加权 CAC = ($50K + $30K + $20K) / (10K + 8K + 15K) = $100K / 33K = $3.03

归因模型对 CAC 的影响:
  - Last Click: 最后点击的渠道获得 100%  credited
  - First Click: 首次点击的渠道获得 100% credited
  - Linear: 均匀分配给所有触点
  - Time Decay: 越接近转化越多的 credit
  - Data-Driven: 基于实际数据分配 credit

渠道 ROI 分析:
  ROI_channel = (LTV_channel - CAC_channel) / CAC_channel
  
  示例:
  | 渠道     | CAC   | LTV   | LTV/CAC | ROI    |
  |---------|-------|-------|---------|--------|
  | Google  | $5.00 | $20.00| 4.0     | 300%   |
  | Facebook | $3.75| $15.00| 4.0     | 300%   |
  | TikTok  | $1.33 | $5.00 | 3.75    | 275%   |
  
  结论: 所有渠道 ROI 健康，TikTok 增长潜力最大
```

---

## 3. 归因模型

### 3.1 归因模型类型

```
归因模型（Attribution Model）:
  决定如何将转化 Credit 分配给各个营销触点

1. Last Click（最后点击）:
   100% Credit 给最后一个触点
   优点: 简单直观
   缺点: 忽略前期触点，偏向转化渠道

2. First Click（首次点击）:
   100% Credit 给第一个触点
   优点: 重视品牌曝光
   缺点: 忽略后期转化触点

3. Linear（线性）:
   所有触点均分 Credit
   优点: 公平
   缺点: 未考虑触点重要性差异

4. Time Decay（时间衰减）:
   越接近转化的触点获得越多 Credit
   公式: Credit ∝ 1 / (转化时间 - 触点时间)^α

5. Position-Based（位置基础）:
   首次点击 40%，末次点击 40%，中间触点平分 20%
   优点: 重视首尾触点
   缺点: 固定比例，不够灵活

6. Data-Driven（数据驱动）:
   基于实际数据（如 Shapley Value、Markov Chain）分配 Credit
   优点: 最准确
   缺点: 需要大量数据，计算复杂

Shapley Value 归因:
  来自博弈论，考虑所有可能的触点组合
  
  示例: 触点 A, B, C
  - A, B, C 顺序: A→B→C (C 贡献最大)
  - A, C, B 顺序: A→C→B (C 贡献最大)
  - B, A, C 顺序: B→A→C (C 贡献最大)
  - ...
  
  计算所有排列的边际贡献，取平均
  计算复杂度: O(2^n)
```

### 3.2 归因模型实战

```python
# 简单时间衰减归因
import numpy as np
from scipy import stats

def time_decay_attribution(touchpoints, conversion_date, alpha=1.5):
    """
    时间衰减归因
    :param touchpoints: 触点日期列表
    :param conversion_date: 转化日期
    :param alpha: 衰减系数
    :return: 各触点 Credit 分配
    """
    # 计算每个触点到转化的时间差（天）
    time_diffs = [(conversion_date - tp).days for tp in touchpoints]
    
    # 计算权重: 1 / time_diff^alpha
    weights = [1.0 / (t + 1) ** alpha for t in time_diffs]  # +1 避免除零
    
    # 归一化
    total = sum(weights)
    credits = [w / total for w in weights]
    
    return credits

# 示例:
# 触点: Day 1, Day 5, Day 10
# 转化: Day 15
touchpoints = [
    np.datetime64('2026-01-01'),
    np.datetime64('2026-01-05'),
    np.datetime64('2026-01-10')
]
conversion = np.datetime64('2026-01-15')

credits = time_decay_attribution(touchpoints, conversion, alpha=1.5)
print(f"触点 Credit: {[f'{c:.2%}' for c in credits]}")
# 输出: ['5.06%', '12.50%', '82.44%'] → 越接近转化 Credit 越大
```

### 3.3 多触点归因数据管道

```sql
-- 归因数据管道
-- 1. 用户行为日志
CREATE TABLE user_touchpoints (
    user_id STRING,
    touchpoint_date DATE,
    channel STRING,
    campaign_id STRING,
    content STRING
);

-- 2. 转化日志
CREATE TABLE conversions (
    user_id STRING,
    conversion_date DATE,
    conversion_value DECIMAL(10,2),
    conversion_type STRING
);

-- 3. 归因计算（时间衰减）
CREATE TABLE channel_attribution AS
WITH user_conversions AS (
    SELECT user_id, MAX(conversion_date) AS conv_date
    FROM conversions
    GROUP BY user_id
),
touchpoint_credits AS (
    SELECT 
        ut.user_id,
        ut.channel,
        ut.touchpoint_date,
        ut.campaign_id,
        1.0 / POWER(MAX(uc.conv_date) - ut.touchpoint_date + 1, 1.5) AS raw_weight
    FROM user_touchpoints ut
    JOIN user_conversions uc ON ut.user_id = uc.user_id
    GROUP BY ut.user_id, ut.channel, ut.touchpoint_date, ut.campaign_id
),
normalized_credits AS (
    SELECT 
        user_id,
        channel,
        campaign_id,
        raw_weight / SUM(raw_weight) OVER (PARTITION BY user_id) AS credit
    FROM touchpoint_credits
)
SELECT 
    channel,
    campaign_id,
    SUM(credit * COALESCE(cv.conversion_value, 0)) AS attributed_value,
    COUNT(DISTINCT user_id) AS attributed_users
FROM normalized_credits nc
LEFT JOIN conversions cv ON nc.user_id = cv.user_id
GROUP BY channel, campaign_id;
```

---

## 4. ROI 优化策略

### 4.1 ROI 优化框架

```
ROI 优化公式:
  ROI = (Revenue - Cost) / Cost
  
  优化方向:
  1. 提高 Revenue:
     - 提高转化率（CVR）
     - 提高客单价（AOV）
     - 提高复购率（Retention）
     - 提高用户生命周期（LTV）
  
  2. 降低成本:
     - 降低 CAC（优化渠道）
     - 降低 CPC/CPM（竞价优化）
     - 提高广告效率（创意优化）
  
  3. 平衡投入产出:
     - ROI ≥ 1: 继续投入
     - ROI < 1: 暂停或优化
     - ROI 最高渠道: 增加预算
     - ROI 最低渠道: 减少预算

ROI 优化迭代:
  1. 数据采集 → 2. 归因分析 → 3. A/B Test → 4. 策略调整 → 5. 监控
```

### 4.2 竞价优化

```
竞价策略:

1. 固定出价（Fixed Bid）:
   - 每次竞价固定出价
   - 简单，但不够灵活
   
2. 智能出价（Smart Bidding）:
   - Target CPA（目标每次转化费用）
   - Target ROAS（目标广告支出回报率）
   - Maximize Conversions（最大化转化）
   - Maximize Conversion Value（最大化转化价值）
   
3. 基于 ML 的竞价:
   p = P(conversion | features) * target_ROAS * bid_cap
   
   特征:
   - 用户特征: 历史行为、 demographics
   - 上下文特征: 时间、位置、设备
   - 广告特征: 创意、出价历史
   
   模型:
   - Logistic Regression（基础）
   - Gradient Boosting（XGBoost/LightGBM）
   - Deep Learning（DNN, Wide&Deep）
   - Multi-Task Learning（CTR + CVR）

RTB 竞价优化:
  出价 = v * pCTR * pCVR * pConversion
  其中:
  - v: 用户价值（LTV/单次价值）
  - pCTR: 点击率预估
  - pCVR: 转化率预估
  - pConversion: 转化概率
  
  优化目标:
  Maximize: Σ (v_i * p_i * bid_i) - Cost
  Subject to: Budget, ROI ≥ target
```

### 4.3 预算分配优化

```
预算分配问题:
  目标: 在多个渠道间分配预算，最大化总转化
  
  模型:
  Maximize: Σ f_i(b_i)
  Subject to: Σ b_i ≤ Budget, b_i ≥ 0
  
  其中 f_i(b_i) 是渠道 i 的转化函数（边际收益递减）

求解方法:
  1. 贪心算法: 每次分配给边际收益最高的渠道
  2. 动态规划: 精确求解（小规模）
  3. 凸优化: 如果 f_i 是凹函数
  4. 机器学习: 训练 f_i 模型，然后优化

实际案例:
  渠道: Google, Facebook, TikTok
  预算: $100K/月
  转化函数（经验拟合）:
    f_google(b) = 100 * ln(b + 1)
    f_facebook(b) = 80 * ln(b + 1)
    f_tiktok(b) = 120 * ln(b + 1)
  
  最优分配（近似）:
    Google: $35K → 转化 ≈ 380
    Facebook: $25K → 转化 ≈ 270
    TikTok: $40K → 转化 ≈ 440
    总转化 ≈ 1,090

ROI 监控仪表盘:
  | 渠道     | 预算    | 花费    | 转化  | CPA   | ROI  |
  |---------|---------|---------|-------|-------|------|
  | Google  | $35K    | $34K    | 380   | $89   | 2.1  |
  | Facebook | $25K   | $26K    | 270   | $96   | 1.8  |
  | TikTok  | $40K    | $39K    | 440   | $89   | 2.5  |
  | 合计    | $100K   | $99K    | 1,090 | $91   | 2.1  |
```

### 4.4 创意优化

```
创意 A/B Test:
  - 测试维度: 图片、文案、CTA、颜色、布局
  - 样本量: 每个变体 ≥ 1000 曝光
  - 显著性: p-value < 0.05
  
  创意 ROI 计算:
  ROI_creative = (Revenue_creative - Cost_creative) / Cost_creative
  
  创意库管理:
  - 高 ROI 创意 → 增加预算
  - 低 ROI 创意 → 替换或迭代
  - 创意疲劳 → 定期更换（CTR 下降 > 20%）

动态创意优化（DCO）:
  - 根据用户特征动态生成创意
  - 实时 A/B Test 组合
  - 机器学习优化创意参数
  
  示例:
  用户: 25-34 岁，女性，北京
  动态创意: 展示时尚类商品，文案强调"新品上市"，CTA"立即选购"
```

---

## 5. 数据基础设施

### 5.1 广告数据分析管道

```
数据管道架构:
┌─────────────────────────────────────────────────────────────┐
│                    数据采集层                                │
│  - 广告平台 API: Google Ads, Facebook Ads, TikTok Ads       │
│  - 网站埋点: GA4, Adobe Analytics, 自定义埋点                │
│  - 应用埋点: Firebase, 自定义 SDK                           │
│  - 服务器日志: Nginx, Application Log                       │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
┌────────┐ ┌────────┐ ┌────────┐
│Kafka   │ │Kafka   │ │Kafka   │
│(实时)  │ │(实时)  │ │(批量)  │
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────┐
│                   数据处理层                                 │
│  - Flink: 实时归因、实时竞价                               │
│  - Spark: 批量 LTV/CAC 计算、A/B Test 分析                  │
│  - dbt: 数据仓库建模、指标计算                              │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┼───────┐
       ▼       ▼       ▼
┌────────┐ ┌────────┐ ┌────────┐
│Hive    │ │Click   │ │Presto  │
│(ODS)   │ │House   │ │(Ad-Hoc│
│        │ │(OLAP)  │ │查询)   │
└────────┘ └────────┘ └────────┘
```

### 5.2 关键指标监控

```sql
-- 广告 ROI 监控看板
CREATE TABLE daily_roi AS
WITH channel_stats AS (
    SELECT 
        DATE(ts) AS dt,
        channel,
        SUM(impressions) AS impressions,
        SUM(clicks) AS clicks,
        SUM(conversions) AS conversions,
        SUM(spend) AS spend,
        SUM(revenue) AS revenue
    FROM ad_events
    GROUP BY DATE(ts), channel
),
channel_roi AS (
    SELECT 
        dt,
        channel,
        impressions,
        clicks,
        conversions,
        spend,
        revenue,
        clicks / NULLIF(impressions, 0) AS CTR,
        conversions / NULLIF(clicks, 0) AS CVR,
        spend / NULLIF(clicks, 0) AS CPC,
        spend / NULLIF(conversions, 0) AS CPA,
        revenue / spend AS ROAS,
        (revenue - spend) / spend AS ROI
    FROM channel_stats
)
SELECT * FROM channel_roi
WHERE dt >= DATE_SUB(CURRENT_DATE, 30)
ORDER BY dt DESC, channel;

-- 每日 ROI 预警
SELECT 
    channel,
    dt,
    ROI,
    LAG(ROI) OVER (PARTITION BY channel ORDER BY dt) AS prev_roi
FROM channel_roi
WHERE ROI < 1.0 
   OR (ROI < LAG(ROI) OVER (PARTITION BY channel ORDER BY dt) * 0.9);
```

---

*本文档覆盖广告数据分析核心方法论，基于实际投放场景整理*
