from __future__ import annotations

import os
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
