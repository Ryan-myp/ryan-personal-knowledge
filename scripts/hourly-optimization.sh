#!/bin/bash
# 每小时完整优化脚本
set -e
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$REPO_DIR/logs/hourly-optimize-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$REPO_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 开始小时级完整优化"

# Step 1: 质量扫描
log "📊 Step 1: 质量扫描..."
python3 "$REPO_DIR/scripts/quality_scorer.py" > /tmp/hourly_scan.json 2>&1 || true

# Step 2: 生成新文档（从薄弱领域开始）
log "🔧 Step 2: 内容增强..."
python3 "$REPO_DIR/scripts/content_generator.py" 2>&1 | tee -a "$LOG_FILE"

# Step 3: 质量检查
log "📈 Step 3: 质量验证..."
python3 << 'PYEOF'
import os
new_files = []
for root, dirs, files in os.walk('knowledge'):
    for fn in files:
        if fn.endswith('-deep.md') and '2026-08-13' in fn:
            new_files.append(fn)
print(f"新增文档: {len(new_files)}篇")
for f in new_files[:5]:
    size = os.path.getsize(f'knowledge/{f}')
    print(f"  - {f}: {size//1024}KB")
PYEOF

# Step 4: Git提交
log "📝 Step 4: Git提交..."
cd "$REPO_DIR"
git add -A
if git diff --cached --quiet; then
    log "无变更，跳过提交"
else
    git commit -m "feat: 小时级优化 - $(date '+%Y-%m-%d %H:%M')" 2>&1 | head -5 || true
fi

log "✅ 小时级优化完成"
