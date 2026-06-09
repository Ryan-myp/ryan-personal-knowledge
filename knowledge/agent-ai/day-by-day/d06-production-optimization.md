# Day 6: 生产级 Agent 系统 — 从入门到源码级

> 学习目标: 先理解生产级 Agent 是什么、为什么需要，再深入源码

---

## 第一部分：入门引导（5 分钟速览）

### 6.1 原型 vs 生产环境

```
原型环境:
├─ 1 个用户
├─ 不关心成本
├─ 偶尔失败没关系
└─ 不考虑安全

生产环境:
├─ 1000+ 用户并发
├─ 严格控制成本
├─ 99.9% 可用
├─ 严格审计
└─ 安全第一
```

### 6.2 生产级 Agent 的关键挑战

```
1. 并发控制
   - 防止死循环
   - 限制 token 消耗
   - 避免雪崩

2. 成本优化
   - Token 压缩
   - 结果缓存
   - 批量处理

3. 可靠性
   - 错误恢复
   - 降级策略
   - 超时处理

4. 可观测性
   - 调用链追踪
   - 指标监控
   - 日志记录
```

### 6.3 缓存策略

```
缓存场景:
1. 相同问题缓存: "北京天气？" → 缓存结果
2. 相似问题缓存: "北京气温？" → 匹配缓存
3. 工具结果缓存: get_weather("北京") → 缓存

缓存策略:
- TTL: 过期时间
- 容量限制: 最多存多少
- 淘汰策略: LRU（最近最少使用）
```

### 6.4 快速体验

```python
# 安装依赖
pip install redis

import redis
import hashlib
from functools import lru_cache

# 1. Redis 缓存
redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_with_cache(key: str, func):
    """带缓存的函数调用"""
    # 先查缓存
    cached = redis_client.get(key)
    if cached:
        print("缓存命中!")
        return cached.decode()
    
    # 缓存未命中，执行函数
    result = func()
    
    # 写入缓存
    redis_client.setex(key, 300, result)  # 5 分钟过期
    return result

# 2. LRU 缓存（简单场景）
@lru_cache(maxsize=100)
def expensive_function(question: str) -> str:
    """需要缓存的函数"""
    # 模拟耗时操作
    import time
    time.sleep(1)
    return f"答案是: {question}"

# 测试
print(get_with_cache("北京天气", lambda: "晴天，25度"))
print(expensive_function("什么是 AI?"))
```

### 6.5 关键概念总结

| 概念 | 说明 |
|------|------|
| **并发控制** | 防止死循环和雪崩 |
| **Token 压缩** | 减少上下文长度 |
| **结果缓存** | 避免重复计算 |
| **错误恢复** | 失败自动重试 |
| **可观测性** | 监控和日志 |

---

## 第二部分：源码级深度剖析

### 6.6 缓存实现源码

```python
# langchain/caching.py
# 缓存系统

class BaseCache(BaseModel):
    """
    缓存基类
    
    支持:
    ├── MemoryCache: 内存缓存
    ├── RedisCache: Redis 缓存
    └── SQLiteCache: 数据库缓存
    """
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        raise NotImplementedError
    
    def put(self, key: str, value: Any) -> None:
        """写入缓存"""
        raise NotImplementedError
    
    def clear(self) -> None:
        """清空缓存"""
        raise NotImplementedError

class MemoryCache(BaseCache):
    """
    内存缓存
    
    实现:
    - 使用 OrderedDict
    - LRU 淘汰策略
    - TTL 过期
    """
    
    def __init__(self, maxsize: int = 100):
        self._cache = {}
        self._access_times = OrderedDict()
        self.maxsize = maxsize
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存
        
        流程:
        1. 检查 key 是否存在
        2. 检查是否过期
        3. 更新访问顺序
        4. 返回缓存值
        """
        if key not in self._cache:
            return None
        
        item = self._cache[key]
        if item["expires"] and time.time() > item["expires"]:
            self._delete(key)
            return None
        
        # 更新访问顺序
        self._access_times.move_to_end(key)
        return item["value"]
    
    def put(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        写入缓存
        
        流程:
        1. 检查是否满
        2. 如果满，淘汰 LRU
        3. 写入新值
        4. 更新访问顺序
        """
        # 检查容量
        if len(self._cache) >= self.maxsize:
            self._evict_lru()
        
        # 写入
        self._cache[key] = {
            "value": value,
            "expires": time.time() + ttl if ttl else None,
            "created": time.time()
        }
        self._access_times[key] = True
    
    def _evict_lru(self) -> None:
        """淘汰 LRU"""
        if self._access_times:
            lru_key, _ = self._access_times.popitem(last=False)
            self._delete(lru_key)
    
    def _delete(self, key: str) -> None:
        """删除缓存"""
        self._cache.pop(key, None)
        self._access_times.pop(key, None)
```

### 6.7 并发控制源码

```python
# langchain/agents/concurrency.py
# 并发控制

class ConcurrencyController:
    """
    并发控制器
    
    功能:
    ├── 限制最大并发数
    ├── 实现信号量
    └── 防止雪崩
    """
    
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_requests = 0
        self.max_active = max_concurrent
    
    async def execute(self, func, *args, **kwargs):
        """
        执行函数
        
        流程:
        1. 等待信号量
        2. 执行函数
        3. 释放信号量
        """
        async with self.semaphore:
            self.active_requests += 1
            try:
                return await func(*args, **kwargs)
            finally:
                self.active_requests -= 1
    
    @property
    def queue_length(self) -> int:
        """当前队列长度"""
        return self.max_active - self.semaphore._value
```

### 6.8 错误恢复源码

```python
# langchain/utils/retry.py
# 错误恢复机制

def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """
    带退避的重试
    
    流程:
    1. 执行函数
    2. 如果失败，等待并重试
    3. 等待时间指数增长
    4. 超过最大重试次数，抛出异常
    
    退避策略:
    - 第 1 次重试: 等待 1s
    - 第 2 次重试: 等待 2s
    - 第 3 次重试: 等待 4s
    ...
    - 最大等待: 60s
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as e:
            if attempt == max_retries:
                raise
            
            # 计算等待时间
            delay = min(base_delay * (2 ** attempt), max_delay)
            time.sleep(delay)
```

---

## 第三部分：自测

### 问题 1
为什么要做缓存？
<details>
<summary>查看答案</summary>

- 避免重复计算
- 降低成本
- 减少延迟
</details>

### 问题 2
LRU 淘汰策略是什么？
<details>
<summary>查看答案</summary>

- Least Recently Used
- 淘汰最久未使用的
- 维护访问顺序
- 当缓存满时淘汰
</details>

### 问题 3
指数退避的好处是什么？
<details>
<summary>查看答案</summary>

- 避免频繁重试
- 给系统恢复时间
- 防止雪崩
- 逐步增加等待时间
</details>

---

## 第四部分：动手验证

### 6.1 测试缓存效果

```python
# 见上方的快速体验代码
```

*今天花 60-90 分钟：前 5 分钟入门，40 分钟源码分析，15 分钟动手验证*
*答不出自测题？回去重读对应章节。*
