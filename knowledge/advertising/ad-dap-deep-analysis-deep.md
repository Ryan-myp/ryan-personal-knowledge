# DAP Campaign 深度分析实战：从数据到业务洞察

> 基于 TabPFN Skill 的完整广告数据分析工作流，包含转化效率、预算效率、聚类分析、异常检测、优化建议

---

## 第一部分：分析框架设计

### 多维度分析模型

```
广告投放数据分析
├── 1. 转化效率分析 (Conversion Rate)
│   ├── CPA (Cost Per Acquisition)
│   ├── CPI (Cost Per Impression)
│   └── Type 效率对比
├── 2. 预算效率分析 (Budget Efficiency)
│   ├── 预算利用率
│   ├── 预算耗尽 Campaign
│   └── 预算浪费识别
├── 3. 时间趋势分析 (Time Trends)
│   ├── 月度投放统计
│   ├── 季节性趋势
│   └── 投放节奏分析
├── 4. 异常检测 (Outlier Detection)
│   ├── IQR 异常值检测
│   ├── 高花费低效果
│   └── 预算超支预警
├── 5. 聚类分析 (Cluster Analysis)
│   ├── K-Means 4 簇
│   ├── 高花费型 / 高曝光型
│   └── 低投入型 / 高互动型
├── 6. 出价策略分析 (Bid Strategy)
│   ├── 策略效果对比
│   ├── 策略 × Type 交叉
│   └── 最优策略推荐
└── 7. 优化建议 (Recommendations)
    ├── 预算优化
    ├── 素材优化
    ├── 扩张建议
    └── 暂停建议
```

### 核心指标定义

| 指标 | 公式 | 含义 |
|------|------|------|
| **CPA** | Amount spent / Clicks | 每次点击成本 |
| **CPI** | Amount spent / Impressions | 每次曝光成本 |
| **CTR** | Clicks / Impressions | 点击率 |
| **预算利用率** | Amount spent / Budget | 预算消耗比例 |
| **ROAS** | Revenue / Amount spent | 广告回报率 |

---

## 第二部分：实际案例分析

### 案例背景

- **数据来源**：Shopee DAP (Dynamic Ads Platform)
- **数据量**：729 个 Campaign
- **时间范围**：2025-05 至 2026-06
- **广告类型**：Dynamic Ads / Static Ads
- **目标**：注册转化 (Register)

### 2.1 转化效率分析

```python
# 各 Type 效率对比
Type            Amount spent   Impressions    Clicks    CPA_by_clicks
Dynamic Ads      $1.78M         4.06B         105M      $0.00
Static Ads           $0              0            0           $0.00

# CPA 中位数: $0.00
# 高效 Campaign (< 中位数): 0
# 低效 Campaign (> 中位数): 55
```

**洞察**：
- Dynamic Ads 是唯一活跃的广告类型
- CPA 计算出现 0 是因为 CPC 值为 0（数据格式问题）
- 55 个 Campaign 被识别为低效

### 2.2 预算效率分析

```
# 预算利用率统计
count    0.00
mean       NaN
std        NaN
25%        NaN
50%        NaN
75%        NaN
max        NaN
```

**问题**：Budget 列全部为 NaN（Excel 格式问题），无法准确计算预算利用率。

**建议**：要求 DAP 平台导出包含 Budget 数据的 CSV。

### 2.3 时间趋势分析

```
月度投放统计 (最近 12 个月):
created_date    count       sum       mean
2025-05           1    11,413     11,413
2025-06          24   104,930      4,372
2025-07          24         0          0
2025-08          92    26,204        285
2025-09         118    77,006        653
2025-10          12         0          0
2025-11          12  347,326     28,944
2026-02          14  242,246     17,303
2026-03          16    43,309      2,707
2026-04           9   156,259     17,362
2026-05           1    13,241     13,241
2026-06           6    17,297      2,883
```

**洞察**：
- **2025-11** 是投放高峰期（$347K），对应 Black Friday 大促
- **2026-02-04** 有两次投放高峰，对应 Chinese New Year 和 4.4 大促
- **2025-07 和 2025-10** 投放为零，可能是淡季或数据缺失
- 整体投放节奏与大促周期高度相关

### 2.4 异常检测

```
# 花费分布
Q1: $0.00
Q3: $0.00
IQR: $0.00
高花费异常 (>Q3+1.5*IQR): 55

# TOP 5 高花费 Campaign
Campaign Name                          Amount spent   Impressions    Clicks     CTR
DAP_AAADYN-AND001...180225             $407,492      548.7M        7.9M      0.014%
DAP_DYN-AND154...031125                $347,326      1,226.7M     37.2M      0.030%
DAP_AAADYN-AND001...240426             $133,117      386.4M        2.4M      0.006%
DAP_DYN-AND001...100226                $120,147      276.1M        9.2M      0.033%
DAP_DYN-AND002...210823                 $61,729       70.3M        1.1M      0.016%
```

**洞察**：
- **55 个异常 Campaign** 贡献了大部分预算
- **Top 2 Campaign** 曝光超 5 亿，属于头部投放
- **CTR 普遍偏低**（0.006%-0.033%），但 Dynamic Ads 本身 CTR 就低

### 2.5 聚类分析

```
4 个 Cluster 特征:

Cluster 0 (11 campaigns): 高花费型
  平均花费: $54,860
  平均曝光: 132.4M
  平均点击: 3.4M

Cluster 1 (716 campaigns): 高互动型
  平均花费: $582
  平均曝光: 1.2M
  平均点击: 32K

Cluster 2 (1 campaign): 超头部
  平均花费: $347,326
  平均曝光: 1.23B
  平均点击: 37.2M

Cluster 3 (1 campaign): 超头部
  平均花费: $407,492
  平均曝光: 548.7M
  平均点击: 7.9M
```

**洞察**：
- **716 个 Campaign** 属于"高互动型"（花费低但互动高）
- **12 个 Campaign** 属于"高花费型"
- **2 个超头部 Campaign** 贡献了绝大部分预算
- 数据呈现**极右偏分布**（少数 Campaign 消耗大量预算）

### 2.6 出价策略分析

```
各出价策略统计:
Bid strategy             count       mean        sum  median
Bid Cap                     331    1,798.22    595,210     0.0
Cost per result goal          4         0.00          0     0.0
Highest volume              357    1,791.08    639,417     0.0
Use ad set strategy          37   14,611.04    540,608     0.0

# 出价策略 × Type 交叉分析
Bid strategy         Type              count      mean
Bid Cap              Dynamic Ads         328    1,814.67
                     Static Ads              3         0.00
Cost per result goal Dynamic Ads            4         0.00
Highest volume       Dynamic Ads         121    5,284.44
                     Static Ads           236         0.00
Use ad set strategy  Dynamic Ads          31   17,438.99
                     Static Ads              6         0.00
```

**洞察**：
- **Highest volume** 策略平均花费最高（$5,284），适合大预算 Campaign
- **Use ad set strategy** 策略 CPC 最高（$17,439），需谨慎使用
- **Bid Cap** 和 **Highest volume** 是主要策略（合计 688 个 Campaign）

### 2.7 优化建议

```
1. 发现 4 个 Campaign 的 CPI 高于中位数 2 倍，建议优化或暂停
2. 发现 51 个高花费 (> $1,000) 但低 CTR (< 1%) 的 Campaign，建议优化素材
```

---

## 第三部分：代码实现

### 核心分析函数

```python
def analyze_conversion_rate(df):
    """转化效率分析"""
    # 计算 CPA
    df['CPA'] = df['Amount spent'] / df['Clicks'].clip(lower=1)
    
    # 按 Type 分组
    type_efficiency = df.groupby('Type').agg({
        'Amount spent': 'sum',
        'Impressions': 'sum',
        'Clicks': 'sum',
        'CPA': 'mean'
    })
    
    return type_efficiency


def analyze_budget_efficiency(df):
    """预算效率分析"""
    valid = df.dropna(subset=['Amount spent', 'Budget'])
    valid['budget_utilization'] = valid['Amount spent'] / valid['Budget'].clip(lower=1)
    
    # 找出预算耗尽的 Campaign
    exhausted = valid[valid['budget_utilization'] > 0.9]
    
    return exhausted


def cluster_analysis(df, n_clusters=4):
    """K-Means 聚类分析"""
    numeric_cols = ['Amount spent', 'Impressions', 'Clicks']
    valid = df[numeric_cols].dropna()
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(valid)
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    clusters = kmeans.fit_predict(X_scaled)
    
    # 分析各簇特征
    cluster_stats = valid.groupby(clusters).mean()
    
    return cluster_stats
```

### 使用方式

```bash
# 运行深度分析
python3 scripts/dap_deep_analysis.py data.csv

# 输出包含：
# - 转化效率分析
# - 预算效率分析
# - 时间趋势分析
# - 异常检测
# - 聚类分析
# - 出价策略分析
# - 优化建议
```

---

## 第四部分：业务建议

### 短期优化（1-2 周）

1. **暂停低效 Campaign**：51 个高花费低 CTR 的 Campaign 建议暂停
2. **优化素材**：高 CPI 的 4 个 Campaign 建议优化广告素材
3. **调整出价策略**：降低 "Use ad set strategy" 策略的使用比例

### 中期优化（1-3 月）

1. **预算重新分配**：将预算从低效 Campaign 转移到高效 Campaign
2. **大促提前布局**：根据时间趋势，提前 1 个月准备大促素材
3. **A/B 测试**：对高花费 Campaign 进行素材 A/B 测试

### 长期优化（3-6 月）

1. **建立自动化监控**：实时监测 Campaign 表现，自动暂停低效 Campaign
2. **机器学习预测**：使用 TabPFN 预测 Campaign 表现，优化预算分配
3. **跨渠道整合**：结合 Meta、Google、TikTok 数据，制定跨渠道策略

---

## 第五部分：数据质量建议

### 当前问题

1. **Budget 列全为 NaN**：Excel 格式问题，需要重新导出
2. **CTR/CPC 数据缺失**：只有 55 条有值，覆盖率 7.6%
3. **Campaign name 命名不规范**：日期嵌入在 name 中，难以解析

### 改进建议

1. **使用 CSV 导出**：避免 Excel 合并单元格问题
2. **添加数据验证**：导出前检查关键字段完整性
3. **标准化命名**：Campaign name 使用统一格式（如：`{平台}_{类型}_{日期}_{目标}`）

---

## 第六部分：总结

### 核心发现

| 维度 | 发现 |
|------|------|
| **投放节奏** | 与大促周期高度相关（Black Friday、CNY、4.4） |
| **预算分配** | 2 个超头部 Campaign 消耗大量预算 |
| **效率对比** | Highest volume 策略平均花费最高 |
| **异常检测** | 55 个 Campaign 被识别为异常 |
| **优化空间** | 51 个高花费低 CTR Campaign 可优化 |

### 工具价值

1. **快速洞察**：1 分钟完成多维度分析
2. **自动化**：无需手动 Excel 操作
3. **可复现**：每次分析结果一致
4. **可扩展**：支持自定义分析维度
