"""
ad_agent - 多渠道广告投放 Agent

单 Agent + 多 Skills 架构，支持 Meta、Google Ads、TikTok Ads、DV360。

快速开始：
    from ad_agent import AdvertisingComposition, create_meta_tool_source
    from ad_agent.core.llm_client import create_llm_client
    
    runtime = AdvertisingComposition(
        require_llm=True,
        llm_client=create_llm_client(
            model=os.environ["LLM_MODEL"], api_key=os.environ["OPENAI_API_KEY"]
        ),
    )
    runtime.register_tool_source(create_meta_tool_source())
    result = runtime.run(user_input="投放Meta广告", user_id="user_001")
"""

from .runtime.runtime import AdvertisingComposition, SessionContext
from .application import AdvertisingApplication, create_advertising_application
from .tools.providers.meta import MetaToolSource, create_meta_tool_source
from .tools.providers.google import GoogleToolSource, create_google_tool_source
from .tools.providers.tiktok import TikTokToolSource, create_tiktok_tool_source
from .tools.providers.dv360 import DV360ToolSource, create_dv360_tool_source
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
from agents.agent_harness import (
    StaticToolSource,
    ToolBinding,
    ToolExecutor,
    ToolSource,
)
from .integration import advertising_skill_source, advertising_tool_source
from .agent_definition import advertising_agent_definition
from .plugin_management import PluginPackageManager
from .runtime.task_executor import (
    TaskCapacityError, TaskExecutionContext, TaskExecutor, TaskExecutorError,
    UnknownTaskKind,
)

__version__ = "1.0.0"
__all__ = [
    "AdvertisingComposition",
    "AdvertisingApplication",
    "create_advertising_application",
    "SessionContext",
    "MetaToolSource",
    "GoogleToolSource",
    "TikTokToolSource",
    "DV360ToolSource",
    "create_meta_tool_source",
    "create_google_tool_source",
    "create_tiktok_tool_source",
    "create_dv360_tool_source",
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
    "advertising_skill_source",
    "advertising_tool_source",
    "advertising_agent_definition",
    "PluginPackageManager",
    "TaskExecutor",
    "TaskExecutionContext",
    "TaskExecutorError",
    "TaskCapacityError",
    "UnknownTaskKind",
]
