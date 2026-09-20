"""
ad_agent - 多渠道广告投放 Agent

单 Agent + 多 Skills 架构，支持 Meta、Google Ads、TikTok Ads、DV360。

快速开始：
    from ad_agent import AgentRuntime, create_meta_capability
    from ad_agent.core.llm_client import create_llm_client
    
    runtime = AgentRuntime(
        require_llm=True,
        llm_client=create_llm_client(
            model=os.environ["LLM_MODEL"], api_key=os.environ["OPENAI_API_KEY"]
        ),
    )
    runtime.register_capability(create_meta_capability())
    result = runtime.run(user_input="投放Meta广告", user_id="user_001")
"""

from .runtime.runtime import AgentRuntime, GenericAgentRuntime, SessionContext
from .capabilities.meta import MetaCapability, create_meta_capability
from .capabilities.google import GoogleCapability, create_google_capability
from .capabilities.tiktok import TikTokCapability, create_tiktok_capability
from .capabilities.dv360 import DV360Capability, create_dv360_capability
from .persistence.store import AdAgentStore
from .persistence.session_manager import SessionManager
from .core.memory import MemoryManager, MemoryRecord, MemoryStore
from .domain.ad.knowledge import (
    KnowledgeDocument, KnowledgeProvider, MarkdownWikiKnowledgeProvider,
)
from .domain.ad.response import LLMResponseSynthesizer
from .core.response import ResponseSynthesizer
from .domain.ad.auth import RequestPrincipal
from .core.plugins import PluginKind, PluginLoader, PluginManifest, PluginRegistry, PluginState
from .core.plugin_package import PluginPackage, PluginPackageError, build_plugin_manifest
from .core.tool_sources import ToolBinding, ToolExecutor, ToolSource, StaticToolSource
from .core.turn_pipeline import (
    SequentialTurnPipeline, TurnExecutionContext, TurnPipeline, TurnStageResult,
)
from .integration import (
    advertising_skill_source,
    advertising_tool_source,
    capability_tool_source,
)
from .plugin_management import PluginPackageManager
from .runtime.task_executor import (
    TaskCapacityError, TaskExecutionContext, TaskExecutor, TaskExecutorError,
    UnknownTaskKind,
)

__version__ = "1.0.0"
__all__ = [
    "AgentRuntime",
    "GenericAgentRuntime",
    "SessionContext",
    "MetaCapability",
    "GoogleCapability",
    "TikTokCapability",
    "DV360Capability",
    "create_meta_capability",
    "create_google_capability",
    "create_tiktok_capability",
    "create_dv360_capability",
    "AdAgentStore",
    "SessionManager",
    "MemoryManager",
    "MemoryRecord",
    "MemoryStore",
    "KnowledgeDocument",
    "KnowledgeProvider",
    "MarkdownWikiKnowledgeProvider",
    "LLMResponseSynthesizer",
    "ResponseSynthesizer",
    "RequestPrincipal",
    "PluginKind",
    "PluginLoader",
    "PluginManifest",
    "PluginRegistry",
    "PluginState",
    "PluginPackage",
    "PluginPackageError",
    "build_plugin_manifest",
    "ToolBinding",
    "ToolExecutor",
    "ToolSource",
    "StaticToolSource",
    "SequentialTurnPipeline",
    "TurnExecutionContext",
    "TurnPipeline",
    "TurnStageResult",
    "advertising_skill_source",
    "advertising_tool_source",
    "capability_tool_source",
    "PluginPackageManager",
    "TaskExecutor",
    "TaskExecutionContext",
    "TaskExecutorError",
    "TaskCapacityError",
    "UnknownTaskKind",
]
