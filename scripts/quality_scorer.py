import os, re, json

def score_doc(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    total = len(lines)
    size = os.path.getsize(path)
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
    score = min(100, size // 100 + density)
    return {'path': path, 'size': size, 'density': density, 'score': score}

results = []
for root, dirs, files in os.walk('knowledge'):
    for fn in files:
        if fn.endswith('-deep.md'):
            results.append(score_doc(os.path.join(root, fn)))

# 按领域分组
domains = {}
for r in results:
    parts = r['path'].split('/')
    domain = f"{parts[1]}/{parts[2]}" if len(parts) > 2 else parts[1]
    if domain not in domains:
        domains[domain] = []
    domains[domain].append(r)

# 计算各领域平均分
domain_avg = {}
for d, docs in domains.items():
    avg_score = sum(doc['score'] for doc in docs) // len(docs)
    domain_avg[d] = {'total': len(docs), 'avg_score': avg_score}

# 输出JSON
output = {'total': len(results), 'domains': domain_avg}
with open('/tmp/quality_stats.json', 'w') as f:
    json.dump(output, f, indent=2)
print(f"扫描完成: {len(results)}篇文档")
for d, info in sorted(domain_avg.items(), key=lambda x: x[1]['avg_score']):
    print(f"  {d}: {info['avg_score']}分 ({info['total']}篇)")
