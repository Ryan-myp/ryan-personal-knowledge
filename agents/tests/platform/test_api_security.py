"""Tests for the API authentication boundary."""

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from agents.deployments.advertising.api.security import RequestAuthorizer
from agents.agent_platform.governance.identity.principal import RequestPrincipal


def test_api_key_principal_mapping_never_uses_body_identity():
    authorizer = RequestAuthorizer(
        runtime_getter=lambda: SimpleNamespace(
            _granted_permissions={"ads.read"},
            whitelist_validator=SimpleNamespace(allowed_accounts={}),
        ),
        api_key_getter=lambda: "",
        principals_getter=lambda: {
            "key": {
                "user_id": "trusted-user",
                "tenant_id": "trusted-tenant",
                "permissions": ["ads.read"],
            }
        },
        allow_unauthenticated_getter=lambda: False,
    )

    principal = authorizer.authorize("key", None)

    assert principal.user_id == "trusted-user"
    assert principal.tenant_id == "trusted-tenant"


@pytest.mark.parametrize("client_host", ["127.0.0.1", "10.53.48.25"])
@pytest.mark.parametrize("api_key", [None, "shared-key", "unrecognized-key"])
def test_unauthenticated_mode_uses_one_shared_identity_for_every_client(
    client_host, api_key
):
    authorizer = RequestAuthorizer(
        runtime_getter=lambda: None,
        api_key_getter=lambda: "shared-key",
        principals_getter=lambda: {
            "user-key": {
                "user_id": "different-user",
                "tenant_id": "different-tenant",
                "permissions": ["ads.read"],
            }
        },
        allow_unauthenticated_getter=lambda: True,
        service_principal_getter=lambda: RequestPrincipal(
            user_id="service-user",
            tenant_id="shared-tenant",
            permissions=frozenset({"ads.read"}),
        ),
    )
    request = SimpleNamespace(client=SimpleNamespace(host=client_host))

    principal = authorizer.authorize(api_key, request)

    assert principal.user_id == "service-user"
    assert principal.tenant_id == "shared-tenant"
    assert principal.permissions == frozenset({"ads.read"})


def test_authentication_mode_still_requires_a_valid_key():
    authorizer = RequestAuthorizer(
        runtime_getter=lambda: None,
        api_key_getter=lambda: "configured-key",
        principals_getter=lambda: {},
        allow_unauthenticated_getter=lambda: False,
    )
    remote_request = SimpleNamespace(
        client=SimpleNamespace(host="10.53.48.25")
    )

    with pytest.raises(HTTPException) as error:
        authorizer.authorize(None, remote_request)

    assert error.value.status_code == 401


def test_local_unauthenticated_request_remains_allowed_in_local_dev_mode():
    authorizer = RequestAuthorizer(
        runtime_getter=lambda: None,
        api_key_getter=lambda: "",
        principals_getter=lambda: {},
        allow_unauthenticated_getter=lambda: True,
        service_principal_getter=lambda: RequestPrincipal(user_id="local-user"),
    )
    local_request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1")
    )

    principal = authorizer.authorize(None, local_request)

    assert principal.user_id == "local-user"


def test_invalid_principal_configuration_is_service_error():
    authorizer = RequestAuthorizer(
        runtime_getter=lambda: None,
        api_key_getter=lambda: "",
        principals_getter=lambda: json.loads('{"key": {"permissions": "bad"}}'),
        allow_unauthenticated_getter=lambda: False,
    )

    with pytest.raises(HTTPException) as error:
        authorizer.authorize("key", None)

    assert error.value.status_code == 503


def test_ads_write_does_not_grant_permissions_in_other_domains():
    authorizer = RequestAuthorizer(
        runtime_getter=lambda: None,
        api_key_getter=lambda: "key",
        principals_getter=lambda: {},
        allow_unauthenticated_getter=lambda: False,
        service_principal_getter=lambda: RequestPrincipal(
            user_id="operator",
            permissions=frozenset({"ads.write"}),
        ),
    )

    principal = authorizer.authorize("key", None)

    with pytest.raises(HTTPException) as error:
        authorizer.require_permission(principal, "knowledge.write")

    assert error.value.status_code == 403


def test_ads_write_keeps_higher_privilege_within_ads_domain():
    authorizer = RequestAuthorizer(
        runtime_getter=lambda: None,
        api_key_getter=lambda: "key",
        principals_getter=lambda: {},
        allow_unauthenticated_getter=lambda: False,
        service_principal_getter=lambda: RequestPrincipal(
            user_id="operator",
            permissions=frozenset({"ads.write"}),
        ),
    )

    principal = authorizer.authorize("key", None)

    authorizer.require_permission(principal, "ads.read")
    authorizer.require_permission(principal, "ads.plan")
