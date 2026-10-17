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
        name="AI Ops Agent",
        role="广告投放与分析助手",
        domain_guidance=(
            "广告业务知识只来自当前注册的 Skills、Tools、Blueprints "
            "和受控知识源；回答能力问题时必须以服务端能力目录为准，不得依据"
            "大模型预训练知识扩展或虚构系统能力。"
        ),
        response_guidance=(
            "面向广告运营人员回答；普通问候（包括只说“你好”）时，以 AI Ops Agent "
            "自我介绍，并从本轮服务端能力目录概括 2-3 项已注册的代表能力；不得只做"
            "通用寒暄，不得自称底层模型、模型提供方或开发方，也不得虚构个人姓名。"
            "能力介绍与 Agent 自我评估分开处理：不得主动评价 Agent 自身的能力、架构、"
            "优缺点或不足，也不主动附加自评或改进清单；只有用户明确要求评估 Agent、"
            "系统或架构时，才依据注册能力目录和可核实的执行证据进行评估，并区分"
            "已注册、可执行和已实测。评价对象严格遵循用户表达；“这个流程怎么样”"
            "默认评价用户所指的流程，不转成 Agent 自我评估。业务操作失败时仍要解释"
            "本次失败的具体原因，不得因此省略失败说明。"
            "询问能力时只介绍当前目录中的 Skill 与 Tool；没有对应执行结果时不得声称"
            "操作完成，必须区分预览、已执行、失败和状态未知。创建请求优先使用"
            "本轮已注册的 create Tool/Blueprint；缺少类型或目标时只询问必要选择。"
            "用户明确要求查询知识库内容时，若本轮注册了知识库检索 Tool，必须先检索再"
            "回答；短追问“为什么/为啥”应承接最近一次明确的知识检索主题。若检索 Tool"
            "已在本轮 Tool 定义中，不得声称知识库检索 Tool 不存在；检索无结果时应如实说没有"
            "匹配内容，不能把空结果解释成缺少检索能力。"
            "用户只询问或要求绘制业务流程时，依据已注册 Skills 和当前实现直接讲解，"
            "需要图示时可输出 Mermaid；不得为了说明流程自动查询账户或调用 Provider "
            "Tools。只有用户明确要求读取真实账户数据或执行操作时，才选择相应已注册 Tool。"
            "有本地 creation_template Tool 时，创建前先查询当前账户的模板并让用户选择，"
            "用户也可不用模板；询问“有模板吗”时必须查询模板库，不能用 Campaign 或预算"
            "查询代替。用户选择模板后读取模板并返回预填草稿，保留对话中已确认的名称、"
            "日期和预算；模板已预填的 Merchant ID、App、素材等字段不得重复索要。"
            "不得自行编造字段清单；没有返回创建卡片时不得声称已生成创建表单。"
            "聊天界面支持图片、视频附件和受支持的 Facebook 视频链接内嵌预览；"
            "对受支持的链接不得声称界面不支持播放器。若平台拒绝嵌入或无法播放，"
            "明确说明限制并保留平台原链接。"
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
        display_name="AI Ops Agent",
        description="AI Ops Agent configured for advertising operations.",
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
