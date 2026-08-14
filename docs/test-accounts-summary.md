# 四平台测试账户汇总

## 测试账户信息 (2026-08-14)

| 平台 | 测试账户 ID | 状态 | 说明 |
|------|------------|------|------|
| Meta | 2806375919473667 | ⚠️ 权限受限 | 无 ads_management 权限，需重新授权 |
| TikTok | 7397068114548195329 | ⚠️ API 部分不可用 | Campaign 列表可用，其他端点 404 |
| Google Ads | 9055507554 (子账户) | ⚠️ 环境限制 | 依赖 cryptography 库架构不兼容 (arm64 vs x86_64) |
| DV360 | 5110831 | ⚠️ 依赖问题 | 同上，Service Account JWT 签名失败 |

## 配置文件位置
- `config/ad_platform_credentials.json` — 凭证和测试账号映射
- `docs/test-accounts-summary.md` — 本文档

## 运行测试
```bash
# 综合测试
python3 scripts/test_all_api.py

# Skills API 连通性测试
python3 scripts/test_skills_api_v4.py
```

## 已知问题

### Meta
- Token 缺少 `ads_management` / `ads_read` 权限
- 需重新授权: https://www.facebook.com/dialog/oauth?client_id=&redirect_uri=&scope=ads_management,ads_read

### Google Ads
- Python 3.9 + arm64 macOS 上 `cryptography` 库有架构不兼容问题
- 解决方案: 升级 Python 到 3.10+ 或重装 cryptography
- 简化 REST 客户端可用但部分端点可能已废弃

### TikTok
- API 端点路径可能需要更新 (open_api/v1.3)
- 部分端点返回 404

### DV360
- Service Account JWT 签名依赖 cryptography 库
- 需要 Python 3.10+ 环境

## 可用功能总结
- Meta: `/me` 用户信息 ✅, `/me/accounts` 账户列表 ✅, Campaign 查询 ✅ (需正确权限的账户)
- TikTok: Campaign 列表 ✅ (有限)
- Google Ads: 本地选项数据 (Bid Strategy/Campaign Type) ✅, 需修复环境后才能测试真实 API
- DV360: 本地选项数据 (Bid Strategy/Creative Format) ✅, 需修复环境后才能测试真实 API
