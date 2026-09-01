"""Local, process-scoped configuration loading for ad-agent entrypoints."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def load_local_env_file(path: Path) -> None:
    """Load simple ``KEY=VALUE`` settings without evaluating the file.

    Explicit process environment variables always win. The parser accepts
    comments, blank lines, optional ``export`` and quoted values, but never
    executes shell syntax from the configuration file.
    """
    if not path.is_file():
        return

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("无法读取本地环境配置 %s: %s", path, exc)
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key or not key.replace("_", "").isalnum():
            continue
        if key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def load_default_local_env() -> None:
    """Load the ignored configuration beside the ad-agent service code."""
    load_local_env_file(Path(__file__).resolve().parents[1] / ".env")
