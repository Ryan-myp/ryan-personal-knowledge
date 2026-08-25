"""
api_clients/meta_client.py - Meta Marketing API 生产级客户端

接入已有 scripts/meta_api.py 的真实 API，补全：
- 自动重试（指数退避）
- 速率限制检测与等待
- 统一错误分类
"""

import logging
from typing import Any, Optional
import requests

from .base import BasePlatformClient, APIError, AuthError, RateLimitError, TemporaryError, RetryConfig, RateLimiter

logger = logging.getLogger(__name__)


class MetaAPIClient(BasePlatformClient):
    """
    Meta Marketing API 客户端 (v19.0)
    
    官方文档: https://developers.facebook.com/docs/marketing-api
    认证: OAuth2 Access Token
    
    速率限制: 
    - App 级: 2000 次/小时
    - 广告账户级: 50 次/10秒
    """
    
    BASE_URL = "https://graph.facebook.com/v19.0"
    
    def __init__(
        self,
        credentials: dict,
        retry_config: Optional[RetryConfig] = None,
    ):
        super().__init__(credentials, "meta", retry_config)
        self.access_token = credentials.get('access_token', '')
        # App 级限流器: 2000次/小时
        self._app_rate_limiter = RateLimiter(max_requests=2000, period=3600)
        # 账户级限流器: 50次/10秒
        self._account_rate_limiters: dict[str, RateLimiter] = {}
    
    def _get_account_limiter(self, account_id: str) -> RateLimiter:
        if account_id not in self._account_rate_limiters:
            self._account_rate_limiters[account_id] = RateLimiter(max_requests=50, period=10)
        return self._account_rate_limiters[account_id]
    
    def _build_url(self, endpoint: str) -> str:
        if endpoint.startswith('http'):
            return endpoint
        return f"{self.BASE_URL}/{endpoint.lstrip('/')}"
    
    def _do_request(self, method: str, url: str, **kwargs) -> dict:
        """发送 HTTP 请求"""
        params = kwargs.get('params', {})
        params['access_token'] = self.access_token
        
        headers = kwargs.get('headers', {})
        
        # 合并 params
        final_params = {**params, **kwargs.get('extra_params', {})}
        
        try:
            if method == 'GET':
                resp = requests.get(url, params=final_params, headers=headers, timeout=30)
            elif method == 'POST':
                resp = requests.post(url, params=final_params, json=kwargs.get('data'), headers=headers, timeout=30)
            elif method == 'DELETE':
                resp = requests.delete(url, params=final_params, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            return {
                'status_code': resp.status_code,
                'data': resp.json() if resp.content else {},
                'headers': dict(resp.headers),
            }
        except requests.exceptions.Timeout:
            return {'status_code': 504, 'data': {}, 'headers': {}}
        except requests.exceptions.ConnectionError:
            return {'status_code': 502, 'data': {}, 'headers': {}}
    
    def _extract_data(self, response: dict) -> Any:
        """从响应中提取数据"""
        data = response.get('data', {})
        
        # 分页处理
        if isinstance(data, dict) and 'paging' in data:
            return {
                'data': data.get('data', []),
                'paging': data.get('paging', {}),
            }
        return data
    
    def _handle_error(self, response: dict, status_code: int) -> Optional[APIError]:
        """解析 Meta API 错误"""
        data = response.get('data', {})
        
        # 认证错误
        if status_code == 401:
            return AuthError("Meta API: Invalid or expired access token")
        
        # 速率限制
        if status_code == 429:
            retry_after = float(response.get('headers', {}).get('X-Marketing-Api-Req-Id', 60))
            return RateLimitError("Meta API: Rate limit exceeded", retry_after=retry_after)
        
        # 业务错误（data 中有 error 字段）
        if isinstance(data, dict) and 'error' in data:
            error = data['error']
            message = error.get('message', 'Unknown error')
            code = error.get('code', 0)
            error_type = error.get('type', 'UnknownError')
            
            # 临时性错误（可重试）
            if code in (4, 17, 32, 80000, 80001, 80002, 80003):
                return TemporaryError(f"Meta API error {code}: {message}")
            
            # 认证相关
            if code in (190, 803, 80004, 80005, 80006, 80007, 80008, 80009, 80010):
                return AuthError(f"Meta API auth error {code}: {message}")
            
            return APIError(f"Meta API error {code}: {message}", status_code=status_code, response=data)
        
        return None
    
    # ==================== 账户管理 ====================
    
    def list_accounts(self, business_id: str = None) -> list:
        """获取广告账户列表"""
        if business_id:
            endpoint = f"{business_id}/accounts"
        else:
            endpoint = "me/accounts"
        
        try:
            result = self.request('GET', endpoint)
            if isinstance(result, dict):
                data = result.get('data', [])
                # 确保返回的是列表而不是生成器/迭代器
                if hasattr(data, '__iter__') and not isinstance(data, (list, dict, str)):
                    return list(data)
                return data
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Failed to list accounts: {e}")
            return []
    
    def get_account(self, account_id: str, fields: list = None) -> dict:
        """获取账户详情"""
        params = {'fields': ','.join(fields) if fields else 'id,name,account_id,status'}
        return self.request('GET', f"/{account_id}", extra_params={'fields': params})
    
    # ==================== Campaign 管理 ====================
    
    def list_campaigns(self, account_id: str, fields: list = None, limit: int = 25) -> dict:
        """获取 Campaign 列表"""
        # 去除可能的 act_ 前缀
        clean_id = account_id.replace('act_', '')
        self._get_account_limiter(clean_id).acquire()
        params = {'fields': ','.join(fields) if fields else 'id,name,status,daily_budget,budget_remaining,objective'}
        result = self.request('GET', f"/act_{clean_id}/campaigns", extra_params={**params, 'limit': limit})
        return result.get('data', []) if isinstance(result, dict) else result
    
    def get_campaign(self, campaign_id: str, fields: list = None) -> dict:
        """获取 Campaign 详情"""
        params = {'fields': ','.join(fields) if fields else 'id,name,status,daily_budget,budget_remaining,objective,adsets,ads'}
        return self.request('GET', f"/{campaign_id}", extra_params=params)
    
    def create_campaign(self, account_id: str, campaign: dict) -> dict:
        """创建 Campaign
        
        Meta Graph API 要求：
        - objective: 必须使用有效值（OUTCOME_SALES, OUTCOME_AWARENESS 等）
        - special_ad_categories: 必须指定（NONE 表示不限制）
        - is_adset_budget_sharing_enabled: 不使用 campaign budget 时必须指定
        """
        self._get_account_limiter(account_id).acquire()
        
        # 验证 objective
        valid_objectives = [
            'APP_INSTALLS', 'PRODUCT_CATALOG_SALES', 'CONVERSIONS', 
            'TRAFFIC', 'LINK_CLICKS', 'OUTCOME_SALES', 
            'OUTCOME_APP_PROMOTION', 'OUTCOME_TRAFFIC',
            'OUTCOME_AWARENESS', 'OUTCOME_LEADS', 'OUTCOME_ENGAGEMENT'
        ]
        objective = campaign.get('objective', 'OUTCOME_SALES')
        if objective not in valid_objectives:
            raise ValueError(f"Invalid objective '{objective}'. Valid values: {valid_objectives}")
        
        data = {
            'name': campaign['name'],
            'objective': objective,
            'special_ad_categories': campaign.get('special_ad_categories', 'NONE'),
            'is_adset_budget_sharing_enabled': 'False',  # 不使用 campaign budget 时必须指定
        }
        if 'status' in campaign:
            data['status'] = campaign['status']
        if 'daily_budget' in campaign:
            data['daily_budget'] = str(int(campaign['daily_budget'] * 100))  # 转为分
        if 'start_time' in campaign:
            data['start_time'] = campaign['start_time']
        if 'end_time' in campaign:
            data['end_time'] = campaign['end_time']
        
        result = self.request('POST', f"/{account_id}/campaigns", data=data)
        return result.get('id', '') if isinstance(result, dict) else ''
    
    def update_campaign(self, campaign_id: str, updates: dict) -> dict:
        """更新 Campaign"""
        data = {k: v for k, v in updates.items() if v is not None}
        if 'daily_budget' in data:
            data['daily_budget'] = str(int(data['daily_budget'] * 100))
        return self.request('POST', f"/{campaign_id}", data=data)
    
    def pause_campaign(self, campaign_id: str) -> dict:
        """暂停 Campaign"""
        return self.update_campaign(campaign_id, {'status': 'PAUSED'})
    
    def resume_campaign(self, campaign_id: str) -> dict:
        """恢复 Campaign"""
        return self.update_campaign(campaign_id, {'status': 'ACTIVE'})
    
    # ==================== Ad Set 管理 ====================
    
    def list_adsets(self, account_id: str, campaign_id: str = None, limit: int = 25) -> list:
        """获取 Ad Set 列表"""
        self._get_account_limiter(account_id).acquire()
        endpoint = f"/{account_id}/adsets"
        params = {'limit': limit}
        if campaign_id:
            params['campaign_id'] = campaign_id
        result = self.request('GET', endpoint, extra_params=params)
        return result.get('data', []) if isinstance(result, dict) else result
    
    def get_adset(self, adset_id: str, fields: list = None) -> dict:
        """获取 Ad Set 详情"""
        params = {'fields': ','.join(fields) if fields else 'id,name,campaign_id,status,daily_budget,bid_amount,targeting'}
        return self.request('GET', f"/{adset_id}", extra_params=params)
    
    def create_adset(self, account_id: str, campaign_id: str, adset: dict) -> str:
        """创建 Ad Set
        
        Meta Graph API 要求：
        - optimization_goal: 必须使用有效值
        - billing_event: 必须指定
        - targeting: 必须指定（即使是空对象）
        - bid_amount: 必须指定
        """
        self._get_account_limiter(account_id).acquire()
        
        # 确保 targeting 是 JSON 字符串
        targeting = adset.get('targeting', {'geo_locations': {'countries': ['US']}})
        if isinstance(targeting, dict):
            targeting = json.dumps(targeting)
        
        data = {
            'name': adset['name'],
            'campaign_id': campaign_id,
            'optimization_goal': adset.get('optimization_goal', 'REACH'),
            'billing_event': adset.get('billing_event', 'IMPRESSIONS'),
            'bidding_strategy': adset.get('bidding_strategy', 'LOWEST_COST_WITHOUT_CAP'),
            'bid_amount': str(adset.get('bid_amount', 100)),
            'daily_budget': str(int(adset.get('daily_budget', 100) * 100)),
            'targeting': targeting,
            'status': adset.get('status', 'PAUSED'),
        }
        result = self.request('POST', f"/{account_id}/adsets", data=data)
        return result.get('id', '') if isinstance(result, dict) else ''
    
    def update_adset(self, adset_id: str, updates: dict) -> dict:
        """更新 Ad Set"""
        data = {k: v for k, v in updates.items() if v is not None}
        if 'bid_amount' in data:
            data['bid_amount'] = str(data['bid_amount'])
        if 'daily_budget' in data:
            data['daily_budget'] = str(int(data['daily_budget'] * 100))
        return self.request('POST', f"/{adset_id}", data=data)
    
    def pause_adset(self, adset_id: str) -> dict:
        """暂停 Ad Set"""
        return self.update_adset(adset_id, {'status': 'PAUSED'})
    
    # ==================== Ad 管理 ====================
    
    def list_ads(self, account_id: str, adset_id: str = None, limit: int = 25) -> list:
        """获取 Ad 列表"""
        self._get_account_limiter(account_id).acquire()
        endpoint = f"/{account_id}/ads"
        params = {'limit': limit}
        if adset_id:
            params['adset_id'] = adset_id
        result = self.request('GET', endpoint, extra_params=params)
        return result.get('data', []) if isinstance(result, dict) else result
    
    def create_ad(self, account_id: str, adset_id: str, ad: dict) -> str:
        """创建 Ad
        
        Meta Graph API 要求：
        - creative: 必须是有效的 JSON 对象（包含 page_id 和 link_data）
        - 需要使用有效的 Facebook Page ID
        """
        self._get_account_limiter(account_id).acquire()
        
        # 构建 creative 参数
        creative = {}
        if ad.get('creative_id'):
            creative['creative_id'] = ad['creative_id']
        elif ad.get('object_story_spec'):
            creative['object_story_spec'] = ad['object_story_spec']
        else:
            # 默认使用 Shopee Page
            creative['object_story_spec'] = {
                'page_id': '1000419343151470',  # Shopee 官方 Page
                'link_data': {
                    'message': ad.get('body', 'Check out this offer!'),
                    'name': ad.get('title', 'Special Offer'),
                    'description': ad.get('description', ''),
                    'link': ad.get('link', 'https://www.shopee.com'),
                }
            }
        
        data = {
            'name': ad.get('name', 'Untitled Ad'),
            'adset_id': adset_id,
            'creative': json.dumps(creative),  # 必须是 JSON 字符串
            'body': ad.get('body', ''),
            'title': ad.get('title', ''),
            'description': ad.get('description', ''),
            'url_tags': ad.get('url_tags', ''),
            'status': ad.get('status', 'PAUSED'),
        }
        # 素材
        if ad.get('media') or ad.get('image_url'):
            media = ad.get('media', [{'type': 'image', 'url': ad.get('image_url')}])
            data['creative'] = {'attachment_link': media[0].get('url', '')}
        
        result = self.request('POST', f"/{account_id}/ads", data=data)
        return result.get('id', '') if isinstance(result, dict) else ''
    
    def update_ad(self, ad_id: str, updates: dict) -> dict:
        """更新 Ad"""
        data = {k: v for k, v in updates.items() if v is not None}
        return self.request('POST', f"/{ad_id}", data=data)
    
    def pause_ad(self, ad_id: str) -> dict:
        """暂停 Ad"""
        return self.update_ad(ad_id, {'status': 'PAUSED'})
    
    # ==================== Creative 管理 ====================
    
    def create_creative(self, account_id: str, creative: dict) -> str:
        """创建 Creative"""
        self._get_account_limiter(account_id).acquire()
        data = {
            'name': creative.get('name', 'Creative'),
            'object_story_spec': {
                'page_id': creative.get('page_id', ''),
                'link_data': json.dumps({
                    'message': creative.get('message', ''),
                    'link': creative.get('link', ''),
                    'image_hash': creative.get('image_hash', ''),
                }),
            },
        }
        if creative.get('image_url'):
            data['object_story_spec']['link_data']['image_url'] = creative['image_url']
        
        result = self.request('POST', f"/{account_id}/creatives", data=data)
        return result.get('id', '') if isinstance(result, dict) else ''
    
    # ==================== 报表查询 ====================
    
    def get_campaign_report(
        self,
        account_id: str,
        campaign_ids: list[str],
        time_range: dict = None,
        fields: list = None,
        level: str = "campaign"
    ) -> dict:
        """
        查询 Campaign 级别报表
        
        Args:
            account_id: 广告账户 ID
            campaign_ids: Campaign ID 列表
            time_range: {"time_min": "2024-01-01", "time_max": "2024-01-31"}
            fields: 指标字段列表
            level: 报表层级 ("campaign" | "adset" | "ad")
        """
        self._get_account_limiter(account_id).acquire()
        
        default_fields = [
            "campaign_id", "impressions", "clicks", "ctr", "cpc",
            "spend", "purchase_roas", "cost_per_registration",
            "actions", "action_values"
        ]
        
        params = {
            'level': level,
            'fields': ','.join(fields or default_fields),
            'time_range': json.dumps(time_range or {}),
            'filtering': json.dumps([
                {'field': f'campaign_id', 'operator': 'IN', 'value': campaign_ids}
            ]),
        }
        
        result = self.request('GET', f"/{account_id}/insights", extra_params=params)
        return result.get('data', []) if isinstance(result, dict) else result
    
    def get_adset_report(
        self,
        account_id: str,
        adset_ids: list[str],
        time_range: dict = None,
        fields: list = None,
    ) -> dict:
        """查询 Ad Set 级别报表"""
        return self.get_campaign_report(account_id, adset_ids, time_range, fields, "adset")
    
    def get_ad_report(
        self,
        account_id: str,
        ad_ids: list[str],
        time_range: dict = None,
        fields: list = None,
    ) -> dict:
        """查询 Ad 级别报表"""
        return self.get_campaign_report(account_id, ad_ids, time_range, fields, "ad")
    
    # ==================== 助推/Spark ====================
    
    def boost_post(self, account_id: str, page_id: str, post_id: str, budget: float, duration_days: int) -> str:
        """
        为 Page 帖子创建 Boost（对应 meta_boost_post 工具）
        
        注意：Boost Post 是 Meta 特有的功能，将已有帖子变成广告
        """
        self._get_account_limiter(account_id).acquire()
        
        # Boost 需要通过 PromotedObject 创建
        data = {
            'object_story_id': f"{page_id}_{post_id}",
            'daily_budget': str(int(budget * 100)),
            'scheduled_publish_time': int(time.time()),
            'promoted_object': {'page_id': page_id},
        }
        
        result = self.request('POST', f"/{account_id}/promoted_objects", data=data)
        return result.get('id', '') if isinstance(result, dict) else ''
