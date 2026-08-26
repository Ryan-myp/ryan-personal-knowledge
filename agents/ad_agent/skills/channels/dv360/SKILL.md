---
name: dv360-api
description: Display & Video 360 API 工具集 - 支持 Line Item/Flight/Creative 全层级管理、媒体购买、定向配置、报表查询等功能
version: 1.0.0
author: Ryan
tags: [dv360, display-video, programmatic, dsp, line-item, creative]
---

# DV360 API 工具集

## 🛠️ 可用 Tools

| Tool | 功能 | 参数 |
|------|------|------|
| `dv360_auth` | OAuth 认证 | service_account_file, customer_id |
| `dv360_get_customer` | 获取客户信息 | customer_id |
| `dv360_list_customers` | 列出所有客户 | limit |
| `dv360_list_advertisers` | 列出广告主 | partner_id, limit |
| `dv360_get_advertiser` | 获取广告主详情 | advertiser_id |
| `dv360_list_line_items` | 列出媒体购买 | advertiser_id, io_id, limit |
| `dv360_get_line_item` | 获取媒体购买详情 | line_item_id |
| `dv360_create_line_item` | 创建媒体购买 | advertiser_id, io_id, name, type, flight, budget |
| `dv360_update_line_item` | 更新媒体购买 | line_item_id, updates |
| `dv360_pause_line_item` | 暂停媒体购买 | line_item_id |
| `dv360_enable_line_item` | 启用媒体购买 | line_item_id |
| `dv360_list_creatives` | 列出创意 | line_item_id, status |
| `dv360_get_creative` | 获取创意详情 | creative_id |
| `dv360_upload_creative` | 上传创意文件 | line_item_id, creative_file, creative_type |
| `dv360_get_report` | 查询报表数据 | advertiser_id, date_range, dimensions, metrics |
| `dv360_list_ios` | 列出插入订单 | advertiser_id |
| `dv360_create_io` | 创建插入订单 | advertiser_id, name, start_time, end_time |

## 📚 参考

- [DV360 API 官方文档](https://developers.google.com/display-video/api/docs)
- [专家知识库](../../../knowledge/skills/dv360-expert/SKILL.md) - 详细 API 指南、最佳实践、常见问题
