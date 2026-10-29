"""Run-local, bounded expansion of registered Tool schemas.

Only a trusted discovery executor can add definitions. Neither model context
updates nor historical messages are authority to load or execute a Tool.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
import threading
from typing import Any, Callable, Mapping, Sequence

from .core.security import redact_sensitive_text
from .core.namespace import normalize_namespace
from .core.tool_selection import _relevance_score, _terms
from .runtime_kernel import TurnRequest


DISCOVERY_TRAIT = "runtime_tool_discovery"
DISCOVERY_GUIDANCE = (
    "当前附带的 Tool 是起始选择，不代表系统全部能力。需要的动作未加载时，先调用带 "
    "runtime_tool_discovery 标记的工具，用下一步的动作、资源类型和 namespace 搜索本地注册目录。"
    "搜索成功后对应 schema 会出现在下一次模型请求中，继续使用已获得的真实 ID 完成原请求，"
    "不要让用户重复提供已有信息。查父级得到下层级 ID 不等于完成下层级明细查询。"
    "不要仅因当前列表没有某个 Tool 就声称系统没有能力或没有权限。"
    "发现只加载能力，不执行业务动作，也不授予权限；只调用当前附带的 schema。"
    "加载窗口有限，新找到的工具会替换较早加载的工具；后续仍需要时可再次搜索加载。"
    "没有匹配结果可改用更具体的资源名或同义表达搜索；区分未找到工具、权限拒绝和上游失败。"
)


def tool_value(tool: Any, key: str, default: Any = "") -> Any:
    return tool.get(key, default) if isinstance(tool, Mapping) else getattr(tool, key, default)


def is_discovery_tool(tool: Any) -> bool:
    return DISCOVERY_TRAIT in (tool_value(tool, "traits", ()) or ())


def _resource(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _matches(tool: Any, namespace: str, resource_type: str, effect: str) -> bool:
    if is_discovery_tool(tool):
        return False
    if namespace and (
        normalize_namespace(tool_value(tool, "namespace")) != normalize_namespace(namespace)
    ):
        return False
    if resource_type and (
        _resource(str(tool_value(tool, "resource_type"))) != _resource(resource_type)
    ):
        return False
    actual = tool_value(tool, "effect_class", "")
    actual = str(getattr(actual, "value", actual))
    effects = {"read", "none"} if effect == "read" else {
        "write", "external_write", "internal_write",
    }
    return actual in effects


@dataclass(frozen=True)
class LoadedCapability:
    contract_hash: Any
    permitted: Callable[[Any], bool]
    namespace: str
    resource_type: str
    effect: str

    def valid(self, tool: Any) -> bool:
        return (
            self.contract_hash == tool_value(tool, "contract_hash")
            and _matches(tool, self.namespace, self.resource_type, self.effect)
            and self.permitted(tool)
        )


@dataclass
class RunToolDiscovery:
    request: TurnRequest
    catalog: Any
    max_tools: int
    max_searches: int = 6
    max_loaded: int = 8
    _loaded: dict[str, LoadedCapability] = field(default_factory=dict)
    _searches: int = 0
    _closed: bool = False
    _lock: Any = field(default_factory=threading.RLock)

    def _allowed(self, tool: Any) -> bool:
        return (
            self.request.tool_allowlist is None
            or tool_value(tool, "name") in self.request.tool_allowlist
        )

    def _prune(self, tools: Sequence[Any]) -> dict[str, Any]:
        available = {str(tool_value(t, "name")): t for t in tools if self._allowed(t)}
        self._loaded = {
            name: record for name, record in self._loaded.items()
            if name in available and record.valid(available[name])
        }
        return available

    def search(
        self, query: str, *, namespace: str = "", resource_type: str = "",
        effect: str = "read", limit: int = 4,
        permitted: Callable[[Any], bool],
    ) -> dict[str, Any]:
        with self._lock:
            if self._closed or self._searches >= self.max_searches:
                return {"status": "discovery_limit", "tools": [], "message": "本次工具查找次数已达上限"}
            self._searches += 1
            available = self._prune(self.catalog.list_tools())
            candidates = [tool for tool in available.values()
                          if permitted(tool)
                          and _matches(tool, namespace, resource_type, effect)]
            exact = [tool for tool in candidates
                     if query.casefold() == str(tool_value(tool, "name")).casefold()]
            candidates = exact or candidates
            # Generic verbs alone must not match every unrelated resource.
            terms = _terms(query) - _terms("get list read search query find 查询 获取 列出 搜索 详情")
            scored = [(1000 if query.casefold() == str(tool_value(t, "name")).casefold()
                       else _relevance_score(terms, t) if terms
                       else int(bool(namespace or resource_type)), t) for t in candidates]
            ranked = [tool for score, tool in sorted(
                scored, key=lambda pair: (-pair[0], str(tool_value(pair[1], "name"))),
            ) if score > 0]
            capacity = min(self.max_loaded, max(0, self.max_tools - 1))
            matches = []
            for tool in ranked[:max(0, min(limit, 4, capacity))]:
                name = str(tool_value(tool, "name"))
                # Refresh recency, then retire the oldest schema if necessary.
                self._loaded.pop(name, None)
                if len(self._loaded) >= capacity:
                    self._loaded.pop(next(iter(self._loaded)))
                self._loaded[name] = LoadedCapability(
                    tool_value(tool, "contract_hash"), permitted, namespace, resource_type, effect,
                )
                matches.append({
                    "name": name, "namespace": tool_value(tool, "namespace"),
                    "resource_type": tool_value(tool, "resource_type"),
                    "action": tool_value(tool, "action"),
                    "description": redact_sensitive_text(
                        str(tool_value(tool, "description")),
                    )[:500],
                })
            status = "loaded" if matches else "capacity_limit" if ranked else "no_matching_tool"
            return {
                "status": status, "tools": matches,
                "message": ("已加载；下一步使用提供的 Tool schema 继续执行原请求" if matches
                            else "未加载新工具；可缩小查询范围或说明具体阻塞，不要声称已执行业务操作"),
                "searches_remaining": self.max_searches - self._searches,
            }

    def select(self, selected: Sequence[Any], catalog: Sequence[Any]) -> list[Any]:
        with self._lock:
            available = self._prune(catalog)
            discoveries = [tool for tool in available.values() if is_discovery_tool(tool)]
            loaded = [available[name] for name in reversed(self._loaded)]
            combined = {str(tool_value(t, "name")): t for t in (*loaded, *selected)}
            slots = max(0, self.max_tools - len(discoveries))
            return [*list(combined.values())[:slots], *discoveries][:self.max_tools]

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._loaded.clear()


active_tool_discovery: ContextVar[RunToolDiscovery | None] = ContextVar(
    "active_tool_discovery", default=None,
)
