#!/usr/bin/env python3
"""
知识蒸馏监控面板
显示蒸馏进度和统计信息
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional


class DistillMonitor:
    """知识蒸馏监控器"""
    
    def __init__(self, kb_root: str = "/Users/yanping.ma/ryan-personal-knowledge"):
        self.kb_root = Path(kb_root)
        self.stats_file = self.kb_root / "stats" / "distill_stats.json"
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
    
    def load_stats(self) -> dict:
        """加载统计信息"""
        if self.stats_file.exists():
            with open(self.stats_file, 'r') as f:
                return json.load(f)
        return {
            "total_distilled": 0,
            "projects": {},
            "history": [],
            "last_update": None,
        }
    
    def save_stats(self, stats: dict):
        """保存统计信息"""
        stats["last_update"] = datetime.now().isoformat()
        with open(self.stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
    
    def add_distillation(self, project_name: str, docs_count: int, 
                        duration_seconds: float):
        """记录一次蒸馏"""
        stats = self.load_stats()
        
        # 更新项目统计
        if project_name not in stats["projects"]:
            stats["projects"][project_name] = {
                "total_docs": 0,
                "total_duration": 0,
                "last_distill": None,
            }
        
        stats["projects"][project_name]["total_docs"] += docs_count
        stats["projects"][project_name]["total_duration"] += duration_seconds
        stats["projects"][project_name]["last_distill"] = datetime.now().isoformat()
        
        # 更新历史
        stats["history"].append({
            "project": project_name,
            "docs": docs_count,
            "duration": duration_seconds,
            "time": datetime.now().isoformat(),
        })
        
        # 只保留最近 100 条记录
        stats["history"] = stats["history"][-100:]
        
        # 更新总数
        stats["total_distilled"] = sum(
            p["total_docs"] for p in stats["projects"].values()
        )
        
        self.save_stats(stats)
    
    def show_dashboard(self):
        """显示仪表盘"""
        stats = self.load_stats()
        
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║              📊 知识蒸馏监控面板                            ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()
        
        # 总体统计
        print(f"📈 总体统计:")
        print(f"   - 已蒸馏项目: {len(stats['projects'])} 个")
        print(f"   - 生成文档: {stats['total_distilled']} 篇")
        print(f"   - 最后更新: {stats.get('last_update', '从未')}")
        print()
        
        # 项目详情
        if stats['projects']:
            print("📋 项目详情:")
            for name, info in stats['projects'].items():
                avg_time = info['total_duration'] / info['total_docs'] if info['total_docs'] > 0 else 0
                print(f"   📄 {name}:")
                print(f"      - 文档数: {info['total_docs']} 篇")
                print(f"      - 平均耗时: {avg_time:.1f} 秒/篇")
                print(f"      - 最后蒸馏: {info.get('last_distill', '从未')}")
            print()
        
        # 最近活动
        if stats['history']:
            print("🕐 最近活动:")
            for event in stats['history'][-5:][::-1]:
                time_str = event['time'][11:19] if 'T' in event['time'] else event['time']
                print(f"   [{time_str}] {event['project']}: +{event['docs']} 文档")
            print()
        
        # 下次计划
        print("🎯 下次计划:")
        print("   - 每小时: 增量蒸馏（优先级 1 项目）")
        print("   - 每天 02:00: 完整蒸馏")
        print("   - 每周日: LLM 项目专项蒸馏")
        print()


def main():
    monitor = DistillMonitor()
    monitor.show_dashboard()


if __name__ == "__main__":
    main()
