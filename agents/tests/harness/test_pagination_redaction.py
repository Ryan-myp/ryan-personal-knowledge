"""Public continuation tokens must not be confused with access credentials."""

import pytest

from agents.agent_harness.redaction import redact_for_persistence


@pytest.mark.parametrize("key", ["next_page_token", "nextPageToken"])
def test_exact_public_continuation_field_keeps_scalar_value(key):
    assert redact_for_persistence({key: "opaque-page-2"}) == {key: "opaque-page-2"}
    assert redact_for_persistence({key: None}) == {key: None}
    assert "PRIVATE" not in str(redact_for_persistence({key: "access_token=PRIVATE"}))


@pytest.mark.parametrize("key", [
    "page_token", "page_access_token", "access_token", "refresh_token", "token",
    "next_page_token_access_token", "client_secret", "private_key",
])
def test_credentials_and_lookalikes_remain_redacted(key):
    assert redact_for_persistence({key: "PRIVATE"}) == {key: "<redacted>"}


@pytest.mark.parametrize("value", [{"access_token": "PRIVATE"}, ["PRIVATE"], True, 123])
def test_continuation_field_cannot_smuggle_structured_credentials(value):
    assert redact_for_persistence({"next_page_token": value}) == {"next_page_token": "<redacted>"}
