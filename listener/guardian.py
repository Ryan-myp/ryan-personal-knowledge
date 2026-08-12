#!/usr/bin/env python3
"""
知识库优化守护进程
功能: 持续监听通知，发现后自动执行优化并git提交
用法: python3 guardian.py start|stop|status
"""

import os
import sys
import json
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

BASE_DIR = Path("/Users/yanping.ma/ryan-personal-knowledge")
LISTENER_DIR = BASE_DIR / "listener"
NOTIFY_DIR = LISTENER_DIR / "notifications"
LOG_DIR = BASE_DIR / "logs"
PID_FILE = LISTENER_DIR / "guardian.pid"
PROCESSING_DIR = NOTIFY_DIR / "processing"

# 确保目录存在
for d in [NOTIFY_DIR, LOG_DIR, PROCESSING_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "guardian.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("knowledge_guardian")


class KnowledgeGuardian:
    """知识库优化守护进程"""
    
    def __init__(self):
        self.running = False
        self.check_interval = 10  # 每10秒检查一次
        self.optimization_script = BASE_DIR / "scripts" / "auto-optimize.py"
    
    def start(self):
        """启动守护进程"""
        if self.is_running():
            logger.warning("守护进程已在运行")
            return
        
        self.running = True
        self._write_pid()
        logger.info("🚀 知识库优化守护进程启动")
        logger.info(f"   监听目录: {NOTIFY_DIR}")
        logger.info(f"   检查间隔: {self.check_interval}秒")
        
        while self.running:
            try:
                self._check_notifications()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.info("收到中断信号，停止守护进程")
                break
            except Exception as e:
                logger.error(f"守护进程错误: {e}")
                time.sleep(5)
        
        self.stop()
    
    def _check_notifications(self):
        """检查通知"""
        try:
            if not NOTIFY_DIR.exists():
                return
            
            # 查找新的通知文件
            for notify_file in NOTIFY_DIR.glob("notify_*.json"):
                if notify_file.name.startswith('.'):
                    continue
                
                try:
                    with open(notify_file, 'r') as f:
                        notification = json.load(f)
                    
                    notify_type = notification.get('type', 'unknown')
                    message = notification.get('message', '')
                    
                    logger.info(f"📥 检测到通知: {notify_type} - {message}")
                    
                    # 执行优化
                    if self._execute_optimization(notification):
                        # 标记为已处理
                        self._mark_processed(notify_file, notification)
                        logger.info(f"✅ 优化任务完成: {notify_type}")
                    else:
                        logger.error(f"❌ 优化任务失败: {notify_type}")
                        
                except Exception as e:
                    logger.error(f"处理通知失败 {notify_file}: {e}")
                    
        except Exception as e:
            logger.error(f"检查通知失败: {e}")
    
    def _execute_optimization(self, notification: Dict) -> bool:
        """执行优化任务"""
        try:
            logger.info("🔧 开始执行优化...")
            
            # 运行优化脚本
            result = subprocess.run(
                ['python3', str(self.optimization_script)],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.info("✅ 优化脚本执行成功")
                logger.info(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
                return True
            else:
                logger.error(f"❌ 优化脚本执行失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ 优化脚本执行超时")
            return False
        except Exception as e:
            logger.error(f"执行优化失败: {e}")
            return False
    
    def _mark_processed(self, notify_file: Path, notification: Dict):
        """标记为已处理"""
        try:
            # 移动到processing目录
            processed_file = PROCESSING_DIR / f"{int(time.time())}_{notify_file.name}"
            notify_file.rename(processed_file)
            
            # 记录处理结果
            result_record = {
                'notification': notification,
                'processed_at': datetime.now().isoformat(),
                'status': 'success'
            }
            
            result_file = processed_file.with_suffix('.result.json')
            with open(result_file, 'w') as f:
                json.dump(result_record, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"标记处理失败: {e}")
    
    def _write_pid(self):
        """写入PID文件"""
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    
    def _remove_pid(self):
        """移除PID文件"""
        if PID_FILE.exists():
            PID_FILE.unlink()
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        if not PID_FILE.exists():
            return False
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError):
            return False
    
    def stop(self):
        """停止守护进程"""
        self.running = False
        self._remove_pid()
        logger.info("🛑 守护进程已停止")
    
    def status(self) -> Dict:
        """获取状态"""
        return {
            'running': self.is_running(),
            'pending_notifications': len(list(NOTIFY_DIR.glob("notify_*.json"))),
            'processing_count': len(list(PROCESSING_DIR.glob("notify_*.json")))
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='知识库优化守护进程')
    parser.add_argument('command', choices=['start', 'stop', 'status', 'restart'],
                       help='命令')
    
    args = parser.parse_args()
    guardian = KnowledgeGuardian()
    
    if args.command == 'start':
        if guardian.is_running():
            print("守护进程已在运行")
            sys.exit(0)
        guardian.start()
    
    elif args.command == 'stop':
        guardian.stop()
    
    elif args.command == 'status':
        status = guardian.status()
        print(json.dumps(status, indent=2))
    
    elif args.command == 'restart':
        guardian.stop()
        time.sleep(1)
        guardian.start()


if __name__ == '__main__':
    main()
