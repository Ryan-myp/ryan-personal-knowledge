# 微信读书 API 参考

> 微信读书 API 接口文档

---

## 认证

```
API Key: wrk-46lTkC9XSvWb4dCvurcwBAAA
```

## 常用接口

| 接口 | 方法 | 说明 |
|------|------|------|
| /bookshelf/books | GET | 获取书架书籍 |
| /bookshelf/stats | GET | 阅读统计 |
| /book/detail | GET | 书籍详情 |
| /note/list | GET | 笔记列表 |
| /highlight/list | GET | 划线列表 |

## 参数说明

- `start`: 分页起始位置
- `count`: 每页数量（最大 50）
- `wr_api_key`: API Key

---

## Go 调用示例

```go
package weread

import (
    "encoding/json"
    "fmt"
    "io"
    "net/http"
)

const baseURL = "https://api.weread.qq.com"
const apiKey = "wrk-46lTkC9XSvWb4dCvurcwBAAA"

type Client struct {
    HTTPClient *http.Client
    APIKey     string
}

func NewClient() *Client {
    return &Client{
        HTTPClient: &http.Client{},
        APIKey:     apiKey,
    }
}

// 获取书架书籍
func (c *Client) GetBookshelf(start, count int) ([]Book, error) {
    url := fmt.Sprintf("%s/bookshelf/books?start=%d&count=%d&wr_api_key=%s",
        baseURL, start, count, c.APIKey)
    
    resp, err := c.HTTPClient.Get(url)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    body, err := io.ReadAll(resp.Body)
    if err != nil {
        return nil, err
    }
    
    var result struct {
        Books []Book `json:"books"`
    }
    if err := json.Unmarshal(body, &result); err != nil {
        return nil, err
    }
    
    return result.Books, nil
}

// 获取书籍详情
func (c *Client) GetBookDetail(bookID string) (*BookDetail, error) {
    url := fmt.Sprintf("%s/book/detail?bookId=%s&wr_api_key=%s",
        baseURL, bookID, c.APIKey)
    
    resp, err := c.HTTPClient.Get(url)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    body, err := io.ReadAll(resp.Body)
    if err != nil {
        return nil, err
    }
    
    var detail BookDetail
    if err := json.Unmarshal(body, &detail); err != nil {
        return nil, err
    }
    
    return &detail, nil
}

// 获取笔记列表
func (c *Client) GetNotes(bookID string, start, count int) ([]Note, error) {
    url := fmt.Sprintf("%s/note/list?bookId=%s&start=%d&count=%d&wr_api_key=%s",
        baseURL, bookID, start, count, c.APIKey)
    
    resp, err := c.HTTPClient.Get(url)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    body, err := io.ReadAll(resp.Body)
    if err != nil {
        return nil, err
    }
    
    var result struct {
        Notes []Note `json:"notes"`
    }
    if err := json.Unmarshal(body, &result); err != nil {
        return nil, err
    }
    
    return result.Notes, nil
}

type Book struct {
    BookID   string `json:"bookId"`
    Title    string `json:"title"`
    Author   string `json:"author"`
    Cover    string `json:"cover"`
    Reading  bool   `json:"reading"`
}

type BookDetail struct {
    BookID    string   `json:"bookId"`
    Title     string   `json:"title"`
    Author    string   `json:"author"`
    Publisher string   `json:"publisher"`
    Summary   string   `json:"summary"`
    Tags      []string `json:"tags"`
}

type Note struct {
    BookID     string `json:"bookId"`
    ChapterTitle string `json:"chapterTitle"`
    Quote      string `json:"quote"`
    Note       string `json:"note"`
    Location   int    `json:"location"`
}
```

---

## 自测题

### 问题 1
微信读书 API 的坑在哪里？

<details>
<summary>查看答案</summary>

1. **参数必须平铺在 JSON body 顶层**：不能嵌套在对象中
2. **必须带 skill_version**：版本号为 1.0.3
3. **分页参数**：start 从 0 开始，count 最大 50
4. **错误处理**：API 返回 -2003 表示权限不足
5. **最佳实践**：使用 Go struct 序列化请求参数

</details>

### 问题 2
如何用 Go 实现微信读书笔记同步到本地知识库？

<details>
<summary>查看答案</summary>

1. **流程**：获取书架 → 遍历书籍 → 获取笔记 → 写入 Markdown
2. **Go 实现**：
```go
func SyncNotes(client *weread.Client, outputDir string) error {
    books, err := client.GetBookshelf(0, 50)
    if err != nil {
        return err
    }
    
    for _, book := range books {
        notes, err := client.GetNotes(book.BookID, 0, 50)
        if err != nil {
            continue
        }
        
        // 写入 Markdown 文件
        filename := filepath.Join(outputDir, 
            sanitizeFilename(book.Title)+".md")
        
        content := fmt.Sprintf("# %s - %s\n\n", book.Title, book.Author)
        for _, note := range notes {
            content += fmt.Sprintf("## %s\n\n> %s\n\n%s\n\n---\n\n",
                note.ChapterTitle, note.Quote, note.Note)
        }
        
        os.WriteFile(filename, []byte(content), 0644)
    }
    
    return nil
}
```
3. **注意事项**：
   - 文件名需要 sanitization（去除特殊字符）
   - 大量笔记需要分页获取
   - 建议定期增量同步

</details>

---

*本文档基于微信读书 API 整理。*