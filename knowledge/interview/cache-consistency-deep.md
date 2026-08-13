# 分布式缓存一致性 - 资深专家深度实现

## 一、缓存模式

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      缓存一致性模式                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Cache-Aside (旁路缓存)                                                  │
│   ├── 读: 缓存命中返回，未命中查DB并写入缓存                                 │
│   ├── 写: 先更新DB，再删除缓存                                             │
│   └── 优点: 简单，延迟低                                                   │
│                                                                         →
│   Read-Through (读写穿透)                                                 │
│   ├── 读: 缓存代理自动处理                                                  │
│   ├── 写: 缓存代理自动更新                                                  │
│   └── 缺点: 缓存与业务耦合                                                  │
│                                                                         →
│   Write-Through (写穿透)                                                   │
│   ├── 写: 同时写缓存和DB                                                   │
│   └── 优点: 数据一致，延迟高                                                 │
│                                                                         →
│   Write-Behind (写后方)                                                    │
│   ├── 写: 只写缓存，异步批量刷DB                                             │
│   └── 缺点: 可能丢失数据                                                     │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、实现代码

```java
// Cache-Aside实现
public class CacheAside implements CacheStrategy {
    
    private final RedisTemplate<String, Object> redis;
    private final Database db;
    
    @Override
    public Object get(String key) {
        // 1. 查缓存
        Object value = redis.opsForValue().get(key);
        if (value != null) {
            return value;
        }
        
        // 2. 查DB
        value = db.query(key);
        if (value != null) {
            // 3. 写缓存
            redis.opsForValue().set(key, value, 30, TimeUnit.MINUTES);
        }
        return value;
    }
    
    @Override
    public void put(String key, Object value) {
        // 1. 更新DB
        db.update(key, value);
        // 2. 删除缓存
        redis.delete(key);
    }
}
```

## 三、面试高频题

### Q1: 如何选择缓存模式？

```
A:
1. Cache-Aside: 最常见
2. Read-Through: 适合读多写少
3. Write-Behind: 适合高并发写
```

### Q2: 如何处理缓存穿透？

```
A:
1. 布隆过滤器
2. 缓存空值
3. 参数校验
```

## 四、自测题

1. 解释四种缓存模式
2. 如何实现Cache-Aside？
3. 如何处理缓存穿透？

---

## 参考文档

- [Redis缓存模式](https://redis.io/docs/manual/patterns/)
- [Netflix Archipelago](https://netflixtechblog.com/netflix-archipelago-ee0887bf15d5)
