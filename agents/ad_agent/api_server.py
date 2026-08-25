"""
api_server.py - ad-agent HTTP API 服务（FastAPI）
"""

import sys
import os
import atexit
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
from agents.ad_agent.skills.registry import load_all_skills, get_skill_registry
from agents.ad_agent.skills.loader import get_skill_loader

# 配置路径
CONFIG_PATH = Path(__file__).parent / "config.yaml"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "chat.html"

# 全局 runtime
runtime: Optional[AgentRuntime] = None


def _init_on_import():
    global runtime
    try:
        from agents.ad_agent.persistence.store import AdAgentStore
        store = AdAgentStore("ad_agent.db")
        runtime = AgentRuntime(persistence_store=store)
        
        # 加载配置
        config_path = Path(__file__).parent / "config.yaml"
        credentials = {}
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                credentials = yaml.safe_load(f).get('credentials', {})
        
        # 注入 LLM 客户端
        models_config = yaml.safe_load(open(config_path)).get('models', {})
        llm_model = models_config.get('default', 'agnes-2.5-flash')
        api_key = os.environ.get('OPENAI_API_KEY', '')
        
        if api_key:
            from agents.ad_agent.core.llm_client import create_llm_client
            base_url = models_config.get("openai", {}).get("base_url") or os.environ.get("OPENAI_BASE_URL")
            llm = create_llm_client(model=llm_model, api_key=api_key, base_url=base_url)
            runtime.inject_llm(llm)
            logger.info(f"✅ LLM 已注入: {llm_model}")
        else:
            logger.warning("⚠️ OPENAI_API_KEY 未设置，使用规则解析")
        
        # 自动加载 Skills
        skills_root = Path(__file__).parent / "skills"
        runtime.auto_load_skills(str(skills_root), credentials)
        
        print(f"\n📊 服务状态:")
        print(f"- ✅ {len(runtime.registry.list_all_platforms())} 平台 {len(runtime.registry.list_all())} 工具")
        print(f"- ✅ Skills 系统已就绪")
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()


_init_on_import()
atexit.register(lambda: print("👋 ad-agent 服务已停止"))

# 创建 FastAPI 应用
app = FastAPI(title="ad-agent API", description="广告投放 Agent HTTP API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class ChatRequest(BaseModel):
    user_input: str
    user_id: str = "web_user"
    account_id: str = ""
    confirmed: bool = False
    confirmation_payload: Optional[dict] = None
    platform_params: Optional[dict] = None


@app.get("/", response_class=HTMLResponse)
async def index():
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>模板文件不存在</h1>", status_code=404)


@app.get("/health", tags=["health"])
async def health():
    tools = runtime.registry.list_all() if runtime else []
    platforms = set(t.platform for t in tools)
    return {"status": "healthy", "service": "ad-agent", "version": "1.0.0", "platforms": list(platforms), "tools": len(tools)}


@app.post("/chat", tags=["chat"])
async def chat(request: ChatRequest):
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    try:
        user_input = request.user_input
        if request.confirmed and request.platform_params:
            params_str = [f"{k}={v}" for p in request.platform_params.values() for k, v in p.items()]
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
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@app.get("/platforms", tags=["info"])
async def get_platforms():
    if not runtime:
        return {"platforms": []}
    return {"platforms": runtime.registry.list_all_platforms()}


@app.get("/tools", tags=["info"])
async def get_tools():
    if not runtime:
        return {"tools": []}
    tools = runtime.registry.list_all()
    return {"tools": [{"name": t.name, "platform": t.platform, "skill": t.skill, "description": t.description} for t in tools]}
