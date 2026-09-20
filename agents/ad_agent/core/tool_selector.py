"""
core/tool_selector.py - 动态工具选择器

核心功能：
1. 根据用户意图 + 目标 namespace，动态选择相关工具
2. 注入 namespace/Skill 专家知识作为上下文
3. 优化 LLM 的 tool 列表，避免信息过载
"""

import re
import logging
import threading
from typing import Any, List, Dict, Optional, Set

from .context import ContextQuery
from .interfaces import ToolDefinition, ParsedIntent, ToolContext, KnowledgeSource
from .policy import RuntimePolicy, apply_policies, policy_metadata
from .namespace import normalize_namespace
from .tool_selection import (
    PromptRenderer,
    ToolSelection,
    ToolSelector,
)

logger = logging.getLogger(__name__)


def _safe_search(pattern: str, text: str) -> bool:
    """Evaluate a Skill-declared trigger pattern without breaking a request."""
    try:
        return re.search(pattern, text, re.IGNORECASE) is not None
    except re.error:
        logger.warning("Ignoring invalid Skill trigger pattern")
        return False


class DynamicToolSelector:
    """
    动态工具选择器
    
    工作原理：
    1. 根据用户意图识别目标 namespace
    2. 从 Skill Registry 获取该 namespace 的所有工具
    3. 根据意图类型筛选相关工具（如查询→只选报表类工具）
    4. 注入 namespace/Skill 专家知识作为上下文
    5. 返回精简的工具列表给 LLM
    """
    
    def __init__(
        self,
        skill_loader,
        knowledge_source: Optional[KnowledgeSource] = None,
        policies: Optional[list[RuntimePolicy]] = None,
    ):
        self.skill_loader = skill_loader
        self.knowledge_source = knowledge_source
        self.policies: list[RuntimePolicy] = list(policies or [])
        self._selector = ToolSelector(policies=self.policies)
        self._prompt_renderer = PromptRenderer()
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
        """Replace the policy set used for namespace filtering and context."""
        self.policies = list(policies or [])
        self._selector.set_policies(self.policies)

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
        selection = self._selector.select(
            user_input=user_input,
            intent=intent,
            available_tools=available_tools,
        )
        selection.expert_knowledge = self._merge_expert_knowledge(
            selection.selected_tools
        )
        return selection

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
        intent here: it only narrows by detected namespace and keeps the first
        few registered tools, while the authoritative post-parse route still
        comes from ``IntentRouter``.
        """
        namespaces = self._detect_namespaces(user_input, available_tools)
        probe_intent = ParsedIntent(
            intent_type=intent_type or "",
            raw_input=user_input,
            namespaces=namespaces,
        )
        selection = self.select_tools(user_input, probe_intent, available_tools)
        knowledge = self._query_knowledge(
            user_input, namespaces, intent_type=intent_type, tenant_id=tenant_id
        )
        if knowledge:
            selection.expert_knowledge = self._format_knowledge(knowledge)
        triggered_context = self._triggered_skill_context(user_input)
        if triggered_context:
            selection.expert_knowledge = "\n\n".join(
                part for part in (selection.expert_knowledge, triggered_context) if part
            )[:6000]
        managed_context = self._managed_skill_context(
            user_input,
            tenant_id=tenant_id,
            skill_refs=self._associated_skill_refs(selection.selected_tools),
        )
        if managed_context:
            selection.expert_knowledge = "\n\n".join(
                part for part in (selection.expert_knowledge, managed_context) if part
            )[:6000]
        return {
            "tool_prompt": self.build_tool_prompt(selection),
            "expert_knowledge": selection.expert_knowledge,
            "namespaces": list(selection.namespaces),
            "knowledge": knowledge,
        }

    @staticmethod
    def _associated_skill_refs(tools: List[ToolDefinition]) -> set[str]:
        """Return explicit Skill bindings without inferring names from Tools."""
        refs: set[str] = set()
        for tool in tools:
            refs.update(
                str(item).strip()
                for item in (getattr(tool, "skill_refs", None) or [])
                if str(item).strip()
            )
        return refs

    def _triggered_skill_context(
        self, user_input: str, max_chars: int = 3600
    ) -> str:
        """Load advisory context from Skills whose declared triggers match."""
        text = str(user_input or "").casefold()
        sections: list[str] = []
        for skill in sorted(
            self.skill_loader.list_all().values(),
            key=lambda item: str(getattr(item, "name", "")),
        ):
            matched = False
            for trigger in getattr(skill, "triggers", []) or []:
                keywords = [str(item).casefold() for item in getattr(trigger, "keywords", []) or []]
                patterns = [str(item) for item in getattr(trigger, "patterns", []) or []]
                if any(keyword and keyword in text for keyword in keywords):
                    matched = True
                if any(pattern and _safe_search(pattern, text) for pattern in patterns):
                    matched = True
                if matched:
                    break
            if not matched:
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
                f"[skill guidance: {getattr(skill, 'name', '')}]\n"
                "以下内容仅用于理解和澄清，不会新增 Tool、权限或账户范围：\n"
                + excerpt[:max_chars]
            )
        return "\n\n".join(sections)[:max_chars]

    def _managed_skill_context(
        self,
        user_input: str,
        max_chars: int = 6000,
        tenant_id: str = "default",
        skill_refs: Optional[set[str]] = None,
    ) -> str:
        """Build bounded, clearly non-executable context from managed Skills."""
        tenant = str(tenant_id or "default")
        with self._context_skills_lock:
            context_skills = dict(self._context_skills.get(tenant, {}))
        if not context_skills:
            return ""
        sections: list[str] = []
        requested_refs = {
            str(item).strip() for item in (skill_refs or set()) if str(item).strip()
        }
        for name, skill in sorted(context_skills.items()):
            # An explicit binding narrows advisory context. With no binding
            # the tenant-wide context remains available; either path cannot
            # add Tools, permissions, credentials or account scope.
            if requested_refs and name not in requested_refs and str(
                getattr(skill, "version", "") or ""
            ) not in requested_refs:
                continue
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
        namespaces: List[str],
        *,
        intent_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """Query advisory knowledge without changing executable routing."""
        if self.knowledge_source is None:
            return []
        try:
            request = ContextQuery(
                text=user_input,
                namespaces=namespaces,
                intent_type=intent_type or "",
                tenant_id=str(tenant_id or "default"),
                limit=4,
                max_excerpt_chars=1000,
            )
            query_context = getattr(self.knowledge_source, "query_context", None)
            if callable(query_context):
                documents = query_context(request)
            else:
                # Compatibility for older third-party context sources. This is an
                # explicit legacy method fallback, not signature inspection.
                documents = self.knowledge_source.query(
                    request.text,
                    namespaces=request.namespaces,
                    intent_type=request.intent_type or None,
                    limit=request.limit,
                    max_excerpt_chars=request.max_excerpt_chars,
                )
            result = []
            for document in documents:
                serializer = getattr(document, "to_context_dict", None)
                if not callable(serializer):
                    serializer = getattr(document, "to_dict", None)
                if callable(serializer):
                    value = serializer()
                    if isinstance(value, dict):
                        result.append(value)
            return result
        except Exception as exc:
            logger.debug("知识库查询失败，继续无知识上下文: %s", exc)
            return []

    @staticmethod
    def _format_knowledge(knowledge: list[dict], max_chars: int = 4000) -> str:
        return "\n\n".join(
            f"[{item['namespace']}] {item['topic']} (source={item['source']}, "
            f"version={item['version']}, confidence={item['confidence']}):\n"
            f"{item['excerpt']}"
            for item in knowledge
        )[:max_chars]
    
    def _registered_namespaces(self, available_tools: List[ToolDefinition]) -> List[str]:
        """Return namespaces published by the current Tool/Skill registry."""
        namespaces = set(self._selector.registered_namespaces(available_tools))
        loaded_skills = getattr(self.skill_loader, "list_all", lambda: {})()
        for skill in loaded_skills.values():
            namespace = getattr(skill, "namespace", "")
            if namespace:
                namespaces.add(self._normalize_namespace(namespace))
        return sorted(namespaces)

    def _namespace_aliases(self, namespace: str) -> set[str]:
        """Build recognition aliases from registered namespace/Skill identity."""
        normalized = self._normalize_namespace(namespace)
        aliases = {
            normalized,
            normalized.replace("-", " "),
            normalized.replace("_", " "),
        }
        loaded_skills = getattr(self.skill_loader, "list_all", lambda: {})()
        for skill in loaded_skills.values():
            if self._normalize_namespace(getattr(skill, "namespace", "")) != normalized:
                continue
            name = str(getattr(skill, "name", "") or "").lower()
            if name:
                aliases.update({name, name.replace("-", " "), name.replace("_", " ")})
            for alias in getattr(skill, "namespace_aliases", []) or []:
                alias = str(alias).lower().strip()
                if alias:
                    aliases.add(alias)
        return {alias for alias in aliases if alias}

    def _detect_namespaces(
        self,
        user_input: str,
        available_tools: Optional[List[ToolDefinition]] = None,
    ) -> List[str]:
        """从当前注册的 Tool/Skill 身份中检测 namespace，不维护固定目录。"""
        text = (user_input or "").lower()
        mentions = []
        for namespace in self._registered_namespaces(available_tools or []):
            positions = [
                text.find(alias)
                for alias in self._namespace_aliases(namespace)
                if text.find(alias) >= 0
            ]
            if positions:
                mentions.append((min(positions), namespace))
        return [namespace for _position, namespace in sorted(mentions)]

    _normalize_namespace = staticmethod(normalize_namespace)

    def _get_namespace_tools(
        self,
        namespace: str,
        available_tools: List[ToolDefinition]
    ) -> List[ToolDefinition]:
        """获取指定 namespace 的所有工具"""
        normalized = self._normalize_namespace(namespace)
        return [
            t for t in available_tools
            if self._normalize_namespace(t.namespace) == normalized
        ]

    def _filter_by_intent(
        self,
        tools: List[ToolDefinition],
        intent_type: str,
    ) -> List[ToolDefinition]:
        """根据意图类型筛选工具"""
        return self._selector.filter_by_intent(tools, intent_type)
    
    def _get_expert_knowledge(
        self,
        namespace: str,
        intent_type: str
    ) -> str:
        """获取 namespace 关联的专家知识"""
        skills = self._get_skills_by_namespace(namespace)
        if not skills:
            return ""
        knowledge: dict[str, str] = {}
        for skill in skills:
            skill_knowledge = getattr(skill, "expert_knowledge", {}) or {}
            if isinstance(skill_knowledge, dict):
                knowledge.update(skill_knowledge)
        if not knowledge:
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
        namespaces = sorted(set(t.namespace for t in tools))
        knowledge = []
        
        for namespace in namespaces:
            for skill in self._get_skills_by_namespace(namespace):
                skill_knowledge = getattr(skill, "expert_knowledge", {}) or {}
                if isinstance(skill_knowledge, dict):
                    for key, content in list(skill_knowledge.items())[:2]:
                        summary = content[:500] + "..." if len(content) > 500 else content
                        knowledge.append(f"[{namespace}] {key}: {summary}")
                # Namespace Skill markdown is advisory context, not an executable
                # registry. Keep a bounded excerpt in the model context so
                # channel-specific hierarchy, parameter dependencies and
                # failure semantics actually guide intent parsing. The
                # authoritative executable plan still comes from Tool metadata
                # and IntentRouter after parsing.
                raw_markdown = str(getattr(skill, "raw_markdown", "") or "")
                if raw_markdown:
                    body = re.sub(
                        r"\A---\s*.*?\s*---\s*",
                        "",
                        raw_markdown,
                        count=1,
                        flags=re.DOTALL,
                    ).strip()
                    if body:
                        knowledge.append(
                            f"[{namespace}] channel_skill_guidance:\n{body[:1800]}"
                        )
                elif getattr(skill, "description", None):
                    knowledge.append(f"[{namespace}] skill_scope: {skill.description[:500]}")
        
        return "\n\n".join(knowledge)

    def _get_skills_by_namespace(self, namespace: str) -> list:
        """Return every active Skill declaring the requested namespace."""
        normalized = self._normalize_namespace(namespace)
        list_all = getattr(self.skill_loader, "list_all", None)
        skills = list_all() if callable(list_all) else getattr(self.skill_loader, "_skills", {})
        if isinstance(skills, dict):
            skills = skills.values()
        return [
            skill for skill in skills
            if self._normalize_namespace(getattr(skill, "namespace", "")) == normalized
        ]
    
    def build_tool_prompt(self, selection: ToolSelection) -> str:
        """构建工具列表 prompt（给 LLM 使用）"""
        return self._prompt_renderer.render(selection)
    
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
        namespaces = intent.namespaces or self._detect_namespaces(user_input, all_tools)
        knowledge = self._query_knowledge(
            user_input, namespaces, intent_type=intent.intent_type, tenant_id=tenant_id
        )
        if knowledge:
            selection.expert_knowledge = "\n\n".join(
                part for part in (
                    selection.expert_knowledge,
                    self._format_knowledge(knowledge),
                ) if part
            )[:4000]
        managed_context = self._managed_skill_context(
            user_input,
            tenant_id=str(tenant_id or "default"),
            skill_refs=self._associated_skill_refs(selection.selected_tools),
        )
        if managed_context:
            selection.expert_knowledge = "\n\n".join(
                part for part in (selection.expert_knowledge, managed_context) if part
            )[:6000]

        return {
            "selected_tools": selection.selected_tools,
            "tool_count": len(selection.selected_tools),
            "tool_prompt": self.build_tool_prompt(selection),
            "expert_knowledge": selection.expert_knowledge,
            "context": selection.context,
            "namespaces": list(selection.namespaces),
            "knowledge": knowledge,
        }


# 扩展的意图类型映射（补充缺失的）
