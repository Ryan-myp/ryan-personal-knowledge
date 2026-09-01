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
from agents.ad_agent.core.plugin_package import PluginPackageError
from agents.ad_agent.core.memory import MEMORY_KINDS
from agents.ad_agent.plugin_management import PluginPackageManager
from agents.ad_agent.skill_management import ManagedSkillManager, SkillPackageError

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
        llm_model = models_config.get('default', 'agnes-2.5-flash')
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
        runtime.auto_load_skills(str(skills_root), credentials)

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
            principal=principal,
        )
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
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
    if not runtime or not runtime.knowledge_provider:
        raise HTTPException(status_code=503, detail="知识库未初始化")
    documents = runtime.knowledge_provider.query(
        query,
        platforms=[platform] if platform else None,
        knowledge_types=[knowledge_type] if knowledge_type else None,
        limit=limit,
        max_excerpt_chars=1200,
    )
    return {"results": [document.to_dict() for document in documents]}


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
    """List versions visible to the authenticated tenant."""
    principal = _authorize_request(x_api_key, http_request)
    _require_skill_permission(principal, "skills.read")
    manager = _skill_manager_or_503()
    return {
        "tenant_id": principal.tenant_id,
        "skills": manager.list_versions(principal.tenant_id, skill_name, limit),
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


@app.get("/parameter-options/resolve", tags=["info"])
async def resolve_parameter_options(
    http_request: Request,
    platform: str = Query(..., min_length=1, max_length=50),
    field: str = Query(..., min_length=1, max_length=100),
    tool_name: str = Query(..., min_length=1, max_length=150),
    account_id: str = Query(..., min_length=1, max_length=200),
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
        return await run_in_threadpool(
            runtime.resolve_parameter_options,
            platform=platform,
            field=field,
            tool_name=tool_name,
            account_id=account_id,
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
