# 已验证可用的 RSS Feeds

**日期**: 2025-06-05
**工具**: blogwatcher-cli (v0.2.1)

## 正常工作的 Feed

### ✅ Hugging Face Blog
- URL: `https://huggingface.co/blog`
- Feed: `https://huggingface.co/blog/feed.xml`
- 模式: RSS
- 文章数: ~793
- 添加命令:
  ```bash
  blogwatcher-cli add "Hugging Face Blog" https://huggingface.co/blog --feed-url "https://huggingface.co/blog/feed.xml"
  ```

## 已失效的 Feed

### ❌ Anthropic Blog
- URL: `https://www.anthropic.com/blog`
- 错误: 307 重定向
- RSS: 404

### ❌ OpenAI Blog
- URL: `https://openai.com/blog`
- 错误: 403 Forbidden
- RSS: 403

### ❌ Google AI Blog
- URL: `https://blog.google/technology/ai/`
- 错误: 301 重定向
- RSS: 解析失败

### ❌ Meta AI Blog
- URL: `https://ai.meta.com/blog/`
- 错误: 404
- HTML scrape: 0 articles (反爬)

### ❌ TikTok Tech Blog
- URL: `https://www.tiktok.com/tech/blog`
- 错误: 302 重定向

## 替代方案

由于主流 AI 博客 RSS 大量失效，建议：

1. **arxiv** — 论文 RSS (通过 hermes `arxiv` skill)
2. **手动收藏** — 定期访问各博客网站
3. **Google Alerts** — 设置关键词提醒
4. **Twitter/X** — 关注各团队官方账号
