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
from functools import lru_cache, partial
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from agents.applications.advertising.persistence.errors import PersistenceConflictError
from agents.applications.advertising.persistence.models import CreationTemplateRecord
from agents.tools.advertising.shared.domain.blueprint import _version_key
from .template_upgrade import preview_template_upgrade, registered_field_schema
from .verification import CreationVerificationCatalog, load_creation_verification


class CreationTemplateError(ValueError):
    """Raised when a template payload is invalid or no longer compatible."""


_SCOPE_TYPES = {"general", "account", "region"}
_STATUSES = {"active", "inactive", "archived"}
_MAX_VALUES_BYTES = 120_000
_FORBIDDEN_KEY = re.compile(
    r"(?:selection[_-]?tokens?(?:[_-]?tools?)?|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?(?:id|secret)|"
    r"app[_-]?secret|developer[_-]?token|private[_-]?key|authorization|"
    r"credentials?|partner[_-]?id|perter[_-]?id|bc[_-]?id|mcc|password|"
    r"(?:^|[._-])(?:scripts?|javascript|commands?|entrypoint|mcp)(?:$|[._-]))",
    re.IGNORECASE,
)
_SELECTION_TOKEN_VALUE = re.compile(r"ps1\.[A-Za-z0-9_-]+\.[a-f0-9]{64}")
_BUILTIN_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "builtin_creation_templates.json"
)
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
        for field in ("name", "provider", "blueprint_id", "blueprint_version"):
            _text(definition.get(field), f"内置模板 {key} 的 {field}", 240, required=True)
        scope_type = definition.get("scope_type", "account")
        if scope_type not in {"account", "general"}:
            raise CreationTemplateError(f"内置模板 {key} 的 scope_type 不支持")
        if scope_type == "general":
            if (definition.get("account_id")
                    or definition.get("verification_status") != "dry_run_only"):
                raise CreationTemplateError("通用起步模板不能绑定账户或声明真实创建验证")
        else:
            _text(definition.get("account_id"), f"内置模板 {key} 的 account_id", 240, required=True)
        values = definition.get("values")
        if not isinstance(values, Mapping):
            raise CreationTemplateError(f"内置模板 {key} 的 values 必须是对象")
        definition["key"] = key
        definition["values"] = dict(values)
        if type(definition.get("catalog_hidden", False)) is not bool:
            raise CreationTemplateError("内置模板 catalog_hidden 必须为布尔值")
        live_create_supported = definition.get("live_create_supported", True)
        if not isinstance(live_create_supported, bool):
            raise CreationTemplateError(
                f"内置模板 {key} 的 live_create_supported 必须是布尔值"
            )
        definition["live_create_supported"] = live_create_supported
        definition["live_create_block_reason"] = _text(
            definition.get("live_create_block_reason"),
            f"内置模板 {key} 的 live_create_block_reason",
            500,
            required=not live_create_supported,
        )
        definition["tags"] = _tags(definition.get("tags", []))
        definition["required_inputs"] = [
            _text(value, f"内置模板 {key} 的 required_inputs", 200)
            for value in (definition.get("required_inputs") or [])
        ]
        required_fields = definition.get("required_input_fields") or []
        if not isinstance(required_fields, list):
            raise CreationTemplateError(
                f"内置模板 {key} 的 required_input_fields 必须是数组"
            )
        definition["required_input_fields"] = list(dict.fromkeys(
            _text(value, f"内置模板 {key} 的 required_input_fields", 240, required=True)
            for value in required_fields
        ))
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
    if isinstance(value, str) and _SELECTION_TOKEN_VALUE.search(value):
        raise CreationTemplateError("模板不能保存凭证或可执行配置")
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
        verification_catalog: Optional[CreationVerificationCatalog] = None,
        field_schema_getter: Optional[Callable[[str], Mapping]] = None,
    ):
        self.store = store
        self.blueprint_getter = blueprint_getter
        self.builtin_templates = [dict(item) for item in (builtin_templates or [])]
        self.verification_catalog = verification_catalog or CreationVerificationCatalog()
        self.field_schema_getter = field_schema_getter
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
        if value["source"] == "user":
            value["verification"] = CreationVerificationCatalog().summarize(value)
            value["verification_status"] = value["verification"]["status"]
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

    def validate_overrides(
        self, template: Mapping[str, Any], values: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate preview values against the same Blueprint as saved presets."""
        blueprint = self._blueprint(template["blueprint_id"], template["blueprint_version"])
        return self._values(blueprint, values)

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
        if definition.get("scope_type") == "general":
            scope = self.account_scope if account_scope is _UNSET else account_scope
            return (
                (scope is None or bool(scope.get(provider)))
                and self.blueprint_getter(
                    definition["blueprint_id"], definition["blueprint_version"]
                ) is not None
            )
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
            "scope_type": definition.get("scope_type", "account"),
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
            "live_create_supported": definition.get("live_create_supported", True),
            "live_create_block_reason": str(
                definition.get("live_create_block_reason") or ""
            ),
            "required_inputs": list(definition.get("required_inputs") or []),
            "required_input_fields": list(
                definition.get("required_input_fields") or []
            ),
        }
        verification = self.verification_catalog.summarize(value)
        value["verification"] = verification
        value["verification_status"] = verification["status"]
        value["verified_scope"] = verification["notice"]
        return self._public(value)

    def _builtin_records(
        self,
        *,
        account_scope: Any = _UNSET,
        account_id: Optional[str] = None,
        provider: Optional[str] = None,
        blueprint_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        records = []
        for definition in self.builtin_templates:
            if definition.get("catalog_hidden", False):
                continue
            if provider and definition.get("provider") != provider:
                continue
            if blueprint_id and definition.get("blueprint_id") != blueprint_id:
                continue
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
        blueprint_id_value = payload.get("blueprint_id") or (
            existing.blueprint_id if existing else ""
        )
        blueprint_id = str(blueprint_id_value).strip()
        version_value = payload.get("blueprint_version") or (
            existing.blueprint_version if existing else ""
        )
        blueprint_version = str(version_value).strip() or None
        if not blueprint_id:
            raise CreationTemplateError("blueprint_id 不能为空")
        blueprint = self._blueprint(blueprint_id, blueprint_version)
        actual_version = str(blueprint.get("version") or blueprint_version or "")
        if blueprint_version and actual_version != blueprint_version:
            raise CreationTemplateError("模板引用的蓝图版本不可用，请重新从向导保存")
        provider_value = payload.get("provider") or (existing.provider if existing else "")
        ad_format_value = payload.get("ad_format") or (existing.ad_format if existing else "")
        provider = str(provider_value).strip()
        ad_format = str(ad_format_value).strip()
        if provider and provider != str(blueprint.get("provider") or ""):
            raise CreationTemplateError("模板渠道与创建蓝图不一致")
        if ad_format and ad_format != str(blueprint.get("ad_format") or ""):
            raise CreationTemplateError("模板广告类型与创建蓝图不一致")
        scope_value = payload.get("scope_type") or (
            existing.scope_type if existing else "general"
        )
        scope_type = str(scope_value).strip().lower()
        if scope_type not in _SCOPE_TYPES:
            raise CreationTemplateError("scope_type 必须是 general、account 或 region")
        account_value = payload.get(
            "account_id", existing.account_id if existing else "",
        )
        account_id = _text(account_value, "account_id", 200)
        region = _text(payload.get("region", existing.region if existing else ""), "region", 120)
        if scope_type == "account" and not account_id:
            raise CreationTemplateError("指定账户模板必须填写 account_id")
        if scope_type == "region" and not region:
            raise CreationTemplateError("指定地区模板必须填写 region")
        status_value = payload.get("status") or (existing.status if existing else "active")
        status = str(status_value).strip().lower()
        if status not in _STATUSES:
            raise CreationTemplateError("模板状态不合法")
        values_value = payload.get("values", existing.values if existing else {})
        values = self._values(blueprint, values_value)
        is_default = bool(payload.get("is_default", existing.is_default if existing else False))
        if status != "active":
            is_default = False
        return {
            "name": _text(
                payload.get("name", existing.name if existing else ""),
                "name",
                120,
                required=True,
            ),
            "description": _text(
                payload.get("description", existing.description if existing else ""),
                "description",
                500,
            ),
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

    def _visible_user_records(
        self,
        records: list[Any],
        *,
        account_id: Optional[str],
        account_scope: Any,
    ) -> list[dict[str, Any]]:
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
        return visible_records

    def _filtered_builtin_records(
        self,
        *,
        account_scope: Any,
        account_id: Optional[str],
        filters: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        records = self._builtin_records(
            account_scope=account_scope,
            account_id=account_id,
            provider=filters.get("provider"),
            blueprint_id=filters.get("blueprint_id"),
        )
        filtered_records = []
        query = str(filters.get("query") or "").strip().casefold()
        for record in records:
            if filters.get("provider") and record["provider"] != str(filters["provider"]):
                continue
            if filters.get("blueprint_id") and record["blueprint_id"] != str(filters["blueprint_id"]):
                continue
            if filters.get("status") and record["status"] != str(filters["status"]):
                continue
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
            filtered_records.append(record)
        return filtered_records

    def list(
        self,
        tenant_id: str,
        user_id: str,
        *,
        account_id: Optional[str] = None,
        account_scope: Any = _UNSET,
        source: Optional[str] = None,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        if source not in {None, "user", "builtin"}:
            raise CreationTemplateError("source 必须是 user 或 builtin")
        if source == "builtin":
            limit = max(1, min(int(filters.get("limit", 100)), 200))
            return self._filtered_builtin_records(
                account_scope=account_scope, account_id=account_id, filters=filters,
            )[:limit]
        records = self.store.list_creation_templates(
            str(tenant_id), str(user_id), **filters,
        )
        visible_records = self._visible_user_records(
            records,
            account_id=account_id,
            account_scope=account_scope,
        )
        if source == "user":
            return visible_records
        builtin_records = self._filtered_builtin_records(
            account_scope=account_scope, account_id=account_id,
            filters=filters,
        )
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
        record = self.store.get_creation_template(
            template_id,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
        )
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

    def update(
        self,
        tenant_id: str,
        user_id: str,
        template_id: str,
        payload: Mapping[str, Any],
    ) -> Optional[dict[str, Any]]:
        if self._builtin_by_id(template_id):
            raise CreationTemplateError("内置模板不可修改，请先复制为个人模板")
        existing = self.store.get_creation_template(
            template_id,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
        )
        if not existing:
            return None
        if payload.get("blueprint_id") and str(payload["blueprint_id"]) != existing.blueprint_id:
            raise CreationTemplateError("模板创建类型不可修改，请复制为新模板")
        if (payload.get("blueprint_version")
                and str(payload["blueprint_version"]) != existing.blueprint_version):
            raise CreationTemplateError("蓝图版本升级必须先预览并另存新模板，不能覆盖旧版本")
        data, _ = self._payload({**existing.to_dict(), **dict(payload)}, existing=existing)
        updated = self.store.update_creation_template(
            template_id,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            data=data,
        )
        return self._public(updated) if updated else None

    def preview_upgrade(
        self, tenant_id: str, user_id: str, template_id: str,
        target_version: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        template = self.get(tenant_id, user_id, template_id)
        if template is None:
            return None
        source = self._blueprint(template["blueprint_id"], template["blueprint_version"])
        target = self._blueprint(template["blueprint_id"], target_version)
        if _version_key(target["version"]) <= _version_key(source["version"]):
            raise CreationTemplateError("没有可升级的新蓝图版本")
        if source["provider"] != target["provider"] or source["ad_format"] != target["ad_format"]:
            raise CreationTemplateError("升级不能改变渠道或广告类型")
        return preview_template_upgrade(
            template, source, target, field_schema_getter=self.field_schema_getter,
        )

    def delete(self, tenant_id: str, user_id: str, template_id: str) -> Optional[dict[str, Any]]:
        if self._builtin_by_id(template_id):
            raise CreationTemplateError("内置模板不可删除，请先复制为个人模板")
        record = self.store.delete_creation_template(
            template_id,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
        )
        return self._public(record) if record else None

    def duplicate(
        self,
        tenant_id: str,
        user_id: str,
        template_id: str,
        name: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        record = self.store.get_creation_template(
            template_id,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
        )
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

    @lru_cache(maxsize=128)
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
    tools = getattr(runtime, "registry", None)

    return CreationTemplateManager(
        store,
        get_blueprint,
        builtin_templates=load_builtin_template_definitions(),
        allowed_accounts=getattr(validator, "allowed_accounts", {}) if validator else {},
        account_scope=account_scope,
        verification_catalog=load_creation_verification(),
        field_schema_getter=partial(registered_field_schema, tools) if tools else None,
    )
