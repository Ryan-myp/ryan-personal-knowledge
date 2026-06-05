# Blogwatcher 前沿博客配置

**日期**: 2025-06-05
**版本**: 0.2.1

## 已配置博客

### ✅ 正常运行
- **Hugging Face Blog** - RSS模式
  - URL: https://huggingface.co/blog
  - Feed: https://huggingface.co/blog/feed.xml
  - 文章数: 793篇

### ⚠️ 需要修复（反爬/重定向）
- Anthropic Blog — 307重定向
- OpenAI Blog — 403禁止
- Google AI Blog — 301重定向
- Meta AI Blog — HTML抓取0篇
- TikTok Tech Blog — 302重定向

## 常用命令
```bash
blogwatcher-cli scan        # 扫描所有博客
blogwatcher-cli articles    # 查看未读
blogwatcher-cli articles --blog "Hugging Face Blog"
blogwatcher-cli read 1      # 标记已读
blogwatcher-cli blogs       # 查看已配置
```
