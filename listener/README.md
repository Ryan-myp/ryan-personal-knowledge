# Ryan Knowledge Base - AI触发优化系统

## 系统架构

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Cron :30  │────▶│ notify脚本       │────▶│ macOS通知   │
│  定时触发   │     │ notify-optimize  │     │ 桌面弹窗    │
└─────────────┘     └──────────────────┘     └──────┬──────┘
                                                      │
                                                      ▼
                                            ┌──────────────────┐
                                            │  通知文件        │
                                            │  notifications/  │
                                            └────────┬─────────┘
                                                     │
                                                     ▼
                                          ┌──────────────────┐
                                          │  AI检测通知      │
                                          │  check-*.py     │
                                          └────────┬─────────┘
                                                   │
                                                   ▼
                                          ┌──────────────────┐
                                          │  AI执行优化      │
                                          │  生成内容        │
                                          └──────────────────┘
```

## 核心组件

| 组件 | 文件 | 用途 |
|------|------|------|
| 通知服务 | `listener/notify.py` | 发送多通道通知 |
| Cron脚本 | `scripts/notify-optimize.sh` | Cron触发通知 |
| 检查工具 | `listener/check-optimization.py` | AI检测通知 |

## 工作流程

1. **Cron触发** (每小时:30)
   - 执行 `scripts/notify-optimize.sh`
   - 发送macOS桌面通知
   - 创建通知文件 `listener/notifications/*.json`

2. **AI检测** (每次对话启动)
   - 运行 `python3 listener/check-optimization.py`
   - 检查是否有待处理通知
   - 在对话中告知用户

3. **AI执行** (检测到通知后)
   - 读取通知内容
   - 执行相应的优化任务
   - 标记通知为已处理

## 通知渠道

- ✅ **macOS桌面通知** - 弹窗提醒
- ✅ **文件记录** - JSON持久化
- ✅ **Pi内部事件** - 供AI检查
- ⬜ **Telegram Bot** - 需配置环境变量
- ⬜ **飞书Webhook** - 需配置环境变量

## Cron配置

```bash
# 每小时30分触发优化通知
30 * * * * cd /Users/yanping.ma/ryan-personal-knowledge && bash scripts/notify-optimize.sh hourly >> logs/cron-notify-hourly.log 2>&1

# 每周日02:00触发深度优化通知
0 2 * * 0 cd /Users/yanping.ma/ryan-personal-knowledge && bash scripts/notify-optimize.sh weekly >> logs/cron-notify-weekly.log 2>&1
```

## 手动测试

```bash
# 发送测试通知
python3 listener/notify.py send --type test --message "测试通知" --priority high

# 查看待处理通知
python3 listener/notify.py list

# 清理通知
python3 listener/notify.py clear

# 模拟Cron触发
bash scripts/notify-optimize.sh hourly
```

## AI使用方式

每次启动对话时，我会自动检查是否有待处理的通知：

```bash
python3 listener/check-optimization.py
```

如果有通知，我会在对话中告诉你：
> "📚 检测到知识库优化任务，现在开始执行..."

---

**部署时间**: 2026-08-13
**版本**: v1.0
