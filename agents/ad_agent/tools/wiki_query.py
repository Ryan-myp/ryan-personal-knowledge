#!/usr/bin/env python3
"""
LLM Wiki 通用知识库查询工具
支持多层级知识查询：层级参数、业务策略、最佳实践、错误解决方案
"""

import json
import sys
import os
from typing import Dict, List, Optional, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from knowledge_base import LLMWikiKnowledgeBase, KnowledgeType, get_wiki_kb


class WikiQueryTool:
    """知识库查询工具"""
    
    def __init__(self, base_path: str = None):
        self.kb = get_wiki_kb(base_path)
    
    # ==================== 平台层查询 ====================
    
    def query_hierarchy(self, platform: str, level: str) -> Dict:
        """查询层级结构"""
        platform_kb = self.kb.get_platform_kb(platform)
        hierarchy_kb = platform_kb.get('hierarchy')
        
        result = {
            'platform': platform,
            'level': level,
            'parameters': {},
            'constraints': [],
            'valid_combinations': []
        }
        
        if hierarchy_kb:
            for entry in hierarchy_kb.entries.values():
                if entry.content.get('level') == level:
                    result['parameters'] = entry.content.get('parameters', {})
                    result['constraints'] = entry.content.get('constraints', [])
                    result['valid_combinations'] = entry.content.get('valid_combinations', [])
                    break
        
        return result
    
    def query_constraints(self, platform: str, source_level: str, 
                         target_level: str, source_value: str = None) -> List[Dict]:
        """查询约束规则"""
        platform_kb = self.kb.get_platform_kb(platform)
        constraint_kb = platform_kb.get('constraints')
        
        if constraint_kb:
            return constraint_kb.get_constraints(source_level, target_level, source_value)
        return []
    
    def get_parameter_suggestions(self, platform: str, level: str, 
                                   existing_params: Dict) -> Dict:
        """获取参数建议"""
        return self.kb.get_parameter_suggestions(platform, level, existing_params)
    
    def validate_creation_flow(self, platform: str, flow: Dict) -> Dict:
        """验证创建流程"""
        return self.kb.validate_creation_flow(platform, flow)
    
    def get_api_workflow(self, platform: str, workflow_type: str = None) -> Dict:
        """获取 API 工作流"""
        return self.kb.get_api_workflow(platform, workflow_type)
    
    # ==================== 业务层查询 ====================
    
    def get_business_strategy(self, business_type: str, platform: str = None) -> List[Dict]:
        """获取业务策略"""
        strategy_kb = self.kb.business_kbs.get('strategy')
        if not strategy_kb:
            return []
        
        results = []
        for entry in strategy_kb.entries.values():
            if entry.content.get('business_type') == business_type:
                if platform and entry.platform != 'all' and entry.platform != platform:
                    continue
                results.append(entry.content)
        return results
    
    def get_bidding_recommendation(self, objective: str, platform: str = None) -> Dict:
        """获取出价建议"""
        bidding_kb = self.kb.business_kbs.get('bidding')
        if not bidding_kb:
            return {}
        
        for entry in bidding_kb.entries.values():
            if entry.content.get('objective') == objective:
                if platform and entry.platform != 'all' and entry.platform != platform:
                    continue
                return entry.content.get('bid_suggestion', {})
        return {}
    
    def get_targeting_recommendation(self, strategy_name: str, platform: str = None) -> List[Dict]:
        """获取定向建议"""
        targeting_kb = self.kb.business_kbs.get('targeting')
        if not targeting_kb:
            return []
        
        results = []
        for entry in targeting_kb.entries.values():
            if strategy_name in entry.content.get('strategy_name', ''):
                if platform and entry.platform != 'all' and entry.platform != platform:
                    continue
                results.append(entry.content)
        return results
    
    def get_creative_guide(self, guide_type: str, platform: str = None) -> List[Dict]:
        """获取素材指南"""
        creative_kb = self.kb.business_kbs.get('creative')
        if not creative_kb:
            return []
        
        results = []
        for entry in creative_kb.entries.values():
            if guide_type in entry.content.get('guide_type', ''):
                if platform and entry.platform != 'all' and entry.platform != platform:
                    continue
                results.append(entry.content)
        return results
    
    # ==================== 经验层查询 ====================
    
    def get_best_practices(self, platform: str = None, 
                          business_type: str = None,
                          limit: int = 10) -> List[Dict]:
        """获取最佳实践"""
        return self.kb.get_best_practices(platform, business_type, limit)
    
    def get_error_solutions(self, error_code: str, platform: str = None) -> List[str]:
        """获取错误解决方案"""
        return self.kb.get_error_solutions(error_code, platform)
    
    def get_random_tips(self, count: int = 5) -> List[Dict]:
        """获取随机技巧"""
        tip_kb = self.kb.expertise_kbs.get('tips')
        if not tip_kb:
            return []
        return [e.content for e in tip_kb.get_random_tips(count)]
    
    def get_case_studies(self, business_type: str, platform: str = None) -> List[Dict]:
        """获取案例研究"""
        case_kb = self.kb.expertise_kbs.get('case_studies')
        if not case_kb:
            return []
        
        results = []
        for entry in case_kb.entries.values():
            tags = entry.content.get('tags', [])
            if business_type in tags:
                if platform and entry.platform != 'all' and entry.platform != platform:
                    continue
                results.append(entry.content)
        return results
    
    # ==================== 通用搜索 ====================
    
    def search(self, query: str, platforms: List[str] = None, 
               knowledge_types: List[KnowledgeType] = None, limit: int = 20) -> List[Dict]:
        """搜索知识库"""
        results = self.kb.search(query, platforms, knowledge_types, limit)
        return [
            {
                'entry_id': r.entry_id,
                'platform': r.platform,
                'knowledge_type': r.knowledge_type.value,
                'content': r.content,
                'source': r.source.value if hasattr(r.source, 'value') else str(r.source),
                'tags': r.tags,
                'confidence': r.confidence
            }
            for r in results
        ]
    
    def get_stats(self) -> Dict:
        """获取知识库统计"""
        stats = {
            'platforms': {},
            'business': {},
            'expertise': {},
            'total': 0
        }
        
        for platform in ['tiktok', 'meta', 'google', 'dv360']:
            if platform in self.kb.platform_kbs:
                stats['platforms'][platform] = {
                    name: len(kbo.entries) 
                    for name, kbo in self.kb.platform_kbs[platform].items()
                }
                stats['total'] += sum(stats['platforms'][platform].values())
        
        for name, kbo in self.kb.business_kbs.items():
            stats['business'][name] = len(kbo.entries)
            stats['total'] += len(kbo.entries)
        
        for name, kbo in self.kb.expertise_kbs.items():
            stats['expertise'][name] = len(kbo.entries)
            stats['total'] += len(kbo.entries)
        
        return stats


def main():
    """命令行接口"""
    import argparse
    
    # 默认使用 knowledge_base 目录
    default_base_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'knowledge_base')
    
    parser = argparse.ArgumentParser(description='LLM Wiki 知识库查询工具')
    parser.add_argument('--platform', '-p', default=None, 
                       choices=['tiktok', 'meta', 'google', 'dv360', 'all'],
                       help='平台名称')
    parser.add_argument('--action', '-a', required=True,
                       choices=['hierarchy', 'constraints', 'suggest', 'validate', 
                               'workflow', 'search', 'strategy', 'bidding', 
                               'targeting', 'creative', 'best_practices', 
                               'errors', 'tips', 'cases', 'stats'],
                       help='查询动作')
    parser.add_argument('--level', '-l', default=None,
                       help='层级名称 (campaign/ad_group/ad)')
    parser.add_argument('--query', '-q', default=None,
                       help='搜索关键词')
    parser.add_argument('--source-level', default=None,
                       help='源层级')
    parser.add_argument('--target-level', default=None,
                       help='目标层级')
    parser.add_argument('--source-value', default=None,
                       help='源值')
    parser.add_argument('--params', '-m', default=None,
                       help='JSON 格式的参数')
    parser.add_argument('--business-type', '-b', default=None,
                       help='业务类型 (ecommerce/gaming/app)')
    parser.add_argument('--limit', '-n', type=int, default=10,
                       help='返回数量限制')
    parser.add_argument('--base-path', default=default_base_path,
                       help='知识库基础路径')
    
    args = parser.parse_args()
    
    tool = WikiQueryTool(args.base_path)
    
    if args.action == 'hierarchy':
        result = tool.query_hierarchy(args.platform or 'tiktok', args.level or 'campaign')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'constraints':
        result = tool.query_constraints(
            args.platform or 'tiktok', 
            args.source_level or 'campaign',
            args.target_level or 'ad_group',
            args.source_value
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'suggest':
        params = json.loads(args.params) if args.params else {}
        result = tool.get_parameter_suggestions(args.platform or 'tiktok', args.level or 'campaign', params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'validate':
        flow = json.loads(args.params) if args.params else {}
        result = tool.validate_creation_flow(args.platform or 'tiktok', flow)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'workflow':
        result = tool.get_api_workflow(args.platform or 'tiktok')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'search':
        platforms = [args.platform] if args.platform and args.platform != 'all' else None
        result = tool.search(args.query or '', platforms)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'strategy':
        result = tool.get_business_strategy(args.business_type or 'ecommerce', args.platform)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'bidding':
        result = tool.get_bidding_recommendation(args.query or 'conversions', args.platform)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'targeting':
        result = tool.get_targeting_recommendation(args.query or '兴趣定向', args.platform)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'creative':
        result = tool.get_creative_guide(args.query or 'video_spec', args.platform)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'best_practices':
        result = tool.get_best_practices(args.platform, args.business_type, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'errors':
        result = tool.get_error_solutions(args.query or 'ERROR_1234', args.platform)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'tips':
        result = tool.get_random_tips(args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'cases':
        result = tool.get_case_studies(args.business_type or 'ecommerce', args.platform)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == 'stats':
        result = tool.get_stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
