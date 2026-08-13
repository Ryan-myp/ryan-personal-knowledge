#!/usr/bin/env python3
"""
意图识别 + 路由模块 - 独立版本 (不依赖 biz-delivery)
"""

from typing import Tuple, Optional, Dict, List

INTENT_PATTERNS = {
    "create": ["创建", "新建", "添加", "新增", "生成", "构建", "add", "new"],
    "update": ["修改", "更新", "变更", "调整", "编辑", "更改", "update", "modify", "edit"],
    "query": ["查询", "查看", "获取", "查找", "检索", "显示", "query", "search", "get", "list"],
    "delete": ["删除", "移除", "清除", "delete", "remove", "cancel"],
    "sync": ["同步", "数据同步", "回流", "sync", "syncing"],
    "config": ["配置", "设置", "参数", "选项", "config", "setting", "parameter"],
    "question": ["什么", "如何", "怎么", "为什么", "吗", "what", "how", "why", "where"],
    "explain": ["解释", "说明", "原理", "机制", "explain", "describe", "how it works"],
    "debug": ["调试", "排障", "错误", "问题", "失败", "bug", "error", "fix", "troubleshoot"],
    "optimize": ["优化", "性能", "效率", "optimize", "performance", "improve"],
    "review": ["评审", "审核", "检查", "review", "audit", "inspect"],
    "compare": ["对比", "比较", "区别", "差异", "compare", "diff", "difference"],
    "migrate": ["迁移", "升级", "转换", "migrate", "upgrade", "convert"],
    "integrate": ["集成", "对接", "连接", "integrate", "connect", "bridge"],
}

# 意图 → 查询类型映射
INTENT_TO_QUERY_TYPE = {
    "create": "code",
    "update": "code",
    "query": "knowledge",
    "delete": "code",
    "sync": "schema",
    "config": "knowledge",
    "question": "knowledge",
    "explain": "code",
    "debug": "code",
    "optimize": "code",
    "review": "knowledge",
    "compare": "knowledge",
    "migrate": "schema",
    "integrate": "code",
}

# 范围权重 - 每个意图对应不同 scope 的权重
SCOPE_WEIGHTS = {
    "create": {"file_content": 0.8, "file_name": 0.6, "tags": 0.7, "directory_path": 0.4},
    "update": {"file_content": 0.8, "file_name": 0.5, "tags": 0.6, "directory_path": 0.4},
    "query": {"file_content": 0.8, "file_name": 0.5, "tags": 0.7, "directory_path": 0.6},
    "delete": {"file_content": 0.7, "file_name": 0.5, "tags": 0.4, "directory_path": 0.3},
    "sync": {"file_content": 0.8, "file_name": 0.5, "tags": 0.8, "directory_path": 0.7},
    "config": {"file_content": 0.5, "file_name": 0.8, "tags": 0.7, "directory_path": 0.6},
    "question": {"file_content": 0.9, "file_name": 0.3, "tags": 0.8, "directory_path": 0.5},
    "explain": {"file_content": 0.9, "file_name": 0.3, "tags": 0.7, "directory_path": 0.5},
    "debug": {"file_content": 0.9, "file_name": 0.4, "tags": 0.8, "directory_path": 0.5},
    "optimize": {"file_content": 0.9, "file_name": 0.4, "tags": 0.7, "directory_path": 0.5},
    "review": {"file_content": 0.7, "file_name": 0.5, "tags": 0.7, "directory_path": 0.5},
    "compare": {"file_content": 0.7, "file_name": 0.5, "tags": 0.8, "directory_path": 0.6},
    "migrate": {"file_content": 0.8, "file_name": 0.6, "tags": 0.7, "directory_path": 0.7},
    "integrate": {"file_content": 0.7, "file_name": 0.5, "tags": 0.8, "directory_path": 0.5},
}


def extract_intent(query: str) -> Tuple[str, float]:
    """从查询文本中提取意图和置信度"""
    query_lower = query.lower()
    scores = {}
    
    for intent, patterns in INTENT_PATTERNS.items():
        score = sum(1 for pattern in patterns if pattern.lower() in query_lower)
        if score > 0:
            avg_pattern_len = sum(len(p) for p in patterns) / len(patterns)
            normalized_score = score / len(patterns) * (avg_pattern_len / 10)
            scores[intent] = min(normalized_score, 1.0)
    
    if not scores:
        return ("unknown", 0.0)
    
    max_intent = max(scores, key=scores.get)
    return (max_intent, scores[max_intent])


def get_scope_weights(intent: str) -> Dict[str, float]:
    """获取意图对应的范围权重"""
    return SCOPE_WEIGHTS.get(intent, {"file_content": 0.8, "file_name": 0.5, "tags": 0.6, "directory_path": 0.5})


def get_query_type(intent: str) -> str:
    """获取意图对应的查询类型"""
    return INTENT_TO_QUERY_TYPE.get(intent, "knowledge")
