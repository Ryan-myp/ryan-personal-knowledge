# 前沿追踪 - Blogwatcher 配置报告

**日期**: 2025-06-05
**分类**: 前沿追踪
**标签**: #前沿 #blogwatcher

## 配置状态

### 已配置博客

#### ✅ 正常运行
- **Hugging Face Blog** - RSS模式
  - URL: https://huggingface.co/blog
  - Feed: https://huggingface.co/blog/feed.xml
  - 文章数: 793篇
  - 最近文章:
    - Nemotron 3.5 Content Safety (2026-06-04)
    - EVA-Bench Data 2.0 (2026-06-04)
    - Designing the hf CLI as an agent-optimized way to work with the Hub (2026-06-04)

#### ⚠️ 需要修复
- **Anthropic Blog** - 307重定向错误
- **OpenAI Blog** - 403禁止访问
- **Google AI Blog** - 301重定向错误
- **Meta AI Blog** - HTML抓取成功但0篇文章
- **TikTok Tech Blog** - 302重定向错误

## 常用命令

```bash
# 扫描所有博客
blogwatcher-cli scan

# 查看未读文章
blogwatcher-cli articles

# 按博客筛选
blogwatcher-cli articles --blog "Hugging Face Blog"

# 标记文章已读
blogwatcher-cli read 1

# 查看已配置博客
blogwatcher-cli blogs
```

## 后续优化
- 需要手动修复其他博客的RSS feed URL或HTML选择器
- 可以设置 cron job 定期自动扫描
- 值得关注的文章可以整理到 `knowledge/前沿/insights/` 目录
