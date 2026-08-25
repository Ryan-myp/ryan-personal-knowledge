# 报表查询功能总结

## 已完成功能

### 1. 参数提取改进 (intent.py)
- **Campaign ID 提取**:
  - `campaign 12345`
  - `campaign_id=12345`
  - `ID: 12345`
  - `campaign ID 12345`

- **日期范围提取**:
  - `最近7天` → `{"start_date": "LAST_7_DAYS", "end_date": "TODAY"}`
  - `last_7_days` → `{"start_date": "LAST_7_DAYS", "end_date": "TODAY"}`
  - `2024-01-01 至 2024-01-31` → `{"start_date": "2024-01-01", "end_date": "2024-01-31"}`
  - `最近30天` → `{"start_date": "LAST_30_DAYS", "end_date": "TODAY"}`

### 2. Meta 报表查询修复 (meta_capability.py + meta_client.py)
- **问题**: Meta Insights API 不接受 `time_range` 参数，需要使用 `date_preset`
- **解决**: 
  - 将 `LAST_7_DAYS` 转换为 `last_7d`
  - 将 `LAST_30_DAYS` 转换为 `last_30d`
  - 使用有效的 Meta Insights API 字段名

### 3. 测试结果

| 平台 | 状态 | 说明 |
|------|------|------|
| Meta | ✅ | 成功调用 API，返回 0 条记录（测试账户无数据） |
| TikTok | ✅ | 成功返回报表数据 (impressions/clicks/cost) |
| Google | ✅ | 成功调用 API |
| DV360 | ⚠️ | Mock 模式，返回示例数据 |

## 工具清单

| 工具名 | 平台 | 状态 |
|--------|------|------|
| meta_get_campaign_report | Meta | ✅ 已修复 |
| tiktok_get_campaign_report | TikTok | ✅ 正常 |
| google_get_campaign_report | Google | ✅ 正常 |
| dv360_get_line_item_report | DV360 | ⚠️ Mock |

## 测试命令

```bash
# Meta 报表查询
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"user_input": "查询 Meta campaign 120251005127660251 最近7天报表", "platform": "meta"}'

# TikTok 报表查询
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"user_input": "查询 TikTok campaign 1874401777748561 最近7天报表", "platform": "tiktok"}'

# Google 报表查询
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"user_input": "查询 Google campaign 934482945 最近30天报表", "platform": "google"}'
```

## 服务状态

- **API 地址**: http://127.0.0.1:8765/
- **Swagger**: http://127.0.0.1:8765/docs
- **工具总数**: 42
- **报表工具**: 4 个
