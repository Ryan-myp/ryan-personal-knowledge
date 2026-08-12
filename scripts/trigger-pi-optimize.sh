#!/bin/bash
# Cron触发脚本 - 创建触发文件供Pi扩展检测

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRIGGER_DIR="$REPO_DIR/listener/triggers"

# 确保目录存在
mkdir -p "$TRIGGER_DIR"

# 创建触发文件
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
cat > "$TRIGGER_DIR/optimize-$TIMESTAMP.json" << INNER_EOF
{
    "type": "$(echo $1 | tr '-' '_')",
    "message": "${2:-知识库优化任务}",
    "timestamp": "$(date -Iseconds)",
    "triggered_by": "cron",
    "auto_execute": true
}
INNER_EOF

echo "✅ 触发文件已创建: optimize-$TIMESTAMP.json"
INNER_EOF

# 同时直接执行（如果Pi不在，就后台执行）
if [ "${3:-}" = "force" ]; then
    cd "$REPO_DIR"
    python3 scripts/auto-optimize.py >> logs/cron-auto.log 2>&1 &
    echo "⚙️  已在后台执行优化（force模式）"
fi
