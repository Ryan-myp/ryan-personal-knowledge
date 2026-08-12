#!/bin/bash
# ============================================================
# 知识库优化通知脚本
# 由Cron调用，发送通知并创建触发文件
# ============================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_SCRIPT="$REPO_DIR/listener/notify.py"
LOG_FILE="$REPO_DIR/logs/cron-notify-$(date +%Y%m%d-%H%M%S).log"

# 确保日志目录存在
mkdir -p "$REPO_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 知识库优化通知启动"

# 确定通知类型
if [[ "$1" == "weekly" ]]; then
    TYPE="weekly_deep_optimize"
    MESSAGE="每周日深度优化任务"
    PRIORITY="high"
elif [[ "$1" == "hourly" ]]; then
    TYPE="hourly_optimize"
    MESSAGE="知识库小时级优化任务"
    PRIORITY="normal"
else
    TYPE="${1:-optimize}"
    MESSAGE="${2:-知识库优化任务}"
    PRIORITY="normal"
fi

# 发送通知
log "📢 发送通知..."
python3 "$PYTHON_SCRIPT" send \
    --type "$TYPE" \
    --message "$MESSAGE" \
    --priority "$PRIORITY" \
    --metadata "{\"triggered_by\": \"cron\", \"source\": \"$0\"}" >> "$LOG_FILE" 2>&1

# 检查结果
if [ -f "$REPO_DIR/listener/notifications/latest.json" ]; then
    log "✅ 通知发送成功"
else
    log "⚠️ 请检查通知服务状态"
fi

log "📝 日志文件: $LOG_FILE"
log "=========================================="
