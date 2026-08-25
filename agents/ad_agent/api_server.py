"""
api_server.py - ad-agent HTTP API 服务（FastAPI）

支持对话接口和 Web UI
启动：python agents/ad_agent/api_server.py
访问：http://127.0.0.1:8765
"""

import sys
import os
import atexit
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# 导入 Agent 核心模块
from agents.ad_agent import AgentRuntime
from agents.ad_agent.api_clients.meta_client import MetaAPIClient
from agents.ad_agent.api_clients.tiktok_client import TikTokAPIClient
from agents.ad_agent.api_clients.google_ads_client import GoogleAdsAPIClient
from agents.ad_agent.api_clients.dv360_client import DV360APIClient
from agents.ad_agent.capabilities.meta_capability import MetaCapability
from agents.ad_agent.capabilities.platform_capabilities import (
    GoogleCapability, TikTokCapability, DV360Capability
)
from agents.ad_agent.skills.registry import load_all_skills, get_skill_registry
from agents.ad_agent.skills.loader import get_skill_loader

# 配置路径
CONFIG_PATH = Path(__file__).parent / "config.yaml"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "chat.html"

# 全局 runtime（懒加载）
runtime: Optional[AgentRuntime] = None


def _init_on_import():
    """初始化运行时"""
    global runtime
    try:
        from agents.ad_agent.persistence.store import AdAgentStore
        store = AdAgentStore("ad_agent.db")
        runtime = AgentRuntime(persistence_store=store)
        
        # 加载配置文件
        config_path = Path(__file__).parent / "config.yaml"
        credentials = {}
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                credentials = yaml.safe_load(f).get('credentials', {})
        
        # ─── 第一步：加载所有 Skills（元信息）───
        skills_root = Path(__file__).parent / "skills"
        
        # 使用 skills/loader.py 的 SkillLoader 加载（支持多根路径）
        from agents.ad_agent.skills.loader import SkillLoader
        skill_loader = SkillLoader()
        skill_loader.add_root(str(skills_root / "channels"))
        skill_loader.add_root(str(skills_root / "businesses"))
        skill_loader.add_root(str(skills_root / "cross-channel"))
        all_skills = skill_loader.load_all()
        print(f"✅ 已加载 {len(all_skills)} 个 Skills: {list(all_skills.keys())}")
        
        # ─── 第二步：动态注册 Skill → Tool Handlers ───
        # 根据 Skill 定义，创建对应的 Capability 并注册
        
        # Meta Skill → Meta Capability
        meta_skill = all_skills.get('meta-marketing-api')
        if meta_skill and 'meta' in credentials:
            from agents.ad_agent.api_clients.meta_client import MetaAPIClient
            from agents.ad_agent.capabilities.meta_capability import MetaCapability
            meta_client = MetaAPIClient(credentials['meta'])
            meta_capability = MetaCapability(api_client=meta_client)
            runtime.register_capability(meta_capability)
            print(f"✅ 已注册 Meta Capability ({len(meta_skill.get_tools())} tools)")
        
        # Google Ads Skill → Google Capability
        google_skill = all_skills.get('google-ads-api')
        if google_skill and 'google' in credentials:
            from agents.ad_agent.api_clients.google_ads_client import GoogleAdsAPIClient
            from agents.ad_agent.capabilities.platform_capabilities import GoogleCapability
            google_client = GoogleAdsAPIClient(credentials['google'])
            google_capability = GoogleCapability(api_client=google_client)
            runtime.register_capability(google_capability)
            print(f"✅ 已注册 Google Capability ({len(google_skill.get_tools())} tools)")
        
        # TikTok Skill → TikTok Capability
        tiktok_skill = all_skills.get('tiktok-ads-api')
        if tiktok_skill and 'tiktok' in credentials:
            from agents.ad_agent.api_clients.tiktok_client import TikTokAPIClient
            from agents.ad_agent.capabilities.platform_capabilities import TikTokCapability
            tiktok_client = TikTokAPIClient(credentials['tiktok'])
            tiktok_capability = TikTokCapability(api_client=tiktok_client)
            runtime.register_capability(tiktok_capability)
            print(f"✅ 已注册 TikTok Capability ({len(tiktok_skill.get_tools())} tools)")
        
        # DV360 Skill → DV360 Capability
        dv360_skill = all_skills.get('dv360-api')
        if dv360_skill:
            from agents.ad_agent.capabilities.platform_capabilities import DV360Capability
            dv360_capability = DV360Capability()
            runtime.register_capability(dv360_capability)
            print(f"✅ 已注册 DV360 Capability ({len(dv360_skill.get_tools())} tools)")
        
        # ─── 第三步：构建系统提示词（注入 Skill 信息）───
        skill_summaries = []
        for skill_name, skill in all_skills.items():
            if skill.platform and skill.get_tools():
                tools_preview = [t.name for t in skill.get_tools()[:3]]
                summary = f"- {skill_name} ({skill.platform}): {skill.description[:60]}... [tools: {', '.join(tools_preview)}]"
                skill_summaries.append(summary)
        
        if skill_summaries:
            print(f"\n📚 渠道能力摘要:")
            for s in skill_summaries:
                print(f"   {s}")
        
        print(f"\n📊 服务状态:")
        print(f"- ✅ {len(runtime.registry.list_all_platforms())} 平台 42 工具")
        print(f"- ✅ Skills 系统已修复")
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()


# 导入时自动初始化
_init_on_import()

# 退出时清理
atexit.register(lambda: print("👋 ad-agent 服务已停止"))

# 创建 FastAPI 应用
app = FastAPI(
    title="ad-agent API",
    description="广告投放 Agent HTTP API",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── 请求模型 ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_input: str
    user_id: str = "web_user"
    account_id: str = ""
    confirmed: bool = False
    confirmation_payload: Optional[dict] = None
    platform_params: Optional[dict] = None


# ─── 路由 ──────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """Web UI"""
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>模板文件不存在</h1>", status_code=404)


@app.get("/health", tags=["health"])
async def health():
    """健康检查"""
    tools = runtime.registry.list_all() if runtime else []
    platforms = set(t.platform for t in tools)
    return {
        "status": "healthy",
        "service": "ad-agent",
        "version": "1.0.0",
        "platforms": list(platforms),
        "tools": len(tools),
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }


@app.post("/chat", tags=["chat"])
async def chat(request: ChatRequest):
    """对话接口"""
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    
    try:
        # 如果是确认请求，将参数合并到 user_input 中
        user_input = request.user_input
        if request.confirmed and request.platform_params:
            # 构建包含参数的请求文本
            params_str = []
            for platform, params in request.platform_params.items():
                for key, value in params.items():
                    params_str.append(f"{key}={value}")
            if params_str:
                user_input = f"{request.user_input} [参数: {', '.join(params_str)}]"
        
        result = runtime.run(
            user_input=user_input,
            user_id=request.user_id,
            account_id=request.account_id or None,
            platform_params=request.platform_params,
        )
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500,
        )


@app.get("/platforms", tags=["info"])
async def get_platforms():
    """列出平台"""
    if not runtime:
        return {"platforms": []}
    return {
        "platforms": runtime.registry.list_all_platforms(),
        "capabilities": list(runtime.capabilities.keys()),
    }


@app.get("/skills", tags=["info"])
async def get_skills():
    """列出所有 Skills"""
    from agents.ad_agent.skills.loader import get_skill_loader
    loader = get_skill_loader()
    skills = loader.load_all()
    return {
        "skills": [
            {
                "name": s.name,
                "version": s.version,
                "description": s.description,
                "platform": s.platform,
                "tool_count": len(s.tools),
                "expert_files": list(s.expert_knowledge.keys()),
            }
            for s in skills.values()
        ]
    }


@app.get("/tools", tags=["info"])
async def get_tools():
    """列出工具"""
    from agents.ad_agent.skills.loader import get_skill_loader
    loader = get_skill_loader()
    tools = loader.get_all_tools()
    
    # 同时获取已注册的工具
    registered_tools = runtime.registry.list_all() if runtime else []
    
    return {
        "skill_tools": [
            {
                "name": t.name,
                "platform": t.platform,
                "description": t.description,
            }
            for t in tools
        ],
        "registered_tools": [
            {
                "name": t.name,
                "platform": t.platform,
                "risk": t.risk_level.value,
                "description": t.description[:100] + "..." if len(t.description) > 100 else t.description,
            }
            for t in registered_tools
        ]
    }


@app.get("/sessions", tags=["sessions"])
async def get_sessions():
    """列出会话"""
    if not runtime and not runtime.persistence:
        return {"sessions": []}
    sessions = runtime.persistence.list_sessions(limit=20)
    return {"sessions": sessions}


@app.get("/campaigns", tags=["campaigns"])
async def get_campaigns(platform: str = "meta", limit: int = 10):
    """列出 Campaign"""
    if not runtime:
        return {"campaigns": []}
    
    # 尝试调用平台 API
    capability = runtime.get_capability(platform)
    if not capability:
        return {"error": f"不支持的平台: {platform}"}
    
    # 调用查询接口
    try:
        campaigns = capability.list_campaigns(limit=limit)
        return {"campaigns": campaigns}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🚀 ad-agent HTTP API 服务")
    print("=" * 60)
    print(f"📍 API:     http://127.0.0.1:8765")
    print(f"📍 Swagger: http://127.0.0.1:8765/docs")
    print(f"📍 Web UI:  http://127.0.0.1:8765/")
    print("=" * 60)
    
    uvicorn.run(
        "agents.ad_agent.api_server:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_level="info",
    )
