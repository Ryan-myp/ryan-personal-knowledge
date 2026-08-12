#!/bin/bash
# Cron自动优化脚本 - 直接执行，不依赖Pi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=== 开始知识库自动优化 ===" | tee -a logs/cron-auto.log
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a logs/cron-auto.log

# 执行优化
python3 scripts/auto-optimize.py >> logs/cron-auto.log 2>&1

# Git提交
git add -A
COMMIT_MSG="feat: 自动优化 - $(date +%Y-%m-%d\ %H:%M)"
git commit -m "$COMMIT_MSG" >> logs/cron-auto.log 2>&1
git push >> logs/cron-auto.log 2>&1

echo "" | tee -a logs/cron-auto.log
echo "=== 优化完成 ===" | tee -a logs/cron-auto.log
