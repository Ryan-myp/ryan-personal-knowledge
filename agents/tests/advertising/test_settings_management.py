from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.deployments.advertising.api.context import ApiContext
from agents.deployments.advertising.api.routes.settings import (
    _require_secure_secret_transport,
    create_settings_router,
)
from agents.deployments.advertising.settings import (
    AgentSettingsService,
    EncryptedSettingsVault,
    SettingsVaultError,
)


def test_model_settings_frontend_lists_free_media_models():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser settings regressions")
    script = (
        Path(__file__).parent
        / "static"
        / "test_chat_settings_models.js"
    )
    result = subprocess.run(
        [node, "--test", str(script)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


class FakeRuntime:
    def __init__(self):
        self.credentials = {}
        self.llm = None

    def set_credentials(self, credentials):
        self.credentials = credentials

    def inject_llm(self, client):
        self.llm = client


def make_service(tmp_path, *, base_credentials=None, model_defaults=None):
    runtime = FakeRuntime()
    vault = EncryptedSettingsVault(
        tmp_path / "settings.vault",
        key_path=tmp_path / "settings.key",
    )
    clients = []

    def model_client_factory(**kwargs):
        client = SimpleNamespace(config=kwargs)
        clients.append(client)
        return client

    service = AgentSettingsService(
        vault,
        runtime=runtime,
        provider_credentials=base_credentials or {},
        model_defaults=model_defaults or {
            "name": "Environment",
            "model": "base-model",
            "base_url": "https://llm.example/v1",
            "api_key": "environment-secret",
        },
        model_client_factory=model_client_factory,
    )
    return service, runtime, vault, clients


def test_vault_encrypts_credentials_and_round_trips(tmp_path):
    vault = EncryptedSettingsVault(
        tmp_path / "settings.vault",
        key_path=tmp_path / "settings.key",
    )

    vault.write({"providers": {"meta": {"access_token": "private-meta-token"}}})

    assert b"private-meta-token" not in (tmp_path / "settings.vault").read_bytes()
    assert vault.read()["providers"]["meta"]["access_token"] == "private-meta-token"
    assert (tmp_path / "settings.key").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "settings.vault").stat().st_mode & 0o777 == 0o600


def test_vault_fails_closed_when_ciphertext_is_tampered(tmp_path):
    vault = EncryptedSettingsVault(
        tmp_path / "settings.vault",
        key_path=tmp_path / "settings.key",
    )
    vault.write({"providers": {}})
    (tmp_path / "settings.vault").write_bytes(b"tampered")

    with pytest.raises(SettingsVaultError):
        vault.read()


def test_vault_write_preserves_existing_parent_directory_permissions(tmp_path):
    directory = tmp_path / "shared-settings"
    directory.mkdir()
    directory.chmod(0o750)
    vault = EncryptedSettingsVault(
        directory / "settings.vault",
        key_path=directory / "settings.key",
    )

    vault.write({"providers": {}})

    assert os.stat(directory).st_mode & 0o777 == 0o750


def test_provider_credentials_update_runtime_without_returning_secrets(tmp_path):
    service, runtime, vault, _clients = make_service(
        tmp_path,
        base_credentials={"meta": {"business_id": "existing-business"}},
    )

    result = service.update_provider_credentials(
        "meta",
        {"access_token": "private-meta-token"},
    )

    assert runtime.credentials["meta"] == {
        "business_id": "existing-business",
        "access_token": "private-meta-token",
    }
    assert result["providers"]["meta"]["fields"] == {
        "access_token": True,
        "business_id": True,
    }
    assert "private-meta-token" not in repr(result)
    assert b"private-meta-token" not in vault.path.read_bytes()


def test_ga4_and_search_console_oauth_credentials_are_separate_and_encrypted(
    tmp_path,
):
    service, runtime, vault, _clients = make_service(
        tmp_path,
        base_credentials={"google": {"refresh_token": "ads-refresh-token"}},
    )

    ga4_result = service.update_provider_credentials("ga4", {
        "client_id": "ga4-client-id",
        "client_secret": "ga4-client-secret",
        "refresh_token": "ga4-refresh-token",
    })
    gsc_result = service.update_provider_credentials("search_console", {
        "client_id": "gsc-client-id",
        "client_secret": "gsc-client-secret",
        "refresh_token": "gsc-refresh-token",
    })

    assert runtime.credentials["google"]["refresh_token"] == "ads-refresh-token"
    assert service.provider_credentials_for("ga4")["refresh_token"] == "ga4-refresh-token"
    assert service.provider_credentials_for("search_console")["refresh_token"] == "gsc-refresh-token"
    assert ga4_result["providers"]["ga4"]["fields"] == {
        "client_id": True,
        "client_secret": True,
        "refresh_token": True,
    }
    assert gsc_result["providers"]["search_console"]["fields"] == {
        "client_id": True,
        "client_secret": True,
        "refresh_token": True,
    }
    assert "ga4-refresh-token" not in repr(ga4_result)
    assert "gsc-refresh-token" not in repr(gsc_result)
    vault_bytes = vault.path.read_bytes()
    assert b"ga4-refresh-token" not in vault_bytes
    assert b"gsc-refresh-token" not in vault_bytes


def test_analytics_provider_rejects_unknown_credential_fields(tmp_path):
    service, _runtime, _vault, _clients = make_service(tmp_path)

    with pytest.raises(ValueError, match="unsupported credential field"):
        service.update_provider_credentials("ga4", {"developer_token": "not-allowed"})


def test_clearing_a_provider_field_removes_the_legacy_value_too(tmp_path):
    service, runtime, _vault, _clients = make_service(
        tmp_path,
        base_credentials={"google": {"developer_token": "legacy-token"}},
    )

    service.update_provider_credentials(
        "google",
        {},
        clear_fields=["developer_token"],
    )

    assert "developer_token" not in runtime.credentials.get("google", {})


def test_model_profile_is_encrypted_redacted_and_applied_immediately(tmp_path):
    service, runtime, vault, clients = make_service(tmp_path)

    profile_id = service.save_model_profile(
        name="Primary",
        model="model-v2",
        base_url="https://llm.example/v1",
        api_key="private-model-token",
    )
    result = service.snapshot()

    assert runtime.llm is clients[-1]
    assert runtime.llm.config == {
        "model": "model-v2",
        "api_key": "private-model-token",
        "base_url": "https://llm.example/v1",
    }
    assert result["models"]["active_profile_id"] == profile_id
    assert result["models"]["profiles"][0]["api_key_configured"] is True
    assert "private-model-token" not in repr(result)
    assert b"private-model-token" not in vault.path.read_bytes()


def test_model_profile_can_be_activated_and_active_profile_cannot_be_deleted(tmp_path):
    service, runtime, _vault, clients = make_service(tmp_path)
    first = service.save_model_profile(
        name="First",
        model="model-one",
        base_url="https://one.example/v1",
        api_key="first-key",
    )
    second = service.save_model_profile(
        name="Second",
        model="model-two",
        base_url="https://two.example/v1",
        api_key="second-key",
    )

    service.activate_model_profile(first)

    assert runtime.llm is clients[-1]
    assert runtime.llm.config["model"] == "model-one"
    with pytest.raises(ValueError, match="active"):
        service.delete_model_profile(first)
    service.delete_model_profile(second)


def test_media_model_profiles_do_not_replace_the_chat_model(tmp_path):
    service, runtime, _vault, clients = make_service(tmp_path)
    chat_profile = service.save_model_profile(
        name="Chat",
        model="chat-model",
        base_url="https://llm.example/v1",
        api_key="chat-key",
    )
    chat_client = runtime.llm

    image_profile = service.save_model_profile(
        name="Image",
        model="agnes-image-2.5-flash",
        base_url="https://apihub.agnes-ai.cn/v1",
        api_key="image-key",
        purpose="image_generation",
    )
    video_profile = service.save_model_profile(
        name="Video",
        model="agnes-video-2.5-flash",
        base_url="https://apihub.agnes-ai.cn/v1",
        api_key="video-key",
        purpose="video_generation",
    )

    assert runtime.llm is chat_client
    assert len(clients) == 1
    assert service.active_model_configuration()["model"] == "chat-model"
    assert service.model_configuration_for("image_generation") == {
        "name": "Image",
        "model": "agnes-image-2.5-flash",
        "base_url": "https://apihub.agnes-ai.cn/v1",
        "api_key": "image-key",
    }
    assert service.model_configuration_for("video_generation")["model"] == (
        "agnes-video-2.5-flash"
    )
    models = service.snapshot()["models"]
    assert models["active_profiles"] == {
        "chat": chat_profile,
        "image_generation": image_profile,
        "video_generation": video_profile,
        "knowledge_embedding": None,
    }
    assert "image-key" not in repr(models)
    assert "video-key" not in repr(models)


def test_model_profiles_cannot_change_purpose_or_delete_while_active(tmp_path):
    service, _runtime, _vault, _clients = make_service(tmp_path)
    profile_id = service.save_model_profile(
        name="Image",
        model="agnes-image-2.5-flash",
        base_url="https://apihub.agnes-ai.cn/v1",
        api_key="image-key",
        purpose="image_generation",
    )

    with pytest.raises(ValueError, match="purpose"):
        service.save_model_profile(
            profile_id=profile_id,
            name="Image",
            model="agnes-image-2.5-flash",
            base_url="https://apihub.agnes-ai.cn/v1",
            api_key="",
            purpose="video_generation",
        )
    with pytest.raises(ValueError, match="active"):
        service.delete_model_profile(profile_id)


@pytest.mark.parametrize(
    ("purpose", "model"),
    [
        ("image_generation", "agnes-image-2.5"),
        ("image_generation", "custom-image-model"),
        ("video_generation", "agnes-video-2.5"),
        ("video_generation", "custom-video-model"),
    ],
)
def test_media_model_profiles_reject_paid_or_unapproved_models(
    tmp_path,
    purpose,
    model,
):
    service, runtime, vault, clients = make_service(tmp_path)

    with pytest.raises(ValueError, match="free Agnes"):
        service.save_model_profile(
            name="Unsupported media model",
            model=model,
            base_url="https://apihub.agnes-ai.cn/v1",
            api_key="media-key",
            purpose=purpose,
        )

    assert runtime.llm is None
    assert vault.read() == {}
    assert clients == []


def test_media_model_profile_defaults_to_official_endpoint_and_catalog_is_public(
    tmp_path,
):
    service, _runtime, _vault, _clients = make_service(tmp_path)

    service.save_model_profile(
        name="Image",
        model="agnes-image-2.5-flash",
        base_url="",
        api_key="image-key",
        purpose="image_generation",
    )

    snapshot = service.snapshot()
    assert service.model_configuration_for("image_generation")["base_url"] == (
        "https://apihub.agnes-ai.cn/v1"
    )
    assert snapshot["media_model_catalog"] == {
        "image_generation": {
            "model": "agnes-image-2.5-flash",
            "name": "Agnes Image 2.5 Flash",
            "availability": "free",
            "base_url": "https://apihub.agnes-ai.cn/v1",
        },
        "video_generation": {
            "model": "agnes-video-2.5-flash",
            "name": "Agnes Video 2.5 Flash",
            "availability": "free_limited_time",
            "base_url": "https://apihub.agnes-ai.cn/v1",
        },
    }


def test_legacy_agnes_com_media_profiles_resolve_to_the_official_cn_endpoint(
    tmp_path,
):
    service, _runtime, vault, _clients = make_service(tmp_path)
    image_id = service.save_model_profile(
        name="Legacy Image",
        model="agnes-image-2.5-flash",
        base_url="https://apihub.agnes-ai.cn/v1",
        api_key="image-key",
        purpose="image_generation",
    )
    video_id = service.save_model_profile(
        name="Legacy Video",
        model="agnes-video-2.5-flash",
        base_url="https://apihub.agnes-ai.cn/v1",
        api_key="video-key",
        purpose="video_generation",
    )
    state = vault.read()
    for profile in state["models"]:
        profile["base_url"] = "https://apihub.agnes-ai.com/v1"
    vault.write(state)

    assert service.model_configuration_for("image_generation") == {
        "name": "Legacy Image",
        "model": "agnes-image-2.5-flash",
        "base_url": "https://apihub.agnes-ai.cn/v1",
        "api_key": "image-key",
    }
    assert service.model_configuration_for("video_generation") == {
        "name": "Legacy Video",
        "model": "agnes-video-2.5-flash",
        "base_url": "https://apihub.agnes-ai.cn/v1",
        "api_key": "video-key",
    }
    profiles = {
        profile["id"]: profile
        for profile in service.snapshot()["models"]["profiles"]
    }
    assert profiles[image_id]["base_url"] == "https://apihub.agnes-ai.cn/v1"
    assert profiles[video_id]["base_url"] == "https://apihub.agnes-ai.cn/v1"
    assert profiles[image_id]["supported"] is True
    assert profiles[video_id]["supported"] is True


def test_media_model_profile_rejects_non_agnes_endpoint(tmp_path):
    service, runtime, vault, clients = make_service(tmp_path)

    with pytest.raises(ValueError, match="official Agnes API URL"):
        service.save_model_profile(
            name="Image",
            model="agnes-image-2.5-flash",
            base_url="https://proxy.example/v1",
            api_key="image-key",
            purpose="image_generation",
        )

    assert runtime.llm is None
    assert vault.read() == {}
    assert clients == []


def test_legacy_paid_media_profile_is_disabled_and_cannot_be_activated(tmp_path):
    service, _runtime, vault, _clients = make_service(tmp_path)
    profile_id = service.save_model_profile(
        name="Image",
        model="agnes-image-2.5-flash",
        base_url="",
        api_key="image-key",
        purpose="image_generation",
    )
    state = vault.read()
    state["models"][0]["model"] = "agnes-image-2.5"
    vault.write(state)

    assert service.model_configuration_for("image_generation") == {}
    profile = next(
        item for item in service.snapshot()["models"]["profiles"]
        if item["id"] == profile_id
    )
    assert profile["supported"] is False
    with pytest.raises(ValueError, match="free Agnes"):
        service.activate_model_profile(profile_id)


def test_legacy_model_profiles_remain_chat_profiles(tmp_path):
    service, runtime, _vault, clients = make_service(tmp_path)
    profile_id = service.save_model_profile(
        name="Legacy Chat",
        model="chat-model",
        base_url="https://llm.example/v1",
        api_key="chat-key",
    )
    state = service.vault.read()
    state["models"][0].pop("purpose")
    state.pop("active_model_profiles", None)
    service.vault.write(state)
    previous_client = runtime.llm

    assert service.model_configuration_for("chat")["model"] == "chat-model"
    assert service.model_configuration_for("image_generation") == {}
    assert service.snapshot()["models"]["active_profiles"] == {
        "chat": profile_id,
        "image_generation": None,
        "video_generation": None,
        "knowledge_embedding": None,
    }
    assert runtime.llm is previous_client
    assert len(clients) == 1


@pytest.mark.parametrize(
    "base_url",
    [
        "file:///etc/passwd",
        "http://user:password@example.com/v1",
        "https://",
    ],
)
def test_model_profile_rejects_unsafe_base_urls(tmp_path, base_url):
    service, runtime, vault, clients = make_service(tmp_path)

    with pytest.raises(ValueError):
        service.save_model_profile(
            name="Unsafe",
            model="model",
            base_url=base_url,
            api_key="private-token",
        )

    assert runtime.llm is None
    assert vault.read() == {}
    assert clients == []


def test_provider_names_and_fields_are_allowlisted(tmp_path):
    service, runtime, _vault, _clients = make_service(tmp_path)

    with pytest.raises(ValueError):
        service.update_provider_credentials("unknown", {"access_token": "token"})
    with pytest.raises(ValueError):
        service.update_provider_credentials("tiktok", {"unexpected": "value"})

    assert runtime.credentials == {}


def test_web_search_key_is_encrypted_and_only_configuration_status_is_exposed(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    service, _runtime, vault, _clients = make_service(tmp_path)

    result = service.update_web_search_credentials(
        provider="brave",
        api_key="private-brave-search-key",
    )

    assert service.web_search_configuration() == {
        "provider": "brave",
        "api_key": "private-brave-search-key",
        "api_key_source": "vault",
    }
    assert result["web_search"] == {
        "backend": "brave",
        "provider": "Brave Search",
        "requires_api_key": True,
        "api_key_configured": True,
        "source": "vault",
        "provider_source": "vault",
    }
    assert "private-brave-search-key" not in repr(result)
    assert b"private-brave-search-key" not in vault.path.read_bytes()

    service.update_web_search_credentials(clear=True)
    assert service.web_search_configuration()["api_key"] == ""
    assert service.snapshot()["web_search"]["api_key_configured"] is False


def test_web_search_key_uses_environment_as_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "environment-brave-key")
    service, _runtime, _vault, _clients = make_service(tmp_path)

    service.update_web_search_credentials(provider="brave")

    assert service.web_search_configuration()["api_key"] == (
        "environment-brave-key"
    )
    assert service.snapshot()["web_search"] == {
        "backend": "brave",
        "provider": "Brave Search",
        "requires_api_key": True,
        "api_key_configured": True,
        "source": "environment",
        "provider_source": "vault",
    }

    service.update_web_search_credentials(api_key="vault-brave-key")
    assert service.web_search_configuration()["api_key"] == "vault-brave-key"
    assert service.snapshot()["web_search"]["source"] == "vault"


def test_web_search_defaults_to_keyless_duckduckgo(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("WEB_SEARCH_PROVIDER", raising=False)
    service, _runtime, _vault, _clients = make_service(tmp_path)

    assert service.web_search_configuration() == {
        "provider": "duckduckgo",
        "api_key": "",
        "api_key_source": "",
    }
    assert service.snapshot()["web_search"] == {
        "backend": "duckduckgo",
        "provider": "DuckDuckGo",
        "requires_api_key": False,
        "api_key_configured": False,
        "source": "in_process",
        "provider_source": "default",
    }


def test_web_search_provider_is_selected_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "duckduckgo")
    service, _runtime, _vault, _clients = make_service(tmp_path)

    assert service.web_search_configuration()["provider"] == "duckduckgo"
    assert service.snapshot()["web_search"]["provider_source"] == "environment"


@pytest.mark.parametrize(
    "scheme,client,accepted",
    [
        ("https", ("10.0.0.9", 4000), True),
        ("http", ("127.0.0.1", 4000), True),
        ("http", ("10.0.0.9", 4000), False),
    ],
)
def test_secret_transport_requires_https_or_loopback(scheme, client, accepted):
    request = Request({
        "type": "http",
        "scheme": scheme,
        "server": ("example.test", 443 if scheme == "https" else 80),
        "client": client,
        "headers": [],
        "method": "PUT",
        "path": "/settings/providers/meta",
        "query_string": b"",
    })

    if accepted:
        _require_secure_secret_transport(request)
    else:
        with pytest.raises(HTTPException) as error:
            _require_secure_secret_transport(request)
        assert error.value.status_code == 400


def test_settings_api_requires_permission_and_never_echoes_secret(tmp_path):
    service, runtime, vault, _clients = make_service(tmp_path)
    principal = RequestPrincipal(
        user_id="settings-admin",
        permissions=frozenset({"settings.manage"}),
    )

    def authorize(api_key, _request):
        if api_key != "trusted-key":
            raise HTTPException(status_code=401, detail="Invalid API key")
        return principal

    def require_permission(request_principal, permission):
        if permission not in request_principal.permissions:
            raise HTTPException(status_code=403, detail="forbidden")

    context = ApiContext(
        runtime_getter=lambda: runtime,
        authorize_request=authorize,
        require_permission=require_permission,
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: type(error).__name__,
        redact=lambda value: value,
        settings_service_getter=lambda: service,
    )
    app = FastAPI()
    app.include_router(create_settings_router(context))
    client = TestClient(app, base_url="https://testserver")

    response = client.put(
        "/settings/providers/meta",
        headers={"X-API-Key": "trusted-key"},
        json={"fields": {"access_token": "private-api-token"}},
    )

    assert response.status_code == 200
    assert "private-api-token" not in response.text
    assert runtime.credentials["meta"]["access_token"] == "private-api-token"
    assert b"private-api-token" not in vault.path.read_bytes()

    settings_response = client.get(
        "/settings",
        headers={"X-API-Key": "trusted-key"},
    )
    assert settings_response.status_code == 200
    assert settings_response.json()["media_model_catalog"]["image_generation"][
        "model"
    ] == "agnes-image-2.5-flash"

    paid_model_response = client.post(
        "/settings/models",
        headers={"X-API-Key": "trusted-key"},
        json={
            "name": "Paid image",
            "purpose": "image_generation",
            "model": "agnes-image-2.5",
            "api_key": "private-media-key",
        },
    )
    assert paid_model_response.status_code == 422

    media_model_response = client.post(
        "/settings/models",
        headers={"X-API-Key": "trusted-key"},
        json={
            "name": "Free image",
            "purpose": "image_generation",
            "model": "agnes-image-2.5-flash",
            "api_key": "private-media-key",
        },
    )
    assert media_model_response.status_code == 200
    assert "private-media-key" not in media_model_response.text

    denied_context = ApiContext(
        runtime_getter=lambda: runtime,
        authorize_request=lambda *_args: RequestPrincipal(user_id="reader"),
        require_permission=require_permission,
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: type(error).__name__,
        redact=lambda value: value,
        settings_service_getter=lambda: service,
    )
    denied_app = FastAPI()
    denied_app.include_router(create_settings_router(denied_context))
    denied_response = TestClient(
        denied_app,
        base_url="https://testserver",
    ).get("/settings")

    assert denied_response.status_code == 403


def test_knowledge_embedding_profile_is_separate_and_never_replaces_chat_model(
    tmp_path,
):
    service, runtime, vault, clients = make_service(tmp_path)

    profile_id = service.save_model_profile(
        name="Knowledge embeddings",
        model="embed-v1",
        base_url="https://models.example/v1",
        api_key="private-embedding-key",
        purpose="knowledge_embedding",
    )
    configuration = service.model_configuration_for("knowledge_embedding")
    snapshot = service.snapshot()

    assert configuration == {
        "name": "Knowledge embeddings",
        "model": "embed-v1",
        "base_url": "https://models.example/v1",
        "api_key": "private-embedding-key",
    }
    assert runtime.llm is None
    assert clients == []
    assert snapshot["models"]["active_profiles"]["knowledge_embedding"] == profile_id
    assert "private-embedding-key" not in repr(snapshot)
    assert b"private-embedding-key" not in vault.path.read_bytes()


def test_web_search_settings_api_is_authorized_secure_and_never_echoes_key(
    tmp_path,
):
    service, runtime, vault, _clients = make_service(tmp_path)
    principal = RequestPrincipal(
        user_id="settings-admin",
        permissions=frozenset({"settings.manage"}),
    )
    context = ApiContext(
        runtime_getter=lambda: runtime,
        authorize_request=lambda _api_key, _request: principal,
        require_permission=lambda request_principal, permission: (
            None if permission in request_principal.permissions
            else (_ for _ in ()).throw(
                HTTPException(status_code=403, detail="forbidden")
            )
        ),
        activate_tenant_skills=lambda _principal: None,
        sync_tenant_extensions=lambda _principal: None,
        safe_exception_text=lambda error: type(error).__name__,
        redact=lambda value: value,
        settings_service_getter=lambda: service,
    )
    app = FastAPI()
    app.include_router(create_settings_router(context))
    client = TestClient(app, base_url="http://testserver")

    response = client.put(
        "/settings/web-search",
        json={"provider": "duckduckgo"},
    )
    assert response.status_code == 200
    assert response.json()["web_search"]["backend"] == "duckduckgo"

    response = client.put(
        "/settings/web-search",
        json={"api_key": "private-brave-search-key"},
    )

    assert response.status_code == 400
    assert service.web_search_configuration()["api_key"] == ""

    secure_client = TestClient(app, base_url="https://testserver")
    response = secure_client.put(
        "/settings/web-search",
        json={
            "provider": "brave",
            "api_key": "private-brave-search-key",
        },
    )

    assert response.status_code == 200
    assert "private-brave-search-key" not in response.text
    assert b"private-brave-search-key" not in vault.path.read_bytes()
    assert response.json()["web_search"]["api_key_configured"] is True
