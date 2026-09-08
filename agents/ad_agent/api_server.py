"""
api_server.py - ad-agent HTTP API 服务（FastAPI）
"""

import sys
import os
import json
import logging
import hmac
import asyncio
import queue
import inspect
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
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal, Optional
from starlette.concurrency import run_in_threadpool

# Keep local credentials and model selection outside source control while
# making service startup reproducible. Explicit process environment variables
# take precedence over the ignored file.
from agents.ad_agent.core.local_config import load_default_local_env, load_local_env_file
load_default_local_env()

# 导入 Agent 核心模块
from agents.ad_agent import AgentRuntime
from agents.ad_agent.core.auth import RequestPrincipal
from agents.ad_agent.core.plugin_package import PluginPackageError
from agents.ad_agent.core.memory import MEMORY_KINDS
from agents.ad_agent.plugin_management import PluginPackageManager
from agents.ad_agent.skill_management import (
    BuiltinSkillCatalog,
    ManagedSkillManager,
    SkillPackageError,
)
from agents.ad_agent.knowledge_management import (
    KnowledgeDocumentError,
    ManagedKnowledgeManager,
)
from agents.ad_agent.persistence.factory import create_persistence_store

# 配置路径
CONFIG_PATH = Path(__file__).parent / "config.yaml"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "chat.html"
STATIC_PATH = Path(__file__).parent / "static"
BUILTIN_SKILLS_ROOT = Path(__file__).parent / "skills"
# Deployment-owned catalog. It is read-only and intentionally independent of
# tenant Skill persistence; the Runtime remains the execution source of truth.
builtin_skill_catalog = BuiltinSkillCatalog(BUILTIN_SKILLS_ROOT)

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

        store = create_persistence_store(sqlite_path=_database_path())
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
                config.get(
                    "granted_permissions",
                    ["ads.read", "ads.plan", "knowledge.read", "knowledge.write"],
                ) or []
            ),
            offline_mode=False,
            require_llm=True,
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
        llm_model = os.environ.get("LLM_MODEL", "").strip() or models_config.get("default")
        api_key = os.environ.get('OPENAI_API_KEY', '')
        
        if api_key:
            from agents.ad_agent.core.llm_client import create_llm_client
            base_url = models_config.get("openai", {}).get("base_url") or os.environ.get("OPENAI_BASE_URL")
            llm = create_llm_client(model=llm_model, api_key=api_key, base_url=base_url)
            runtime.inject_llm(llm)
            logger.info(f"✅ LLM 已注入: {llm_model}")
        else:
            raise RuntimeError(
                "OPENAI_API_KEY 未设置；ad-agent 服务必须配置 LLM，禁止降级为规则解析"
            )

        runtime.assert_llm_ready()
        
        # 自动加载 Skills
        skills_root = Path(__file__).parent / "skills"
        runtime.auto_load_skills(
            str(skills_root), credentials,
            allow_executable_plugins=True,
            allow_capability_discovery=True,
        )

        # Published user Skills are standard directory snapshots loaded as
        # advisory context only. They never replace or add provider Tools.
        # This process is intentionally bound to its configured service
        # tenant; multi-tenant deployments should isolate Runtime contexts.
        skill_manager = ManagedSkillManager(store)
        recovered = skill_manager.recover_interrupted_evaluations(
            stale_after_seconds=0
        )
        if recovered:
            logger.warning("已恢复 %s 个被中断的 Skill-up 评测任务", recovered)
        skill_manager.activate_published(
            os.environ.get("AD_AGENT_SERVICE_TENANT", "default"), runtime
        )

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
    active_runtime = runtime
    try:
        yield
    finally:
        # Runtime owns the durable worker lifecycle. Shut it down through the
        # generic lifecycle seam so ASGI reloads/tests do not leave task
        # workers holding SQLite connections or provider-adjacent state.
        close = getattr(active_runtime, "close", None)
        if callable(close):
            close(wait=True)
        else:
            executor = getattr(active_runtime, "task_executor", None)
            shutdown = getattr(executor, "shutdown", None)
            if callable(shutdown):
                shutdown(wait=True)
        if runtime is active_runtime:
            # Permit a later ASGI lifespan (reload/test restart) to create a
            # fresh Runtime instead of reusing one whose workers are closed.
            runtime = None
        print("👋 ad-agent 服务已停止")


# 创建 FastAPI 应用
app = FastAPI(
    title="ad-agent API",
    description="广告投放 Agent HTTP API",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
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
    creation_blueprint_id: Optional[str] = Field(default=None, max_length=200)
    creation_blueprint_version: Optional[str] = Field(default=None, max_length=32)
    # Per-turn override; omitted requests use the principal-scoped setting.
    execution_mode: Optional[Literal["dry_run", "live"]] = None


class ExecutionModeRequest(BaseModel):
    """Request to change the authenticated principal's Runtime mode."""

    mode: str = Field(min_length=1, max_length=16)


class SessionDeleteRequest(BaseModel):
    """Bounded local conversation deletion request."""

    session_ids: list[str] = Field(min_length=1, max_length=50)


class SessionRenameRequest(BaseModel):
    """A short user-facing title for one local conversation."""

    title: str = Field(min_length=1, max_length=32)


class TaskSubmitRequest(BaseModel):
    """Data-only asynchronous task envelope.

    The initial registered kind is ``agent.turn``.  Its payload is the same
    safe, provider-neutral input accepted by ``/chat``.  The API never
    accepts callbacks, scripts, Provider clients or credentials.
    """

    kind: str = Field(default="agent.turn", min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=200)


class MemoryWriteRequest(BaseModel):
    """Explicit user memory; identity and tenant come from the principal."""

    content: str = Field(min_length=1, max_length=4000)
    kind: str = Field(default="semantic", min_length=1, max_length=32)
    tags: list[str] = Field(default_factory=list, max_length=20)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


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
    live_reason = None
    live_available = False
    if runtime is not None:
        if getattr(runtime, "_read_only_mode", False):
            live_reason = "服务当前处于只读配置，不能切换到 live"
        elif os.environ.get("AD_AGENT_ENABLE_LIVE") != "1":
            live_reason = "服务未开启 live 环境开关"
        elif not bool(getattr(runtime, "allow_live_writes", False)):
            live_reason = "服务未开启 live 写入权限"
        else:
            live_available = True
    else:
        live_reason = "Runtime 尚未就绪"
    return {
        "status": "healthy" if state == "ready" else "unhealthy",
        "state": state, "error": runtime_status.get("error"),
        "service": "ad-agent", "version": "1.0.0",
        "execution_mode": runtime.execution_mode if runtime else None,
        "execution_mode_options": ["dry_run", "live"],
        "live_mode_available": live_available,
        "live_mode_reason": live_reason,
        "platforms": list(platforms), "tools": len(tools),
    }


@app.get("/readyz", tags=["health"])
async def readiness():
    """Return whether the Agent can accept normal requests.

    ``/health`` is intentionally a liveness endpoint: a process can be alive
    while still booting or missing its model. ``/readyz`` is the deployment
    gate and checks the Runtime state and model dependency without making any
    Provider request or exposing credentials.
    """
    state = runtime_status.get("state", "not_initialized")
    runtime_ready = runtime is not None and state in {"ready", "not_initialized"}
    if runtime is not None and state == "not_initialized":
        # Embedded/test callers may inject an already-created Runtime without
        # going through _init_runtime().
        state = "ready"
    model_required = bool(getattr(runtime, "require_llm", False)) if runtime else False
    model_ready = not model_required or getattr(runtime, "_llm", None) is not None
    try:
        tool_count = len(runtime.registry.list_all()) if runtime else 0
    except Exception:
        tool_count = 0
    checks = {
        "runtime": runtime_ready,
        "llm": model_ready,
        "tool_registry": tool_count > 0,
    }
    ready = all(checks.values()) and state == "ready"
    payload = {
        "status": "ready" if ready else "not_ready",
        "state": state,
        "checks": checks,
        "error": runtime_status.get("error"),
        "service": "ad-agent",
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)


def _live_mode_unavailable_reason() -> Optional[str]:
    """Return the deployment-owned reason live mode cannot be enabled."""
    if runtime is None:
        return "Runtime 尚未就绪"
    if getattr(runtime, "_read_only_mode", False):
        return "服务当前处于只读配置，不能切换到 live"
    if os.environ.get("AD_AGENT_ENABLE_LIVE") != "1":
        return "服务未开启 live 环境开关"
    if not bool(getattr(runtime, "allow_live_writes", False)):
        return "服务未开启 live 写入权限"
    return None


def _principal_execution_mode(principal: RequestPrincipal) -> str:
    """Resolve scoped mode while keeping lightweight embedding fakes compatible."""
    if runtime is None:
        return "dry_run"
    getter = getattr(runtime, "get_execution_mode", None)
    if callable(getter):
        return str(getter(principal.tenant_id, principal.user_id))
    return str(getattr(runtime, "execution_mode", "dry_run"))


def _set_principal_execution_mode(principal: RequestPrincipal, mode: str) -> None:
    """Set scoped mode without requiring legacy Runtime test doubles to change."""
    setter = getattr(runtime, "set_execution_mode", None)
    if not callable(setter):
        raise RuntimeError("Runtime 不支持执行模式设置")
    try:
        parameters = inspect.signature(setter).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "tenant_id" in parameters and "user_id" in parameters:
        setter(mode, tenant_id=principal.tenant_id, user_id=principal.user_id)
    else:
        setter(mode)


@app.post("/settings/execution-mode", tags=["settings"])
async def change_execution_mode(
    request: ExecutionModeRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Change the authenticated principal's mode without changing deployment config.

    Selecting live is an operational capability, not a UI-only preference.
    The endpoint keeps the existing environment, permission and Runtime
    gates in force; it never enables live writes by itself.
    """
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    principal = _authorize_request(x_api_key, http_request)
    mode = str(request.mode or "").strip().lower()
    if mode not in {"dry_run", "live"}:
        raise HTTPException(status_code=422, detail="执行模式只能是 dry_run 或 live")
    _require_principal_permission(principal, "ads.plan")
    if mode == "live":
        _require_principal_permission(principal, "ads.write")
        reason = _live_mode_unavailable_reason()
        if reason:
            raise HTTPException(status_code=409, detail=reason)
    try:
        await run_in_threadpool(_set_principal_execution_mode, principal, mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    live_reason = _live_mode_unavailable_reason()
    return {
        "mode": _principal_execution_mode(principal),
        "execution_mode_options": ["dry_run", "live"],
        "live_mode_available": live_reason is None,
        "live_mode_reason": live_reason,
        "message": (
            "已切换到安全预览模式"
            if _principal_execution_mode(principal) == "dry_run"
            else "已切换到受控 live 模式；写操作仍需账户、权限和二次确认"
        ),
    }


@app.get("/sessions", tags=["sessions"])
async def list_sessions(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    limit: int = Query(50, ge=1, le=200),
):
    """List durable conversations owned by the authenticated principal."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "list_conversations", None)):
        raise HTTPException(status_code=503, detail="会话存储未初始化")
    conversations = await run_in_threadpool(
        runtime.list_conversations,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        limit=limit,
    )
    return {"sessions": conversations}


@app.get("/sessions/{session_id}", tags=["sessions"])
async def get_session_history(
    session_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    limit: int = Query(500, ge=1, le=1000),
):
    """Load one durable conversation inside the principal's user/tenant scope."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "get_conversation", None)):
        raise HTTPException(status_code=503, detail="会话存储未初始化")
    conversation = await run_in_threadpool(
        runtime.get_conversation,
        session_id=session_id,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        limit=limit,
    )
    # Do not reveal whether a session exists for another principal.
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return conversation


@app.patch("/sessions/{session_id}", tags=["sessions"])
async def rename_session(
    session_id: str,
    request: SessionRenameRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Rename one local conversation inside the authenticated scope."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "rename_conversation", None)):
        raise HTTPException(status_code=503, detail="会话存储未初始化")
    try:
        conversation = await run_in_threadpool(
            runtime.rename_conversation,
            session_id=session_id,
            title=request.title,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return conversation


@app.get("/sessions/{session_id}/runs/latest", tags=["runs"])
async def get_latest_session_run(
    session_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Return the latest durable Agent run and its replayable events."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "get_latest_run", None)):
        raise HTTPException(status_code=503, detail="运行状态存储未初始化")
    run = await run_in_threadpool(
        runtime.get_latest_run,
        session_id=session_id,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
    )
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在或无权访问")
    return run


@app.get("/runs/{run_id}/events", tags=["runs"])
async def get_run_events(
    run_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    after_seq: int = Query(0, ge=0),
    limit: int = Query(256, ge=1, le=512),
):
    """Read incremental durable events for one owned Agent run."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "get_run_events", None)):
        raise HTTPException(status_code=503, detail="运行状态存储未初始化")
    run = await run_in_threadpool(
        runtime.get_run_events,
        run_id=run_id,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        after_seq=after_seq,
        limit=limit,
    )
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在或无权访问")
    return run


@app.delete("/sessions", tags=["sessions"])
async def delete_sessions(
    request: SessionDeleteRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Delete selected local conversations in the authenticated scope."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "delete_conversations", None)):
        raise HTTPException(status_code=503, detail="会话存储未初始化")
    deleted_session_ids = await run_in_threadpool(
        runtime.delete_conversations,
        session_ids=request.session_ids,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
    )
    if not deleted_session_ids:
        raise HTTPException(status_code=404, detail="没有找到可删除的会话")
    return {
        "deleted": True,
        "deleted_session_ids": deleted_session_ids,
        "deleted_count": len(deleted_session_ids),
    }


@app.delete("/sessions/{session_id}", tags=["sessions"])
async def delete_session(
    session_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Delete one local conversation in the authenticated scope."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "delete_conversation", None)):
        raise HTTPException(status_code=503, detail="会话存储未初始化")
    deleted = await run_in_threadpool(
        runtime.delete_conversation,
        session_id=session_id,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return {"deleted": True, "deleted_session_id": str(session_id)}


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
        _activate_request_tenant_skills(principal)
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
            creation_blueprint_id=request.creation_blueprint_id,
            creation_blueprint_version=request.creation_blueprint_version,
            execution_mode=request.execution_mode,
            principal=principal,
        )
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RuntimeError as e:
        message = str(e)
        if "session is busy" in message:
            raise HTTPException(status_code=409, detail="会话正在其他实例执行，请稍后重试")
        if "durable Agent run persistence" in message:
            raise HTTPException(status_code=503, detail="运行状态存储暂不可用，请稍后重试")
        return JSONResponse(
            content={"success": False, "error": _safe_exception_text(e)},
            status_code=500,
        )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": _safe_exception_text(e)},
            status_code=500,
        )


@app.post("/tasks", tags=["tasks"])
async def submit_task(
    body: TaskSubmitRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    idempotency_header: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Queue an Agent turn and return immediately with its durable status."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "submit_task", None)):
        raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
    _activate_request_tenant_skills(principal)
    idempotency_key = idempotency_header or body.idempotency_key
    try:
        task, created = await run_in_threadpool(
            runtime.submit_task,
            body.kind,
            body.payload,
            principal=principal,
            idempotency_key=idempotency_key,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        message = str(exc)
        status = 429 if "queue is full" in message else 503
        raise HTTPException(status_code=status, detail=message)
    return JSONResponse(
        status_code=202,
        content={"task": task, "created": created},
    )


@app.get("/tasks/{task_id}", tags=["tasks"])
async def get_task(
    task_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Read one task only within the authenticated tenant/user scope."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "get_task", None)):
        raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
    task = await run_in_threadpool(
        runtime.get_task, task_id,
        user_id=principal.user_id, tenant_id=principal.tenant_id,
    )
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@app.get("/tasks", tags=["tasks"])
async def list_tasks(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    status: Optional[str] = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
):
    """List tasks only within the authenticated tenant/user scope."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "list_tasks", None)):
        raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
    statuses = [item.strip() for item in status.split(",") if item.strip()] if status else None
    tasks = await run_in_threadpool(
        runtime.list_tasks,
        user_id=principal.user_id, tenant_id=principal.tenant_id,
        statuses=statuses, limit=limit,
    )
    return {"tasks": tasks}


@app.post("/tasks/{task_id}/pause", tags=["tasks"])
async def pause_task(
    task_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Pause a queued task; a running provider operation is never force-paused."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.plan")
    if not runtime or not callable(getattr(runtime, "pause_task", None)):
        raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
    task = await run_in_threadpool(
        runtime.pause_task, task_id,
        user_id=principal.user_id, tenant_id=principal.tenant_id,
    )
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    if task.get("status") == "running":
        raise HTTPException(status_code=409, detail="运行中的任务不能被强制暂停")
    return task


@app.post("/tasks/{task_id}/resume", tags=["tasks"])
async def resume_task(
    task_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Resume a paused task and schedule it through the bounded worker pool."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.plan")
    if not runtime or not callable(getattr(runtime, "resume_task", None)):
        raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
    task = await run_in_threadpool(
        runtime.resume_task, task_id,
        user_id=principal.user_id, tenant_id=principal.tenant_id,
    )
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@app.delete("/tasks/{task_id}", tags=["tasks"])
async def cancel_task(
    task_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Cancel local task scheduling/execution; never roll back a provider."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.plan")
    if not runtime or not callable(getattr(runtime, "cancel_task", None)):
        raise HTTPException(status_code=503, detail="异步任务执行器未初始化")
    task = await run_in_threadpool(
        runtime.cancel_task, task_id,
        user_id=principal.user_id, tenant_id=principal.tenant_id,
    )
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@app.get("/knowledge/search", tags=["knowledge"])
async def search_knowledge(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    query: str = Query("", max_length=2000),
    platform: Optional[str] = Query(None, max_length=64),
    knowledge_type: Optional[str] = Query(None, max_length=64),
    limit: int = Query(10, ge=1, le=50),
):
    """Search the published Markdown LLM Wiki through the Runtime provider."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "search_knowledge", None)):
        raise HTTPException(status_code=503, detail="知识库未初始化")
    documents = await run_in_threadpool(
        runtime.search_knowledge,
        query,
        tenant_id=principal.tenant_id,
        platform=platform,
        knowledge_type=knowledge_type,
        limit=limit,
        max_excerpt_chars=1200,
    )
    summary = await run_in_threadpool(runtime.summarize_knowledge, query, documents)
    return {"query": query, "summary": summary, "results": documents}


class KnowledgeDocumentRequest(BaseModel):
    """A standard Markdown Wiki document body and its frontmatter fields."""

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=60_000)
    platform: str = Field(default="all", max_length=64)
    layer: str = Field(default="business", max_length=32)
    knowledge_type: str = Field(default="general", max_length=64)
    source: str = Field(default="user", max_length=200)
    source_ref: str = Field(default="", max_length=500)
    version: str = Field(default="1.0.0", max_length=80)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list, max_length=20)


def _knowledge_manager_or_503() -> ManagedKnowledgeManager:
    if not runtime or not getattr(runtime, "persistence_store", None):
        raise HTTPException(status_code=503, detail="知识库存储未初始化")
    return ManagedKnowledgeManager(runtime.persistence_store)


@app.get("/knowledge/documents", tags=["knowledge"])
async def list_knowledge_documents(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    status: Optional[str] = Query(None, max_length=32),
    limit: int = Query(100, ge=1, le=200),
):
    """List tenant-owned Wiki drafts and published documents."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    return {
        "tenant_id": principal.tenant_id,
        "documents": _knowledge_manager_or_503().list_documents(
            principal.tenant_id, status=status, limit=limit
        ),
    }


@app.post("/knowledge/documents", tags=["knowledge"])
async def create_knowledge_document(
    body: KnowledgeDocumentRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Save a tenant-owned Markdown Wiki draft; publication is explicit."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "knowledge.write")
    try:
        result = _knowledge_manager_or_503().create_document(
            principal.tenant_id, body.model_dump(), principal.user_id
        )
    except KnowledgeDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(status_code=201, content=result)


@app.get("/knowledge/documents/{document_id}", tags=["knowledge"])
async def get_knowledge_document(
    document_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "knowledge.read")
    result = _knowledge_manager_or_503().get_document(principal.tenant_id, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="知识文档不存在或无权访问")
    return result


@app.post("/knowledge/documents/{document_id}/publish", tags=["knowledge"])
async def publish_knowledge_document(
    document_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "knowledge.write")
    result = _knowledge_manager_or_503().publish(principal.tenant_id, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="知识文档不存在、已废弃或无权访问")
    return result


@app.post("/knowledge/documents/{document_id}/unpublish", tags=["knowledge"])
async def unpublish_knowledge_document(
    document_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "knowledge.write")
    result = _knowledge_manager_or_503().unpublish(principal.tenant_id, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="知识文档不是当前发布状态或无权访问")
    return result


@app.get("/memory", tags=["memory"])
async def recall_memory(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    query: str = Query("", max_length=2000),
    session_id: Optional[str] = Query(None, max_length=200),
    limit: int = Query(10, ge=1, le=20),
):
    """Recall only the authenticated principal's tenant/user memories."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "memory.read")
    if not runtime or not runtime.memory_manager:
        raise HTTPException(status_code=503, detail="Memory 未初始化")
    records = runtime.memory_manager.recall(
        query,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        session_id=session_id,
        limit=limit,
    )
    return {"memories": [record.to_context_dict() for record in records]}


@app.post("/memory", tags=["memory"])
async def write_memory(
    body: MemoryWriteRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Create a governed explicit memory; no body identity is trusted."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "memory.write")
    if body.kind.lower() not in MEMORY_KINDS:
        raise HTTPException(status_code=422, detail="unsupported memory kind")
    if not runtime or not runtime.memory_manager:
        raise HTTPException(status_code=503, detail="Memory 未初始化")
    try:
        record = runtime.memory_manager.remember(
            body.content,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            kind=body.kind,
            tags=body.tags,
            importance=body.importance,
            confidence=body.confidence,
            source="api_explicit",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(status_code=201, content=record.to_context_dict())


@app.delete("/memory/{memory_id}", tags=["memory"])
async def delete_memory(
    memory_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Delete (tombstone) one memory within the authenticated scope."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "memory.write")
    if not runtime or not runtime.memory_manager:
        raise HTTPException(status_code=503, detail="Memory 未初始化")
    deleted = runtime.memory_manager.forget(
        memory_id, tenant_id=principal.tenant_id, user_id=principal.user_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True, "memory_id": memory_id}


@app.get("/platforms", tags=["info"])
async def get_platforms(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    _authorize_request(x_api_key, http_request)
    if not runtime:
        return {"platforms": []}
    return {"platforms": runtime.registry.list_all_platforms()}


class PluginPackageRequest(BaseModel):
    """A declaration plus complete package snapshot.

    This endpoint is a control-plane upload. It accepts arbitrary standard
    package files as data, but does not import or execute them.
    """

    manifest: dict[str, object]
    files: dict[str, object]


@app.get("/plugins", tags=["info"])
async def get_plugins(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Expose plugin manifests and lifecycle state without executable data."""
    principal = _authorize_request(x_api_key, http_request)
    if not runtime:
        return {"plugins": []}
    return {"plugins": runtime.list_plugins(principal.tenant_id)}


@app.get("/plugins/packages", tags=["plugins"])
async def list_plugin_packages(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    plugin_id: Optional[str] = Query(None, max_length=128),
    limit: int = Query(50, ge=1, le=200),
):
    """List immutable Plugin package versions for the authenticated tenant."""
    principal = _authorize_request(x_api_key, http_request)
    _require_plugin_permission(principal, "plugins.read")
    manager = _plugin_manager_or_503()
    return {
        "tenant_id": principal.tenant_id,
        "packages": manager.list_packages(principal.tenant_id, plugin_id, limit),
    }


@app.post("/plugins/packages", tags=["plugins"])
async def create_plugin_package(
    body: PluginPackageRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Validate and store a user Plugin package without loading its code."""
    principal = _authorize_request(x_api_key, http_request)
    _require_plugin_permission(principal, "plugins.write")
    manager = _plugin_manager_or_503()
    try:
        result = manager.create_package(
            principal.tenant_id, body.manifest, body.files, principal.user_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except PluginPackageError as exc:
        status = 409 if "already exists" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc))
    return JSONResponse(status_code=201, content=result)


@app.post("/plugins/packages/archive", tags=["plugins"])
async def upload_plugin_package_archive(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Import a standard ZIP containing ``plugin.manifest.json`` as data."""
    principal = _authorize_request(x_api_key, request)
    _require_plugin_permission(principal, "plugins.write")
    try:
        result = _plugin_manager_or_503().create_archive(
            principal.tenant_id, await request.body(), principal.user_id
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except PluginPackageError as exc:
        status = 409 if "already exists" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc))
    return JSONResponse(status_code=201, content=result)


@app.get("/plugins/packages/{plugin_id:path}/versions/{version}", tags=["plugins"])
async def get_plugin_package(
    plugin_id: str,
    version: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Return one package declaration and its complete file snapshot."""
    principal = _authorize_request(x_api_key, http_request)
    _require_plugin_permission(principal, "plugins.read")
    result = _plugin_manager_or_503().get_package(
        principal.tenant_id, plugin_id, version, include_files=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Plugin package not found")
    return result


@app.get("/plugins/packages/{plugin_id:path}/versions/{version}/health", tags=["plugins"])
async def health_plugin_package(
    plugin_id: str,
    version: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Check package integrity and dependency readiness without execution."""
    principal = _authorize_request(x_api_key, http_request)
    _require_plugin_permission(principal, "plugins.read")
    result = _plugin_manager_or_503().health(
        principal.tenant_id, plugin_id, version
    )
    if not result:
        raise HTTPException(status_code=404, detail="Plugin package not found")
    return result


@app.post("/plugins/packages/{plugin_id:path}/versions/{version}/activate", tags=["plugins"])
async def activate_plugin_package(
    plugin_id: str,
    version: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Select a verified package version as the tenant release candidate.

    User packages are never hot-loaded.  Executable activation remains a
    deployment-host operation that must inject a reviewed contribution.
    """
    principal = _authorize_request(x_api_key, http_request)
    _require_plugin_permission(principal, "plugins.write")
    try:
        result = _plugin_manager_or_503().activate(
            principal.tenant_id, plugin_id, version
        )
    except PluginPackageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Plugin package not found")
    return result


@app.post("/plugins/packages/{plugin_id:path}/versions/{version}/deactivate", tags=["plugins"])
async def deactivate_plugin_package(
    plugin_id: str,
    version: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Remove the tenant release pointer while retaining the audit snapshot."""
    principal = _authorize_request(x_api_key, http_request)
    _require_plugin_permission(principal, "plugins.write")
    result = _plugin_manager_or_503().deactivate(
        principal.tenant_id, plugin_id, version
    )
    if not result:
        raise HTTPException(status_code=409, detail="Plugin package is not the active release")
    return result


@app.delete("/plugins/packages/{plugin_id:path}/versions/{version}", tags=["plugins"])
async def uninstall_plugin_package(
    plugin_id: str,
    version: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Uninstall a package from the control plane without deleting its audit row."""
    principal = _authorize_request(x_api_key, http_request)
    _require_plugin_permission(principal, "plugins.write")
    result = _plugin_manager_or_503().uninstall(
        principal.tenant_id, plugin_id, version
    )
    if not result:
        raise HTTPException(status_code=404, detail="Plugin package not found")
    return result


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
                "contract_version": t.contract_version,
                "provider_api_version": t.provider_api_version,
                "input_schema": t.input_schema.to_dict() if t.input_schema else None,
            }
            for t in tools
        ]
    }


@app.get("/ad-formats", tags=["info"])
async def get_ad_formats(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    platform: Optional[str] = Query(None, max_length=50),
    coverage: Optional[str] = Query(None, max_length=40),
):
    """Expose provider-owned ad-format coverage without making network calls.

    ``coverage`` distinguishes a declared enum from a payload-backed
    dry-run contract.  This endpoint is metadata-only and cannot enable live
    writes or accept credentials/account identifiers.
    """
    _authorize_request(x_api_key, http_request)
    if not runtime:
        return {"formats": []}
    try:
        return {
            "platform": platform,
            "coverage": coverage,
            "formats": runtime.list_ad_formats(platform, coverage),
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/creation-blueprints", tags=["info"])
async def get_creation_blueprints(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    provider: Optional[str] = Query(None, max_length=50),
    ad_format: Optional[str] = Query(None, max_length=80),
    selector_dimension: Optional[str] = Query(None, max_length=40),
    selector_value: Optional[str] = Query(None, max_length=120),
):
    """Expose declarative ad-creation metadata without making network calls."""
    _authorize_request(x_api_key, http_request)
    if not runtime:
        return {"blueprints": []}
    return {
        "provider": provider,
        "ad_format": ad_format,
        "selector_dimension": selector_dimension,
        "selector_value": selector_value,
        "blueprints": runtime.list_creation_blueprints(
            provider, ad_format, selector_dimension, selector_value
        ),
    }


class BlueprintEvaluationRequest(BaseModel):
    """Current draft state sent to the deterministic cascade evaluator."""

    values: dict[str, object] = Field(default_factory=dict)
    previous_values: Optional[dict[str, object]] = None
    changed_fields: Optional[list[str]] = None
    version: Optional[str] = Field(None, max_length=80)


class BlueprintResolveRequest(BaseModel):
    """Selector values used to choose a provider-owned creation Blueprint."""

    provider: str = Field(min_length=1, max_length=50)
    selector_values: dict[str, object] = Field(default_factory=dict)
    values: dict[str, object] = Field(default_factory=dict)
    version: Optional[str] = Field(None, max_length=80)


@app.post("/creation-blueprints/resolve", tags=["info"])
async def resolve_creation_blueprint(
    body: BlueprintResolveRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Resolve a Blueprint by its declarative selector; metadata-only."""
    _authorize_request(x_api_key, http_request)
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    blueprint = runtime.resolve_creation_blueprint(
        body.provider,
        selector_values=body.selector_values,
        values=body.values,
        version=body.version,
    )
    if blueprint is None:
        raise HTTPException(status_code=404, detail="未找到匹配当前选择的广告创建蓝图")
    return {"blueprint": blueprint}


@app.post("/creation-blueprints/{blueprint_id}/evaluate", tags=["info"])
async def evaluate_creation_blueprint(
    blueprint_id: str,
    body: BlueprintEvaluationRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Evaluate field cascade state; this endpoint never calls a Provider API."""
    _authorize_request(x_api_key, http_request)
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    try:
        return runtime.evaluate_creation_blueprint(
            blueprint_id,
            body.values,
            version=body.version,
            previous_values=body.previous_values,
            changed_fields=body.changed_fields,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class SkillVersionRequest(BaseModel):
    """Complete standard Agent Skill directory snapshot.

    ``files`` values may be UTF-8 strings or
    ``{"encoding": "base64", "content": "..."}`` for binary assets.
    """

    version: str = Field(min_length=5, max_length=80)
    files: dict[str, object]


def _skill_manager_or_503() -> ManagedSkillManager:
    if not runtime or not getattr(runtime, "persistence_store", None):
        raise HTTPException(status_code=503, detail="Skill 管理存储未初始化")
    return ManagedSkillManager(runtime.persistence_store)


def _plugin_manager_or_503() -> PluginPackageManager:
    if not runtime or not getattr(runtime, "persistence_store", None):
        raise HTTPException(status_code=503, detail="Plugin 管理存储未初始化")
    return PluginPackageManager(runtime.persistence_store)


def _require_skill_permission(principal: RequestPrincipal, permission: str) -> None:
    if permission not in principal.permissions and "admin" not in principal.permissions:
        raise HTTPException(status_code=403, detail=f"缺少 Skill 管理权限：{permission}")


def _require_plugin_permission(principal: RequestPrincipal, permission: str) -> None:
    if permission not in principal.permissions and "admin" not in principal.permissions:
        raise HTTPException(status_code=403, detail=f"缺少 Plugin 管理权限：{permission}")


def _activate_request_tenant_skills(principal: RequestPrincipal) -> None:
    """Load the authenticated tenant's published Skills before Agent turns.

    Startup activation covers the configured service tenant. API-key
    principal mappings may serve multiple tenants from the same process, so a
    request for another tenant must activate only that tenant's published
    advisory snapshots. ``activate_published`` is idempotent and skips an
    already materialized release.
    """
    if not runtime or not getattr(runtime, "persistence_store", None):
        return
    try:
        ManagedSkillManager(runtime.persistence_store).activate_published(
            principal.tenant_id, runtime
        )
    except Exception as exc:
        logger.error(
            "无法激活租户 %s 的已发布 Skill: %s",
            principal.tenant_id,
            _safe_exception_text(exc),
        )
        raise HTTPException(status_code=503, detail="租户 Skill 上下文加载失败") from exc


@app.get("/skills", tags=["skills"])
async def list_managed_skills(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    skill_name: Optional[str] = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=200),
):
    """List tenant versions together with deployment-owned built-in Skills."""
    principal = _authorize_request(x_api_key, http_request)
    _require_skill_permission(principal, "skills.read")
    manager = _skill_manager_or_503()
    managed = manager.list_versions(principal.tenant_id, skill_name, limit)
    builtin = builtin_skill_catalog.list_versions(skill_name, limit)
    return {
        "tenant_id": principal.tenant_id,
        # Keep managed records first for API consumers that previously read
        # ``skills`` as the tenant list. The explicit partitions remove any
        # ambiguity for new consumers and the UI.
        "skills": managed + builtin,
        "managed_skills": managed,
        "builtin_skills": builtin,
    }


@app.post("/skills/{skill_name}/versions", tags=["skills"])
async def create_managed_skill_version(
    skill_name: str,
    body: SkillVersionRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Validate and store a draft standard Skill directory snapshot."""
    principal = _authorize_request(x_api_key, http_request)
    _require_skill_permission(principal, "skills.write")
    manager = _skill_manager_or_503()
    try:
        result = manager.create_version(
            tenant_id=principal.tenant_id,
            skill_name=skill_name,
            version=body.version,
            raw_files=body.files,
            created_by=principal.user_id,
        )
    except SkillPackageError as exc:
        status = 409 if "already exists" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc))
    return JSONResponse(status_code=201, content=result)


@app.post("/skills/{skill_name}/versions/archive", tags=["skills"])
async def upload_managed_skill_archive(
    skill_name: str,
    request: Request,
    version: str = Query(..., min_length=5, max_length=80),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Upload a complete standard Skill directory as a ZIP archive."""
    principal = _authorize_request(x_api_key, request)
    _require_skill_permission(principal, "skills.write")
    manager = _skill_manager_or_503()
    try:
        result = manager.create_version_archive(
            principal.tenant_id, skill_name, version,
            await request.body(), principal.user_id,
        )
    except SkillPackageError as exc:
        status = 409 if "already exists" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc))
    return JSONResponse(status_code=201, content=result)


@app.get("/skills/{skill_name}/versions", tags=["skills"])
async def list_managed_skill_versions(
    skill_name: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    limit: int = Query(50, ge=1, le=200),
):
    principal = _authorize_request(x_api_key, http_request)
    _require_skill_permission(principal, "skills.read")
    manager = _skill_manager_or_503()
    return {
        "tenant_id": principal.tenant_id,
        "skill_name": skill_name,
        "versions": manager.list_versions(principal.tenant_id, skill_name, limit),
    }


@app.get("/skills/builtin/{skill_name}/versions/{version}", tags=["skills"])
async def get_builtin_skill_version(
    skill_name: str,
    version: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Read one deployment-owned Skill package without enabling edits."""
    principal = _authorize_request(x_api_key, http_request)
    _require_skill_permission(principal, "skills.read")
    result = builtin_skill_catalog.get_version(skill_name, version)
    if not result:
        raise HTTPException(status_code=404, detail="Builtin Skill version not found")
    return result


@app.get("/skills/{skill_name}/versions/{version}", tags=["skills"])
async def get_managed_skill_version(
    skill_name: str,
    version: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    principal = _authorize_request(x_api_key, http_request)
    _require_skill_permission(principal, "skills.read")
    manager = _skill_manager_or_503()
    result = manager.get_version(
        principal.tenant_id, skill_name, version, include_files=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Skill version not found")
    return result


@app.post("/skills/{skill_name}/versions/{version}/publish", tags=["skills"])
async def publish_managed_skill_version(
    skill_name: str,
    version: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Publish one immutable version and activate it as advisory context."""
    principal = _authorize_request(x_api_key, http_request)
    _require_skill_permission(principal, "skills.write")
    manager = _skill_manager_or_503()
    try:
        result = manager.publish(
            principal.tenant_id, skill_name, version, runtime=runtime
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SkillPackageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Skill version not found")
    return result


@app.post("/skills/{skill_name}/versions/{version}/unpublish", tags=["skills"])
async def unpublish_managed_skill_version(
    skill_name: str,
    version: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Deactivate the current release without deleting its immutable version."""
    principal = _authorize_request(x_api_key, http_request)
    _require_skill_permission(principal, "skills.write")
    manager = _skill_manager_or_503()
    try:
        result = manager.unpublish(
            principal.tenant_id, skill_name, version, runtime=runtime
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except SkillPackageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not result:
        raise HTTPException(
            status_code=409,
            detail="Skill version is not the current published release",
        )
    return result


@app.post("/skills/{skill_name}/versions/{version}/evaluate", tags=["skills"])
async def evaluate_managed_skill_version(
    skill_name: str,
    version: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Queue a skill-up run for the immutable Skill version."""
    principal = _authorize_request(x_api_key, http_request)
    _require_skill_permission(principal, "skills.evaluate")
    manager = _skill_manager_or_503()
    try:
        run = manager.start_evaluation(principal.tenant_id, skill_name, version)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill version not found")
    except SkillPackageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(status_code=202, content=run)


@app.get("/skills/evaluations/{run_id}", tags=["skills"])
async def get_managed_skill_evaluation(
    run_id: str,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    principal = _authorize_request(x_api_key, http_request)
    _require_skill_permission(principal, "skills.read")
    manager = _skill_manager_or_503()
    result = manager.get_evaluation(principal.tenant_id, run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Skill evaluation not found")
    return result


class ChatStreamRequest(BaseModel):
    user_input: str = Field(min_length=1, max_length=12_000)
    session_id: Optional[str] = None
    user_id: str = Field(default="web_user", min_length=1, max_length=200)
    account_id: str = Field(default="", max_length=200)
    confirmed: bool = False
    confirmation_payload: Optional[dict] = None
    platform_params: Optional[dict] = None
    creation_blueprint_id: Optional[str] = Field(default=None, max_length=200)
    creation_blueprint_version: Optional[str] = Field(default=None, max_length=32)
    execution_mode: Optional[Literal["dry_run", "live"]] = None


class WorkflowReconcileRequest(BaseModel):
    """Provider-verified observations supplied by a recovery worker."""

    observations: object


@app.post("/chat/stream", tags=["chat"])
async def chat_stream(
    request: ChatStreamRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Stream the Runtime's safe execution events over SSE.

    The Runtime owns the execution lifecycle.  This endpoint only bridges its
    observer callback to the browser; it must not infer plans or replay Tool
    results after the turn has finished.
    """
    from fastapi.responses import StreamingResponse
    
    if not runtime:
        return JSONResponse(content={"success": False, "error": "服务未初始化"}, status_code=503)
    
    try:
        principal = _authorize_request(x_api_key, http_request)
        _activate_request_tenant_skills(principal)
        if request.confirmed and not request.confirmation_payload:
            raise HTTPException(
                status_code=400,
                detail="confirmed=true 必须携带与当前计划匹配的 confirmation_payload",
            )
        user_input = request.user_input
        
        async def generate():
            def event(payload: dict) -> str:
                return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            event_queue: queue.Queue[dict] = queue.Queue(maxsize=256)

            # This is only the stream lifecycle marker.  It intentionally
            # carries no guessed Intent/Skill/account/Tool node; those can
            # only arrive from Runtime's real plan/events below.
            yield event({
                "type": "start",
                "event_type": "start",
                "status": "running",
                "safe_metadata": {"source": "stream_gateway"},
            })

            def observe(payload: dict) -> None:
                # Runtime runs in the worker thread.  Only put the already
                # sanitized event into the bridge queue; no request data is
                # reconstructed in the HTTP layer.
                try:
                    event_queue.put_nowait(payload)
                except queue.Full:
                    # The trace is diagnostic; never let a slow/disconnected
                    # client block the Agent or a Tool execution.
                    return

            task = asyncio.create_task(
                run_in_threadpool(
                    runtime.run,
                    user_input=user_input,
                    session_id=request.session_id,
                    account_id=request.account_id or None,
                    platform_params=request.platform_params,
                    confirmed=request.confirmed,
                    confirmation_payload=request.confirmation_payload,
                    creation_blueprint_id=request.creation_blueprint_id,
                    creation_blueprint_version=request.creation_blueprint_version,
                    execution_mode=request.execution_mode,
                    principal=principal,
                    event_callback=observe,
                )
            )
            final_event = None
            reply_marker = None
            try:
                while True:
                    try:
                        payload = await asyncio.to_thread(event_queue.get, True, 0.25)
                    except queue.Empty:
                        if task.done():
                            break
                        continue
                    # Runtime emits done after it has rendered the reply, but
                    # the reply body is intentionally kept out of the trace
                    # envelope.  Buffer done so the HTTP bridge can append the
                    # safe final response before closing the stream.
                    if payload.get("type") == "done":
                        final_event = payload
                    elif payload.get("type") == "reply":
                        # The Runtime marker intentionally has no reply body.
                        # It becomes the metadata envelope for the one final
                        # reply event below, avoiding duplicate UI entries.
                        reply_marker = payload
                    else:
                        yield event(payload)

                result = await task
            except Exception as exc:
                yield event({
                    "type": "error",
                    "event_type": "error",
                    "status": "failed",
                    "safe_metadata": {"reason": "runtime_error"},
                    "error": _safe_exception_text(exc),
                })
                yield event({"type": "done", "status": "failed"})
                return

            safe_results = []
            for item in result.get("results", []) if isinstance(result, dict) else []:
                if not isinstance(item, dict):
                    continue
                safe_results.append({
                    key: AgentRuntime._redact_for_persistence(item.get(key))
                    for key in ("tool", "platform", "resource_type", "success", "error", "needs_confirmation", "skipped", "data")
                    if key in item
                })
            run_id = result.get("run_id") if isinstance(result, dict) else None
            # Runtime implementations that do not persist runs (for example
            # an embedded/test runtime) may legitimately omit this optional
            # readback API. The stream already has the authoritative result;
            # only enrich it with a run id when the capability is available.
            get_latest_run = getattr(runtime, "get_latest_run", None)
            if (
                not run_id
                and isinstance(result, dict)
                and result.get("session_id")
                and callable(get_latest_run)
            ):
                latest = await run_in_threadpool(
                    get_latest_run,
                    session_id=result.get("session_id"),
                    user_id=principal.user_id,
                    tenant_id=principal.tenant_id,
                )
                run_id = (latest or {}).get("run_id")
            yield event({
                "type": "reply",
                "event_type": "reply",
                "trace_id": (reply_marker or {}).get("trace_id"),
                "seq": (reply_marker or {}).get("seq"),
                "status": "awaiting_confirmation" if result.get("needs_confirmation") else "succeeded",
                "content": AgentRuntime._redact_for_persistence(result.get("reply", "")),
                "session_id": result.get("session_id"),
                "turn_id": result.get("turn_id"),
                "run_id": run_id,
                "needs_confirmation": bool(result.get("needs_confirmation")),
                "confirmation_payload": AgentRuntime._redact_for_persistence(result.get("confirmation_payload")),
                "results": safe_results,
                "ui": AgentRuntime._redact_for_persistence(result.get("ui") or {}),
            })
            yield event(final_event or {
                "type": "done",
                "event_type": "done",
                "status": "awaiting_confirmation" if result.get("needs_confirmation") else "succeeded",
            })
        
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


@app.get("/parameter-options/resolve", tags=["info"])
async def resolve_parameter_options(
    http_request: Request,
    platform: str = Query(..., min_length=1, max_length=50),
    field: str = Query(..., min_length=1, max_length=100),
    tool_name: str = Query(..., min_length=1, max_length=150),
    account_id: Optional[str] = Query(None, max_length=200),
    lookup_context: Optional[str] = Query(None, max_length=8000),
    query: Optional[str] = Query(None, max_length=200),
    session_id: Optional[str] = Query(None, max_length=200),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Resolve a provider-backed parameter catalog for a form or UI.

    Identity, tenant, permissions and account scope come only from the
    authenticated principal.  Query parameters select the catalog/account;
    they cannot impersonate a user or grant access to an account.
    """
    principal = _authorize_request(x_api_key, http_request)
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    try:
        context = {}
        if lookup_context:
            try:
                decoded = json.loads(lookup_context)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail="查询上下文不是有效的 JSON") from exc
            if not isinstance(decoded, dict):
                raise HTTPException(status_code=422, detail="查询上下文必须是对象")
            context = decoded
        return await run_in_threadpool(
            runtime.resolve_parameter_options,
            platform=platform,
            field=field,
            tool_name=tool_name,
            account_id=account_id,
            lookup_context=context,
            query=query,
            session_id=session_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            account_scope=principal.account_scope,
            granted_permissions=principal.permissions,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=_safe_exception_text(exc))


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
