#!/bin/bash
# ============================================================
# 知识库优化守护进程管理脚本
# 用法: ./guardian.sh start|stop|status|restart
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR/.."
PYTHON_SCRIPT="$REPO_DIR/listener/guardian.py"

case "$1" in
    start)
        echo "🚀 启动知识库优化守护进程..."
        if pgrep -f "guardian.py start" > /dev/null; then
            echo "⚠️ 守护进程已在运行"
            exit 0
        fi
        
        nohup python3 "$PYTHON_SCRIPT" start > "$REPO_DIR/logs/guardian-startup.log" 2>&1 &
        sleep 2
        
        if pgrep -f "guardian.py start" > /dev/null; then
            echo "✅ 守护进程已启动"
            $0 status
        else
            echo "❌ 启动失败，请查看日志: $REPO_DIR/logs/guardian-startup.log"
        fi
        ;;
    
    stop)
        echo "🛑 停止知识库优化守护进程..."
        pkill -f "guardian.py start" 2>/dev/null || true
        rm -f "$REPO_DIR/listener/guardian.pid"
        echo "✅ 守护进程已停止"
        ;;
    
    status)
        echo "📊 守护进程状态:"
        if pgrep -f "guardian.py start" > /dev/null; then
            echo "  状态: 运行中 ✅"
            PID=$(pgrep -f "guardian.py start" | head -1)
            echo "  PID: $PID"
        else
            echo "  状态: 未运行 ❌"
        fi
        echo ""
        echo "  通知文件: $REPO_DIR/listener/notifications/"
        NOTIFY_COUNT=$(ls "$REPO_DIR/listener/notifications/notify_*.json" 2>/dev/null | wc -l | tr -d ' ')
        echo "  待处理通知: $NOTIFY_COUNT"
        echo ""
        echo "  日志文件: $REPO_DIR/logs/guardian.log"
        echo ""
        echo "  最近日志:"
        tail -5 "$REPO_DIR/logs/guardian.log" 2>/dev/null || echo "  (无日志)"
        ;;
    
    restart)
        $0 stop
        sleep 1
        $0 start
        ;;
    
    *)
        echo "用法: $0 {start|stop|status|restart}"
        echo ""
        echo "命令:"
        echo "  start     启动守护进程"
        echo "  stop      停止守护进程"
        echo "  status    查看状态"
        echo "  restart   重启守护进程"
        ;;
esac
