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

*本文档基于 blogwatcher CLI 整理。*