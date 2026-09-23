"""Management facade for user-owned campaign creation presets.

Templates are data-only snapshots of values accepted by a registered
creation Blueprint. They never contain code, provider clients, credentials,
or a shortcut around Runtime policy gates.
"""

from __future__ import annotations

import json
import hashlib
import re
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
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
_BUILTIN_TEMPLATE_PATH = Path(__file__).parent / "contracts" / "builtin_creation_templates.json"
_UNSET = object()


@lru_cache(maxsize=4)
def load_builtin_template_definitions(path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Load the checked-in, data-only template catalog.

    The catalog is intentionally outside persistence. It is versioned with the
    Blueprint contracts and rebuilt at process start, so it cannot become a
    second mutable template store.
    """
    catalog_path = Path(path or _BUILTIN_TEMPLATE_PATH)
    try:
        document = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CreationTemplateError("内置创建模板目录不可用") from exc
    if not isinstance(document, Mapping) or not isinstance(document.get("templates"), list):
        raise CreationTemplateError("内置创建模板目录格式不正确")
    definitions: list[dict[str, Any]] = []
    keys: set[str] = set()
    for item in document["templates"]:
        if not isinstance(item, Mapping):
            raise CreationTemplateError("内置创建模板必须是对象")
        definition = dict(item)
        key = _text(definition.get("key"), "内置模板 key", 160, required=True)
        if key in keys:
            raise CreationTemplateError(f"内置模板 key 重复：{key}")
        keys.add(key)
        for field in ("name", "provider", "blueprint_id", "blueprint_version", "account_id"):
            _text(definition.get(field), f"内置模板 {key} 的 {field}", 240, required=True)
        values = definition.get("values")
        if not isinstance(values, Mapping):
            raise CreationTemplateError(f"内置模板 {key} 的 values 必须是对象")
        definition["key"] = key
        definition["values"] = dict(values)
        definition["tags"] = _tags(definition.get("tags", []))
        definition["required_inputs"] = [
            _text(value, f"内置模板 {key} 的 required_inputs", 200)
            for value in (definition.get("required_inputs") or [])
        ]
        definitions.append(definition)
    return definitions


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

    def __init__(
        self,
        store: Any,
        blueprint_getter: Callable[[str, Optional[str]], Optional[dict]],
        *,
        builtin_templates: Optional[list[Mapping[str, Any]]] = None,
        allowed_accounts: Optional[Mapping[str, Any]] = None,
        account_scope: Optional[Mapping[str, Any]] = None,
    ):
        self.store = store
        self.blueprint_getter = blueprint_getter
        self.builtin_templates = [dict(item) for item in (builtin_templates or [])]
        self.allowed_accounts = {
            str(provider): {str(account) for account in (accounts or [])}
            for provider, accounts in (allowed_accounts or {}).items()
        }
        self.account_scope = (
            None
            if account_scope is None
            else {
                str(provider): {str(account) for account in (accounts or [])}
                for provider, accounts in account_scope.items()
            }
        )

    @staticmethod
    def _public(record: Any) -> dict[str, Any]:
        if isinstance(record, CreationTemplateRecord):
            value = record.to_dict()
        elif isinstance(record, Mapping):
            value = dict(record)
            value["tags"] = list(value.get("tags") or [])
            value["values"] = json.loads(
                json.dumps(value.get("values") or {}, ensure_ascii=False, default=str)
            )
        else:
            raise CreationTemplateError("模板记录格式不正确")
        fields = value.get("values") if isinstance(value.get("values"), dict) else {}
        value["covered_fields"] = len(fields)
        value["scope_label"] = {
            "general": "个人通用",
            "account": "指定账户",
            "region": "指定地区",
        }.get(value.get("scope_type"), value.get("scope_type"))
        value["is_usable"] = value.get("status") == "active"
        value.setdefault("source", "user")
        value.setdefault("editable", value["source"] == "user")
        value.setdefault("template_kind", "builtin" if value["source"] == "builtin" else "user")
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

    @staticmethod
    def _builtin_id(definition: Mapping[str, Any]) -> str:
        identity = ":".join(
            str(definition.get(field) or "")
            for field in ("key", "blueprint_id", "blueprint_version", "account_id")
        )
        return f"builtin_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"

    def _account_is_visible(
        self,
        provider: str,
        account_id: str,
        account_scope: Any = _UNSET,
        *,
        require_configured: bool = False,
    ) -> bool:
        account_id = str(account_id or "").strip()
        if not account_id:
            return True
        configured = self.allowed_accounts.get(provider)
        if configured and account_id not in configured:
            return False
        if require_configured and not configured:
            return False
        scope = self.account_scope if account_scope is _UNSET else account_scope
        if scope is None:
            return True
        scoped = {
            str(value)
            for value in (scope.get(provider, ()) if isinstance(scope, Mapping) else ())
        }
        return account_id in scoped

    def _builtin_is_visible(
        self,
        definition: Mapping[str, Any],
        account_scope: Any = _UNSET,
        account_id: Optional[str] = None,
    ) -> bool:
        provider = str(definition.get("provider") or "")
        template_account = str(definition.get("account_id") or "")
        if account_id and template_account != str(account_id):
            return False
        return self._account_is_visible(
            provider,
            template_account,
            account_scope,
            require_configured=True,
        )

    def _builtin_record(self, definition: Mapping[str, Any]) -> dict[str, Any]:
        key = str(definition.get("key") or "builtin")
        data, _ = self._payload({
            "name": definition.get("name"),
            "description": definition.get("description", ""),
            "provider": definition.get("provider", ""),
            "blueprint_id": definition.get("blueprint_id"),
            "blueprint_version": definition.get("blueprint_version"),
            "ad_format": definition.get("ad_format", ""),
            "scope_type": "account",
            "account_id": definition.get("account_id"),
            "region": definition.get("region", ""),
            "tags": definition.get("tags", []),
            "values": definition.get("values", {}),
            "status": "active",
            "is_default": True,
        })
        value: dict[str, Any] = {
            "template_id": self._builtin_id(definition),
            "tenant_id": "",
            "user_id": "",
            **data,
            "usage_count": 0,
            "created_at": "",
            "updated_at": "",
            "last_used_at": None,
            "source": "builtin",
            "editable": False,
            "template_kind": "builtin",
            "catalog_key": key,
            "verification_status": str(definition.get("verification_status") or "dry_run_only"),
            "verified_scope": str(definition.get("verified_scope") or ""),
            "required_inputs": list(definition.get("required_inputs") or []),
        }
        return self._public(value)

    def _builtin_records(
        self,
        *,
        account_scope: Any = _UNSET,
        account_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        records = []
        for definition in self.builtin_templates:
            if self._builtin_is_visible(definition, account_scope, account_id):
                records.append(self._builtin_record(definition))
        return records

    def _builtin_by_id(
        self,
        template_id: str,
        *,
        account_scope: Any = _UNSET,
        account_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        for definition in self.builtin_templates:
            if (
                self._builtin_id(definition) == str(template_id)
                and self._builtin_is_visible(definition, account_scope, account_id)
            ):
                return self._builtin_record(definition)
        return None

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

    def list(
        self,
        tenant_id: str,
        user_id: str,
        *,
        account_id: Optional[str] = None,
        account_scope: Any = _UNSET,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        records = self.store.list_creation_templates(
            str(tenant_id), str(user_id), **filters,
        )
        visible_records = []
        for record in records:
            public = self._public(record)
            if account_id and (
                public.get("scope_type") == "account"
                and str(public.get("account_id") or "") != str(account_id)
            ):
                continue
            if not self._account_is_visible(
                str(public.get("provider") or ""),
                str(public.get("account_id") or ""),
                account_scope,
            ):
                continue
            visible_records.append(public)
        builtin_records = []
        for record in self._builtin_records(
            account_scope=account_scope, account_id=account_id,
        ):
            if filters.get("provider") and record["provider"] != str(filters["provider"]):
                continue
            if filters.get("blueprint_id") and record["blueprint_id"] != str(filters["blueprint_id"]):
                continue
            if filters.get("status") and record["status"] != str(filters["status"]):
                continue
            query = str(filters.get("query") or "").strip().casefold()
            if query:
                searchable = " ".join([
                    str(record.get("name") or ""),
                    str(record.get("description") or ""),
                    str(record.get("provider") or ""),
                    str(record.get("catalog_key") or ""),
                    " ".join(record.get("tags") or []),
                    " ".join(record.get("required_inputs") or []),
                ]).casefold()
                if query not in searchable:
                    continue
            builtin_records.append(record)
        limit = max(1, min(int(filters.get("limit", 100)), 200))
        return [*builtin_records, *visible_records][:limit]

    def get(
        self,
        tenant_id: str,
        user_id: str,
        template_id: str,
        *,
        account_id: Optional[str] = None,
        account_scope: Any = _UNSET,
    ) -> Optional[dict[str, Any]]:
        record = self.store.get_creation_template(template_id, tenant_id=str(tenant_id), user_id=str(user_id))
        if record:
            public = self._public(record)
            if account_id and (
                public.get("scope_type") == "account"
                and str(public.get("account_id") or "") != str(account_id)
            ):
                return None
            if not self._account_is_visible(
                str(public.get("provider") or ""),
                str(public.get("account_id") or ""),
                account_scope,
            ):
                return None
            return public
        return self._builtin_by_id(
            template_id, account_scope=account_scope, account_id=account_id,
        )

    def update(self, tenant_id: str, user_id: str, template_id: str, payload: Mapping[str, Any]) -> Optional[dict[str, Any]]:
        if self._builtin_by_id(template_id):
            raise CreationTemplateError("内置模板不可修改，请先复制为个人模板")
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
        if self._builtin_by_id(template_id):
            raise CreationTemplateError("内置模板不可删除，请先复制为个人模板")
        record = self.store.delete_creation_template(template_id, tenant_id=str(tenant_id), user_id=str(user_id))
        return self._public(record) if record else None

    def duplicate(self, tenant_id: str, user_id: str, template_id: str, name: Optional[str] = None) -> Optional[dict[str, Any]]:
        record = self.store.get_creation_template(template_id, tenant_id=str(tenant_id), user_id=str(user_id))
        builtin = self._builtin_by_id(template_id)
        if record:
            payload = record.to_dict()
        elif builtin:
            payload = dict(builtin)
        else:
            return None
        source_name = record.name if record else builtin["name"]
        payload["name"] = name or f"{source_name} · 副本"
        payload["status"] = "active"
        payload["is_default"] = False
        return self.create(tenant_id, user_id, payload)

    def apply(self, tenant_id: str, user_id: str, template_id: str) -> Optional[dict[str, Any]]:
        builtin = self._builtin_by_id(template_id)
        if builtin:
            return builtin
        record = self.store.record_creation_template_usage(
            template_id, tenant_id=str(tenant_id), user_id=str(user_id)
        )
        return self._public(record) if record else None


def creation_template_manager_for_runtime(
    runtime: Any,
    *,
    account_scope: Any = None,
) -> CreationTemplateManager:
    """Build the shared data-only template service for a Runtime request.

    The manager owns catalog validation and persistence access, while the
    caller supplies the current principal's account scope.  No request path
    receives provider clients or credentials through this service.
    """
    store = getattr(runtime, "persistence_store", None)
    if store is None:
        raise CreationTemplateError("创建模板存储未初始化")
    registry = getattr(runtime, "creation_blueprints", None)
    getter = getattr(registry, "get", None)
    if not callable(getter):
        raise CreationTemplateError("创建蓝图注册表未初始化")

    def get_blueprint(
        blueprint_id: str, version: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        blueprint = getter(str(blueprint_id), version or None)
        if blueprint is None:
            return None
        builder = getattr(runtime, "creation_card_builder", None)
        expand = getattr(builder, "expand_blueprint", None)
        if callable(expand):
            blueprint = expand(blueprint)
        to_dict = getattr(blueprint, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        return blueprint if isinstance(blueprint, dict) else None

    validator = getattr(runtime, "whitelist_validator", None)
    return CreationTemplateManager(
        store,
        get_blueprint,
        builtin_templates=load_builtin_template_definitions(),
        allowed_accounts=getattr(validator, "allowed_accounts", {}) if validator else {},
        account_scope=account_scope,
    )
