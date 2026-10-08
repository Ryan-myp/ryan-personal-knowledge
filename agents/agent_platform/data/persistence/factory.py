"""Select the configured persistence backend without leaking it into Runtime."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .store import AdAgentStore


def create_persistence_store(
    *, sqlite_path: str | Path | None = None,
    database_url: str | None = None,
    backend: str | None = None,
    **kwargs: Any,
):
    """Create SQLite by default, or MySQL when explicitly configured."""
    configured_url = database_url or os.environ.get("AD_AGENT_DATABASE_URL", "").strip()
    configured_backend = (backend or os.environ.get("AD_AGENT_DB_BACKEND", "")).strip().lower()
    if configured_url or configured_backend == "mysql":
        if not configured_url:
            raise ValueError("AD_AGENT_DATABASE_URL is required when AD_AGENT_DB_BACKEND=mysql")
        from .mysql_store import MySQLStore
        return MySQLStore(
            configured_url,
            pool_size=int(os.environ.get("AD_AGENT_DB_POOL_SIZE", "5")),
            max_overflow=int(os.environ.get("AD_AGENT_DB_MAX_OVERFLOW", "10")),
            connect_timeout=int(os.environ.get("AD_AGENT_DB_CONNECT_TIMEOUT", "10")),
            **kwargs,
        )
    path = sqlite_path or os.environ.get("AD_AGENT_DB_PATH")
    if path is None:
        path = Path(__file__).parent.parent / "ad_agent.db"
    return AdAgentStore(str(Path(path).expanduser().resolve()))
