# 微信读书 weread-skills 集成

## 安装
```bash
npx skills add Tencent/WeChatReading -g
```
安装到 `~/.agents/skills/weread-skills/`

## API 配置
- API Key: `WR...
- 统一入口: `POST https://i.weread.qq.com/api/agent/gateway`
- 鉴权: `Authorization: Bearer *** 常用接口
- `/shelf/sync` — 获取书架
- `/store/search` — 搜索书籍
- `/book/info` — 书籍详情
- `/book/getprogress` — 阅读进度
- `/book/bookmarklist` — 划线列表
- `/readdata/detail` — 阅读统计

## 示例
```bash
curl -X POST "https://i.weread.qq.com/api/agent/gateway" \
  -H "Authorization: Bearer *** -H "Content-Type: application/json" \
  -d '{"api_name":"/shelf/sync","skill_version":"1.0.3"}'
```

## 书架数量计算
total = books.length + albums.length + (mp 非空 ? 1 : 0)
