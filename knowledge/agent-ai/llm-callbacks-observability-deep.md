# LLM 回调系统与可观测性深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、回调架构设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LLM 回调系统架构图                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐             │
│  │   Client     │──────▶│  Callback    │──────▶│  Handlers    │             │
│  │   (请求方)   │      │  Dispatcher  │      │              │             │
│  └──────────────┘      └──────┬───────┘      └──────┬───────┘             │
│                               │                     │                      │
│                    ┌──────────▼──────────┐  ┌───────▼────────┐            │
│                    │  Pre-Call Hooks     │  │  Post-Call      │            │
│                    │  • 限流检查         │  │  Handlers       │            │
│                    │  • 缓存命中         │  │  • Token 统计   │            │
│                    │  • 安全校验         │  │  • 成本追踪     │            │
│                    └─────────────────────┘  │  • 日志记录     │            │
│                                              └────────────────┘            │
│                                                                             │
│  关键设计点:                                                                 │
│  • 异步回调: 不阻塞主流程                                                    │
│  • 错误隔离: 单个 handler 失败不影响其他                                     │
│  • 优先级: 高优先级 handler 先执行                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心代码实现

```python
# 文件: callbacks/dispatcher.py

from typing import Callable, Dict, List, Any
from dataclasses import dataclass
import asyncio
import time

@dataclass
class CallbackContext:
    """回调上下文"""
    request_id: str
    model: str
    prompt: str
    start_time: float
    end_time: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    error: str = None
    cached: bool = False

class CallbackDispatcher:
    """回调分发器 - 支持异步和同步"""
    
    def __init__(self):
        self._pre_handlers: List[Callable] = []
        self._post_handlers: List[Callable] = []
        
    def on_pre_call(self, handler: Callable):
        """注册预调用处理器"""
        self._pre_handlers.append(handler)
        
    def on_post_call(self, handler: Callable):
        """注册后调用处理器"""
        self._post_handlers.append(handler)
        
    async def dispatch_pre(self, ctx: CallbackContext) -> bool:
        """
        分发预调用回调
        返回 False 表示应中止请求
        """
        for handler in self._pre_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(ctx)
                else:
                    result = handler(ctx)
                    
                if result is False:
                    return False  # 中止请求
            except Exception as e:
                logger.error(f"Pre-handler error: {e}")
                
        return True
        
    async def dispatch_post(self, ctx: CallbackContext):
        """分发后调用回调"""
        for handler in self._post_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(ctx)
                else:
                    handler(ctx)
            except Exception as e:
                logger.error(f"Post-handler error: {e}")


# ─── 内置回调处理器 ───

class RateLimitHandler:
    """限流处理器"""
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}
        
    async def __call__(self, ctx: CallbackContext) -> bool:
        now = time.time()
        key = ctx.request_id
        
        if key not in self.requests:
            self.requests[key] = []
            
        # 清理过期请求
        self.requests[key] = [
            t for t in self.requests[key]
            if t > now - self.window_seconds
        ]
        
        if len(self.requests[key]) >= self.max_requests:
            raise RateLimitError(f"Rate limit exceeded for {ctx.model}")
            
        self.requests[key].append(now)
        return True


class TokenCounter:
    """Token 计数器"""
    def __init__(self):
        self.total_tokens = 0
        self.cost_tracker = {}
        
    async def __call__(self, ctx: CallbackContext):
        cost = ctx.tokens_input * 0.000001 + ctx.tokens_output * 0.000002
        self.total_tokens += ctx.tokens_input + ctx.tokens_output
        
        model = ctx.model
        if model not in self.cost_tracker:
            self.cost_tracker[model] = {"tokens": 0, "cost": 0}
            
        self.cost_tracker[model]["tokens"] += ctx.tokens_input + ctx.tokens_output
        self.cost_tracker[model]["cost"] += cost


class CacheHandler:
    """缓存处理器 - 避免重复调用"""
    def __init__(self, cache: RedisCache):
        self.cache = cache
        
    async def __call__(self, ctx: CallbackContext) -> bool:
        cache_key = self._make_key(ctx.prompt)
        cached_result = await self.cache.get(cache_key)
        
        if cached_result:
            ctx.cached = True
            return False  # 使用缓存，跳过调用
            
        return True
```

---

## 三、监控指标

```yaml
# Prometheus metrics 定义
llm_callbacks_total:
  description: "总调用次数"
  type: counter
  
llm_callback_duration_seconds:
  description: "单次调用耗时"
  type: histogram
  
llm_callback_errors_total:
  description: "错误次数"
  type: counter
  
llm_tokens_total:
  description: "Token 消耗总量"
  type: counter
  
llm_cache_hit_ratio:
  description: "缓存命中率"
  type: gauge
```

---

## 四、参考资料

```
核心库:
├── LangChain Callbacks: https://python.langchain.com/docs/modules/callbacks/
├── OpenTelemetry: https://opentelemetry.io/
└── Weights & Biases: 实验追踪
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
