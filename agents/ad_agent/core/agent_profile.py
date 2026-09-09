"""Application profile injected into the business-neutral Agent Core."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    """Static role/presentation policy; never contains request or credentials."""

    name: str = "agent"
    role: str = "一个严谨、可审计的通用 Agent"
    language: str = "优先使用用户使用的语言，保持回答清晰、简洁、可验证"
    domain_guidance: str = "业务知识只来自当前注册的 Skills、Tools 和受控知识源。"
    response_guidance: str = "只基于已提供的输入和执行结果回答，不改变执行状态。"
    structured_fields: str = ""

    def prompt_block(self) -> str:
        return (
            f"[PROFILE · {self.name}]\n"
            f"角色：{self.role}\n"
            f"语言：{self.language}\n"
            f"边界：{self.domain_guidance}{self.response_guidance}"
            + (f"\n应用扩展字段：{self.structured_fields}" if self.structured_fields else "")
        )


__all__ = ["AgentProfile"]
