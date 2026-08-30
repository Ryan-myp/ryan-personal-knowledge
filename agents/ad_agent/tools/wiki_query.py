#!/usr/bin/env python3
"""
LLM Wiki 知识库查询工具 - Karpathy 风格
支持从 Markdown 知识库查询专家知识、最佳实践、常见问题等
"""

import json
import os
import re
import sys
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agents.ad_agent.core.platform import normalize_platform


@dataclass
class WikiEntry:
    """知识库条目"""
    entry_id: str
    platform: str
    knowledge_type: str  # hierarchy/workflow/constraint/best_practice/error_pattern/case_study/tip
    content: Dict[str, Any]
    source: str
    tags: List[str] = field(default_factory=list)
    created_at: str = ""


class MarkdownWikiLoader:
    """从 Markdown 文件加载知识库"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.entries: Dict[str, WikiEntry] = {}
        self._load()
    
    def _load(self):
        """加载所有 Markdown 文件"""
        # 加载平台知识
        platforms_dir = self.base_path / 'platforms'
        if platforms_dir.exists():
            for platform_dir in platforms_dir.iterdir():
                if platform_dir.is_dir():
                    platform = platform_dir.name
                    for md_file in platform_dir.glob('*.md'):
                        self._parse_markdown(md_file, platform)
        
        # 加载经验知识
        expertise_dir = self.base_path / 'expertise'
        if expertise_dir.exists():
            for md_file in expertise_dir.glob('*.md'):
                self._parse_markdown(md_file, 'all')
    
    def _parse_markdown(self, path: Path, platform: str):
        """解析 Markdown 文件"""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 entry_id 从文件名
        entry_id = path.stem.replace('-', '_')
        
        # 解析内容
        knowledge_type = self._detect_type(path.name)
        
        # 提取 frontmatter
        fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        fm_content = {}
        if fm_match:
            fm_text = fm_match.group(1)
            for line in fm_text.split('\n'):
                if ':' in line:
                    key, val = line.split(':', 1)
                    fm_content[key.strip()] = val.strip()
        
        # 提取正文内容
        body_match = re.search(r'\n---\n(.*)', content, re.DOTALL)
        body = body_match.group(1).strip() if body_match else content
        
        entry = WikiEntry(
            entry_id=f"{platform}_{entry_id}",
            platform=platform,
            knowledge_type=knowledge_type,
            content={
                'title': path.stem,
                'raw_content': body,
                'metadata': fm_content,
                'source_file': str(path),
            },
            source=fm_content.get('来源', 'markdown'),
            tags=[platform, knowledge_type],
            created_at=datetime.now().isoformat()
        )
        
        self.entries[entry.entry_id] = entry
    
    def _detect_type(self, filename: str) -> str:
        """检测知识类型"""
        name = filename.lower()
        if 'campaign' in name or 'hierarchy' in name:
            return 'hierarchy'
        elif 'workflow' in name:
            return 'workflow'
        elif 'constraint' in name:
            return 'constraint'
        elif 'best-practice' in name or 'best_practice' in name:
            return 'best_practice'
        elif 'error' in name:
            return 'error_pattern'
        elif 'case' in name:
            return 'case_study'
        elif 'tip' in name:
            return 'tip'
        return 'general'
    
    def search(self, query: str, platforms: List[str] = None, 
               knowledge_types: List[str] = None, limit: int = 10) -> List[WikiEntry]:
        """搜索知识库"""
        results = []
        query_lower = query.lower()
        normalized_platforms = {
            normalize_platform(platform) if str(platform).lower() != "all" else "all"
            for platform in (platforms or [])
        }
        
        for entry in self.entries.values():
            # 过滤平台
            entry_platform = (
                normalize_platform(entry.platform)
                if str(entry.platform).lower() != "all" else "all"
            )
            if normalized_platforms and entry_platform not in normalized_platforms and entry_platform != 'all':
                continue
            
            # 过滤知识类型
            if knowledge_types and entry.knowledge_type not in knowledge_types:
                continue
            
            # 搜索内容
            content_str = json.dumps(entry.content, ensure_ascii=False).lower()
            if query_lower in content_str or query_lower in entry.entry_id.lower():
                results.append(entry)
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_by_type(self, knowledge_type: str, platform: str = None) -> List[WikiEntry]:
        """按类型获取条目"""
        results = []
        normalized_platform = (
            normalize_platform(platform)
            if platform and str(platform).lower() != "all" else platform
        )
        for entry in self.entries.values():
            if entry.knowledge_type == knowledge_type:
                entry_platform = (
                    normalize_platform(entry.platform)
                    if str(entry.platform).lower() != "all" else "all"
                )
                if platform is None or str(platform).lower() == "all" \
                        or entry_platform == normalized_platform or entry_platform == 'all':
                    results.append(entry)
        return results
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = {
            'total': len(self.entries),
            'by_platform': {},
            'by_type': {},
        }
        
        for entry in self.entries.values():
            # 按平台统计
            platform = entry.platform
            stats['by_platform'][platform] = stats['by_platform'].get(platform, 0) + 1
            
            # 按类型统计
            ktype = entry.knowledge_type
            stats['by_type'][ktype] = stats['by_type'].get(ktype, 0) + 1
        
        return stats


# 全局实例
_wiki_instance = None

def get_wiki_loader(base_path: str = None) -> MarkdownWikiLoader:
    """获取知识库加载器实例"""
    global _wiki_instance
    if _wiki_instance is None:
        if base_path is None:
            base_path = str(Path(__file__).parent.parent / 'knowledge_base')
        _wiki_instance = MarkdownWikiLoader(base_path)
    return _wiki_instance


class WikiQueryTool:
    """知识库查询工具 - 查询专家知识"""
    
    def __init__(self, base_path: str = None):
        self.loader = get_wiki_loader(base_path)
    
    def search(self, query: str, platforms: List[str] = None, 
               knowledge_types: List[str] = None, limit: int = 10) -> List[Dict]:
        """搜索知识库"""
        results = self.loader.search(query, platforms, knowledge_types, limit)
        return [
            {
                'entry_id': r.entry_id,
                'platform': r.platform,
                'knowledge_type': r.knowledge_type,
                'content': r.content,
                'source': r.source,
                'tags': r.tags,
            }
            for r in results
        ]
    
    def get_best_practices(self, platform: str = None, 
                          business_type: str = None,
                          limit: int = 10) -> List[Dict]:
        """获取最佳实践"""
        results = self.loader.get_by_type('best_practice', platform)
        return [r.content for r in results[:limit]]
    
    def get_error_solutions(
        self, error_code: str, platform: str = None, limit: int = 10,
    ) -> List[str]:
        """获取错误解决方案"""
        results = self.loader.search(error_code, platforms=[platform] if platform else None, knowledge_types=['error_pattern'])
        solutions = []
        for r in results:
            content = r.content.get('raw_content', '')
            # 提取解决方案部分
            if '解决方案' in content:
                sol_match = re.search(r'解决方案[：:]\n?(.*)', content, re.DOTALL)
                if sol_match:
                    solutions.append(sol_match.group(1).strip())
        return solutions[:limit] if limit else solutions
    
    def get_workflow(self, platform: str, workflow_type: str = None) -> Dict:
        """获取工作流"""
        results = self.loader.get_by_type(
            'workflow', None if not platform or str(platform).lower() == 'all' else platform
        )
        return {
            'platform': platform or 'all',
            'workflows': [r.content for r in results]
        }
    
    def get_stats(self) -> Dict:
        """获取知识库统计"""
        return self.loader.get_stats()


# 便捷函数
def wiki_search(query: str, platforms: List[str] = None, 
                knowledge_types: List[str] = None, limit: int = 10) -> List[Dict]:
    """便捷函数：搜索知识库"""
    return WikiQueryTool().search(query, platforms, knowledge_types, limit)


def wiki_get_best_practices(platform: str = None, 
                           business_type: str = None,
                           limit: int = 10) -> List[Dict]:
    """便捷函数：获取最佳实践"""
    return WikiQueryTool().get_best_practices(platform, business_type, limit)


def wiki_get_errors(
    error_code: str, platform: str = None, limit: int = 10,
) -> List[str]:
    """便捷函数：获取错误解决方案"""
    return WikiQueryTool().get_error_solutions(error_code, platform, limit)


def wiki_get_workflow(platform: str, workflow_type: str = None) -> Dict:
    """便捷函数：获取工作流"""
    return WikiQueryTool().get_workflow(platform, workflow_type)


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='LLM Wiki 知识库查询工具')
    parser.add_argument('--action', '-a', required=True,
                       choices=['search', 'best_practices', 'errors', 'workflow', 'stats'])
    parser.add_argument('--query', '-q', default=None)
    parser.add_argument('--platform', '-p', default=None,
                       help='平台标识；不限制为固定渠道，all 表示全部')
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
        result = tool.get_workflow(args.platform or 'all', args.workflow_type)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'stats':
        result = tool.get_stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
