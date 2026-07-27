---

## 自测题

### 问题 1
Go 的 `sort.Slice` 和 C 的 `qsort` 有什么区别？

<details>
<summary>查看答案</summary>

1. Go 的 sort.Slice 是闭包排序，可以访问外部变量
2. C 的 qsort 需要回调函数，类型不安全
3. Go 的 sort 是 TimSort 变体，对部分有序数据优化
4. sort.Slice 是 Go 1.8 引入的，比 sort.Interface 更简洁

</details>

### 问题 2
为什么 agentmemory-analysis 要分析 memory 的使用模式？

<details>
<summary>查看答案</summary>

1. Agent 的 memory 增长是线性的，长期运行会 OOM
2. 分析使用模式可以找出 memory 泄漏点
3. 优化策略：滑动窗口、摘要压缩、定期清理
4. Go 的 GC 虽然自动，但频繁分配/释放仍会影响性能

</details>
## Go 源码级实现：Memory 使用模式分析

```go
package agentmemory

import (
	"fmt"
	"sort"
	"sync"
	"time"
)

// MemoryAnalyzer 记忆使用模式分析器
type MemoryAnalyzer struct {
	mu          sync.Mutex
	history     []AccessRecord
	stats       *MemoryStats
	expiryQueue *ExpiryQueue
}

// AccessRecord 访问记录
type AccessRecord struct {
	MemoryID   string
	SessionID  string
	AccessType string // read, write, delete, search
	Timestamp  time.Time
	LatencyMs  float64
}

// MemoryStats 内存使用统计
type MemoryStats struct {
	TotalEntries    int               `json:"total_entries"`
	TotalChars      int               `json:"total_chars"`
	ByType          map[string]int    `json:"by_type"`
	ByProject       map[string]int    `json:"by_project"`
	AvgEntryLength  float64           `json:"avg_entry_length"`
	OldestEntry     time.Time         `json:"oldest_entry"`
	NewestEntry     time.Time         `json:"newest_entry"`
	GrowthRate      float64           `json:"growth_rate_per_day"` // 每日新增条目数
	LastCleanup     time.Time         `json:"last_cleanup"`
}

// NewMemoryAnalyzer 创建分析器
func NewMemoryAnalyzer() *MemoryAnalyzer {
	return &MemoryAnalyzer{
		history:     make([]AccessRecord, 0),
		expiryQueue: NewExpiryQueue(),
	}
}

// RecordAccess 记录一次访问
func (ma *MemoryAnalyzer) RecordAccess(record AccessRecord) {
	ma.mu.Lock()
	defer ma.mu.Unlock()
	
	ma.history = append(ma.history, record)
	
	// 限制历史记录大小（保留最近 10000 条）
	if len(ma.history) > 10000 {
		ma.history = ma.history[len(ma.history)-5000:]
	}
}

// Analyze 分析记忆使用模式
func (ma *MemoryAnalyzer) Analyze(sessionID string) (*AnalysisReport, error) {
	ma.mu.Lock()
	defer ma.mu.Unlock()
	
	report := &AnalysisReport{
		SessionID:   sessionID,
		GeneratedAt: time.Now(),
	}
	
	// 1. 基础统计
	report.Stats = ma.calculateStats(sessionID)
	
	// 2. 增长趋势分析
	report.GrowthTrend = ma.analyzeGrowthTrend(sessionID)
	
	// 3. 访问模式分析
	report.AccessPattern = ma.analyzeAccessPattern(sessionID)
	
	// 4. 泄漏检测
	report.Leaks = ma.detectLeaks(sessionID)
	
	// 5. 优化建议
	report.Recommendations = ma.generateRecommendations(report)
	
	return report, nil
}

// calculateStats 计算基础统计
func (ma *MemoryAnalyzer) calculateStats(sessionID string) *MemoryStats {
	stats := &MemoryStats{
		ByType:  make(map[string]int),
		ByProject: make(map[string]int),
	}
	
	// 遍历历史记录计算
	var totalChars int
	var oldest, newest time.Time
	
	for _, rec := range ma.history {
		if rec.SessionID != sessionID {
			continue
		}
		
		totalChars += len(rec.AccessType) + len(rec.MemoryID)
		
		if rec.Timestamp.Before(oldest) || oldest.IsZero() {
			oldest = rec.Timestamp
		}
		if rec.Timestamp.After(newest) {
			newest = rec.Timestamp
		}
	}
	
	stats.TotalChars = totalChars
	stats.OldestEntry = oldest
	stats.NewestEntry = newest
	
	// 计算增长率
	if !oldest.IsZero() && !newest.IsZero() {
		days := newest.Sub(oldest).Hours() / 24
		if days > 0 {
			stats.GrowthRate = float64(len(ma.history)) / days
		}
	}
	
	return stats
}

// GrowthTrend 增长趋势
type GrowthTrend struct {
	DailyCounts []DailyCount
	Pattern     string // linear, exponential, stable
}

// DailyCount 每日计数
type DailyCount struct {
	Date  string
	Count int
}

// analyzeGrowthTrend 分析增长趋势
func (ma *MemoryAnalyzer) analyzeGrowthTrend(sessionID string) *GrowthTrend {
	trend := &GrowthTrend{}
	
	// 按天分组
	dayMap := make(map[string]int)
	for _, rec := range ma.history {
		if rec.SessionID != sessionID {
			continue
		}
		day := rec.Timestamp.Format("2006-01-02")
		dayMap[day]++
	}
	
	for day, count := range dayMap {
		trend.DailyCounts = append(trend.DailyCounts, DailyCount{day, count})
	}
	
	// 排序
	sort.Slice(trend.DailyCounts, func(i, j int) bool {
		return trend.DailyCounts[i].Date < trend.DailyCounts[j].Date
	})
	
	// 简单趋势判断
	if len(trend.DailyCounts) >= 3 {
		increasing := true
		for i := 1; i < len(trend.DailyCounts); i++ {
			if trend.DailyCounts[i].Count <= trend.DailyCounts[i-1].Count {
				increasing = false
				break
			}
		}
		if increasing {
			trend.Pattern = "exponential"
		} else {
			trend.Pattern = "stable"
		}
	}
	
	return trend
}

// AccessPattern 访问模式
type AccessPattern struct {
	ReadRatio     float64
	WriteRatio    float64
	DeleteRatio   float64
	PeakHour      int
	AvgLatencyMs  float64
}

// analyzeAccessPattern 分析访问模式
func (ma *MemoryAnalyzer) analyzeAccessPattern(sessionID string) *AccessPattern {
	pattern := &AccessPattern{}
	
	var reads, writes, deletes int
	var totalLatency float64
	hourCounts := make(map[int]int)
	
	for _, rec := range ma.history {
		if rec.SessionID != sessionID {
			continue
		}
		
		switch rec.AccessType {
		case "read":
			reads++
		case "write":
			writes++
		case "delete":
			deletes++
		}
		
		totalLatency += rec.LatencyMs
		hourCounts[rec.Timestamp.Hour()]++
	}
	
	total := reads + writes + deletes
	if total > 0 {
		pattern.ReadRatio = float64(reads) / float64(total)
		pattern.WriteRatio = float64(writes) / float64(total)
		pattern.DeleteRatio = float64(deletes) / float64(total)
	}
	
	// 找出高峰时段
	maxCount := 0
	for hour, count := range hourCounts {
		if count > maxCount {
			maxCount = count
			pattern.PeakHour = hour
		}
	}
	
	if total > 0 {
		pattern.AvgLatencyMs = totalLatency / float64(total)
	}
	
	return pattern
}

// LeakDetection 泄漏检测结果
type LeakDetection struct {
	HasLeak     bool
	Reason      string
	Severity    string // low, medium, high, critical
	Recommendation string
}

// detectLeaks 检测 memory 泄漏
func (ma *MemoryAnalyzer) detectLeaks(sessionID string) []*LeakDetection {
	var leaks []*LeakDetection
	
	// 检查 1：线性增长过快
	if len(ma.history) > 5000 {
		leaks = append(leaks, &LeakDetection{
			HasLeak:    true,
			Reason:     fmt.Sprintf("历史记录过多 (%d 条)，可能存在未清理的临时数据", len(ma.history)),
			Severity:   "high",
			Recommendation: "启用自动清理机制，限制最大记录数",
		})
	}
	
	// 检查 2：写入远大于读取（可能是缓存泄漏）
	pattern := ma.analyzeAccessPattern(sessionID)
	if pattern.WriteRatio > 0.8 && pattern.ReadRatio < 0.1 {
		leaks = append(leaks, &LeakDetection{
			HasLeak:    true,
			Reason:     "写入比例过高 (>80%)，读取比例过低 (<10%)，可能存在缓存泄漏",
			Severity:   "medium",
			Recommendation: "检查是否有只写不读的记忆条目",
		})
	}
	
	return leaks
}

// AnalysisReport 分析报告
type AnalysisReport struct {
	SessionID        string            `json:"session_id"`
	GeneratedAt      time.Time         `json:"generated_at"`
	Stats            *MemoryStats      `json:"stats"`
	GrowthTrend      *GrowthTrend      `json:"growth_trend"`
	AccessPattern    *AccessPattern    `json:"access_pattern"`
	Leaks            []*LeakDetection  `json:"leaks"`
	Recommendations  []string          `json:"recommendations"`
}

// generateRecommendations 生成优化建议
func (ma *MemoryAnalyzer) generateRecommendations(report *AnalysisReport) []string {
	var recommendations []string
	
	if report.Stats.GrowthRate > 100 {
		recommendations = append(recommendations, "记忆增长过快（>100条/天），建议启用自动清理")
	}
	
	if report.AccessPattern.WriteRatio > 0.7 {
		recommendations = append(recommendations, "写入比例过高，建议审查是否有无效写入")
	}
	
	for _, leak := range report.Leaks {
		if leak.HasLeak {
			recommendations = append(recommendations, fmt.Sprintf("[%s] %s: %s", 
				leak.Severity, leak.Reason, leak.Recommendation))
		}
	}
	
	if len(recommendations) == 0 {
		recommendations = append(recommendations, "当前记忆使用状态健康")
	}
	
	return recommendations
}

// ExpiryQueue 过期队列
type ExpiryQueue struct {
	items []*ExpiryItem
}

// ExpiryItem 过期项
type ExpiryItem struct {
	MemoryID string
	ExpiresAt time.Time
}

// NewExpiryQueue 创建过期队列
func NewExpiryQueue() *ExpiryQueue {
	return &ExpiryQueue{
		items: make([]*ExpiryItem, 0),
	}
}

// Add 添加过期项
func (eq *ExpiryQueue) Add(memoryID string, expiresAt time.Time) {
	eq.items = append(eq.items, &ExpiryItem{memoryID, expiresAt})
	sort.Slice(eq.items, func(i, j int) bool {
		return eq.items[i].ExpiresAt.Before(eq.items[j].ExpiresAt)
	})
}

// GetExpired 获取已过期的项
func (eq *ExpiryQueue) GetExpired() []*ExpiryItem {
	now := time.Now()
	var expired []*ExpiryItem
	var remaining []*ExpiryItem
	
	for _, item := range eq.items {
		if item.ExpiresAt.Before(now) {
			expired = append(expired, item)
		} else {
			remaining = append(remaining, item)
		}
	}
	
	eq.items = remaining
	return expired
}
```

### 性能优化：批量操作与并发控制

```go
package agentmemory

import (
	"context"
	"sync"
	"time"
)

// BatchProcessor 批量处理器
type BatchProcessor struct {
	mu       sync.Mutex
	batch    []*MemoryEntry
	batchSize int
	interval time.Duration
	handler  func(entries []*MemoryEntry) error
	done     chan struct{}
}

// NewBatchProcessor 创建批量处理器
func NewBatchProcessor(batchSize int, interval time.Duration, handler func([]*MemoryEntry) error) *BatchProcessor {
	bp := &BatchProcessor{
		batch:     make([]*MemoryEntry, 0, batchSize),
		batchSize: batchSize,
		interval:  interval,
		handler:   handler,
		done:      make(chan struct{}),
	}
	
	// 启动定时刷新
	go bp.flushLoop()
	
	return bp
}

// Add 添加条目到批处理队列
func (bp *BatchProcessor) Add(entry *MemoryEntry) error {
	bp.mu.Lock()
	defer bp.mu.Unlock()
	
	bp.batch = append(bp.batch, entry)
	
	// 达到批次大小立即刷新
	if len(bp.batch) >= bp.batchSize {
		return bp.flushLocked()
	}
	
	return nil
}

// flushLoop 定时刷新循环
func (bp *BatchProcessor) flushLoop() {
	ticker := time.NewTicker(bp.interval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			bp.mu.Lock()
			bp.flushLocked()
			bp.mu.Unlock()
		case <-bp.done:
			return
		}
	}
}

func (bp *BatchProcessor) flushLocked() error {
	if len(bp.batch) == 0 {
		return nil
	}
	
	err := bp.handler(bp.batch)
	bp.batch = bp.batch[:0] // 清空切片
	return err
}

// Shutdown 关闭处理器
func (bp *BatchProcessor) Shutdown() error {
	close(bp.done)
	bp.mu.Lock()
	defer bp.mu.Unlock()
	return bp.flushLocked()
}

// ConcurrentWriter 并发写入器（线程安全）
type ConcurrentWriter struct {
	mu      sync.RWMutex
	writers map[string]*MemoryStore
}

// GetWriter 获取或创建会话写入器
func (cw *ConcurrentWriter) GetWriter(sessionID string) (*MemoryStore, error) {
	cw.mu.RLock()
	writer, ok := cw.writers[sessionID]
	cw.mu.RUnlock()
	
	if ok {
		return writer, nil
	}
	
	cw.mu.Lock()
	defer cw.mu.Unlock()
	
	// 双重检查
	if writer, ok := cw.writers[sessionID]; ok {
		return writer, nil
	}
	
	// 创建新写入器
	store, err := NewMemoryStore(fmt.Sprintf("memory_%s.db", sessionID))
	if err != nil {
		return nil, err
	}
	
	cw.writers[sessionID] = store
	return store, nil
}
```
### 问题 3
会话内存清理中的 LRU 算法如何实现？

<details>
<summary>查看答案</summary>

1. **双向链表 + Hash Map**：map[sessionID]*ListNode + doubly linked list，实现 O(1) 查找和移动
2. **访问即置顶**：每次 Get/LRU 命中时将对应节点移到链表头部（最常用）
3. **尾部驱逐**：当容量超限时，删除链表尾部的 Least Recently Used 节点
4. **容量管理**：maxEntries 参数控制最大条数，溢出时自动触发 prune
5. **并发安全**：使用 sync.Mutex 保护链表结构，读写分离可用 sync.RWMutex
</details>
