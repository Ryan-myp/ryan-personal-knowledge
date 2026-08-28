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
from pathlib import Path

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agents.ad_agent import (
    AgentRuntime,
    AdAgentStore,
)


def print_banner():
    """打印欢迎界面"""
    print("""
╔══════════════════════════════════════════════════════════════╗
    ║               🚀 ad-agent 广告专家助手（安全 dry-run）          ║
║                                                              ║
║  渠道能力: 从 skills/channels 自动发现                         ║
    ║  模式: 🧪 dry-run（创建/更新只生成计划，不调用线上写 API）      ║
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
    parser = argparse.ArgumentParser(description="ad-agent 对话入口（安全 dry-run 模式）")
    parser.add_argument("--credentials", help="API 凭证文件路径 (JSON)")
    parser.add_argument("--user", default="web_user", help="用户 ID")
    parser.add_argument(
        "--account",
        help="广告账户 ID；仅在白名单恰有一个账户时允许自动选择，多个账户必须显式指定",
    )
    args = parser.parse_args()

    # 初始化 Runtime（只读模式）
    database_path = Path(
        os.environ.get("AD_AGENT_DB_PATH", Path(__file__).parent / "ad_agent.db")
    ).expanduser().resolve()
    store = AdAgentStore(str(database_path))
    runtime = AgentRuntime(
        persistence_store=store,
        read_only_mode=False,
        execution_mode="dry_run",
        offline_mode=False,
        require_llm=True,
    )

    llm_api_key = os.environ.get("OPENAI_API_KEY", "")
    if not llm_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 未设置；ad-agent CLI 必须配置 LLM，禁止降级为规则解析"
        )
    from agents.ad_agent.core.llm_client import create_llm_client
    runtime.inject_llm(create_llm_client(
        model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        api_key=llm_api_key,
        base_url=os.environ.get("OPENAI_BASE_URL"),
    ))
    runtime.assert_llm_ready()

    # 加载凭证
    credentials = {}
    if args.credentials and os.path.exists(args.credentials):
        with open(args.credentials) as f:
            credentials = json.load(f)

    # 渠道 Skill 只提供专家上下文；Runtime 按目录约定自动发现对应
    # Capability，并按渠道约定创建 Client。新增渠道无需修改 CLI 的中心列表。
    skills_root = Path(__file__).parent / "skills"
    runtime.auto_load_skills(str(skills_root), credentials)

    print_banner()
    platforms = runtime.registry.list_all_platforms()
    tools = runtime.registry.list_all()
    print(f"✅ 已注册 {len(tools)} 个工具（dry-run，写操作只生成本地计划）")
    print(f"📦 平台: {', '.join(platforms)}")
    print(f"💾 持久化: {database_path}")
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

示例输入（dry-run 模式）:
  - 列出 Meta Campaign 列表
  - 查询 Google Ads 过去7天报表
  - 查看 TikTok 广告组列表
  - 获取 DV360 Campaign 详情
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
