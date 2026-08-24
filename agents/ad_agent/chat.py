#!/usr/bin/env python3
"""
chat.py - ad-agent 对话入口（CLI 交互模式）

启动方式：
    python agents/ad_agent/chat.py
    
或者从根目录：
    python -m agents.ad_agent.chat
"""

import sys
import os
import argparse
import json
from datetime import datetime

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agents.ad_agent import (
    AgentRuntime,
    create_meta_capability,
    create_google_capability,
    create_tiktok_capability,
    create_dv360_capability,
    AdAgentStore,
)
from agents.ad_agent.user_skills.orchestrator import AdCampaignOrchestratorSkill


def print_banner():
    """打印欢迎界面"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                   🚀 ad-agent 对话入口                        ║
║                                                              ║
║  支持平台: Meta / Google Ads / TikTok / DV360                ║
║  模式: Mock (无需 API 凭证)                                  ║
║                                                              ║
║  命令:                                                       ║
║    /clear    - 清除会话历史                                   ║
║    /status   - 查看当前状态                                   ║
║    /help     - 显示帮助                                       ║
║    /quit     - 退出                                           ║
╚══════════════════════════════════════════════════════════════╝
""")


def print_result(result: dict):
    """打印执行结果"""
    print("\n" + "=" * 60)
    print("📊 执行结果")
    print("=" * 60)
    
    # Intent 信息
    intent = result.get("intent", {})
    print(f"\n🎯 意图: {intent.get('intent_type', 'unknown')}")
    print(f"📱 平台: {', '.join(intent.get('platforms', []))}")
    if intent.get('objective'):
        print(f"🎯 目标: {intent['objective']}")
    if intent.get('budget'):
        print(f"💰 预算: {intent['budget']} 元/天")
    
    # 工具调用
    tool_plan = result.get("tool_plan", {})
    if tool_plan:
        print(f"\n🔧 工具调用计划:")
        for platform, tools in tool_plan.items():
            print(f"  [{platform}]")
            for tool in tools:
                print(f"    • {tool}")
    
    # 执行结果
    results = result.get("results", [])
    if results:
        print(f"\n✅ 执行结果:")
        for r in results:
            status = "✅" if r.get("success") else "❌"
            tool = r.get("tool", "unknown")
            platform = r.get("platform", "?")
            data = r.get("data", {})
            print(f"  {status} [{platform}] {tool}")
            if data:
                for k, v in list(data.items())[:3]:
                    print(f"      {k}: {v}")
    
    # 确认卡片
    if result.get("needs_confirmation"):
        card = result.get("confirmation_payload", {})
        print(f"\n⚠️  需要确认:")
        print(f"   标题: {card.get('title', '确认投放计划')}")
        print(f"   操作: {[a['label'] for a in card.get('actions', [])]}")
    
    # 回复
    reply = result.get("reply", "")
    if reply:
        print(f"\n💬 {reply}")
    
    print("=" * 60)


def print_status(runtime: AgentRuntime, session_id: str):
    """打印当前状态"""
    tools = runtime.registry.list_all()
    platforms = set(t.platform for t in tools)
    print(f"\n📌 当前会话: {session_id}")
    print(f"🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🛠️  已注册工具: {len(tools)}")
    print(f"📦 平台: {', '.join(platforms)}")


def main():
    parser = argparse.ArgumentParser(description="ad-agent 对话入口")
    parser.add_argument("--credentials", help="API 凭证文件路径")
    parser.add_argument("--user", default="anonymous", help="用户 ID")
    parser.add_argument("--account", help="广告账户 ID")
    args = parser.parse_args()
    
    # 初始化 Runtime
    store = AdAgentStore("ad_agent.db")
    runtime = AgentRuntime(persistence_store=store)
    
    # 加载凭证（如果提供）
    credentials = {}
    if args.credentials and os.path.exists(args.credentials):
        with open(args.credentials) as f:
            credentials = json.load(f)
    
    # 注册所有平台 Capability
    runtime.register_capability(create_meta_capability(credentials.get("meta")))
    runtime.register_capability(create_google_capability(credentials.get("google")))
    runtime.register_capability(create_tiktok_capability(credentials.get("tiktok")))
    runtime.register_capability(create_dv360_capability())
    
    # 注册编排 Skill
    orchestrator = AdCampaignOrchestratorSkill()
    runtime.registry.register(orchestrator.get_tool_definition(), orchestrator.get_handler())
    
    print_banner()
    print(f"✅ 已注册 {len(runtime.registry.list_all())} 个工具")
    print(f"📦 平台: meta, google, tiktok, dv360")
    print(f"💾 持久化: ad_agent.db")
    print()
    
    # 对话循环
    session_id = None
    user_id = args.user
    
    while True:
        try:
            user_input = input("\n💬 你: ").strip()
            
            if not user_input:
                continue
            
            # 命令处理
            if user_input == "/quit" or user_input == "/exit":
                print("👋 再见！")
                break
            elif user_input == "/clear":
                session_id = None
                print("🗑️  会话已清除")
                continue
            elif user_input == "/status":
                print_status(runtime, session_id or "未开始")
                continue
            elif user_input == "/help":
                print("""
可用命令:
  /clear  - 清除当前会话
  /status - 查看运行状态
  /help   - 显示帮助
  /quit   - 退出程序

示例输入:
  - 帮我投放Meta广告，预算100元/天
  - 在TikTok上创建产品销售广告
  - 查询Meta和Google过去7天的报表
  - 用这张海报图，投放Meta和Google，预算200元/天
""")
                continue
            
            # 执行对话
            result = runtime.run(
                user_input=user_input,
                session_id=session_id,
                user_id=user_id,
                account_id=args.account,
                credentials=credentials,
            )
            
            # 保存 session_id
            session_id = result.get("session_id")
            
            # 打印结果
            print_result(result)
            
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
