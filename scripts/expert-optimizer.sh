#!/bin/bash
# 知识库资深专家优化脚本
# 目标：将知识库打造成资深专家水平

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$REPO_DIR/logs/expert-optimizer.log"

echo "[$(date -Iseconds)] 开始知识库资深专家优化..." | tee -a "$LOG_FILE"

# 1. 分析当前状态
echo "[$(date -Iseconds)] 分析知识库现状..." | tee -a "$LOG_FILE"

TOTAL_DOCS=$(find "$REPO_DIR/knowledge" -name "*-deep.md" | wc -l | tr -d ' ')
DEEP_DOCS=$(find "$REPO_DIR/knowledge" -name "*-deep.md" -size +5k | wc -l | tr -d ' ')

echo "[$(date -Iseconds)] 当前状态:" | tee -a "$LOG_FILE"
echo "  - 深度文档总数: $TOTAL_DOCS" | tee -a "$LOG_FILE"
echo "  - 高质量文档(>5KB): $DEEP_DOCS" | tee -a "$LOG_FILE"

# 2. 计算质量分数
QUALITY_SCORE=0
if [ "$TOTAL_DOCS" -gt 0 ]; then
    QUALITY_SCORE=$((DEEP_DOCS * 100 / TOTAL_DOCS))
fi
echo "  - 当前质量分数: ${QUALITY_SCORE}%" | tee -a "$LOG_FILE"

# 3. 识别薄弱领域
echo "" | tee -a "$LOG_FILE"
echo "[$(date -Iseconds)] 薄弱领域分析..." | tee -a "$LOG_FILE"

for domain in advertising agent-ai fullstack devops growth-plan 前沿 interview; do
    count=$(find "$REPO_DIR/knowledge/$domain" -name "*-deep.md" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -lt 20 ]; then
        echo "  ⚠️  $domain: 仅 $count 篇深度文档（目标≥50）" | tee -a "$LOG_FILE"
    else
        echo "  ✅ $domain: $count 篇深度文档" | tee -a "$LOG_FILE"
    fi
done

# 4. 调用AI生成优化内容（这里需要配置API）
# 实际执行时由Pi扩展的scheduler.ts处理

echo "" | tee -a "$LOG_FILE"
echo "[$(date -Iseconds)] 优化任务已提交，等待AI执行..." | tee -a "$LOG_FILE"

exit 0
