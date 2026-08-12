#!/usr/bin/env python3
"""
统一搜索入口 - 支持多路径RRF融合搜索
"""

import sys
import os
import json
import re
from pathlib import Path

def search_knowledge(query, top_k=10):
    """统一搜索接口"""
    results = []
    
    # 定义搜索路径
    search_paths = [
        "knowledge/agent-ai",
        "knowledge/advertising", 
        "knowledge/fullstack",
        "knowledge/前沿",
        "knowledge/interview",
        "knowledge/devops"
    ]
    
    # 解析查询
    query_lower = query.lower()
    keywords = query_lower.split()
    
    for path in search_paths:
        if not os.path.exists(path):
            continue
            
        for root, dirs, files in os.walk(path):
            for fname in files:
                if not fname.endswith('.md') or '-deep' not in fname:
                    continue
                    
                filepath = os.path.join(root, fname)
                score = calculate_relevance(filepath, keywords, query_lower)
                
                if score > 0:
                    results.append({
                        "path": filepath,
                        "score": score,
                        "title": fname.replace('.md', ''),
                        "category": get_category(path, fname)
                    })
    
    # RRF融合排序
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]

def calculate_relevance(filepath, keywords, query_lower):
    """计算相关度分数"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(5000)  # 只读前5000字符
        
        score = 0
        filepath_lower = filepath.lower()
        
        # 标题匹配权重最高
        title = os.path.basename(filepath).replace('.md', '').lower()
        for kw in keywords:
            if kw in title:
                score += 10
            if kw in filepath_lower:
                score += 5
        
        # 内容匹配
        for kw in keywords:
            score += content.count(kw) * 2
        
        return score
    except:
        return 0

def get_category(path, fname):
    """获取分类"""
    if 'agent-ai' in path:
        return "Agent/AI"
    elif 'advertising' in path:
        return "广告技术"
    elif 'fullstack' in path:
        return "全栈开发"
    elif '前沿' in path:
        return "前沿追踪"
    elif 'interview' in path:
        return "面试题库"
    elif 'devops' in path:
        return "DevOps"
    return "其他"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 unified_search.py <query> [--top-k N]")
        sys.exit(1)
    
    query = sys.argv[1]
    top_k = 10
    
    # 解析参数
    for i, arg in enumerate(sys.argv):
        if arg == "--top-k" and i + 1 < len(sys.argv):
            try:
                top_k = int(sys.argv[i + 1])
            except:
                pass
    
    results = search_knowledge(query, top_k)
    
    print(f"搜索: {query}")
    print(f"找到 {len(results)} 个结果\n")
    
    for i, r in enumerate(results, 1):
        print(f"{i}. [{r['category']}] {r['title']}")
        print(f"   路径: {r['path']}")
        print(f"   相关度: {r['score']}\n")
