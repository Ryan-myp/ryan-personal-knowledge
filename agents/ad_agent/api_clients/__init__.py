"""
ad_agent/api_clients/__init__.py - 生产级广告平台 API 客户端

每个平台客户端继承 BasePlatformClient，提供：
- 自动重试（指数退避）
- 速率限制检测与等待
- 统一的错误分类
- 连接池管理
"""

from .base import BasePlatformClient, APIError, RateLimitError, AuthError, RetryConfig
from .meta_client import MetaAPIClient
from .tiktok_client import TikTokAPIClient
from .google_ads_client import GoogleAdsAPIClient
from .dv360_client import DV360APIClient

__all__ = [
    "BasePlatformClient", "APIError", "RateLimitError", "AuthError", "RetryConfig",
    "MetaAPIClient", "TikTokAPIClient", "GoogleAdsAPIClient", "DV360APIClient",
]
