"""
ad_agent - 多渠道广告投放 Agent

单 Agent + 多 Skills 架构，支持 Meta、Google Ads、TikTok Ads、DV360。

快速开始：
    from ad_agent import AgentRuntime, create_meta_capability
    from ad_agent.core.llm_client import create_llm_client
    
    runtime = AgentRuntime(
        require_llm=True,
        llm_client=create_llm_client(
            model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"]
        ),
    )
    runtime.register_capability(create_meta_capability())
    result = runtime.run(user_input="投放Meta广告", user_id="user_001")
"""

from .runtime.runtime import AgentRuntime, SessionContext
from .capabilities.meta import MetaCapability, create_meta_capability
from .capabilities.google import GoogleCapability, create_google_capability
from .capabilities.tiktok import TikTokCapability, create_tiktok_capability
from .capabilities.dv360 import DV360Capability, create_dv360_capability
from .persistence.store import AdAgentStore
from .persistence.session_manager import SessionManager
from .core.memory import MemoryManager, MemoryRecord, MemoryStore
from .core.knowledge import (
    KnowledgeDocument, KnowledgeProvider, MarkdownWikiKnowledgeProvider,
)
from .core.auth import RequestPrincipal
from .core.plugins import PluginKind, PluginLoader, PluginManifest, PluginRegistry, PluginState
from .core.plugin_package import PluginPackage, PluginPackageError, build_plugin_manifest
from .plugin_management import PluginPackageManager

__version__ = "1.0.0"
__all__ = [
    "AgentRuntime",
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
    "RequestPrincipal",
    "PluginKind",
    "PluginLoader",
    "PluginManifest",
    "PluginRegistry",
    "PluginState",
    "PluginPackage",
    "PluginPackageError",
    "build_plugin_manifest",
    "PluginPackageManager",
]
