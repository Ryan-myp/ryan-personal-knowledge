#!/usr/bin/env python3
"""
知识库优化通知服务
功能: 发送通知到不同渠道（macOS通知/Telegram/飞书/文件）
用法: python3 notify.py send --type optimize --message "知识库优化任务"
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

BASE_DIR = Path("/Users/yanping.ma/ryan-personal-knowledge")
NOTIFY_DIR = BASE_DIR / "listener" / "notifications"
LOG_FILE = BASE_DIR / "logs" / "notify.log"

# 通知渠道配置
CHANNELS = {
    "macos": False,           # macOS桌面通知
    "telegram": False,       # Telegram Bot（需配置）
    "feishu": False,         # 飞书Webhook（需配置）
    "file": True,            # 文件记录
    "pi_internal": True,     # Pi内部事件
}

class NotificationService:
    """通知服务"""
    
    def __init__(self):
        self.channels = CHANNELS.copy()
        self._setup_directories()
        self._setup_logging()
    
    def _setup_directories(self):
        """创建目录"""
        for d in [NOTIFY_DIR, BASE_DIR / "logs"]:
            d.mkdir(parents=True, exist_ok=True)
    
    def _setup_logging(self):
        """设置日志"""
        import logging
        self.logger = logging.getLogger("notify")
        self.logger.setLevel(logging.INFO)
        
        handler = logging.FileHandler(LOG_FILE)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)
    
    def send(self, 
             notify_type: str, 
             message: str, 
             priority: str = "normal",
             metadata: Optional[Dict] = None) -> Dict:
        """发送通知到所有渠道"""
        
        notification = {
            'id': self._generate_id(),
            'type': notify_type,
            'message': message,
            'priority': priority,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {},
            'sent_at': datetime.now().isoformat()
        }
        
        results = {}
        
        # macOS通知
        if self.channels.get('macos'):
            results['macos'] = self._send_macos(notification)
        
        # 文件通知
        if self.channels.get('file'):
            results['file'] = self._send_file(notification)
        
        # Pi内部事件（供AI检查）
        if self.channels.get('pi_internal'):
            results['pi'] = self._send_pi_internal(notification)
        
        # Telegram（需配置）
        if self.channels.get('telegram'):
            results['telegram'] = self._send_telegram(notification)
        
        # 飞书（需配置）
        if self.channels.get('feishu'):
            results['feishu'] = self._send_feishu(notification)
        
        self.logger.info(f"通知已发送: {notify_type} - {message}")
        self.logger.info(f"发送结果: {results}")
        
        return results
    
    def _send_macos(self, notification: Dict) -> bool:
        """发送macOS桌面通知"""
        try:
            title = f"📚 知识库优化: {notification['type']}"
            message = notification['message']
            
            script = f'''
            display notification "{message}" 
            with title "{title}"
            sound name "Default"
            '''
            
            subprocess.run(['osascript', '-e', script], 
                         capture_output=True, timeout=5)
            return True
        except Exception as e:
            self.logger.error(f"macOS通知失败: {e}")
            return False
    
    def _send_file(self, notification: Dict) -> bool:
        """写入通知文件"""
        try:
            # 保存到通知目录
            notify_file = NOTIFY_DIR / f"{notification['id']}.json"
            with open(notify_file, 'w') as f:
                json.dump(notification, f, ensure_ascii=False, indent=2)
            
            # 追加到日志
            with open(NOTIFY_DIR / "notifications.jsonl", 'a') as f:
                f.write(json.dumps(notification, ensure_ascii=False) + '\n')
            
            return True
        except Exception as e:
            self.logger.error(f"文件通知失败: {e}")
            return False
    
    def _send_pi_internal(self, notification: Dict) -> bool:
        """发送到Pi内部事件队列"""
        try:
            # 创建触发文件（供AI检查）
            trigger_dir = BASE_DIR / "listener" / "triggers"
            trigger_dir.mkdir(parents=True, exist_ok=True)
            
            trigger_file = trigger_dir / f"{notification['id']}.json"
            with open(trigger_file, 'w') as f:
                json.dump(notification, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            self.logger.error(f"Pi内部事件失败: {e}")
            return False
    
    def _send_telegram(self, notification: Dict) -> bool:
        """发送Telegram消息（需配置BOT_TOKEN和CHAT_ID）"""
        try:
            import urllib.request
            
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            chat_id = os.getenv('TELEGRAM_CHAT_ID')
            
            if not bot_token or not chat_id:
                self.logger.warning("Telegram未配置，跳过")
                return False
            
            message = f"""📚 **知识库优化通知**

类型: {notification['type']}
消息: {notification['message']}
时间: {notification['timestamp']}
优先级: {notification['priority']}

请在Pi中执行优化任务。"""
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = json.dumps({
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }).encode()
            
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                return result.get('ok', False)
                
        except Exception as e:
            self.logger.error(f"Telegram发送失败: {e}")
            return False
    
    def _send_feishu(self, notification: Dict) -> bool:
        """发送飞书消息（需配置WEBHOOK_URL）"""
        try:
            import urllib.request
            
            webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
            
            if not webhook_url:
                self.logger.warning("飞书未配置，跳过")
                return False
            
            message = {
                "msg_type": "text",
                "content": {
                    "text": f"""📚 知识库优化通知

类型: {notification['type']}
消息: {notification['message']}
时间: {notification['timestamp']}
优先级: {notification['priority']}

请在Pi中执行优化任务。"""
                }
            }
            
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(message).encode(),
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                return result.get('code', -1) == 0
                
        except Exception as e:
            self.logger.error(f"飞书发送失败: {e}")
            return False
    
    def _generate_id(self) -> str:
        """生成通知ID"""
        return f"notify_{int(datetime.now().timestamp())}_{os.getpid()}"
    
    def get_pending(self, limit: int = 10) -> List[Dict]:
        """获取待处理通知"""
        if not NOTIFY_DIR.exists():
            return []
        
        notifications = []
        for f in NOTIFY_DIR.glob("*.json"):
            try:
                with open(f, 'r') as file:
                    notifications.append(json.load(file))
            except:
                pass
        
        notifications.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return notifications[:limit]
    
    def mark_processed(self, notification_id: str) -> bool:
        """标记为已处理"""
        notify_file = NOTIFY_DIR / f"{notification_id}.json"
        if notify_file.exists():
            processed_dir = NOTIFY_DIR / "processed"
            processed_dir.mkdir(exist_ok=True)
            notify_file.rename(processed_dir / f"{datetime.now().timestamp()}_{notification_id}.json")
            return True
        return False


def main():
    parser = argparse.ArgumentParser(description='知识库优化通知服务')
    parser.add_argument('command', choices=['send', 'list', 'clear'],
                       help='命令')
    parser.add_argument('--type', '-t', help='通知类型')
    parser.add_argument('--message', '-m', help='通知消息')
    parser.add_argument('--priority', '-p', default='normal',
                       choices=['low', 'normal', 'high', 'urgent'])
    parser.add_argument('--metadata', help='元数据JSON字符串')
    
    args = parser.parse_args()
    service = NotificationService()
    
    if args.command == 'send':
        metadata = None
        if args.metadata:
            try:
                metadata = json.loads(args.metadata)
            except:
                print("❌ 元数据JSON格式错误")
                sys.exit(1)
        
        result = service.send(
            notify_type=args.type or 'optimize',
            message=args.message or '知识库优化任务',
            priority=args.priority,
            metadata=metadata
        )
        
        print("✅ 通知已发送")
        for channel, success in result.items():
            status = "✅" if success else "❌"
            print(f"   {status} {channel}")
    
    elif args.command == 'list':
        notifications = service.get_pending()
        if notifications:
            print(f"📋 待处理通知 ({len(notifications)}条):")
            for n in notifications:
                print(f"  [{n['priority']}] {n['type']}: {n['message']}")
                print(f"    时间: {n['timestamp']}")
        else:
            print("✅ 没有待处理通知")
    
    elif args.command == 'clear':
        processed_dir = NOTIFY_DIR / "processed"
        processed_dir.mkdir(exist_ok=True)
        
        count = 0
        for f in NOTIFY_DIR.glob("*.json"):
            f.rename(processed_dir / f.name)
            count += 1
        
        print(f"✅ 已清除 {count} 条通知")


if __name__ == '__main__':
    main()
