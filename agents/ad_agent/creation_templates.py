"""Management facade for user-owned campaign creation presets.

Templates are data-only snapshots of values accepted by a registered
creation Blueprint. They never contain code, provider clients, credentials,
or a shortcut around Runtime policy gates.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from .persistence.errors import PersistenceConflictError
from .persistence.models import CreationTemplateRecord


class CreationTemplateError(ValueError):
    """Raised when a template payload is invalid or no longer compatible."""


_SCOPE_TYPES = {"general", "account", "region"}
_STATUSES = {"active", "inactive", "archived"}
_MAX_VALUES_BYTES = 120_000
_FORBIDDEN_KEY = re.compile(
    r"(?:access[_-]?token|refresh[_-]?token|client[_-]?(?:id|secret)|"
    r"app[_-]?secret|developer[_-]?token|private[_-]?key|authorization|"
    r"credentials?|partner[_-]?id|perter[_-]?id|bc[_-]?id|mcc|password|"
    r"script|command|entrypoint|mcp)",
    re.IGNORECASE,
)


def _text(value: Any, field: str, maximum: int, *, required: bool = False) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise CreationTemplateError(f"{field} 不能为空")
    if len(result) > maximum:
        raise CreationTemplateError(f"{field} 超过 {maximum} 个字符")
    if "\x00" in result:
        raise CreationTemplateError(f"{field} 不能包含 NUL")
    return result


def _tags(value: Any) -> list[str]:
    if value is None:
        return []
    values = value.split(",") if isinstance(value, str) else value
    if not isinstance(values, (list, tuple, set)):
        raise CreationTemplateError("tags 必须是字符串数组")
    result = [_text(item, "tags", 64) for item in values]
    result = list(dict.fromkeys(item for item in result if item))
    if len(result) > 20:
        raise CreationTemplateError("tags 最多 20 个")
    return result


def _safe_json(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        raise CreationTemplateError("模板参数嵌套层级过深")
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and (value != value or abs(value) == float("inf")):
            raise CreationTemplateError("模板参数不能包含无效数字")
        return value
    if isinstance(value, list):
        if len(value) > 200:
            raise CreationTemplateError("单个模板参数列表最多 200 项")
        return [_safe_json(item, depth + 1) for item in value]
    if isinstance(value, Mapping):
        if len(value) > 100:
            raise CreationTemplateError("单个模板参数对象最多 100 个字段")
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = _text(key, "模板参数字段", 160, required=True)
            if _FORBIDDEN_KEY.search(name):
                raise CreationTemplateError("模板不能保存凭证或可执行配置")
            result[name] = _safe_json(item, depth + 1)
        return result
    raise CreationTemplateError("模板参数只能是 JSON 数据")


class CreationTemplateManager:
    """CRUD and compatibility checks for one authenticated principal."""

    def __init__(self, store: Any, blueprint_getter: Callable[[str, Optional[str]], Optional[dict]]):
        self.store = store
        self.blueprint_getter = blueprint_getter

    @staticmethod
    def _public(record: CreationTemplateRecord) -> dict[str, Any]:
        value = record.to_dict()
        fields = value.get("values") if isinstance(value.get("values"), dict) else {}
        value["covered_fields"] = len(fields)
        value["scope_label"] = {
            "general": "个人通用",
            "account": "指定账户",
            "region": "指定地区",
        }.get(record.scope_type, record.scope_type)
        value["is_usable"] = record.status == "active"
        return value

    def _blueprint(self, blueprint_id: str, version: Optional[str] = None) -> dict[str, Any]:
        result = self.blueprint_getter(str(blueprint_id), version or None)
        if not isinstance(result, Mapping):
            raise CreationTemplateError("创建蓝图不存在或版本已不可用")
        return dict(result)

    def _values(self, blueprint: Mapping[str, Any], value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise CreationTemplateError("values 必须是对象")
        allowed = {
            str(field.get("path"))
            for field in (blueprint.get("fields") or [])
            if isinstance(field, Mapping) and field.get("path")
        }
        unknown = sorted(set(str(key) for key in value) - allowed)
        if unknown:
            raise CreationTemplateError(f"模板包含当前蓝图不支持的字段：{', '.join(unknown[:5])}")
        result = _safe_json(dict(value))
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > _MAX_VALUES_BYTES:
            raise CreationTemplateError("模板参数总量过大")
        return result

    def _payload(
        self, payload: Mapping[str, Any], *, existing: Optional[CreationTemplateRecord] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not isinstance(payload, Mapping):
            raise CreationTemplateError("模板必须是对象")
        blueprint_id = str(payload.get("blueprint_id") or (existing.blueprint_id if existing else "")).strip()
        blueprint_version = str(payload.get("blueprint_version") or (existing.blueprint_version if existing else "")).strip() or None
        if not blueprint_id:
            raise CreationTemplateError("blueprint_id 不能为空")
        blueprint = self._blueprint(blueprint_id, blueprint_version)
        actual_version = str(blueprint.get("version") or blueprint_version or "")
        if blueprint_version and actual_version != blueprint_version:
            raise CreationTemplateError("模板引用的蓝图版本不可用，请重新从向导保存")
        provider = str(payload.get("provider") or (existing.provider if existing else "")).strip()
        ad_format = str(payload.get("ad_format") or (existing.ad_format if existing else "")).strip()
        if provider and provider != str(blueprint.get("provider") or ""):
            raise CreationTemplateError("模板渠道与创建蓝图不一致")
        if ad_format and ad_format != str(blueprint.get("ad_format") or ""):
            raise CreationTemplateError("模板广告类型与创建蓝图不一致")
        scope_type = str(payload.get("scope_type") or (existing.scope_type if existing else "general")).strip().lower()
        if scope_type not in _SCOPE_TYPES:
            raise CreationTemplateError("scope_type 必须是 general、account 或 region")
        account_id = _text(payload.get("account_id", existing.account_id if existing else ""), "account_id", 200)
        region = _text(payload.get("region", existing.region if existing else ""), "region", 120)
        if scope_type == "account" and not account_id:
            raise CreationTemplateError("指定账户模板必须填写 account_id")
        if scope_type == "region" and not region:
            raise CreationTemplateError("指定地区模板必须填写 region")
        status = str(payload.get("status") or (existing.status if existing else "active")).strip().lower()
        if status not in _STATUSES:
            raise CreationTemplateError("模板状态不合法")
        values = self._values(blueprint, payload.get("values", existing.values if existing else {}))
        is_default = bool(payload.get("is_default", existing.is_default if existing else False))
        if status != "active":
            is_default = False
        return {
            "name": _text(payload.get("name", existing.name if existing else ""), "name", 120, required=True),
            "description": _text(payload.get("description", existing.description if existing else ""), "description", 500),
            "provider": str(blueprint.get("provider") or provider),
            "blueprint_id": blueprint_id,
            "blueprint_version": actual_version,
            "ad_format": str(blueprint.get("ad_format") or ad_format),
            "scope_type": scope_type,
            "account_id": account_id,
            "region": region,
            "tags": _tags(payload.get("tags", existing.tags if existing else [])),
            "values": values,
            "status": status,
            "is_default": is_default,
        }, blueprint

    def create(self, tenant_id: str, user_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        data, _ = self._payload(payload)
        now = datetime.now(timezone.utc).isoformat()
        record = CreationTemplateRecord(
            template_id=uuid.uuid4().hex,
            tenant_id=str(tenant_id), user_id=str(user_id),
            created_at=now, updated_at=now, **data,
        )
        try:
            saved = self.store.create_creation_template(record)
        except PersistenceConflictError as exc:
            raise CreationTemplateError("模板保存冲突，请稍后重试") from exc
        return self._public(saved)

    def list(self, tenant_id: str, user_id: str, **filters: Any) -> list[dict[str, Any]]:
        records = self.store.list_creation_templates(str(tenant_id), str(user_id), **filters)
        return [self._public(record) for record in records]

    def get(self, tenant_id: str, user_id: str, template_id: str) -> Optional[dict[str, Any]]:
        record = self.store.get_creation_template(template_id, tenant_id=str(tenant_id), user_id=str(user_id))
        return self._public(record) if record else None

    def update(self, tenant_id: str, user_id: str, template_id: str, payload: Mapping[str, Any]) -> Optional[dict[str, Any]]:
        existing = self.store.get_creation_template(template_id, tenant_id=str(tenant_id), user_id=str(user_id))
        if not existing:
            return None
        if payload.get("blueprint_id") and str(payload["blueprint_id"]) != existing.blueprint_id:
            raise CreationTemplateError("模板创建类型不可修改，请复制为新模板")
        data, _ = self._payload({**existing.to_dict(), **dict(payload)}, existing=existing)
        updated = self.store.update_creation_template(
            template_id, tenant_id=str(tenant_id), user_id=str(user_id), data=data
        )
        return self._public(updated) if updated else None

    def delete(self, tenant_id: str, user_id: str, template_id: str) -> Optional[dict[str, Any]]:
        record = self.store.delete_creation_template(template_id, tenant_id=str(tenant_id), user_id=str(user_id))
        return self._public(record) if record else None

    def duplicate(self, tenant_id: str, user_id: str, template_id: str, name: Optional[str] = None) -> Optional[dict[str, Any]]:
        record = self.store.get_creation_template(template_id, tenant_id=str(tenant_id), user_id=str(user_id))
        if not record:
            return None
        payload = record.to_dict()
        payload["name"] = name or f"{record.name} · 副本"
        payload["status"] = "active"
        payload["is_default"] = False
        return self.create(tenant_id, user_id, payload)

    def apply(self, tenant_id: str, user_id: str, template_id: str) -> Optional[dict[str, Any]]:
        record = self.store.record_creation_template_usage(
            template_id, tenant_id=str(tenant_id), user_id=str(user_id)
        )
        return self._public(record) if record else None
