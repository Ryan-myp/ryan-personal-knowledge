#!/bin/bash
# ============================================================
# 知识库优化监听服务管理脚本
# 用法: ./listener.sh start|stop|status|trigger
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LISTENER_DIR="$SCRIPT_DIR/.."
PYTHON_SCRIPT="$LISTENER_DIR/listener/listener.py"

case "$1" in
    start)
        echo "🚀 启动监听服务..."
        nohup python3 "$PYTHON_SCRIPT" start --interval 5 > "$LISTENER_DIR/logs/listener-startup.log" 2>&1 &
        sleep 1
        if pgrep -f "listener.py start" > /dev/null; then
            echo "✅ 监听服务已启动"
            $0 status
        else
            echo "❌ 启动失败，请查看日志"
        fi
        ;;
    
    stop)
        echo "🛑 停止监听服务..."
        pkill -f "listener.py start" 2>/dev/null || true
        rm -f "$LISTENER_DIR/listener/listener.pid"
        echo "✅ 监听服务已停止"
        ;;
    
    status)
        echo "📊 监听服务状态:"
        if pgrep -f "listener.py start" > /dev/null; then
            echo "  状态: 运行中 ✅"
            PID=$(pgrep -f "listener.py start" | head -1)
            echo "  PID: $PID"
        else
            echo "  状态: 未运行 ❌"
        fi
        echo ""
        echo "  通知文件: $LISTENER_DIR/listener/notifications.jsonl"
        if [ -f "$LISTENER_DIR/listener/notifications.jsonl" ]; then
            COUNT=$(wc -l < "$LISTENER_DIR/listener/notifications.jsonl")
            echo "  通知数量: $COUNT"
        fi
        echo ""
        echo "  待处理触发: $(ls $LISTENER_DIR/listener/triggers/*.json 2>/dev/null | wc -l)"
        ;;
    
    trigger)
        TYPE="${2:-optimize}"
        MESSAGE="${3:-定时优化任务}"
        echo "📢 发送触发信号..."
        python3 "$PYTHON_SCRIPT" trigger --type "$TYPE" --message "$MESSAGE"
        ;;
    
    *)
        echo "用法: $0 {start|stop|status|trigger [type] [message]}"
        echo ""
        echo "命令:"
        echo "  start          启动监听服务"
        echo "  stop           停止监听服务"
        echo "  status         查看状态"
        echo "  trigger        手动触发"
        echo ""
        echo "示例:"
        echo "  $0 start"
        echo "  $0 trigger optimize \"知识库小时级优化\""
        ;;
esac
