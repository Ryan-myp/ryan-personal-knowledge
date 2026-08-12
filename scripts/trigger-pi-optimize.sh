#!/bin/bash
# Cron触发脚本 - 通知Pi执行优化

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRIGGER_DIR="$REPO_DIR/listener/triggers"

mkdir -p "$TRIGGER_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
cat > "$TRIGGER_DIR/optimize-$TIMESTAMP.json" << INNER_EOF
{
    "type": "$(echo $1 | tr '-' '_')",
    "message": "${2:-知识库优化任务}",
    "timestamp": "$(date -Iseconds)",
    "triggered_by": "cron"
}
INNER_EOF

echo "✅ 触发文件已创建: optimize-$TIMESTAMP.json"
echo "   Pi将在下次会话时检测并执行优化"
