# 短链接系统设计 --- 资深专家深度实现

## 概述

短链接服务是互联网基础服务之一，广泛应用于营销推广和社交媒体。本文深入剖析短链生成、跳转和统计的实现。

## 一、核心算法

### 1.1 Base62编码

```go
package shortlink

import (
    "strconv"
)

const base62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

// ID转短链
func IDToShortLink(id int64) string {
    if id == 0 {
        return "0"
    }
    
    var result []byte
    for id > 0 {
        result = append(result, base62[id%62])
        id /= 62
    }
    
    // 反转
    for i, j := 0, len(result)-1; i < j; i, j = i+1, j-1 {
        result[i], result[j] = result[j], result[i]
    }
    
    return string(result)
}

// 短链转ID
func ShortLinkToID(short string) int64 {
    var id int64
    for _, ch := range short {
        id = id*62 + indexOf(base62, byte(ch))
    }
    return id
}

func indexOf(chars []byte, ch byte) int64 {
    for i, c := range chars {
        if c == ch {
            return int64(i)
        }
    }
    return -1
}
```

### 1.2 哈希缩短

```go
import (
    "crypto/sha256"
    "encoding/binary"
)

// 使用URL的hash值生成短链
func URLToShortLink(url string) string {
    hash := sha256.Sum256([]byte(url))
    // 取前8字节
    id := binary.BigEndian.Uint64(hash[:8])
    return IDToShortLink(int64(id))
}
```

## 二、存储设计

### 2.1 表结构

```sql
CREATE TABLE short_links (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    short_code VARCHAR(10) NOT NULL UNIQUE,
    original_url VARCHAR(2048) NOT NULL,
    create_time DATETIME NOT NULL,
    expire_time DATETIME,
    status TINYINT DEFAULT 1,
    
    INDEX idx_short_code (short_code),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 支持62^6 ≈ 568亿条记录（6位短链）
-- 支持62^8 ≈ 218万亿条记录（8位短链）
```

### 2.2 分表策略

```sql
-- 按短链ID取模分表
CREATE TABLE short_links_0 LIKE short_links;
CREATE TABLE short_links_1 LIKE short_links;
CREATE TABLE short_links_2 LIKE short_links;
-- ... 共1024张表

-- 路由
-- short_code = IDToShortLink(id % 1024)
```

## 三、跳转优化

### 3.1 301 vs 302

```go
// 301永久重定向（SEO友好）
func Redirect301(w http.ResponseWriter, url string) {
    w.Header().Set("Location", url)
    w.WriteHeader(http.StatusMovedPermanently)
}

// 302临时重定向（可动态修改）
func Redirect302(w http.ResponseWriter, url string) {
    w.Header().Set("Location", url)
    w.WriteHeader(http.StatusFound)
}
```

### 3.2 负载均衡

```go
// 使用Nginx负载均衡
location /s/ {
    # 短链跳转
    rewrite ^/s/([a-zA-Z0-9]+)$ /redirect?code=$1 last;
}

location = /redirect {
    # 代理到后端服务
    proxy_pass http://backend;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## 四、统计分析

### 4.1 访问日志

```sql
CREATE TABLE link_stats (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    short_code VARCHAR(10) NOT NULL,
    ip VARCHAR(45),
    user_agent TEXT,
    referer VARCHAR(256),
    country VARCHAR(64),
    city VARCHAR(64),
    create_time DATETIME NOT NULL,
    
    INDEX idx_short_code (short_code),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 4.2 实时统计

```go
// 使用Redis统计PV/UV
func RecordVisit(shortCode string, visitorID string) {
    ctx := context.Background()
    
    // PV统计
    redis.Incr(ctx, fmt.Sprintf("pv:%s", shortCode))
    
    // UV统计（去重）
    redis.SAdd(ctx, fmt.Sprintf("uv:%s", shortCode), visitorID)
    
    // 实时计数
    redis.HIncrBy(ctx, fmt.Sprintf("stats:%s", shortCode), 
        time.Now().Format("2006-01-02"), 1)
}
```

### 4.3 批量聚合

```go
// 定时聚合统计数据
func AggregateStats() {
    // 每小时的统计数据
    startDate := time.Now().Add(-24 * time.Hour)
    
    for startDate.Before(time.Now()) {
        date := startDate.Format("2006-01-02")
        
        // 从Redis读取当日数据
        pv, _ := redis.Get(context.Background(), 
            fmt.Sprintf("pv:%s:%s", shortCode, date)).Int64()
        
        // 写入ClickHouse
        clickhouse.Insert("link_stats_daily", StatsRecord{
            Date:     date,
            ShortCode: shortCode,
            PV:       pv,
            UV:       uv,
        })
        
        startDate = startDate.Add(24 * time.Hour)
    }
}
```

## 五、缓存策略

### 5.1 多级缓存

```go
// L1: 本地缓存 (热点短链)
var localCache = cache.New(5*time.Minute, 10*time.Minute)

// L2: Redis缓存
var redisClient = redis.NewClient(...)

func GetOriginalURL(shortCode string) (string, error) {
    // 1. 查本地缓存
    if v, ok := localCache.Get(shortCode); ok {
        return v.(string), nil
    }
    
    // 2. 查Redis
    url, err := redisClient.Get(context.Background(), 
        fmt.Sprintf("short:%s", shortCode)).String()
    if err == nil {
        localCache.Set(shortCode, url, 5*time.Minute)
        return url, nil
    }
    
    // 3. 查数据库
    var link ShortLink
    db.Where("short_code = ?", shortCode).First(&link)
    
    // 写入缓存
    redisClient.Set(context.Background(), 
        fmt.Sprintf("short:%s", shortCode), link.OriginalURL, 10*time.Minute)
    localCache.Set(shortCode, link.OriginalURL, 5*time.Minute)
    
    return link.OriginalURL, nil
}
```

## 六、面试高频题

### 6.1 高频问题

**Q1: 如何生成唯一短链？**

A: 基于自增ID的Base62编码或URL的Hash值。

**Q2: 如何解决短链冲突？**

A: 增加短链长度或检测冲突后重试。

**Q3: 如何提高跳转性能？**

A: 多级缓存 + 本地缓存热点数据 + 异步统计。

### 6.2 自测题

1. 实现Base62编码算法
2. 设计短链存储方案
3. 分析跳转性能优化点
4. 设计实时统计方案
5. 解释短链过期的处理

---

**创建时间**: 2026-10-17
**作者**: Ryan
**领域**: Interview / 系统设计
**关键词**: short-link, url-shortener, base62, redirect, statistics
