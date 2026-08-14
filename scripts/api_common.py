# -*- coding: utf-8 -*-
"""
广告平台 API 公共模块
包含 ApiResponse 数据类和 BaseAdPlatformClient 基类
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import requests


@dataclass
class ApiResponse:
    """API 响应封装"""
    success: bool
    data: Any = None
    error: str = ""
    rate_limit: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'rate_limit': self.rate_limit
        }


class BaseAdPlatformClient:
    """基础广告平台客户端"""
    
    def __init__(self, credentials: dict, platform: str):
        self.credentials = credentials
        self.platform = platform
        self.base_url = ""
        self.token = None
        self.token_expiry = 0
        
    def get_token(self) -> str:
        """获取访问令牌"""
        raise NotImplementedError
        
    def request(self, method: str, endpoint: str, **kwargs) -> ApiResponse:
        """发送 API 请求"""
        raise NotImplementedError
