"""The advertising Tool package receives account policy from its deployment."""

from agents.tools.advertising.application.account_policy import (
    AccountWhitelistValidator,
)


def test_account_allowlist_is_not_implicitly_loaded_from_a_deployment_path():
    validator = AccountWhitelistValidator()

    allowed, reason = validator.validate_account("dv360", "5110831")

    assert not allowed
    assert "未配置受控账户白名单" in reason


def test_account_allowlist_can_be_injected_from_deployment_configuration(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "allowed_accounts:\n  dv360:\n    - '5110831'\n",
        encoding="utf-8",
    )

    validator = AccountWhitelistValidator(str(config_path))

    assert validator.validate_account("dv360", "5110831") == (True, "")
    assert not validator.validate_account("dv360", "other-account")[0]
