# TikTok Ads 最佳实践

## 1. 速率限制处理

```python
import time

def safe_request(client, func, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func(client, *args)
        except Exception as e:
            if 'rate limit' in str(e).lower():
                wait_time = min(2 ** attempt, 60)
                time.sleep(wait_time)
            else:
                raise
```

## 2. 用户数据加密

```python
import hashlib

def hash_user_data(email, phone):
    return {
        'em': [hashlib.sha256(email.lower().encode()).hexdigest()],
        'ph': [hashlib.sha256(phone.encode()).hexdigest()]
    }

def send_converted_event(pixel_id, event_data):
    hashed = hash_user_data(
        event_data.get('email', ''),
        event_data.get('phone', '')
    )
    
    event = {
        'event_name': 'Converted',
        'event_time': int(time.time()),
        'event_id': str(uuid.uuid4()),
        'user_data': hashed,
        'custom_data': event_data.get('custom', {})
    }
    
    client.send_event(pixel_id, event)
```

## 3. Spark Ads 创建

```python
def create_spark_ad(client, account_id, campaign_id, adgroup_id, video_id, creator_id):
    """创建 Spark Ads（达人原生广告）"""
    ad = client.create_ad(
        account_id=account_id,
        campaign_id=campaign_id,
        adgroup_id=adgroup_id,
        name='Spark Ad',
        tracking_url='https://example.com',
        creative={
            'spark_ad': {
                'video_id': video_id,
                'creator_id': creator_id,
                'hashtag': '#Example'
            }
        }
    )
    return ad
```

## 4. 常见问题

**Q: Spark Ads 和普通 Ads 有什么区别？**
A: Spark Ads 使用创作者原生内容，信任度高，点击率通常更高。需要创作者授权。

**Q: 如何处理 iOS 14+ 的隐私限制？**
A: 优先使用 Conversion API，启用聚合事件测量，设置事件优先级。

**Q: 如何优化 Spark Ads 的投放效果？**
A: 选择高互动创作者，使用原生视频内容，设置合理的转化目标。
