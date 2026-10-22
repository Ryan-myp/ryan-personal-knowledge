"""Bounded, tenant-aware capability inventory for advertising Agent context."""

from __future__ import annotations

from typing import Any, Mapping


class AdvertisingCapabilityCatalog:
    """Render registered Skills and Tool contracts without implying execution."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def build(self, request: Any, *, max_chars: int = 9_000) -> str:
        application = getattr(self.owner, "platform_application", None)
        skills = self._registered_skills(application, request)
        tools = self._registered_tools(application, request)
        tool_lines, has_live_adapter = self._tool_lines(tools)
        lines = tool_lines + self._skill_lines(skills)
        lines.extend(self._execution_lines(request, has_live_adapter))
        return self._redact_and_bound("\n".join(lines), max_chars)

    def read_account_candidates(
        self, request: Any, *, max_accounts: int = 20,
    ) -> dict[str, list[str]]:
        """Expose a bounded discovery scope, not write selection or credentials."""
        scope = getattr(getattr(request, "principal", None), "account_scope", None)
        available = getattr(self.owner, "_available_accounts_for_request", None)
        registry = getattr(self.owner, "registry", None)
        namespaces = getattr(registry, "list_all_namespaces", None)
        if scope is None or not callable(available) or not callable(namespaces):
            return {}
        candidates: dict[str, list[str]] = {}
        remaining = max(0, int(max_accounts))
        for namespace in sorted(namespaces()):
            if not remaining:
                break
            accounts = list(available(namespace, scope))[:remaining]
            if accounts:
                candidates[str(namespace)] = [str(value) for value in accounts]
                remaining -= len(accounts)
        return candidates

    def _registered_skills(
        self, application: Any, request: Any,
    ) -> dict[str, tuple[str, Any]]:
        skills: dict[str, tuple[str, Any]] = {}
        self._add_from_catalog(
            skills,
            getattr(application, "skills", None),
            "list_skills",
            "scenario",
        )
        self._add_from_catalog(
            skills,
            getattr(self.owner, "skill_loader", None),
            "list_all",
            "installed",
        )
        get_managed = getattr(self.owner, "get_managed_skills", None)
        if callable(get_managed):
            tenant_id = str(getattr(request, "tenant_id", None) or "default")
            self._add_skills(
                skills, get_managed(tenant_id), "tenant-published",
            )
        return skills

    def _registered_tools(self, application: Any, request: Any) -> list[Any]:
        catalog = getattr(application, "tools", None)
        list_tools = getattr(catalog, "list_tools", None)
        tools = list(list_tools()) if callable(list_tools) else []
        allowlist = getattr(request, "tool_allowlist", None)
        if allowlist is None:
            return tools
        allowed = {str(name) for name in allowlist}
        return [
            tool for tool in tools
            if self._field(tool, "name", "") in allowed
        ]

    @classmethod
    def _add_from_catalog(
        cls,
        destination: dict[str, tuple[str, Any]],
        catalog: Any,
        method_name: str,
        source: str,
    ) -> None:
        list_items = getattr(catalog, method_name, None)
        if callable(list_items):
            cls._add_skills(destination, list_items(), source)

    @classmethod
    def _skill_lines(
        cls, skills: dict[str, tuple[str, Any]],
    ) -> list[str]:
        lines = [
            "Skills (advisory guidance only; they do not execute operations):",
        ]
        for name, (source, skill) in sorted(skills.items()):
            description = cls._single_line(
                cls._field(skill, "description", ""), limit=64,
            )
            suffix = f": {description}" if description else ""
            lines.append(f"- {name} [{source}]{suffix}")
        if not skills:
            lines.append("- none registered")
        return lines

    @classmethod
    def _tool_lines(cls, tools: list[Any]) -> tuple[list[str], bool]:
        groups: dict[tuple[str, str], set[tuple[str, str]]] = {}
        fallback_tools: set[str] = set()
        platform_tools: set[str] = set()
        has_live_adapter = False
        for tool in tools:
            state, declared_live = cls._tool_state(tool)
            has_live_adapter = has_live_adapter or declared_live
            kind, support = cls._compact_tool_state(state)
            namespace = cls._single_line(
                cls._field(tool, "namespace", ""), limit=100,
            )
            resource = cls._single_line(
                cls._field(tool, "resource_type", ""), limit=100,
            )
            action = cls._single_line(
                cls._field(tool, "action", ""), limit=80,
            )
            name = cls._single_line(
                cls._field(tool, "name", ""), limit=160,
            )
            if namespace == "agent-platform" and name:
                description = cls._single_line(
                    cls._field(tool, "description", ""), limit=180,
                )
                suffix = f": {description}" if description else ""
                platform_tools.add(
                    f"{name}{suffix} [{kind},{support}]"
                )
                continue
            if namespace and resource and action:
                groups.setdefault((namespace, resource), set()).add(
                    (action, f"{kind},{support}")
                )
                continue
            if name:
                fallback_tools.add(f"{name} [{kind},{support}]")
        lines = [
            "Tools (registered structured execution contracts):",
            "Action markers: R/W=read/write; L=live adapter declared only; "
            "D=dry-run only; ?=live support undeclared.",
        ]
        lines.extend(
            f"- agent-platform Tool: {name}"
            for name in sorted(platform_tools)
        )
        for (namespace, resource), action_states in sorted(groups.items()):
            actions = ", ".join(
                f"{action}({state})"
                for action, state in sorted(action_states)
            )
            lines.append(f"- {namespace}: {resource} -> {actions}")
        lines.extend(f"- {name}" for name in sorted(fallback_tools))
        if not groups and not fallback_tools:
            lines.append("- none registered")
        return lines, has_live_adapter

    @classmethod
    def _tool_state(cls, tool: Any) -> tuple[str, bool]:
        live_support = cls._field(tool, "live_support")
        effect = cls._field(tool, "effect_class")
        effect = str(getattr(effect, "value", effect) or "").casefold()
        is_write = bool(cls._field(tool, "is_write_tool", False)) or (
            effect in {"write", "external_write", "internal_write"}
        )
        kind = "write" if is_write else "read"
        if live_support is True:
            return f"{kind}; live adapter declared", True
        if live_support is False:
            return f"{kind}; dry-run only", False
        return f"{kind}; live support undeclared", False

    @staticmethod
    def _compact_tool_state(state: str) -> tuple[str, str]:
        kind, _, support = state.partition(";")
        marker = {
            " live adapter declared": "L",
            " dry-run only": "D",
            " live support undeclared": "?",
        }.get(support, "?")
        return ("W" if kind.strip() == "write" else "R"), marker

    def _execution_lines(
        self, request: Any, has_live_adapter: bool,
    ) -> list[str]:
        mode = (
            getattr(request, "execution_mode", None)
            or getattr(self.owner, "execution_mode", None)
            or "dry_run"
        )
        lines = [
            f"Current execution mode: {self._single_line(mode, limit=40)}.",
            "A live adapter declaration does not verify account access or live API success.",
        ]
        if str(mode).casefold() == "dry_run":
            lines.append("In dry_run, write operations are previews only.")
        else:
            lines.append(
                "Live operations remain subject to application permissions, "
                "account scope, confirmation and idempotency."
            )
        if has_live_adapter:
            lines.append(
                "The catalog reports registered contracts, not provider health "
                "or account connectivity."
            )
        return lines

    def _redact_and_bound(self, text: str, max_chars: int) -> str:
        redactor = getattr(self.owner, "_redact_for_persistence", None)
        if callable(redactor):
            text = str(redactor(text) or "")
        return self._bound_catalog(text, max_chars)

    @classmethod
    def _add_skills(
        cls,
        destination: dict[str, tuple[str, Any]],
        values: Any,
        source: str,
    ) -> None:
        if isinstance(values, Mapping):
            values = values.values()
        for skill in values or ():
            name = cls._single_line(cls._field(skill, "name", ""), limit=100)
            if name:
                destination.setdefault(name, (source, skill))

    @staticmethod
    def _field(value: Any, name: str, default: Any = "") -> Any:
        if isinstance(value, Mapping):
            return value.get(name, default)
        return getattr(value, name, default)

    @staticmethod
    def _single_line(value: Any, *, limit: int) -> str:
        return " ".join(str(value or "").split())[:max(0, int(limit))]

    @staticmethod
    def _bound_catalog(text: str, max_chars: int) -> str:
        limit = max(0, int(max_chars))
        if len(text) <= limit:
            return text
        marker = "[catalog truncated]"
        if limit <= len(marker):
            return text[:limit]
        lines = text.splitlines()
        included: list[str] = []
        for index, line in enumerate(lines):
            if len("\n".join((*included, line, marker))) > limit:
                omitted = len(lines) - index
                marker = f"[catalog truncated; {omitted} lines omitted]"
                while included and len("\n".join((*included, marker))) > limit:
                    included.pop()
                    omitted += 1
                    marker = f"[catalog truncated; {omitted} lines omitted]"
                return "\n".join((*included, marker))[:limit]
            included.append(line)
        return "\n".join(included)[:limit]


__all__ = ["AdvertisingCapabilityCatalog"]
