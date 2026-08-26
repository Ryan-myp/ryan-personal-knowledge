# LLM Wiki 索引

> **版本**: v1.0.0
> **更新时间**: 2026-08-26
> **作者**: Ryan

## 📚 知识库概览

本知识库遵循 [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 架构，包含：

- **平台层知识**: Google Ads, Meta, TikTok, DV360 四大广告平台
- **业务层知识**: 出价策略、定向策略、素材指南
- **经验层知识**: 最佳实践、错误模式、案例研究

## 📂 目录结构

```
knowledge_base/
├── index.md                    # 本索引文件
├── log.md                      # 更新日志
├── platforms/                  # 平台层知识
│   ├── google/
│   │   ├── campaigns.md        # Campaign 层级结构
│   │   ├── workflows.md        # API 工作流
│   │   └── constraints.md      # 参数约束规则
│   ├── meta/
│   ├── tiktok/
│   └── dv360/
├── expertise/                  # 经验层知识
│   ├── best-practices.md       # 最佳实践
│   ├── error-patterns.md       # 错误模式
│   └── case-studies.md         # 案例研究
└── business/                   # 业务层知识
    ├── bidding-strategies.md
    ├── targeting-strategies.md
    └── creative-guides.md
```

## 🔍 快速搜索

使用 `wiki_search` 工具查询知识库：

```python
from agents.ad_agent.tools.wiki_query import wiki_search

# 搜索关键词
results = wiki_search("限流处理", platforms=['google'], limit=5)

# 获取最佳实践
results = wiki_search("best_practices", limit=10)
```

## 📊 知识库统计

| 类别 | 条目数 |
|------|--------|
| 平台层知识 | ~30 |
| 经验层知识 | ~15 |
| 业务层知识 | ~10 |

## 🔄 更新日志

见 [log.md](log.md)
