# 日常学习系统

> 每日学习笔记模板 + 自测题机制

---

## 学习模板

```markdown
# [主题] — [日期]

## 今天学了什么？
- [知识点 1]
- [知识点 2]
- [知识点 3]

## 代码实现
```go
// 代码示例
```

## 自测题
### 问题 1
[问题描述]
<details>
<summary>查看答案</summary>
[答案]
</details>
```

## 明日计划
- [计划 1]
- [计划 2]
```

## 自测题机制

1. **出题**：学习时自出 3 道题
2. **答题**：1 小时后闭卷回答
3. **回顾**：24 小时后回顾答案
4. **错题**：标记错题，3 天后重测

---

## Go 实现示例

### 学习笔记系统

```go
package main

import (
    "fmt"
    "os"
    "path/filepath"
    "time"
)

type Note struct {
    Title   string
    Content string
    Date    time.Time
    Tags    []string
    Questions []Question
}

type Question struct {
    Question string
    Answer   string
    Mastered bool
}

func (n *Note) Save(outputDir string) error {
    filename := filepath.Join(outputDir, 
        sanitizeFilename(n.Title)+".md")
    
    content := fmt.Sprintf("# %s\n\n%s\n\n", n.Title, n.Content)
    for _, q := range n.Questions {
        content += fmt.Sprintf("## Q: %s\n\n%s\n\n---\n\n", 
            q.Question, q.Answer)
    }
    
    return os.WriteFile(filename, []byte(content), 0644)
}

func sanitizeFilename(name string) string {
    // 去除特殊字符
    result := ""
    for _, r := range name {
        if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') ||
           (r >= '0' && r <= '9') || r == ' ' || r == '-' || r == '_' {
            result += string(r)
        }
    }
    return result
}
```

---

*本文档基于日常学习系统整理。*
