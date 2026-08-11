# MySQL 执行计划深度解析

> 深入MySQL执行计划：EXPLAIN分析、索引选择、优化策略。
> 包含真实生产环境慢查询优化案例。
> 适用对象：DBA、后端工程师

---

## 1. EXPLAIN 分析

### 1.1 输出字段

```
EXPLAIN 关键字段：

├── id: 查询标识符
├── select_type: 查询类型
│   ├── SIMPLE: 简单查询
│   ├── PRIMARY: 主查询
│   ├── SUBQUERY: 子查询
│   └── DERIVED: 派生表
│
├── table: 表名
├── partitions: 匹配分区
├── type: 访问类型
│   ├── system: 系统表
│   ├── const: 常量
│   ├── eq_ref: 唯一索引
│   ├── ref: 非唯一索引
│   ├── range: 索引范围
│   ├── index: 全索引扫描
│   └── ALL: 全表扫描
│
├── possible_keys: 可能使用的索引
├── key: 实际使用的索引
├── key_len: 使用的索引长度
├── ref: 索引比较的列
├── rows: 扫描行数
├── filtered: 过滤比例
└── Extra: 额外信息
    ├── Using filesort: 需要额外排序
    ├── Using temporary: 使用临时表
    ├── Using index: 覆盖索引
    └── Using where: 使用WHERE过滤
```

### 1.2 Go 实现 EXPLAIN 分析

```go
// explain_analyzer.go

package mysql

import (
    "database/sql"
    "fmt"
)

type ExplainResult struct {
    ID         int    `json:"id"`
    SelectType string `json:"select_type"`
    Table      string `json:"table"`
    Type       string `json:"type"`
    PossibleKeys []string `json:"possible_keys"`
    Key        string `json:"key"`
    KeyLen     int    `json:"key_len"`
    Ref        string `json:"ref"`
    Rows       int    `json:"rows"`
    Filtered   float64 `json:"filtered"`
    Extra      string `json:"extra"`
}

type ExplainAnalyzer struct {
    db *sql.DB
}

func NewExplainAnalyzer(db *sql.DB) *ExplainAnalyzer {
    return &ExplainAnalyzer{db: db}
}

func (ea *ExplainAnalyzer) Analyze(sql string) ([]ExplainResult, error) {
    rows, err := ea.db.Query("EXPLAIN " + sql)
    if err != nil {
        return nil, err
    }
    defer rows.Close()
    
    var results []ExplainResult
    for rows.Next() {
        var r ExplainResult
        err := rows.Scan(
            &r.ID,
            &r.SelectType,
            &r.Table,
            &r.Type,
            &r.PossibleKeys,
            &r.Key,
            &r.KeyLen,
            &r.Ref,
            &r.Rows,
            &r.Filtered,
            &r.Extra,
        )
        if err != nil {
            return nil, err
        }
        results = append(results, r)
    }
    return results, nil
}

func (ea *ExplainAnalyzer) AnalyzeSQL(sql string) (*AnalysisReport, error) {
    explains, err := ea.Analyze(sql)
    if err != nil {
        return nil, err
    }
    
    report := &AnalysisReport{
        ExplainResults: explains,
        Issues:         []string{},
        Suggestions:    []string{},
    }
    
    // 分析每个阶段
    for _, e := range explains {
        ea.analyzeStage(e, report)
    }
    
    return report, nil
}

func (ea *ExplainAnalyzer) analyzeStage(e ExplainResult, report *AnalysisReport) {
    // 检查全表扫描
    if e.Type == "ALL" {
        report.Issues = append(report.Issues, 
            fmt.Sprintf("表 %s 进行全表扫描，建议添加索引", e.Table))
    }
    
    // 检查文件排序
    if contains(e.Extra, "Using filesort") {
        report.Issues = append(report.Issues,
            "需要额外排序，考虑优化ORDER BY")
    }
    
    // 检查临时表
    if contains(e.Extra, "Using temporary") {
        report.Issues = append(report.Issues,
            "使用临时表，考虑优化查询")
    }
    
    // 检查索引使用
    if e.Key == "" && e.Type != "ALL" {
        report.Suggestions = append(report.Suggestions,
            "没有使用索引，建议添加合适索引")
    }
}
```

---

## 2. 索引选择

### 2.1 选择原则

```
索引选择原则：

1. 最左前缀原则
   └── 联合索引从左开始匹配

2. 索引覆盖原则
   └── 查询列都在索引中

3. 选择性原则
   └── 高选择性列优先

4. 范围查询原则
   └── 范围查询右侧索引失效
```

### 2.2 Go 实现索引选择

```go
// index_selector.go

package mysql

import "sort"

type IndexInfo struct {
    Name         string
    Columns      []string
    Cardinality  []int
    IsUnique     bool
}

type TableSchema struct {
    Name    string
    Indexes []IndexInfo
}

type IndexSelector struct {
    schemas map[string]*TableSchema
}

func NewIndexSelector() *IndexSelector {
    return &IndexSelector{
        schemas: make(map[string]*TableSchema),
    }
}

func (is *IndexSelector) SelectIndex(table string, columns []string) *IndexInfo {
    schema, ok := is.schemas[table]
    if !ok {
        return nil
    }
    
    var bestIndex *IndexInfo
    bestScore := 0
    
    for i := range schema.Indexes {
        idx := &schema.Indexes[i]
        score := is.calculateScore(idx, columns)
        if score > bestScore {
            bestScore = score
            bestIndex = idx
        }
    }
    
    return bestIndex
}

func (is *IndexSelector) calculateScore(idx *IndexInfo, columns []string) int {
    score := 0
    matched := 0
    
    for i, col := range idx.Columns {
        if i >= len(columns) {
            break
        }
        if col == columns[i] {
            matched++
            score += idx.Cardinality[i]
        } else {
            break
        }
    }
    
    // 覆盖索引额外加分
    if matched == len(columns) {
        score *= 2
    }
    
    return score
}
```

---

## 3. 优化策略

### 3.1 优化方法

```
查询优化方法：

├── 索引优化
│   ├── 添加缺失索引
│   ├── 删除冗余索引
│   └── 优化索引顺序
│
├── 查询优化
│   ├── 避免SELECT *
│   ├── 优化JOIN顺序
│   └── 拆分复杂查询
│
├── 表优化
│   ├── 分区表
│   ├── 垂直拆分
│   └── 水平拆分
│
└── 配置优化
    ├── 缓冲区大小
    ├── 连接数
    └── 查询缓存
```

### 3.2 Go 实现优化建议

```go
// query_optimizer.go

package mysql

type QueryOptimizer struct {
    db *sql.DB
}

func (qo *QueryOptimizer) Optimize(sql string) (*OptimizationReport, error) {
    // 1. 获取执行计划
    explain, err := qo.getExplain(sql)
    if err != nil {
        return nil, err
    }
    
    // 2. 分析性能问题
    issues := qo.analyzeIssues(explain)
    
    // 3. 生成优化建议
    suggestions := qo.generateSuggestions(explain, issues)
    
    return &OptimizationReport{
        OriginalSQL:   sql,
        ExplainPlan:   explain,
        Issues:        issues,
        Suggestions:   suggestions,
    }, nil
}

func (qo *QueryOptimizer) generateSuggestions(explain []ExplainResult, issues []string) []string {
    var suggestions []string
    
    for _, e := range explain {
        switch e.Type {
        case "ALL":
            suggestions = append(suggestions,
                fmt.Sprintf("表%s添加索引: ALTER TABLE %s ADD INDEX idx_xxx", e.Table, e.Table))
        case "Using filesort":
            suggestions = append(suggestions,
                "优化ORDER BY，确保使用索引排序")
        case "Using temporary":
            suggestions = append(suggestions,
                "减少GROUP BY或优化子查询")
        }
    }
    
    return suggestions
}
```

---

## 4. 总结

### 4.1 核心原理回顾

| 概念 | 说明 |
|------|------|
| EXPLAIN | 分析查询执行计划 |
| 索引选择 | 最左前缀、覆盖索引 |
| 优化策略 | 索引、查询、表、配置 |

### 4.2 最佳实践

- [ ] 始终使用EXPLAIN分析
- [ ] 避免全表扫描
- [ ] 合理使用索引
- [ ] 定期优化慢查询

---

*最后更新：2026-08-11*
*作者：Ryan*
