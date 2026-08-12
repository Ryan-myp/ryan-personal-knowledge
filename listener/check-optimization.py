#!/usr/bin/env python3
"""
知识库优化检查工具
用途: AI在启动时检查是否有待处理的优化任务
用法: python3 check-optimization.py [--auto-execute]
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

BASE_DIR = Path("/Users/yanping.ma/ryan-personal-knowledge")
LISTENER_DIR = BASE_DIR / "listener"
NOTIFICATION_FILE = LISTENER_DIR / "notifications.jsonl"
PROCESS_DIR = LISTENER_DIR / "processed"

class OptimizationChecker:
    """优化任务检查器"""
    
    def __init__(self, auto_execute: bool = False):
        self.auto_execute = auto_execute
        self.notifications = []
        self._load_notifications()
    
    def _load_notifications(self):
        """加载通知"""
        if NOTIFICATION_FILE.exists():
            with open(NOTIFICATION_FILE, 'r') as f:
                for line in f:
                    try:
                        self.notifications.append(json.loads(line.strip()))
                    except:
                        pass
    
    def get_pending_tasks(self) -> List[Dict]:
        """获取待处理任务"""
        return [n for n in self.notifications if n.get('type') in ['optimize', 'hourly_optimize', 'weekly_optimize', 'deep_optimize']]
    
    def check_and_report(self) -> Dict:
        """检查并报告"""
        pending = self.get_pending_tasks()
        
        result = {
            'has_tasks': len(pending) > 0,
            'task_count': len(pending),
            'tasks': pending,
            'last_check': datetime.now().isoformat()
        }
        
        if pending:
            print("=" * 60)
            print("🔔 检测到待处理的优化任务")
            print("=" * 60)
            for task in pending:
                print(f"\n  类型: {task.get('type', 'unknown')}")
                print(f"  消息: {task.get('message', '无')}")
                print(f"  时间: {task.get('timestamp', 'unknown')}")
                print(f"  来源: {task.get('source', 'unknown')}")
            print("\n" + "=" * 60)
            
            if self.auto_execute:
                print("🚀 自动执行优化任务...")
                self.execute_tasks(pending)
            else:
                print("💡 提示: 使用 --auto-execute 参数自动执行")
        else:
            print("✅ 没有待处理的优化任务")
        
        return result
    
    def execute_tasks(self, tasks: List[Dict]):
        """执行任务"""
        print("\n开始执行优化任务...")
        
        for task in tasks:
            task_type = task.get('type', 'unknown')
            print(f"\n处理任务: {task_type}")
            
            # 标记为已处理
            task['processed'] = True
            task['processed_at'] = datetime.now().isoformat()
            
            # 移动到processed目录
            PROCESS_DIR.mkdir(parents=True, exist_ok=True)
            processed_file = PROCESS_DIR / f"{int(datetime.now().timestamp())}_{task.get('source', 'unknown')}.json"
            with open(processed_file, 'w') as f:
                json.dump(task, f, ensure_ascii=False, indent=2)
        
        # 清空通知文件
        with open(NOTIFICATION_FILE, 'w') as f:
            pass
        
        print("\n✅ 所有优化任务已标记为已处理")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.notifications)
        optimize_tasks = len([n for n in self.notifications if n.get('type') in ['optimize', 'hourly_optimize', 'weekly_optimize']])
        
        return {
            'total_notifications': total,
            'optimize_tasks': optimize_tasks,
            'pending_optimize': len(self.get_pending_tasks())
        }


def main():
    parser = argparse.ArgumentParser(description='知识库优化检查工具')
    parser.add_argument('--auto-execute', action='store_true',
                       help='自动执行待处理任务')
    parser.add_argument('--stats', action='store_true',
                       help='显示统计信息')
    
    args = parser.parse_args()
    
    checker = OptimizationChecker(auto_execute=args.auto_execute)
    
    if args.stats:
        stats = checker.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        result = checker.check_and_report()
        
        if result['has_tasks'] and not args.auto_execute:
            sys.exit(1)  # 有任务但未自动执行


if __name__ == '__main__':
    main()
