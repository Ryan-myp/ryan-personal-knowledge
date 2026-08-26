# DV360 最佳实践

## 1. Line Item 创建

```python
def create_line_item(client, advertiser_id, config):
    """创建媒体购买 Line Item"""
    body = {
        'name': config['name'],
        'goal': config.get('goal', {'goalType': 'IMPRESSIONS'}),
        'targeting': config.get('targeting', {}),
        'lineItemType': config.get('type', 'SPONSORED'),
        'status': 'DRAFT',
        'flight': {
            'startTimeMicros': config.get('start_time', 0),
            'endTimeMicros': config.get('end_time', 0)
        },
        'budgetMicros': config.get('budget_micros', 0)
    }
    
    result = client.create_line_item(advertiser_id, body)
    return result
```

## 2. 定向配置

```python
def create_targeting(client, advertiser_id, config):
    """创建定向条件"""
    body = {
        'name': config['name'],
        'targetingType': config.get('targeting_type', 'GEO'),
        'geoTargeting': config.get('geo', {}),
        'deviceTypeTargeting': config.get('devices', {}),
        'placementTargeting': config.get('placements', {})
    }
    
    result = client.create_targeting(advertiser_id, body)
    return result
```

## 3. 报表查询

```python
def get_campaign_report(client, advertiser_id, date_range):
    """查询 Campaign 报表"""
    report = client.create_report(advertiser_id, {
        'dateRange': {
            'startDate': {'year': 2026, 'month': 8, 'day': 1},
            'endDate': {'year': 2026, 'month': 8, 'day': 26}
        },
        'dimensions': ['DATE', 'CAMPAIGN'],
        'metrics': ['IMPRESSIONS', 'CLICKS', 'CONVERSIONS', 'SPEND']
    })
    
    data = client.get_report_result(report['reportId'])
    return data
```

## 4. 投放方式选择

| 需求 | 推荐方式 |
|------|----------|
| 品牌保量采购 | PG (Programmatic Guaranteed) |
| 精选媒体采购 | PMP (Private Marketplace) |
| 大规模流量 | Open Auction |
| 常规投放 | Standard Flight |

## 5. 常见问题

**Q: DV360 和 Google Ads 有什么区别？**
A: DV360 是程序化广告平台，支持跨媒体采购（YouTube、外部网站、OTT/CTV），Google Ads 主要是 Google 自营广告位。

**Q: Line Item 和 Flight 有什么区别？**
A: Line Item 是媒体购买单元，Flight 是投放时间段配置，一个 Line Item 可以包含多个 Flight。

**Q: PMP 和 Open Auction 有什么区别？**
A: PMP 是邀请制的私人 marketplace，价格更高但媒体质量更好；Open Auction 是公开竞价，价格更低但媒体质量参差不齐。

**Q: 如何处理创意审批？**
A: 提交创意后，系统会自动审批，通常 24-48 小时内完成。可以调用 `get_creative_approval` 查询状态。
