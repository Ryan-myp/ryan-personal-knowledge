#!/usr/bin/env python3
"""
RRF (Reciprocal Rank Fusion) 融合算法 - 独立版本
支持多种输入格式
"""

from typing import Dict, List, Tuple, Any, Union
import math
import time
import json


def rrf_ranks(ranks_input: Union[Dict, List], k: int = 60) -> List[Tuple[str, float]]:
    """
    Reciprocal Rank Fusion 融合多个排序结果
    
    Args:
        ranks_input: 
          - dict: {"source_name": [(doc_id, score), ...]} 
          - list: [[(doc_id, score), ...], ...] 或 [doc_id, ...]
        k: 平滑常数，默认 60
    
    Returns:
        融合后的排序结果: [(doc_id, fused_score), ...]
    """
    # 统一转换为 dict 格式: {source_name: [(doc_id, rank), ...]}
    ranks_dict = {}
    
    if isinstance(ranks_input, dict):
        for name, items in ranks_input.items():
            normalized = _normalize_results(items)
            ranks_dict[name] = normalized
    elif isinstance(ranks_input, list):
        for i, items in enumerate(ranks_input):
            if isinstance(items, dict):
                # dict 格式: {doc_id: score}
                normalized = [(doc_id, score) for doc_id, score in items.items()]
                ranks_dict[f"source_{i}"] = normalized
            elif isinstance(items, list):
                normalized = _normalize_results(items)
                ranks_dict[f"source_{i}"] = normalized
    
    if not ranks_dict:
        return []
    
    # 收集所有文档
    all_docs = set()
    for source_ranks in ranks_dict.values():
        for item in source_ranks:
            if isinstance(item, (list, tuple)) and len(item) >= 1:
                all_docs.add(item[0])
            elif isinstance(item, str):
                all_docs.add(item)
    
    # 计算 RRF 分数
    rrf_scores = {}
    for doc_id in all_docs:
        score = 0.0
        for source_name, source_ranks in ranks_dict.items():
            # 找到该文档在当前源中的排名
            rank = None
            for i, item in enumerate(source_ranks):
                item_doc_id = item[0] if isinstance(item, (list, tuple)) else item
                if item_doc_id == doc_id:
                    rank = i + 1  # 排名从1开始
                    break
            
            if rank is not None:
                score += 1.0 / (k + rank)
        
        if score > 0:
            rrf_scores[doc_id] = score
    
    # 按分数排序
    sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


def _normalize_results(items: List) -> List[Tuple[str, float]]:
    """将各种格式统一为 [(doc_id, score), ...]"""
    normalized = []
    for item in items:
        if isinstance(item, dict):
            # {"doc_id": score} 或 {"path": "...", "score": 0.8}
            if "path" in item:
                normalized.append((item["path"], item.get("score", 1.0)))
            else:
                for doc_id, score in item.items():
                    normalized.append((doc_id, score))
        elif isinstance(item, (list, tuple)):
            if len(item) >= 2:
                normalized.append((item[0], item[1]))
            elif len(item) == 1:
                normalized.append((item[0], 1.0))
        elif isinstance(item, str):
            normalized.append((item, 1.0))
    return normalized


def merge_search_results(
    content_results: List[Tuple[str, float]],
    name_results: List[Tuple[str, float]],
    tag_results: List[Tuple[str, float]],
    path_results: List[Tuple[str, float]],
    weights: Dict[str, float] = None
) -> List[Tuple[str, float]]:
    """
    多维度搜索融合
    
    Args:
        content_results: 文件内容匹配结果
        name_results: 文件名匹配结果
        tag_results: 标签匹配结果
        path_results: 路径匹配结果
        weights: 各维度权重，默认均衡
    """
    if weights is None:
        weights = {
            "file_content": 0.8,
            "file_name": 0.5,
            "tags": 0.6,
            "directory_path": 0.5,
        }
    
    ranks_dict = {}
    
    if content_results:
        ranks_dict["content"] = content_results
    
    if name_results:
        ranks_dict["name"] = name_results
    
    if tag_results:
        ranks_dict["tags"] = tag_results
    
    if path_results:
        ranks_dict["path"] = path_results
    
    return rrf_ranks(ranks_dict)


# 缓存模块
class QueryCache:
    """查询结果缓存"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.access_order: List[str] = []
    
    def get(self, query: str, params: dict = None) -> Any:
        """获取缓存结果"""
        # 使用 query + params 作为复合 key
        if params:
            cache_key = f"{query}:{json.dumps(params, sort_keys=True)}"
        else:
            cache_key = query
            
        if cache_key not in self.cache:
            return None
        
        result, timestamp = self.cache[cache_key]
        if time.time() - timestamp > self.ttl:
            del self.cache[cache_key]
            if cache_key in self.access_order:
                self.access_order.remove(cache_key)
            return None
        
        return result
    
    def set(self, query: str, result: Any, params: dict = None):
        """设置缓存结果"""
        if params:
            cache_key = f"{query}:{json.dumps(params, sort_keys=True)}"
        else:
            cache_key = query
            
        if cache_key in self.cache:
            if cache_key in self.access_order:
                self.access_order.remove(cache_key)
        
        if len(self.cache) >= self.max_size:
            # LRU 淘汰
            oldest = self.access_order.pop(0)
            del self.cache[oldest]
        
        self.cache[cache_key] = (result, time.time())
        self.access_order.append(cache_key)
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.access_order.clear()


def rrf_ranks_compat(ranks_input: Union[Dict, List], k: int = 60) -> Dict[str, float]:
    """
    RRF 融合兼容版本，返回 dict 格式 {doc_id: score}
    """
    results = rrf_ranks(ranks_input, k)
    return {doc_id: score for doc_id, score in results}
