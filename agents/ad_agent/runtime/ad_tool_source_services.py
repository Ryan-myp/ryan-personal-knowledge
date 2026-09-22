"""Advertising Tool Source/Skill lifecycle services.

The lifecycle is application composition: the generic Runtime Kernel only
receives an already assembled turn executor and never discovers Providers.
"""

from __future__ import annotations

import copy
from functools import wraps
import hashlib
import hmac
import importlib.util
import inspect
import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping, Optional

from ..core.interfaces import (
    ToolSourceModule, ToolSourceRuntime, ToolContext, ToolResult,
)
from ..domain.ad.contracts import AdFormatCoverage
from .tool_source_context import ToolSourceContextWrapper
from ..core.plugins import PluginKind
from .provider_bindings import ProviderBindings
from .skill import Skill

logger = logging.getLogger(__name__)


def _serialize_skill_lifecycle(method):
    """Serialize registry and ownership-index mutations in one Runtime."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        lock = getattr(self, "_skill_lifecycle_lock", None)
        if lock is None:
            return method(self, *args, **kwargs)
        with lock:
            return method(self, *args, **kwargs)

    return wrapped


class AdToolSourceLifecycleMixin:
    @_serialize_skill_lifecycle
    def register_provider_tool_source(
        self, module: ToolSourceModule
    ) -> ToolSourceRuntime:
        """Register a Tool Source atomically from the Runtime's perspective.

        Tool Source ``configure`` implementations register Tools through a
        callback, so a failure after the first Tool would otherwise leave a
        half-loaded provider in the live Registry.  Keep the rollback here,
        at the boundary that owns the derived indexes, rather than requiring
        every provider package to implement its own transaction protocol.
        """
        before_tool_names = {
            definition.name for definition in self.registry.list_all()
        }
        before_formats = copy.deepcopy(self.ad_format_catalogs)
        before_provider_versions = copy.deepcopy(self.provider_version_contracts)
        before_provider_surfaces = copy.deepcopy(self.provider_api_surfaces)
        before_blueprints = self.creation_blueprints.snapshot()
        try:
            runtime = self._register_provider_tool_source_unchecked(module)
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self._register_builtin_plugin(
                    f"provider-tools:{platform}",
                    module,
                    (PluginKind.TOOL_SOURCE.value,),
                    version=str(
                        getattr(module, "tool_source_version", "1.0.0") or "1.0.0"
                    ),
                    description=f"Provider tool_source {platform}",
                )
            return runtime
        except Exception:
            current_tool_names = {
                definition.name for definition in self.registry.list_all()
            }
            added_tool_names = current_tool_names - before_tool_names
            for name in added_tool_names:
                self.registry.unregister(name)
            self.parameter_catalogs.remove_tools(list(added_tool_names))

            # Normally ownership indexes are written only after all metadata
            # validation succeeds.  Remove them defensively as well so a
            # future failure in the final parser refresh cannot leave an
            # unloadable Skill marker behind.
            for skill_key, tool_names in list(self._skill_tool_names.items()):
                if not (set(tool_names) & added_tool_names):
                    continue
                platform = self._skill_namespaces.pop(skill_key, None)
                self._skill_tool_names.pop(skill_key, None)
                self._skill_objects.pop(skill_key, None)
                self._skill_format_ids.pop(skill_key, None)
                if platform:
                    canonical = self._canonical_platform(platform)
                    keys = [
                        key for key in self._skill_keys_by_platform.get(canonical, [])
                        if key != skill_key
                    ]
                    if keys:
                        self._skill_keys_by_platform[canonical] = keys
                    else:
                        self._skill_keys_by_platform.pop(canonical, None)
            self.ad_format_catalogs = before_formats
            self.provider_version_contracts = before_provider_versions
            self.provider_api_surfaces = before_provider_surfaces
            self.creation_blueprints.restore(before_blueprints)
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self.plugin_registry.unregister(f"provider-tools:{platform}")
            try:
                self._refresh_parser_catalog()
            except Exception:
                logger.exception("Tool Source rollback could not refresh parser catalog")
            raise

    def _register_provider_tool_source_unchecked(
        self, module: ToolSourceModule
    ) -> ToolSourceRuntime:
        """
        注册一个 ToolSourceModule。

        对应 DAP Agent 的 ToolSourceModule.Configure() 模式：
        业务模块不直接操作 Runtime，而是通过接口注入能力。
        """
        before_tool_names = {
            definition.name for definition in self.registry.list_all()
        }
        context = ToolSourceContextWrapper(self.registry)
        runtime = module.configure(context)

        # Publish provider parameter options as data owned by the Tool Source.
        # Existing tools get enum/lookup discovery automatically; a future
        # Skill can additionally provide richer versioned catalogs through the
        # ToolSourceRuntime extension field.
        for definition in self.registry.list_all():
            self.parameter_catalogs.register_tool_schema(
                definition.namespace,
                getattr(definition.input_schema, "properties", {})
                if definition.input_schema else {},
                tool_name=definition.name,
            )
        self.parameter_catalogs.register_many(
            getattr(runtime, "parameter_catalogs", []) or []
        )
        platform = self._canonical_platform(getattr(module, "platform_name", ""))
        blueprints = getattr(runtime, "creation_blueprints", []) or []
        if blueprints:
            self.creation_blueprints.register_many(
                blueprints,
                owner=platform or None,
                tool_registry=self.registry,
            )
        self._register_ad_format_catalog(
            getattr(module, "platform_name", "") or "",
            getattr(runtime, "ad_format_catalogs", []) or [],
        )
        provider_contract_getter = getattr(module, "get_provider_version_contract", None)
        if callable(provider_contract_getter):
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self.provider_version_contracts[platform] = copy.deepcopy(
                    provider_contract_getter()
                )
        provider_surface_getter = getattr(module, "get_api_surface", None)
        if callable(provider_surface_getter):
            platform = self._canonical_platform(getattr(module, "platform_name", ""))
            if platform:
                self.provider_api_surfaces[platform] = copy.deepcopy(
                    provider_surface_getter()
                )
        self._validate_parameter_lookup_contract()
        # Tool Source.configure() registers platform tools before returning.
        # Apply the read-only boundary immediately so callers cannot forget a
        # second, manually-invoked enable_read_only_mode() call.
        if self._read_only_mode:
            self._filter_write_tools()

        # Keep the Parser's language catalog derived from the actual Registry
        # rather than from a central intent table.  Custom parsers may ignore
        # this optional extension seam.
        register_tools = getattr(self.intent_parser, "register_tool_definitions", None)
        if callable(register_tools):
            register_tools(self.registry.list_all())

        # Register executable tools supplied by the Tool Source.  Tool metadata
        # is the routing contract; no workflow file is consulted here.
        tool_source_platform = getattr(module, "platform_name", None)
        # A Tool Source registration already activated the platform's tools.
        # Keep the declarative Skill as the platform lifecycle marker so the
        # next turn does not try to register the same tools again.
        if tool_source_platform:
            canonical_namespace = self._canonical_platform(tool_source_platform)
            skill_candidates = self.skill_loader.get_by_namespace(canonical_namespace)
            if skill_candidates:
                primary_skill = skill_candidates[0]
                skill_key = str(getattr(primary_skill, "name", "") or canonical_namespace)
            else:
                primary_skill = None
                skill_key = f"{canonical_namespace}:provider-tools:{id(module)}"
            registered_names = sorted(
                definition.name
                for definition in self.registry.list_all()
                if definition.name not in before_tool_names
            )
            if registered_names:
                self._skill_tool_names[skill_key] = registered_names
                self._skill_namespaces[skill_key] = canonical_namespace
                if primary_skill is not None:
                    self._skill_objects[skill_key] = primary_skill
                self._skill_keys_by_platform.setdefault(canonical_namespace, []).append(
                    skill_key
                )
                self._skill_format_ids[skill_key] = {
                    str(item.get("format_id"))
                    for item in (getattr(runtime, "ad_format_catalogs", []) or [])
                    if isinstance(item, dict) and item.get("format_id")
                }

        # Rebuild derived discovery state after ownership has been recorded.
        # This is the same lifecycle boundary used by unload_skill().
        self._refresh_parser_catalog()

        # 注册后台任务
        self._background_tasks.extend(runtime.background_tasks)

        # 注册写入保护
        if runtime.write_guard:
            self.write_guard = runtime.write_guard
            if self._session_manager and hasattr(self.write_guard, "bind_store"):
                self.write_guard.bind_store(self._session_manager.store)

        # A caller may set credentials before registering a Tool Source.  Bind
        # a client only to handlers that were created without an explicit
        # client; never replace an injected fake/test/client instance.
        self._refresh_unbound_clients()

        return runtime

    def _register_ad_format_catalog(
        self, platform: str, catalogs: list[dict[str, Any]]
    ) -> None:
        """Validate and index a Tool Source's format metadata.

        The catalog is intentionally declarative.  It cannot register a
        handler, expand permissions, or enable live writes.  Duplicate IDs
        are rejected so two provider packages cannot silently disagree about
        the same format contract.
        """
        if not catalogs:
            return
        canonical = self._canonical_platform(platform)
        allowed = {item.value for item in AdFormatCoverage}
        existing = {
            str(item.get("format_id")): item
            for item in self.ad_format_catalogs.get(canonical, [])
        }
        normalized: list[dict[str, Any]] = list(
            self.ad_format_catalogs.get(canonical, [])
        )
        for item in catalogs:
            if not isinstance(item, dict):
                raise ValueError(f"{canonical}: ad format catalog entry must be an object")
            entry = dict(item)
            format_id = str(entry.get("format_id", "")).strip()
            status = str(entry.get("coverage", "")).strip().lower()
            if not format_id:
                raise ValueError(f"{canonical}: ad format catalog entry needs format_id")
            if status not in allowed:
                raise ValueError(
                    f"{canonical}.{format_id}: unsupported coverage {status!r}"
                )
            if not str(entry.get("category", "")).strip():
                raise ValueError(f"{canonical}.{format_id}: category is required")
            if not str(entry.get("resource_type", "")).strip():
                raise ValueError(f"{canonical}.{format_id}: resource_type is required")
            tool_names = entry.get("tool_names", []) or []
            if not isinstance(tool_names, list) or not all(
                isinstance(name, str) and name for name in tool_names
            ):
                raise ValueError(f"{canonical}.{format_id}: tool_names must be a string list")
            entry["format_id"] = format_id
            entry["coverage"] = status
            entry["tool_names"] = list(dict.fromkeys(tool_names))
            entry["live_support"] = bool(entry.get("live_support", False))
            registered_tools = {
                definition.name for definition in self.registry.list_all()
            }
            missing_tools = sorted(set(entry["tool_names"]) - registered_tools)
            if missing_tools:
                raise ValueError(
                    f"{canonical}.{format_id}: unknown tool_names: {', '.join(missing_tools)}"
                )
            if entry["live_support"]:
                raise ValueError(
                    f"{canonical}.{format_id}: ad-format live_support must remain false; "
                    "live enablement is a separate deployment approval"
                )
            if status == AdFormatCoverage.SUPPORTED_DRY_RUN.value and not entry.get(
                "payload_adapter"
            ):
                raise ValueError(
                    f"{canonical}.{format_id}: supported_dry_run needs payload_adapter"
                )
            previous = existing.get(format_id)
            if previous is not None and previous != entry:
                raise ValueError(f"{canonical}.{format_id}: conflicting catalog entry")
            if previous is None:
                existing[format_id] = entry
                normalized.append(entry)
        self.ad_format_catalogs[canonical] = normalized


    def _register_skill(self, skill: Skill) -> None:
        """将 Skill 的工具注册到 Registry"""
        register_aliases = getattr(self.intent_parser, "register_namespace_aliases", None)
        if callable(register_aliases):
            register_aliases(skill.namespace, skill.namespace_aliases or [])
        registered_names: list[str] = []
        for tool_def in skill.get_tools():
            skill_namespace = self._canonical_platform(skill.namespace)
            tool_namespace = self._canonical_platform(tool_def.namespace)
            if tool_namespace != skill_namespace:
                raise ValueError(
                    f"Tool '{tool_def.name}' namespace '{tool_namespace}' "
                    f"does not match Skill namespace '{skill_namespace}'"
                )
            if self._read_only_mode and tool_def.is_write_tool:
                continue
            handler = skill.get_tool_handler(tool_def.name)
            if handler:
                self.registry.register(tool_def, handler)
                registered_names.append(tool_def.name)
        if registered_names:
            skill_key = str(getattr(skill, "name", "") or skill.namespace)
            self._skill_tool_names[skill_key] = registered_names
            self._skill_namespaces[skill_key] = skill.namespace
            self._skill_objects[skill_key] = skill
            namespace_key = self._canonical_platform(skill.namespace)
            keys = self._skill_keys_by_platform.setdefault(namespace_key, [])
            if skill_key not in keys:
                keys.append(skill_key)
            register_tools = getattr(self.intent_parser, "register_tool_definitions", None)
            if callable(register_tools):
                register_tools([self.registry.get(name)[0] for name in registered_names])

    # ─── Skill 动态注册 ────────────────────────────────────────

    @_serialize_skill_lifecycle
    def register_skill(self, skill: Skill, platform: str, api_client=None) -> bool:
        """
        动态注册一个 Skill。

        策略：直接使用 Tool Source 的工具定义，而不是动态创建 Handler。

        Args:
            skill: Skill 对象（从 SKILL.md 解析）
            platform: 平台名称
            api_client: API 客户端（None 时使用 mock 模式）
        """
        # Dynamic Skill loading and the API/CLI path must use the same
        # canonical Tool Source factory.  The factory only constructs local
        # objects and does not contact a provider.
        canonical_namespace = self.provider_bindings.normalize_namespace(platform)
        declared_namespace = self.provider_bindings.normalize_namespace(
            getattr(skill, "namespace", "")
        )
        if declared_namespace and declared_namespace != canonical_namespace:
            raise ValueError(
                f"Skill '{getattr(skill, 'name', '')}' namespace '{declared_namespace}' "
                f"does not match requested namespace '{canonical_namespace}'"
            )
        skill_key = str(getattr(skill, "name", "") or f"{canonical_namespace}:{id(skill)}")
        if skill_key in self._skill_tool_names:
            logger.info("ⓘ Skill '%s' 已加载，跳过重复注册", skill_key)
            return True

        # A custom Skill may provide its own ToolDefinitions and handlers; in
        # that case register only the declared executable tools instead of
        # exposing every tool belonging to the platform.
        declared_tools = []
        get_tools = getattr(skill, "get_tools", None)
        get_handler = getattr(skill, "get_tool_handler", None)
        if callable(get_tools) and callable(get_handler):
            try:
                declared_tools = list(get_tools() or [])
            except Exception as exc:
                logger.warning("解析 Skill '%s' 工具声明失败: %s", skill_key, exc)

        # A custom Skill can target a new platform and provide all of its own
        # handlers. Built-in provider packages can be discovered by convention;
        # the extension seam remains genuinely Skill + Tools based.
        tool_source = self._discover_tool_source(canonical_namespace, api_client)
        if tool_source is None:
            try:
                tool_source = self.provider_bindings.create_tool_source(
                    canonical_namespace, api_client
                )
            except ValueError:
                if not declared_tools:
                    logger.warning("⚠️ 未找到平台 '%s' 的 Tool Source，且 Skill 没有声明可执行工具", platform)
                    return

        tool_source_tools = {
            definition.name: (definition, handler)
            for definition, handler in tool_source.register_tools()
        } if tool_source is not None else {}

        tools = []
        if declared_tools:
            for declared in declared_tools:
                declared_tool_namespace = self.provider_bindings.normalize_namespace(
                    getattr(declared, "namespace", "")
                )
                if declared_tool_namespace != canonical_namespace:
                    raise ValueError(
                        f"Tool '{declared.name}' namespace '{declared_tool_namespace}' "
                        f"does not match Skill namespace '{canonical_namespace}'"
                    )
                handler = get_handler(declared.name)
                if handler is None and declared.name in tool_source_tools:
                    # Allow a declarative channel Skill to reuse the verified
                    # provider handler while retaining the Skill's own scope.
                    _, handler = tool_source_tools[declared.name]
                if handler is not None:
                    tools.append((declared, handler))
            if not tools:
                logger.warning(
                    "⚠️ Skill '%s' 的工具均没有可执行 Handler，未注册",
                    skill_key,
                )
                return False
        else:
            # A declarative Skill with no executable declarations uses the
            # provider Tool Source for its platform's verified handlers.
            tools = list(tool_source_tools.values())

        if not tools:
            logger.warning(f"⚠️ Tool Source '{platform}' 没有定义任何工具")
            return False

        # 注册工具
        registered_count = 0
        for tool_def, handler in tools:
            tool_namespace = self.provider_bindings.normalize_namespace(
                getattr(tool_def, "namespace", "")
            )
            if tool_namespace != canonical_namespace:
                raise ValueError(
                    f"Tool '{tool_def.name}' namespace '{tool_namespace}' "
                    f"does not match Skill namespace '{canonical_namespace}'"
                )
            metadata_errors = tool_def.routing_metadata_errors()
            if metadata_errors:
                raise ValueError(
                    f"Skill '{skill_key}' Tool '{tool_def.name}' is missing explicit "
                    "routing metadata: " + ", ".join(metadata_errors)
                )
            if self._read_only_mode and tool_def.is_write_tool:
                continue
            # These defaults belong to the advertising adapter. Core Runtime
            # consumes the published metadata but never infers ad permissions
            # or account fields for arbitrary applications.
            if not tool_def.scope_fields:
                tool_def.scope_type = tool_def.scope_type or "account"
                tool_def.scope_fields = [
                    "account_id", "ad_account_id", "advertiser_id", "customer_id",
                ]
                tool_def.scope_required = True
            if tool_def.is_write_tool and not tool_def.live_permission:
                tool_def.live_permission = "ads.write"
            if not tool_def.required_permissions:
                tool_def.required_permissions = [
                    "ads.plan" if tool_def.is_write_tool else "ads.read"
                ]
            try:
                self.registry.register(tool_def, handler)
                self.parameter_catalogs.register_tool_schema(
                    tool_def.namespace,
                    getattr(tool_def.input_schema, "properties", {})
                    if tool_def.input_schema else {},
                    tool_name=tool_def.name,
                )
                registered_count += 1
                logger.debug(f"✅ 注册工具: {tool_def.name} (platform={platform})")
            except Exception as e:
                logger.warning(f"⚠️ 注册工具失败 '{tool_def.name}': {e}")

        if registered_count == 0:
            logger.warning("⚠️ Skill '%s' 没有实际注册任何工具", skill_key)
            return False

        self._validate_parameter_lookup_contract()
        register_tools = getattr(self.intent_parser, "register_tool_definitions", None)
        if callable(register_tools):
            register_tools(self.registry.list_all())

        # 保存 Skill 和平台映射
        self._skill_tool_names[skill_key] = [tool_def.name for tool_def, _ in tools]
        self._skill_namespaces[skill_key] = canonical_namespace
        self._skill_objects[skill_key] = skill
        keys = self._skill_keys_by_platform.setdefault(canonical_namespace, [])
        if skill_key not in keys:
            keys.append(skill_key)

        self._refresh_parser_catalog()
        self._register_builtin_plugin(
            f"skill:{skill_key}",
            skill,
            (PluginKind.SKILL.value, PluginKind.TOOL_SOURCE.value),
            version=str(getattr(skill, "version", "1.0.0") or "1.0.0"),
            description=str(getattr(skill, "description", "") or ""),
        )

        logger.info(f"✅ 已动态注册 Skill '{skill.name}'，共 {registered_count} 个工具")
        return True

    @staticmethod
    def _verify_skill_plugin(skill_dir: Any, plugin_path: Any) -> tuple[bool, str]:
        """Verify an optional Skill manifest before importing executable code."""
        skill_dir = os.fspath(skill_dir)
        plugin_path = os.fspath(plugin_path)
        manifest_path = os.path.join(skill_dir, "skill.manifest.json")
        require_manifest = os.environ.get("AD_AGENT_REQUIRE_SKILL_MANIFEST") == "1"
        if not os.path.exists(manifest_path):
            if require_manifest:
                return False, "skill.manifest.json is required"
            return True, "manifest not configured"
        try:
            with open(manifest_path, "r", encoding="utf-8") as file:
                manifest = json.load(file)
        except (OSError, TypeError, ValueError) as exc:
            return False, f"invalid skill manifest: {exc}"
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(files, dict):
            return False, "skill manifest files must be an object"
        relative_name = os.path.basename(plugin_path)
        expected = files.get(relative_name) or files.get(os.path.relpath(plugin_path, skill_dir))
        if not isinstance(expected, str):
            return False, f"skill manifest does not cover {relative_name}"
        digest = hashlib.sha256()
        try:
            with open(plugin_path, "rb") as file:
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            return False, f"cannot hash Skill plugin: {exc}"
        if not hmac.compare_digest(digest.hexdigest(), expected.lower()):
            return False, f"hash mismatch for {relative_name}"

        signing_key = os.environ.get("AD_AGENT_SKILL_MANIFEST_KEY")
        signature = manifest.get("signature") if isinstance(manifest, dict) else None
        if require_manifest and not signing_key:
            return False, "AD_AGENT_SKILL_MANIFEST_KEY is required with manifest enforcement"
        if signing_key:
            if not isinstance(signature, str) or not signature:
                return False, "signed Skill manifest is required"
            signed_payload = json.dumps(
                {
                    "skill": manifest.get("skill", os.path.basename(skill_dir)),
                    "version": manifest.get("version", "1"),
                    "files": files,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            expected_signature = hmac.new(
                signing_key.encode("utf-8"), signed_payload, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected_signature):
                return False, "skill manifest signature mismatch"
        return True, "verified"

    @staticmethod
    def _load_skill_plugin(skill_dir: Any, api_client=None) -> Optional[Skill]:
        """Load an optional executable Skill plugin from a Skill directory.

        Supported convention:

        ``skills/<name>/tools.py`` or ``skills/<name>/tools/__init__.py``
        exports ``create_skill(api_client)``. The factory must return a Core ``Skill``
        implementation with ``get_tools`` and ``get_tool_handler`` methods.

        Importing a plugin only constructs local objects; provider I/O remains
        inside Runtime's normal execution gates.
        """
        from pathlib import Path

        skill_dir = Path(skill_dir)
        candidates = [skill_dir / "tools.py", skill_dir / "tools" / "__init__.py"]
        plugin_path = next((path for path in candidates if path.exists()), None)
        if plugin_path is None:
            return None

        verified, reason = AdToolSourceLifecycleMixin._verify_skill_plugin(
            skill_dir, plugin_path
        )
        if not verified:
            logger.error("拒绝加载 Skill plugin %s: %s", plugin_path, reason)
            return None

        module_name = "ad_agent_skill_" + hashlib.sha256(
            str(plugin_path.resolve()).encode("utf-8")
        ).hexdigest()[:16]
        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            factory = getattr(module, "create_skill", None)
            if not callable(factory):
                logger.warning("Skill plugin %s 缺少 create_skill(api_client)", plugin_path)
                return None
            skill = factory(api_client)
            if not (
                skill is not None
                and callable(getattr(skill, "get_tools", None))
                and callable(getattr(skill, "get_tool_handler", None))
            ):
                logger.warning("Skill plugin %s 未返回可执行 Core Skill", plugin_path)
                return None
            return skill
        except Exception as exc:
            logger.warning("加载 Skill plugin %s 失败: %s", plugin_path, exc)
            return None

    @_serialize_skill_lifecycle
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
        skill_key = str(getattr(skill, "name", "") or platform)
        if skill_key in self._skill_tool_names:
            logger.info(f"ⓘ Skill '{skill_key}' 已加载，跳过")
            return True

        try:
            return bool(self.register_skill(skill, platform, api_client))
        except Exception as e:
            logger.error(f"❌ 加载 Skill '{platform}' 失败: {e}")
            return False

    @_serialize_skill_lifecycle
    def unload_skill(self, platform: str, skill_name: Optional[str] = None) -> bool:
        """
        卸载指定平台的 Skill 工具。

        Args:
            platform: 平台名称

        Returns:
            是否卸载成功
        """
        canonical_namespace = self._canonical_platform(platform)
        candidates = list(self._skill_keys_by_platform.get(canonical_namespace, []))
        if not candidates:
            return True

        target_key = ""
        tool_names: list[str] = []
        registry_snapshot = None
        parameter_snapshot = None
        blueprint_snapshot = None
        loaded_skill_snapshot = None
        context_snapshot = None
        try:
            if skill_name:
                if skill_name not in candidates:
                    return False
                target_key = skill_name
            else:
                target_key = candidates[0]
            tool_names = list(self._skill_tool_names.get(target_key, []))
            target_skill = self._skill_objects.get(target_key)
            registry_snapshot = self.registry._snapshot_tools(
                tool_names,
                _execution_token=self._registry_execution_token,
            )
            parameter_snapshot = self.parameter_catalogs.snapshot()
            blueprint_snapshot = self.creation_blueprints.snapshot()
            loaded_skill_snapshot = self.skill_loader.snapshot()
            skill_tool_snapshot = {
                key: list(value) for key, value in self._skill_tool_names.items()
            }
            skill_namespace_snapshot = dict(self._skill_namespaces)
            skill_object_snapshot = dict(self._skill_objects)
            skill_keys_snapshot = {
                key: list(value) for key, value in self._skill_keys_by_platform.items()
            }
            skill_format_snapshot = {
                key: set(value) for key, value in self._skill_format_ids.items()
            }
            format_catalog_snapshot = copy.deepcopy(self.ad_format_catalogs)
            context_service = getattr(self, "_context_service", None)
            if callable(context_service):
                context_snapshot = context_service().snapshot()

            # Use the registry's locking/unregister seam instead of mutating
            # private indexes directly.
            for name in dict.fromkeys(tool_names):
                self.registry.unregister(name)
            self.parameter_catalogs.remove_tools(tool_names)
            format_ids = self._skill_format_ids.pop(target_key, set())
            if format_ids:
                self.ad_format_catalogs[canonical_namespace] = [
                    entry for entry in self.ad_format_catalogs.get(canonical_namespace, [])
                    if str(entry.get("format_id")) not in format_ids
                ]
                if not self.ad_format_catalogs[canonical_namespace]:
                    self.ad_format_catalogs.pop(canonical_namespace, None)
            self._skill_tool_names.pop(target_key, None)
            self._skill_namespaces.pop(target_key, None)
            self._skill_objects.pop(target_key, None)
            if target_skill is not None:
                self.skill_loader.unload(getattr(target_skill, "name", ""))

            remaining = [key for key in candidates if key != target_key]
            if remaining:
                self._skill_keys_by_platform[canonical_namespace] = remaining
            else:
                self._skill_keys_by_platform.pop(canonical_namespace, None)
                # Blueprints are owned by the provider Tool Source. Remove
                # them only after the final Skill for that platform is gone.
                self.creation_blueprints.remove_owner(canonical_namespace)

            self._refresh_parser_catalog()
            # Keep the lifecycle record until every derived index has been
            # refreshed. If this final operation fails, the rollback below
            # can leave the PluginRegistry untouched.
            self.plugin_registry.unregister(f"skill:{target_key}")
            logger.info(
                "✅ 已卸载 Skill '%s' (platform=%s)，移除 %s 个工具",
                target_key, canonical_namespace, len(set(tool_names)),
            )
            return True
        except Exception as e:
            logger.error(f"❌ 卸载 Skill '{platform}' 失败: {e}")
            try:
                if target_key:
                    self.registry._restore_tools(
                        registry_snapshot,
                        _execution_token=self._registry_execution_token,
                    )
                    self.parameter_catalogs.restore(parameter_snapshot)
                    self.creation_blueprints.restore(blueprint_snapshot)
                    self.skill_loader.restore(loaded_skill_snapshot)
                    self._skill_tool_names = skill_tool_snapshot
                    self._skill_namespaces = skill_namespace_snapshot
                    self._skill_objects = skill_object_snapshot
                    self._skill_keys_by_platform = skill_keys_snapshot
                    self._skill_format_ids = skill_format_snapshot
                    self.ad_format_catalogs = format_catalog_snapshot
                    if context_snapshot is not None:
                        context_service = getattr(self, "_context_service", None)
                        if callable(context_service):
                            context_service().restore(context_snapshot)
                    self._refresh_parser_catalog()
            except Exception:
                logger.exception(
                    "❌ Skill '%s' 卸载回滚失败，Runtime 需要重新加载",
                    target_key or platform,
                )
            return False

    def get_loaded_skills(self) -> dict[str, Skill]:
        """Return every active Skill keyed by its declared Skill name."""
        return self._skill_objects.copy()

    def get_available_skills(self) -> dict[str, Skill]:
        """获取所有可用的 Skills（包括未加载的）"""
        for skill_dir in self.skill_loader.iter_skill_dirs():
            try:
                self.skill_loader.load_skill_dir(skill_dir)
            except Exception as exc:
                logger.debug("加载可用 Skill 失败 %s: %s", skill_dir, exc)
        return self.skill_loader.list_all()

    def _load_required_skills(self, platforms: list[str]) -> None:
        """
        根据平台列表动态加载对应的 Skill 工具。

        Args:
            platforms: 需要加载的平台列表
        """
        if not platforms:
            return

        for platform in platforms:
            actual_platform = self._canonical_platform(platform)

            if self._skill_keys_by_platform.get(actual_platform):
                continue  # 已加载，跳过

            # 查找对应的 Skill
            skill = self._find_skill_by_platform(actual_platform)
            if not skill:
                logger.warning(f"未找到平台 '{actual_platform}' 的 Skill 定义")
                continue

            # 获取 API 客户端
            api_client = self._get_api_client(platform)

            # 加载 Skill
            self.load_skill(actual_platform, skill, api_client)

    def _find_skill_by_platform(self, platform: str) -> 'Skill':
        """
        根据平台名称查找对应的 Skill。
        """
        canonical_namespace = self._canonical_platform(platform)
        for skill_key in self._skill_keys_by_platform.get(canonical_namespace, []):
            skill = self._skill_objects.get(skill_key)
            if skill is not None:
                return skill

        # SkillLoader owns recursive discovery and package validation.  Runtime
        # only asks for the loaded package by its declared platform; it does not
        # parse another copy of SKILL.md or inspect loader internals.
        candidates = self.skill_loader.get_by_namespace(canonical_namespace)
        if candidates:
            return candidates[0]
        return None

    def set_credentials(self, credentials: dict) -> None:
        """设置凭证，仅保存在进程内；绝不据此修改账户白名单。

        白名单必须来自受控配置文件，不能由线上凭证中的 account/customer ID
        自动扩大，否则会把凭证范围误当成允许操作范围。
        """
        self._credentials = copy.deepcopy(credentials or {})
        self._refresh_unbound_clients()

    def _refresh_unbound_clients(self) -> None:
        """Attach configured clients to handlers that are still offline.

        This makes ``runtime.set_credentials(...)`` and
        ``runtime.run(credentials=...)`` useful even when Tool Sources were
        registered first.  Explicitly injected clients are left untouched.
        Client construction itself is side-effect free; network access only
        occurs when a read Handler is actually executed.
        """
        if not self._credentials:
            return
        clients: dict[str, Any] = {}
        for tool_def in self.registry.list_all():
            try:
                _, handler = self._get_registered_tool(tool_def.name)
            except KeyError:
                continue
            if not hasattr(handler, "client") or getattr(handler, "client") is not None:
                continue
            platform = self._canonical_platform(tool_def.namespace)
            if platform not in clients:
                clients[platform] = self._get_api_client(platform)
            client = clients[platform]
            if client is not None:
                handler.client = client

    def _get_api_client(self, platform: str):
        """获取指定平台的 API 客户端"""
        if not self._credentials:
            return None

        # Keep provider construction in one side-effect-free factory.  The
        # previous implementation duplicated this map in Runtime and could
        # drift from the CLI/server construction path.
        credentials = self._credentials_for_platform(platform)
        if not credentials:
            return None

        try:
            return self.provider_bindings.create_client(platform, credentials)
        except Exception as e:
            logger.debug(f"创建 {platform} API Client 失败: {e}")

        return None

    def _credentials_for_platform(
        self, platform: str, credentials: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Resolve credentials by the same canonical platform identity.

        Credential dictionaries are request/application configuration, not a
        second provider registry.  Normalizing their keys lets a newly added
        Tool Source use its own platform ID without adding another Runtime
        branch.  The returned value is copied so callers cannot mutate the
        request envelope through a Client constructor.
        """
        source = credentials if credentials is not None else self._credentials
        if not isinstance(source, Mapping):
            return {}
        wanted = self._resolve_platform_identifier(platform)
        for key, value in source.items():
            # Credential keys are deployment-facing aliases (for example
            # ``google``), while Tool/Tool Source identity may be
            # ``google-ads``. Resolve both through the active Skill metadata
            # so the Runtime does not grow a provider catalogue or a Google
            # specific branch.
            if (
                self._resolve_platform_identifier(str(key)) == wanted
                and isinstance(value, dict)
            ):
                return copy.deepcopy(value)
        return {}

    @staticmethod
    def _discover_tool_source(platform: str, api_client: Any = None) -> Any:
        """Discover a built-in Tool Source by package convention.

        This keeps adding a provider out of the central Router and factory
        table. A channel package only needs
        ``tools/providers/<platform>/provider.py`` and a
        ``create_<platform>_tool_source`` factory. Custom channels can instead
        expose executable Tools from their Skill plugin.
        """
        return ProviderBindings.discover_tool_source(platform, api_client)

    def _build_request_clients(self, credentials: Optional[dict]) -> dict[str, Any]:
        """Build per-request clients without replacing shared handlers.

        ``run(credentials=...)`` is request-scoped input. Mutating the
        Runtime's global credential/client state here would allow one user to
        affect another user's request, so these clients are passed through a
        copied Handler at execution time instead.
        """
        if not credentials:
            return {}
        clients: dict[str, Any] = {}
        for raw_platform in credentials:
            platform = self._resolve_platform_identifier(str(raw_platform))
            provider_credentials = self._credentials_for_platform(platform, credentials)
            if not provider_credentials:
                continue
            try:
                client = self.provider_bindings.create_client(
                    platform, provider_credentials
                )
                if client is not None:
                    clients[platform] = client
            except Exception as exc:
                logger.warning("创建请求级 %s client 失败: %s", platform, exc)
        return clients

    def _execute_registered_tool(
        self, ctx: ToolContext, tool_name: str, input_data: dict,
    ) -> ToolResult:
        """Execute through the registry's Runtime-only authorized seam."""
        execute = getattr(self.registry, "execute_authorized", None)
        if callable(execute):
            return execute(
                ctx, tool_name, input_data,
                _execution_token=self._registry_execution_token,
            )
        return self.registry.execute(ctx, tool_name, input_data)

    def _get_registered_tool(self, tool_name: str):
        """Get a raw tool tuple only through Runtime's guarded seam."""
        getter = getattr(self.registry, "get_authorized", None)
        if callable(getter):
            return getter(tool_name, self._registry_execution_token)
        return self.registry.get(tool_name)

    def auto_load_skills(
        self,
        skills_root: str,
        credentials: dict = None,
        *,
        allow_executable_plugins: bool = False,
        allow_provider_tool_discovery: bool = False,
    ) -> int:
        """
        自动加载 skills 目录下的所有 Skills。

        策略：
        1. 按标准 Agent Skill 约定发现所有包含 SKILL.md 的目录（可在根目录或任意层级）
        2. 业务上下文 Skill 只作为策略上下文，不注册执行工具
        3. 只有受信部署根显式允许时，插件 Skill 才能注册工具
        4. 只有受信部署根显式允许时，渠道 Skill 才能发现 Tool Source
        5. 其他 Skill 只保留为自然语言上下文，不会因文件名或 workflow.yaml 变成工具

        Args:
            skills_root: Skills 根目录路径
            credentials: API 凭证配置
            allow_executable_plugins: 是否允许导入受信插件代码；用户上传目录必须为 False。
            allow_provider_tool_discovery: 是否允许从该目录发现内置渠道 Tool Source。

        Returns:
            成功加载的 Skill 数量
        """
        loaded_count = 0
        # Reuse credentials previously installed through set_credentials()
        # when callers do not repeat them during Skill discovery. Passing an
        # explicit empty mapping still means intentionally no provider creds.
        credentials = self._credentials if credentials is None else credentials
        credentials = credentials or {}
        # 保存凭证配置
        if credentials:
            self._credentials = copy.deepcopy(credentials)

        # Keep automatic discovery on the same canonical SkillLoader used by
        # normal Runtime initialization. This publishes aliases and expert
        # context from the user's root as well; the executable plugin or
        # Tool Source is still the only source of Tools below.
        self.skill_loader.add_root(skills_root)
        self.skill_loader.load_all()

        # SkillLoader is the single source of truth for standard directory
        # discovery.  Do not infer behavior from a parent folder name: a
        # packaged Skill can be mounted at the root or nested arbitrarily.
        # Only scan the root explicitly requested by this call.  The Runtime
        # may also have its built-in Skill root registered; including it here
        # would make a caller's temporary/managed root unexpectedly register
        # all built-in Tool Sources a second time.
        for skill_dir in self.skill_loader.iter_skill_dirs([skills_root]):
            try:
                    # SkillLoader owns SKILL.md parsing, standard frontmatter,
                    # duplicate detection and malformed-package isolation.
                    # Runtime consumes the validated package instead of
                    # maintaining a second YAML parser for the same contract.
                    loaded_skill = self.skill_loader.load_skill_dir(skill_dir)
                    if loaded_skill is None or bool(getattr(loaded_skill, "context_only", False)):
                        continue
                    platform = loaded_skill.namespace

                    # Loading SKILL.md supplies bounded expert context. It
                    # does not register routes or executable workflow steps.

                    # Executable extensions take precedence over declarative
                    # Skill metadata.  A plugin is still
                    # subject to the same registry, schema, account and write
                    # gates as built-in Tool Sources.
                    api_client = None
                    # Advisory/user-managed roots must not even receive a
                    # Provider client. Credentials and client construction
                    # belong only to the trusted deployment path.
                    provider_credentials = (
                        self._credentials_for_platform(platform, credentials)
                        if (allow_executable_plugins or allow_provider_tool_discovery)
                        else {}
                    )
                    if provider_credentials and (
                        allow_executable_plugins or allow_provider_tool_discovery
                    ):
                        try:
                            api_client = self.provider_bindings.create_client(
                                platform, provider_credentials
                            )
                        except Exception as e:
                            logger.debug(f"创建 {platform} API Client 失败: {e}")
                    plugin_skill = (
                        self._load_skill_plugin(skill_dir, api_client)
                        if allow_executable_plugins else None
                    )
                    if plugin_skill is not None:
                        before_tool_count = len(self.registry.list_all())
                        registered = self.register_skill(
                            plugin_skill, platform, api_client
                        )
                        if not registered:
                            logger.warning(
                                "⚠️ Skill plugin '%s' 未注册任何可执行工具",
                                plugin_skill.name,
                            )
                            continue
                        loaded_count += 1
                        logger.info(
                            f"✅ 自动加载 Skill plugin: {plugin_skill.name} ({platform}, "
                            f"{len(self.registry.list_all()) - before_tool_count} executable tools)"
                        )
                        continue

                    # Channel tool_source discovery is based on package
                    # convention, not on a parent directory name or a
                    # Markdown table. Context-only Skills remain
                    # context-only because their frontmatter is handled by
                    # SkillContract as ``context_only`` and never reaches
                    # this loop.
                    try:
                        if not allow_provider_tool_discovery:
                            continue
                        canonical = self._canonical_platform(platform)
                        tool_source = self._discover_tool_source(canonical, api_client)
                        if tool_source is None:
                            tool_source = self.provider_bindings.create_tool_source(
                                canonical, api_client
                            )
                        before_tool_count = len(self.registry.list_all())
                        self.register_provider_tool_source(tool_source)
                        registered_count = len(self.registry.list_all()) - before_tool_count
                        if registered_count <= 0:
                            logger.warning(
                                "⚠️ Tool Source '%s' 未注册任何可执行工具",
                                canonical,
                            )
                            continue
                        loaded_count += 1
                        logger.info(
                            "✅ 自动加载 Tool Source: %s (%s, %s executable tools)",
                            platform,
                            platform,
                            registered_count,
                        )
                    except ValueError:
                        # A normal advisory Skill may have no executable
                        # Tool Source. That is expected and must not make a
                        # package layout convention mandatory.
                        logger.debug("未找到平台 Tool Source: %s", platform)
            except Exception as e:
                logger.warning(f"⚠️ 解析 Skill {skill_dir.name}/SKILL.md 失败: {e}")

        logger.info(f"✅ 自动加载完成，共加载 {loaded_count} 个 Skills")
        return loaded_count
