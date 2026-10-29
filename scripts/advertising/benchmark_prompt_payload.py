"""离线捕获真实组装的模型文本与 Tool schema；不调用模型或渠道 API。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agents.agent_harness import ModelTurn
from agents.agent_harness.core.llm_client import LLMClient
from agents.agent_harness.model_limits import provider_input_chars, serialized_chars
from agents.agent_platform.governance.identity.principal import RequestPrincipal
from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.applications.advertising.persistence.store import AdAgentStore


CASES = (
    ("greeting", "你好"),
    ("capabilities", "你支持哪些能力？"),
    ("knowledge", "讲解程序化广告中 SSP 和 DSP 的区别，不需要账户数据。"),
    ("report", "查询 Meta 最近七天的 campaign 报表"),
    ("templates", "列出 Google 的创建模板"),
    ("creation", "用模板创建一个 Meta campaign，所有层级保持 PAUSED"),
)


class CaptureModel:
    """只返回固定文本；保留计数和能力名称，不持久化 Prompt 正文。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.case_id = ""

    def complete(self, messages, tools, _request):
        parts: dict[str, int] = {}
        skills = []
        for message in messages:
            kind = message.metadata.get("context_type", message.role)
            parts[kind] = parts.get(kind, 0) + len(str(message.content))
            if kind == "skills":
                skills.extend(re.findall(r"## Skill: (.+)", message.content))
        schemas = LLMClient._provider_tools(tools)
        self.rows.append({
            "case_id": self.case_id, "message_content_chars": parts,
            "tool_names": [tool.name for tool in tools], "skills": skills,
            "tool_schema_chars": serialized_chars(schemas),
            "payload_chars": provider_input_chars(LLMClient._provider_messages(messages), schemas),
        })
        return ModelTurn(content="离线输入采样完成。")


def benchmark() -> dict:
    model = CaptureModel()
    # Any accidental external access fails instead of consuming Provider QPS.
    with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")):
        runtime = AdvertisingComposition(
            require_llm=False, offline_mode=True, start_background_workers=False,
            persistence_store=AdAgentStore(":memory:"),
        )
        try:
            runtime.auto_load_skills(
                str(ROOT / "agents/skills/advertising"),
                allow_executable_plugins=True, allow_provider_tool_discovery=True,
            )
            runtime.whitelist_validator.allowed_accounts = {
                name: ["1234567890"] for name in runtime.registry.list_all_namespaces()
            }
            definitions = runtime.platform_application.tools.list_tools()
            principal = RequestPrincipal(
                user_id="prompt-benchmark",
                permissions=frozenset(
                    permission for tool in definitions
                    for permission in runtime.policy_engine.required_permissions(tool, "dry_run")
                ),
                account_scope={name: frozenset({"1234567890"})
                               for name in runtime.registry.list_all_namespaces()},
            )
            runtime.platform_application.agent.model = model
            session_id = None
            for case_id, query in (*CASES, ("followup", "继续，保持刚才的暂停状态")):
                model.case_id = case_id
                result = runtime.run(
                    query, user_id=principal.user_id, principal=principal,
                    session_id=session_id if case_id == "followup" else None,
                )
                session_id = result.get("session_id")
                if result.get("status") != "succeeded":
                    raise AssertionError(f"benchmark case failed: {case_id}")
        finally:
            runtime.close(wait=True)
    return {"schema_version": "prompt-payload/v1", "units": "serialized_characters_not_tokens",
            "provider_calls": 0, "external_model_calls": 0, "cases": model.rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(benchmark(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
