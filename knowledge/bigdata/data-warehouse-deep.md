# 数据仓库深度：维度建模/数仓分层/ETL/数据质量

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解数据仓库

```
数据仓库 = 图书馆的图书管理系统

原始数据（OLTP）：
→ 每本书的借还记录
→ 杂乱无章
→ 难以分析

数据仓库（OLAP）：
→ 按时间/分类/作者组织
→ 便于分析
→ 维度建模
```

### 数据仓库核心概念

```
1. 维度建模：事实表 + 维度表
2. ETL：抽取/转换/加载
3. 分层：ODS/DWD/DWS/ADS
4. 数据质量：准确性/完整性/一致性
```

---

## 第二部分：维度建模深度

### 2.1 星型模型

```
星型模型 = 事实表在中心，维度表围绕

事实表（Fact Table）：
→ 存储度量值（销售额/点击量）
→ 外键指向维度表
→ 大量行

维度表（Dimension Table）：
→ 存储描述性信息（用户/商品/时间）
→ 较小
→ 缓慢变化
```

### 2.2 Go 实现维度建模

```go
package dimmodel

import (
    "time"
)

// FactTable 事实表
type FactTable struct {
    Date        time.Time
    UserID      string
    AdID        string
    Impressions int
    Clicks      int
    Conversions int
    Revenue     float64
}

// DimensionUser 用户维度表
type DimensionUser struct {
    UserID   string
    Age      int
    Gender   string
    Location string
    Segment  string
}

// DimensionAd 广告维度表
type DimensionAd struct {
    AdID       string
    CampaignID string
    AdType     string
    Platform   string
}

// DimensionDate 日期维度表
type DimensionDate struct {
    Date        time.Time
    Year        int
    Month       int
    Day         int
    Weekday     string
    IsHoliday   bool
}

// 查询：按日期和用户维度聚合
func QueryFact(facts []FactTable, dims map[string]DimensionUser, dates map[time.Time]DimensionDate) []Result {
    results := make([]Result, 0)
    
    for _, fact := range facts {
        user, ok := dims[fact.UserID]
        if !ok {
            continue
        }
        
        date, ok := dates[fact.Date]
        if !ok {
            continue
        }
        
        results = append(results, Result{
            Year:      date.Year,
            Month:     date.Month,
            Day:       date.Day,
            UserID:    fact.UserID,
            UserAge:   user.Age,
            UserGender: user.Gender,
            Impressions: fact.Impressions,
            Clicks:     fact.Clicks,
            Revenue:    fact.Revenue,
        })
    }
    
    return results
}
```

---

## 第三部分：数仓分层深度

### 3.1 分层架构

```
ODS（Operational Data Store）：
→ 原始数据
→ 不做任何处理
→ 每天增量/全量同步

DWD（Data Warehouse Detail）：
→ 数据清洗
→ 数据标准化
→ 数据脱敏

DWS（Data Warehouse Service）：
→ 轻度汇总
→ 宽表
→ 预计算

ADS（Application Data Store）：
→ 应用数据
→ 报表
→ 分析结果
```

### 3.2 Go 实现数据管道

```go
package pipeline

import (
    "context"
    "fmt"
)

// ODS Layer ODS 层
type ODSSource struct {
    rawData []RawRecord
}

type RawRecord struct {
    RawData []byte
    Source  string
    Time    time.Time
}

// DWD Layer DWD 层
type DWDProcessor struct{}

func (d *DWDProcessor) Process(raw RawRecord) (*CleanRecord, error) {
    // 1. 数据清洗
    cleaned, err := d.clean(raw.RawData)
    if err != nil {
        return nil, err
    }
    
    // 2. 数据标准化
    standard := d.standardize(cleaned)
    
    // 3. 数据脱敏
    return d.sanitize(standard), nil
}

func (d *DWDProcessor) clean(data []byte) ([]byte, error) {
    // 清洗逻辑
    return data, nil
}

func (d *DWDProcessor) standardize(data []byte) []byte {
    // 标准化逻辑
    return data
}

func (d *DWDProcessor) sanitize(record *CleanRecord) *CleanRecord {
    // 脱敏逻辑
    return record
}

// DWS Layer DWS 层
type DWSService struct {
    dwdRecords []*CleanRecord
}

func (d *DWSService) AggregateDaily() []DailySummary {
    summaries := make(map[string]*DailySummary)
    
    for _, record := range d.dwdRecords {
        key := record.Date.Format("2006-01-02")
        summary, ok := summaries[key]
        if !ok {
            summary = &DailySummary{Date: record.Date}
            summaries[key] = summary
        }
        
        summary.TotalImpressions += record.Impressions
        summary.TotalClicks += record.Clicks
        summary.TotalRevenue += record.Revenue
    }
    
    results := make([]DailySummary, 0, len(summaries))
    for _, s := range summaries {
        results = append(results, *s)
    }
    
    return results
}

// ADS Layer ADS 层
type ADSApplication struct {
    dailySummaries []DailySummary
}

func (a *ADSApplication) GetReport(date string) *Report {
    for _, s := range a.dailySummaries {
        if s.Date.Format("2006-01-02") == date {
            return &Report{
                Date:   s.Date,
                Summary: s,
            }
        }
    }
    return nil
}
```

---

## 第四部分：ETL 深度

### 4.1 ETL 流程

```
Extract（抽取）：
→ 从源系统读取数据
→ 全量/增量
→ CDC（Change Data Capture）

Transform（转换）：
→ 数据清洗
→ 数据转换
→ 数据聚合

Load（加载）：
→ 写入目标系统
→ 全量/增量/合并
```

### 4.2 Go 实现 ETL

```go
type ETLJob struct {
    name     string
    source   Source
    transform Transform
    target   Target
}

type Source interface {
    Read(ctx context.Context) ([]interface{}, error)
}

type Transform interface {
    Transform(data interface{}) (interface{}, error)
}

type Target interface {
    Write(ctx context.Context, data interface{}) error
}

func (job *ETLJob) Execute(ctx context.Context) error {
    // Extract
    rawData, err := job.source.Read(ctx)
    if err != nil {
        return fmt.Errorf("extract failed: %v", err)
    }
    
    // Transform
    transformedData := make([]interface{}, 0)
    for _, data := range rawData {
        transformed, err := job.transform.Transform(data)
        if err != nil {
            return fmt.Errorf("transform failed: %v", err)
        }
        transformedData = append(transformedData, transformed)
    }
    
    // Load
    for _, data := range transformedData {
        if err := job.target.Write(ctx, data); err != nil {
            return fmt.Errorf("load failed: %v", err)
        }
    }
    
    return nil
}
```

---

## 第五部分：数据质量

### 5.1 数据质量规则

```
1. 完整性：非空检查
2. 准确性：值域检查
3. 一致性：跨表一致性
4. 及时性：数据延迟检查
5. 唯一性：主键唯一性
```

### 5.2 Go 实现数据质量检查

```go
type DataQualityChecker struct {
    rules []QualityRule
}

type QualityRule struct {
    Name     string
    Type     string // completeness/accuracy/consistency/uniqueness
    Check    func(interface{}) bool
}

func (qc *DataQualityChecker) AddRule(name, ruleType string, check func(interface{}) bool) {
    qc.rules = append(qc.rules, QualityRule{
        Name:  name,
        Type:  ruleType,
        Check: check,
    })
}

func (qc *DataQualityChecker) Validate(data interface{}) ([]Violation, error) {
    violations := make([]Violation, 0)
    
    for _, rule := range qc.rules {
        if !rule.Check(data) {
            violations = append(violations, Violation{
                Rule: rule.Name,
                Type: rule.Type,
            })
        }
    }
    
    return violations, nil
}

// 使用示例
checker := &DataQualityChecker{}
checker.AddRule("not_null", "completeness", func(data interface{}) bool {
    return data != nil
})
checker.AddRule("age_range", "accuracy", func(data interface{}) bool {
    age := data.(int)
    return age >= 0 && age <= 120
})
checker.AddRule("unique_id", "uniqueness", func(data interface{}) bool {
    // 检查 ID 唯一性
    return true
})
```

---

## 第六部分：生产排障案例

### 6.1 ETL 延迟

```
现象：ETL 任务延迟严重

排查：
1. 检查源系统数据量
2. 检查转换逻辑
3. 检查目标系统写入速度

根因：数据量突增

解决方案：
1. 增加并行度
2. 优化转换逻辑
3. 批量写入
```

### 6.2 数据不一致

```
现象：报表数据不一致

排查：
1. 检查 ETL 日志
2. 检查数据质量规则
3. 检查源系统数据

根因：源系统数据变更

解决方案：
1. 添加数据质量监控
2. 定期校验
3. 增量同步
```

---

## 第七部分：自测题

### 问题 1
维度建模中事实表和维度表有什么区别？

<details>
<summary>查看答案</summary>

1. **事实表**：存储度量值
2. **维度表**：存储描述信息
3. **星型模型**：事实表在中心
4. **雪花模型**：维度表进一步拆分
5. **Go 实现**：FactTable/DimensionUser

</details>

### 问题 2
数仓分层的目的是什么？

<details>
<summary>查看答案</summary>

1. **ODS**：原始数据保留
2. **DWD**：数据清洗标准化
3. **DWS**：轻度汇总
4. **ADS**：面向应用
5. **Go 实现**：ETL Pipeline

</details>

### 问题 3
如何保证数据质量？

<details>
<summary>查看答案</summary>

1. **完整性**：非空检查
2. **准确性**：值域检查
3. **一致性**：跨表检查
4. **及时性**：延迟监控
5. **Go 实现**：DataQualityChecker

</details>

---

*本文档基于数据仓库原理整理。*