"""
api_clients/base.py - 生产级 API 客户端基类

核心能力：
1. 自动重试（指数退避 + 可配置策略）
2. 速率限制检测（429 自动等待）
3. 统一错误分类（APIError / AuthError / RateLimitError）
4. 请求/响应日志
"""

import time
import requests
import logging
import hashlib
import copy
import random
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)


# ─── 错误分类 ───────────────────────────────────────────────────

class APIError(Exception):
    """API 调用失败"""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthError(APIError):
    """认证失败（token 过期 / 无效）"""
    pass


class RateLimitError(APIError):
    """触发速率限制"""
    def __init__(self, message: str, retry_after: float = 60.0):
        super().__init__(message)
        self.retry_after = retry_after


class TemporaryError(APIError):
    """临时性错误（5xx / 网络超时）- 应该重试"""
    pass


# ─── 重试配置 ───────────────────────────────────────────────────

@dataclass
class RetryConfig:
    """重试策略配置"""
    max_retries: int = 3                    # 最大重试次数
    base_delay: float = 1.0                 # 基础延迟（秒）
    max_delay: float = 60.0                 # 最大延迟（秒）
    exponential_base: float = 2.0           # 指数退避基数
    jitter: bool = True                     # 是否添加随机抖动
    retryable_status_codes: tuple = (429, 500, 502, 503, 504)
    retryable_errors: tuple = (TemporaryError, RateLimitError)
    
    def get_delay(self, attempt: int) -> float:
        """计算第 N 次重试的延迟时间"""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        if self.jitter:
            # 添加 0~50% 随机抖动，避免雪崩
            delay = delay * random.uniform(0.5, 1.0)
        return delay


# ─── 限流器 ─────────────────────────────────────────────────────

class RateLimiter:
    """
    令牌桶限流器（简化版）。
    
    用于控制对平台 API 的调用频率，避免触发速率限制。
    """
    
    def __init__(self, max_requests: int, period: float):
        """
        Args:
            max_requests: 周期内最大请求数
            period: 周期（秒）
        """
        self.max_requests = max_requests
        self.period = period
        self._timestamps: list[float] = []
        self._lock = threading.RLock()
    
    def acquire(self, max_wait: Optional[float] = None) -> None:
        """获取令牌，如果超出限制则阻塞等待。

        ``max_wait`` lets a Runtime request deadline bound the limiter wait;
        otherwise a saturated limiter could outlive the tool timeout before
        the HTTP request even started.
        """
        # A client is shared by multiple Runtime sessions.  Protect the
        # timestamp window so concurrent requests cannot oversubscribe it.
        with self._lock:
            now = time.time()
            self._timestamps = [t for t in self._timestamps if now - t < self.period]

            if len(self._timestamps) >= self.max_requests:
                wait_time = self.period - (now - self._timestamps[0])
                if wait_time > 0:
                    if max_wait is not None and wait_time > max_wait:
                        raise TemporaryError("Provider request deadline exceeded while rate limited")
                    logger.debug(f"Rate limiter: waiting {wait_time:.2f}s")
                    time.sleep(wait_time)
                    now = time.time()
                    self._timestamps = [
                        t for t in self._timestamps if now - t < self.period
                    ]
            self._timestamps.append(time.time())


# ─── 基类 ────────────────────────────────────────────────────────

class BasePlatformClient(ABC):
    """
    广告平台 API 客户端基类。
    
    子类只需实现：
    1. _do_request() - 发送实际 HTTP 请求
    2. _extract_data() - 从响应中提取数据
    3. _handle_error() - 处理 API 错误
    
    基类提供：
    - 自动重试（指数退避）
    - 限流保护
    - 统一错误分类
    - 请求日志
    """
    
    def __init__(
        self,
        credentials: dict,
        platform: str,
        retry_config: Optional[RetryConfig] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        # Keep an internal snapshot.  Client-side token refresh and endpoint
        # normalization must never mutate the caller-owned credential object.
        # This is especially important when one runtime shares a credential
        # configuration across multiple platform clients.
        self.credentials = copy.deepcopy(credentials or {})
        self.platform = platform
        self.retry_config = retry_config or RetryConfig()
        self.rate_limiter = rate_limiter
        self._session_cache: dict[str, Any] = {}  # 请求级缓存
        self.request_timeout = 30.0
        self.request_deadline: Optional[float] = None

    def set_request_timeout(self, timeout_seconds: float) -> None:
        """Set the upper bound used by provider HTTP calls for one tool turn."""
        timeout = float(timeout_seconds)
        if timeout <= 0:
            raise ValueError("request timeout must be positive")
        self.request_timeout = timeout

    def set_request_budget(self, timeout_seconds: float) -> None:
        """Bound both each HTTP attempt and the complete retry sequence."""
        self.set_request_timeout(timeout_seconds)
        self.request_deadline = time.monotonic() + float(timeout_seconds)

    def http_timeout(self, requested: Optional[float] = None) -> float:
        """Return a bounded connect/read timeout for adapter implementations."""
        timeout = self.request_timeout
        if requested is not None:
            timeout = min(timeout, float(requested))
        if self.request_deadline is not None:
            timeout = min(timeout, self.request_deadline - time.monotonic())
        return max(float(timeout), 0.001)

    def remaining_request_budget(self) -> Optional[float]:
        if self.request_deadline is None:
            return None
        return self.request_deadline - time.monotonic()

    def acquire_rate_limit(self, limiter: Optional[RateLimiter] = None) -> None:
        """Acquire a provider limiter without exceeding the request budget.

        Some providers have account-scoped limiters in addition to the base
        client limiter. Keeping this helper on the base client makes both
        kinds of limiter obey the same Runtime deadline contract.
        """
        limiter = limiter or self.rate_limiter
        if limiter is None:
            return
        remaining = self.remaining_request_budget()
        if remaining is not None and remaining <= 0:
            raise TemporaryError("Provider request deadline exceeded while rate limited")
        limiter.acquire(max_wait=remaining)
        remaining = self.remaining_request_budget()
        if remaining is not None and remaining <= 0:
            raise TemporaryError("Provider request deadline exceeded while rate limited")

    def sleep_with_budget(self, seconds: float) -> None:
        """Sleep for polling/backoff only while the request budget remains."""
        duration = max(float(seconds), 0.0)
        remaining = self.remaining_request_budget()
        if remaining is not None:
            if remaining <= 0:
                raise TemporaryError("Provider request deadline exceeded while waiting")
            if duration > remaining:
                time.sleep(remaining)
                raise TemporaryError("Provider request deadline exceeded while waiting")
        time.sleep(duration)
        
    @abstractmethod
    def _do_request(self, method: str, url: str, **kwargs) -> dict:
        """发送 HTTP 请求，返回原始响应数据"""
        pass
    
    @abstractmethod
    def _extract_data(self, response: dict) -> Any:
        """从响应中提取业务数据"""
        pass
    
    @abstractmethod
    def _handle_error(self, response: dict, status_code: int) -> Optional[APIError]:
        """解析错误响应，返回对应异常（None 表示无错误）"""
        pass
    
    def request(
        self,
        method: str,
        endpoint: str,
        retry_count: int = 0,
        retry_non_idempotent: bool = False,
        **kwargs
    ) -> Any:
        """
        带重试的请求入口。
        
        逻辑：
        1. 检查限流器
        2. 发送请求
        3. 检查错误（认证/限流/临时）
        4. 根据错误类型决定是否重试
        """
        response = self.request_raw(
            method,
            endpoint,
            retry_count=retry_count,
            retry_non_idempotent=retry_non_idempotent,
            **kwargs,
        )
        return self._extract_data(response)

    def request_raw(
        self,
        method: str,
        endpoint: str,
        retry_count: int = 0,
        retry_non_idempotent: bool = False,
        **kwargs,
    ) -> dict:
        """Execute a request and return the transport envelope.

        Some provider APIs expose response-specific envelopes (for example
        TikTok's ``code/message/data`` or Google REST's ``results``).  Those
        adapters need the raw HTTP status and body to normalize the response,
        but they must still receive the same retry and error handling as the
        high-level ``request`` method.  Provider code should use this method
        instead of calling ``_do_request`` directly.
        """
        if self.rate_limiter:
            remaining = self.remaining_request_budget()
            if remaining is not None and remaining <= 0:
                raise TemporaryError("Provider request deadline exceeded")
            self.rate_limiter.acquire(max_wait=remaining)

        try:
            if self.request_deadline is not None and self.request_deadline <= time.monotonic():
                raise TemporaryError("Provider request deadline exceeded")
            url = self._build_url(endpoint)
            logger.debug(f"[{self.platform}] {method} {endpoint}")
            response = self._do_request(method, url, **kwargs)
            status_code = response.get("status_code", 200)
            error = self._handle_error(response, status_code)
            if error:
                # A provider 401 is recoverable only when this client has a
                # caller-supplied refresh path.  Retry GET-like requests once
                # after clearing the cached token; never replay a POST/PUT/
                # PATCH/DELETE merely because authentication failed.
                if (
                    status_code == 401
                    and retry_count == 0
                    and method.upper() in {"GET", "HEAD", "OPTIONS"}
                    and self._reset_auth()
                ):
                    return self.request_raw(
                        method,
                        endpoint,
                        retry_count=retry_count + 1,
                        retry_non_idempotent=retry_non_idempotent,
                        **kwargs,
                    )
                return self._on_error_raw(
                    error,
                    method,
                    endpoint,
                    retry_count,
                    kwargs,
                    retry_non_idempotent=retry_non_idempotent,
                )
            return response
        except requests.exceptions.Timeout as e:
            return self._on_error_raw(
                TemporaryError(f"Timeout: {e}"),
                method,
                endpoint,
                retry_count,
                kwargs,
                retry_non_idempotent=retry_non_idempotent,
            )
        except requests.exceptions.ConnectionError as e:
            return self._on_error_raw(
                TemporaryError(f"Connection error: {e}"),
                method,
                endpoint,
                retry_count,
                kwargs,
                retry_non_idempotent=retry_non_idempotent,
            )

    def _reset_auth(self) -> bool:
        """Clear auth state and report whether a refresh retry is possible."""
        return False
    
    def _on_error(
        self,
        error: APIError,
        method: str,
        endpoint: str,
        retry_count: int,
        kwargs: dict,
    ) -> Any:
        """
        错误处理：判断是否重试。
        
        - AuthError: 不重试，直接抛出（需要刷新 token）
        - RateLimitError: 等待后重试
        - TemporaryError: 指数退避重试
        - 其他: 不重试
        """
        logger.warning(
            f"[{self.platform}] Error on {method} {endpoint}: {error} "
            f"(retry={retry_count}/{self.retry_config.max_retries})"
        )
        
        # 认证错误不重试
        if isinstance(error, AuthError):
            raise error
        
        # 重试判断
        should_retry = (
            retry_count < self.retry_config.max_retries
            and isinstance(error, self.retry_config.retryable_errors)
        )
        
        if should_retry:
            delay = self.retry_config.get_delay(retry_count)
            logger.info(f"[{self.platform}] Retrying in {delay:.2f}s...")
            time.sleep(delay)
            return self.request(method, endpoint, retry_count + 1, **kwargs)
        
        raise error

    def _on_error_raw(
        self,
        error: APIError,
        method: str,
        endpoint: str,
        retry_count: int,
        kwargs: dict,
        retry_non_idempotent: bool = False,
    ) -> dict:
        """Raw-envelope counterpart of :meth:`_on_error`."""
        logger.warning(
            f"[{self.platform}] Error on {method} {endpoint}: {error} "
            f"(retry={retry_count}/{self.retry_config.max_retries})"
        )
        if isinstance(error, AuthError):
            raise error

        should_retry = (
            retry_count < self.retry_config.max_retries
            and isinstance(error, self.retry_config.retryable_errors)
            and (
                method.upper() in {"GET", "HEAD", "OPTIONS"}
                or retry_non_idempotent
            )
        )
        if should_retry:
            delay = error.retry_after if isinstance(error, RateLimitError) else self.retry_config.get_delay(retry_count)
            delay = min(max(float(delay), 0.0), self.retry_config.max_delay)
            remaining = self.remaining_request_budget()
            if remaining is not None:
                if remaining <= 0:
                    raise TemporaryError("Provider request deadline exceeded")
                delay = min(delay, remaining)
            logger.info(f"[{self.platform}] Retrying in {delay:.2f}s...")
            time.sleep(delay)
            return self.request_raw(
                method,
                endpoint,
                retry_count + 1,
                retry_non_idempotent=retry_non_idempotent,
                **kwargs,
            )
        raise error
    
    def _build_url(self, endpoint: str) -> str:
        """子类覆盖：构建完整 URL"""
        return endpoint
    
    def invalidate_cache(self, key_pattern: str = None) -> None:
        """清除请求缓存"""
        if key_pattern:
            self._session_cache = {
                k: v for k, v in self._session_cache.items()
                if key_pattern not in k
            }
        else:
            self._session_cache.clear()


# ─── 装饰器工具 ──────────────────────────────────────────────────

def with_retry(retry_config: Optional[RetryConfig] = None):
    """
    重试装饰器（用于方法级别的细粒度重试）。
    
    用法：
        @with_retry(RetryConfig(max_retries=5))
        def fetch_campaigns(self, campaign_id):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            config = retry_config or getattr(self, 'retry_config', RetryConfig())
            last_error = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(self, *args, **kwargs)
                except config.retryable_errors as e:
                    last_error = e
                    if attempt < config.max_retries:
                        delay = config.get_delay(attempt)
                        logger.debug(f"{func.__name__} failed (attempt {attempt+1}): {e}, retrying in {delay:.2f}s")
                        time.sleep(delay)
                    else:
                        raise
            
            raise last_error  # type: ignore
        return wrapper
    return decorator
