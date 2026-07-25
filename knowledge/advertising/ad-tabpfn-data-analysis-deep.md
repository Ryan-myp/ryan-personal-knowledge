# TabPFN 数据分析实践深度：从安装到生产应用

> 基于 Hermes Skill 的 TabPFN 自动化数据分析工作流，零代码实现表格数据建模

---

## 第一部分：TabPFN 是什么？

### 核心概念

TabPFN（Tabular Prior Flow Network）是一个基于 Transformer 的深度学习模型，专为表格数据设计。它在中小规模数据集上表现远超传统 ML 方法。

```
传统 ML 流程：
数据 → 特征工程 → 选择模型(XGBoost/LightGBM) → 网格搜索调参 → 训练 → 评估

TabPFN 流程：
数据 → 自动建模 → 训练 → 评估
（几乎零调参！）
```

### 核心优势

| 特性 | 传统 ML (XGBoost) | TabPFN |
|------|------------------|--------|
| **调参** | 需要大量网格搜索 | 几乎零调参 |
| **小数据表现** | 一般 | 优秀（< 1000 行） |
| **训练速度** | 快 | 中等 |
| **推理速度** | 极快 | 快 |
| **特征工程** | 需要手动处理 | 自动处理分类/数值 |
| **适用场景** | 大规模数据 | 中小规模数据 |

### 适用场景

1. **快速原型**：上传 CSV，一键生成预测模型
2. **特征分析**：自动计算特征重要性
3. **业务预测**：销售额预测、客户流失预测、广告 ROI 预测
4. **异常检测**：自动识别离群点

---

## 第二部分：Hermes Skill 架构

### 整体设计

```
用户输入 CSV 文件
    ↓
Hermes 加载 Skill (tabpfn-data-analysis)
    ↓
脚本自动执行：
1. 检查/创建 Python 3.12 虚拟环境
2. 安装依赖 (pandas, numpy<2, scikit-learn, tabpfn)
3. 加载并分析数据
4. 自动选择目标变量
5. 训练 TabPFN 模型
6. 输出分析报告
    ↓
返回结构化 JSON 结果
```

### 文件结构

```
~/.hermes/skills/tabpfn-data-analysis/
├── SKILL.md                          # Skill 说明文档
├── scripts/
│   └── tabpfn_analyzer.py           # 核心脚本（~300 行）
└── assets/
    └── sample_ad_data.csv           # 示例数据
```

### 关键设计决策

| 决策 | 原因 |
|------|------|
| **Python 3.12 虚拟环境** | tabpfn 依赖 torch，torch 不支持 Python 3.13 |
| **numpy<2** | torch 2.2.2 需要 numpy<2 |
| **主进程安装 pandas** | 数据加载在主进程（Python 3.13），venv 是 3.12 |
| **自动 fallback** | TabPFN 失败时自动使用 sklearn |

---

## 第三部分：脚本源码解析

### 1. 虚拟环境管理

```python
VENV_PYTHON = "/usr/local/bin/python3.12"  # tabpfn 需要 Python 3.10-3.12
VENV_DIR = Path.home() / ".hermes" / "skills" / "tabpfn-data-analysis" / ".venv"

def setup_venv():
    """创建或使用虚拟环境（使用 Python 3.12）"""
    if not VENV_DIR.exists() or not (VENV_DIR / "bin" / "python").exists():
        print("🔧 创建虚拟环境 (Python 3.12)...")
        subprocess.run([VENV_PYTHON, "-m", "venv", str(VENV_DIR)], check=True)
        print("✅ 虚拟环境创建成功")
    return VENV_DIR / "bin" / "python"
```

**关键点**：
- 使用 `brew install python@3.12` 安装 Python 3.12
- 虚拟环境隔离，不污染系统 Python
- 首次创建约 10 秒，后续直接使用

### 2. 依赖安装

```python
def install_dependencies(venv_python):
    """安装依赖"""
    packages = ["pandas", "numpy<2", "scikit-learn"]
    
    for pkg in packages:
        print(f"📦 安装 {pkg}...")
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", pkg, "--quiet"],
            check=True,
        )
    print("✅ 基础依赖安装完成")
```

**关键点**：
- `numpy<2` 是关键约束，torch 不支持 numpy 2.x
- `--quiet` 减少输出噪音
- 约 30-60 秒完成

### 3. TabPFN 安装

```python
def ensure_tabpfn(venv_python):
    """确保 tabpfn 已安装"""
    try:
        result = subprocess.run(
            [str(venv_python), "-c", "import tabpfn"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            print("✅ TabPFN 已安装")
            return True
    except Exception:
        pass
    
    print("⚠️  TabPFN 未安装，尝试安装...")
    try:
        result = subprocess.run(
            [str(venv_python), "-m", "pip", "install", "tabpfn", "--quiet"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            print("✅ TabPFN 安装成功")
            return True
        else:
            print(f"⚠️  TabPFN 安装失败（依赖冲突），将使用基础分析功能")
            return False
    except Exception as e:
        print(f"⚠️  TabPFN 安装出错: {e}")
        return False
```

**关键点**：
- 先检查是否已安装，避免重复安装
- 安装失败时 graceful fallback
- 约 2-3 分钟（下载 torch 较大）

### 4. 数据分析

```python
def analyze_data(df, target_col=None):
    """分析数据并输出概览"""
    import pandas as pd
    import numpy as np

    print("\n" + "=" * 60)
    print("📋 数据集概览")
    print("=" * 60)

    # 基本统计
    print(f"行数: {len(df)}")
    print(f"列数: {len(df.columns)}")
    print(f"\n数据类型分布:")
    print(df.dtypes.value_counts().to_string())

    # 缺失值
    print(f"\n缺失值统计:")
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(1)
    missing_df = pd.DataFrame({"缺失数": missing, "缺失比例%": missing_pct})
    missing_df = missing_df[missing_df["缺失数"] > 0]
    if len(missing_df) > 0:
        print(missing_df.to_string())
    else:
        print("  无缺失值 ✅")

    # 数值列统计
    numeric_cols = df.select_dtypes(include=["number"]).columns
    if len(numeric_cols) > 0:
        print(f"\n数值列统计 ({len(numeric_cols)} 列):")
        print(df[numeric_cols].describe().round(2).to_string())

    # 分类列统计
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns
    if len(categorical_cols) > 0:
        print(f"\n分类列统计 ({len(categorical_cols)} 列):")
        for col in categorical_cols[:5]:
            print(f"  {col}: {df[col].nunique()} 个唯一值")

    # 确定目标列
    if target_col is None:
        if len(numeric_cols) > 0:
            target_col = numeric_cols[-1]
        elif len(categorical_cols) > 0:
            target_col = categorical_cols[-1]
        else:
            target_col = df.columns[-1]

    target_series = df[target_col]
    is_classification = target_series.dtype == "object" or target_series.nunique() < 10
    task_type = "分类" if is_classification else "回归"

    print(f"\n🎯 目标变量: {target_col}")
    print(f"📊 任务类型: {task_type}")

    return df, target_col, task_type
```

**关键点**：
- 自动选择目标变量（优先最后一列）
- 自动判断分类/回归任务
- 详细的统计概览

### 5. 模型训练

```python
def train_with_tabpfn(df, target_col, task_type, venv_python):
    """使用 TabPFN 训练模型"""
    import numpy as np
    from sklearn.preprocessing import LabelEncoder

    # 准备数据
    X = df.drop(columns=[target_col])
    y = df[target_col]

    # 编码分类变量
    label_encoders = {}
    for col in X.select_dtypes(include=["object", "category"]).columns:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
        label_encoders[col] = le

    # 填充缺失值
    X = X.fillna(X.median())
    X_np = X.values.astype(np.float32)
    y_np = y.values

    if task_type == "分类":
        y_le = LabelEncoder()
        y_np = y_le.fit_transform(y_np)

    print(f"特征矩阵形状: {X_np.shape}")

    # 通过子进程调用 TabPFN
    script = f'''
import numpy as np
from sklearn.preprocessing import LabelEncoder
from tabpfn import TabPFNClassifier, TabPFNRegressor

X_np = np.array({X_np.tolist()}, dtype=np.float32)
y_np = np.array({y_np.tolist()})

if "{task_type}" == "分类":
    model = TabPFNClassifier()
else:
    model = TabPFNRegressor()

model.fit(X_np, y_np)
predictions = model.predict(X_np)

print(f"{{predictions.tolist()}}")
'''

    try:
        result = subprocess.run(
            [str(venv_python), "-c", script],
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        if result.returncode == 0:
            predictions = eval(result.stdout.strip())
            print(f"✅ 模型训练完成")
            return predictions
        else:
            print(f"❌ TabPFN 训练失败: {result.stderr}")
            return None
    except Exception as e:
        print(f"❌ 训练出错: {e}")
        return None
```

**关键点**：
- 分类变量自动编码
- 缺失值自动填充（中位数）
- 子进程调用，避免主进程依赖冲突
- 300 秒超时保护

---

## 第四部分：使用示例

### 示例 1：广告表现分析

```bash
# 数据文件：ad_performance.csv
campaign_id,ad_spend,impressions,clicks,conversions,cpa,roas,status
camp_001,1000,50000,1500,150,6.67,3.2,active
camp_002,2000,80000,2000,180,11.11,2.8,active
camp_003,500,20000,800,40,12.50,1.9,inactive
# ... 更多数据

# 运行分析
python3 scripts/tabpfn_analyzer.py ad_performance.csv --json-output /tmp/result.json
```

**输出**：
```
📊 加载数据: 10 行 × 8 列

📋 数据集概览
行数: 10
列数: 8

🎯 目标变量: roas
📊 任务类型: 回归

🚀 开始训练模型...
✅ 模型训练完成

📊 分析完成!
{
  "task_type": "回归",
  "target_col": "roas",
  "num_rows": 10,
  "num_columns": 8,
  "predictions_count": 10
}
```

### 示例 2：客户流失预测

```bash
# 数据文件：customers.csv
customer_id,age,income,tenure,monthly_charges,total_charges,churn
1,35,50000,24,65.0,1560.0,no
2,45,80000,12,90.0,1080.0,yes
3,28,40000,36,55.0,1980.0,no
# ... 更多数据

# 指定目标列
python3 scripts/tabpfn_analyzer.py customers.csv --target churn --json-output /tmp/churn_result.json
```

**输出**：
```
📋 数据集概览
行数: 1000
列数: 7

🎯 目标变量: churn
📊 任务类型: 分类

🚀 开始训练模型...
✅ 模型训练完成

📊 分析完成!
{
  "task_type": "分类",
  "target_col": "churn",
  "num_rows": 1000,
  "num_columns": 7,
  "predictions_count": 1000
}
```

### 示例 3：Hermes 聊天调用

```
你：帮我分析 ~/data/ad_performance.csv 的数据

Hermes：
✅ 已加载 Skill: tabpfn-data-analysis
📊 加载数据: 10 行 × 8 列
🎯 目标变量: roas
📊 任务类型: 回归
✅ 模型训练完成

分析结果：
- 最佳特征：impressions（与 ROAS 相关性最高）
- 模型类型：TabPFNRegressor
- 训练样本：10 条
```

---

## 第五部分：生产部署建议

### 1. 缓存虚拟环境

```bash
# 首次安装后，虚拟环境在：
~/.hermes/skills/tabpfn-data-analysis/.venv/

# 后续使用直接使用，无需重新安装
# 约 2-3 分钟 → 秒级
```

### 2. 批量处理

```bash
#!/bin/bash
# batch_analyze.sh

for file in ~/data/*.csv; do
    filename=$(basename "$file" .csv)
    echo "处理: $filename"
    python3 scripts/tabpfn_analyzer.py "$file" \
        --json-output "/tmp/${filename}_result.json"
done
```

### 3. 定时任务（Cron Job）

```bash
# 每天凌晨 2 点分析广告数据
hermes cron create "0 2 * * *" \
    --prompt "用 tabpfn 分析 ~/data/daily_ad_performance.csv，输出报告到 ~/reports/" \
    --skills tabpfn-data-analysis
```

### 4. 性能优化

| 优化项 | 建议 |
|--------|------|
| **数据量** | < 50,000 行 × 100 列 |
| **内存** | 至少 8GB |
| **CPU** | 多核 CPU 更快 |
| **GPU** | 有 NVIDIA GPU 可加速（自动检测） |
| **缓存** | 虚拟环境复用，避免重复安装 |

---

## 第六部分：常见问题

### Q1: TabPFN 安装失败怎么办？

**A**: 确保使用 Python 3.12 的虚拟环境：
```bash
# 检查 Python 版本
~/.hermes/skills/tabpfn-data-analysis/.venv/bin/python --version
# 应该是 Python 3.12.x

# 如果不对，删除重建
rm -rf ~/.hermes/skills/tabpfn-data-analysis/.venv
python3 scripts/tabpfn_analyzer.py your_data.csv
```

### Q2: 内存不足怎么办？

**A**: 减少数据量或增加内存：
```python
# 采样数据
df = df.sample(n=1000, random_state=42)
```

### Q3: 预测新数据？

**A**: 使用 `--predict` 参数：
```bash
python3 scripts/tabpfn_analyzer.py train_data.csv \
    --predict new_data.csv \
    --json-output /tmp/predict_result.json
```

### Q4: 没有 GPU 能跑吗？

**A**: 可以！TabPFN 会自动使用 CPU。GPU 仅加速训练，不影响功能。

### Q5: 如何集成到自己的项目？

**A**: 直接复制 `tabpfn_analyzer.py` 到你的项目，修改 `VENV_PYTHON` 路径即可。

---

## 第七部分：总结

### 核心优势

| 特性 | 价值 |
|------|------|
| **零代码** | 上传 CSV，一键建模 |
| **自动调参** | 无需网格搜索 |
| **自动分析** | 统计、缺失值、分布一键生成 |
| **自动建模** | 分类/回归自动选择 |
| **Hermes 集成** | 聊天中直接调用 |

### 适用场景

1. **快速探索**：新数据快速了解
2. **原型开发**：快速验证想法
3. **日常分析**：定期分析业务数据
4. **教学演示**：展示 ML 能力

### 局限性

1. **大数据**：> 50,000 行建议用 XGBoost
2. **实时推理**：TabPFN 推理较慢，不适合高并发
3. **依赖体积**：torch + tabpfn 约 2GB

---

## Go 代码实战：广告数据分析流水线

### 1. 广告指标分析引擎

```go
package analytics

import (
	"context"
	"math"
	"sync"
	"time"
)

// AdMetric 广告指标
type AdMetric struct {
	Date        time.Time `json:"date"`
	CampaignID  string    `json:"campaign_id"`
	Impressions int64     `json:"impressions"`
	Clicks      int64     `json:"clicks"`
	Conversions int64     `json:"conversions"`
	Spend       float64   `json:"spend"`
	Revenue     float64   `json:"revenue"`
}

// CampaignStats 广告系列统计
type CampaignStats struct {
	CampaignID   string
	DailyMetrics []AdMetric
	CTR          float64
	CVR          float64
	CPC          float64
	CPM          float64
	ROAS         float64
	Trend        TrendAnalysis
}

// TrendAnalysis 趋势分析
type TrendAnalysis struct {
	Direction   string // up, down, stable
	Magnitude   float64 // 变化幅度
	Confidence  float64 // 置信度
	AnomalyDays []time.Time
}

// Analyzer 分析器
type Analyzer struct {
	window time.Duration // 分析窗口
}

func NewAnalyzer(window time.Duration) *Analyzer {
	return &Analyzer{window: window}
}

// AnalyzeCampaign 分析广告系列
func (a *Analyzer) AnalyzeCampaign(ctx context.Context, metrics []AdMetric) (*CampaignStats, error) {
	if len(metrics) == 0 {
		return nil, nil
	}
	
	stats := &CampaignStats{
		CampaignID: metrics[0].CampaignID,
		DailyMetrics: metrics,
	}
	
	// 计算聚合指标
	var totalImp, totalClick, totalConv int64
	var totalSpend, totalRevenue float64
	
	for _, m := range metrics {
		totalImp += m.Impressions
		totalClick += m.Clicks
		totalConv += m.Conversions
		totalSpend += m.Spend
		totalRevenue += m.Revenue
	}
	
	stats.CTR = float64(totalClick) / max(float64(totalImp), 1)
	stats.CVR = float64(totalConv) / max(float64(totalClick), 1)
	stats.CPC = totalSpend / max(float64(totalClick), 1)
	stats.CPM = totalSpend / max(float64(totalImp)/1000, 1)
	stats.ROAS = totalRevenue / max(totalSpend, 0.01)
	
	// 趋势分析
	stats.Trend = a.analyzeTrend(metrics)
	
	return stats, nil
}

// analyzeTrend 趋势分析（线性回归）
func (a *Analyzer) analyzeTrend(metrics []AdMetric) TrendAnalysis {
	if len(metrics) < 3 {
		return TrendAnalysis{Direction: "stable", Confidence: 0}
	}
	
	// 提取 spend 序列
	values := make([]float64, len(metrics))
	for i, m := range metrics {
		values[i] = m.Spend
	}
	
	// 简单线性回归
	n := float64(len(values))
	sumX := 0.0
	sumY := 0.0
	sumXY := 0.0
	sumXX := 0.0
	
	for i, v := range values {
		x := float64(i)
		sumX += x
		sumY += v
		sumXY += x * v
		sumXX += x * x
	}
	
	slope := (n*sumXY - sumX*sumY) / max(n*sumXX - sumX*sumX, 0.001)
	meanY := sumY / n
	
	// 判断趋势
	direction := "stable"
	magnitude := math.Abs(slope / max(meanY, 0.01))
	
	if magnitude > 0.1 && slope > 0 {
		direction = "up"
	} else if magnitude > 0.1 && slope < 0 {
		direction = "down"
	}
	
	confidence := math.Min(magnitude, 1.0)
	
	// 异常检测（Z-Score）
	anomalyDays := a.detectAnomalies(metrics)
	
	return TrendAnalysis{
		Direction:  direction,
		Magnitude:  magnitude,
		Confidence: confidence,
		AnomalyDays: anomalyDays,
	}
}

// detectAnomalies 异常检测（Z-Score > 2）
func (a *Analyzer) detectAnomalies(metrics []AdMetric) []time.Time {
	if len(metrics) < 5 {
		return nil
	}
	
	// 计算均值和标准差
	var sum float64
	for _, m := range metrics {
		sum += m.Spend
	}
	mean := sum / float64(len(metrics))
	
	var sqSum float64
	for _, m := range metrics {
		sqSum += (m.Spend - mean) * (m.Spend - mean)
	}
	stddev := math.Sqrt(sqSum / float64(len(metrics)))
	
	var anomalies []time.Time
	for _, m := range metrics {
		zScore := math.Abs((m.Spend - mean) / max(stddev, 0.001))
		if zScore > 2.0 {
			anomalies = append(anomalies, m.Date)
		}
	}
	
	return anomalies
}

// MultiCampaignAnalyzer 多广告系列并行分析
type MultiCampaignAnalyzer struct {
	analyzer *Analyzer
	concurrency int
}

func (ma *MultiCampaignAnalyzer) AnalyzeAll(
	ctx context.Context, 
	campaigns map[string][]AdMetric,
) []*CampaignStats {
	results := make([]*CampaignStats, 0, len(campaigns))
	
	type result struct {
		stats *CampaignStats
		id    string
	}
	
	resultCh := make(chan result, len(campaigns))
	var wg sync.WaitGroup
	
	sem := make(chan struct{}, ma.concurrency)
	
	for id, metrics := range campaigns {
		wg.Add(1)
		sem <- struct{}{}
		
		go func(campID string, campMetrics []AdMetric) {
			defer wg.Done()
			defer func() { <-sem }()
			
			stats, err := ma.analyzer.AnalyzeCampaign(ctx, campMetrics)
			if err != nil {
				return
			}
			resultCh <- result{stats, campID}
		}(id, metrics)
	}
	
	go func() {
		wg.Wait()
		close(resultCh)
	}()
	
	for r := range resultCh {
		results = append(results, r.stats)
	}
	
	return results
}
```

### 2. A/B 测试统计检验

```go
package analytics

import "math"

// ABTest A/B 测试结果
type ABTest struct {
	VariantA VariantResult
	VariantB VariantResult
	PValue   float64
	Significant bool
	Lift    float64
}

type VariantResult struct {
	Name      string
	Impressions int64
	Clicks    int64
	Conversions int64
	Spend     float64
}

// RunABTest 执行 A/B 测试分析
func RunABTest(a, b VariantResult) *ABTest {
	ctrA := float64(a.Clicks) / max(float64(a.Impressions), 1)
	ctrB := float64(b.Clicks) / max(float64(b.Impressions), 1)
	
	// Z-test for proportion difference
	pooled := float64(a.Clicks+b.Clicks) / max(float64(a.Impressions+b.Impressions), 1)
	standardError := math.Sqrt(pooled * (1 - pooled) * (1/float64(a.Impressions) + 1/float64(b.Impressions)))
	
	zScore := (ctrB - ctrA) / max(standardError, 0.0001)
	pValue := 2 * (1 - normalCDF(math.Abs(zScore)))
	
	lift := (ctrB - ctrA) / max(ctrA, 0.0001)
	
	return &ABTest{
		VariantA:    a,
		VariantB:    b,
		PValue:      pValue,
		Significant: pValue < 0.05,
		Lift:        lift,
	}
}

// normalCDF 正态分布累积函数（近似）
func normalCDF(x float64) float64 {
	// Abramowitz and Stegun approximation
	a1, a2, a3, a4, a5 := 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
	p := 0.3275911
	
	sign := 1.0
	if x < 0 {
		sign = -1
	}
	
	x = math.Abs(x)
	t := 1.0 / (1.0 + p*x)
	y := 1.0 - (((((a5*t+a4)*t)+a3)*t+a2)*t+a1)*t*math.Exp(-x*x/2)
	
	return 0.5 * (1.0 + sign*y)
}
```

### 自测题

<details>
<summary>Q1: analyzeTrend 的线性回归在广告数据中有什么局限性？什么场景会误判？</summary>

**答案**：

**局限性**：
| 场景 | 问题 | 解决方案 |
|------|------|---------|
| 周期性数据 | 周末CTR天然低 → 回归线向下 | 用季节性分解(STL) |
| 突变点 | 新素材上线 → CTR跳升 | 用CUSUM或Page-Hinkley检测 |
| 噪声大 | 每日波动 ±30% | 用移动平均平滑 |
| 非线性 | S型增长曲线 | 用多项式回归或分片线性 |

**生产实践**：先用 STL 分解趋势+季节+残差，再对趋势分量做回归。

</details>

<details>
<summary>Q2: Z-test 假设两个样本独立且服从正态分布，广告点击率真的满足吗？</summary>

**答案**：

**不满足！点击率是二项分布，不是正态分布。**

但当 n*p > 5 且 n*(1-p) > 5 时，二项分布近似正态——这就是为什么 Z-test 在实践中可用。

**更精确的方案**：
```go
// 方案1: Fisher精确检验（小样本）
// 方案2: Beta-Bernoulli贝叶斯（推荐）
// 方案3: Bootstrap重采样（非参数）

// 贝叶斯方法优势：直接给出 P(B>A) 的概率，而非 p-value
// 业务方更容易理解："Variant B 有 97% 概率优于 A"
```

</details>

<details>
<summary>Q3: MultiCampaignAnalyzer 的并发控制为什么用 sem channel 而不是无限制 goroutine？</summary>

**答案**：

**无限制 goroutine 的问题**：
- 1000 个 campaign × 每个 1 个 goroutine = 1000 个 goroutine
- 每个 goroutine 约 2KB stack → 2MB 内存
- 但更重要的是：CPU 上下文切换开销

**sem channel 控制**：
```go
sem := make(chan struct{}, concurrency) // 限制并发数
```

**选择 concurrency 值**：
| CPU 核心数 | 推荐并发数 | 理由 |
|-----------|-----------|------|
| 4 | 8-16 | IO 密集型可超分 |
| 8 | 16-32 | CPU 密集型取 1:2 |
| 16+ | 32-64 | 注意内存带宽瓶颈 |

广告分析通常是 CPU 密集型（数学计算），建议 1:1 到 1:2 的比例。

</details>
