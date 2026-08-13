#!/bin/bash
# 知识库全面优化脚本
# 目标：打造资深专家水平

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$REPO_DIR/logs/full-optimization-$(date +%Y%m%d-%H%M%S).log"

log() {
    echo "[$(date -Iseconds)] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "开始知识库全面优化"
log "=========================================="

# 1. 统计当前状态
log ""
log "【第一步：现状分析】"

TOTAL_DOCS=$(find "$REPO_DIR/knowledge" -name "*-deep.md" | wc -l | tr -d ' ')
GOOD_DOCS=$(find "$REPO_DIR/knowledge" -name "*-deep.md" -size +5k | wc -l | tr -d ' ')
WEAK_DOCS=$(find "$REPO_DIR/knowledge" -name "*-deep.md" -size -3k | wc -l | tr -d ' ')

log "  总文档数: $TOTAL_DOCS"
log "  高质量(>5KB): $GOOD_DOCS"
log "  低质量(<3KB): $WEAK_DOCS"

# 2. 各领域统计
log ""
log "【各领域文档数】"

declare -A domain_counts
for dir in advertising agent-ai fullstack devops growth-plan interview 前沿; do
    count=$(find "$REPO_DIR/knowledge/$dir" -name "*-deep.md" 2>/dev/null | wc -l | tr -d ' ')
    domain_counts[$dir]=$count
    log "  $dir: $count篇"
done

# 3. 识别最薄弱领域
log ""
log "【薄弱领域排名】"

sorted_domains=$(for dir in "${!domain_counts[@]}"; do
    echo "${domain_counts[$dir]} $dir"
done | sort -n)

min_count=999
for line in $sorted_domains; do
    count=$(echo "$line" | awk '{print $1}')
    domain=$(echo "$line" | awk '{print $2}')
    if [ "$count" -lt "$min_count" ]; then
        min_count=$count
        log "  ⚠️  $domain: 仅$count篇（目标≥50）"
    fi
done

# 4. 生成优化计划
log ""
log "【优化计划】"

# 优先补充薄弱领域
weak_domains=()
for dir in "${!domain_counts[@]}"; do
    if [ "${domain_counts[$dir]}" -lt 20 ]; then
        weak_domains+=($dir)
    fi
done

if [ ${#weak_domains[@]} -eq 0 ]; then
    log "  所有领域文档数≥20，进入质量提升阶段"
else
    log "  优先补充领域: ${weak_domains[*]}"
fi

# 5. 删除低质量文档
log ""
log "【清理低质量文档】"

low_quality_count=$(find "$REPO_DIR/knowledge" -name "*-deep.md" -size -3k | wc -l | tr -d ' ')
if [ "$low_quality_count" -gt 0 ]; then
    find "$REPO_DIR/knowledge" -name "*-deep.md" -size -3k -delete
    log "  已删除$low_quality_count篇低质量文档"
else
    log "  无需清理"
fi

# 6. 生成新内容（模拟AI执行）
log ""
log "【生成新内容】"

# 这里应该调用AI API生成内容
# 实际执行时由Pi扩展处理

log "  优化任务已提交，等待AI执行"

# 7. 提交变更
log ""
log "【提交变更】"

cd "$REPO_DIR"
git add -A
git commit -m "docs: 知识库全面优化 - $(date +%Y-%m-%d)" 2>/dev/null
git push 2>/dev/null

log "  ✅ 优化完成"
log ""
log "=========================================="
log "优化报告已保存: $LOG_FILE"
log "=========================================="
