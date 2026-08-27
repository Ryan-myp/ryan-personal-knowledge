"""
api_server.py - ad-agent HTTP API 服务（FastAPI）
"""

import sys
import os
import json
import logging
import hmac
from contextlib import asynccontextmanager
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from starlette.concurrency import run_in_threadpool

# 导入 Agent 核心模块
from agents.ad_agent import AgentRuntime

# 配置路径
CONFIG_PATH = Path(__file__).parent / "config.yaml"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "chat.html"

# 全局 runtime
runtime: Optional[AgentRuntime] = None
runtime_status = {
    "state": "not_initialized",
    "error": None,
}


def _database_path() -> Path:
    """Resolve the service database independently of the process cwd."""
    configured = os.environ.get("AD_AGENT_DB_PATH")
    path = Path(configured).expanduser() if configured else Path(__file__).parent / "ad_agent.db"
    return path.resolve()

# The service may hold platform credentials in memory, so HTTP access is
# authenticated by default.  Local development can explicitly opt into an
# unauthenticated localhost-only mode with AD_AGENT_ALLOW_UNAUTHENTICATED=1.
API_KEY = os.environ.get("AD_AGENT_API_KEY", "")
ALLOW_UNAUTHENTICATED = os.environ.get("AD_AGENT_ALLOW_UNAUTHENTICATED", "0") == "1"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "AD_AGENT_CORS_ORIGINS",
        "http://127.0.0.1:8765,http://localhost:8765",
    ).split(",")
    if origin.strip()
]


def _authorize_request(api_key: Optional[str], request: Optional[Request] = None) -> None:
    """Authorize data-bearing endpoints without logging secrets.

    The explicit unauthenticated escape hatch is intentionally localhost-only;
    CORS is not an authentication boundary and cannot enforce that property.
    """
    if ALLOW_UNAUTHENTICATED:
        client_host = request.client.host if request and request.client else None
        if client_host in {"127.0.0.1", "::1", "localhost"}:
            return
        raise HTTPException(
            status_code=403,
            detail="Unauthenticated mode is restricted to localhost",
        )
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured; set AD_AGENT_API_KEY or explicitly enable local unauthenticated mode",
        )
    if not api_key or not hmac.compare_digest(api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


def _init_runtime():
    global runtime
    runtime_status.update({"state": "initializing", "error": None})
    try:
        from agents.ad_agent.persistence.store import AdAgentStore

        # Load the YAML once and make the execution contract explicit.  The
        # server remains dry-run by default; switching to live additionally
        # requires AD_AGENT_ENABLE_LIVE=1 and a non-empty code/config allowlist.
        import yaml
        config_path = Path(__file__).parent / "config.yaml"
        config = {}
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        requested_mode = config.get("execution_mode", config.get("mode", "dry_run"))
        if requested_mode not in {"dry_run", "live", "read_only"}:
            raise ValueError(f"Unsupported configured execution mode: {requested_mode}")
        read_only_mode = requested_mode == "read_only"
        execution_mode = "dry_run" if requested_mode == "read_only" else requested_mode
        if execution_mode == "live" and os.environ.get("AD_AGENT_ENABLE_LIVE") != "1":
            logger.warning("配置请求 live，但 AD_AGENT_ENABLE_LIVE 未显式开启；服务降级为 dry_run")
            execution_mode = "dry_run"

        store = AdAgentStore(str(_database_path()))
        runtime = AgentRuntime(
            persistence_store=store,
            read_only_mode=read_only_mode,
            execution_mode=execution_mode,
            live_approved_tools=set(config.get("live_approved_tools", []) or []),
            offline_mode=False,
        )

        credentials = {}
        models_config = {}
        
        # 优先从 JSON 凭证文件加载
        # __file__ = agents/ad_agent/api_server.py
        # parent.parent.parent = ryan-personal-knowledge
        creds_path = Path(__file__).parent.parent.parent / "config" / "ad_platform_credentials.json"
        if creds_path.exists():
            import json
            with open(creds_path) as f:
                creds_config = json.load(f)
                # 提取各平台凭证
                for platform in ['meta', 'google', 'tiktok', 'dv360']:
                    if platform in creds_config:
                        credentials[platform] = creds_config[platform]
        
        # 如果 JSON 文件不存在，回退到 YAML
        if not credentials and config_path.exists():
            credentials = config.get('credentials', {})
            models_config = config.get('models', {})
        
        # 设置凭证到 runtime
        runtime.set_credentials(credentials)
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
        runtime_status.update({"state": "ready", "error": None})
        return runtime
    except Exception as e:
        runtime = None
        runtime_status.update({"state": "failed", "error": f"{type(e).__name__}: {e}"})
        logger.exception("ad-agent Runtime 初始化失败")
        return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize and shut down the Runtime at ASGI lifecycle boundaries."""
    global runtime
    if runtime is None:
        if _init_runtime() is None:
            # Fail ASGI startup instead of serving a process that reports
            # healthy while every data endpoint is unusable.
            raise RuntimeError("ad-agent Runtime 初始化失败")
    try:
        yield
    finally:
        print("👋 ad-agent 服务已停止")


# 创建 FastAPI 应用
app = FastAPI(
    title="ad-agent API",
    description="广告投放 Agent HTTP API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


class ChatRequest(BaseModel):
    user_input: str
    session_id: Optional[str] = None
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
    state = runtime_status.get("state", "not_initialized")
    if runtime is not None and state == "not_initialized":
        # Useful for tests/embedding callers that inject an already-created
        # Runtime instead of going through the ASGI lifespan.
        state = "ready"
    return {
        "status": "healthy" if state == "ready" else "unhealthy",
        "state": state, "error": runtime_status.get("error"),
        "service": "ad-agent", "version": "1.0.0",
        "execution_mode": runtime.execution_mode if runtime else None,
        "platforms": list(platforms), "tools": len(tools),
    }


@app.post("/chat", tags=["chat"])
async def chat(
    request: ChatRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    try:
        _authorize_request(x_api_key, http_request)
        if request.confirmed and not request.confirmation_payload:
            raise HTTPException(
                status_code=400,
                detail="confirmed=true 必须携带与当前计划匹配的 confirmation_payload",
            )
        user_input = request.user_input
        
        result = await run_in_threadpool(
            runtime.run,
            user_input=user_input,
            session_id=request.session_id,
            user_id=request.user_id,
            account_id=request.account_id or None,
            platform_params=request.platform_params,
            confirmed=request.confirmed,
            confirmation_payload=request.confirmation_payload,
        )
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@app.get("/platforms", tags=["info"])
async def get_platforms(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    _authorize_request(x_api_key, http_request)
    if not runtime:
        return {"platforms": []}
    return {"platforms": runtime.registry.list_all_platforms()}


@app.get("/tools", tags=["info"])
async def get_tools(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    _authorize_request(x_api_key, http_request)
    if not runtime:
        return {"tools": []}
    tools = runtime.registry.list_all()
    return {
        "tools": [
            {
                "name": t.name,
                "platform": t.platform,
                "skill": t.skill,
                "description": t.description,
                "risk_level": t.risk_level.value,
                "effect_class": t.effect_class.value,
                "live_support": t.live_support,
                "input_schema": t.input_schema.to_dict() if t.input_schema else None,
            }
            for t in tools
        ]
    }


class ChatStreamRequest(BaseModel):
    user_input: str
    session_id: Optional[str] = None
    user_id: str = "web_user"
    account_id: str = ""
    confirmed: bool = False
    confirmation_payload: Optional[dict] = None
    platform_params: Optional[dict] = None


@app.post("/chat/stream", tags=["chat"])
async def chat_stream(
    request: ChatStreamRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """流式对话接口，返回 SSE 格式的思考过程"""
    from fastapi.responses import StreamingResponse
    
    if not runtime:
        return JSONResponse(content={"success": False, "error": "服务未初始化"}, status_code=503)
    
    try:
        _authorize_request(x_api_key, http_request)
        if request.confirmed and not request.confirmation_payload:
            raise HTTPException(
                status_code=400,
                detail="confirmed=true 必须携带与当前计划匹配的 confirmation_payload",
            )
        user_input = request.user_input
        
        async def generate():
            def event(payload: dict) -> str:
                return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            # 发送开始信号
            yield event({"type": "start", "content": "🤔 正在分析您的需求..."})
            
            # 执行对话
            result = await run_in_threadpool(
                runtime.run,
                user_input=user_input,
                session_id=request.session_id,
                user_id=request.user_id,
                account_id=request.account_id or None,
                platform_params=request.platform_params,
                confirmed=request.confirmed,
                confirmation_payload=request.confirmation_payload,
            )
            
            # 发送思考过程
            yield event({"type": "thinking", "content": "✅ 已完成分析，准备执行工具..."})
            
            # 发送工具执行状态
            for r in result.get("results", []):
                tool = r.get("tool", "")
                success = r.get("success", False)
                status = "✅" if success else "❌"
                yield event({"type": "tool_status", "tool": tool, "success": success, "status": f"{status} {tool}"})
            
            # 发送最终回复
            reply = result.get("reply", "")
            yield event({"type": "reply", "content": reply})
            
            # 发送完成信号
            yield event({"type": "done"})
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
