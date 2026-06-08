# 微信读书 weread API 调用规范

> 创建日期: 20260608  
> 分类: weread  
> 标签: #微信读书 #API #weread #技能修复

## 核心规则

### 1. 必须参数
- `api_name`: 接口名（如 `/shelf/sync`、`/store/search`）
- `skill_version`: 当前版本 `"1.0.3"`（必须每次传）

### 2. 参数位置
**业务参数必须和 `api_name`、`skill_version` 放在同一层（JSON body 顶层），不要包在 `params`、`data`、`body` 等对象里。**

✅ **正确**:
```json
{
    "api_name": "/store/search",
    "keyword": "Kafka",
    "skill_version": "1.0.3"
}
```

❌ **错误**:
```json
{
    "api_name": "/store/search",
    "body": {
        "keyword": "Kafka"
    },
    "skill_version": "1.0.3"
}
```
→ 会返回 `errcode: -2003` 缺少必填参数

### 3. 请求格式
```bash
curl -X POST "https://i.weread.qq.com/api/agent/gateway" \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"api_name": "/store/search", "keyword": "三体", "count": 10, "skill_version": "1.0.3"}'
```

## Python 调用模板

```python
import requests

api_key = "wrk-46lTkC9XSvWb4dCvurcwBAAA"
url = "https://i.weread.qq.com/api/agent/gateway"
headers = {
    "Authorization": "Bearer " + api_key,
    "Content-Type": "application/json"
}

def call_weread(api_name, **kwargs):
    """
    调用微信读书 API
    :param api_name: 接口名，如 "/shelf/sync"
    :param kwargs: 业务参数，平铺在 body 顶层
    :return: JSON 响应
    """
    body = {"api_name": api_name, "skill_version": "1.0.3"}
    body.update(kwargs)  # 业务参数平铺在顶层
    r = requests.post(url, headers=headers, json=body, timeout=15)
    return r.json()
```

## 常用接口

### 1. 书架 `/shelf/sync`
```python
call_weread("/shelf/sync")
# 返回: books[], albums[], mp[]
# 总数 = len(books) + len(albums) + (1 if mp else 0)
```

### 2. 搜索 `/store/search`
```python
call_weread("/store/search", keyword="Kafka", scope=10, count=10)
# scope: 0=全部, 10=电子书, 20=网文, 30=杂志, 40=漫画
# 返回: results[0].books[]
```

### 3. 阅读统计 `/readdata/detail`
```python
call_weread("/readdata/detail", mode="monthly")
# mode: weekly=本周, monthly=本月, annually=本年, overall=总计
# 返回: 阅读时长、天数、偏好分析等
```

### 4. 书籍详情 `/book/info`
```python
call_weread("/book/info", bookId="3300044310")
# 返回: title, author, chapters[], intro, rating 等
```

### 5. 笔记划线 `/user/notebooks`
```python
call_weread("/user/notebooks", count=20)
# 返回: totalBookCount, noteCount, notebooks[]
```

### 6. 推荐好书 `/book/recommend`
```python
call_weread("/book/recommend", count=12, maxIdx=0)
# 返回: books[]，每本有 title, reason, bookId 等
```

## 常见错误

| errcode | 原因 | 解决 |
|---------|------|------|
| -2003 | 缺少 api_name 或 keyword | 传 `api_name` 和正确的业务参数 |
| -2003 | 参数在 `body` 内 | 参数必须平铺在 body 顶层 |
| -2013 | 鉴权失败 | API Key 无效或过期 |

## 深度链接

| 场景 | URL Schema |
|------|-----------|
| 打开书籍 | `weread://reading?bId={bookId}` |
| 跳转到章节 | `weread://reading?bId={bookId}&chapterUid={chapterUid}` |
| 跳转到划线 | `weread://bestbookmark?bookId={bookId}&chapterUid={chapterUid}&rangeStart={start}&rangeEnd={end}&userVid={vid}` |

## 注意事项
- 所有 Unix 时间戳须转为 YYYY-MM-DD 展示
- 阅读时长单位为秒，展示时转为"X小时Y分钟"
- 书架总数必须包含 albums（有声书）
- 如果回包出现 `upgrade_info`，必须按指引升级后再继续
