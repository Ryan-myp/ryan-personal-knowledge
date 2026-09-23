"""Template lookup and application for advertising creation."""

from __future__ import annotations

import copy
from typing import Any, Mapping, Optional

from ..core.interfaces import ParsedIntent
from ..creation_templates import (
    CreationTemplateError,
    creation_template_manager_for_runtime,
)


class AdCreationTemplateServicesMixin:
    def _creation_template_manager_for_request(
        self, account_scope: Any = None,
    ) -> Any:
        return creation_template_manager_for_runtime(
            self, account_scope=account_scope,
        )

    def list_creation_templates(
        self,
        *,
        provider: Optional[str] = None,
        account_id: Optional[str] = None,
        account_scope: Any = None,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        blueprint_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return templates visible to one principal and optional account."""
        try:
            return self._creation_template_manager_for_request(
                account_scope,
            ).list(
                tenant_id,
                user_id,
                provider=provider,
                blueprint_id=blueprint_id,
                status="active",
                account_id=account_id,
                account_scope=account_scope,
                limit=100,
            )
        except CreationTemplateError:
            return []

    def apply_creation_template_to_intent(
        self,
        intent: ParsedIntent,
        template_id: str,
        *,
        account_id: Optional[str] = None,
        account_scope: Any = None,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> ParsedIntent:
        """Apply a data-only template to a draft, never to a Tool executor."""
        manager = self._creation_template_manager_for_request(account_scope)
        template = manager.get(
            tenant_id,
            user_id,
            str(template_id),
            account_id=account_id,
            account_scope=account_scope,
        )
        if not template or template.get("status") != "active":
            raise CreationTemplateError("模板不存在、已停用或不在当前账户授权范围内")
        provider = self._canonical_platform(str(template.get("provider") or ""))
        if not provider:
            raise CreationTemplateError("模板没有声明有效的广告平台")
        namespaces = [
            self._canonical_platform(item)
            for item in (getattr(intent, "namespaces", []) or [])
        ]
        if namespaces and provider not in namespaces:
            raise CreationTemplateError("模板平台与当前创建请求的平台不一致")
        namespaces = [provider] if not namespaces else namespaces
        scoped = {
            str(namespace): dict(values or {})
            for namespace, values in (
                getattr(intent, "scoped_parameters", {}) or {}
            ).items()
            if isinstance(values, Mapping)
        }
        existing = dict(scoped.get(provider, {}) or {})
        template_values = template.get("values")
        if not isinstance(template_values, Mapping):
            raise CreationTemplateError("模板参数不是对象")
        normalized_values = copy.deepcopy(dict(template_values))
        blueprint = self.creation_blueprints.get(
            str(template.get("blueprint_id") or ""),
            str(template.get("blueprint_version") or "") or None,
        )
        for field in getattr(blueprint, "fields", ()) if blueprint else ():
            if not isinstance(field, Mapping):
                continue
            path = str(field.get("path") or "")
            if path not in template_values:
                continue
            tool_ref = str(field.get("tool_ref") or "")
            if "." not in tool_ref:
                continue
            tool_name, schema_path = tool_ref.split(".", 1)
            parts = [item for item in schema_path.split(".") if item]
            target = normalized_values
            for part in parts[:-1]:
                child = target.get(part)
                if not isinstance(child, Mapping):
                    child = {}
                    target[part] = child
                target = child
            if parts:
                target[parts[-1]] = copy.deepcopy(template_values[path])
            scoped_tool = normalized_values.setdefault(tool_name, {})
            target = scoped_tool
            for part in parts[:-1]:
                child = target.get(part)
                if not isinstance(child, Mapping):
                    child = {}
                    target[part] = child
                target = child
            if parts:
                target[parts[-1]] = copy.deepcopy(template_values[path])
        scoped[provider] = {**normalized_values, **existing}
        metadata = dict(getattr(intent, "metadata", {}) or {})
        metadata.update({
            "creation_template_id": str(template.get("template_id") or template_id),
            "creation_template_source": str(template.get("source") or "user"),
            "creation_blueprint_id": str(template.get("blueprint_id") or ""),
            "creation_blueprint_version": str(template.get("blueprint_version") or ""),
            "creation_template_account_id": str(
                template.get("account_id") or account_id or ""
            ),
        })
        return ParsedIntent(
            "create_campaign",
            getattr(intent, "raw_input", ""),
            namespaces,
            attributes=dict(getattr(intent, "attributes", {}) or {}),
            parameters=dict(getattr(intent, "parameters", {}) or {}),
            scoped_parameters=scoped,
            metadata=metadata,
        )


__all__ = ["AdCreationTemplateServicesMixin"]
