# 分布式锁实现 - 资深专家深度实现

## 一、Redis分布式锁

```java
// 基本实现
public class RedisLock {
    private final RedisTemplate<String, String> redisTemplate;
    private static final String LOCK_PREFIX = "lock:";
    private static final Long RELEASE_SUCCESS = 1L;
    
    /**
     * 加锁
     * @param key 锁key
     * @param value 请求标识
     * @param expireTime 过期时间
     */
    public boolean tryLock(String key, String value, long expireTime) {
        String lockKey = LOCK_PREFIX + key;
        Boolean result = redisTemplate.opsForValue()
            .setIfAbsent(lockKey, value, expireTime, TimeUnit.MILLISECONDS);
        return Boolean.TRUE.equals(result);
    }
    
    /**
     * 释放锁
     */
    public boolean releaseLock(String key, String value) {
        String lockKey = LOCK_PREFIX + key;
        String currentValue = redisTemplate.opsForValue().get(lockKey);
        
        if (value.equals(currentValue)) {
            redisTemplate.delete(lockKey);
            return true;
        }
        return false;
    }
}
```

## 二、Redisson实现

```java
// 使用Redisson
RLock lock = redisson.getLock("myLock");

try {
    // 尝试加锁，最多等待100秒，锁自动10秒后过期
    if (lock.tryLock(100, 10, TimeUnit.SECONDS)) {
        // 业务逻辑
        doSomething();
    }
} finally {
    lock.unlock();
}
```

## 三、面试高频题

### Q1: Redis分布式锁原理？

```
A:
1. SET NX EX命令
2. 原子性保证
3. 看门狗续期
```

### Q2: 如何解决锁过期问题？

```
A:
1. 看门狗机制
2. 手动续期
3. Redisson自动续期
```

## 四、自测题

1. 解释Redis锁原理
2. 如何实现公平锁？
3. 如何处理锁失效？

---

## 参考文档

- [Redisson文档](https://github.com/redisson/redisson)
- [分布式锁实现](https://github.com/redis/redis-py/blob/master/redis/lock.py)
