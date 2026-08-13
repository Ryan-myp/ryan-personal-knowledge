# 短链接系统设计 - 资深专家深度实现

## 一、核心流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       短链接系统流程                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   User → 长链接 → [编码] → 短链接 → [存储] → 数据库                     │
│                                      ↓                                  │
│                              访问短链接                                   │
│                                      ↓                                  │
│                              [解码] → 查库 → 重定向到长链接                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、编码方案

```go
package shorturl

import (
    "strconv"
)

const base62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

// 62进制编码
func Encode(id int64) string {
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

// 62进制解码
func Decode(s string) int64 {
    var id int64
    for _, c := range s {
        id = id*62 + int64(indexOf(string(c)))
    }
    return id
}

func indexOf(c string) int {
    for i := 0; i < len(base62); i++ {
        if string(base62[i]) == c {
            return i
        }
    }
    return -1
}
```

## 三、数据库设计

```sql
CREATE TABLE short_url (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    long_url VARCHAR(2048) NOT NULL,
    short_code VARCHAR(10) UNIQUE NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    expire_time DATETIME,
    click_count INT DEFAULT 0,
    INDEX idx_short_code (short_code),
    INDEX idx_create_time (create_time)
);
```

## 四、面试高频题

### Q1: 如何解决哈希碰撞？

```
A:
1. 使用更长编码 (base62)
2. 数据库唯一约束
3. 冲突重试
```

### Q2: 如何优化查询性能？

```
A:
1. Redis缓存热点链接
2. 数据库索引优化
3. CDN缓存静态内容
```

## 五、自测题

1. 解释编码方案
2. 如何处理过期链接？
3. 如何统计点击量？

---

## 参考文档

- [短链接系统设计](https://github.com/vipshop/vns-service-team/wiki)
- [URL缩短算法](https://en.wikipedia.org/wiki/Ur Shortening_service)
