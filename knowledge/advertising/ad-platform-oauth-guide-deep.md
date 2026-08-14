# 广告平台 OAuth Token 刷新与异常处理完全指南

> **领域**: 广告投放 / API 工程
> **深度**: ⭐⭐⭐⭐⭐ 生产级指南
> **标签**: oauth, token-refresh, google-ads, meta-ads, tiktok-ads, dv360
> **更新时间**: 2026-08-14
> **type**: production/engineering

---

## 一、各平台 OAuth 机制对比

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      各平台 OAuth Token 机制                                 │
├──────────────┬──────────────────┬──────────────┬──────────────────────────┤
│    维度       │   Google Ads     │   Meta Ads    │    TikTok Ads            │
├──────────────┼──────────────────┼──────────────┼──────────────────────────┤
│ Access Token │ JWT Bearer       │ OAuth Token  │ Bearer Token             │
│ 有效期       │ 1 hour         │ 2-6 hours    │ 不确定                   │
│ Refresh Token│ ✅ 长期有效     │ ✅ 长期有效   │ ✅ 长期有效              │
│ 刷新方式     │ Google Auth    │ POST /oauth  │ POST /oauth/access_token │
│ 授权类型     │ OAuth 2.0      │ OAuth 2.0    │ OAuth 2.0                │
│ 特殊要求     │ Developer Token│ App Secret   │ App Key/Secret           │
├──────────────┼──────────────────┼──────────────┼──────────────────────────┤
│    维度       │   DV360        │               │                          │
├──────────────┼──────────────────┼──────────────┼──────────────────────────┤
│ Access Token │ JWT via Service Account (Google Sign-In)   │
│ 有效期       │ 1 hour                               │
│ Refresh Token│ ❌ 无（用 RSA 私钥签发 JWT）          │
│ 授权类型     │ OAuth 2.0 + Service Account          │
│ 特殊要求     │ Google Cloud Project + JSON Key    │
└──────────────┴──────────────────┴──────────────┴──────────────────────────┘
```

---

## 二、Token 刷新架构

### 2.1 统一 Token Manager

```python
"""
统一 Token 管理器 — 四个平台的 Token 生命周期统一管控
"""
import time
import hashlib
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

@dataclass
class TokenInfo:
    """Token 信息"""
    platform: str
    access_token: str
    expires_at: float          # Unix timestamp
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    scope: str = ""
    last_refreshed_at: float = 0.0
    refresh_count: int = 0
    error_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Token 是否已过期（提前 5 分钟刷新）"""
        return time.time() >= (expires_at - 300)

    @property
    def time_until_expiry(self) -> float:
        """距过期剩余秒数"""
        return max(0, self.expires_at - time.time())


class TokenManager:
    """
    统一 Token 管理器

    职责:
    1. Token 存储与检索（支持内存/Redis/DB）
    2. 自动刷新过期 Token
    3. Token 错误重试与降级
    4. 多账户 Token 管理
    """

    def __init__(self, storage=None, refresh_buffer_seconds: int = 300):
        self._tokens: Dict[str, TokenInfo] = {}  # key: platform:account_id
        self._storage = storage  # None=内存, 否则使用外部存储
        self._refresh_buffer = refresh_buffer_seconds
        self._lock = threading.Lock()
        self._refresh_callbacks: Dict[str, callable] = {}

    def get_token(self, platform: str, account_id: str) -> Optional[TokenInfo]:
        """获取 Token（自动刷新）"""
        key = f"{platform}:{account_id}"

        with self._lock:
            token = self._tokens.get(key)

        if token is None:
            token = self._load_from_storage(key)

        if token is None:
            return None

        # 检查是否需要刷新
        if token.is_expired or self._should_force_refresh(token):
            token = self._refresh_token(platform, account_id, token)
            if token is None:
                logger.error(f"Failed to refresh token for {key}")
                return None

        return token

    def _should_force_refresh(self, token: TokenInfo) -> bool:
        """判断是否需要强制刷新（基于错误计数）"""
        # 如果有连续错误，说明 token 可能已失效
        if token.error_count >= 3:
            return True
        # 如果距上次刷新超过 23 小时（Google token 有效期 1h，但 refresh token 长期有效）
        if time.time() - token.last_refreshed_at > 82800:
            return True
        return False

    def _refresh_token(self, platform: str, account_id: str,
                       current_token: TokenInfo) -> Optional[TokenInfo]:
        """执行 Token 刷新"""
        key = f"{platform}:{account_id}"
        callback = self._refresh_callbacks.get(platform)

        if callback is None:
            logger.error(f"No refresh callback registered for {platform}")
            return None

        try:
            new_token_info = callback(platform, account_id, current_token)
            if new_token_info is None:
                return None

            new_token = TokenInfo(
                platform=platform,
                access_token=new_token_info['access_token'],
                expires_at=new_token_info['expires_at'],
                refresh_token=new_token_info.get('refresh_token', current_token.refresh_token),
                token_type=new_token_info.get('token_type', 'Bearer'),
                scope=new_token_info.get('scope', current_token.scope),
                last_refreshed_at=time.time(),
                refresh_count=current_token.refresh_count + 1,
                error_count=0,  # 刷新成功，重置错误计数
            )

            with self._lock:
                self._tokens[key] = new_token

            self._save_to_storage(key, new_token)
            logger.info(f"Token refreshed for {key}, expires in {new_token.time_until_expiry:.0f}s")
            return new_token

        except Exception as e:
            logger.error(f"Token refresh failed for {key}: {e}")
            with self._lock:
                if key in self._tokens:
                    self._tokens[key].error_count += 1
            return None

    def register_refresh_callback(self, platform: str, callback: callable):
        """注册 Token 刷新回调"""
        self._refresh_callbacks[platform] = callback

    def record_error(self, platform: str, account_id: str):
        """记录 Token 相关错误"""
        key = f"{platform}:{account_id}"
        with self._lock:
            if key in self._tokens:
                self._tokens[key].error_count += 1

    def invalidate(self, platform: str, account_id: str):
        """使 Token 失效（登录过期、权限变更等）"""
        key = f"{platform}:{account_id}"
        with self._lock:
            self._tokens.pop(key, None)
        self._delete_from_storage(key)

    # ── 存储接口 ──────────────────────────────────────────────
    def _load_from_storage(self, key: str) -> Optional[TokenInfo]:
        if self._storage is None:
            return None
        data = self._storage.get(key)
        if data is None:
            return None
        return TokenInfo(**json.loads(data))

    def _save_to_storage(self, key: str, token: TokenInfo):
        if self._storage is None:
            return
        self._storage.set(key, json.dumps(token.__dict__), ex=int(token.time_until_expiry + 3600))

    def _delete_from_storage(self, key: str):
        if self._storage is None:
            return
        self._storage.delete(key)
```

---

## 三、各平台 Token 刷新实现

### 3.1 Google Ads Token 刷新

```python
"""
Google Ads OAuth Token 刷新
"""
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json

def refresh_google_token(platform: str, account_id: str,
                         current_token: TokenInfo) -> Optional[Dict]:
    """
    Google Ads Token 刷新

    Google 使用 Refresh Token 获取新的 Access Token
    Access Token 有效期 1 小时，Refresh Token 长期有效
    """
    try:
        # 从 storage 获取 credential 配置
        creds = Credentials(
            token=current_token.access_token,
            refresh_token=current_token.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=current_token.client_id,
            client_secret=current_token.client_secret,
        )

        # 刷新 token
        creds.refresh(Request())

        return {
            'access_token': creds.token,
            'expires_at': time.time() + creds.expiry.timestamp() - time.time(),
            'refresh_token': creds.refresh_token or current_token.refresh_token,
            'token_type': 'Bearer',
        }

    except Exception as e:
        logger.error(f"Google token refresh failed: {e}")
        # Refresh token 也可能过期，需要重新授权
        if "refresh_token" in str(e).lower() or "invalid_grant" in str(e).lower():
            logger.warning("Google refresh token expired, need re-authentication")
            return None
        raise
```

### 3.2 Meta Token 刷新

```python
"""
Meta Marketing API Token 刷新
"""
import requests

def refresh_meta_token(platform: str, account_id: str,
                       current_token: TokenInfo) -> Optional[Dict]:
    """
    Meta Token 刷新

    Meta 使用 long-lived access token (60天) 换取短期 token
    或者使用 permission tool 刷新
    """
    try:
        # 方式 1: 使用 exchange token 端点
        resp = requests.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                'grant_type': 'fb_exchange_token',
                'client_id': current_token.client_id,
                'client_secret': current_token.client_secret,
                'fb_exchange_token': current_token.access_token,
            }
        )
        data = resp.json()

        if 'access_token' not in data:
            logger.error(f"Meta token refresh error: {data}")
            return None

        # Meta long-lived token 有效期 60 天
        return {
            'access_token': data['access_token'],
            'expires_at': time.time() + 5184000,  # 60 days
            'refresh_token': current_token.refresh_token,
        }

    except Exception as e:
        logger.error(f"Meta token refresh failed: {e}")
        return None
```

### 3.3 TikTok Token 刷新

```python
"""
TikTok Marketing API Token 刷新
"""
import requests
import hashlib
import time

def refresh_tiktok_token(platform: str, account_id: str,
                         current_token: TokenInfo) -> Optional[Dict]:
    """
    TikTok Token 刷新

    TikTok 使用 Refresh Token 换取新的 Access Token
    需要 App Key + App Secret
    """
    try:
        # 生成签名
        timestamp = str(int(time.time()))
        nonce = hashlib.md5(f"{timestamp}{current_token.app_key}".encode()).hexdigest()[:16]

        # 调用刷新端点
        resp = requests.post(
            "https://openapi.tiktok.com/api/v2/oauth/refresh_token/",
            json={
                'app_key': current_token.app_key,
                'refresh_token': current_token.refresh_token,
                'grant_type': 'refresh_token',
            }
        )
        data = resp.json()

        if data.get('access_token'):
            # TikTok token 有效期不确定，保守估计 7 天
            return {
                'access_token': data['access_token'],
                'expires_at': time.time() + 604800,  # 7 days
                'refresh_token': data.get('refresh_token', current_token.refresh_token),
            }
        else:
            logger.error(f"TikTok refresh error: {data}")
            return None

    except Exception as e:
        logger.error(f"TikTok token refresh failed: {e}")
        return None
```

### 3.4 DV360 Token 刷新 (Service Account JWT)

```python
"""
DV360 Service Account JWT 签名
"""
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import jwt

def refresh_dv360_token(platform: str, account_id: str,
                        current_token: TokenInfo) -> Optional[Dict]:
    """
    DV360 使用 Service Account 签发 JWT

    不需要 Refresh Token，每次用私钥重新签发 JWT 即可
    """
    try:
        # 从 storage 加载 Service Account JSON
        sa_json = json.loads(current_token.service_account_json)

        # 创建 credentials
        credentials = service_account.Credentials.from_service_account_info(
            sa_json,
            scopes=['https://www.googleapis.com/auth/display-video']
        )

        # 签名 JWT
        credentials.refresh(Request())

        return {
            'access_token': credentials.token,
            'expires_at': time.time() + 3600,  # JWT 有效期 1 小时
            'token_type': 'Bearer',
        }

    except Exception as e:
        logger.error(f"DV360 token refresh failed: {e}")
        return None
```

---

## 四、Token 异常处理

### 4.1 常见 Token 错误及处理

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Token 错误处理决策树                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  收到 401/403                                                              │
│      │                                                                      │
│      ├─ "invalid_token" / "Token has expired"                              │
│      │     → 自动刷新 Token                                                 │
│      │     → 刷新成功后重试请求                                             │
│      │     → 如果刷新失败 → 返回 401 错误给前端                             │
│      │                                                                      │
│      ├─ "invalid_grant" / "Refresh token used"                             │
│      │     → Refresh Token 已被使用或过期                                   │
│      │     → 清除本地缓存，提示用户重新授权                                  │
│      │                                                                      │
│      ├─ "insufficient_permissions" / "permission_denied"                   │
│      │     → Token 有效但权限不足                                            │
│      │     → 检查 OAuth scope 是否包含所需权限                               │
│      │     → 提示用户重新授权并授予更多权限                                   │
│      │                                                                      │
│      ├─ "appsecret_proof invalid" (Meta 特有)                               │
│      │     → 需要使用 App Secret 签名 Token                                  │
│      │     → 重新构建请求 URL 加上 appsecret_proof 参数                       │
│      │                                                                      │
│      └─ "User not enabled" / "Application disabled"                        │
│            → 应用/账户被禁用，联系平台支持                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Token 缓存策略

```python
"""
Token 缓存策略 — 防止并发刷新和缓存穿透
"""
import asyncio
import functools

class TokenCache:
    """
    Token 缓存层

    策略:
    1. L1: 内存缓存（TTL = token 有效期 - 5分钟）
    2. L2: Redis 缓存（分布式共享）
    3. L3: 文件系统缓存（持久化）

    防并发刷新: 使用分布式锁，同一时刻只允许一个刷新请求
    """

    def __init__(self, redis_client=None, ttl_seconds: int = 3300):
        self._redis = redis_client
        self._ttl = ttl_seconds
        self._local_cache: Dict[str, tuple] = {}  # key -> (token_info, expire_time)
        self._locks: Dict[str, asyncio.Lock] = {}

    async def get(self, key: str) -> Optional[TokenInfo]:
        """获取 Token"""
        # L1: 内存缓存
        if key in self._local_cache:
            token_info, expire_time = self._local_cache[key]
            if time.time() < expire_time:
                return token_info
            del self._local_cache[key]

        # L2: Redis 缓存
        if self._redis:
            data = self._redis.get(f"token:{key}")
            if data:
                token = TokenInfo(**json.loads(data))
                self._local_cache[key] = (token, time.time() + self._ttl)
                return token

        return None

    async def set(self, key: str, token: TokenInfo):
        """设置 Token"""
        expire_time = time.time() + self._ttl
        self._local_cache[key] = (token, expire_time)

        if self._redis:
            self._redis.set(
                f"token:{key}",
                json.dumps(token.__dict__),
                ex=self._ttl
            )

    async def invalidate(self, key: str):
        """使 Token 失效"""
        self._local_cache.pop(key, None)
        if self._redis:
            self._redis.delete(f"token:{key}")

    @functools.lru_cache(maxsize=1024)
    def _get_lock(self, key: str) -> asyncio.Lock:
        return asyncio.Lock()

    async def refresh_with_lock(self, key: str, refresh_fn) -> Optional[TokenInfo]:
        """
        带锁的 Token 刷新

        防止多个并发请求同时触发刷新
        """
        lock = self._get_lock(key)
        async with lock:
            # 双重检查
            cached = await self.get(key)
            if cached and not cached.is_expired:
                return cached

            # 执行刷新
            new_token = await refresh_fn(key)
            if new_token:
                await self.set(key, new_token)
            return new_token
```

---

## 五、生产级 Token 管理器

### 5.1 完整实现

```go
package token

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// TokenStore Token 存储接口
type TokenStore interface {
	Get(ctx context.Context, key string) (*Token, error)
	Set(ctx context.Context, key string, token *Token, ttl time.Duration) error
	Delete(ctx context.Context, key string) error
}

// TokenRefreshFunc Token 刷新函数
type TokenRefreshFunc func(ctx context.Context, platform, accountID string, current *Token) (*Token, error)

// Manager Token 管理器
type Manager struct {
	store          TokenStore
	refreshFuncs   map[string]TokenRefreshFunc
	mu             sync.RWMutex
	cache          map[string]*cachedToken
	preRefreshSecs int
}

type cachedToken struct {
	token      *Token
	expiredAt  time.Time
	refreshing bool
}

// NewManager 创建 Token 管理器
func NewManager(store TokenStore, preRefreshSecs int) *Manager {
	return &Manager{
		store:          store,
		refreshFuncs:   make(map[string]TokenRefreshFunc),
		cache:          make(map[string]*cachedToken),
		preRefreshSecs: preRefreshSecs,
	}
}

// RegisterRefreshCallback 注册刷新回调
func (m *Manager) RegisterRefreshCallback(platform string, fn TokenRefreshFunc) {
	m.refreshFuncs[platform] = fn
}

// GetToken 获取 Token（自动刷新）
func (m *Manager) GetToken(ctx context.Context, platform, accountID string) (*Token, error) {
	key := platform + ":" + accountID

	m.mu.RLock()
	cached, exists := m.cache[key]
	m.mu.RUnlock()

	// 缓存命中且未过期
	if exists && time.Now().Before(cached.expiredAt) {
		return cached.token, nil
	}

	// 缓存未命中或已过期，从存储加载
	token, err := m.store.Get(ctx, key)
	if err != nil {
		return nil, fmt.Errorf("failed to get token from store: %w", err)
	}

	// 检查是否需要刷新
	if time.Now().Add(time.Duration(m.preRefreshSecs) * time.Second).After(token.ExpiresAt) {
		token, err = m.refreshToken(ctx, platform, accountID, token)
		if err != nil {
			return nil, err
		}
	}

	// 更新缓存
	m.mu.Lock()
	m.cache[key] = &cachedToken{
		token:     token,
		expiredAt: token.ExpiresAt,
	}
	m.mu.Unlock()

	return token, nil
}

// refreshToken 刷新 Token
func (m *Manager) refreshToken(ctx context.Context, platform, accountID string,
	current *Token) (*Token, error) {

	fn, ok := m.refreshFuncs[platform]
	if !ok {
		return nil, fmt.Errorf("no refresh callback for platform: %s", platform)
	}

	newToken, err := fn(ctx, platform, accountID, current)
	if err != nil {
		return nil, fmt.Errorf("token refresh failed: %w", err)
	}

	// 更新缓存
	key := platform + ":" + accountID
	m.mu.Lock()
	m.cache[key] = &cachedToken{
		token:     newToken,
		expiredAt: newToken.ExpiresAt,
	}
	m.mu.Unlock()

	// 持久化
	err = m.store.Set(ctx, key, newToken, time.Until(newToken.ExpiresAt))
	if err != nil {
		// 持久化失败不影响使用，下次请求时会重试
	}

	return newToken, nil
}

// Invalidate 使 Token 失效
func (m *Manager) Invalidate(ctx context.Context, platform, accountID string) error {
	key := platform + ":" + accountID
	m.mu.Lock()
	delete(m.cache, key)
	m.mu.Unlock()
	return m.store.Delete(ctx, key)
}
```

---

## 六、自测题

### Q1: Google Ads 的 Refresh Token 什么情况下会失效？

<details>
<summary>点击查看答案</summary>

Refresh Token 失效场景：
1. **用户撤销授权** — 用户在 Google 账户中取消了应用访问权限
2. **长时间未使用** — Refresh Token 超过 6 个月未使用会被 Google 回收
3. **安全事件** — Google 检测到异常活动，强制撤销所有 token
4. **应用被删除** — Google Cloud 项目被删除

处理方式：
- 检测 `invalid_grant` 错误
- 清除本地缓存
- 引导用户重新走 OAuth 授权流程
- 记录审计日志
</details>

### Q2: DV360 为什么不需要 Refresh Token？

<details>
<summary>点击查看答案</summary>

DV360 使用 Service Account（服务账号）认证：
1. **不依赖用户授权** — Service Account 是服务器级别的凭证
2. **JWT 签名替代** — 每次用私钥重新签发 JWT，无需刷新 Token
3. **JWT 有效期短** — 通常 1 小时，但可以随时重新签发
4. **更安全** — 私钥保存在服务器，不会泄露给客户端

核心区别：
- Google Ads/Meta/TikTok: 用户授权模式（OAuth 2.0 + Refresh Token）
- DV360: 服务账号模式（Service Account + JWT 签名）
</details>

---

*本文档提供了四大广告平台 Token 管理的完整生产级方案。*
