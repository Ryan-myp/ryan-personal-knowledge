# 阅读统计与进度追踪

> 从微信读书 API 同步的阅读数据整合

## 读取 API 接口

### 书架同步
```bash
curl -X POST "https://i.weread.qq.com/api/agent/gateway" \
  -H "Authorization: Bearer $WEREAD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"api_name": "/shelf/sync", "skill_version": "1.0.3"}'
```

### 阅读笔记概览
```bash
curl -X POST "https://i.weread.qq.com/api/agent/gateway" \
  -H "Authorization: Bearer $WEREAD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"api_name": "/user/notebooks", "count": 50, "skill_version": "1.0.3"}'
```

### 单本书笔记
```bash
curl -X POST "https://i.weread.qq.com/api/agent/gateway" \
  -H "Authorization: Bearer $WEREAD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"api_name": "/book/bookmarklist", "bookId": "{bookId}", "skill_version": "1.0.3"}'
```

## 书架数据统计口径

| 指标 | 计算方式 |
|------|---------|
| 书架总数 | `books.length + albums.length + (mp非空?1:0)` |
| 电子书数 | `books.length` |
| 有声书数 | `albums.length` |
| 文章收藏 | `mp非空?1:0` |
| 公开阅读 | `books[secret==0].length + albums[secret==0].length` |
| 私密阅读 | `books[secret==1].length + albums[secret==1].length + (mp非空?1:0)` |

## 笔记统计口径

| 指标 | 计算方式 |
|------|---------|
| 单本书笔记总数 | `reviewCount + noteCount + bookmarkCount` |
| 总笔记数 | 所有书籍的笔记总数求和 |
| 划线数 | `noteCount` 汇总 |
| 想法/点评数 | `reviewCount` 汇总 |
| 书签数 | `bookmarkCount` 汇总 |

## 自动化脚本

### 同步书架到本地
```bash
#!/bin/bash
# sync_weread.sh
curl -s -X POST "https://i.weread.qq.com/api/agent/gateway" \
  -H "Authorization: Bearer $WEREAD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"api_name": "/shelf/sync", "skill_version": "1.0.3"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2, ensure_ascii=False))" \
  > books/weread-shelf.json
```

### 同步笔记概览
```bash
#!/bin/bash
# sync_notes.sh
curl -s -X POST "https://i.weread.qq.com/api/agent/gateway" \
  -H "Authorization: Bearer $WEREAD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"api_name": "/user/notebooks", "count": 100, "skill_version": "1.0.3"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2, ensure_ascii=False))" \
  > books/weread-notes.json
```

## 集成到知识库

1. **书架数据** → `books/weread-shelf.json`（定期同步）
2. **笔记概览** → `books/weread-notes.json`（定期同步）
3. **蒸馏笔记** → `books/notes/{book-name}.md`（手动创建）
4. **知识文档** → `knowledge/agent-ai/weread-*.md`（蒸馏后归档）
