#!/bin/bash
# Cron触发脚本 - 通知Pi执行优化（有AI参与）

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRIGGER_DIR="$REPO_DIR/listener/triggers"
LOG_FILE="$REPO_DIR/logs/cron-trigger.log"

mkdir -p "$TRIGGER_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
TYPE="${1:-hourly}"
MESSAGE="${2:-知识库优化任务}"

cat > "$TRIGGER_DIR/optimize-$TIMESTAMP.json" << INNER_EOF
{
    "type": "$TYPE",
    "message": "$MESSAGE",
    "timestamp": "$(date -Iseconds)",
    "triggered_by": "cron",
    "require_ai": true
}
INNER_EOF

echo "✅ 触发文件已创建: optimize-$TIMESTAMP.json" | tee -a "$LOG_FILE"
echo "   Pi将在下次会话时检测并执行AI优化" | tee -a "$LOG_FILE"
