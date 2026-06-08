# 微信读书集成

> 微信读书 API 集成方式、鉴权、接口列表、深度链接

## 概述

微信读书有官方 Python SDK (`@tencent/wxread-cli`)，通过 API Key 接入。

## 安装

```bash
pip install wxread-cli
```

或者使用 skill 提供的 `wxread` CLI 命令。

## 鉴权

通过 API Key 鉴权，存储在环境变量 `WEXREAD_API_KEY` 中。

- API Key 格式：`wrk-<base64string>`
- 获取方式：在微信读书 App 中登录，通过 SDK 获取

## 主要接口

### 书架管理

```bash
# 查看书架
wxread shelf list

# 添加书籍
wxread shelf add <book_id>

# 移除书籍
wxread shelf remove <book_id>
```

### 阅读进度

```bash
# 查看当前阅读进度
wxread progress current

# 查看某本书的进度
wxread progress get <book_id>
```

### 笔记划线

```bash
# 查看书籍笔记
wxread notes list <book_id>

# 导出笔记
wxread notes export <book_id> --format markdown

# 查看高亮
wxread highlights list <book_id>
```

### 阅读统计

```bash
# 查看阅读统计
wxread statistics daily --date 2026-06-08
wxread statistics weekly
wxread statistics monthly
```

### 书籍搜索

```bash
# 搜索书籍
wxread search "Agent设计模式"

# 查看书籍详情
wxread book info <book_id>
```

### 推荐

```bash
# 获取个性化推荐
wxread recommendations

# 查看排行榜
wxread rankings <category>
```

## 深度链接

微信读书 Deep Link 格式：

```
weread://bookDetail?bookId=<book_id>
weread://reading?bookId=<book_id>&chapterId=<chapter_id>
```

## 笔记模板

每读完一本书，在 `books/notes/` 下创建笔记：

```markdown
# <书名> — 读书笔记

**完成日期**: YYYY-MM-DD
**总阅读时长**: X 小时
**划线数**: X 条

## 核心收获

1. ...
2. ...
3. ...

## 实践要点

- ...

## 相关知识点

- ...

## 待实践

- [ ] ...
```
