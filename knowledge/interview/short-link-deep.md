# 系统设计：短链接 - 资深专家深度实现

## 一、核心流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       短链接系统架构                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│   │  Browser │───►│  Redis   │───►│  Cache   │───►│  MySQL   │        │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘        │
│                                                                         │
│   生成: URL → Base62 → ID → 存储                                      │
│   解析: ID → 查询 → 301 Redirect                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Go实现

```go
package shortlink

import (
    "encoding/base64"
    "strconv"
)

const charset = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

type ShortLinkService struct {
    redis  *RedisClient
    db     *DB
}

// 生成短链接
func (s *ShortLinkService) Create(longURL string) (string, error) {
    // 1. 获取唯一ID
    id, err := s.getNextID()
    if err != nil {
        return "", err
    }
    
    // 2. 转换为Base62
    shortCode := base62Encode(id)
    
    // 3. 存储到Redis
    ctx, cancel := context.WithTimeout(context.Background(), time.Second)
    defer cancel()
    err = s.redis.SetEX(ctx, "url:"+shortCode, longURL, 365*24*time.Hour)
    if err != nil {
        return "", err
    }
    
    // 4. 持久化到MySQL
    err = s.db.Insert(shortCode, longURL)
    
    return shortCode, nil
}

// 解析短链接
func (s *ShortLinkService) Resolve(shortCode string) (string, error) {
    ctx, cancel := context.WithTimeout(context.Background(), time.Second)
    defer cancel()
    
    // 从Redis获取
    longURL, err := s.redis.Get(ctx, "url:"+shortCode)
    if err == redis.Nil {
        // 回源到MySQL
        longURL, err = s.db.SelectByShortCode(shortCode)
        if err != nil {
            return "", err
        }
        // 回填Redis
        s.redis.SetEX(ctx, "url:"+shortCode, longURL, 365*24*time.Hour)
    }
    
    return longURL, nil
}

// Base62编码
func base62Encode(n int64) string {
    if n == 0 {
        return string(charset[0])
    }
    
    var result []byte
    for n > 0 {
        result = append(result, charset[n%62])
        n /= 62
    }
    
    // 反转
    for i, j := 0, len(result)-1; i < j; i, j = i+1, j-1 {
        result[i], result[j] = result[j], result[i]
    }
    
    return string(result)
}
```

## 三、面试高频题

### Q1: 如何处理冲突？

```
A: 使用数据库唯一约束或Redis原子操作
```

### Q2: 如何保证短链接不重复？

```
A: 使用分布式ID生成器
```

## 四、自测题

1. 解释短链接系统架构
2. 如何处理高并发？
3. 如何实现统计功能？

---

## 参考文档

- [TinyURL源码](https://github.com/ridiculousfish/tinyservice)
- [Bitly架构](https://github.com/bitly/bitly)
