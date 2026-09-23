"""Tests for the API authentication boundary."""

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from agents.ad_agent.api.security import RequestAuthorizer
from agents.ad_agent.domain.ad.auth import RequestPrincipal


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
