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
        print(f"✅ 已注册平台: {', '.join(runtime.registry.list_all_platforms())}")
        print(f"✅ 已注册工具: {len(runtime.registry.list_all())}")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")


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
        result = runtime.run(
            user_input=request.user_input,
            user_id=request.user_id,
            account_id=request.account_id or None,
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


@app.get("/tools", tags=["info"])
async def get_tools():
    """列出工具"""
    if not runtime:
        return {"tools": []}
    tools = runtime.registry.list_all()
    return {
        "tools": [
            {
                "name": t.name,
                "platform": t.platform,
                "risk": t.risk_level.value,
                "description": t.description[:100] + "..." if len(t.description) > 100 else t.description,
            }
            for t in tools
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
