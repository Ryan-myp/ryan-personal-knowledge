#!/bin/bash
# ============================================================
# 知识库自动优化工具
# 功能: 质量检查、低质文档清理、内容增强建议
# 作者: Ryan
# 版本: v2.0
# ============================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$REPO_DIR/logs/optimizer-$(date +%Y%m%d-%H%M%S).log"
QUALITY_REPORT="$REPO_DIR/knowledge/plans/quality-report-$(date +%Y%m%d).md"

mkdir -p "$REPO_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ============================================================
# 第一步: 全局质量扫描
# ============================================================
scan_quality() {
    log "📊 开始全局质量扫描..."
    
    python3 << 'PYEOF'
import os
import re
from datetime import datetime

def analyze_doc(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    total = len(lines)
    size = os.path.getsize(path)
    
    # 计算代码密度
    in_code = False
    code_lines = 0
    for line in lines:
        s = line.strip()
        if s.startswith('```'):
            in_code = not in_code
            continue
        if in_code and s:
            code_lines += 1
    density = code_lines * 100 // total if total > 0 else 0
    
    # 质量评分
    score = 0
    
    # 文件大小 (25分)
    if size >= 15000: score += 25
    elif size >= 10000: score += 20
    elif size >= 5000: score += 15
    elif size >= 2000: score += 10
    else: score += 5
    
    # 代码密度 (30分)
    if density >= 35: score += 30
    elif density >= 25: score += 25
    elif density >= 15: score += 20
    elif density >= 10: score += 15
    else: score += 10
    
    # 结构完整性 (25分)
    has_frontmatter = content.startswith('---\n')
    has_sections = content.count('## ') >= 2
    has_code_blocks = content.count('```') >= 4
    has_qa = bool(re.search(r'Q\d+', content))
    has_table = '|' in content
    
    if has_frontmatter: score += 5
    if has_sections: score += 5
    if has_code_blocks: score += 5
    if has_qa: score += 5
    if has_table: score += 5
    
    # 实战价值 (20分)
    has_examples = any(kw in content for kw in ['example', '示例', '实战', '生产'])
    has_benchmark = any(kw in content for kw in ['benchmark', '性能', '压测'])
    has_debug = any(kw in content for kw in ['debug', '排障', '故障'])
    
    if has_examples: score += 7
    if has_benchmark: score += 7
    if has_debug: score += 6
    
    return {
        'path': path,
        'name': os.path.basename(path).replace('.md', ''),
        'size': size,
        'lines': total,
        'code_density': density,
        'score': score,
        'has_qa': has_qa,
        'has_code': has_code_blocks,
    }

# 扫描所有deep文档
results = []
for root, dirs, files in os.walk('knowledge'):
    for fn in files:
        if fn.endswith('-deep.md'):
            results.append(analyze_doc(os.path.join(root, fn)))

# 分类统计
excellent = [r for r in results if r['score'] >= 80]
good = [r for r in results if 60 <= r['score'] < 80]
pass_ = [r for r in results if 40 <= r['score'] < 60]
fail = [r for r in results if r['score'] < 40]

low_quality = [r for r in results if r['size'] < 2000]
no_code = [r for r in results if not r['has_code'] and r['size'] >= 2000]
no_qa = [r for r in results if not r['has_qa'] and r['size'] >= 5000]

# 按领域统计
domain_stats = {}
for r in results:
    domain = '/'.join(r['path'].split('/')[:3])
    if domain not in domain_stats:
        domain_stats[domain] = {'total': 0, 'excellent': 0, 'avg_score': 0, 'scores': []}
    domain_stats[domain]['total'] += 1
    domain_stats[domain]['scores'].append(r['score'])
    if r['score'] >= 80:
        domain_stats[domain]['excellent'] += 1

for d in domain_stats.values():
    d['avg_score'] = sum(d['scores']) // len(d['scores']) if d['scores'] else 0

# 输出报告
print("=" * 70)
print("              知识库质量扫描报告")
print("=" * 70)
print(f"总文档数: {len(results)}")
print(f"平均质量分: {sum(r['score'] for r in results) // len(results)}/100")
print(f"平均代码密度: {sum(r['code_density'] for r in results) // len(results)}%")
print()
print("质量分布:")
print(f"  优秀(≥80):  {len(excellent)}篇 ({len(excellent)*100//len(results)}%)")
print(f"  良好(60-79): {len(good)}篇 ({len(good)*100//len(results)}%)")
print(f"  及格(40-59): {len(pass_)}篇 ({len(pass_)*100//len(results)}%)")
print(f"  不及格(<40): {len(fail)}篇 ({len(fail)*100//len(results)}%)")
print()
print("问题文档:")
print(f"  低质量(<2KB): {len(low_quality)}篇 - 建议删除")
print(f"  无代码块: {len(no_code)}篇 - 建议补充源码")
print(f"  无自测题: {len(no_qa)}篇 - 建议补充QA")
print()
print("领域健康度:")
for domain, stats in sorted(domain_stats.items(), key=lambda x: x[1]['avg_score'], reverse=True):
    bar = '█' * min(stats['excellent'] // 5, 10)
    print(f"  {domain:30s}: {stats['avg_score']:3d}分 | 优秀:{stats['excellent']:3d}篇 {bar}")
print()

# 保存JSON结果供后续使用
import json
with open('/tmp/knowledge_scan_result.json', 'w') as f:
    json.dump({
        'total': len(results),
        'excellent': len(excellent),
        'good': len(good),
        'pass': len(pass_),
        'fail': len(fail),
        'low_quality_count': len(low_quality),
        'no_code_count': len(no_code),
        'no_qa_count': len(no_qa),
        'avg_score': sum(r['score'] for r in results) // len(results),
        'avg_density': sum(r['code_density'] for r in results) // len(results),
    }, f)
PYEOF
}

# ============================================================
# 第二步: 清理低质量文档
# ============================================================
clean_low_quality() {
    log "🧹 开始清理低质量文档..."
    
    local count=0
    local dry_run=${1:-false}
    
    find knowledge -name "*-deep.md" -type f -size -2k 2>/dev/null | while read file; do
        if [ "$dry_run" = "true" ]; then
            log "  [预览] 待删除: $file ($(wc -c < "$file" | tr -d ' ')B)"
        else
            rm "$file"
            log "  ✅ 已删除: $(basename $file)"
        fi
        count=$((count + 1))
    done
    
    log "清理完成，共处理 $count 篇文档"
}

# ============================================================
# 第三步: 识别需要增强的文档
# ============================================================
identify_enhancements() {
    log "🔍 识别需要增强的文档..."
    
    python3 << 'PYEOF'
import os
import json

with open('/tmp/knowledge_scan_result.json', 'r') as f:
    stats = json.load(f)

# 找需要补充代码的文档
print("=" * 70)
print("              文档增强建议列表")
print("=" * 70)
print()

# 无代码块但需要代码的文档
print("【需要补充代码示例】")
for root, dirs, files in os.walk('knowledge'):
    for fn in files:
        if fn.endswith('-deep.md'):
            path = os.path.join(root, fn)
            size = os.path.getsize(path)
            if size >= 3000:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if content.count('```') < 4:
                    print(f"  ⚠️  {path.replace('knowledge/', '')} ({size//1024}KB)")
print()

# 无自测题的大文档
print("【需要补充自测题】")
for root, dirs, files in os.walk('knowledge'):
    for fn in files:
        if fn.endswith('-deep.md'):
            path = os.path.join(root, fn)
            size = os.path.getsize(path)
            if size >= 5000:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if 'Q' not in content and 'qa' not in content.lower():
                    print(f"  ⚠️  {path.replace('knowledge/', '')} ({size//1024}KB)")
print()

# 前沿追踪最新内容建议
print("【前沿追踪更新建议】")
frontier_files = []
for root, dirs, files in os.walk('knowledge/前沿'):
    for fn in files:
        if fn.endswith('-deep.md'):
            frontier_files.append(os.path.join(root, fn))

print(f"  当前前沿文档: {len(frontier_files)}篇")
print("  建议新增主题:")
print("    - LLM Agent 2026 Q3 趋势更新")
print("    - MCP 协议最新进展")
print("    - RAG 4.0 技术演进")
print("    - Multi-Agent 协作模式")
print("    - AI 安全与对齐最新研究")
print()

# 面试题库更新建议
print("【面试题库更新建议】")
interview_files = []
for root, dirs, files in os.walk('knowledge/interview'):
    for fn in files:
        if fn.endswith('-deep.md'):
            interview_files.append(os.path.join(root, fn))

print(f"  当前面试文档: {len(interview_files)}篇")
print("  建议新增主题:")
print("    - Go 1.22+ 新特性面试")
print("    - Agent 架构设计面试")
print("    - 广告系统高级面试")
print("    - 分布式系统一致性面试")
print()
PYEOF
}

# ============================================================
# 第四步: 生成优化报告
# ============================================================
generate_report() {
    log "📝 生成质量报告..."
    
    python3 << 'PYEOF'
import json
from datetime import datetime

with open('/tmp/knowledge_scan_result.json', 'r') as f:
    stats = json.load(f)

report = f"""# 知识库质量报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 一、总体健康度

| 指标 | 数值 | 评级 |
|------|------|------|
| 总文档数 | {stats['total']}篇 | - |
| 平均质量分 | {stats['avg_score']}/100 | {'优秀' if stats['avg_score'] >= 70 else '良好' if stats['avg_score'] >= 50 else '待提升'} |
| 平均代码密度 | {stats['avg_density']}% | {'优秀' if stats['avg_density'] >= 30 else '良好' if stats['avg_density'] >= 20 else '待提升'} |

## 二、质量分布

| 等级 | 数量 | 占比 | 健康度 |
|------|------|------|--------|
| 优秀(≥80) | {stats['excellent']}篇 | {stats['excellent']*100//max(stats['total'],1)}% | {'⭐★★★★★' if stats['excellent'] > 100 else '⭐★★★' if stats['excellent'] > 50 else '⭐★★'} |
| 良好(60-79) | {stats['good']}篇 | {stats['good']*100//max(stats['total'],1)}% | - |
| 及格(40-59) | {stats['pass']}篇 | {stats['pass']*100//max(stats['total'],1)}% | - |
| 不及格(<40) | {stats['fail']}篇 | {stats['fail']*100//max(stats['total'],1)}% | {'⚠️ 需改进' if stats['fail'] > 50 else '✓'} |

## 三、问题清单

| 问题类型 | 数量 | 建议操作 |
|----------|------|----------|
| 低质量(<2KB) | {stats['low_quality_count']}篇 | 删除或合并 |
| 无代码块 | {stats['no_code_count']}篇 | 补充源码示例 |
| 无自测题 | {stats['no_qa_count']}篇 | 补充QA |

## 四、综合评分

```
健康度 = 广度×30% + 深度×40% + 实用性×30%

广度(6大领域):      90/100 × 30% = 27.0
深度(源码级文档):   {min(100, stats['avg_score'])}/100 × 40% = {min(40, stats['avg_score']*0.4):.1f}
实用性(代码+案例):  {min(100, stats['avg_density']*2 + 20)}/100 × 30% = {min(30, (stats['avg_density']*2 + 20)*0.3):.1f}

综合健康度: {27.0 + min(40, stats['avg_score']*0.4) + min(30, (stats['avg_density']*2 + 20)*0.3):.0f}/100
```

## 五、下一步行动

"""

if stats['low_quality_count'] > 100:
    report += "- [ ] 批量删除低质量占位符文档\n"
if stats['no_code_count'] > 20:
    report += "- [ ] 为无代码块文档补充源码示例\n"
if stats['no_qa_count'] > 100:
    report += "- [ ] 为文档补充自测题\n"

report += """
---
**下次检查**: 建议每周执行一次
**目标**: 3个月内达到90+/100健康度
"""

    with open('knowledge/plans/quality-report-current.md', 'w') as f:
        f.write(report)
    
    print(f"✅ 报告已生成: knowledge/plans/quality-report-current.md")
PYEOF
}

# ============================================================
# 主流程
# ============================================================
main() {
    log "=========================================="
    log "知识库自动优化工具启动"
    log "=========================================="
    log ""
    
    cd "$REPO_DIR"
    
    # Step 1: 质量扫描
    scan_quality
    log "✅ 质量扫描完成"
    log ""
    
    # Step 2: 清理低质量文档
    clean_low_quality
    log "✅ 低质量文档清理完成"
    log ""
    
    # Step 3: 识别增强需求
    identify_enhancements
    log "✅ 增强需求分析完成"
    log ""
    
    # Step 4: 生成报告
    generate_report
    log "✅ 质量报告生成完成"
    log ""
    
    log "=========================================="
    log "优化完成！日志: $LOG_FILE"
    log "=========================================="
}

# 执行
main "$@"
