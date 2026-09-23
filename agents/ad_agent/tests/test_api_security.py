"""Tests for the API authentication boundary."""

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from agents.ad_agent.api.security import RequestAuthorizer


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
