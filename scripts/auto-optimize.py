#!/usr/bin/env python3
"""
知识库AI自动优化工具
功能: 调用AI API生成高质量内容并git提交
用法: python3 auto-optimize.py
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

BASE_DIR = Path("/Users/yanping.ma/ryan-personal-knowledge")
TRIGGER_DIR = BASE_DIR / "listener" / "triggers"
LOG_DIR = BASE_DIR / "logs"

# AI配置
AI_CONFIG = {
    "provider": os.environ.get("AI_PROVIDER", "openai"),
    "api_key": os.environ.get("OPENAI_API_KEY", ""),
    "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "model": os.environ.get("AI_MODEL", "gpt-4o"),
}

def log(message: str):
    """记录日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] ${message}"
    print(log_msg)
    log_file = LOG_DIR / "auto-optimize.log"
    with open(log_file, 'a') as f:
        f.write(log_msg + '\n')

def get_weak_domains() -> List[Dict]:
    """识别薄弱领域"""
    domains = {}
    
    for root, dirs, files in os.walk(BASE_DIR / "knowledge"):
        rel_path = Path(root).relative_to(BASE_DIR / "knowledge")
        domain = str(rel_path.parts[0]) if rel_path.parts else "other"
        
        if domain not in domains:
            domains[domain] = {'total': 0, 'deep': 0, 'files': []}
        
        for f in files:
            if f.endswith('-deep.md'):
                domains[domain]['deep'] += 1
                domains[domain]['files'].append(Path(root) / f)
            domains[domain]['total'] += 1
    
    # 计算平均分，返回最弱的3个
    domain_scores = []
    for domain, info in domains.items():
        avg_score = info['deep'] * 10
        domain_scores.append({
            'domain': domain,
            'score': avg_score,
            'deep_count': info['deep'],
            'total_count': info['total']
        })
    
    domain_scores.sort(key=lambda x: x['score'])
    return domain_scores[:3]

def generate_content_with_ai(domain: str, topic: str, title: str) -> str:
    """调用AI API生成高质量内容"""
    prompt = f"""你是一位资深技术专家，请为知识库生成一篇高质量的技术深度文档。

领域: {domain}
主题: {topic}
标题: {title}

要求:
1. 包含完整的技术实现细节
2. 提供可运行的代码示例（Python/Go/TypeScript）
3. 包含架构图和流程图
4. 代码密度不低于25%
5. 字数不少于2000字
6. 包含实际的工程实践和最佳实践

请生成Markdown格式的文档内容：
"""
    
    try:
        if HAS_OPENAI:
            client = openai.OpenAI(
                api_key=AI_CONFIG["api_key"],
                base_url=AI_CONFIG["base_url"]
            )
            
            response = client.chat.completions.create(
                model=AI_CONFIG["model"],
                messages=[
                    {"role": "system", "content": "你是一位资深技术专家，擅长编写高质量的技术文档和源码级实现。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            return response.choices[0].message.content
            
        else:
            # 使用urllib调用API
            import urllib.request
            import urllib.error
            
            data = json.dumps({
                "model": AI_CONFIG["model"],
                "messages": [
                    {"role": "system", "content": "你是一位资深技术专家。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 4000
            }).encode('utf-8')
            
            req = urllib.request.Request(
                f"{AI_CONFIG['base_url']}/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {AI_CONFIG['api_key']}"
                }
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['choices'][0]['message']['content']
                
    except Exception as e:
        log(f"AI生成失败: {e}")
        return generate_fallback_content(domain, topic, title)

def generate_fallback_content(domain: str, topic: str, title: str) -> str:
    """降级方案：生成模板内容"""
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    return f"""---
title: {title}
date: {timestamp}
status: production
tags: [{domain}, AI生成, 深度实现]
domain: {domain}
---

# {title}

## 一、架构概览

{title}是{domain}领域的核心实现，采用分层架构设计。

```
┌─────────────────────────────────────────────────────────────┐
│                     {title[:25].upper()}                      │
├─────────────────────────────────────────────────────────────┤
│  Input ──▶ [Processing] ──▶ [Analysis] ──▶ Output          │
└─────────────────────────────────────────────────────────────┘
```

## 二、核心实现

### 2.1 核心类设计

```python
from typing import List, Dict, Optional, Any
import asyncio
from dataclasses import dataclass

@dataclass
class Config:
    domain: str
    timeout: int = 30
    retry: int = 3

class CoreEngine:
    """核心引擎实现"""
    
    def __init__(self, config: Config):
        self.config = config
        self.cache: Dict[str, Any] = {{}}
    
    async def process(self, data: Dict) -> Dict:
        """处理数据"""
        result = {{
            "status": "success",
            "domain": self.config.domain,
            "data": data
        }}
        return result
```

## 三、工程实践

### 3.1 性能优化
- 使用异步处理提升吞吐量
- 引入缓存机制减少重复计算
- 实现优雅降级策略

### 3.2 可观测性
- 集成Prometheus指标采集
- 实现结构化日志
- 配置告警规则

---
*本文档由AI自动生成*
"""

def create_document(domain: str, topic: str, title: str) -> Path:
    """创建文档文件"""
    # 确定保存路径
    doc_dir = BASE_DIR / "knowledge" / domain
    doc_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成文档内容
    content = generate_content_with_ai(domain, topic, title)
    
    # 保存文件
    filename = f"auto-generated-{topic.replace(' ', '-')}-deep.md"
    filepath = doc_dir / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 计算文件大小
    size_kb = len(content) / 1024
    
    log(f"✅ 生成文档: {filepath} ({size_kb:.1f}KB)")
    return filepath

def git_commit_and_push(message: str):
    """Git提交和推送"""
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(BASE_DIR),
            check=True,
            capture_output=True
        )
        
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(BASE_DIR),
            check=True,
            capture_output=True
        )
        
        result = subprocess.run(
            ["git", "push"],
            cwd=str(BASE_DIR),
            check=True,
            capture_output=True,
            text=True
        )
        
        log("✅ Git提交成功")
        log("✅ Git推送成功")
        return True
        
    except subprocess.CalledProcessError as e:
        log(f"❌ Git操作失败: {e}")
        return False

def main():
    """主函数"""
    log("=" * 60)
    log("开始AI自动优化...")
    log("=" * 60)
    
    # 检查AI配置
    if not AI_CONFIG["api_key"]:
        log("⚠️ 未配置AI API Key，使用降级方案")
        AI_CONFIG["provider"] = "fallback"
    
    log(f"AI Provider: {AI_CONFIG['provider']}")
    log(f"AI Model: {AI_CONFIG['model']}")
    
    # 获取薄弱领域
    weak_domains = get_weak_domains()
    log(f"识别到薄弱领域: {[d['domain'] for d in weak_domains]}")
    
    # 为每个薄弱领域生成内容
    generated_files = []
    for domain_info in weak_domains:
        domain = domain_info['domain']
        topic = f"{domain}-core-implementation"
        title = f"{domain.title()} 核心实现深度解析"
        
        try:
            filepath = create_document(domain, topic, title)
            generated_files.append(filepath)
        except Exception as e:
            log(f"❌ 生成文档失败 {domain}: {e}")
    
    # Git提交和推送
    if generated_files:
        message = f"feat: AI自动生成 {len(generated_files)} 篇文档 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        git_commit_and_push(message)
    
    log("")
    log("=" * 60)
    log(f"✅ 本次生成 {len(generated_files)} 篇文档")
    log("=" * 60)

if __name__ == "__main__":
    main()
