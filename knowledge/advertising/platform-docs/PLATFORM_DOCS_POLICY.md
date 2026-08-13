# 广告平台官方文档接入策略

> **领域**: 广告投放 / 平台文档接入
> **类型**: strategy/policy
> **更新时间**: 2026-08-14
> **作者**: Ryan

---

## 📌 四大广告平台官方文档

### 1. TikTok Ads API

| 属性 | 值 |
|------|-----|
| **官方文档** | https://business-api.tiktok.com/portal/docs |
| **API 基础** | https://business-api.tiktok.com/portal |
| **认证方式** | OAuth 2.0 + App Key/Secret |
| **支持格式** | REST API (JSON) |
| **沙箱环境** | ✅ 提供测试账户 |

**核心模块：**
- 广告账户管理
- 广告系列/广告组/广告创意
- Spark Ads（达人广告）
- Pixel 事件追踪
- Conversion API
- 报表查询

---

### 2. Meta Marketing API

| 属性 | 值 |
|------|-----|
| **官方文档** | https://developers.facebook.com/docs/marketing-api |
| **API 基础** | https://developers.facebook.com/docs |
| **认证方式** | OAuth 2.0 + Access Token |
| **支持格式** | REST API (JSON) |
| **沙箱环境** | ✅ 提供开发者工具 |

**核心模块：**
- 广告账户管理
- Campaign/Ad Set/Ad
- Pixel 事件追踪
- Conversion API (CAPI)
- 受众管理
- 创意管理
- 报表分析

---

### 3. Google Ads API

| 属性 | 值 |
|------|-----|
| **官方文档** | https://developers.google.com/google-ads/api |
| **API 基础** | https://developers.google.com/google-ads/api/docs/start |
| **认证方式** | OAuth 2.0 + Developer Token |
| **支持格式** | gRPC + REST API |
| **沙箱环境** | ✅ 提供测试账户 |

**核心模块：**
- 客户管理
- 广告系列/广告组/关键词
- 出价策略（智能出价）
- 报表下载
- 批量操作
- Streaming mutate

---

### 4. Display & Video 360 API

| 属性 | 值 |
|------|-----|
| **官方文档** | https://developers.google.com/display-video/api |
| **API 基础** | https://developers.google.com/display-video/api/guides/overview |
| **认证方式** | OAuth 2.0 + Service Account |
| **支持格式** | REST API |
| **沙箱环境** | ⚠️ 需要客户支持 |

**核心模块：**
- 媒体购买管理
- 创意上传
- 报表查询
- 需求方平台（DSP）集成
- 程序化广告

---

## 🔄 接入模式对比

| 模式 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **爬虫抓取** | 完整、结构化 | 动态页面难解析、可能违反 robots.txt | 静态文档 |
| **实时搜索** | 最新、灵活 | 搜索结果不确定、需要搜索能力 | 追踪更新 |
| **混合模式** | 平衡完整性和时效性 | 实现复杂 | 生产环境 |
| **知识蒸馏** | 深度整合、独家洞察 | 需要人工审核 | 核心文档 |

---

## 📋 文档获取流程

```
┌─────────────────┐
│  1. 识别文档源  │
└────────┬────────┘
         ▼
┌─────────────────┐
│  2. 确定接入模式│
└────────┬────────┘
         ▼
┌─────────────────┐
│  3. 执行获取    │
└────────┬────────┘
         ▼
┌─────────────────┐
│  4. 内容整理    │
└────────┬────────┘
         ▼
┌─────────────────┐
│  5. 质量审核    │
└────────┬────────┘
         ▼
┌─────────────────┐
│  6. 入库存储    │
└─────────────────┘
```

---

## 🎯 最佳实践

### 1. 版权合规

✅ **可以做：**
- 获取公开的技术文档
- 提取代码示例并添加注释
- 整理 API 参考文档
- 创建摘要和索引

❌ **不能做：**
- 抓取需要付费的内容
- 绕过认证获取私有文档
- 大规模复制整本书籍
- 用于商业产品替代

### 2. 内容整合策略

**三级整合法：**

| 级别 | 内容来源 | 处理方式 |
|------|---------|---------|
| L1 基础 | 官方文档 | 直接引用 + 注释 |
| L2 深入 | 技术博客 | 对比分析 + 实战经验 |
| L3 独家 | 个人实践 | 决策背景 + 踩坑记录 |

### 3. 文档更新机制

```python
# 建议的更新频率
UPDATE_FREQ = {
    "tiktok-ads": "每月",
    "facebook-ads": "每月",
    "google-ads": "每季度",
    "display-video-360": "每季度",
}
```

---

## 📊 知识库现有覆盖

| 平台 | 文档数 | 深度占比 | 更新状态 |
|------|--------|---------|---------|
| TikTok Ads | 8+ | 60% | 待补充 |
| Meta Ads | 15+ | 70% | 待补充 |
| Google Ads | 10+ | 65% | 待补充 |
| DV360 | 5+ | 50% | 待补充 |

**目标：** 每个平台达到 20+ 篇深度文档，深度占比 75%+

---

## 🔧 自动化脚本

使用 `scripts/platform_docs_scraper.py` 进行文档接入：

```bash
# 处理单个平台
python3 scripts/platform_docs_scraper.py --platform tiktok-ads --mode hybrid

# 处理所有平台
python3 scripts/platform_docs_scraper.py --all --mode hybrid

# 查看结果
cat logs/platform_docs_$(date +%Y%m%d).json
```

---

## 📚 参考资源

- **TikTok Ads API 文档**: https://business-api.tiktok.com/portal/docs
- **Meta Marketing API**: https://developers.facebook.com/docs/marketing-api
- **Google Ads API**: https://developers.google.com/google-ads/api
- **Display & Video 360 API**: https://developers.google.com/display-video/api

---

*本策略基于版权合规原则，仅获取公开技术文档，确保知识库合法合规。*
