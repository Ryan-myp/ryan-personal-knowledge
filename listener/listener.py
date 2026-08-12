#!/usr/bin/env python3
"""
知识库优化监听服务
功能: 监听触发文件，发送通知，支持多种通知渠道
用法: python3 listener.py start|stop|status|trigger
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# 配置
BASE_DIR = Path("/Users/yanping.ma/ryan-personal-knowledge")
LISTENER_DIR = BASE_DIR / "listener"
TRIGGER_DIR = LISTENER_DIR / "triggers"
LOG_DIR = BASE_DIR / "logs"
NOTIFICATION_FILE = LISTENER_DIR / "notifications.jsonl"
PID_FILE = LISTENER_DIR / "listener.pid"

# 通知渠道
NOTIFICATION_CHANNELS = {
    "log": True,          # 日志文件
    "notification_file": True,  # 通知文件
    "desktop": False,     # 桌面通知（可选）
}

class KnowledgeListener:
    """知识库优化监听服务"""
    
    def __init__(self):
        self.triggers = []
        self.notifications = []
        self.running = False
        self._setup_directories()
        self._setup_logging()
    
    def _setup_directories(self):
        """创建必要目录"""
        for d in [LISTENER_DIR, TRIGGER_DIR, LOG_DIR]:
            d.mkdir(parents=True, exist_ok=True)
    
    def _setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger("knowledge_listener")
        self.logger.setLevel(logging.INFO)
        
        # 文件处理器
        log_file = LOG_DIR / "listener.log"
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)
        
        # 控制台处理器
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        self.logger.addHandler(console)
    
    def start(self, interval: int = 5):
        """启动监听服务"""
        if self._is_running():
            self.logger.warning("监听服务已在运行")
            return
        
        self.running = True
        self._write_pid()
        self.logger.info("🚀 监听服务启动...")
        self.logger.info(f"   触发目录: {TRIGGER_DIR}")
        self.logger.info(f"   检查间隔: {interval}秒")
        
        last_check = 0
        while self.running:
            try:
                current_time = time.time()
                
                # 定期检查触发文件
                if current_time - last_check >= interval:
                    self._check_triggers()
                    last_check = current_time
                
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                self.logger.info("收到中断信号，停止监听")
                break
            except Exception as e:
                self.logger.error(f"监听循环错误: {e}")
                time.sleep(1)
        
        self.stop()
    
    def _check_triggers(self):
        """检查触发文件"""
        try:
            if not TRIGGER_DIR.exists():
                return
            
            for trigger_file in TRIGGER_DIR.glob("*.json"):
                self._process_trigger(trigger_file)
                
        except Exception as e:
            self.logger.error(f"检查触发文件失败: {e}")
    
    def _process_trigger(self, trigger_file: Path):
        """处理单个触发文件"""
        try:
            with open(trigger_file, 'r') as f:
                data = json.load(f)
            
            task_type = data.get('type', 'unknown')
            message = data.get('message', '')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            self.logger.info(f"📥 收到触发: {task_type} - {message}")
            
            # 发送通知
            self._send_notification({
                'type': task_type,
                'message': message,
                'timestamp': timestamp,
                'source': str(trigger_file.name)
            })
            
            # 移动已处理的触发文件
            processed_dir = TRIGGER_DIR / "processed"
            processed_dir.mkdir(exist_ok=True)
            dest = processed_dir / f"{int(time.time())}_{trigger_file.name}"
            trigger_file.rename(dest)
            
        except Exception as e:
            self.logger.error(f"处理触发文件失败 {trigger_file}: {e}")
    
    def _send_notification(self, notification: Dict):
        """发送通知"""
        # 写入通知文件
        with open(NOTIFICATION_FILE, 'a') as f:
            f.write(json.dumps(notification, ensure_ascii=False) + '\n')
        
        # 记录日志
        self.logger.info(f"📢 通知已发送: {notification['type']}")
        
        # 桌面通知（如果启用）
        if NOTIFICATION_CHANNELS.get('desktop'):
            self._send_desktop_notification(notification)
    
    def _send_desktop_notification(self, notification: Dict):
        """发送桌面通知"""
        try:
            import subprocess
            msg = f"知识库优化: {notification['type']} - {notification['message']}"
            subprocess.run(['osascript', '-e', 
                          f'display notification "{msg}" with title "知识库优化"'],
                         capture_output=True)
        except Exception as e:
            self.logger.debug(f"桌面通知失败: {e}")
    
    def _write_pid(self):
        """写入PID文件"""
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    
    def _is_running(self) -> bool:
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
        """停止服务"""
        self.running = False
        self._remove_pid()
        self.logger.info("监听服务已停止")
    
    def _remove_pid(self):
        """移除PID文件"""
        if PID_FILE.exists():
            PID_FILE.unlink()
    
    def status(self) -> Dict:
        """获取状态"""
        result = {
            'running': self._is_running(),
            'notification_count': self._get_notification_count(),
            'pending_triggers': len(list(TRIGGER_DIR.glob("*.json"))),
            'last_notifications': self._get_recent_notifications(5)
        }
        return result
    
    def _get_notification_count(self) -> int:
        """获取通知数量"""
        if not NOTIFICATION_FILE.exists():
            return 0
        with open(NOTIFICATION_FILE, 'r') as f:
            return sum(1 for _ in f)
    
    def _get_recent_notifications(self, count: int = 5) -> List[Dict]:
        """获取最近通知"""
        if not NOTIFICATION_FILE.exists():
            return []
        
        notifications = []
        with open(NOTIFICATION_FILE, 'r') as f:
            for line in f:
                try:
                    notifications.append(json.loads(line.strip()))
                except:
                    pass
        
        return notifications[-count:]


def main():
    parser = argparse.ArgumentParser(description='知识库优化监听服务')
    parser.add_argument('command', choices=['start', 'stop', 'status', 'trigger'],
                       help='命令')
    parser.add_argument('--type', '-t', help='触发类型')
    parser.add_argument('--message', '-m', help='触发消息')
    parser.add_argument('--interval', '-i', type=int, default=5,
                       help='检查间隔（秒）')
    
    args = parser.parse_args()
    listener = KnowledgeListener()
    
    if args.command == 'start':
        listener.start(interval=args.interval)
    
    elif args.command == 'stop':
        listener.stop()
    
    elif args.command == 'status':
        status = listener.status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
    
    elif args.command == 'trigger':
        # 手动触发
        trigger_data = {
            'type': args.type or 'manual',
            'message': args.message or '手动触发优化',
            'timestamp': datetime.now().isoformat(),
            'triggered_by': 'manual'
        }
        
        trigger_file = TRIGGER_DIR / f"{int(time.time())}_manual.json"
        with open(trigger_file, 'w') as f:
            json.dump(trigger_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 触发文件已创建: {trigger_file}")
        print(f"   类型: {trigger_data['type']}")
        print(f"   消息: {trigger_data['message']}")


if __name__ == '__main__':
    main()
