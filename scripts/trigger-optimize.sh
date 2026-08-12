#!/bin/bash
# ============================================================
# 知识库优化触发脚本
# 由Cron调用，触发AI优化任务
# ============================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LISTENER_DIR="$REPO_DIR/listener"
TRIGGER_FILE="$LISTENER_DIR/triggers/optimize-$(date +%Y%m%d-%H%M%S).json"

# 确保触发目录存在
mkdir -p "$LISTENER_DIR/triggers"

# 创建触发文件
cat > "$TRIGGER_FILE" << 'EOF'
{
    "type": "hourly_optimize",
    "message": "知识库小时级优化任务",
    "timestamp": "TIMESTAMP",
    "triggered_by": "cron",
    "priority": "normal"
}
EOF

# 替换时间戳
sed -i '' "s/TIMESTAMP/$(date -Iseconds)/" "$TRIGGER_FILE" 2>/dev/null || \
sed -i "s/TIMESTAMP/$(date -Iseconds)/" "$TRIGGER_FILE"

echo "✅ 触发信号已发送: $TRIGGER_FILE"
echo "   监听服务将检测到并记录通知"
