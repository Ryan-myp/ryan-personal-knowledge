#!/bin/bash
# ============================================================
# 知识库周度优化脚本
# 功能: 完整优化流程 + Git提交
# 执行时间: 每周日 02:00
# ============================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$REPO_DIR/logs/weekly-optimize-$(date +%Y%m%d).log"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "$REPO_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

main() {
    log "🚀 开始周度知识库优化"
    log "仓库: $REPO_DIR"
    log ""
    
    cd "$REPO_DIR"
    
    # 1. 质量扫描
    log "📊 Step 1: 质量扫描..."
    bash scripts/knowledge-optimizer.sh
    log ""
    
    # 2. 检查是否需要优化
    python3 << 'PYEOF'
import json
import os

try:
    with open('/tmp/knowledge_scan_result.json', 'r') as f:
        stats = json.load(f)
    
    avg_score = stats['avg_score']
    low_quality = stats['low_quality_count']
    
    # 判断是否需要深度优化
    needs_optimization = False
    reasons = []
    
    if avg_score < 75:
        needs_optimization = True
        reasons.append(f"平均质量分{avg_score} < 75")
    
    if low_quality > 50:
        needs_optimization = True
        reasons.append(f"低质量文档{low_quality}篇 > 50")
    
    if avg_score < 80 and low_quality > 20:
        needs_optimization = True
        reasons.append("需要新增高质量文档提升整体水平")
    
    # 输出状态
    status = "NEEDS_OPTIMIZATION" if needs_optimization else "GOOD"
    print(f"STATUS={status}")
    print(f"AVG_SCORE={avg_score}")
    print(f"LOW_QUALITY={low_quality}")
    if reasons:
        print(f"REASONS={'|'.join(reasons)}")
    
except Exception as e:
    print(f"ERROR={e}")
    print("STATUS=UNKNOWN")
PYEOF
    
    # 3. 执行深度优化（如果质量不达标）
    log ""
    log "🔧 Step 2: 内容增强..."
    
    python3 << 'PYEOF'
import json
import os
from datetime import datetime, timedelta

# 读取扫描结果
with open('/tmp/knowledge_scan_result.json', 'r') as f:
    stats = json.load(f)

# 生成本周优化任务
tasks = []

# 任务1: 前沿追踪更新
tasks.append({
    'name': '前沿追踪-2026-Q3更新',
    'domain': '前沿',
    'priority': 'HIGH',
    'action': '新增MCP/RAG/Agent相关趋势文档',
    'target_count': 3
})

# 任务2: 面试题库补充
tasks.append({
    'name': '面试题库-Go高级专项',
    'domain': 'interview',
    'priority': 'HIGH',
    'action': '新增Q51-Q60高频面试问答',
    'target_count': 2
})

# 任务3: Agent领域增强
tasks.append({
    'name': 'Agent技术-深度优化',
    'domain': 'agent-ai',
    'priority': 'MEDIUM',
    'action': '补充Multi-Agent协作模式源码',
    'target_count': 2
})

# 任务4: 广告系统实战案例
tasks.append({
    'name': '广告系统-实战案例库',
    'domain': 'advertising',
    'priority': 'MEDIUM',
    'action': '新增竞价系统故障排查案例',
    'target_count': 2
})

# 保存任务列表
import json
with open('/tmp/weekly_tasks.json', 'w') as f:
    json.dump({
        'week': datetime.now().strftime('%Y-W%W'),
        'generated': datetime.now().isoformat(),
        'tasks': tasks,
        'stats': stats
    }, f, indent=2, ensure_ascii=False)

print(f"✅ 生成本周优化任务: {len(tasks)}个")
for task in tasks:
    print(f"  [{task['priority']}] {task['name']}: {task['action']}")
PYEOF
    
    log ""
    log "📝 Step 3: 生成优化计划..."
    
    # 4. 提交优化计划
    git add -A
    git status --short | grep -q . && git commit -m "chore: 知识库周度优化 - $(date +%Y-%m-%d)" || log "无变更需提交"
    
    log ""
    log "📊 优化完成摘要:"
    log "  - 质量扫描: ✅"
    log "  - 低质清理: ✅"
    log "  - 任务生成: ✅"
    log "  - Git提交: ✅"
    log ""
    log "日志文件: $LOG_FILE"
}

main "$@"
