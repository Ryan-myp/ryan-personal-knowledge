"""Account scope and test-account whitelist policy."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import yaml

from ..core.auth import normalize_account_id
from ..core.platform import normalize_platform

logger = logging.getLogger(__name__)


class AccountWhitelistValidator:
    """Allow only explicitly configured accounts, normally test accounts."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), "..", "config.yaml"
        )
        self.allowed_accounts: dict[str, list[str]] = {}
        self._load_config()

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as file:
                    config = yaml.safe_load(file)
                configured = (
                    config.get("allowed_accounts", {})
                    if isinstance(config, dict) else {}
                )
                self.allowed_accounts = (
                    configured if isinstance(configured, dict) else {}
                )
        except Exception as exc:
            logger.warning("加载账户白名单配置失败: %s", exc)

    def reload(self):
        self._load_config()

    def validate_account(
        self, platform: str, account_id: str
    ) -> tuple[bool, str]:
        canonical_platform = normalize_platform(platform)
        allowed = self._accounts_for_platform(canonical_platform)
        if not allowed:
            return False, f"{canonical_platform} 未配置受控账户白名单"
        normalized_account = normalize_account_id(account_id)
        is_allowed = bool(normalized_account) and normalized_account in {
            normalize_account_id(account) for account in allowed
        }
        if not is_allowed:
            return (
                False,
                f"账户 {account_id} 不在 {canonical_platform} 白名单中。"
                f"允许操作的账户: {', '.join(str(account) for account in allowed)}",
            )
        return True, ""

    def get_allowed_accounts(self, platform: str) -> list[str]:
        return list(self._accounts_for_platform(normalize_platform(platform)))

    def _accounts_for_platform(self, platform: str) -> list[Any]:
        configured = self.allowed_accounts
        if not platform or not isinstance(configured, dict):
            return []
        values = []
        for raw_platform, raw_accounts in configured.items():
            if normalize_platform(raw_platform) != platform:
                continue
            if isinstance(raw_accounts, (str, bytes)) or not isinstance(
                raw_accounts, (list, tuple, set, frozenset)
            ):
                return []
            for account in raw_accounts:
                if not isinstance(account, (str, int)) or isinstance(account, bool):
                    return []
                normalized = normalize_account_id(account)
                if normalized:
                    values.append(account)
        return values
