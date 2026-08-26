"""
runtime/runtime.py - Agent Runtime 主循环

借鉴 DAP Agent internal/core/engine/runtime.go
核心职责：
1. 管理 Session 生命周期
2. 处理用户输入 → LLM → ToolCall → 执行 → 返回结果
3. 多平台 Skill 工具的统一调度
4. 跨 Skill 上下文传递
5. 预留 MultiAgentBridge 接口（用于后续切换到多 Agent）
"""

import uuid
import time
import json
import os
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import yaml

from ..core.interfaces import (
    ToolContext, ToolResult, ChatMessage, CapabilityModule,
    CapabilityRuntime, ToolRegistry, WriteGuard, IntentParser, IntentRouter,
    ParsedIntent, ToolHandler
)
from ..core.tool_registry import SimpleToolRegistry
from ..core.intent import LLMIntentParser, SimpleIntentRouter
from .skill import Skill, SkillLoader
from ..persistence.session_manager import SessionManager
from ..persistence.store import AdAgentStore
from ..skills.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)


# ─── 账户白名单验证器 ───────────────────────────────────────────

class AccountWhitelistValidator:
    """
    账户白名单验证器
    
    只允许操作配置文件中指定的测试账户，防止误操作生产账户
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        self.allowed_accounts: dict[str, list[str]] = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self.allowed_accounts = config.get('allowed_accounts', {})
        except Exception as e:
            print(f"⚠️ 加载账户白名单配置失败: {e}")
    
    def reload(self):
        """重新加载配置"""
        self._load_config()
    
    def validate_account(self, platform: str, account_id: str) -> tuple[bool, str]:
        """
        验证账户是否在白名单中
        
        Returns:
            (is_allowed, error_message)
        """
        allowed = self.allowed_accounts.get(platform, [])
        
        # 如果白名单为空，允许所有账户（兼容模式）
        if not allowed:
            return True, ""
        
        # 检查账户是否匹配
        normalized_account = account_id.replace("act_", "")
        is_allowed = any(
            acc.replace("act_", "") == normalized_account 
            for acc in allowed
        )
        
        if not is_allowed:
            return False, f"账户 {account_id} 不在 {platform} 白名单中。允许操作的账户: {', '.join(allowed)}"
        
        return True, ""
    
    def get_allowed_accounts(self, platform: str) -> list[str]:
        """获取平台允许操作的账户列表"""
        return self.allowed_accounts.get(platform, [])


# ─── Agent Runtime ─────────────────────────────────────────────

class AgentRuntime:
    """
    单 Agent + 多 Skills 的主运行时。
    
    架构层次：
    ┌─────────────────────────────────────────┐
    │  AgentRuntime（主循环）                   │
    │  ├─ SessionManager（会话管理）             │
    │  ├─ IntentRouter（意图路由）               │
    │  ├─ ToolRegistry（工具执行）               │
    │  ├─ WriteGuard（写入保护）                 │
    │  └─ MultiAgentBridge（多 Agent 预留）      │
    └─────────────────────────────────────────┘
    
    借鉴 DAP Agent internal/core/engine/runtime.go 的核心设计：
    - Core 只认接口，不 import 业务
    - 业务通过 CapabilityModule 注入
    - Tool 执行有统一的生命周期（权限→审批→幂等→执行→审计）
    """
    
    def __init__(
        self,
        registry: ToolRegistry = None,
        intent_parser: IntentParser = None,
        intent_router: IntentRouter = None,
        write_guard: WriteGuard = None,
        skill_roots: list[str] = None,
        llm_client=None,  # 可选：自定义 LLM 客户端
        persistence_store: AdAgentStore = None,
        whitelist_validator: AccountWhitelistValidator = None,
    ):
        self.registry = registry or SimpleToolRegistry()
        self.intent_parser = intent_parser or LLMIntentParser(llm_client)
        self.intent_router = intent_router or SimpleIntentRouter()
        self.write_guard = write_guard
        self.skill_loader = SkillLoader(skill_roots)
        self._llm = llm_client
        self._sessions: dict[str, "SessionContext"] = {}
        self._background_tasks: list[dict] = []
        self._loaded_skills: dict[str, Skill] = {}  # platform -> Skill
        self._skill_factories: dict[str, callable] = {}  # platform -> Capability factory
        self._credentials: dict = {}  # API 凭证配置
        
        # 账户白名单验证器
        self.whitelist_validator = whitelist_validator or AccountWhitelistValidator()
        
        # 预留：多 Agent 桥接
        self._multi_agent_bridge: Optional["MultiAgentBridge"] = None
        
        # 持久化层（可选）
        self._session_manager: Optional[SessionManager] = None
        if persistence_store:
            self._session_manager = SessionManager(persistence_store)
    
    def inject_llm(self, llm_client) -> None:
        """注入 LLM 客户端"""
        self._llm = llm_client
        if isinstance(self.intent_parser, LLMIntentParser):
            self.intent_parser.inject_llm(llm_client)
    
    # ─── Capability 注册 ───────────────────────────────────────
    
    def register_capability(self, module: CapabilityModule) -> CapabilityRuntime:
        """
        注册一个 CapabilityModule。
        
        对应 DAP Agent 的 CapabilityModule.Configure() 模式：
        业务模块不直接操作 Runtime，而是通过接口注入能力。
        """
        context = CapabilityContextWrapper(self.registry)
        runtime = module.configure(context)
        
        # 注册编排 Skill
        for skill in runtime.orchestrator_skills:
            self._register_skill(skill)
        
        # 注册后台任务
        self._background_tasks.extend(runtime.background_tasks)
        
        # 注册写入保护
        if runtime.write_guard:
            self.write_guard = runtime.write_guard
        
        return runtime
    
    def _register_skill(self, skill: Skill) -> None:
        """将 Skill 的工具注册到 Registry"""
        for tool_def in skill.get_tools():
            handler = skill.get_tool_handler(tool_def.name)
            if handler:
                self.registry.register(tool_def, handler)
    
    # ─── Skill 动态注册 ────────────────────────────────────────
    
    def register_skill(self, skill: Skill, platform: str, api_client=None) -> None:
        """
        动态注册一个 Skill。
        
        策略：直接使用 Capability 的工具定义，而不是动态创建 Handler。
        
        Args:
            skill: Skill 对象（从 SKILL.md 解析）
            platform: 平台名称
            api_client: API 客户端（None 时使用 mock 模式）
        """
        from ..skills.skill_registry import SkillBinding
        
        # 查找对应的 Capability 模块
        from ..capabilities import meta, google, tiktok, dv360
        platform_map = {
            'meta': (meta, 'Meta'),
            'google-ads': (google, 'Google'),
            'tiktok': (tiktok, 'TikTok'),
            'dv360': (dv360, 'DV360'),
        }
        
        module_info = platform_map.get(platform)
        if not module_info:
            logger.warning(f"⚠️ 未找到平台 '{platform}' 的 Capability 模块")
            return
        
        module, prefix = module_info
        
        # 创建 Capability 实例并设置 api_client
        capability_class = getattr(module, f'{prefix}Capability')
        capability = capability_class()
        capability._api_client = api_client
        
        # 获取所有工具定义（直接从 Capability 获取）
        tools = capability.register_tools()
        if not tools:
            logger.warning(f"⚠️ Capability '{platform}' 没有定义任何工具")
            return
        
        # 创建 SkillBinding
        binding = SkillBinding(
            skill=skill,
            platform=platform,
            handler_factory=lambda client: self._create_handler(skill, platform, client),
            is_enabled=True
        )
        
        # 注册工具
        registered_count = 0
        for tool_def, handler in tools:
            try:
                self.registry.register(tool_def, handler)
                registered_count += 1
                logger.debug(f"✅ 注册工具: {tool_def.name} (platform={platform})")
            except Exception as e:
                logger.warning(f"⚠️ 注册工具失败 '{tool_def.name}': {e}")
        
        # 保存 Skill 和平台映射
        self._loaded_skills[platform] = skill
        logger.info(f"✅ 已动态注册 Skill '{skill.name}'，共 {registered_count} 个工具")
    
    def load_skill(self, platform: str, skill: Skill, api_client=None) -> bool:
        """
        根据平台名称加载对应的 Skill。
        
        Args:
            platform: 平台名称 (meta/google/tiktok/dv360)
            skill: Skill 对象
            api_client: API 客户端
            
        Returns:
            是否加载成功
        """
        if platform in self._loaded_skills:
            logger.info(f"ⓘ Skill '{platform}' 已加载，跳过")
            return True
        
        try:
            self.register_skill(skill, platform, api_client)
            return True
        except Exception as e:
            logger.error(f"❌ 加载 Skill '{platform}' 失败: {e}")
            return False
    
    def unload_skill(self, platform: str) -> bool:
        """
        卸载指定平台的 Skill 工具。
        
        Args:
            platform: 平台名称
            
        Returns:
            是否卸载成功
        """
        if platform not in self._loaded_skills:
            return True
        
        try:
            skill = self._loaded_skills[platform]
            tool_names = [t.name for t in skill.tools]
            
            # 从 registry 中移除
            for name in tool_names:
                if name in self.registry._tools:
                    del self.registry._tools[name]
                    # 清理索引
                    for index in [self.registry._by_skill, self.registry._by_platform]:
                        for key in list(index.keys()):
                            if name in index[key]:
                                index[key].remove(name)
            
            # 清理工具定义缓存
            for skill_name in list(self.registry._skill_tool_defs.keys()):
                self.registry._skill_tool_defs[skill_name] = [
                    t for t in self.registry._skill_tool_defs[skill_name]
                    if t.name not in tool_names
                ]
            
            del self._loaded_skills[platform]
            logger.info(f"✅ 已卸载 Skill '{platform}'，移除 {len(tool_names)} 个工具")
            return True
        except Exception as e:
            logger.error(f"❌ 卸载 Skill '{platform}' 失败: {e}")
            return False
    
    def get_loaded_skills(self) -> dict[str, Skill]:
        """获取所有已加载的 Skills"""
        return self._loaded_skills.copy()
    
    def get_available_skills(self) -> dict[str, Skill]:
        """获取所有可用的 Skills（包括未加载的）"""
        all_skills = {}
        for root in self.skill_loader._roots:
            if root.exists():
                for skill_dir in root.iterdir():
                    if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                        # 尝试加载但只获取元信息
                        pass
        return all_skills
    
    def _load_required_skills(self, platforms: list[str]) -> None:
        """
        根据平台列表动态加载对应的 Skill 工具。
        
        Args:
            platforms: 需要加载的平台列表
        """
        if not platforms:
            return
        
        for platform in platforms:
            if platform in self._loaded_skills:
                continue  # 已加载，跳过
            
            # 查找对应的 Skill
            skill = self._find_skill_by_platform(platform)
            if not skill:
                logger.warning(f"⚠️ 未找到平台 '{platform}' 的 Skill 定义")
                continue
            
            # 获取 API 客户端
            api_client = self._get_api_client(platform)
            
            # 加载 Skill
            self.load_skill(platform, skill, api_client)
    
    def _find_skill_by_platform(self, platform: str) -> 'Skill':
        """
        根据平台名称查找对应的 Skill。
        
        策略：
        1. 从已加载的 Skill 中查找
        2. 从 SkillLoader 缓存中查找
        """
        # 先从已加载的 Skill 中查找
        if platform in self._loaded_skills:
            return self._loaded_skills[platform]
        
        # 从 skill_loader 中查找
        for root in self.skill_loader._roots:
            if not root.exists():
                continue
            for skill_dir in root.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                try:
                    import re
                    with open(skill_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if content.startswith('---'):
                        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                        if match:
                            import yaml
                            metadata = yaml.safe_load(match.group(1))
                            skill_name = metadata.get('name', skill_dir.name)
                            # 检查平台匹配（支持 google/google-ads 映射）
                            skill_platform = metadata.get('platform', skill_dir.name)
                            if skill_platform == platform or skill_dir.name == platform:
                                # 直接加载这个 skill
                                from ..skills.loader import SkillLoader as Loader
                                loader = Loader()
                                loader.add_root(str(root))
                                skills = loader.load_all()
                                if skill_name in skills:
                                    return skills[skill_name]
                except Exception as e:
                    logger.debug(f"解析 Skill 文件失败 {skill_dir.name}: {e}")
        return None
    
    def set_credentials(self, credentials: dict) -> None:
        """设置 API 凭证配置"""
        self._credentials = credentials
    
    def _get_api_client(self, platform: str):
        """获取指定平台的 API 客户端"""
        if not self._credentials:
            return None
        
        # 支持平台别名映射（google-ads -> google）
        alias_map = {'google-ads': 'google'}
        cred_key = alias_map.get(platform, platform)
        
        credentials = self._credentials.get(cred_key, {})
        if not credentials:
            # 尝试原始平台名
            credentials = self._credentials.get(platform, {})
        
        if not credentials:
            return None
        
        try:
            client_map = {
                'meta': ('api_clients.meta_client', 'MetaAPIClient'),
                'google-ads': ('api_clients.google_ads_client', 'GoogleAdsAPIClient'),
                'google': ('api_clients.google_ads_client', 'GoogleAdsAPIClient'),
                'tiktok': ('api_clients.tiktok_client', 'TikTokAPIClient'),
                'dv360': ('api_clients.dv360_client', 'DV360APIClient'),
            }
            
            if platform in client_map:
                module_name, class_name = client_map[platform]
                import importlib
                module = importlib.import_module(f'..{module_name}', __package__)
                client_class = getattr(module, class_name)
                return client_class(credentials)
        except Exception as e:
            logger.debug(f"创建 {platform} API Client 失败: {e}")
        
        return None
    
    def auto_load_skills(self, skills_root: str, credentials: dict = None) -> int:
        """
        自动加载 skills 目录下的所有 Skills。
        
        策略：
        1. 扫描 channels/ 子目录（渠道层 Skills）
        2. 扫描 businesses/ 子目录（业务层 Skills）
        3. 扫描 cross-channel/ 子目录（跨渠道 Skills）
        4. 只加载有工具定义的 Skill
        
        Args:
            skills_root: Skills 根目录路径
            credentials: API 凭证配置
            
        Returns:
            成功加载的 Skill 数量
        """
        import yaml
        from pathlib import Path
        
        loaded_count = 0
        # 保存凭证配置
        if credentials:
            self._credentials = credentials
        
        skill_roots = [
            Path(skills_root) / "channels",
            Path(skills_root) / "businesses",
            Path(skills_root) / "cross-channel",
        ]
        
        for root in skill_roots:
            if not root.exists():
                continue
            
            for skill_dir in root.iterdir():
                if not skill_dir.is_dir():
                    continue
                
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                
                try:
                    # 解析 SKILL.md frontmatter
                    with open(skill_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    metadata = {}
                    if content.startswith('---'):
                        import re
                        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                        if match:
                            metadata = yaml.safe_load(match.group(1))
                    
                    platform = metadata.get('platform', skill_dir.name)
                    
                    # 检查是否有工具定义（从表格解析）
                    has_tools = '| Tool |' in content or 'name:' in content
                    
                    if has_tools:
                        # 加载 Skill
                        from ..skills.loader import SkillLoader
                        loader = SkillLoader()
                        loader.add_root(str(root))
                        skills = loader.load_all()
                        
                        skill = skills.get(skill_dir.name)
                        if not skill:
                            # 尝试从 name 字段获取
                            for s_name, s in skills.items():
                                if s.platform == platform:
                                    skill = s
                                    break
                        
                        if skill and skill.tools:
                            # 获取 API 客户端
                            # 支持平台别名映射（google-ads -> google）
                            cred_key = platform
                            if platform not in credentials:
                                alias_map = {'google-ads': 'google'}
                                cred_key = alias_map.get(platform, platform)
                            
                            api_client = None
                            if credentials and cred_key in credentials:
                                # 根据平台导入对应的 API Client
                                client_map = {
                                    'meta': ('api_clients.meta_client', 'MetaAPIClient'),
                                    'google-ads': ('api_clients.google_ads_client', 'GoogleAdsAPIClient'),
                                    'tiktok': ('api_clients.tiktok_client', 'TikTokAPIClient'),
                                    'dv360': ('api_clients.dv360_client', 'DV360APIClient'),
                                }
                                
                                if platform in client_map:
                                    module_name, class_name = client_map[platform]
                                    try:
                                        import importlib
                                        module = importlib.import_module(f'..{module_name}', __package__)
                                        client_class = getattr(module, class_name)
                                        api_client = client_class(credentials[cred_key])
                                    except Exception as e:
                                        logger.debug(f"创建 {platform} API Client 失败: {e}")
                            
                            # 加载 Skill
                            if self.load_skill(platform, skill, api_client):
                                loaded_count += 1
                                logger.info(f"✅ 自动加载 Skill: {skill.name} ({platform}, {len(skill.tools)} tools)")
                            else:
                                logger.warning(f"⚠️ 加载 Skill 失败: {skill.name}")
                
                except Exception as e:
                    logger.warning(f"⚠️ 解析 Skill {skill_dir.name}/SKILL.md 失败: {e}")
        
        logger.info(f"✅ 自动加载完成，共加载 {loaded_count} 个 Skills")
        return loaded_count
    
    def _create_handler(self, skill: Skill, platform: str, api_client=None) -> Optional[ToolHandler]:
        """
        根据 Skill 和平台动态创建 Handler。
        
        策略：
        1. 根据 tool_name 推断 Handler 类名
        2. 从对应的 Capability 模块动态导入
        3. 支持多种命名约定：
           - {Prefix}{Action}RealHandler
           - {Prefix}{Action}Handler
           - {Prefix}{Action}MockHandler
        """
        import importlib
        
        # 根据 platform 选择模块和 prefix
        platform_map = {
            'meta': ('meta', 'Meta'),
            'google-ads': ('google', 'Google'),
            'tiktok': ('tiktok', 'TikTok'),
            'dv360': ('dv360', 'DV360'),
        }
        
        module_name, prefix = platform_map.get(platform, (None, None))
        if not module_name:
            return None
        
        try:
            # 导入模块
            module = importlib.import_module(f'..capabilities.{module_name}', __package__)
            
            # 返回工厂函数
            def handler_factory(tool_name):
                # 移除 platform 前缀
                parts = tool_name.split('_', 1)
                if len(parts) < 2:
                    return None
                
                action_part = parts[1]  # 'auth', 'create_campaign', 'list_campaigns'
                
                # 转换为 TitleCase
                words = action_part.split('_')
                title_case = ''.join(w.capitalize() for w in words)
                
                # 生成多种可能的 Handler 类名
                possible_names = [
                    f"{prefix}{title_case}RealHandler",     # MetaListCampaignsRealHandler
                    f"{prefix}{title_case}Handler",         # TikTokListCampaignsHandler
                    f"{prefix}{title_case}MockHandler",     # MetaListCampaignsMockHandler
                ]
                
                # 尝试找到对应的 Handler 类
                for handler_name in possible_names:
                    if hasattr(module, handler_name):
                        handler_class = getattr(module, handler_name)
                        
                        # 检查构造函数签名
                        import inspect
                        sig = inspect.signature(handler_class.__init__)
                        params = list(sig.parameters.keys())
                        
                        # 根据参数决定如何实例化
                        if 'api_client' in params or 'client' in params:
                            return handler_class(api_client)
                        else:
                            return handler_class()
                
                return None
            
            # 绑定当前 tool_name
            return lambda tool_name: handler_factory(tool_name)
            
        except Exception as e:
            logger.debug(f"创建 Handler 失败 {platform}: {e}")
            return None
    
    # ─── 主循环入口 ────────────────────────────────────────────
    
    def run(
        self,
        user_input: str,
        session_id: str = None,
        user_id: str = "anonymous",
        account_id: str = None,
        credentials: dict = None,
        platform_params: dict = None,
    ) -> dict:
        """
        执行一次完整的对话回合。
        
        对应 DAP Agent 的 Core Engine 主循环：
        用户输入 → 意图解析 → 工具路由 → 执行 → 返回结果
        
        Returns:
            {
                "session_id": str,
                "turn_id": str,
                "intent": dict,           # 解析后的意图
                "tool_calls": [...],       # 计划调用的工具
                "results": [...],          # 各工具执行结果
                "reply": str,              # 给用户的回复
                "needs_confirmation": bool, # 是否需要用户确认
            }
        """
        session_id = session_id or str(uuid.uuid4())
        turn_id = str(uuid.uuid4())[:8]
        
        # Step 1: 确保 Session 存在
        session = self._ensure_session(session_id, user_id, account_id, credentials)
        
        # Step 2: 解析用户意图
        intent = self.intent_parser.parse(user_input, session.ctx)
        
        # 如果提供了 platform_params（来自确认请求），合并到意图中
        if platform_params:
            intent.platform_params = platform_params
        
        # Step 2.5: 动态加载相关平台的 Skill 工具
        self._load_required_skills(intent.platforms)
        
        # Step 3: 路由到平台工具
        tool_plan = self.intent_router.route(intent, self.registry)
        
        # 检查是否需要执行任何工具
        if not tool_plan:
            return {
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": datetime.now().isoformat(),
                "intent": intent.to_dict(),
                "tool_plan": {},
                "results": [],
                "reply": self._generate_chat_reply(user_input),
                "needs_confirmation": False,
                "confirmation_payload": None,
            }
        
        # Step 4: 执行工具（按平台顺序）
        results = []
        needs_confirmation = False
        confirmation_payload = None
        
        for platform, tools in tool_plan.items():
            # 检查账户是否有效（所有操作都需要）
            if not account_id:
                # 尝试从配置中获取测试账户
                test_accounts = self.whitelist_validator.get_allowed_accounts(platform)
                if test_accounts:
                    # 自动使用第一个测试账户
                    account_id = test_accounts[0]
                    # 同时更新 session context
                    session.ctx.account_id = account_id
                else:
                    # 没有配置测试账户，询问用户
                    results.append({
                        "tool": tools[0].name if tools else "unknown",
                        "platform": platform,
                        "success": False,
                        "error": "缺少账户ID",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "ask_account",
                            "platform": platform,
                            "question": f"请问您要操作哪个 {platform} 账户？请提供账户ID",
                        },
                    })
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    continue
            
            for tool_def in tools:
                # 白名单验证（写操作）
                if tool_def.is_write_tool and account_id:
                    allowed, error_msg = self.whitelist_validator.validate_account(platform, account_id)
                    if not allowed:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": f"账户验证失败: {error_msg}",
                        })
                        continue
                # 检查是否需要写入保护
                if tool_def.is_write_tool and self.write_guard:
                    allowed, reason = self.write_guard.reserve_write(
                        session.ctx, tool_def, intent.platform_params.get(platform, {})
                    )
                    if not allowed:
                        results.append({
                            "tool": tool_def.name,
                            "platform": platform,
                            "success": False,
                            "error": f"Write guard blocked: {reason}",
                        })
                        continue
                
                # 构建执行输入
                tool_input = self._build_tool_input(
                    tool_def, intent, platform, session.ctx
                )
                
                # 检查必需参数是否齐全，不齐全则询问用户
                missing_params = tool_input.pop("_missing_params", None)
                if missing_params:
                    results.append({
                        "tool": tool_def.name,
                        "platform": platform,
                        "success": False,
                        "error": f"缺少必需参数: {', '.join(missing_params)}",
                        "needs_confirmation": True,
                        "confirmation_payload": {
                            "type": "ask_params",
                            "tool": tool_def.name,
                            "missing": missing_params,
                            "question": f"⚠️ 执行 {tool_def.name} 需要以下参数：{', '.join(missing_params)}，请提供这些参数",
                        },
                    })
                    needs_confirmation = True
                    confirmation_payload = results[-1]["confirmation_payload"]
                    continue
                
                # 执行工具
                result = self.registry.execute(session.ctx, tool_def.name, tool_input)
                
                results.append({
                    "tool": tool_def.name,
                    "platform": platform,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                    "needs_confirmation": result.requires_confirmation,
                })
                
                if result.requires_confirmation:
                    needs_confirmation = True
                    confirmation_payload = result.card_payload
                
                # 保存执行结果到会话上下文（跨 Tool 传递）
                session.save_result(tool_def.name, result)
                
                # 将 protected_state 同步回 ctx，使后续 Tool 可以读取
                session.ctx.protected_state.update(session.protected_state)
        
        # Step 5: 生成回复
        reply = self._generate_reply(intent, results, needs_confirmation)
        
        # Step 6: 记录消息历史
        session.add_message({"role": "user", "content": user_input})
        session.add_message({"role": "assistant", "content": reply})
        
        return {
            "session_id": session_id,
            "turn_id": turn_id,
            "timestamp": datetime.now().isoformat(),
            "intent": intent.to_dict(),
            "tool_plan": {k: [t.name for t in v] for k, v in tool_plan.items()},
            "results": results,
            "reply": reply,
            "needs_confirmation": needs_confirmation,
            "confirmation_payload": confirmation_payload,
        }
    
    def _build_tool_input(
        self,
        tool_def: Any,
        intent: ParsedIntent,
        platform: str,
        ctx: Any = None,
    ) -> dict:
        """
        根据意图和工具定义，构建执行输入。
        
        优先级：
        1. intent.platform_params[platform][tool_name]  ← 最具体
        2. intent.platform_params[platform].get(...)     ← 平台级参数
        3. ctx.account_id                              ← 账户ID
        4. intent 通用字段（budget, objective 等）
        5. 工具定义的默认值
        """
        platform_params = intent.platform_params.get(platform, {})
        tool_input = {}
        
        # 从平台参数中提取该工具需要的字段
        tool_prefix = tool_def.name.replace(f"{platform}_", "")
        for param_name, param_value in platform_params.items():
            if param_name in tool_def.input_schema.properties:
                tool_input[param_name] = param_value
        
        # 填充账户 ID（从上下文）
        if ctx and ctx.account_id:
            # 尝试多种账户 ID 字段名
            for account_field in ["account_id", "advertiser_id", "customer_id"]:
                if account_field in tool_def.input_schema.properties:
                    if account_field not in tool_input:
                        tool_input[account_field] = ctx.account_id
                        break
        
        # 填充通用字段
        if intent.budget and "budget" not in tool_input:
            tool_input["budget"] = intent.budget
        if intent.objective and "objective" not in tool_input:
            tool_input["objective"] = intent.objective
        if intent.creative_materials and "creative_materials" not in tool_input:
            tool_input["creative_materials"] = intent.creative_materials
        
        # 检查必需参数是否齐全
        missing = []
        for req in tool_def.input_schema.required or []:
            if req not in tool_input:
                missing.append(req)
        
        if missing:
            # 参数不全，标记为需要确认
            tool_input["_missing_params"] = missing
        
        return tool_input
    
    def _generate_reply(
        self,
        intent: ParsedIntent,
        results: list[dict],
        needs_confirmation: bool,
    ) -> str:
        """根据执行结果生成用户友好的回复"""
        success_count = sum(1 for r in results if r.get("success"))
        fail_count = len(results) - success_count
        
        # 检查是否有需要确认的情况
        ask_params_results = [r for r in results if r.get("needs_confirmation") and r.get("confirmation_payload")]
        if ask_params_results:
            # 需要用户提供参数
            questions = []
            for r in ask_params_results:
                payload = r.get("confirmation_payload", {})
                if payload.get("type") == "ask_params":
                    questions.append(payload.get("question", "请提供必要参数"))
            if questions:
                return "\n\n".join(questions)
        
        if needs_confirmation:
            return "⚠️ 需要确认：部分操作需要您的确认才能继续。"
        
        if fail_count > 0 and success_count == 0:
            errors = [r.get("error", "unknown") for r in results if not r.get("success")]
            return f"❌ 执行失败：{errors}"
        elif fail_count > 0:
            return (
                f"⚠️ 部分成功：{success_count} 个操作完成，{fail_count} 个失败。\n"
                + "\n".join(f"  - {r['tool']}: {r.get('error', 'failed')}"
                          for r in results if not r.get("success"))
            )
        else:
            # 根据工具名判断操作类型
            is_list_op = any('list' in r.get('tool', '').lower() for r in results)
            is_get_op = any('get_' in r.get('tool', '').lower() or 'report' in r.get('tool', '').lower() for r in results)
            
            if is_list_op or is_get_op:
                # 查询类操作
                lines = []
                for r in results:
                    tool = r.get('tool', '')
                    platform = r.get('platform', '')
                    data = r.get('data', {})
                    
                    # 提取并格式化结果数据
                    if 'campaigns' in data:
                        campaigns = data['campaigns']
                        if campaigns:
                            lines.append(f"📊 [{platform}] 找到 {len(campaigns)} 个 Campaign:\n")
                            for i, c in enumerate(campaigns[:5], 1):  # 最多显示 5 个
                                lines.append(f"  📌 Campaign #{i}:")
                                for k, v in c.items():
                                    if v is not None and v != '' and v != 0:
                                        lines.append(f"    • {k}: {v}")
                            if len(campaigns) > 5:
                                lines.append(f"  ... 还有 {len(campaigns) - 5} 个")
                        else:
                            lines.append(f"📊 [{platform}] 没有找到 Campaign")
                    elif 'accounts' in data:
                        accounts = data['accounts']
                        if accounts:
                            lines.append(f"📊 [{platform}] 找到 {len(accounts)} 个账户:\n")
                            for i, a in enumerate(accounts[:5], 1):
                                lines.append(f"  📌 Account #{i}:")
                                for k, v in a.items():
                                    if v is not None and v != '':
                                        lines.append(f"    • {k}: {v}")
                        else:
                            lines.append(f"📊 [{platform}] 没有找到账户")
                    elif 'metrics' in data:
                        metrics = data['metrics']
                        lines.append(f"📊 [{platform}] 报表数据:\n")
                        for k, v in metrics.items():
                            if isinstance(v, float):
                                lines.append(f"  • {k}: {v:.2f}")
                            else:
                                lines.append(f"  • {k}: {v}")
                    else:
                        lines.append(f"✅ [{platform}] {tool}")
                
                return "\n".join(lines) if lines else f"✅ 成功执行 {success_count} 个查询操作"
            else:
                # 创建类操作
                return (
                    f"✅ 成功创建 {success_count} 个广告操作：\n"
                    + "\n".join(f"  - [{r.get('platform', '?')}] {r['tool']}"
                              for r in results)
                )
    
    def _generate_chat_reply(self, user_input: str) -> str:
        """生成闲聊回复"""
        text = user_input.lower()
        
        # 问候语
        if any(kw in text for kw in ["你好", "hello", "hi", "在吗"]):
            return (
                "👋 你好！我是 ad-agent，您的广告投放专家助手。\n\n"
                "我可以帮您：\n"
                "• 创建 Meta/TikTok/Google Ads/DV360 广告系列\n"
                "• 查询投放报表和性能数据\n"
                "• 优化跨渠道预算分配\n\n"
                "请告诉我您的需求，例如：\n"
                '- "帮我创建一个 Meta 广告系列"\n'
                '- "列出 TikTok Campaign 列表"'
            )
        
        # 帮助请求
        if any(kw in text for kw in ["帮助", "help", "你能做什么", "怎么使用"]):
            return (
                "🤖 我是广告投放专家助手，支持以下功能：\n\n"
                "📊 **查询功能**\n"
                "• 列出各平台 Campaign 列表\n"
                "• 查看投放报表和性能数据\n\n"
                "✏️ **创建功能**\n"
                "• Meta: 创建 Campaign/Ad Set/Ad\n"
                "• TikTok: 创建 Campaign/Ad Group/Ad\n"
                "• Google Ads: 创建 Campaign（搜索/购物/PMax）\n"
                "• DV360: 创建 Campaign/IO/Line Item\n\n"
                "⚡ **优化功能**\n"
                "• 跨渠道预算分配建议\n"
                "• 出价策略优化\n\n"
                "💡 **提示**：请明确指定平台和操作，例如：\n"
                '- "帮我创建一个 Meta 广告系列"\n'
                '- "列出 TikTok Campaign 列表"'
            )
        
        # 默认回复
        return "👋 你好！我是 ad-agent，您的广告投放专家助手。请告诉我您的需求。"

# ─── Session 管理 ──────────────────────────────────────────
    
    def _ensure_session(
        self,
        session_id: str,
        user_id: str,
        account_id: str,
        credentials: dict,
    ) -> "SessionContext":
        if session_id not in self._sessions:
            ctx = ToolContext(
                session_id=session_id,
                user_id=user_id,
                account_id=account_id,
                credentials=credentials or {},
            )
            session = SessionContext(session_id, ctx)
            self._sessions[session_id] = session
            
            # Save to persistence if available
            if self._session_manager:
                self._session_manager.create_session(
                    session_id, user_id, account_id, {"credentials": credentials or {}}
                )
        return self._sessions[session_id]
    
    # ─── 多 Agent 桥接（预留） ─────────────────────────────────
    
    def attach_multi_agent_bridge(self, bridge: "MultiAgentBridge") -> None:
        """
        附加多 Agent 桥接器。
        
        当前是单 Agent 模式，调用此方法后可无缝切换到多 Agent 模式。
        桥接器负责将单次 run() 拆分为多个 Agent 实例的协作调用。
        """
        self._multi_agent_bridge = bridge
    
    def run_multi_agent(self, user_input: str, **kwargs) -> dict:
        """
        多 Agent 模式入口（预留接口）。
        
        当 attach_multi_agent_bridge() 被调用后，此方法生效。
        否则回退到单 Agent 模式（调用 run()）。
        """
        if self._multi_agent_bridge:
            return self._multi_agent_bridge.dispatch(user_input, **kwargs)
        return self.run(user_input, **kwargs)


# ─── Session Context ────────────────────────────────────────────

class SessionContext:
    """
    会话上下文 - 对应 Go 的 core.AgentContext + Session
    
    管理单次对话的历史消息和跨 Tool 调用状态。
    """
    
    def __init__(self, session_id: str, ctx: ToolContext):
        self.session_id = session_id
        self.ctx = ctx
        self.messages: list[dict] = []
        self.tool_results: dict[str, ToolResult] = {}  # tool_name -> last result
        self.protected_state: dict[str, Any] = {}      # 跨 Tool 保持的状态
    
    def add_message(self, message: dict) -> None:
        """添加对话消息"""
        self.messages.append(message)
    
    def save_result(self, tool_name: str, result: ToolResult) -> None:
        """保存工具执行结果，供后续 Tool 引用"""
        self.tool_results[tool_name] = result
        # 如果结果中有 campaign_id 等关键字段，自动保存到 protected_state
        for key in ["campaign_id", "ad_set_id", "ad_group_id", "creative_id"]:
            if key in result.data:
                self.protected_state[key] = result.data[key]
    
    def get_protected(self, key: str, default=None) -> Any:
        """获取跨 Tool 共享的受保护状态"""
        return self.protected_state.get(key, default)
    
    def to_chat_messages(self) -> list[ChatMessage]:
        """转换为 ChatMessage 列表（供 LLM 使用）"""
        return [
            ChatMessage(
                role=m["role"],
                content=m["content"],
            )
            for m in self.messages
        ]


# ─── CapabilityContextWrapper ───────────────────────────────────

class CapabilityContextWrapper:
    """
    Capability 配置上下文包装器。
    
    对应 DAP Agent 的 CapabilityContext，提供给 CapabilityModule.configure()。
    """
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.skills: dict[str, Skill] = {}
        self.config: dict[str, Any] = {}
    
    def register_skill(self, skill: Skill) -> None:
        """注册一个 Skill"""
        self.skills[skill.name] = skill


# ─── MultiAgentBridge（预留接口） ──────────────────────────────

class MultiAgentBridge:
    """
    多 Agent 桥接器接口。
    
    预留：未来可从单 Agent 切换到多 Agent 架构时，
    实现此接口并 attach 到 AgentRuntime。
    
    职责：
    - 将单次 run() 请求拆分为多个子 Agent 任务
    - 协调各子 Agent 的执行顺序和依赖
    - 汇总各子 Agent 的执行结果
    """
    
    @abstractmethod
    def dispatch(self, user_input: str, **kwargs) -> dict:
        """分发请求到多个子 Agent"""
        pass
    
    @abstractmethod
    def collect_results(self, agent_results: list[dict]) -> dict:
        """收集并汇总各子 Agent 的结果"""
        pass


from abc import ABC
MultiAgentBridge.__abstractmethods__ = {"dispatch", "collect_results"}
