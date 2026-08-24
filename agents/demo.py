#!/usr/bin/env python3
"""
demo.py - 广告投放 Agent 演示

演示单 Agent + 多 Skills 架构的完整流程：
1. 注册所有平台 Capability
2. 注册编排 Skill
3. 接收用户输入 → 意图解析 → 工具路由 → 执行 → 返回结果
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ad_agent import (
    AgentRuntime,
    create_meta_capability,
    create_google_capability,
    create_tiktok_capability,
    create_dv360_capability,
    AdCampaignOrchestratorSkill,
)


def demo_basic_flow():
    """演示基本流程：用户输入 → 多平台广告创建"""
    
    print("=" * 60)
    print("🚀 广告投放 Agent 演示")
    print("=" * 60)
    
    # Step 1: 创建 Runtime
    runtime = AgentRuntime()
    
    # Step 2: 注册所有平台 Capability
    print("\n📦 注册平台 Capability...")
    
    meta_cap = create_meta_capability()
    google_cap = create_google_capability()
    tiktok_cap = create_tiktok_capability()
    dv360_cap = create_dv360_capability()
    
    runtime.register_capability(meta_cap)
    runtime.register_capability(google_cap)
    runtime.register_capability(tiktok_cap)
    runtime.register_capability(dv360_cap)
    
    print("  ✅ Meta Capability 已注册")
    print("  ✅ Google Ads Capability 已注册")
    print("  ✅ TikTok Capability 已注册")
    print("  ✅ DV360 Capability 已注册")
    
    # Step 3: 注册编排 Skill
    print("\n🔧 注册编排 Skill...")
    skill = AdCampaignOrchestratorSkill()
    orchestrator_defn, orchestrator_handler = skill.get_tool_definition(), skill.get_handler()
    runtime.registry.register(orchestrator_defn, orchestrator_handler)
    print("  ✅ ad_campaign_orchestrator 已注册")
    
    # 打印已注册的工具
    print(f"\n📋 已注册工具总数: {len(runtime.registry.list_all())}")
    print("  按平台分布:")
    for platform in ["meta", "google", "tiktok", "dv360"]:
        tools = runtime.registry.list_by_platform(platform)
        tool_names = [t.name for t in tools]
        print(f"    {platform}: {tool_names}")
    
    # Step 4: 模拟用户请求
    print("\n" + "=" * 60)
    print("📝 测试用例 1: 多平台 Campaign 创建")
    print("=" * 60)
    
    user_input = "用这张海报图，帮我投放Meta和Google广告，预算100元/天，跑7天"
    print(f"\n用户输入: {user_input}")
    
    result = runtime.run(
        user_input=user_input,
        user_id="ryan_test",
        account_id="test_account_123",
    )
    
    print(f"\n✅ 执行结果:")
    print(f"   Intent Type: {result['intent']['intent_type']}")
    print(f"   Platforms: {result['intent']['platforms']}")
    print(f"   Objective: {result['intent']['objective']}")
    print(f"   Budget: {result['intent']['budget']}")
    print(f"\n🔧 Tool Calls:")
    for platform, tools in result['tool_plan'].items():
        print(f"   [{platform}] {tools}")
    print(f"\n📊 Results:")
    for r in result['results']:
        status = "✅" if r['success'] else "❌"
        print(f"   {status} [{r.get('platform', '?')}] {r['tool']}: {r.get('data', {})}")
    print(f"\n💬 Reply: {result['reply']}")
    
    # Step 5: 演示单平台
    print("\n" + "=" * 60)
    print("📝 测试用例 2: 单平台 TikTok 投放")
    print("=" * 60)
    
    user_input2 = "在 TikTok 上投放一个产品销售广告，预算50元/天"
    print(f"\n用户输入: {user_input2}")
    
    result2 = runtime.run(
        user_input=user_input2,
        user_id="ryan_test",
    )
    
    print(f"\n✅ 执行结果:")
    print(f"   Intent Type: {result2['intent']['intent_type']}")
    print(f"   Platforms: {result2['intent']['platforms']}")
    print(f"\n🔧 Tool Calls: {result2['tool_plan']}")
    print(f"\n💬 Reply: {result2['reply']}")
    
    # Step 6: 演示报表查询
    print("\n" + "=" * 60)
    print("📝 测试用例 3: 查询报表")
    print("=" * 60)
    
    user_input3 = "查询 Meta 和 Google 过去7天的投放报表"
    print(f"\n用户输入: {user_input3}")
    
    result3 = runtime.run(
        user_input=user_input3,
        user_id="ryan_test",
    )
    
    print(f"\n✅ 执行结果:")
    print(f"   Intent Type: {result3['intent']['intent_type']}")
    print(f"   Platforms: {result3['intent']['platforms']}")
    print(f"\n🔧 Tool Calls: {result3['tool_plan']}")
    print(f"\n💬 Reply: {result3['reply']}")
    
    print("\n" + "=" * 60)
    print("✅ 演示完成！")
    print("=" * 60)


def demo_orchestrator_tool():
    """演示编排工具的直接调用"""
    
    print("\n" + "=" * 60)
    print("🔧 直接调用编排工具")
    print("=" * 60)
    
    runtime = AgentRuntime()
    
    # 注册平台
    for cap_factory in [create_meta_capability, create_google_capability,
                        create_tiktok_capability, create_dv360_capability]:
        runtime.register_capability(cap_factory())
    
    # 直接调用编排工具
    from agents.ad_agent.user_skills.orchestrator import AdCampaignOrchestratorSkill
    
    skill = AdCampaignOrchestratorSkill()
    handler = skill.get_handler()
    
    ctx = type('Ctx', (), {
        'session_id': 'demo_session',
        'user_id': 'test_user',
        'account_id': 'acc_123',
        'credentials': {},
        'protected_state': {},
        'messages': [],
        'metadata': {},
        'get_protected': lambda self, k, d=None: d,
    })()
    
    input_data = {
        "user_input": "投放Meta和Google，销售目标，预算200元/天",
        "platforms": ["meta", "google"],
        "objective": "sales",
        "budget": 200,
        "creative_materials": [{"type": "image", "description": "summer_poster"}],
    }
    
    result = handler.execute(ctx, input_data)
    
    print(f"\n编排结果:")
    print(f"  需要确认: {result.requires_confirmation}")
    if result.card_payload:
        print(f"  卡片标题: {result.card_payload.get('title')}")
        print(f"  计划平台: {[p['platform'] for p in result.card_payload.get('plan', [])]}")
        print(f"  可用操作: {[a['label'] for a in result.card_payload.get('actions', [])]}")


if __name__ == "__main__":
    demo_basic_flow()
    demo_orchestrator_tool()
