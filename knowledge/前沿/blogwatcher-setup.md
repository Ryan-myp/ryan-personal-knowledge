# Blogwatcher RSS 配置指南

> 通过 blogwatcher 自动收集 LLM/Agent/MLOps 前沿洞察

## 安装

```bash
go install github.com/yourusername/blogwatcher-cli@latest
```

## 配置

```yaml
feeds:
  - name: Anthropic
    url: https://blog.anthropic.com/atom.xml
    tags: [ai, llm]
  - name: OpenAI
    url: https://openai.com/blog/rss.xml
    tags: [ai, llm]
  - name: Google AI
    url: https://blog.google/technology/ai/rss/
    tags: [ai, llm]
  - name: Hugging Face
    url: https://huggingface.co/blog/feed.xml
    tags: [ai, ml]
  - name: Lilian Weng
    url: https://lilianweng.github.io/index.xml
    tags: [ai, ml, agent]
```

## 运行

```bash
# 首次运行
blogwatcher --config config.yaml --output-dir ../前沿

# 持续运行
blogwatcher --config config.yaml --poll-interval 2h
```

## 输出格式

```markdown
# [Feed Name] - [Article Title]
[Published Date]

[Content Summary]

## Tags
[tags]

## Link
[URL]
```

---

## 自测题

### 问题 1
如何监控 RSS 订阅源的可用性？

<details>
<summary>查看答案</summary>

1. **健康检查**：定期 curl 订阅 URL，检查 HTTP 状态码
2. **解析失败告警**：XML 解析失败时发送通知
3. **更新频率检测**：超过 N 天没有更新则告警
4. **Go 实现**：
```go
func (w *Watcher) CheckFeeds() {
    for _, feed := range w.feeds {
        resp, err := http.Get(feed.URL)
        if err != nil || resp.StatusCode != 200 {
            w.alert(feed.Name, err)
            continue
        }
        // 解析 RSS
        items, err := parseRSS(resp.Body)
        if err != nil {
            w.alert(feed.Name, err)
            continue
        }
        // 检查更新频率
        if len(items) > 0 {
            lastUpdated := items[0].PubDate
            if time.Since(lastUpdated) > 7*24*time.Hour {
                w.alert(feed.Name, "no update for 7 days")
            }
        }
    }
}
```
5. **最佳实践**：使用 cron 定期运行，邮件/Slack 通知

</details>

---

*本文档基于 blogwatcher CLI 整理。*