# 广告平台专家 Skills 索引

> **领域**: 广告投放 / 平台技能
> **类型**: skills-index
> **更新时间**: 2026-08-14
> **作者**: Ryan

---

## 📌 Skills 概述

本目录包含四大广告平台的专家 Skills，每个 Skill 提供完整的 API 调用能力和独家洞察。

---

## 🎯 可用的 Skills

### 1. TikTok Ads 专家
**路径**: `skills/tiktok-ads-expert/SKILL.md`

**核心能力:**
- OAuth 认证管理
- 广告系列/广告组/创意管理
- Spark Ads（达人原生广告）
- Pixel + Conversion API 事件追踪
- 报表查询与数据分析

**使用场景:**
- 创建和管理 TikTok 广告活动
- 配置 Spark Ads 达人合作
- 追踪转化事件和归因分析

---

### 2. Meta Marketing API 专家
**路径**: `skills/meta-marketing-api-expert/SKILL.md`

**核心能力:**
- OAuth 2.0 认证与权限管理
- Campaign/Ad Set/Ad 层级管理
- Pixel 事件追踪与 CAPI 实现
- 自定义受众与 Lookalike 受众管理
- 报表分析与归因

**使用场景:**
- Facebook/Instagram 广告投放
- 多渠道受众定向
- 转化追踪与优化

---

### 3. Google Ads API 专家
**路径**: `skills/google-ads-api-expert/SKILL.md`

**核心能力:**
- OAuth + Developer Token 认证
- Campaign/Ad Group/Keyword/Ad 全层级管理
- Streaming Mutate 批量操作
- 智能出价策略配置（Target CPA/ROAS）
- 报表下载与数据分析

**使用场景:**
- Google Search/Shopping 广告投放
- 批量操作优化
- 智能出价策略配置

---

### 4. Display & Video 360 专家
**路径**: `skills/dv360-expert/SKILL.md`

**核心能力:**
- 服务账号认证
- Line Item（媒体购买）管理
- 创意上传与管理
- 报表查询与分析
- DSP 集成

**使用场景:**
- 程序化广告采购
- 媒体购买管理
- 创意资产审批

---

### 5. 广告平台统一工具集
**路径**: `skills/ad-platform-tools/SKILL.md`

**核心能力:**
- 统一认证管理（四大平台）
- 跨平台数据同步
- 统一报表聚合
- 多平台事件追踪

**使用场景:**
- 跨平台账户管理
- 多平台报表聚合
- 统一事件追踪

---

## 🚀 快速开始

### 1. 配置凭证

```bash
# 复制凭证模板
cp config/ad_platform_credentials_template.json config/ad_platform_credentials.json

# 编辑凭证文件（务必保密！）
nano config/ad_platform_credentials.json
```

### 2. 测试连接

```bash
# 测试所有平台
python3 scripts/ad_platform_api.py --all --test

# 测试单个平台
python3 scripts/ad_platform_api.py --platform meta --test
```

### 3. 使用 API

```bash
# 获取账户列表
python3 scripts/ad_platform_api.py --platform google --action list_accounts

# 创建广告系列
python3 scripts/ad_platform_api.py --platform meta --action create_campaign --name "Summer Sale"

# 追踪转化事件
python3 scripts/ad_platform_api.py --platform tiktok --action track_pixel --pixel_id "123"
```

---

## 📂 文件结构

```
knowledge/skills/
├── SKILLS_INDEX.md                    # 本索引文件
├── tiktok-ads-expert/
│   └── SKILL.md                       # TikTok Ads 专家技能
├── meta-marketing-api-expert/
│   └── SKILL.md                       # Meta Marketing API 专家技能
├── google-ads-api-expert/
│   └── SKILL.md                       # Google Ads API 专家技能
├── dv360-expert/
│   └── SKILL.md                       # DV360 专家技能
└── ad-platform-tools/
    └── SKILL.md                       # 统一工具集技能

scripts/
├── ad_platform_api.py                 # 统一 API 调用脚本
├── fetch_platform_docs.py             # 文档获取脚本
└── platform_docs_scraper.py           # 文档刮削器

config/
└── ad_platform_credentials_template.json  # 凭证配置模板
```

---

## 🔐 安全注意事项

1. **凭证管理**
   - 使用环境变量或密钥管理服务
   - 不要将 `ad_platform_credentials.json` 提交到 Git
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

## 🎓 进阶使用

### 批量操作

```bash
# 批量创建广告系列
python3 scripts/ad_platform_api.py --platform google --action batch_create_campaigns --config campaigns.json

# 批量同步账户
python3 scripts/ad_platform_api.py --platform meta --action sync_accounts
```

### 定时任务

```bash
# 添加定时任务
crontab scripts/ad_platform_cron.txt
```

### API 限流处理

各平台都有 API 调用限制，脚本已内置自动重试和指数退避机制：
- TikTok: 10,000 次/小时
- Meta: 200,000 次/天
- Google Ads: 100,000 Get/10,000 Mutate 次/天
- DV360: 根据账户等级

---

*本 Skills 系统设计为跨平台、可扩展的广告平台操作工具集。*
