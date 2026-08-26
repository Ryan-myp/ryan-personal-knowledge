#!/usr/bin/env python3
"""
LLM Wiki 知识库查询工具 - Karpathy 风格
支持从知识库查询专家知识、最佳实践、常见问题等
"""

import json
import os
import sys
from typing import Dict, List, Optional, Any
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from knowledge_base import get_wiki_kb, KnowledgeType


class WikiQueryTool:
    """知识库查询工具 - 查询专家知识"""
    
    def __init__(self, base_path: str = None):
        self.kb = get_wiki_kb(base_path)
    
    def search(self, query: str, platforms: List[str] = None, 
               knowledge_types: List[str] = None, limit: int = 10) -> List[Dict]:
        """搜索知识库"""
        results = []
        query_lower = query.lower()
        
        # 搜索平台知识
        for platform, pkb in self.kb.platform_kbs.items():
            if platforms and platform not in platforms:
                continue
            for kb_name, kb_obj in pkb.items():
                for entry_id, entry in kb_obj.entries.items():
                    # 过滤知识类型
                    if knowledge_types:
                        type_str = entry.knowledge_type.value if hasattr(entry.knowledge_type, 'value') else str(entry.knowledge_type)
                        if type_str not in knowledge_types:
                            continue
                    
                    # 搜索内容
                    content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                    if query_lower in content_str or query_lower in entry_id.lower():
                        results.append({
                            'entry_id': entry.entry_id,
                            'platform': entry.platform,
                            'knowledge_type': entry.knowledge_type.value if hasattr(entry.knowledge_type, 'value') else str(entry.knowledge_type),
                            'content': entry.content,
                            'source': entry.source.value if hasattr(entry.source, 'value') else str(entry.source),
                            'tags': entry.tags,
                        })
                    
                    if len(results) >= limit:
                        return results
        
        # 搜索经验知识
        for kb_name, kb_obj in self.kb.expertise_kbs.items():
            for entry_id, entry in kb_obj.entries.items():
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str or query_lower in entry_id.lower():
                    results.append({
                        'entry_id': entry.entry_id,
                        'platform': entry.platform,
                        'knowledge_type': kb_name,
                        'content': entry.content,
                        'source': entry.source.value if hasattr(entry.source, 'value') else str(entry.source),
                        'tags': entry.tags,
                    })
                
                if len(results) >= limit:
                    return results
        
        return results
    
    def get_best_practices(self, platform: str = None, 
                          business_type: str = None,
                          limit: int = 10) -> List[Dict]:
        """获取最佳实践"""
        results = []
        if 'best_practices' in self.kb.expertise_kbs:
            for entry_id, entry in self.kb.expertise_kbs['best_practices'].entries.items():
                if platform and entry.platform != 'all' and entry.platform != platform:
                    continue
                results.append(entry.content)
                if len(results) >= limit:
                    break
        return results
    
    def get_error_solutions(self, error_code: str, platform: str = None) -> List[str]:
        """获取错误解决方案"""
        results = []
        if 'error_patterns' in self.kb.expertise_kbs:
            for entry_id, entry in self.kb.expertise_kbs['error_patterns'].entries.items():
                content = entry.content
                if isinstance(content, dict):
                    if error_code.lower() in str(content.get('error_code', '')).lower():
                        results.append(content.get('solution', ''))
                elif isinstance(content, str):
                    if error_code.lower() in content.lower():
                        results.append(content)
        return results
    
    def get_workflow(self, platform: str, workflow_type: str = None) -> Dict:
        """获取工作流"""
        if platform not in self.kb.platform_kbs:
            return {'platform': platform, 'workflows': []}
        
        workflows = []
        if 'WORKFLOW' in self.kb.platform_kbs[platform]:
            for entry_id, entry in self.kb.platform_kbs[platform]['WORKFLOW'].entries.items():
                workflows.append(entry.content)
        
        return {'platform': platform, 'workflows': workflows}
    
    def get_stats(self) -> Dict:
        """获取知识库统计"""
        stats = {
            'platforms': {},
            'expertise': {},
            'total': 0
        }
        
        for platform, pkb in self.kb.platform_kbs.items():
            stats['platforms'][platform] = {}
            for kb_name, kb_obj in pkb.items():
                count = len(kb_obj.entries)
                stats['platforms'][platform][kb_name] = count
                stats['total'] += count
        
        for kb_name, kb_obj in self.kb.expertise_kbs.items():
            count = len(kb_obj.entries)
            stats['expertise'][kb_name] = count
            stats['total'] += count
        
        return stats


# 全局实例
_tool_instance = None

def get_wiki_query_tool() -> WikiQueryTool:
    global _tool_instance
    if _tool_instance is None:
        _tool_instance = WikiQueryTool()
    return _tool_instance


def wiki_search(query: str, platforms: List[str] = None, 
                knowledge_types: List[str] = None, limit: int = 10) -> List[Dict]:
    """便捷函数：搜索知识库"""
    return get_wiki_query_tool().search(query, platforms, knowledge_types, limit)


def wiki_get_best_practices(platform: str = None, 
                           business_type: str = None,
                           limit: int = 10) -> List[Dict]:
    """便捷函数：获取最佳实践"""
    return get_wiki_query_tool().get_best_practices(platform, business_type, limit)


def wiki_get_errors(error_code: str, platform: str = None) -> List[str]:
    """便捷函数：获取错误解决方案"""
    return get_wiki_query_tool().get_error_solutions(error_code, platform)


def wiki_get_workflow(platform: str, workflow_type: str = None) -> Dict:
    """便捷函数：获取工作流"""
    return get_wiki_query_tool().get_workflow(platform, workflow_type)


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='LLM Wiki 知识库查询工具')
    parser.add_argument('--action', '-a', required=True,
                       choices=['search', 'best_practices', 'errors', 'workflow', 'stats'])
    parser.add_argument('--query', '-q', default=None)
    parser.add_argument('--platform', '-p', default=None,
                       choices=['google', 'meta', 'tiktok', 'dv360', 'all'])
    parser.add_argument('--error', '-e', default=None)
    parser.add_argument('--workflow-type', '-w', default=None)
    parser.add_argument('--limit', '-n', type=int, default=10)
    
    args = parser.parse_args()
    
    tool = WikiQueryTool()
    
    if args.action == 'search':
        platforms = [args.platform] if args.platform and args.platform != 'all' else None
        result = tool.search(args.query or '', platforms)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'best_practices':
        result = tool.get_best_practices(args.platform)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'errors':
        result = tool.get_error_solutions(args.error or '')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'workflow':
        result = tool.get_workflow(args.platform or 'google', args.workflow_type)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'stats':
        result = tool.get_stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
