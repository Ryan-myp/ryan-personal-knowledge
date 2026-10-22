"""Encrypted deployment settings for model and advertising credentials."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken

from agents.tools.creative_media.models import (
    FREE_AGNES_MEDIA_MODELS,
    profile_supports_free_media_model,
    public_media_model_catalog,
    validate_free_media_configuration,
)


_WEB_SEARCH_PROVIDERS = frozenset({"duckduckgo", "brave"})
_MODEL_PURPOSES = frozenset({
    "chat",
    "knowledge_embedding",
    "image_generation",
    "video_generation",
})


class SettingsVaultError(RuntimeError):
    """The encrypted settings store is unavailable or cannot be trusted."""


class EncryptedSettingsVault:
    """Small encrypted file store for deployment-owned secrets."""

    def __init__(
        self,
        path: Path,
        *,
        key_path: Path | None = None,
        encryption_key: str | bytes | None = None,
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.key_path = (
            Path(key_path).expanduser().resolve()
            if key_path is not None
            else self.path.with_suffix(".key")
        )
        configured_key = encryption_key
        if configured_key is None:
            configured_key = os.environ.get("AD_AGENT_SETTINGS_ENCRYPTION_KEY")
        if isinstance(configured_key, str):
            configured_key = configured_key.encode("ascii")
        self._configured_key = configured_key
        self._lock = threading.RLock()

    def read(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return {}
            try:
                token = self.path.read_bytes()
                data = json.loads(self._fernet(create_key=False).decrypt(token))
            except (OSError, InvalidToken, ValueError, TypeError) as error:
                raise SettingsVaultError(
                    "encrypted settings are unavailable or invalid"
                ) from error
            if not isinstance(data, dict) or data.get("version") != 1:
                raise SettingsVaultError("encrypted settings version is unsupported")
            return data

    def write(self, data: Mapping[str, Any]) -> None:
        if not isinstance(data, Mapping):
            raise ValueError("settings payload must be an object")
        payload = dict(data)
        payload["version"] = 1
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        with self._lock:
            encrypted = self._fernet(create_key=True).encrypt(encoded)
            self._atomic_write(self.path, encrypted)

    def _fernet(self, *, create_key: bool) -> Fernet:
        key = self._configured_key
        if key is None and self.key_path.is_file():
            try:
                key = self.key_path.read_bytes().strip()
            except OSError as error:
                raise SettingsVaultError(
                    "settings encryption key cannot be read"
                ) from error
        if key is None and create_key:
            key = Fernet.generate_key()
            self._atomic_write(self.key_path, key)
        if key is None:
            raise SettingsVaultError("settings encryption key is missing")
        try:
            return Fernet(key)
        except (TypeError, ValueError) as error:
            raise SettingsVaultError("settings encryption key is invalid") from error

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix=".settings-",
                dir=path.parent,
            )
            try:
                os.fchmod(file_descriptor, 0o600)
                with os.fdopen(file_descriptor, "wb") as output:
                    output.write(content)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary_name, path)
                os.chmod(path, 0o600)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        except OSError as error:
            raise SettingsVaultError("settings could not be written securely") from error


class AgentSettingsService:
    """Validate, persist and apply the active deployment model and credentials."""

    PROVIDER_FIELDS = {
        "meta": frozenset({"access_token", "business_id"}),
        "google": frozenset({
            "access_token",
            "client_id",
            "client_secret",
            "developer_token",
            "login_customer_id",
            "refresh_token",
        }),
        "tiktok": frozenset({"access_token", "app_key", "app_secret", "bc_id"}),
    }
    ENVIRONMENT_PROFILE_ID = "__environment__"
    MAX_SECRET_LENGTH = 8192
    MAX_MODEL_NAME_LENGTH = 160

    def __init__(
        self,
        vault: EncryptedSettingsVault,
        *,
        runtime: Any = None,
        provider_credentials: Mapping[str, Any] | None = None,
        model_defaults: Mapping[str, Any] | None = None,
        model_client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.vault = vault
        self.runtime = runtime
        self.provider_credentials = copy.deepcopy(dict(provider_credentials or {}))
        self.model_defaults = {
            "name": str((model_defaults or {}).get("name") or "环境变量配置"),
            "model": str((model_defaults or {}).get("model") or ""),
            "base_url": str((model_defaults or {}).get("base_url") or ""),
            "api_key": str((model_defaults or {}).get("api_key") or ""),
        }
        self.model_client_factory = model_client_factory or self._create_model_client
        self._lock = threading.RLock()

    @staticmethod
    def _create_model_client(**configuration: str) -> Any:
        from agents.agent_harness.core.llm_client import create_llm_client
        from agents.agent_harness.core.timeouts import DEFAULT_EXECUTION_TIMEOUT_SECONDS

        return create_llm_client(
            **configuration,
            timeout_seconds=DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        )

    def configure(
        self,
        *,
        runtime: Any = None,
        provider_credentials: Mapping[str, Any] | None = None,
        model_defaults: Mapping[str, Any] | None = None,
    ) -> None:
        with self._lock:
            if runtime is not None:
                self.runtime = runtime
            if provider_credentials is not None:
                self.provider_credentials = copy.deepcopy(
                    dict(provider_credentials)
                )
            if model_defaults is not None:
                self.model_defaults = {
                    "name": str(model_defaults.get("name") or "环境变量配置"),
                    "model": str(model_defaults.get("model") or ""),
                    "base_url": str(model_defaults.get("base_url") or ""),
                    "api_key": str(model_defaults.get("api_key") or ""),
                }

    def effective_provider_credentials(self) -> dict[str, Any]:
        return self._effective_provider_credentials(self.vault.read())

    def _effective_provider_credentials(
        self,
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        credentials = copy.deepcopy(self.provider_credentials)
        overrides = state.get("providers", {})
        for provider, fields in overrides.items():
            if provider not in self.PROVIDER_FIELDS or not isinstance(fields, dict):
                continue
            current = credentials.setdefault(provider, {})
            if not isinstance(current, dict):
                current = {}
                credentials[provider] = current
            for field, value in fields.items():
                if value is None:
                    current.pop(field, None)
                else:
                    current[field] = value
            if not current:
                credentials.pop(provider, None)
        return credentials

    def active_model_configuration(self) -> dict[str, str]:
        """Return the active conversational model configuration."""
        return self.model_configuration_for("chat")

    def model_configuration_for(self, purpose: str) -> dict[str, str]:
        """Resolve a secret model configuration without exposing it in snapshots."""
        purpose = self._model_purpose(purpose)
        state = self.vault.read()
        profiles = state.get("models", [])
        active_id = self._active_model_profiles(state).get(purpose)
        profile = next(
            (
                item for item in profiles
                if (
                    isinstance(item, dict)
                    and item.get("id") == active_id
                    and self._profile_purpose(item) == purpose
                )
            ),
            None,
        )
        if profile is None:
            return copy.deepcopy(self.model_defaults) if purpose == "chat" else {}
        base_url = str(profile.get("base_url") or "")
        if purpose in FREE_AGNES_MEDIA_MODELS:
            try:
                base_url = validate_free_media_configuration(
                    purpose,
                    profile.get("model"),
                    base_url,
                )
            except ValueError:
                return {}
        return {
            "name": str(profile.get("name") or ""),
            "model": str(profile.get("model") or ""),
            "base_url": base_url,
            "api_key": str(profile.get("api_key") or ""),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            state = self.vault.read()
            return {
                "models": self._model_snapshot(state),
                "media_model_catalog": public_media_model_catalog(),
                "providers": self._provider_snapshot(state),
                "web_search": self._web_search_snapshot(state),
            }

    def _model_snapshot(self, state: Mapping[str, Any]) -> dict[str, Any]:
        safe_profiles = [
            self._safe_profile(item)
            for item in state.get("models", [])
            if isinstance(item, dict) and item.get("id")
        ]
        active_profiles = self._active_model_profiles(state)
        active_id = active_profiles.get("chat")
        active = next((
            item for item in safe_profiles
            if item["id"] == active_id and item["purpose"] == "chat"
        ), None)
        if active is None:
            active_id = self.ENVIRONMENT_PROFILE_ID
            active = {
                "id": active_id,
                "name": self.model_defaults["name"],
                "model": self.model_defaults["model"],
                "base_url": self.model_defaults["base_url"],
                "api_key_configured": bool(self.model_defaults["api_key"]),
                "source": "environment",
                "purpose": "chat",
                "active": True,
            }
        else:
            active["active"] = True
        environment_profile = self._environment_model_profile(active_id)
        profiles = [environment_profile]
        profiles.extend(
            item for item in safe_profiles
            if item["id"] != self.ENVIRONMENT_PROFILE_ID
        )
        resolved_active_profiles = {
            purpose: active_profiles.get(purpose)
            for purpose in sorted(_MODEL_PURPOSES)
        }
        resolved_active_profiles["chat"] = active_id
        for profile in profiles:
            purpose = profile["purpose"]
            profile["active"] = profile["id"] == resolved_active_profiles.get(
                purpose
            )
        return {
            "active_profile_id": active_id,
            "active_profiles": resolved_active_profiles,
            "active": active,
            "profiles": profiles,
        }

    def _environment_model_profile(self, active_id: str) -> dict[str, Any]:
        return {
            "id": self.ENVIRONMENT_PROFILE_ID,
            "name": self.model_defaults["name"],
            "model": self.model_defaults["model"],
            "base_url": self.model_defaults["base_url"],
            "api_key_configured": bool(self.model_defaults["api_key"]),
            "source": "environment",
            "purpose": "chat",
            "active": active_id == self.ENVIRONMENT_PROFILE_ID,
        }

    def _provider_snapshot(self, state: Mapping[str, Any]) -> dict[str, Any]:
        credentials = self._effective_provider_credentials(state)
        return {
            provider: {
                "fields": {
                    field: bool(
                        isinstance(credentials.get(provider), dict)
                        and credentials[provider].get(field)
                    )
                    for field in sorted(allowed_fields)
                }
            }
            for provider, allowed_fields in self.PROVIDER_FIELDS.items()
        }

    def web_search_configuration(self) -> dict[str, str]:
        """Resolve the selected search backend and its private configuration."""
        with self._lock:
            return self._web_search_configuration(self.vault.read())

    def _web_search_snapshot(self, state: Mapping[str, Any]) -> dict[str, Any]:
        configuration = self._web_search_configuration(state)
        provider = configuration["provider"]
        requires_api_key = provider == "brave"
        provider_source = self._web_search_provider_source(state)
        source = (
            configuration["api_key_source"]
            if requires_api_key and configuration["api_key"]
            else "in_process" if provider == "duckduckgo" else ""
        )
        return {
            "backend": provider,
            "provider": "DuckDuckGo" if provider == "duckduckgo" else "Brave Search",
            "requires_api_key": requires_api_key,
            "api_key_configured": (
                requires_api_key and bool(configuration["api_key"])
            ),
            "source": source,
            "provider_source": provider_source,
        }

    @staticmethod
    def _web_search_provider_source(state: Mapping[str, Any]) -> str:
        if os.environ.get("WEB_SEARCH_PROVIDER", "").strip():
            return "environment"
        settings = state.get("web_search")
        settings = settings if isinstance(settings, Mapping) else {}
        return "vault" if settings.get("provider") else "default"

    @staticmethod
    def _web_search_configuration(state: Mapping[str, Any]) -> dict[str, str]:
        settings = state.get("web_search")
        settings = settings if isinstance(settings, Mapping) else {}
        provider = (
            os.environ.get("WEB_SEARCH_PROVIDER", "").strip().lower()
            or str(settings.get("provider") or "duckduckgo").strip().lower()
        )
        if provider not in _WEB_SEARCH_PROVIDERS:
            provider = "duckduckgo"
        api_key = settings.get("api_key")
        api_key_source = "vault" if isinstance(api_key, str) and api_key.strip() else ""
        if not api_key_source:
            api_key = os.environ.get("BRAVE_API_KEY", "").strip()
            api_key_source = "environment" if api_key else ""
        return {
            "provider": provider,
            "api_key": api_key.strip() if isinstance(api_key, str) else "",
            "api_key_source": api_key_source,
        }

    def update_web_search_credentials(
        self,
        *,
        provider: str | None = None,
        api_key: str = "",
        clear: bool = False,
    ) -> dict[str, Any]:
        """Select a search backend and optionally store or clear its key."""
        if not isinstance(clear, bool):
            raise ValueError("clear must be a boolean")
        cleaned_provider = None
        if provider is not None:
            cleaned_provider = str(provider).strip().lower()
            if cleaned_provider not in _WEB_SEARCH_PROVIDERS:
                raise ValueError("unsupported web-search provider")
        if api_key not in (None, ""):
            cleaned_key = self._clean_secret(api_key, "api_key")
        else:
            cleaned_key = ""
        if clear and cleaned_key:
            raise ValueError("the API key cannot be updated and cleared")

        with self._lock:
            if cleaned_provider is None and not cleaned_key and not clear:
                return self.snapshot()
            previous = self.vault.read()
            next_state = copy.deepcopy(previous)
            web_search = next_state.setdefault("web_search", {})
            if not isinstance(web_search, dict):
                web_search = {}
                next_state["web_search"] = web_search
            if cleaned_provider is not None:
                web_search["provider"] = cleaned_provider
            if cleaned_key or clear:
                web_search["api_key"] = None if clear else cleaned_key
            self.vault.write(next_state)
            return self.snapshot()

    def update_provider_credentials(
        self,
        provider: str,
        fields: Mapping[str, str],
        *,
        clear_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        provider = str(provider or "").strip().lower()
        if provider not in self.PROVIDER_FIELDS:
            raise ValueError("unsupported advertising provider")
        if not isinstance(fields, Mapping):
            raise ValueError("credential fields must be an object")
        clear = set(clear_fields or [])
        allowed = self.PROVIDER_FIELDS[provider]
        if set(fields) - allowed or clear - allowed:
            raise ValueError("unsupported credential field")
        cleaned = {
            field: self._clean_secret(value, field)
            for field, value in fields.items()
            if value not in (None, "")
        }
        if set(cleaned) & clear:
            raise ValueError("a credential field cannot be updated and cleared")

        with self._lock:
            previous = self.vault.read()
            next_state = copy.deepcopy(previous)
            overrides = next_state.setdefault("providers", {})
            provider_overrides = overrides.setdefault(provider, {})
            provider_overrides.update(cleaned)
            provider_overrides.update({field: None for field in clear})
            def apply_credentials() -> None:
                if self.runtime is not None:
                    self.runtime.set_credentials(
                        self.effective_provider_credentials()
                    )

            self._commit_and_apply(
                previous,
                next_state,
                apply_credentials,
                "provider credentials could not be applied",
            )
            return self.snapshot()

    def save_model_profile(
        self,
        *,
        name: str,
        model: str,
        base_url: str,
        api_key: str,
        purpose: str = "chat",
        profile_id: str | None = None,
    ) -> str:
        purpose = self._model_purpose(purpose)
        cleaned_name = self._bounded_text(name, "name", 80)
        cleaned_model = self._bounded_text(
            model, "model", self.MAX_MODEL_NAME_LENGTH
        )
        cleaned_url = self._validate_base_url(base_url)
        cleaned_key = self._clean_secret(api_key, "api_key") if api_key else ""
        with self._lock:
            if self.runtime is None:
                raise RuntimeError("agent runtime is not ready")
            previous = self.vault.read()
            state = copy.deepcopy(previous)
            resolved_id, cleaned_key = self._merge_model_profile(
                state,
                profile_id=profile_id,
                name=cleaned_name,
                model=cleaned_model,
                base_url=cleaned_url,
                api_key=cleaned_key,
                purpose=purpose,
            )
            client = (
                self.model_client_factory(
                    model=cleaned_model,
                    api_key=cleaned_key,
                    base_url=cleaned_url or None,
                )
                if purpose == "chat"
                else None
            )
            self._commit_and_apply(
                previous,
                state,
                (
                    lambda: self.runtime.inject_llm(client)
                    if client is not None else None
                ),
                "model configuration could not be applied",
            )
            return resolved_id

    def _merge_model_profile(
        self,
        state: dict[str, Any],
        *,
        profile_id: str | None,
        name: str,
        model: str,
        base_url: str,
        api_key: str,
        purpose: str,
    ) -> tuple[str, str]:
        profiles = state.setdefault("models", [])
        existing = next(
            (
                item for item in profiles
                if isinstance(item, dict) and item.get("id") == profile_id
            ),
            None,
        ) if profile_id else None
        if profile_id and existing is None:
            raise ValueError("model profile does not exist")
        if existing is not None and self._profile_purpose(existing) != purpose:
            raise ValueError("model profile purpose cannot be changed")
        if purpose in FREE_AGNES_MEDIA_MODELS:
            base_url = validate_free_media_configuration(
                purpose,
                model,
                base_url,
            )
        if existing is None and not api_key:
            raise ValueError("a new model profile requires an API key")
        resolved_key = api_key or str((existing or {}).get("api_key") or "")
        if not resolved_key:
            raise ValueError("model API key is not configured")
        resolved_id = profile_id or uuid.uuid4().hex
        profile = {
            "id": resolved_id,
            "name": name,
            "model": model,
            "base_url": base_url,
            "api_key": resolved_key,
            "purpose": purpose,
        }
        if existing is None:
            profiles.append(profile)
        else:
            profiles[profiles.index(existing)] = profile
        active_profiles = self._active_model_profiles(state)
        active_profiles[purpose] = resolved_id
        state["active_model_profiles"] = active_profiles
        if purpose == "chat":
            state["active_model_profile_id"] = resolved_id
        return resolved_id, resolved_key

    def _commit_and_apply(
        self,
        previous: Mapping[str, Any],
        next_state: Mapping[str, Any],
        apply: Callable[[], None],
        failure_message: str,
    ) -> None:
        try:
            self.vault.write(next_state)
            apply()
        except Exception as error:
            self.vault.write(previous)
            raise RuntimeError(failure_message) from error

    def activate_model_profile(self, profile_id: str) -> None:
        with self._lock:
            if profile_id == self.ENVIRONMENT_PROFILE_ID:
                if self.runtime is None:
                    raise RuntimeError("agent runtime is not ready")
                configuration = copy.deepcopy(self.model_defaults)
                purpose = "chat"
            else:
                state = self.vault.read()
                profile = next(
                    (
                        item for item in state.get("models", [])
                        if isinstance(item, dict) and item.get("id") == profile_id
                    ),
                    None,
                )
                if profile is None:
                    raise ValueError("model profile does not exist")
                purpose = self._profile_purpose(profile)
                if purpose in FREE_AGNES_MEDIA_MODELS:
                    validate_free_media_configuration(
                        purpose,
                        profile.get("model"),
                        profile.get("base_url"),
                    )
                configuration = {
                    "model": profile["model"],
                    "api_key": profile["api_key"],
                    "base_url": profile["base_url"] or None,
                }
            if purpose == "chat" and self.runtime is None:
                raise RuntimeError("agent runtime is not ready")
            if not configuration.get("api_key"):
                raise ValueError("model API key is not configured")
            client = (
                self.model_client_factory(
                    model=configuration["model"],
                    api_key=configuration["api_key"],
                    base_url=configuration.get("base_url") or None,
                )
                if purpose == "chat"
                else None
            )
            previous = self.vault.read()
            next_state = copy.deepcopy(previous)
            active_profiles = self._active_model_profiles(next_state)
            if profile_id == self.ENVIRONMENT_PROFILE_ID:
                next_state.pop("active_model_profile_id", None)
                active_profiles.pop("chat", None)
            else:
                active_profiles[purpose] = profile_id
                if purpose == "chat":
                    next_state["active_model_profile_id"] = profile_id
            next_state["active_model_profiles"] = active_profiles
            self._commit_and_apply(
                previous,
                next_state,
                (
                    lambda: self.runtime.inject_llm(client)
                    if client is not None else None
                ),
                "model profile could not be activated",
            )

    def delete_model_profile(self, profile_id: str) -> None:
        with self._lock:
            state = self.vault.read()
            if profile_id in self._active_model_profiles(state).values():
                raise ValueError("cannot delete the active model profile")
            profiles = state.get("models", [])
            retained = [
                item for item in profiles
                if not isinstance(item, dict) or item.get("id") != profile_id
            ]
            if len(retained) == len(profiles):
                raise ValueError("model profile does not exist")
            state["models"] = retained
            self.vault.write(state)

    def _safe_profile(self, profile: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": str(profile.get("id") or ""),
            "name": str(profile.get("name") or ""),
            "model": str(profile.get("model") or ""),
            "base_url": str(profile.get("base_url") or ""),
            "purpose": self._profile_purpose(profile),
            "supported": self._profile_supports_free_media(profile),
            "api_key_configured": bool(profile.get("api_key")),
            "source": "vault",
            "active": False,
        }

    @staticmethod
    def _model_purpose(value: Any) -> str:
        purpose = str(value or "chat").strip().lower()
        if purpose not in _MODEL_PURPOSES:
            raise ValueError("unsupported model purpose")
        return purpose

    @classmethod
    def _profile_purpose(cls, profile: Mapping[str, Any]) -> str:
        return cls._model_purpose(profile.get("purpose", "chat"))

    @classmethod
    def _profile_supports_free_media(cls, profile: Mapping[str, Any]) -> bool:
        purpose = cls._profile_purpose(profile)
        if purpose not in FREE_AGNES_MEDIA_MODELS:
            return True
        if not profile_supports_free_media_model(profile):
            return False
        try:
            validate_free_media_configuration(
                purpose,
                profile.get("model"),
                profile.get("base_url"),
            )
        except ValueError:
            return False
        return True

    @classmethod
    def _active_model_profiles(cls, state: Mapping[str, Any]) -> dict[str, str]:
        configured = state.get("active_model_profiles")
        result = {
            str(purpose): str(profile_id)
            for purpose, profile_id in configured.items()
            if (
                isinstance(configured, Mapping)
                and purpose in _MODEL_PURPOSES
                and isinstance(profile_id, str)
                and profile_id.strip()
            )
        } if isinstance(configured, Mapping) else {}
        legacy_id = state.get("active_model_profile_id")
        if "chat" not in result and isinstance(legacy_id, str) and legacy_id:
            result["chat"] = legacy_id
        return result

    @classmethod
    def _clean_secret(cls, value: Any, field: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be text")
        cleaned = value.strip()
        if len(cleaned) > cls.MAX_SECRET_LENGTH:
            raise ValueError(f"{field} exceeds the maximum length")
        if any(ord(character) < 32 or ord(character) == 127 for character in cleaned):
            raise ValueError(f"{field} contains unsupported control characters")
        return cleaned

    @staticmethod
    def _bounded_text(value: Any, field: str, maximum: int) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be text")
        cleaned = value.strip()
        if not cleaned or len(cleaned) > maximum:
            raise ValueError(f"{field} is empty or exceeds the maximum length")
        if any(ord(character) < 32 or ord(character) == 127 for character in cleaned):
            raise ValueError(f"{field} contains unsupported control characters")
        return cleaned

    @staticmethod
    def _validate_base_url(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("base_url must be text")
        cleaned = value.strip()
        if not cleaned:
            return ""
        if len(cleaned) > 2048:
            raise ValueError("base_url exceeds the maximum length")
        parsed = urlsplit(cleaned)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("base_url must be an HTTP(S) URL without credentials")
        if parsed.scheme == "http" and parsed.hostname.lower() not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("remote model endpoints must use HTTPS")
        try:
            parsed.port
        except ValueError as error:
            raise ValueError("base_url contains an invalid port") from error
        return cleaned.rstrip("/")


__all__ = [
    "AgentSettingsService",
    "EncryptedSettingsVault",
    "SettingsVaultError",
]
