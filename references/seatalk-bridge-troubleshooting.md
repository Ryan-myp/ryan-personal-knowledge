# SeaTalk Bridge 排障指南

**日期**: 2025-06-05
**架构**: SeaTalk → Cloudflare Worker → SSH tunnel (localhost.run, port 8067) → Hermes bridge server

## 关键文件
- Bridge start: `~/seatalk_start.sh`
- Bridge stop: `~/seatalk_stop.sh`
- Bridge status: `~/seatalk_status.sh`
- Tunnel URL: `~/seatalk_bridge_url.txt`
- LaunchAgent: `~/Library/LaunchAgents/com.seatalk.bridge.plist`
- 一键修复: `~/seatalk_fix.sh`

## 关键配置
- Bridge port: 8067 | Hermes CLI: `~/.local/bin/hermes`
- Bot app_id: ODI1NTYyMzI4NTQ0 | Group ID: Mzk3NzkzMTc5ODE3
- Cloudflare account: 2c8358d0028184124678510c33d17f73

## 常见故障 Checklist
1. Bridge server 在监听 8067? (`curl -s http://localhost:8067/health`)
2. SSH tunnel URL 有效? (`cat ~/seatalk_bridge_url.txt`)
3. Cloudflare Worker 已更新 URL? (`hermes cron list`)
4. Worker 有 event_id 去重逻辑?
5. Worker 语法是 Service Worker (`addEventListener`), 不是 ES Module?
6. Cron job 正常运行?
7. LaunchAgent 自动启动?

## Worker 关键要点
- 去重: `event_id + Map` 防止 SeaTalk 重试导致重复回复
- 语法: `addEventListener('fetch', ...)` — 不是 `export default`
- Account ID: 用 `https://api.cloudflare.com/client/v4/accounts` 获取，不是 zone ID
- Token: CF token 保密，不要硬编码
