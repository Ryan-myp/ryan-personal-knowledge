# 广告平台限流(Ratelimit)处理完全指南

> **领域**: 广告投放 / API 工程
> **深度**: ⭐⭐⭐⭐⭐ 生产级指南
> **标签**: ratelimit, throttling, retry, google-ads, meta-ads, tiktok-ads, dv360
> **更新时间**: 2026-08-14
> **类型**: production/engineering

---

## 一、各平台限流对比

### 1.1 限流规则速查表

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    四大平台限流规则对比                                   │
├──────────────┬──────────────┬───────────────┬──────────────┬─────────────┤
│    平台       │   限流单位    │   速率限制     │   触发响应    │  恢复策略    │
├──────────────┼──────────────┼───────────────┼──────────────┼─────────────┤
│ Google Ads   │ per customer │ 100 req/min    │ 429 + header │ 指数退避    │
│              │ per operation│ 10 req/sec     │ Retry-After  │             │
├──────────────┼──────────────┼───────────────┼──────────────┼─────────────┤
│ Meta         │ per app      │ 2000 req/hr    │ 500 + JSON   │ 等待 Retry  │
│              │ per user     │ 100 req/min    │ error_code   │ 头信息      │
├──────────────┼──────────────┼───────────────┼──────────────┼─────────────┤
│ TikTok       │ per account  │ 100 req/min    │ 429 JSON     │ Retry-After │
│              │ per ip       │ 500 req/min    │              │             │
├──────────────┼──────────────┼───────────────┼──────────────┼─────────────┤
│ DV360        │ per project  │ 1000 req/min   │ 429/503      │ Retry-After │
│              │ per user     │ 100 req/sec    │              │             │
└──────────────┴──────────────┴───────────────┴──────────────┴─────────────┘
```

### 1.2 各平台限流响应头

```
Google Ads (gRPC):
├── x-goog-request-reason: RATE_LIMITED
├── google.rpc.retryinfo-bin: RetryInfo 消息
└── status code: 429

Google Ads (REST):
├── Retry-After: 30 (秒)
├── X-Google-Trace-Id: 追踪 ID
└── status code: 429

Meta:
├── X-FB-Rate-Limit: 当前限流状态
├── Retry-After: 秒数
└── error_code: 4/17/613

TikTok:
├── X-RateLimit-Limit: 限制值
├── X-RateLimit-Remaining: 剩余次数
├── X-RateLimit-Reset: 重置时间戳
└── status code: 429

DV360:
├── Retry-After: 秒数
├── x-google-quota-exhausted: true
└── status code: 429/503
```

---

## 二、通用限流处理架构

### 2.1 三层防护模型

```
┌─────────────────────────────────────────────────────────────────┐
│                      限流防护三层模型                            │
│                                                                 │
│  Layer 1: 客户端预检 (Pre-check)                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • 令牌桶 (Token Bucket) — 本地速率控制                  │   │
│  │  • 滑动窗口 (Sliding Window) — 精确统计                   │   │
│  │  • 漏桶 (Leaky Bucket) — 匀速输出                        │   │
│  │  → 目标: 在 80% 配额内发送请求                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  Layer 2: 智能重试 (Smart Retry)                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • 指数退避 (Exponential Backoff)                        │   │
│  │  • 带抖动的退避 (Jitter)                                 │   │
│  │  • 基于 Retry-After 头的等待                             │   │
│  │  • 部分失败重试 (Partial Retry)                          │   │
│  │  → 目标: 优雅处理 429 响应                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  Layer 3: 降级与熔断 (Circuit Breaker)                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • 熔断器模式 (Circuit Breaker)                          │   │
│  │  • 队列缓冲 (Queue Buffer)                               │   │
│  │  • 本地缓存 (Local Cache)                                │   │
│  │  • 优雅降级 (Graceful Degradation)                       │   │
│  │  → 目标: 持续高可用，不雪崩                               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Go 实现

```go
package ratelimit

import (
	"context"
	"fmt"
	"math"
	"math/rand"
	"sync"
	"time"
)

// ─────────────────────────────────────────────
// Layer 1: 令牌桶限流器
// ─────────────────────────────────────────────

type TokenBucket struct {
	mu         sync.Mutex
	tokens     float64
	maxTokens  float64
	refillRate float64 // tokens per second
	lastRefill time.Time
}

func NewTokenBucket(maxTokens, refillRate float64) *TokenBucket {
	return &TokenBucket{
		tokens:     maxTokens,
		maxTokens:  maxTokens,
		refillRate: refillRate,
		lastRefill: time.Now(),
	}
}

func (tb *TokenBucket) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.tokens = math.Min(tb.maxTokens, tb.tokens+elapsed*tb.refillRate)
	tb.lastRefill = now

	if tb.tokens >= 1.0 {
		tb.tokens -= 1.0
		return true
	}
	return false
}

func (tb *TokenBucket) Wait(ctx context.Context) error {
	for {
		if tb.Allow() {
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(10 * time.Millisecond):
			// 短暂等待后重试
		}
	}
}

// ─────────────────────────────────────────────
// Layer 2: 智能重试器
// ─────────────────────────────────────────────

type RetryConfig struct {
	MaxRetries     int
	InitialDelay   time.Duration
	MaxDelay       time.Duration
	BackoffFactor  float64
	Jitter         bool
	RetryableCodes []int
}

var DefaultRetryConfig = RetryConfig{
	MaxRetries:     5,
	InitialDelay:   100 * time.Millisecond,
	MaxDelay:       30 * time.Second,
	BackoffFactor:  2.0,
	Jitter:         true,
	RetryableCodes: []int{429, 500, 502, 503, 504},
}

func CalculateBackoff(attempt int, cfg RetryConfig) time.Duration {
	delay := float64(cfg.InitialDelay)
	for i := 0; i < attempt; i++ {
		delay *= cfg.BackoffFactor
	}
	if delay > float64(cfg.MaxDelay) {
		delay = float64(cfg.MaxDelay)
	}
	if cfg.Jitter {
		// 添加 0-50% 随机抖动，避免 thundering herd
		jitter := rand.Float64() * 0.5 * delay
		delay += jitter
	}
	return time.Duration(delay)
}

// RetryableError 判断错误是否可重试
func IsRetryable(statusCode int, cfg RetryConfig) bool {
	for _, code := range cfg.RetryableCodes {
		if statusCode == code {
			return true
		}
	}
	return false
}

// ParseRetryAfter 解析 Retry-After 头
func ParseRetryAfter(header string) (time.Duration, error) {
	// 尝试解析为秒数
	var seconds int
	if _, err := fmt.Sscanf(header, "%d", &seconds); err == nil {
		return time.Duration(seconds) * time.Second, nil
	}
	// 尝试解析为 HTTP 日期
	t, err := time.Parse(time.RFC1123, header)
	if err != nil {
		return 0, err
	}
	delay := time.Until(t)
	if delay < 0 {
		delay = 0
	}
	return delay, nil
}

// ─────────────────────────────────────────────
// Layer 3: 熔断器
// ─────────────────────────────────────────────

type CircuitState int

const (
	CircuitClosed   CircuitState = iota // 正常
	CircuitOpen                         // 熔断
	CircuitHalfOpen                     // 半开（测试中）
)

type CircuitBreaker struct {
	mu               sync.Mutex
	state            CircuitState
	failureCount     int
	successCount     int
	failureThreshold int
	successThreshold int
	openDuration     time.Duration
	lastFailureTime  time.Time
}

func NewCircuitBreaker(failureThreshold, successThreshold int, duration time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:            CircuitClosed,
		failureThreshold: failureThreshold,
		successThreshold: successThreshold,
		openDuration:     duration,
	}
}

func (cb *CircuitBreaker) Allow() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	switch cb.state {
	case CircuitClosed:
		return true
	case CircuitOpen:
		// 检查是否过了开放时间
		if time.Since(cb.lastFailureTime) > cb.openDuration {
			cb.state = CircuitHalfOpen
			cb.successCount = 0
			return true
		}
		return false
	case CircuitHalfOpen:
		return true
	}
	return false
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.failureCount = 0
	if cb.state == CircuitHalfOpen {
		cb.successCount++
		if cb.successCount >= cb.successThreshold {
			cb.state = CircuitClosed
		}
	}
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.failureCount++
	cb.lastFailureTime = time.Now()

	if cb.state == CircuitHalfOpen {
		cb.state = CircuitOpen
	} else if cb.failureCount >= cb.failureThreshold {
		cb.state = CircuitOpen
	}
}
```

---

## 三、各平台限流处理实战

### 3.1 Google Ads 限流处理

```go
package googleads

import (
	"context"
	"fmt"
	"log"
	"time"

	"google.golang.org/api/googleads/v16"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// GoogleAdsRateLimiter Google Ads 专用限流器
type GoogleAdsRateLimiter struct {
	bucket     *TokenBucket
	circuit    *CircuitBreaker
	retryCfg   RetryConfig
	client     *googleads.GoogleAdsClient
	customerID int64
}

func NewGoogleAdsRateLimiter(client *googleads.GoogleAdsClient, customerID int64) *GoogleAdsRateLimiter {
	// Google Ads: 100 req/min = 1.67 req/sec
	return &GoogleAdsRateLimiter{
		bucket:     NewTokenBucket(100.0, 1.67),
		circuit:    NewCircuitBreaker(5, 3, 60*time.Second),
		retryCfg:   DefaultRetryConfig,
		client:     client,
		customerID: customerID,
	}
}

// MutateWithRetry 带限流和重试的 mutate 操作
func (g *GoogleAdsRateLimiter) MutateWithRetry(
	ctx context.Context,
	op func(ctx context.Context) error,
) error {
	for attempt := 0; attempt <= g.retryCfg.MaxRetries; attempt++ {
		// Layer 1: 令牌桶限流
		if err := g.bucket.Wait(ctx); err != nil {
			return fmt.Errorf("rate limit wait cancelled: %w", err)
		}

		// Layer 3: 熔断器检查
		if !g.circuit.Allow() {
			return fmt.Errorf("circuit breaker is OPEN, retry after %v", g.retryCfg.MaxDelay)
		}

		// 执行操作
		err := op(ctx)
		if err == nil {
			g.circuit.RecordSuccess()
			return nil
		}

		// 判断是否可重试
		st, ok := status.FromError(err)
		if !ok || !isGoogleRetryable(st.Code()) {
			g.circuit.RecordFailure()
			return err // 不可重试，直接返回
		}

		g.circuit.RecordFailure()

		// 计算重试延迟
		if attempt < g.retryCfg.MaxRetries {
			delay := CalculateBackoff(attempt, g.retryCfg)
			log.Printf("[Google Ads] Rate limited, retry %d/%d after %v",
				attempt+1, g.retryCfg.MaxRetries, delay)
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(delay):
			}
		}
	}

	return fmt.Errorf("failed after %d retries", g.retryCfg.MaxRetries)
}

func isGoogleRetryable(code codes.Code) bool {
	return code == codes.ResourceExhausted || // 429
		code == codes.Unavailable ||      // 503
		code == codes.DeadlineExceeded    // 504
}
```

### 3.2 Meta 限流处理

```python
"""
Meta Marketing API 限流处理
"""
import time
import logging
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)

class MetaRateLimiter:
    """Meta Marketing API 限流器"""

    def __init__(self, app_id: str, access_token: str):
        self.app_id = app_id
        self.access_token = access_token
        self.base_url = "https://graph.facebook.com/v18.0"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"OAuth {access_token}",
        })
        # Meta: 2000 req/hour = 0.556 req/sec
        self._last_request_time = 0
        self._min_interval = 1.8  # 安全间隔 (秒)

    def _respect_rate_limit(self):
        """遵守限流规则"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            sleep_time = self._min_interval - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _parse_retry_after(self, response: requests.Response) -> float:
        """解析 Retry-After 响应"""
        # Meta 通常在 error body 中提供重试信息
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            return float(retry_after)

        # 检查 error code
        if response.status_code == 429:
            try:
                error_data = response.json()
                # Meta 的 error code 17 = Rate limit
                if error_data.get('error', {}).get('code') == 17:
                    # 通常建议等待 60-300 秒
                    return 60.0
            except:
                pass
        return 60.0  # 默认等待 60 秒

    def request_with_retry(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        max_retries: int = 5
    ) -> Dict[str, Any]:
        """带重试的请求"""
        params = params or {}
        params['access_token'] = self.access_token

        for attempt in range(max_retries + 1):
            self._respect_rate_limit()

            url = f"{self.base_url}/{endpoint}"
            try:
                response = self.session.request(
                    method, url, params=params, timeout=30
                )

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 429:
                    retry_after = self._parse_retry_after(response)
                    jitter = retry_after * 0.3 * (hash(time.time()) % 100) / 100
                    wait_time = retry_after + jitter
                    logger.warning(
                        f"Meta rate limited (attempt {attempt+1}/{max_retries+1}), "
                        f"retry after {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)
                    continue

                # 其他可重试错误
                if response.status_code in (500, 502, 503):
                    delay = min(2 ** attempt * 0.5, 30)
                    jitter = delay * 0.3 * (hash(time.time()) % 100) / 100
                    logger.warning(
                        f"Meta server error {response.status_code}, "
                        f"retry in {delay+jitter:.1f}s"
                    )
                    time.sleep(delay + jitter)
                    continue

                # 不可重试的错误
                response.raise_for_status()

            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        raise Exception(f"Failed after {max_retries} retries")
```

### 3.3 TikTok 限流处理

```python
"""
TikTok Marketing API 限流处理
"""
import time
import hashlib
import logging
from typing import Optional, Dict
import requests

logger = logging.getLogger(__name__)

class TikTokRateLimiter:
    """TikTok Marketing API 限流器"""

    def __init__(self, app_key: str, app_secret: str, access_token: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self.base_url = "https://business-api.tiktok.com/portal/api/v20230728"
        self.session = requests.Session()
        # TikTok: 100 req/min per account
        self._request_count = 0
        self._window_start = time.time()
        self._rate_limit = 100  # per minute
        self._reset_interval = 60  # seconds

    def _check_rate_limit(self):
        """检查并遵守限流"""
        now = time.time()

        # 重置窗口
        if now - self._window_start >= self._reset_interval:
            self._request_count = 0
            self._window_start = now

        if self._request_count >= self._rate_limit:
            wait_time = self._reset_interval - (now - self._window_start)
            logger.warning(f"TikTok rate limit reached, waiting {wait_time:.1f}s")
            time.sleep(wait_time + 0.1)
            self._request_count = 0
            self._window_start = time.time()

        self._request_count += 1

    def _handle_response(self, response: requests.Response) -> Optional[Dict]:
        """处理响应，包括限流"""
        if response.status_code == 200:
            data = response.json()
            # 检查业务层限流
            if data.get('response_code') == 200013:
                # Rate limited
                retry_after = data.get('message', '')
                logger.warning(f"TikTok business rate limited: {retry_after}")
                time.sleep(60)
                return None
            return data.get('data')

        if response.status_code == 429:
            # 解析 X-RateLimit-Reset
            reset_ts = response.headers.get('X-RateLimit-Reset')
            if reset_ts:
                wait = int(reset_ts) - int(time.time()) + 1
            else:
                wait = 60
            logger.warning(f"TikTok HTTP 429, waiting {wait}s")
            time.sleep(max(wait, 1))
            return None

        response.raise_for_status()
        return None

    def request_with_retry(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        max_retries: int = 3
    ) -> Optional[Dict]:
        """带限流和重试的请求"""
        data = data or {}
        data['access_token'] = self.access_token
        data['app_key'] = self.app_key

        for attempt in range(max_retries):
            self._check_rate_limit()

            url = f"{self.base_url}/{endpoint}"
            try:
                response = self.session.request(
                    method, url, json=data, timeout=30
                )
                result = self._handle_response(response)
                if result is not None:
                    return result
            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        return None
```

---

## 四、统一限流客户端

### 4.1 多平台限流器

```python
"""
统一限流客户端 — 四个平台的统一抽象
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any
import time
import logging

logger = logging.getLogger(__name__)

class Platform(str, Enum):
    GOOGLE = "google"
    META = "meta"
    TIKTOK = "tiktok"
    DV360 = "dv360"

class RateLimitHandler(ABC):
    """限流处理器抽象基类"""

    @abstractmethod
    def check_limit(self) -> bool:
        """检查是否超出限流"""
        pass

    @abstractmethod
    def wait_if_limited(self) -> float:
        """如果超限，等待并返回等待时间"""
        pass

    @abstractmethod
    def handle_rate_limit_response(self, response: Any) -> float:
        """处理限流响应，返回需要等待的秒数"""
        pass


class UnifiedRateLimiter:
    """
    统一限流管理器
    维护所有平台的令牌桶 + 熔断器
    """

    def __init__(self):
        self._limiters: Dict[Platform, RateLimitHandler] = {}
        self._stats = {
            'total_requests': 0,
            'rate_limited': 0,
            'retries': 0,
            'circuit_breaker_trips': 0,
        }

    def register(self, platform: Platform, limiter: RateLimitHandler):
        """注册平台限流器"""
        self._limiters[platform] = limiter

    def execute_with_protection(
        self,
        platform: Platform,
        operation,
        *args,
        max_retries: int = 5,
        **kwargs
    ) -> Any:
        """
        带限流保护的操作执行

        流程:
        1. 令牌桶检查 (Layer 1)
        2. 执行操作
        3. 如果遇到限流 → 智能重试 (Layer 2)
        4. 如果持续限流 → 熔断 (Layer 3)
        """
        limiter = self._limiters.get(platform)
        if not limiter:
            return operation(*args, **kwargs)

        self._stats['total_requests'] += 1
        last_wait_time = 0

        for attempt in range(max_retries + 1):
            # Layer 1: 令牌桶检查
            if not limiter.check_limit():
                wait_time = limiter.wait_if_limited()
                self._stats['rate_limited'] += 1
                last_wait_time = wait_time
                logger.warning(
                    f"[{platform}] Rate limited, waiting {wait_time:.1f}s "
                    f"(attempt {attempt+1}/{max_retries+1})"
                )
                time.sleep(wait_time)
                self._stats['retries'] += 1
                continue

            # 执行操作
            try:
                result = operation(*args, **kwargs)
                return result
            except Exception as e:
                # Layer 2: 处理限流响应
                if hasattr(e, 'response') and e.response:
                    wait_time = limiter.handle_rate_limit_response(e.response)
                    if wait_time > 0:
                        self._stats['rate_limited'] += 1
                        self._stats['retries'] += 1
                        logger.warning(
                            f"[{platform}] Got 429, waiting {wait_time:.1f}s "
                            f"(attempt {attempt+1}/{max_retries+1})"
                        )
                        time.sleep(wait_time)
                        continue

                # 非限流错误，直接抛出
                raise

        raise Exception(
            f"[{platform}] Failed after {max_retries} retries, "
            f"last wait: {last_wait_time:.1f}s"
        )

    def get_stats(self) -> Dict:
        """获取限流统计"""
        total = self._stats['total_requests']
        if total == 0:
            return dict(self._stats, hit_rate=0.0, retry_rate=0.0)
        return {
            **self._stats,
            'hit_rate': self._stats['rate_limited'] / total,
            'retry_rate': self._stats['retries'] / total,
        }
```

---

## 五、生产环境监控

### 5.1 关键监控指标

```
限流监控指标：

实时指标 (每秒):
├── 各平台请求速率 (req/sec)
├── 各平台限流率 (%) = 限流次数 / 总请求数
├── 各平台平均等待时间 (ms)
└── 熔断器状态 (Closed/Open/Half-Open)

累计指标 (每日):
├── 总请求数 / 限流次数 / 重试次数
├── 限流率趋势 (小时级)
├── 熔断触发次数
└── 各 API 端点的限流分布

告警阈值：
├── 限流率 > 5% → 警告（需要扩大批量间隔）
├── 限流率 > 10% → 严重（需要重新设计批次大小）
├── 熔断触发 > 3次/小时 → 检查平台健康状态
└── 平均等待时间 > 5s → 限流过于频繁，需要优化
```

### 5.2 告警配置

```yaml
# prometheus alert rules
groups:
  - name: ad_platform_ratelimit
    rules:
      - alert: HighRateLimitRate
        expr: rate(ad_platform_ratelimit_hits_total[5m]) / rate(ad_platform_requests_total[5m]) > 0.05
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "广告平台限流率过高: {{ $labels.platform }}"

      - alert: CircuitBreakerTripped
        expr: ad_platform_circuit_breaker_state == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "广告平台熔断器触发: {{ $labels.platform }}"

      - alert: HighRetryRate
        expr: rate(ad_platform_ratelimit_retries_total[5m]) / rate(ad_platform_requests_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "广告平台重试率过高: {{ $labels.platform }}"
```

---

## 六、自测题

### Q1: 为什么指数退避要加抖动(Jitter)？

<details>
<summary>点击查看答案</summary>

**问题**: 如果没有抖动，多个客户端同时被限流后，会在同一时刻同时重试，导致"雷鸣群效应"(thundering herd)，再次触发限流。

**解决方案**: 添加随机抖动，使每个客户端的重试时间分散：
- 基础退避: 1s, 2s, 4s, 8s, 16s
- 加抖动后: 1.3s, 2.7s, 3.8s, 8.2s, 15.1s

这样重试时间分散，避免再次集中触发限流。

公式: `delay = base_delay * (2 ^ attempt) * (1 + random(0, 0.5))`
</details>

### Q2: 如何处理 TikTok 的 X-RateLimit-Remaining = 0 但还没收到 429 的情况？

<details>
<summary>点击查看答案</summary>

这是"预测性限流"场景。TikTok 会在 headers 中提供:
- X-RateLimit-Limit: 总限制
- X-RateLimit-Remaining: 剩余次数
- X-RateLimit-Reset: 重置时间

最佳实践：
1. 当 Remaining ≤ 5 时，开始减速（提前降速）
2. 当 Remaining = 0 时，停止发送请求，等待 Reset
3. 在 Reset 时间前 1-2 秒恢复发送

代码示例：
```python
remaining = int(response.headers.get('X-RateLimit-Remaining', 100))
if remaining <= 5:
    # 提前减速：增加请求间隔
    time.sleep(base_interval * (6 - remaining))
elif remaining == 0:
    # 完全停止，等待重置
    reset_ts = int(response.headers.get('X-RateLimit-Reset', 0))
    wait = max(0, reset_ts - int(time.time())) + 2
    time.sleep(wait)
```
</details>

---

*本文档提供了四大广告平台限流处理的完整生产级方案，建议结合实际业务场景调整参数。*
