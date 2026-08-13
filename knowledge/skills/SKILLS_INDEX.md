# 广告平台专家 Skills 索引 v2.0

> **版本**: v2.0.0
> **更新时间**: 2026-08-14
> **作者**: Ryan

---

## 📌 Skills 概览

本索引包含四大广告平台的完整专家 Skills，每个 Skill 提供 45-60+ API 工具的完整调用能力。

| Skill | 平台 | Tools 数量 | 覆盖范围 |
|-------|------|-----------|---------|
| **tiktok-ads-expert** | TikTok Ads | 50+ | Campaign/Ad Group/Ad/Spark Ads/Pixel/CAPI/报表 |
| **meta-marketing-api-expert** | Meta/Facebook | 60+ | Campaign/Ad Set/Ad/受众/产品目录/动态广告/CAPI |
| **google-ads-api-expert** | Google Ads | 55+ | Campaign/Ad Group/Keyword/Ad/智能出价/素材组 |
| **dv360-expert** | DV360 | 45+ | Line Item/Flight/Creative/定向/报表 |
| **ad-platform-tools** | 通用工具集 | 30+ | 跨平台认证/同步/报表聚合/事件追踪 |

---

## 🚀 快速开始

### 1. 配置凭证

```bash
cp config/ad_platform_credentials_template.json config/ad_platform_credentials.json
nano config/ad_platform_credentials.json
```

### 2. 测试连接

```bash
python3 scripts/ad_platform_api.py --all --test
```

### 3. 使用 API

```bash
# 获取账户列表
python3 scripts/ad_platform_api.py --platform meta --action list_accounts

# 创建广告系列
python3 scripts/ad_platform_api.py --platform google --action create_campaign --name "Summer Sale"
```

---

## 📂 文件结构

```
knowledge/skills/
├── SKILLS_INDEX.md                    # 本索引文档
├── tiktok-ads-expert/
│   └── SKILL.md                       # 50+ API 工具
├── meta-marketing-api-expert/
│   └── SKILL.md                       # 60+ API 工具
├── google-ads-api-expert/
│   └── SKILL.md                       # 55+ API 工具
├── dv360-expert/
│   └── SKILL.md                       # 45+ API 工具
└── ad-platform-tools/
    └── SKILL.md                       # 30+ 通用工具

scripts/
├── ad_platform_api.py                 # 统一 API 调用脚本
├── fetch_platform_docs.py             # 文档获取脚本
└── platform_docs_scraper.py           # 文档刮削器

config/
└── ad_platform_credentials_template.json  # 凭证模板
```

---

## 🎯 各 Skill 详细能力

### TikTok Ads Expert (50+ Tools)

**认证管理**: auth, refresh_token, get_account, list_accounts, validate_token

**Campaign 管理**: create, update, get, list, pause, enable, delete, copy (8 tools)

**Ad Group 管理**: create, update, get, list, pause, enable, delete, targeting, copy (10 tools)

**Ad 创意管理**: create, update, get, list, pause, enable, delete, copy (8 tools)

**Spark Ads**: create_spark_ad, list_creators, get_creator_info, authorize, revoke, list_videos (6 tools)

**受众管理**: create, update, get, list, delete, estimate (6 tools)

**素材管理**: upload_video, get_video, list_videos, delete_video, upload_image (5 tools)

**报表分析**: query_report, get_campaign_report, get_adgroup_report, get_ad_report, export_report, get_metrics_summary (7 tools)

**事件追踪**: track_pixel, send_capi_event, create_pixel, get_pixel, list_pixels (5 tools)

**辅助工具**: list_locations, list_platforms, list_interests, list_languages, list_promotion_goals (5 tools)

---

### Meta Marketing API Expert (60+ Tools)

**认证管理**: auth, refresh_token, get_account, list_accounts, validate_token, generate_user_token (7 tools)

**Campaign 管理**: create, update, get, list, pause, enable, delete, copy, clone, insights (10 tools)

**Ad Set 管理**: create, update, get, list, pause, enable, delete, targeting, copy, insights, batch_create (12 tools)

**Ad 创意管理**: create, update, get, list, pause, enable, delete, copy, insights, batch_create (10 tools)

**创意资产**: create_carousel, create_single_image, create_video, create_collection, upload_image, get_creative, list_creatives, delete_creative (8 tools)

**受众管理**: create_custom_audience, update_custom_audience, get_custom_audience, list_custom_audiences, delete_custom_audience, create_lookalike, get_lookalike, estimate_audience, add_to_audience, remove_from_audience (10 tools)

**产品目录**: create_catalog, get_catalog, list_catalogs, update_catalog, delete_catalog, upload_products, get_product, list_products (8 tools)

**动态广告**: create_dras_campaign, create_dras_adset, create_dras_ad, update_dynamic_offer, list_dynamic_ads, get_dynamic_ad_insights (6 tools)

**事件追踪**: create_pixel, get_pixel, list_pixels, track_pixel, send_capi_event, test_events (6 tools)

**报表分析**: query_insights, get_campaign_insights, get_adset_insights, get_ad_insights, download_report, get_breakdown_insights, get_custom_tables (7 tools)

**辅助工具**: list_locations, list_platforms, list_interests, list_behaviors, list_languages (5 tools)

---

### Google Ads API Expert (55+ Tools)

**认证管理**: auth, get_customer, list_customers, list_accessible_customers, get_hierarchy, validate_token (6 tools)

**Campaign 管理**: create, update, get, list, pause, enable, delete, copy, get_bidding_strategy, set_bidding_strategy, get_budget, list_ad_testing (12 tools)

**Ad Group 管理**: create, update, get, list, pause, enable, delete, targeting, audience, cpc_bid (10 tools)

**关键词管理**: add_keywords, update_keywords, get_keyword, list_keywords, remove_keywords, negative_keywords, get_metrics, list_auction_insights (8 tools)

**广告创意管理**: create_text_ad, create_responsive_search_ad, create_expand_text_ad, get_ad, list_ads, pause, enable, delete, update, get_performance (10 tools)

**素材组管理**: create_asset_group, update_asset_group, get_asset_group, list_asset_groups, pause, enable (6 tools)

**智能出价**: create_target_cpa, create_target_roas, create_max_conversions, create_ecpa, get_bidding_strategy, list_bidding_strategies, update_bidding_strategy, delete_bidding_strategy, get_bid_loose, set_bid_multiplier (10 tools)

**报表分析**: download_report, get_metrics, get_campaign_metrics, get_ad_group_metrics, get_keyword_metrics, get_ad_metrics, export_report, get_auction_insights (8 tools)

**辅助工具**: list_locations, list_languages, list_ad_networks, list_device_types, list_placement_types (5 tools)

---

### DV360 Expert (45+ Tools)

**认证管理**: auth, get_customer, list_customers, get_advertisers, get_advertiser, validate_credentials (6 tools)

**Line Item 管理**: create, update, get, list, pause, enable, delete, copy, get_budget, update_budget, get_performance, batch_create (12 tools)

**Flight 管理**: create, update, get, list, pause, enable, delete, extend (8 tools)

**创意管理**: upload_creative, get_creative, list_creatives, update_creative, delete_creative, get_approval, list_templates, create_banner, create_video, create_native (10 tools)

**定向管理**: create_targeting, get_targeting, list_targeting, update_targeting, delete_targeting, estimate_reach (6 tools)

**报表分析**: get_report, get_line_item_report, get_creative_report, get_impression_report, get_click_report, export_report, get_breakdown_report (7 tools)

**辅助工具**: list_platforms, list_device_types, list_ad_formats, list_brand_safety, list_viewability, list_geo_locations (6 tools)

---

### Ad Platform Tools (30+ Tools)

**认证管理**: configure, test, refresh, list_configured, get_token, clear_credentials (6 tools)

**数据同步**: sync_accounts, sync_campaigns, sync_ad_groups, sync_ads, sync_audiences, sync_creatives, sync_products, sync_all (8 tools)

**报表聚合**: get_report, aggregate_report, compare_platforms, export_report, get_metrics_summary, get_daily_trends (6 tools)

**事件追踪**: track_event, track_multi_platform, get_conversion_summary, validate_pixel, test_conversion (5 tools)

**通用操作**: create_campaign, update_campaign, pause_campaign, enable_campaign, duplicate_campaign (5 tools)

**辅助工具**: list_platforms, get_platform_status, check_rate_limits, get_quota_usage, sync_config_to_env (5 tools)

---

## 🔐 安全注意事项

1. **凭证管理**
   - 使用环境变量或密钥管理服务
   - 不要将凭证提交到 Git
   - 定期轮换 Access Token

2. **权限控制**
   - 最小权限原则
   - 使用子账户隔离不同环境
   - 定期审计 API 权限

3. **数据安全**
   - 加密传输敏感数据
   - 遵守各平台数据使用政策
   - 用户数据脱敏处理

---

## 📚 相关文档

- **API 参考**: `knowledge/advertising/google-ads-api/`
- **官方文档**: `knowledge/advertising/platform-docs/`
- **跨渠道优化**: `knowledge/advertising/cross-channel-optimization/`
- **使用指南**: `docs/ad-platform-skills-guide.md`

---

*本 Skills 系统支持 50+ API 工具，覆盖广告投放的全生命周期管理。*
