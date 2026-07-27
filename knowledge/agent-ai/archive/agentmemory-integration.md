---

## 自测题

### 问题 1
Go 的 `map` 遍历顺序为什么不确定？

<details>
<summary>查看答案</summary>

1. Go 设计有意打乱 map 遍历顺序，防止依赖遍历顺序的代码
2. 内部实现中，key 的哈希值决定了桶的位置
3. 如果需要有序遍历，应该用 slice + sort
4. 这在测试中会导致不确定的行为，所以不能依赖

</details>

### 问题 2
agentmemory-integration 中为什么推荐用 SQLite 而不是 Redis？

<details>
<summary>查看答案</summary>

1. SQLite 是嵌入式数据库，零运维，适合 Agent 本地部署
2. Redis 需要单独部署和维护，对小型项目过重
3. SQLite 支持复杂的查询（FTS5、JOIN），适合知识图谱
4. Go 的 `database/sql` 标准库对 SQLite 有优秀的支持

</details>
## Go 源码级实现：Agent Memory 集成

```go
package agentmemory

import (
	"context"
	"database/sql"
	"fmt"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// MemoryEntry 记忆条目
type MemoryEntry struct {
	ID        int64     `json:"id"`
	SessionID string    `json:"session_id"`
	Type      string    `json:"type"` // fact, preference, pattern, architecture
	Content   string    `json:"content"`
	Files     string    `json:"files,omitempty"`
	Project   string    `json:"project,omitempty"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
	TTL       time.Duration `json:"ttl,omitempty"`
}

// MemoryStore Agent 持久化记忆存储
type MemoryStore struct {
	db   *sql.DB
	mu   sync.RWMutex
	cache map[string]*MemoryEntry // sessionID -> entry
	ttl  time.Duration
}

// NewMemoryStore 创建记忆存储
func NewMemoryStore(dbPath string) (*MemoryStore, error) {
	db, err := sql.Open("sqlite3", dbPath+"?_journal=WAL&_busy_timeout=5000")
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}
	
	// WAL 模式提升并发读写性能
	db.SetMaxOpenConns(1) // SQLite 单写者模型
	db.SetMaxIdleConns(1)
	
	store := &MemoryStore{
		db:    db,
		cache: make(map[string]*MemoryEntry),
		ttl:   24 * time.Hour,
	}
	
	// 初始化表结构
	if err := store.initSchema(); err != nil {
		return nil, err
	}
	
	// 启动后台清理
	go store.cleanupLoop()
	
	return store, nil
}

// initSchema 初始化数据库 schema
func (ms *MemoryStore) initSchema() error {
	schema := `
	CREATE TABLE IF NOT EXISTS memories (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		session_id TEXT NOT NULL,
		type TEXT NOT NULL CHECK(type IN ('fact', 'preference', 'pattern', 'architecture', 'bug', 'workflow', 'user')),
		content TEXT NOT NULL,
		files TEXT DEFAULT '',
		project TEXT DEFAULT '',
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		ttl_seconds INTEGER DEFAULT 86400,
		UNIQUE(session_id, type, content)
	);
	CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
	CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project);
	CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at);
	`
	_, err := ms.db.Exec(schema)
	return err
}

// Save 保存记忆（带去重）
func (ms *MemoryStore) Save(entry *MemoryEntry) error {
	ms.mu.Lock()
	defer ms.mu.Unlock()
	
	// 检查是否已存在相同类型的记忆
	existing, err := ms.findByType(entry.SessionID, entry.Type)
	if err == nil && existing != nil {
		// 更新而非插入
		query := `UPDATE memories SET content=?, files=?, project=?, updated_at=CURRENT_TIMESTAMP, ttl_seconds=? 
		          WHERE id=?`
		_, err = ms.db.Exec(query, entry.Content, entry.Files, entry.Project, int(entry.TTL.Seconds()), existing.ID)
		return err
	}
	
	// 插入新记忆
	query := `INSERT INTO memories (session_id, type, content, files, project, ttl_seconds) 
	          VALUES (?, ?, ?, ?, ?, ?)`
	result, err := ms.db.Exec(query, entry.SessionID, entry.Type, entry.Content, 
		entry.Files, entry.Project, int(entry.TTL.Seconds()))
	if err != nil {
		return err
	}
	
	id, _ := result.LastInsertId()
	entry.ID = id
	entry.CreatedAt = time.Now()
	entry.UpdatedAt = time.Now()
	
	// 更新缓存
	ms.cache[entry.SessionID] = entry
	
	return nil
}

// FindByType 按类型查询记忆
func (ms *MemoryStore) FindByType(sessionID, memType string) ([]*MemoryEntry, error) {
	query := `SELECT id, session_id, type, content, files, project, created_at, updated_at, ttl_seconds 
	          FROM memories WHERE session_id=? AND type=? ORDER BY updated_at DESC`
	
	rows, err := ms.db.Query(query, sessionID, memType)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	var entries []*MemoryEntry
	for rows.Next() {
		var e MemoryEntry
		var ttlSeconds int
		err := rows.Scan(&e.ID, &e.SessionID, &e.Type, &e.Content, 
			&e.Files, &e.Project, &e.CreatedAt, &e.UpdatedAt, &ttlSeconds)
		if err != nil {
			continue
		}
		e.TTL = time.Duration(ttlSeconds) * time.Second
		entries = append(entries, &e)
	}
	
	return entries, rows.Err()
}

// FindAll 获取所有记忆
func (ms *MemoryStore) FindAll(sessionID string) ([]*MemoryEntry, error) {
	query := `SELECT id, session_id, type, content, files, project, created_at, updated_at, ttl_seconds 
	          FROM memories WHERE session_id=? ORDER BY updated_at DESC`
	
	rows, err := ms.db.Query(query, sessionID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	var entries []*MemoryEntry
	for rows.Next() {
		var e MemoryEntry
		var ttlSeconds int
		err := rows.Scan(&e.ID, &e.SessionID, &e.Type, &e.Content,
			&e.Files, &e.Project, &e.CreatedAt, &e.UpdatedAt, &ttlSeconds)
		if err != nil {
			continue
		}
		e.TTL = time.Duration(ttlSeconds) * time.Second
		entries = append(entries, &e)
	}
	
	return entries, rows.Err()
}

// Delete 删除记忆
func (ms *MemoryStore) Delete(sessionID, memoryID string, reason string) error {
	query := `DELETE FROM memories WHERE session_id=? AND id=?`
	_, err := ms.db.Exec(query, sessionID, memoryID)
	return err
}

// cleanupLoop 定期清理过期记忆
func (ms *MemoryStore) cleanupLoop() {
	ticker := time.NewTicker(1 * time.Hour)
	defer ticker.Stop()
	
	for range ticker.C {
		ms.cleanupExpired()
	}
}

// cleanupExpired 清理过期记忆
func (ms *MemoryStore) cleanupExpired() {
	past := time.Now().Add(-24 * time.Hour).Format(time.RFC3339)
	query := `DELETE FROM memories WHERE updated_at < ?`
	_, err := ms.db.Exec(query, past)
	if err != nil {
		fmt.Printf("cleanup error: %v\n", err)
	}
}

// MemoryStats 记忆统计
type MemoryStats struct {
	Total      int `json:"total"`
	ByType     map[string]int `json:"by_type"`
	TotalChars int `json:"total_chars"`
}

// GetStats 获取记忆统计
func (ms *MemoryStore) GetStats(sessionID string) (*MemoryStats, error) {
	stats := &MemoryStats{
		ByType: make(map[string]int),
	}
	
	// 总数
	var total int
	err := ms.db.QueryRow("SELECT COUNT(*) FROM memories WHERE session_id=?", sessionID).Scan(&total)
	if err != nil {
		return nil, err
	}
	stats.Total = total
	
	// 按类型统计
	rows, err := ms.db.Query("SELECT type, COUNT(*) FROM memories WHERE session_id=? GROUP BY type", sessionID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	for rows.Next() {
		var memType string
		var count int
		rows.Scan(&memType, &count)
		stats.ByType[memType] = count
	}
	
	// 总字符数
	var chars int
	err = ms.db.QueryRow("SELECT SUM(LENGTH(content)) FROM memories WHERE session_id=?", sessionID).Scan(&chars)
	if err == nil {
		stats.TotalChars = chars
	}
	
	return stats, nil
}

// BatchSave 批量保存记忆（事务）
func (ms *MemoryStore) BatchSave(entries []*MemoryEntry) error {
	tx, err := ms.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	
	stmt, err := tx.Prepare(`INSERT OR REPLACE INTO memories (session_id, type, content, files, project, updated_at)
	                         VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)`)
	if err != nil {
		return err
	}
	defer stmt.Close()
	
	for _, e := range entries {
		_, err := stmt.Exec(e.SessionID, e.Type, e.Content, e.Files, e.Project)
		if err != nil {
			return err
		}
	}
	
	return tx.Commit()
}

func (ms *MemoryStore) findByType(sessionID, memType string) (*MemoryEntry, error) {
	query := `SELECT id, session_id, type, content, files, project, created_at, updated_at, ttl_seconds 
	          FROM memories WHERE session_id=? AND type=? LIMIT 1`
	var e MemoryEntry
	var ttlSeconds int
	err := ms.db.QueryRow(query, sessionID, memType).Scan(
		&e.ID, &e.SessionID, &e.Type, &e.Content, &e.Files, &e.Project,
		&e.CreatedAt, &e.UpdatedAt, &ttlSeconds)
	if err != nil {
		return nil, err
	}
	e.TTL = time.Duration(ttlSeconds) * time.Second
	return &e, nil
}
```

### FTS5 全文搜索增强

```go
package agentmemory

import "database/sql"

// FTSIndex FTS5 全文搜索索引
type FTSIndex struct {
	db *sql.DB
}

// NewFTSIndex 创建 FTS 索引
func NewFTSIndex(db *sql.DB) (*FTSIndex, error) {
	idx := &FTSIndex{db: db}
	if err := idx.createIndex(); err != nil {
		return nil, err
	}
	return idx, nil
}

func (idx *FTSIndex) createIndex() error {
	_, err := idx.db.Exec(`
		CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
			content,
			unable=rebuild,
			tokenize='unicode61 remove_diacritics 2'
		);
	`)
	return err
}

// SyncFTS 同步主表到 FTS 索引
func (idx *FTSIndex) SyncFTS(sessionID string) error {
	// 先清空再重建（简单方案，生产可用增量同步）
	_, err := idx.db.Exec("DELETE FROM memories_fts WHERE content IN (SELECT content FROM memories WHERE session_id=?)", sessionID)
	if err != nil {
		return err
	}
	
	rows, err := idx.db.Query("SELECT content FROM memories WHERE session_id=?", sessionID)
	if err != nil {
		return err
	}
	defer rows.Close()
	
	stmt, err := idx.db.Prepare("INSERT INTO memories_fts (content) VALUES (?)")
	if err != nil {
		return err
	}
	defer stmt.Close()
	
	for rows.Next() {
		var content string
		rows.Scan(&content)
		stmt.Exec(content)
	}
	
	return nil
}

// Search 全文搜索
func (idx *FTSIndex) Search(sessionID, query string, limit int) ([]*MemoryEntry, error) {
	ftsQuery := query + "* OR *" + query // 前缀匹配
	sql := `SELECT m.id, m.session_id, m.type, m.content, m.files, m.project, m.created_at, m.updated_at, m.ttl_seconds
	        FROM memories m INNER JOIN memories_fts f ON m.content = f.content
	        WHERE memories_fts MATCH ? AND m.session_id=?
	        ORDER BY rank LIMIT ?`
	
	rows, err := idx.db.Query(sql, ftsQuery, sessionID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	var entries []*MemoryEntry
	for rows.Next() {
		var e MemoryEntry
		var ttlSeconds int
		err := rows.Scan(&e.ID, &e.SessionID, &e.Type, &e.Content,
			&e.Files, &e.Project, &e.CreatedAt, &e.UpdatedAt, &ttlSeconds)
		if err != nil {
			continue
		}
		e.TTL = time.Duration(ttlSeconds) * time.Second
		entries = append(entries, &e)
	}
	
	return entries, rows.Err()
}
### 问题 3
Agent Memory 与外部存储（如 Redis）同步时的容错策略是什么？

<details>
<summary>查看答案</summary>

1. **写入确认**：Redis SET 返回成功才认为内存持久化完成，失败则回滚本地变更
2. **异步队列**：主线程将写操作放入缓冲队列，后台 Worker 批量刷入 Redis，避免阻塞
3. **死信队列**：持续失败的记录进入 dead letter queue，人工介入排查而非无限重试
4. **版本戳**：每个内存条目附带版本号，写 Redis 时比较 version 防止覆盖更新
5. **熔断机制**：Redis 连续 N 次失败时触发熔断，暂停同步并告警，恢复后重放队列中积压项
</details>
