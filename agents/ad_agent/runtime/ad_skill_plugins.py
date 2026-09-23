"""Verified executable Skill plugin loading."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from .skill import Skill

logger = logging.getLogger(__name__)


class AdSkillPluginMixin:
    @staticmethod
    def _verify_skill_plugin(skill_dir: Any, plugin_path: Any) -> tuple[bool, str]:
        """Verify a Skill manifest before importing executable code."""
        skill_dir = os.fspath(skill_dir)
        plugin_path = os.fspath(plugin_path)
        manifest_path = os.path.join(skill_dir, "skill.manifest.json")
        require_manifest = os.environ.get("AD_AGENT_REQUIRE_SKILL_MANIFEST") == "1"
        if not os.path.exists(manifest_path):
            if require_manifest:
                return False, "skill.manifest.json is required"
            return True, "manifest not configured"
        try:
            with open(manifest_path, "r", encoding="utf-8") as file:
                manifest = json.load(file)
        except (OSError, TypeError, ValueError) as exc:
            return False, f"invalid skill manifest: {exc}"
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(files, dict):
            return False, "skill manifest files must be an object"
        relative_name = os.path.basename(plugin_path)
        expected = files.get(relative_name) or files.get(
            os.path.relpath(plugin_path, skill_dir)
        )
        if not isinstance(expected, str):
            return False, f"skill manifest does not cover {relative_name}"
        digest = hashlib.sha256()
        try:
            with open(plugin_path, "rb") as file:
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            return False, f"cannot hash Skill plugin: {exc}"
        if not hmac.compare_digest(digest.hexdigest(), expected.lower()):
            return False, f"hash mismatch for {relative_name}"
        signing_key = os.environ.get("AD_AGENT_SKILL_MANIFEST_KEY")
        signature = manifest.get("signature") if isinstance(manifest, dict) else None
        if require_manifest and not signing_key:
            return False, "AD_AGENT_SKILL_MANIFEST_KEY is required with manifest enforcement"
        if signing_key:
            if not isinstance(signature, str) or not signature:
                return False, "signed Skill manifest is required"
            signed_payload = json.dumps(
                {
                    "skill": manifest.get("skill", os.path.basename(skill_dir)),
                    "version": manifest.get("version", "1"),
                    "files": files,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            expected_signature = hmac.new(
                signing_key.encode("utf-8"), signed_payload, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected_signature):
                return False, "skill manifest signature mismatch"
        return True, "verified"

    @staticmethod
    def _load_skill_plugin(skill_dir: Any, api_client=None) -> Optional[Skill]:
        """Load a verified executable Skill plugin from a Skill directory."""
        skill_dir = Path(skill_dir)
        candidates = [
            skill_dir / "tools.py",
            skill_dir / "tools" / "__init__.py",
        ]
        plugin_path = next((path for path in candidates if path.exists()), None)
        if plugin_path is None:
            return None
        verified, reason = AdSkillPluginMixin._verify_skill_plugin(
            skill_dir, plugin_path
        )
        if not verified:
            logger.error("拒绝加载 Skill plugin %s: %s", plugin_path, reason)
            return None
        module_name = "ad_agent_skill_" + hashlib.sha256(
            str(plugin_path.resolve()).encode("utf-8")
        ).hexdigest()[:16]
        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            factory = getattr(module, "create_skill", None)
            if not callable(factory):
                logger.warning(
                    "Skill plugin %s 缺少 create_skill(api_client)", plugin_path
                )
                return None
            skill = factory(api_client)
            if not (
                skill is not None
                and callable(getattr(skill, "get_tools", None))
                and callable(getattr(skill, "get_tool_handler", None))
            ):
                logger.warning(
                    "Skill plugin %s 未返回可执行 Core Skill", plugin_path
                )
                return None
            return skill
        except Exception as exc:
            logger.warning("加载 Skill plugin %s 失败: %s", plugin_path, exc)
            return None


__all__ = ["AdSkillPluginMixin"]
