#!/usr/bin/env python3.13
"""
api_server.py - ad-agent HTTP API 服务（FastAPI）
"""

import sys
import os
import json
import logging
import inspect
from contextlib import asynccontextmanager
from pathlib import Path

if sys.version_info[:2] != (3, 13):
    raise RuntimeError(
        "ad-agent requires Python 3.13; use ./scripts/ad-agent-python "
        "or make ad-agent-run"
    )

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
from typing import Optional
from starlette.concurrency import run_in_threadpool

# Keep local credentials and model selection outside source control while
# making service startup reproducible. Explicit process environment variables
# take precedence over the ignored file.
from agents.ad_agent.core.local_config import load_default_local_env, load_local_env_file
load_default_local_env()

# 导入 Agent 核心模块
from agents.ad_agent import AdvertisingApplication, create_advertising_application
from agents.agent_harness.redaction import redact_for_persistence
from agents.ad_agent.domain.ad.auth import RequestPrincipal
from agents.ad_agent.mcp_management import MCPServerManager
from agents.ad_agent.runtime_mcp import RuntimeMCPServers
from agents.ad_agent.skill_management import (
    BuiltinSkillCatalog,
    ManagedSkillManager,
)
from agents.ad_agent.persistence.factory import create_persistence_store
from agents.ad_agent.api.security import RequestAuthorizer
from agents.ad_agent.api.context import ApiContext
from agents.ad_agent.api.routes.chat import create_chat_router
from agents.ad_agent.api.routes.catalog import create_catalog_router
from agents.ad_agent.api.routes.knowledge import create_knowledge_router
from agents.ad_agent.api.routes.management import create_management_router
from agents.ad_agent.api.routes.sessions import create_sessions_router
from agents.ad_agent.api.routes.tasks import create_tasks_router
from agents.ad_agent.api.routes.workflows import create_workflows_router
from agents.ad_agent.api.models import (
    ExecutionModeRequest,
)

# 配置路径
CONFIG_PATH = Path(__file__).parent / "config.yaml"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "chat.html"
STATIC_PATH = Path(__file__).parent / "static"
BUILTIN_SKILLS_ROOT = Path(__file__).parent / "skills"
# Deployment-owned catalog. It is read-only and intentionally independent of
# tenant Skill persistence; the Runtime remains the execution source of truth.
builtin_skill_catalog = BuiltinSkillCatalog(BUILTIN_SKILLS_ROOT)

# 全局 runtime
runtime: Optional[AdvertisingApplication] = None
mcp_manager: Optional[MCPServerManager] = None
runtime_mcp_servers: Optional[RuntimeMCPServers] = None
runtime_mcp_servers_app = None
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
    return redact_for_persistence(str(error))


request_authorizer = RequestAuthorizer(
    runtime_getter=lambda: runtime,
    api_key_getter=lambda: API_KEY,
    principals_getter=_api_key_principals,
    allow_unauthenticated_getter=lambda: ALLOW_UNAUTHENTICATED,
    service_principal_getter=_configured_service_principal,
)


def _authorize_request(
    api_key: Optional[str], request: Optional[Request] = None
) -> RequestPrincipal:
    """Route authentication through the dedicated API security boundary."""
    return request_authorizer.authorize(api_key, request)


def _require_principal_permission(principal: RequestPrincipal, permission: str) -> None:
    request_authorizer.require_permission(principal, permission)


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

        database_config = config.get("database", {}) or {}
        store = create_persistence_store(
            sqlite_path=_database_path(),
            backend=database_config.get("backend"),
            database_url=database_config.get("url"),
        )
        runtime = create_advertising_application(
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
                    [
                        "ads.read", "ads.plan", "knowledge.read", "knowledge.write",
                        "mcp.read", "mcp.manage",
                    ],
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
            allow_provider_tool_discovery=True,
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
        # Only explicitly validated and enabled external MCP servers can
        # surface Tools to Runtime. Skill files and user package uploads never
        # register an MCP endpoint or executable handler.
        global mcp_manager
        mcp_manager = MCPServerManager(store)
        registered_mcp_tools = mcp_manager.sync_tenant_if_changed(
            os.environ.get("AD_AGENT_SERVICE_TENANT", "default"), runtime
        )
        if runtime.task_executor is not None:
            runtime.task_executor.set_before_execute_hook(
                lambda context: mcp_manager.sync_tenant_if_changed(
                    context.tenant_id, runtime
                )
            )
        runtime_mcp_count = runtime_mcp_servers.refresh(runtime) if runtime_mcp_servers else 0

        print(f"\n📊 服务状态:")
        print(f"- ✅ {len(runtime.registry.list_all_namespaces())} 平台 {len(runtime.registry.list_all())} 工具")
        print(f"- ✅ Skills 系统已就绪")
        print(f"- ✅ MCP 管理已就绪（{registered_mcp_tools} 个已启用 Tool）")
        print(f"- ✅ Runtime MCP Servers 已准备（{runtime_mcp_count} 个 Registry Tool，HTTP 暴露默认关闭）")
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
    global runtime, mcp_manager
    if runtime is None:
        if _init_runtime() is None:
            # Fail ASGI startup instead of serving a process that reports
            # healthy while every data endpoint is unusable.
            raise RuntimeError("ad-agent Runtime 初始化失败")
    active_runtime = runtime
    mcp_lifespan = getattr(runtime_mcp_servers_app, "lifespan", None)
    try:
        if callable(mcp_lifespan):
            async with mcp_lifespan(_app):
                yield
        else:
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
            mcp_manager = None
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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "Idempotency-Key"],
)
runtime_mcp_servers = RuntimeMCPServers(lambda: runtime, _authorize_request)
runtime_mcp_servers_app = runtime_mcp_servers.asgi_app()


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
    platforms = set(t.namespace for t in tools)
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
    get_readiness = getattr(runtime, "get_readiness", None) if runtime else None
    if callable(get_readiness):
        report = get_readiness()
        checks = dict(report.get("checks") or {})
        checks["runtime"] = state in {"ready", "not_initialized"}
        ready = all(checks.values()) and state in {"ready", "not_initialized"}
        payload = {
            "status": "ready" if ready else "not_ready",
            "state": "ready" if state == "not_initialized" else state,
            "checks": checks,
            "tool_count": report.get("tool_count", 0),
            "supervisor": report.get("supervisor"),
            "deployment_health": report.get("deployment_health"),
            "error": runtime_status.get("error"),
            "service": "ad-agent",
        }
        return JSONResponse(status_code=200 if ready else 503, content=payload)
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


@app.get("/monitoring/overview", tags=["monitoring"])
async def monitoring_overview(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Return the scoped operational snapshot for the monitoring console."""
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.read")
    if not runtime or not callable(getattr(runtime, "get_monitoring_snapshot", None)):
        raise HTTPException(status_code=503, detail="监控数据存储未初始化")
    try:
        return await run_in_threadpool(
            runtime.get_monitoring_snapshot,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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


def _principal_live_mode_unavailable_reason(principal: RequestPrincipal) -> Optional[str]:
    """Add the authenticated principal's live permission gate to the status."""
    deployment_reason = _live_mode_unavailable_reason()
    if deployment_reason:
        return deployment_reason
    if "ads.write" not in principal.permissions:
        return "当前身份缺少 live 执行权限：ads.write"
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


@app.get("/settings/execution-mode", tags=["settings"])
async def get_execution_mode(
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Return the authenticated principal's current mode and live gates."""
    if not runtime:
        raise HTTPException(status_code=503, detail="服务未初始化")
    principal = _authorize_request(x_api_key, http_request)
    _require_principal_permission(principal, "ads.plan")
    live_reason = _principal_live_mode_unavailable_reason(principal)
    return {
        "mode": _principal_execution_mode(principal),
        "execution_mode_options": ["dry_run", "live"],
        "live_mode_available": live_reason is None,
        "live_mode_reason": live_reason,
    }


@app.post("/settings/execution-mode", tags=["settings"])
async def change_execution_mode(
    request: ExecutionModeRequest,
    http_request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Change the authenticated principal's mode without changing deployment config.

    Selecting live is an operational tool_source, not a UI-only preference.
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
    # Selecting live is a scoped execution preference, not a grant of
    # mutation authority.  The actual write path still requires ads.write
    # plus every deployment, account, Tool and confirmation gate. Keeping
    # those checks at execution time lets a planner switch the mode here
    # without making the UI itself an authorization boundary.
    try:
        await run_in_threadpool(_set_principal_execution_mode, principal, mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    live_reason = _principal_live_mode_unavailable_reason(principal)
    return {
        "mode": _principal_execution_mode(principal),
        "execution_mode_options": ["dry_run", "live"],
        "live_mode_available": live_reason is None,
        "live_mode_reason": live_reason,
        "message": (
            "已切换到安全预览模式"
            if _principal_execution_mode(principal) == "dry_run"
            else (
                "已切换到受控 live 模式；写操作仍需账户、权限和二次确认，"
                "并满足部署开关、ads.write、测试账户和 Tool 白名单"
            )
        ),
    }


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


def _sync_request_tenant_extensions(principal: RequestPrincipal) -> None:
    """Refresh durable MCP declarations before a request enters Runtime."""
    if not runtime or mcp_manager is None:
        return
    try:
        mcp_manager.sync_tenant_if_changed(principal.tenant_id, runtime)
    except Exception as exc:
        logger.error(
            "无法同步租户 %s 的 MCP 扩展：%s",
            principal.tenant_id, _safe_exception_text(exc),
        )
        raise HTTPException(status_code=503, detail="MCP 扩展同步失败，请稍后重试") from exc


_chat_api_context = ApiContext(
    runtime_getter=lambda: runtime,
    authorize_request=_authorize_request,
    require_permission=_require_principal_permission,
    activate_tenant_skills=_activate_request_tenant_skills,
    sync_tenant_extensions=_sync_request_tenant_extensions,
    safe_exception_text=_safe_exception_text,
    redact=redact_for_persistence,
    persistence_store_getter=lambda: (
        runtime.persistence_store if runtime else None
    ),
    mcp_manager_getter=lambda: mcp_manager,
    runtime_mcp_servers_getter=lambda: runtime_mcp_servers,
    builtin_skill_catalog_getter=lambda: builtin_skill_catalog,
)
app.include_router(create_chat_router(_chat_api_context))
app.include_router(create_catalog_router(_chat_api_context))
app.include_router(create_knowledge_router(_chat_api_context))
app.include_router(create_management_router(_chat_api_context))
app.include_router(create_sessions_router(_chat_api_context))
app.include_router(create_tasks_router(_chat_api_context))
app.include_router(create_workflows_router(_chat_api_context))


# FastMCP's own streamable HTTP endpoint is mounted after the FastAPI routes
# so it cannot shadow the authenticated management/test APIs above. The
# endpoint is still disabled unless AD_AGENT_MCP_CHANNELS_ENABLED=1.
app.mount("/mcp/channels", runtime_mcp_servers_app)
