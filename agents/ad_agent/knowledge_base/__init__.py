"""
LLM Wiki 通用知识库系统
支持多层级知识：层级参数 → 业务策略 → 最佳实践 → 案例分析
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import json
import os
from pathlib import Path
from datetime import datetime


class KnowledgeType(Enum):
    """知识类型枚举"""
    # 平台层知识
    HIERARCHY = "hierarchy"          # 层级结构定义
    CONSTRAINT = "constraint"        # 参数约束规则
    PARAMETER = "parameter"          # 参数定义
    WORKFLOW = "workflow"            # 操作工作流
    
    # 业务层知识
    BUSINESS_STRATEGY = "business_strategy"   # 业务策略
    BIDDING_STRATEGY = "bidding_strategy"      # 出价策略
    TARGETING_STRATEGY = "targeting_strategy"  # 定向策略
    CREATIVE_GUIDE = "creative_guide"          # 素材指南
    
    # 经验层知识
    BEST_PRACTICE = "best_practice"       # 最佳实践
    CASE_STUDY = "case_study"             # 案例研究
    ERROR_PATTERN = "error_pattern"       # 错误模式
    TIP = "tip"                           # 实用技巧
    
    # 动态知识
    API_CHANGE = "api_change"             # API 变更日志
    PERFORMANCE_DATA = "performance_data" # 性能数据


class KnowledgeSource(Enum):
    """知识来源"""
    OFFICIAL_DOCS = "official_docs"       # 官方文档
    API_TEST = "api_test"                 # API 实测
    MANUAL_EXPERT = "manual_expert"       # 专家经验
    HISTORICAL_DATA = "historical_data"   # 历史数据
    USER_CONTRIBUTED = "user_contributed" # 用户贡献


@dataclass
class KnowledgeEntry:
    """知识条目基类"""
    entry_id: str
    knowledge_type: KnowledgeType
    platform: str  # tiktok/meta/google/dv360/all
    content: Dict[str, Any]
    source: KnowledgeSource
    source_ref: str = ""  # 来源引用（文档链接/API版本等）
    created_at: str = ""
    updated_at: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0  # 置信度 0-1
    usage_count: int = 0     # 使用次数
    
    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class ParameterDefinition:
    """参数定义（用于层级知识）"""
    name: str
    type: str  # string/integer/boolean/datetime/float
    required: bool
    description: str
    valid_values: List[str] = field(default_factory=list)
    constraints: List[Dict] = field(default_factory=list)
    depends_on: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'type': self.type,
            'required': self.required,
            'description': self.description,
            'valid_values': self.valid_values,
            'constraints': self.constraints,
            'depends_on': self.depends_on
        }


@dataclass
class ConstraintRule:
    """约束规则"""
    rule_id: str
    condition: Dict[str, Any]
    effect: Dict[str, Any]
    description: str
    source: str = "official_docs"
    
    def to_dict(self) -> Dict:
        return {
            'rule_id': self.rule_id,
            'condition': self.condition,
            'effect': self.effect,
            'description': self.description,
            'source': self.source
        }


class BaseKnowledgeBase(ABC):
    """知识库基类"""
    
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = Path(path)
        self.entries: Dict[str, KnowledgeEntry] = {}
        self._load()
    
    @abstractmethod
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        pass
    
    @abstractmethod
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        pass
    
    @abstractmethod
    def add(self, entry: KnowledgeEntry) -> bool:
        pass
    
    @abstractmethod
    def update(self, entry: KnowledgeEntry) -> bool:
        pass
    
    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        pass
    
    def _load(self):
        """从 JSON 加载"""
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for entry_data in data.get('entries', []):
                        # 处理 KnowledgeType 字符串到枚举的转换
                        if 'knowledge_type' in entry_data:
                            kt = entry_data['knowledge_type']
                            if isinstance(kt, str):
                                try:
                                    entry_data['knowledge_type'] = KnowledgeType(kt)
                                except ValueError:
                                    entry_data['knowledge_type'] = KnowledgeType.OTHER
                        entry = KnowledgeEntry(**entry_data)
                        self.entries[entry.entry_id] = entry
            except Exception as e:
                print(f"[{self.name}] 加载失败: {e}")
    
    def _save(self):
        """保存到 JSON"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        def serialize_entry(entry):
            data = entry.__dict__.copy()
            # 处理枚举类型
            if hasattr(entry, 'knowledge_type') and isinstance(entry.knowledge_type, KnowledgeType):
                data['knowledge_type'] = entry.knowledge_type.value
            if hasattr(entry, 'source') and isinstance(entry.source, KnowledgeSource):
                data['source'] = entry.source.value
            return data
        
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump({
                'name': self.name,
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'entries': [serialize_entry(e) for e in self.entries.values()]
            }, f, ensure_ascii=False, indent=2)


# ==================== 平台层知识库 ====================

class PlatformHierarchyKB(BaseKnowledgeBase):
    """平台层级结构知识库"""
    
    def __init__(self, platform: str, path: str):
        super().__init__(f"{platform}_hierarchy", path)
        self.platform = platform
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.HIERARCHY:
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False
    
    def get_hierarchy(self, level: str = None) -> Optional[KnowledgeEntry]:
        """获取层级结构"""
        for entry in self.entries.values():
            if entry.content.get('level') == level or level is None:
                return entry
        return None
    
    def get_parameter(self, level: str, parameter: str) -> Optional[ParameterDefinition]:
        """获取参数定义"""
        for entry in self.entries.values():
            if entry.content.get('level') == level:
                params = entry.content.get('parameters', {})
                if parameter in params:
                    pd = params[parameter]
                    return ParameterDefinition(
                        name=parameter,
                        type=pd.get('type', 'string'),
                        required=pd.get('required', False),
                        description=pd.get('description', ''),
                        valid_values=pd.get('valid_values', []),
                        constraints=pd.get('constraints', []),
                        depends_on=pd.get('depends_on', {})
                    )
        return None


class PlatformConstraintKB(BaseKnowledgeBase):
    """平台约束规则知识库"""
    
    def __init__(self, platform: str, path: str):
        super().__init__(f"{platform}_constraints", path)
        self.platform = platform
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.CONSTRAINT:
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False
    
    def get_constraints(self, source_level: str, target_level: str, 
                       source_value: str = None) -> List[Dict]:
        """获取层级间约束"""
        constraints = []
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.CONSTRAINT:
                content = entry.content
                if content.get('source_level') == source_level and \
                   content.get('target_level') == target_level:
                    if source_value is None or content.get('source_value') == source_value:
                        constraints.append(content)
        return constraints


class PlatformWorkflowKB(BaseKnowledgeBase):
    """平台工作流知识库"""
    
    def __init__(self, platform: str, path: str):
        super().__init__(f"{platform}_workflows", path)
        self.platform = platform
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            content_str = json.dumps(entry.content, ensure_ascii=False).lower()
            if query_lower in content_str:
                results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False
    
    def get_workflow(self, workflow_type: str) -> Optional[KnowledgeEntry]:
        """获取工作流"""
        for entry in self.entries.values():
            if entry.content.get('type') == workflow_type:
                return entry
        return None
    
    def get_steps(self, workflow_type: str) -> List[Dict]:
        """获取工作流步骤"""
        workflow = self.get_workflow(workflow_type)
        if workflow:
            return workflow.content.get('steps', [])
        return []


# ==================== 业务层知识库 ====================

class BusinessStrategyKB(BaseKnowledgeBase):
    """业务策略知识库"""
    
    def __init__(self, path: str):
        super().__init__("business_strategy", path)
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.BUSINESS_STRATEGY:
                # 检查平台匹配
                if platform and entry.platform != 'all' and entry.platform != platform:
                    continue
                # 检查知识类型
                if knowledge_type and entry.knowledge_type != knowledge_type:
                    continue
                # 搜索内容
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False
    
    def get_by_business_type(self, business_type: str) -> List[KnowledgeEntry]:
        """按业务类型获取策略"""
        results = []
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.BUSINESS_STRATEGY:
                tags = entry.content.get('tags', [])
                if business_type in tags:
                    results.append(entry)
        return results


class BiddingStrategyKB(BaseKnowledgeBase):
    """出价策略知识库"""
    
    def __init__(self, path: str):
        super().__init__("bidding_strategy", path)
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.BIDDING_STRATEGY:
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False
    
    def get_optimal_bid(self, objective: str, platform: str, 
                       conversion_value: float = None) -> Dict:
        """获取最优出价建议"""
        for entry in self.entries.values():
            if (entry.knowledge_type == KnowledgeType.BIDDING_STRATEGY and
                entry.content.get('objective') == objective and
                (entry.platform == platform or entry.platform == 'all')):
                return entry.content.get('bid_suggestion', {})
        return {}


class TargetingStrategyKB(BaseKnowledgeBase):
    """定向策略知识库"""
    
    def __init__(self, path: str):
        super().__init__("targeting_strategy", path)
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.TARGETING_STRATEGY:
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False


class CreativeGuideKB(BaseKnowledgeBase):
    """素材指南知识库"""
    
    def __init__(self, path: str):
        super().__init__("creative_guide", path)
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.CREATIVE_GUIDE:
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False


# ==================== 经验层知识库 ====================

class BestPracticeKB(BaseKnowledgeBase):
    """最佳实践知识库"""
    
    def __init__(self, path: str):
        super().__init__("best_practice", path)
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.BEST_PRACTICE:
                if platform and entry.platform != 'all' and entry.platform != platform:
                    continue
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False
    
    def get_trending(self, limit: int = 10) -> List[KnowledgeEntry]:
        """获取热门最佳实践（按使用次数排序）"""
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda x: x.usage_count,
            reverse=True
        )
        return sorted_entries[:limit]


class CaseStudyKB(BaseKnowledgeBase):
    """案例研究知识库"""
    
    def __init__(self, path: str):
        super().__init__("case_study", path)
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.CASE_STUDY:
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False


class ErrorPatternKB(BaseKnowledgeBase):
    """错误模式知识库"""
    
    def __init__(self, path: str):
        super().__init__("error_pattern", path)
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.ERROR_PATTERN:
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False
    
    def get_solutions(self, error_code: str) -> List[str]:
        """获取错误解决方案"""
        solutions = []
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.ERROR_PATTERN:
                if entry.content.get('error_code') == error_code:
                    solutions.extend(entry.content.get('solutions', []))
        return solutions


class TipKB(BaseKnowledgeBase):
    """技巧知识库"""
    
    def __init__(self, path: str):
        super().__init__("tip", path)
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.TIP:
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False
    
    def get_random_tips(self, count: int = 5) -> List[KnowledgeEntry]:
        """获取随机技巧"""
        import random
        tips = list(self.entries.values())
        return random.sample(tips, min(count, len(tips)))


# ==================== 动态知识知识库 ====================

class APIChangeKB(BaseKnowledgeBase):
    """API 变更知识库"""
    
    def __init__(self, path: str):
        super().__init__("api_change", path)
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.API_CHANGE:
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False
    
    def get_recent_changes(self, platform: str, days: int = 30) -> List[KnowledgeEntry]:
        """获取最近变更"""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        results = []
        for entry in self.entries.values():
            if entry.platform == platform or entry.platform == 'all':
                if entry.created_at >= cutoff:
                    results.append(entry)
        return sorted(results, key=lambda x: x.created_at, reverse=True)


class PerformanceDataKB(BaseKnowledgeBase):
    """性能数据知识库"""
    
    def __init__(self, path: str):
        super().__init__("performance_data", path)
    
    def search(self, query: str, platform: Optional[str] = None, 
               knowledge_type: Optional[KnowledgeType] = None) -> List[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        
        for entry in self.entries.values():
            if entry.knowledge_type == KnowledgeType.PERFORMANCE_DATA:
                content_str = json.dumps(entry.content, ensure_ascii=False).lower()
                if query_lower in content_str:
                    results.append(entry)
        
        return results
    
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        return self.entries.get(entry_id)
    
    def add(self, entry: KnowledgeEntry) -> bool:
        self.entries[entry.entry_id] = entry
        self._save()
        return True
    
    def update(self, entry: KnowledgeEntry) -> bool:
        if entry.entry_id in self.entries:
            self.entries[entry.entry_id] = entry
            self._save()
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save()
            return True
        return False


# ==================== 主控制器 ====================

class LLMWikiKnowledgeBase:
    """LLM Wiki 通用知识库主控制器"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.platforms = ['meta', 'tiktok', 'google', 'dv360']
        
        # 初始化平台层知识库
        self.platform_kbs = {}
        for platform in self.platforms:
            platform_path = self.base_path / platform
            self.platform_kbs[platform] = {
                'hierarchy': PlatformHierarchyKB(platform, str(platform_path / 'hierarchy.json')),
                'constraints': PlatformConstraintKB(platform, str(platform_path / 'constraints.json')),
                'workflows': PlatformWorkflowKB(platform, str(platform_path / 'workflows.json')),
            }
        
        # 初始化业务层知识库
        self.business_kbs = {
            'strategy': BusinessStrategyKB(str(self.base_path / 'business/strategy.json')),
            'bidding': BiddingStrategyKB(str(self.base_path / 'business/bidding.json')),
            'targeting': TargetingStrategyKB(str(self.base_path / 'business/targeting.json')),
            'creative': CreativeGuideKB(str(self.base_path / 'business/creative.json')),
        }
        
        # 初始化经验层知识库
        self.expertise_kbs = {
            'best_practices': BestPracticeKB(str(self.base_path / 'expertise/best_practices.json')),
            'case_studies': CaseStudyKB(str(self.base_path / 'expertise/case_studies.json')),
            'error_patterns': ErrorPatternKB(str(self.base_path / 'expertise/error_patterns.json')),
            'tips': TipKB(str(self.base_path / 'expertise/tips.json')),
        }
        
        # 初始化动态知识知识库
        self.dynamic_kbs = {
            'api_changes': APIChangeKB(str(self.base_path / 'dynamic/api_changes.json')),
            'performance': PerformanceDataKB(str(self.base_path / 'dynamic/performance.json')),
        }
        
        # 确保目录存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保所有必要的目录存在"""
        dirs = [
            'meta', 'tiktok', 'google', 'dv360',
            'business', 'expertise', 'dynamic'
        ]
        for d in dirs:
            (self.base_path / d).mkdir(parents=True, exist_ok=True)
    
    def get_platform_kb(self, platform: str) -> Dict:
        """获取平台知识库"""
        return self.platform_kbs.get(platform, {})
    
    def search(self, query: str, 
               platforms: List[str] = None,
               knowledge_types: List[KnowledgeType] = None,
               limit: int = 20) -> List[KnowledgeEntry]:
        """跨知识库搜索"""
        all_results = []
        seen_ids = set()
        
        # 搜索平台层
        if not platforms or 'all' in platforms:
            search_platforms = self.platforms
        else:
            search_platforms = [p for p in platforms if p in self.platforms]
        
        for platform in search_platforms:
            for kb_name, kb in self.platform_kbs[platform].items():
                if knowledge_types and KnowledgeType(kb_name) not in knowledge_types:
                    continue
                results = kb.search(query)
                for r in results:
                    if r.entry_id not in seen_ids:
                        all_results.append(r)
                        seen_ids.add(r.entry_id)
        
        # 搜索业务层
        if not platforms or 'all' in platforms:
            for kb_name, kb in self.business_kbs.items():
                if knowledge_types and KnowledgeType(kb_name) not in knowledge_types:
                    continue
                results = kb.search(query)
                for r in results:
                    if r.entry_id not in seen_ids:
                        all_results.append(r)
                        seen_ids.add(r.entry_id)
        
        # 搜索经验层
        for kb_name, kb in self.expertise_kbs.items():
            if knowledge_types and KnowledgeType(kb_name) not in knowledge_types:
                continue
            results = kb.search(query)
            for r in results:
                if r.entry_id not in seen_ids:
                    all_results.append(r)
                    seen_ids.add(r.entry_id)
        
        # 按相关性排序
        all_results.sort(key=lambda x: x.confidence * (1 + x.usage_count * 0.01), reverse=True)
        
        return all_results[:limit]
    
    def get_parameter_suggestions(self, platform: str, level: str, 
                                   existing_params: Dict) -> Dict:
        """获取参数建议"""
        suggestions = {
            'required_params': [],
            'optional_params': [],
            'constraints': [],
            'warnings': []
        }
        
        # 从层级知识库获取
        hierarchy_kb = self.platform_kbs.get(platform, {}).get('hierarchy')
        if hierarchy_kb:
            entry = hierarchy_kb.get_hierarchy(level)
            if entry:
                params = entry.content.get('parameters', {})
                for param_name, param_def in params.items():
                    if param_def.get('required', False):
                        if param_name not in existing_params:
                            suggestions['required_params'].append(param_def)
                    else:
                        if param_name not in existing_params:
                            suggestions['optional_params'].append(param_def)
                
                # 检查约束
                constraints = entry.content.get('constraints', [])
                suggestions['constraints'] = constraints
                
                # 检查依赖
                for param_name, param_def in params.items():
                    depends_on = param_def.get('depends_on', {})
                    for dep_param, dep_value in depends_on.items():
                        if existing_params.get(dep_param) != dep_value:
                            suggestions['warnings'].append(
                                f"参数 {param_name} 需要 {dep_param}={dep_value}"
                            )
        
        return suggestions
    
    def validate_creation_flow(self, platform: str, flow: Dict) -> Dict:
        """验证创建流程"""
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }
        
        # 验证 Campaign
        if 'campaign' in flow:
            campaign = flow['campaign']
            suggestions = self.get_parameter_suggestions(platform, 'campaign', campaign)
            result['errors'].extend([
                f"缺少必需参数: {p.get('name')}" 
                for p in suggestions['required_params']
            ])
            result['warnings'].extend(suggestions['warnings'])
        
        # 验证 AdGroup
        if 'ad_group' in flow:
            ad_group = flow['ad_group']
            suggestions = self.get_parameter_suggestions(platform, 'ad_group', ad_group)
            result['errors'].extend([
                f"缺少必需参数: {p.get('name')}" 
                for p in suggestions['required_params']
            ])
        
        # 验证 Ad
        if 'ad' in flow:
            ad = flow['ad']
            suggestions = self.get_parameter_suggestions(platform, 'ad', ad)
            result['errors'].extend([
                f"缺少必需参数: {p.get('name')}" 
                for p in suggestions['required_params']
            ])
        
        # 检查层级约束
        if 'campaign' in flow and 'ad_group' in flow:
            campaign = flow['campaign']
            ad_group = flow['ad_group']
            constraints = self._check_campaign_to_adgroup_constraints(platform, campaign, ad_group)
            result['errors'].extend([c['error'] for c in constraints if c.get('severity') == 'error'])
            result['warnings'].extend([c['error'] for c in constraints if c.get('severity') == 'warning'])
        
        result['valid'] = len(result['errors']) == 0
        return result
    
    def _check_campaign_to_adgroup_constraints(self, platform: str, 
                                                campaign: Dict, ad_group: Dict) -> List[Dict]:
        """检查 Campaign → AdGroup 约束"""
        constraints = []
        
        # 获取约束知识库
        constraint_kb = self.platform_kbs.get(platform, {}).get('constraints')
        if not constraint_kb:
            return constraints
        
        # 查询约束
        rules = constraint_kb.get_constraints('campaign', 'ad_group')
        for rule in rules:
            # 检查条件是否匹配
            condition = rule.get('condition', {})
            if all(campaign.get(k) == v for k, v in condition.items()):
                # 检查效果
                effect = rule.get('effect', {})
                if effect.get('forbidden'):
                    constraints.append({
                        'severity': 'error',
                        'error': f"Campaign objective={campaign.get('objective')} 不支持 {effect.get('forbidden')}"
                    })
                elif effect.get('required'):
                    for req in effect.get('required', []):
                        if req not in ad_group:
                            constraints.append({
                                'severity': 'warning',
                                'error': f"Campaign objective={campaign.get('objective')} 需要 AdGroup 包含 {req}"
                            })
        
        return constraints
    
    def get_api_workflow(self, platform: str, workflow_type: str = None) -> Dict:
        """获取 API 工作流"""
        workflow_kb = self.platform_kbs.get(platform, {}).get('workflows')
        if not workflow_kb:
            return {'platform': platform, 'steps': []}
        
        if workflow_type:
            workflow = workflow_kb.get_workflow(workflow_type)
            if workflow:
                return {
                    'platform': platform,
                    'workflow_type': workflow_type,
                    'description': workflow.content.get('description', ''),
                    'steps': workflow.content.get('steps', []),
                    'error_handling': workflow.content.get('error_handling', {})
                }
        else:
            # 返回所有工作流
            steps = []
            for entry in workflow_kb.entries.values():
                steps.append({
                    'type': entry.content.get('type'),
                    'description': entry.content.get('description'),
                    'steps': entry.content.get('steps', [])
                })
            return {'platform': platform, 'workflows': steps}
        
        return {'platform': platform, 'steps': []}
    
    def get_best_practices(self, platform: str = None, 
                          business_type: str = None,
                          limit: int = 10) -> List[Dict]:
        """获取最佳实践"""
        bp_kb = self.expertise_kbs.get('best_practices')
        if not bp_kb:
            return []
        
        results = []
        for entry in bp_kb.entries.values():
            # 过滤平台
            if platform and entry.platform != 'all' and entry.platform != platform:
                continue
            # 过滤业务类型
            if business_type:
                tags = entry.content.get('tags', [])
                if business_type not in tags:
                    continue
            results.append(entry)
        
        # 按使用次数排序
        results.sort(key=lambda x: x.usage_count, reverse=True)
        return [r.content for r in results[:limit]]
    
    def get_error_solutions(self, error_code: str, platform: str = None) -> List[str]:
        """获取错误解决方案"""
        ep_kb = self.expertise_kbs.get('error_patterns')
        if not ep_kb:
            return []
        
        solutions = []
        for entry in ep_kb.entries.values():
            if entry.content.get('error_code') == error_code:
                if platform and entry.platform != 'all' and entry.platform != platform:
                    continue
                solutions.extend(entry.content.get('solutions', []))
        
        return solutions
    
    def record_usage(self, entry_id: str, platform: str = None):
        """记录知识使用"""
        # 在所有知识库中查找并更新使用次数
        for kb_dict in [self.platform_kbs, self.business_kbs, 
                       self.expertise_kbs, self.dynamic_kbs]:
            for kb_name, kb in kb_dict.items():
                if hasattr(kb, 'entries') and entry_id in kb.entries:
                    kb.entries[entry_id].usage_count += 1
                    kb._save()
                    return


def get_wiki_kb(base_path: str = None) -> LLMWikiKnowledgeBase:
    """获取知识库实例"""
    if base_path is None:
        # 默认路径
        base_path = os.path.join(os.path.dirname(__file__), '..')
    return LLMWikiKnowledgeBase(base_path)
