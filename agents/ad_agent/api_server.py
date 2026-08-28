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

from fastapi import FastAPI, HTTPException, Header, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from starlette.concurrency import run_in_threadpool

# 导入 Agent 核心模块
from agents.ad_agent import AgentRuntime
from agents.ad_agent.core.auth import RequestPrincipal

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


def _configured_service_principal() -> RequestPrincipal:
    """Build the service identity from trusted process configuration.

    A single shared API key has no end-user identity.  In that deployment
    shape, all requests intentionally run as one configured service principal;
    the JSON request body's ``user_id`` is never treated as authentication.
    Multi-user deployments should configure ``AD_AGENT_API_KEY_PRINCIPALS``
    instead.
    """
    if runtime is not None:
        permissions = set(getattr(runtime, "_granted_permissions", set()))
        validator = getattr(runtime, "whitelist_validator", None)
        account_scope = {
            str(platform): set(values or [])
            for platform, values in getattr(validator, "allowed_accounts", {}).items()
        } if validator is not None else {}
    else:
        permissions = set()
        account_scope = {}
    configured_permissions = os.environ.get("AD_AGENT_SERVICE_PERMISSIONS")
    if configured_permissions is not None:
        permissions = {
            item.strip() for item in configured_permissions.split(",") if item.strip()
        }
    return RequestPrincipal(
        user_id=os.environ.get("AD_AGENT_SERVICE_PRINCIPAL", "ad-agent-service"),
        tenant_id=os.environ.get("AD_AGENT_SERVICE_TENANT", "default"),
        permissions=frozenset(permissions),
        account_scope=account_scope,
        source="api-key-service",
    )


def _api_key_principals() -> dict[str, dict]:
    """Load API-key-to-principal claims without logging the key material."""
    raw = os.environ.get("AD_AGENT_API_KEY_PRINCIPALS", "")
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        logger.error("AD_AGENT_API_KEY_PRINCIPALS 不是合法 JSON；拒绝映射登录")
        return {}
    return value if isinstance(value, dict) else {}


def _safe_exception_text(error: Exception) -> str:
    """Keep provider/client exception text from becoming a secret sink."""
    return AgentRuntime._redact_for_persistence(str(error))


def _authorize_request(
    api_key: Optional[str], request: Optional[Request] = None
) -> RequestPrincipal:
    """Authorize data-bearing endpoints without logging secrets.

    The explicit unauthenticated escape hatch is intentionally localhost-only;
    CORS is not an authentication boundary and cannot enforce that property.
    The returned principal is the only identity passed into Runtime; request
    body/query user IDs are intentionally ignored.
    """
    if ALLOW_UNAUTHENTICATED:
        client_host = request.client.host if request and request.client else None
        if client_host in {"127.0.0.1", "::1", "localhost"}:
            return _configured_service_principal()
        raise HTTPException(
            status_code=403,
            detail="Unauthenticated mode is restricted to localhost",
        )
    principals = _api_key_principals()
    if principals:
        claims = principals.get(api_key or "")
        if not isinstance(claims, dict):
            raise HTTPException(status_code=401, detail="Invalid API key")
        try:
            return RequestPrincipal.from_claims(claims)
        except (TypeError, ValueError) as exc:
            logger.error("API key principal 配置无效: %s", exc)
            raise HTTPException(status_code=503, detail="API principal configuration is invalid")
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured; set AD_AGENT_API_KEY or explicitly enable local unauthenticated mode",
        )
    if not api_key or not hmac.compare_digest(api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return _configured_service_principal()


def _require_principal_permission(principal: RequestPrincipal, permission: str) -> None:
    """Keep durable recovery actions behind an explicit gateway grant."""
    if permission not in principal.permissions and "ads.write" not in principal.permissions:
        raise HTTPException(status_code=403, detail=f"缺少操作所需权限：{permission}")


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
            # A config allowlist is not enough to enable mutations.  Both the
            # checked-in switch and the deployment environment must opt in;
            # this remains false until an operator explicitly selects the
            # approved test account workflow.
            allow_live_writes=(
                bool(config.get("allow_live_writes", False))
                and os.environ.get("AD_AGENT_ENABLE_LIVE") == "1"
            ),
            granted_permissions=set(
                config.get("granted_permissions", ["ads.read", "ads.plan"]) or []
            ),
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
                # Each provider owns its credential shape.  Do not maintain a
                # second list of channels in the HTTP bootstrap path.
                credentials = {
                    str(platform): value
                    for platform, value in creds_config.items()
                    if isinstance(value, dict)
                }
        
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
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)


class ChatRequest(BaseModel):
    user_input: str = Field(min_length=1, max_length=12_000)
    session_id: Optional[str] = None
    user_id: str = Field(default="web_user", min_length=1, max_length=200)
    account_id: str = Field(default="", max_length=200)
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
        principal = _authorize_request(x_api_key, http_request)
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
            account_id=request.account_id or None,
            platform_params=request.platform_params,
            confirmed=request.confirmed,
            confirmation_payload=request.confirmation_payload,
            principal=principal,
        )
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": _safe_exception_text(e)},
            status_code=500,
        )


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
                "action": t.action,
                "resource_type": t.resource_type,
                "parent_resource_type": t.parent_resource_type,
                "intent_types": list(t.intent_types),
                "risk_level": t.risk_level.value,
                "effect_class": t.effect_class.value,
                "replay_policy": t.replay_policy.value,
                "traits": list(t.traits),
                "live_support": t.live_support,
                "timeout_seconds": t.timeout_seconds,
                "max_output_bytes": t.max_output_bytes,
                "required_permissions": list(t.required_permissions),
                "input_schema": t.input_schema.to_dict() if t.input_schema else None,
            }
            for t in tools
        ]
    }


class ChatStreamRequest(BaseModel):
    user_input: str = Field(min_length=1, max_length=12_000)
    session_id: Optional[str] = None
    user_id: str = Field(default="web_user", min_length=1, max_length=200)
    account_id: str = Field(default="", max_length=200)
    confirmed: bool = False
    confirmation_payload: Optional[dict] = None
    platform_params: Optional[dict] = None


class WorkflowReconcileRequest(BaseModel):
    """Provider-verified observations supplied by a recovery worker."""

    observations: object


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
        principal = _authorize_request(x_api_key, http_request)
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
                account_id=request.account_id or None,
                platform_params=request.platform_params,
                confirmed=request.confirmed,
                confirmation_payload=request.confirmation_payload,
                principal=principal,
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
        return JSONResponse(
            content={"success": False, "error": _safe_exception_text(e)},
            status_code=500,
        )


@app.get("/parameter-options", tags=["info"])
async def get_parameter_options(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    platform: Optional[str] = Query(None, max_length=50),
    field: Optional[str] = Query(None, max_length=100),
    tool_name: Optional[str] = Query(None, max_length=150),
):
    """Expose Skill-owned static enums and dynamic lookup descriptors."""
    _authorize_request(x_api_key, http_request)
    if not runtime:
        return {"options": []}
    return {
        "platform": platform,
        "field": field,
        "tool_name": tool_name,
        "options": runtime.list_parameter_options(platform, field, tool_name),
    }


@app.get("/workflows/{workflow_id}", tags=["workflows"])
async def get_workflow(
    workflow_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Read an auditable workflow without exposing credentials."""
    principal = _authorize_request(x_api_key, http_request)
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    try:
        workflow = runtime.get_workflow(
            workflow_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not workflow:
        raise HTTPException(status_code=404, detail="workflow not found")
    return workflow


@app.delete("/workflows/{workflow_id}", tags=["workflows"])
async def cancel_workflow(
    workflow_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Cancel a local workflow; this never calls a provider API."""
    principal = _authorize_request(x_api_key, http_request)
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    try:
        cancelled = runtime.cancel_workflow(
            workflow_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not cancelled:
        raise HTTPException(status_code=404, detail="workflow not found or not cancellable")
    return {"workflow_id": workflow_id, "status": "cancelled"}


@app.get("/workflows/{workflow_id}/resume-plan", tags=["workflows"])
async def get_workflow_resume_plan(
    workflow_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Return recovery items without replaying any provider write."""
    principal = _authorize_request(x_api_key, http_request)
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    try:
        return runtime.get_workflow_resume_plan(
            workflow_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail="workflow not found")


@app.post("/workflows/{workflow_id}/reconcile", tags=["workflows"])
async def reconcile_workflow(
    workflow_id: str,
    body: WorkflowReconcileRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Apply verified recovery observations; never contacts a provider."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.reconcile")
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    if not isinstance(body.observations, (list, dict)):
        raise HTTPException(status_code=422, detail="observations must be an array or object")
    try:
        return runtime.reconcile_workflow(
            workflow_id,
            body.observations,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail="workflow not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/workflows/{workflow_id}/reconcile/provider", tags=["workflows"])
async def reconcile_workflow_from_provider(
    workflow_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Resolve pending items with registered provider read-back adapters."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.reconcile")
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    try:
        return await run_in_threadpool(
            runtime.reconcile_workflow_from_provider,
            workflow_id=workflow_id,
            principal=principal,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail="workflow not found")
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
