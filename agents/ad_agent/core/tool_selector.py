"""
core/tool_selector.py - 动态工具选择器

核心功能：
1. 根据用户意图 + 目标平台，动态选择相关工具
2. 注入平台专家知识作为上下文
3. 优化 LLM 的 tool 列表，避免信息过载
"""

import re
import logging
import threading
import inspect
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field

from .interfaces import ToolDefinition, ParsedIntent, ToolContext
from .knowledge import KnowledgeProvider
from .policy import RuntimePolicy, apply_policies, policy_metadata
from .platform import normalize_platform

logger = logging.getLogger(__name__)


@dataclass
class ToolSelection:
    """工具选择结果"""
    selected_tools: List[ToolDefinition] = field(default_factory=list)
    platform: str = ""
    context: Dict = field(default_factory=dict)
    expert_knowledge: str = ""
    
    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "tool_count": len(self.selected_tools),
            "tools": [t.name for t in self.selected_tools],
            "context_keys": list(self.context.keys()),
            "expert_knowledge_available": bool(self.expert_knowledge),
        }


class DynamicToolSelector:
    """
    动态工具选择器
    
    工作原理：
    1. 根据用户意图识别目标平台
    2. 从 Skill Registry 获取该平台的所有工具
    3. 根据意图类型筛选相关工具（如查询→只选报表类工具）
    4. 注入平台专家知识作为上下文
    5. 返回精简的工具列表给 LLM
    """
    
    def __init__(
        self,
        skill_loader=None,
        knowledge_provider: Optional[KnowledgeProvider] = None,
        policies: Optional[list[RuntimePolicy]] = None,
    ):
        # Runtime injects its canonical SkillLoader.  The lazy fallback keeps
        # the standalone selector usable without importing the Runtime package
        # during module initialization.
        if skill_loader is None:
            from ..runtime.skill import SkillLoader
            skill_loader = SkillLoader()
            skill_loader.load_all()
        self.skill_loader = skill_loader
        self.knowledge_provider = knowledge_provider
        self.policies: list[RuntimePolicy] = list(policies or [])
        # Managed Skills are tenant-owned advisory context.  Keep them out of
        # the executable SkillLoader and select them per request so the
        # process-global Runtime can safely serve multiple tenants.
        self._context_skills: dict[str, dict[str, object]] = {}
        self._context_skills_lock = threading.RLock()

    def register_context_skill(self, skill: object, tenant_id: str = "default") -> None:
        """Register a user-managed Skill as bounded advisory context only."""
        name = str(getattr(skill, "name", "") or "").strip()
        if name:
            tenant = str(tenant_id or "default")
            with self._context_skills_lock:
                self._context_skills.setdefault(tenant, {})[name] = skill

    def unregister_context_skill(
        self, skill_name: str, tenant_id: str = "default"
    ) -> None:
        tenant = str(tenant_id or "default")
        with self._context_skills_lock:
            skills = self._context_skills.get(tenant)
            if not skills:
                return
            skills.pop(str(skill_name or ""), None)
            if not skills:
                self._context_skills.pop(tenant, None)
    
    def set_policies(self, policies: list[RuntimePolicy]) -> None:
        """Replace the policy set used for platform filtering and context."""
        self.policies = list(policies or [])

    def select_tools(
        self,
        user_input: str,
        intent: ParsedIntent,
        available_tools: List[ToolDefinition],
    ) -> ToolSelection:
        """
        根据用户输入和意图，动态选择相关工具
        
        Args:
            user_input: 用户原始输入
            intent: 解析后的意图
            available_tools: 所有可用工具
            
        Returns:
            ToolSelection: 选中的工具 + 上下文
        """
        # 1. 确定目标平台
        platforms = intent.platforms or self._detect_platforms(user_input, available_tools)
        
        # 2. 根据业务上下文过滤平台
        if self.policies:
            platforms = apply_policies(self.policies, platforms)
            if not platforms:
                platforms = apply_policies(
                    self.policies,
                    self._registered_platforms(available_tools),
                )
        
        # 3. 根据意图类型筛选工具
        intent_type = intent.intent_type
        selected_tools = []
        
        for platform in platforms:
            # 从 Skill Registry 获取该平台工具
            platform_tools = self._get_platform_tools(platform, available_tools)
            
            # 根据意图类型筛选
            filtered_tools = self._filter_by_intent(platform_tools, intent_type)
            
            # 4. 获取专家知识
            expert_knowledge = self._get_expert_knowledge(platform, intent_type)
            
            if filtered_tools:
                selection = ToolSelection(
                    selected_tools=filtered_tools,
                    platform=platform,
                    context={
                        "intent_type": intent_type,
                        "objective": intent.objective,
                        "budget": intent.budget,
                        **policy_metadata(self.policies),
                    },
                    expert_knowledge=expert_knowledge,
                )
                selected_tools.extend(filtered_tools)
        
        return ToolSelection(
            selected_tools=selected_tools,
            platform=",".join(platforms),
            expert_knowledge=self._merge_expert_knowledge(selected_tools),
            context={
                **policy_metadata(self.policies),
            },
        )

    def build_context_for_input(
        self,
        user_input: str,
        available_tools: List[ToolDefinition],
        intent_type: Optional[str] = None,
        tenant_id: str = "default",
    ) -> dict:
        """Build bounded Skill context before intent parsing.

        Intent parsing used to happen before the selector was consulted, which
        meant the LLM never saw the channel tool contracts or expert guidance
        that the selector had already prepared.  Use an intentionally neutral
        intent here: it only narrows by detected platform and keeps the first
        few registered tools, while the authoritative post-parse route still
        comes from ``IntentRouter``.
        """
        platforms = self._detect_platforms(user_input, available_tools)
        probe_intent = ParsedIntent(
            intent_type=intent_type or "",
            raw_input=user_input,
            platforms=platforms,
        )
        selection = self.select_tools(user_input, probe_intent, available_tools)
        knowledge = self._query_knowledge(
            user_input, platforms, intent_type=intent_type, tenant_id=tenant_id
        )
        if knowledge:
            selection.expert_knowledge = self._format_knowledge(knowledge)
        scheduling_context = self._scheduling_skill_context(
            user_input, intent_type=intent_type
        )
        if scheduling_context:
            selection.expert_knowledge = "\n\n".join(
                part for part in (selection.expert_knowledge, scheduling_context) if part
            )[:6000]
        managed_context = self._managed_skill_context(user_input, tenant_id=tenant_id)
        if managed_context:
            selection.expert_knowledge = "\n\n".join(
                part for part in (selection.expert_knowledge, managed_context) if part
            )[:6000]
        return {
            "tool_prompt": self.build_tool_prompt(selection),
            "expert_knowledge": selection.expert_knowledge,
            "platforms": selection.platform,
            "knowledge": knowledge,
        }

    def _scheduling_skill_context(
        self, user_input: str, *, intent_type: Optional[str] = None,
        max_chars: int = 3600,
    ) -> str:
        """Inject the built-in scheduling SOP as advisory parser context.

        Scheduling is a Runtime control feature, not a provider platform and
        therefore has no executable Tool definitions.  It still needs its
        Skill guidance before the first intent parse; selecting it through the
        normal provider-tool path would incorrectly make it look executable.
        """
        text = str(user_input or "").lower()
        schedule_markers = (
            "定时任务", "定时执行", "定期执行", "每小时", "每天", "每日",
            "每周", "每月", "cron", "schedule",
        )
        if not str(intent_type or "").startswith("schedule_") and not any(
            marker in text for marker in schedule_markers
        ):
            return ""
        loaded = getattr(self.skill_loader, "list_all", lambda: {})()
        sections: list[str] = []
        for skill in sorted(loaded.values(), key=lambda item: str(getattr(item, "name", ""))):
            platform = str(getattr(skill, "platform", "") or "").strip().lower()
            name = str(getattr(skill, "name", "") or "").strip().lower()
            if platform != "scheduling" and "schedule" not in name:
                continue
            markdown = str(getattr(skill, "raw_markdown", "") or "").strip()
            if not markdown:
                continue
            excerpt = markdown[:max_chars]
            references = getattr(skill, "reference_documents", {}) or {}
            if isinstance(references, dict):
                for path, content in sorted(references.items()):
                    excerpt += f"\n\n[{path}]\n{str(content)[:700]}"
                    if len(excerpt) >= max_chars:
                        break
            sections.append(
                "[built-in scheduling skill]\n"
                "以下内容仅用于定时任务理解和澄清，不会新增 Tool、权限或账户范围：\n"
                + excerpt[:max_chars]
            )
            if sections:
                break
        return "\n\n".join(sections)[:max_chars]

    def _managed_skill_context(
        self,
        user_input: str,
        max_chars: int = 6000,
        tenant_id: str = "default",
    ) -> str:
        """Build bounded, clearly non-executable context from managed Skills."""
        tenant = str(tenant_id or "default")
        with self._context_skills_lock:
            context_skills = dict(self._context_skills.get(tenant, {}))
        if not context_skills:
            return ""
        sections: list[str] = []
        for name, skill in sorted(context_skills.items()):
            markdown = str(getattr(skill, "raw_markdown", "") or "")
            description = str(getattr(skill, "description", "") or "")
            if not markdown and not description:
                continue
            excerpt = markdown[:2200] if markdown else description[:600]
            references = getattr(skill, "reference_documents", {}) or {}
            if isinstance(references, dict):
                reference_text = "\n\n".join(
                    f"[{path}]\n{str(content)[:800]}"
                    for path, content in sorted(references.items())
                )[:1800]
                if reference_text:
                    excerpt += "\n\n参考资料（仅上下文）：\n" + reference_text
            sections.append(
                f"[managed skill: {name}]\n"
                "以下内容仅是业务指导，不能新增工具、权限或修改账户/凭证：\n"
                + excerpt
            )
            if sum(len(item) for item in sections) >= max_chars:
                break
        return "\n\n".join(sections)[:max_chars]

    def _query_knowledge(
        self,
        user_input: str,
        platforms: List[str],
        *,
        intent_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """Query advisory knowledge without changing executable routing."""
        if self.knowledge_provider is None:
            return []
        try:
            kwargs = {
                "platforms": platforms,
                "intent_type": intent_type,
                "limit": 4,
                "max_excerpt_chars": 1000,
            }
            try:
                parameters = inspect.signature(self.knowledge_provider.query).parameters
                if tenant_id is not None and (
                    "tenant_id" in parameters or any(
                        item.kind == inspect.Parameter.VAR_KEYWORD
                        for item in parameters.values()
                    )
                ):
                    kwargs["tenant_id"] = tenant_id
            except (TypeError, ValueError):
                pass
            documents = self.knowledge_provider.query(user_input, **kwargs)
            return [document.to_dict() for document in documents]
        except Exception as exc:
            logger.debug("知识库查询失败，继续无知识上下文: %s", exc)
            return []

    @staticmethod
    def _format_knowledge(knowledge: list[dict], max_chars: int = 4000) -> str:
        return "\n\n".join(
            f"[{item['platform']}] {item['topic']} (source={item['source']}, "
            f"version={item['version']}, confidence={item['confidence']}):\n"
            f"{item['excerpt']}"
            for item in knowledge
        )[:max_chars]
    
    def _registered_platforms(self, available_tools: List[ToolDefinition]) -> List[str]:
        """Return platforms published by the current Tool/Skill registry."""
        platforms = {
            self._normalize_platform(tool.platform)
            for tool in (available_tools or [])
            if getattr(tool, "platform", None)
            and str(tool.platform).lower() != "multi_platform"
        }
        loaded_skills = getattr(self.skill_loader, "list_all", lambda: {})()
        for skill in loaded_skills.values():
            platform = getattr(skill, "platform", "")
            if platform and str(platform).lower() != "multi_platform":
                platforms.add(self._normalize_platform(platform))
        return sorted(platforms)

    def _platform_aliases(self, platform: str) -> set[str]:
        """Build recognition aliases from registered platform/Skill identity."""
        normalized = self._normalize_platform(platform)
        aliases = {
            normalized,
            normalized.replace("-", " "),
            normalized.replace("_", " "),
        }
        loaded_skills = getattr(self.skill_loader, "list_all", lambda: {})()
        for skill in loaded_skills.values():
            if self._normalize_platform(getattr(skill, "platform", "")) != normalized:
                continue
            name = str(getattr(skill, "name", "") or "").lower()
            if name:
                aliases.update({name, name.replace("-", " "), name.replace("_", " ")})
            for alias in getattr(skill, "platform_aliases", []) or []:
                alias = str(alias).lower().strip()
                if alias:
                    aliases.add(alias)
        return {alias for alias in aliases if alias}

    def _detect_platforms(
        self,
        user_input: str,
        available_tools: Optional[List[ToolDefinition]] = None,
    ) -> List[str]:
        """从当前注册的 Tool/Skill 身份中检测平台，不维护渠道表。"""
        text = (user_input or "").lower()
        mentions = []
        for platform in self._registered_platforms(available_tools or []):
            positions = [
                text.find(alias)
                for alias in self._platform_aliases(platform)
                if text.find(alias) >= 0
            ]
            if positions:
                mentions.append((min(positions), platform))
        return [platform for _position, platform in sorted(mentions)]

    _normalize_platform = staticmethod(normalize_platform)
    
    def _get_platform_tools(
        self, 
        platform: str, 
        available_tools: List[ToolDefinition]
    ) -> List[ToolDefinition]:
        """获取指定平台的所有工具"""
        normalized = self._normalize_platform(platform)
        return [
            t for t in available_tools
            if self._normalize_platform(t.platform) == normalized
        ]
    
    def _filter_by_intent(
        self,
        tools: List[ToolDefinition],
        intent_type: str,
    ) -> List[ToolDefinition]:
        """根据意图类型筛选工具"""
        if not intent_type:
            return tools[:5]  # 限制返回数量，避免过长
        
        # Tool metadata is the routing contract.  In particular, do not add a
        # new intent to a core ``intent -> keyword`` table: a provider Skill or
        # Capability must be able to publish a new intent without changing the
        # shared selector.
        exact = [
            tool for tool in tools
            if intent_type in (getattr(tool, "intent_types", None) or [])
        ]
        if exact:
            return exact[:8]

        # Keep a bounded, metadata-only fallback for older/custom tools that
        # have not published intent_types yet.  The selector never interprets
        # provider-specific intent names; it only compares generic fields that
        # are already part of ToolDefinition.
        intent_tokens = {
            token for token in re.split(r"[^a-z0-9]+", str(intent_type).lower())
            if token and token not in {"the", "a", "an", "to", "for"}
        }
        ranked: list[tuple[int, int, ToolDefinition]] = []
        for index, tool in enumerate(tools):
            metadata = " ".join(
                str(value or "").lower()
                for value in (
                    getattr(tool, "action", ""),
                    getattr(tool, "resource_type", ""),
                    " ".join(getattr(tool, "traits", []) or []),
                    getattr(tool, "name", ""),
                    getattr(tool, "description", ""),
                )
            )
            score = sum(1 for token in intent_tokens if token in metadata)
            if score:
                ranked.append((score, -index, tool))
        if ranked:
            ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return [tool for _score, _index, tool in ranked[:8]]

        # Unknown intents must remain bounded.  The LLM can ask for the
        # missing capability rather than receiving the entire provider tool
        # catalog and hallucinating a route.
        return tools[:5]
    
    def _get_expert_knowledge(
        self, 
        platform: str, 
        intent_type: str
    ) -> str:
        """获取平台专家知识"""
        skill = self._get_skill_by_platform(platform)
        if not skill:
            return ""
        
        knowledge = getattr(skill, "expert_knowledge", {}) or {}
        if not isinstance(knowledge, dict):
            return ""

        # Knowledge keys are Skill-owned.  Prefer an exact key, then select
        # keys whose names overlap the Tool-published intent tokens, and finally
        # use a small deterministic prefix.  No shared selector table is needed
        # when a Skill adds a new knowledge section or workflow intent.
        intent_text = str(intent_type or "").lower()
        intent_tokens = {
            token for token in re.split(r"[^a-z0-9]+", intent_text)
            if token and token not in {"the", "a", "an", "to", "for"}
        }
        keys = list(knowledge.keys())
        if intent_type in knowledge:
            selected_keys = [intent_type]
        else:
            selected_keys = [
                key for key in keys
                if any(token in str(key).lower() for token in intent_tokens)
            ][:3]
            if not selected_keys:
                selected_keys = keys[:2]
        return "\n\n".join(
            f"## {key}\n{knowledge[key]}" for key in selected_keys
        )
    
    def _merge_expert_knowledge(self, tools: List[ToolDefinition]) -> str:
        """合并多个工具的专家知识"""
        platforms = set(t.platform for t in tools)
        knowledge = []
        
        for platform in platforms:
            skill = self._get_skill_by_platform(platform)
            if skill and skill.expert_knowledge:
                # 提取关键专家知识摘要
                for key, content in list(skill.expert_knowledge.items())[:2]:
                    # 截取前 500 字符
                    summary = content[:500] + "..." if len(content) > 500 else content
                    knowledge.append(f"[{platform}] {key}: {summary}")
            elif skill and getattr(skill, "description", None):
                # Channel SKILL.md files currently carry their expert scope in
                # frontmatter rather than separate expert/*.md files.  Keep a
                # compact description available to the LLM instead of silently
                # dropping all Skill context.
                knowledge.append(f"[{platform}] skill_scope: {skill.description[:500]}")
        
        return "\n\n".join(knowledge)

    def _get_skill_by_platform(self, platform: str):
        """Resolve a skill by either its name or its declared platform.

        Channel skills live below ``skills/channels`` and their registry key
        is normally ``meta-marketing-api-expert`` rather than ``meta``.  The
        old direct lookup therefore silently disabled expert knowledge.
        """
        normalized = self._normalize_platform(platform)
        skill = self.skill_loader.get_skill(platform)
        if skill:
            return skill
        loaded_skills = getattr(self.skill_loader, "list_all", lambda: {})()
        for candidate in loaded_skills.values():
            candidate_platform = self._normalize_platform(getattr(candidate, "platform", ""))
            if candidate_platform == normalized:
                return candidate
        return None
    
    def build_tool_prompt(self, selection: ToolSelection) -> str:
        """构建工具列表 prompt（给 LLM 使用）"""
        if not selection.selected_tools:
            return "暂无可用工具"
        
        lines = [f"## 可用工具（平台: {selection.platform}）"]
        
        for i, tool in enumerate(selection.selected_tools, 1):
            lines.append(f"{i}. **{tool.name}** ({tool.risk_level.value})")
            lines.append(f"   描述: {tool.description[:100]}...")
            if tool.input_schema.properties:
                lines.append(f"   参数: {list(tool.input_schema.properties.keys())}")
                enum_fields = {
                    name: spec.get("enum")
                    for name, spec in tool.input_schema.properties.items()
                    if isinstance(spec, dict) and spec.get("enum") is not None
                }
                if enum_fields:
                    lines.append(f"   固定选项: {enum_fields}")
                lookup_fields = {
                    name: (
                        spec.get("lookup_tool")
                        or (
                            spec.get("lookup", {}).get("tool")
                            if isinstance(spec.get("lookup"), dict)
                            else None
                        )
                    )
                    for name, spec in tool.input_schema.properties.items()
                    if isinstance(spec, dict)
                    and (spec.get("lookup_tool") or isinstance(spec.get("lookup"), dict))
                }
                lookup_fields = {
                    name: tool_name for name, tool_name in lookup_fields.items() if tool_name
                }
                if lookup_fields:
                    lines.append(f"   动态选项查询工具: {lookup_fields}")
            if tool.input_schema.required:
                lines.append(f"   必填: {tool.input_schema.required}")
            if tool.input_schema.provider_required:
                lines.append(f"   Provider 必填: {tool.input_schema.provider_required}")
            if tool.input_schema.provider_any_of:
                lines.append(f"   Provider 至少选择一项: {tool.input_schema.provider_any_of}")
            if tool.input_schema.provider_exactly_one_of:
                lines.append(
                    f"   Provider 必须且只能选择一项: "
                    f"{tool.input_schema.provider_exactly_one_of}"
                )
            if tool.input_schema.conditional_rules:
                lines.append(f"   条件依赖: {tool.input_schema.conditional_rules}")
            lines.append("")
        
        if selection.expert_knowledge:
            lines.append("## 专家知识")
            lines.append(selection.expert_knowledge[:1000] + "..." if len(selection.expert_knowledge) > 1000 else selection.expert_knowledge)
        
        return "\n".join(lines)
    
    def optimize_for_llm(
        self,
        user_input: str,
        intent: ParsedIntent,
        all_tools: List[ToolDefinition],
        tenant_id: Optional[str] = None,
    ) -> dict:
        """
        为 LLM 优化工具选择
        
        Returns:
            {
                "selected_tools": [...],
                "tool_prompt": "...",
                "expert_knowledge": "...",
                "context": {...}
            }
        """
        selection = self.select_tools(user_input, intent, all_tools)
        platforms = intent.platforms or self._detect_platforms(user_input, all_tools)
        knowledge = self._query_knowledge(
            user_input, platforms, intent_type=intent.intent_type, tenant_id=tenant_id
        )
        if knowledge:
            selection.expert_knowledge = "\n\n".join(
                part for part in (
                    selection.expert_knowledge,
                    self._format_knowledge(knowledge),
                ) if part
            )[:4000]

        return {
            "selected_tools": selection.selected_tools,
            "tool_count": len(selection.selected_tools),
            "tool_prompt": self.build_tool_prompt(selection),
            "expert_knowledge": selection.expert_knowledge,
            "context": selection.context,
            "platforms": selection.platform,
            "knowledge": knowledge,
        }


# 全局实例
_tool_selector: Optional[DynamicToolSelector] = None


def get_tool_selector() -> DynamicToolSelector:
    """获取全局工具选择器"""
    global _tool_selector
    if _tool_selector is None:
        _tool_selector = DynamicToolSelector()
    return _tool_selector


def select_tools_for_intent(
    user_input: str,
    intent: ParsedIntent,
    all_tools: List[ToolDefinition],
) -> dict:
    """便捷函数：为意图选择工具"""
    return get_tool_selector().optimize_for_llm(user_input, intent, all_tools)

# 扩展的意图类型映射（补充缺失的）
