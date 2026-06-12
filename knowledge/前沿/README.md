# 前沿追踪

> 通过 blogwatcher/arxiv 收集的 LLM/Agent/MLOps 前沿洞察

## 文档

| 文档 | 说明 |
|------|------|
| [blogwatcher-setup.md](./blogwatcher-setup.md) | Blogwatcher RSS 配置指南 |

## 推荐关注的博客

- blog.anthropic.com (Claude)
- openai.com/blog
- blog.google/technology/ai
- huggingface.co/blog
- lilianweng.github.io (Lilian Weng)
- karpathy.github.io

---

## 自测题

### 问题 1
Go 中如何实现一个高性能的博客聚合器？

<details>
<summary>查看答案</summary>

1. **并发抓取**：使用 goroutine + WaitGroup 并发抓取多个博客
2. **超时控制**：使用 context.WithTimeout 防止单个请求阻塞
3. **示例**：
```go
type BlogFetcher struct {
    client *http.Client
}

func (bf *BlogFetcher) FetchAll(ctx context.Context, urls []string) ([]*Article, error) {
    var wg sync.WaitGroup
    articles := make([]*Article, 0, len(urls))
    var mu sync.Mutex
    
    for _, url := range urls {
        wg.Add(1)
        go func(u string) {
            defer wg.Done()
            article, err := bf.fetchArticle(ctx, u)
            if err == nil {
                mu.Lock()
                articles = append(articles, article)
                mu.Unlock()
            }
        }(url)
    }
    
    wg.Wait()
    return articles, nil
}
```
4. **注意事项**：控制并发数，避免过多请求
5. **缓存**：使用本地缓存避免重复抓取

</details>

### 问题 2
如何评估一个技术博客的质量？

<details>
<summary>查看答案</summary>

1. **原创性**：是否有独特的见解和实践
2. **深度**：是否深入源码/原理
3. **实用性**：是否有可复用的代码/方案
4. **准确性**：技术细节是否正确
5. **可读性**：结构是否清晰，语言是否易懂
6. **时效性**：内容是否反映最新技术趋势
7. **影响力**：被引用/转发的次数

</details>

### 问题 3
Go 中如何实现一个简单的 RSS 订阅器？

<details>
<summary>查看答案</summary>

1. **XML 解析**：使用 encoding/xml 解析 RSS feed
2. **并发处理**：使用 goroutine 并行处理多个 feed
3. **示例**：
```go
type RSSFeed struct {
    XMLName xml.Name `xml:"rss"`
    Channel Channel  `xml:"channel"`
}

type Channel struct {
    Title   string    `xml:"title"`
    Items   []Item    `xml:"item"`
}

type Item struct {
    Title   string `xml:"title"`
    Link    string `xml:"link"`
    PubDate string `xml:"pubDate"`
}

func (r *RSSReader) FetchFeed(url string) (*RSSFeed, error) {
    resp, err := http.Get(url)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    var feed RSSFeed
    decoder := xml.NewDecoder(resp.Body)
    if err := decoder.Decode(&feed); err != nil {
        return nil, err
    }
    return &feed, nil
}
```
4. **注意事项**：处理 XML 命名空间，避免 XXE 攻击
5. **缓存**：使用 etag/if-modified-since 减少带宽消耗

</details>
