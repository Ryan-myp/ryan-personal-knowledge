"""Advertising Agent product definition for the generic platform catalog."""

from __future__ import annotations

from typing import Sequence
from pathlib import Path

from agents.agent_harness import ToolSource, MarkdownSkillDirectorySource
from agents.agent_harness.core.agent_profile import AgentProfile
from agents.agent_platform import AgentDefinition, ScenarioDefinition


def advertising_agent_profile() -> AgentProfile:
    """Return the stable advertising behavior profile shared by composition."""
    return AgentProfile(
        name="ad-agent",
        role="广告投放与分析助手",
        domain_guidance=(
            "广告业务知识只来自当前注册的 Skills、Tools、Blueprints "
            "和受控知识源；回答能力问题时必须以服务端能力目录为准，不得依据"
            "大模型预训练知识扩展或虚构系统能力。"
        ),
        response_guidance=(
            "面向广告运营人员回答；问候时简洁回应，询问能力时只介绍当前能力目录中"
            "已注册的 Skill 与 Tool；没有对应执行结果时不得声称操作完成，必须区分"
            "预览、已执行、失败和状态未知。"
        ),
        structured_fields=(
            "仅使用当前注册的 Skill、Tool、Tool Source 和 Blueprint 契约中声明的字段；"
            "缺少必填信息时先澄清，不从业务常识猜测"
        ),
    )


def advertising_skill_source(*, source_id: str = "ad-skills") -> MarkdownSkillDirectorySource:
    """Select a portable directory of standard, advisory Skill packages."""
    return MarkdownSkillDirectorySource(
        Path(__file__).resolve().parents[1] / "skills/advertising",
        source_id=source_id,
    )


def advertising_agent_definition(
    *,
    tool_sources: Sequence[ToolSource] = (),
    skill_source_id: str = "ad-skills",
) -> AgentDefinition:
    """Describe advertising as a product without creating a second Runtime.

    The returned definition can be registered in ``AgentPlatform`` and its
    standard Skill/Tool sources can be selected by any compatible scenario.
    """
    return AgentDefinition(
        agent_id="default-agent",
        version="1.0.0",
        display_name="General Agent",
        description="One general Agent configured for the advertising scenario.",
        system_prompt=advertising_agent_profile().prompt_block(),
        skill_sources=(advertising_skill_source(source_id=skill_source_id),),
        tool_sources=tuple(tool_sources),
        metadata={"scenario_domain": "advertising"},
    )


def advertising_scenario_definition(
    *,
    agent_id: str = "default-agent",
    skill_source_id: str = "ad-skills",
    tool_source_ids: Sequence[str] = (),
) -> ScenarioDefinition:
    """Declare which registered sources the advertising use case selects."""
    return ScenarioDefinition(
        scenario_id="advertising",
        agent_id=agent_id,
        display_name="Advertising",
        description="General Agent configured with advertising capabilities.",
        skill_source_ids=(skill_source_id,),
        tool_source_ids=tuple(tool_source_ids),
        metadata={"domain": "advertising"},
    )


__all__ = [
    "advertising_agent_profile",
    "advertising_skill_source",
    "advertising_agent_definition",
    "advertising_scenario_definition",
]
