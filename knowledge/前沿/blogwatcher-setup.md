---

## 自测题

### 问题 1
BlogWatcher 为什么用 Python 而不是 Go？

<details>
<summary>查看答案</summary>

1. **RSS 生态**：Python 的 feedparser 是最成熟的 RSS 解析库
2. **邮件发送**：Python 的 smtplib 简单好用
3. **脚本性质**：BlogWatcher 是低频运行的脚本，Go 的编译启动时间反而浪费
4. **Go 也适用**：如果要用 Go，可以用 gofeed 库替代

</details>

### 问题 2
RSS 在 AI 时代还有什么价值？

<details>
<summary>查看答案</summary>

1. **去中心化**：RSS 不依赖任何平台，内容所有权归用户
2. **无算法干扰**：看到最新文章，不被推荐算法过滤
3. **Agent 数据源**：LLM Agent 可以通过 RSS 获取最新信息
4. **技术博客**：大多数技术博客都提供 RSS，是获取前沿知识的好渠道

</details>