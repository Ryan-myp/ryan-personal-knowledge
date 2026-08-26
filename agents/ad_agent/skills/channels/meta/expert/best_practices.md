# Meta Marketing API 最佳实践

## 1. iOS 14+ 隐私适配

```python
# 启用聚合事件测量
def enable_aggregated_event_measurement(pixel_id):
    pixel = Pixel(pixel_id)
    pixel.set_field('aggregated_event_measurement_enabled', True)
    pixel.remote_update()
```

## 2. 高级数据匹配（CAPI）

```python
import hashlib

def send_capi_with_advanced_matching(pixel_id, event_name, user_data):
    events = [{
        'event_name': event_name,
        'event_time': int(time.time()),
        'action_source': 'website',
        'user_data': {
            'em': [hashlib.sha256(user_data.get('email', '').lower().encode()).hexdigest()],
            'ph': [hashlib.sha256(user_data.get('phone', '').encode()).hexdigest()],
            'fn': user_data.get('first_name', ''),
            'ln': user_data.get('last_name', ''),
            'ct': user_data.get('city', ''),
            'st': user_data.get('state', ''),
            'zp': user_data.get('zip', ''),
            'co': user_data.get('country', '')
        },
        'custom_data': user_data.get('custom', {})
    }]
    
    account = AdAccount('act_' + account_id)
    account.call_api('/events', method='POST', params={'data': json.dumps(events)})
```

## 3. 批量操作优化

```python
def batch_create_ads(account, ads_config):
    batch = account.new_batch()
    
    for config in ads_config:
        ad = account.create_ad(
            name=config['name'],
            campaign_id=config['campaign_id'],
            adset_id=config['adset_id'],
            creative={
                'title': config['title'],
                'body': config['body'],
                'link_url': config['url']
            }
        )
        batch.add(ad, key=config['name'])
    
    response = batch.execute()
    return response
```

## 4. 受众创建

```python
def create_custom_audience(account_id, name, rules):
    """创建自定义受众"""
    from facebook_business.adobjects.customaudience import CustomAudience
    
    audience = account.create_custom_audience(
        {'name': name, 'rule': rules}
    )
    return audience

# 使用示例
rules = {
    'or': [{
        'event': [{
            'action_type': 'landing',
            'attribute': 'page',
            'filters': [{'field': 'url', 'operator': 'contains', 'value': 'example.com'}]
        }]
    }]
}
audience = create_custom_audience(account_id, 'Website Visitors', rules)
```

## 5. 常见问题

**Q: Pixel 和 CAPI 有什么区别？**
A: 
- **Pixel**: 浏览器端追踪，受 CORS、广告拦截器影响
- **CAPI**: 服务器端追踪，更准确，iOS 14+ 必备

**Q: 如何处理权限不足错误？**
A: 检查 app 权限范围，确保包含 `ads_management`、`ads_read`、`pages_read_engagement` 等必要权限。

**Q: 如何优化 CAPI 事件匹配率？**
A: 提供完整用户数据（email、phone、name）、使用哈希加密、设置正确的 event_source_url。
