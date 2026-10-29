"""Tests for standard-directory Skill management and safe activation."""

import pytest
from agents.applications.advertising.integrations.skill_evaluation import advertising_evaluation_engines
import time
import threading
from pathlib import Path

from agents.applications.advertising.composition.ad_application import AdvertisingComposition
from agents.agent_harness.core.interfaces import ParsedIntent
from agents.agent_harness.core.interfaces import ToolDefinition, ToolSchema
from agents.agent_harness.messages import ModelTurn
from agents.agent_harness.skills.contract import SkillLoader
from agents.applications.advertising.persistence.store import AdAgentStore
from agents.agent_platform.management.skill_management import (
    BuiltinSkillCatalog,
    ManagedSkillManager,
    SkillPackageError,
    _safe_evaluation_payload,
)
from agents.tests.advertising.harness_models import ScriptedHarnessModel


def test_builtin_skill_catalog_lists_standard_packages_as_read_only():
    skills_root = Path(__file__).resolve().parents[2] / "skills" / "advertising"
    catalog = BuiltinSkillCatalog(skills_root)

    items = catalog.list_versions(limit=200)
    assert all(
        any("\u3400" <= char <= "\u9fff" for char in item["description"])
        for item in items
    )

    assert {item["skill_name"] for item in items} >= {
        "google-ads-api-expert", "meta-marketing-api-expert", "tiktok-ads-expert",
        "creative-strategy", "account-diagnostics", "experimentation-design",
        "measurement-attribution", "measurement-instrumentation",
        "ad-copywriting", "paid-landing-page-review",
        "knowledge-explainer", "web-research", "data-visualization", "app-growth",
        "ad-growth-operations", "growth-strategy", "seo-growth",
        "generative-search-visibility",
        "competitor-research", "influencer-partnerships",
        "referral-growth", "lifecycle-retention", "content-distribution",
        "offer-economics",
    }
    assert all(item["source"] == "builtin" and item["editable"] is False for item in items)
    detail = catalog.get_version("google-ads-api-expert", "2.1.0")
    assert detail["files"]["SKILL.md"]["encoding"] == "base64"
    assert detail["location"] == "channels/google-ads"
    creative = catalog.get_version("creative-strategy", "1.0.1")
    assert creative["location"] == "practices/creative-strategy"
    assert "references/creative-roadmap.md" in creative["files"]
    production = catalog.get_version("creative-production", "1.1.0")
    assert production["location"] == "practices/creative-production"
    assert "references/production-workflow.md" in production["files"]
    assert "references/visual-quality-review.md" in production["files"]
    assert "references/brand-asset-check.md" in production["files"]
    diagnostics = catalog.get_version("account-diagnostics", "1.5.0")
    assert diagnostics["location"] == "practices/account-diagnostics"
    assert "references/google-report-interpretation.md" in diagnostics["files"]
    assert "references/meta-insights-interpretation.md" in diagnostics["files"]
    assert "references/tiktok-report-interpretation.md" in diagnostics["files"]
    assert "references/dv360-report-interpretation.md" in diagnostics["files"]
    assert "references/operating-check.md" in diagnostics["files"]
    assert "references/report-context-contract.md" in diagnostics["files"]
    experimentation = catalog.get_version("experimentation-design", "1.0.1")
    assert experimentation["location"] == "practices/experimentation-design"
    assert "references/test-design.md" in experimentation["files"]
    attribution = catalog.get_version("measurement-attribution", "1.1.0")
    assert attribution["location"] == "practices/measurement-attribution"
    assert "references/attribution-and-incrementality.md" in attribution["files"]
    instrumentation = catalog.get_version("measurement-instrumentation", "1.2.0")
    assert instrumentation["location"] == "practices/measurement-instrumentation"
    assert "references/event-measurement-contract.md" in instrumentation["files"]
    assert "references/conversion-qa-runbook.md" in instrumentation["files"]
    growth_operations = catalog.get_version("ad-growth-operations", "1.2.0")
    assert growth_operations["location"] == "practices/ad-growth-operations"
    assert "references/loop-contract.md" in growth_operations["files"]
    competitor_research = catalog.get_version("competitor-research", "1.0.0")
    assert competitor_research["location"] == "practices/competitor-research"
    assert "references/evidence-scorecard.md" in competitor_research["files"]
    influencer = catalog.get_version("influencer-partnerships", "1.0.0")
    assert influencer["location"] == "practices/influencer-partnerships"
    assert "references/creator-evaluation.md" in influencer["files"]
    referral_growth = catalog.get_version("referral-growth", "1.0.0")
    assert referral_growth["location"] == "practices/referral-growth"
    assert "references/referral-unit-economics.md" in referral_growth["files"]
    lifecycle = catalog.get_version("lifecycle-retention", "1.0.0")
    assert lifecycle["location"] == "practices/lifecycle-retention"
    assert "references/lifecycle-measurement.md" in lifecycle["files"]
    content_distribution = catalog.get_version("content-distribution", "1.0.0")
    assert content_distribution["location"] == "practices/content-distribution"
    assert "references/content-portfolio.md" in content_distribution["files"]
    offer_economics = catalog.get_version("offer-economics", "1.0.0")
    assert offer_economics["location"] == "practices/offer-economics"
    assert "references/offer-unit-economics.md" in offer_economics["files"]
    copywriting = catalog.get_version("ad-copywriting", "1.0.1")
    assert copywriting["location"] == "practices/ad-copywriting"
    assert "references/ad-copy-brief.md" in copywriting["files"]
    landing_page = catalog.get_version("paid-landing-page-review", "1.0.1")
    assert landing_page["location"] == "practices/paid-landing-page-review"
    assert "references/post-click-audit.md" in landing_page["files"]
    knowledge_explainer = catalog.get_version("knowledge-explainer", "1.0.6")
    assert knowledge_explainer["location"] == "practices/knowledge-explainer"
    assert "references/answer-structure.md" in knowledge_explainer["files"]
    web_research = catalog.get_version("web-research", "1.0.4")
    assert web_research["location"] == "web-research"
    visualization = catalog.get_version("data-visualization", "1.2.1")
    assert visualization["location"] == "practices/data-visualization"
    assert "references/chart-visual-review.md" in visualization["files"]
    app_growth = catalog.get_version("app-growth", "1.1.1")
    assert app_growth["location"] == "practices/app-growth"
    assert "references/store-listing-review.md" in app_growth["files"]
    assert "references/store-market-research.md" in app_growth["files"]
    growth_strategy = catalog.get_version("growth-strategy", "1.0.0")
    assert growth_strategy["location"] == "practices/growth-strategy"
    assert "references/channel-portfolio.md" in growth_strategy["files"]
    seo_growth = catalog.get_version("seo-growth", "1.0.0")
    assert seo_growth["location"] == "practices/seo-growth"
    assert "references/organic-search-audit.md" in seo_growth["files"]
    geo_visibility = catalog.get_version("generative-search-visibility", "1.1.0")
    assert geo_visibility["location"] == "practices/generative-search-visibility"
    assert "references/visibility-measurement.md" in geo_visibility["files"]


def test_standard_skill_metadata_supports_application_routing(tmp_path):
    skill_dir = tmp_path / "growth-strategy"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: growth-strategy\n"
        "description: Plan sustainable growth channels.\n"
        "metadata:\n"
        "  version: 1.2.0\n"
        "  namespace: advertising\n"
        "  triggers:\n"
        "    - [growth strategy, growth channels]\n"
        "---\n"
        "# Growth strategy\n"
        "Compare evidence-backed growth paths.\n",
        encoding="utf-8",
    )

    skill = SkillLoader().load_skill_dir(skill_dir)

    assert skill is not None
    assert skill.name == "growth-strategy"
    assert skill.version == "1.2.0"
    assert skill.namespace == "advertising"
    assert skill.triggers[0].keywords == ["growth strategy", "growth channels"]


def test_standard_skill_metadata_rejects_non_mapping_values(tmp_path):
    skill_dir = tmp_path / "invalid-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: invalid-skill\n"
        "description: Invalid metadata test.\n"
        "metadata: invalid\n"
        "---\n"
        "# Invalid Skill\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="frontmatter.metadata must be an object"):
        SkillLoader().load_skill_dir(skill_dir)


def _files(name="business-growth"):
    return {
        "SKILL.md": (
            "---\n"
            f"name: {name}\n"
            "description: Business campaign planning guidance\n"
            "platform: multi_platform\n"
            "version: 1.0.0\n"
            "---\n\n"
            "# Campaign planning\n\n"
            "Use the registered provider Tools and keep all writes in dry-run.\n"
        ),
        "scripts/README.md": "Scripts are package assets, not provider Tools.\n",
        "scripts/check.py": "print('must never be imported by Runtime')\n",
        "references/launch.md": "Ask for objective, budget and account before planning.\n",
        "assets/example.svg": "<svg xmlns='http://www.w3.org/2000/svg'/>\n",
    }


def test_channel_and_cross_channel_skills_are_natural_language_guidance():
    skills_root = Path(__file__).resolve().parents[2] / "skills" / "advertising"
    skill_paths = [
        *sorted((skills_root / "channels").glob("*/SKILL.md")),
        skills_root / "cross-channel" / "SKILL.md",
    ]

    for skill_path in skill_paths:
        content = skill_path.read_text(encoding="utf-8")
        # Internal intent labels and provider Tool names are Runtime concerns.
        # Keeping them out of Skill prose prevents the LLM from treating a
        # tool_source description as an executable Tool registry.
        assert "cross_channel_" not in content, skill_path
        assert "workflow.yaml" not in content, skill_path
        assert "meta_list_pixels" not in content, skill_path
        assert "ToolDefinition" in content or "Tool Source" in content, skill_path


def test_channel_skill_body_is_available_to_model_context():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        examples = {
                "google-ads": ("查询 Google Ads campaign", "Google Ads API 专家技能"),
                "meta": ("查询 Meta campaign performance", "Meta Marketing API 专家技能"),
                "tiktok": ("查询 TikTok campaign performance", "TikTok Ads 专家技能"),
                "dv360": ("查询 DV360 line item report", "Display & Video 360 专家技能"),
        }
        for platform, (request, marker) in examples.items():
            # The test only needs a provider-owned contract to enter the
            # selector's expert-context merge; it must not initialize or call
            # a real Provider client.
            tool = ToolDefinition(
                name=f"{platform}_list_campaigns",
                skill=f"{platform}-tool_source",
                namespace=platform,
                description="list campaigns",
                input_schema=ToolSchema(),
                intent_types=["list_campaigns"],
            )
            selection = runtime.tool_selector.select_tools(
                request,
                ParsedIntent("list_campaigns", request, [platform]),
                [tool],
            )
            assert marker in selection.expert_knowledge, platform
    finally:
        runtime.close(wait=True)


def test_builtin_creative_strategy_is_context_only_and_uses_relevant_references():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        skill = runtime.skill_loader.get("creative-strategy")
        assert skill is not None
        assert skill.get_tools() == []

        context = runtime.tool_selector._triggered_skill_context(
            "制定广告创意路线图，按账户证据排序并规划制作产能"
        )

        assert "[skill guidance: creative-strategy]" in context
        assert "references/creative-roadmap.md" in context
        assert "制作产能" in context
        assert "不会新增 Tool、权限或账户范围" in context

        hook_context = runtime.tool_selector._triggered_skill_context(
            "帮我诊断广告 Hook 和前三秒留存为什么下降"
        )

        assert "[skill guidance: creative-strategy]" in hook_context
        assert "references/hook-diagnosis.md" in hook_context
    finally:
        runtime.close(wait=True)


def test_builtin_account_diagnostics_is_advisory_and_selects_relevant_references():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        skill = runtime.skill_loader.get("account-diagnostics")
        assert skill is not None
        assert skill.get_tools() == []

        report_context = runtime.tool_selector._triggered_skill_context(
                "Google Ads 搜索词报告可见点击覆盖率与缺失查询"
        )
        assert "[skill guidance: account-diagnostics]" in report_context
        assert "references/google-report-interpretation.md" in report_context
        assert "披露的点击覆盖率" in report_context
        assert "simulated" in report_context

        audit_context = runtime.tool_selector._triggered_skill_context(
            "对 Meta 广告账户做审计，区分 Pass Fail Unknown N/A 和证据覆盖率"
        )
        assert "[skill guidance: account-diagnostics]" in audit_context
        assert "Unknown** 表示缺少证据" in audit_context
        assert "standard `search_term_view` does not cover Performance Max" not in audit_context
        assert "[references/tiktok-report-interpretation.md]" not in audit_context
        assert "[references/dv360-report-interpretation.md]" not in audit_context

        meta_context = runtime.tool_selector._triggered_skill_context(
            "Meta Insights 报表 breakdown action_breakdowns attribution window "
            "action_values 分层 report"
        )
        assert "[skill guidance: account-diagnostics]" in meta_context
        assert "references/meta-insights-interpretation.md" in meta_context
        assert "报告 Tools 不暴露" in meta_context
        assert "offline_no_client" in meta_context
        assert "[references/tiktok-report-interpretation.md]" not in meta_context

        tiktok_context = runtime.tool_selector._triggered_skill_context(
            "TikTok 报表 campaign adgroup 花费为零，诊断数据口径"
        )
        assert "[skill guidance: account-diagnostics]" in tiktok_context
        assert "references/tiktok-report-interpretation.md" in tiktok_context
        assert "AUCTION_ADGROUP" in tiktok_context

        dv360_context = runtime.tool_selector._triggered_skill_context(
            "DV360 line item 报表为空，查询失败后如何恢复"
        )
        assert "[skill guidance: account-diagnostics]" in dv360_context
        assert "references/dv360-report-interpretation.md" in dv360_context
        assert "Campaign-level report" in dv360_context

        operation_context = runtime.tool_selector._triggered_skill_context(
            "做一次周度广告账户检查，按 HOLD、FIX、TEST、INVESTIGATE 给出结论"
        )
        assert "[skill guidance: account-diagnostics]" in operation_context
        assert "references/operating-check.md" in operation_context
        assert "关键数据缺失、报告完整性/口径有疑问" in operation_context

        from agents.tools.advertising.providers.meta.provider import create_meta_tool_source

        report_tools = {
            definition.name: definition
            for definition, _handler in create_meta_tool_source().register_tools()
            if definition.action == "report"
        }
        expected_report_tools = {
            "meta_get_campaign_report",
            "meta_get_adset_report",
            "meta_get_ad_report",
        }
        assert expected_report_tools <= set(report_tools)
        for tool_name in expected_report_tools:
            properties = report_tools[tool_name].input_schema.properties
            assert not {
                "breakdowns",
                "action_breakdowns",
                "attribution_setting",
            } & set(properties), tool_name
    finally:
        runtime.close(wait=True)


def test_marketplace_copywriting_and_post_click_skills_are_advisory():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        copywriting = runtime.skill_loader.get("ad-copywriting")
        landing_page = runtime.skill_loader.get("paid-landing-page-review")
        assert copywriting is not None
        assert landing_page is not None
        assert copywriting.get_tools() == []
        assert landing_page.get_tools() == []

        copy_context = runtime.tool_selector._triggered_skill_context(
            "帮我写 5 条 TikTok 广告主文案和 CTA，突出产品卖点"
        )
        assert "[skill guidance: ad-copywriting]" in copy_context
        assert "references/ad-copy-brief.md" in copy_context
        assert "不补写数据" in copy_context

        landing_context = runtime.tool_selector._triggered_skill_context(
            "检查这条广告点击后的 landing page 是否和广告承诺匹配"
        )
        assert "[skill guidance: paid-landing-page-review]" in landing_context
        assert "references/post-click-audit.md" in landing_context
        assert "不代表已经访问页面" in landing_context
    finally:
        runtime.close(wait=True)


def test_app_growth_and_recurring_loop_skills_are_context_only():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        cases = (
            (
                "app-growth",
                "审查这个 App Store 页面和 App Promotion 广告承诺是否匹配，并分析安装后留存",
                "references/store-market-research.md",
                "App Store 搜索结果不覆盖 Google Play",
            ),
            (
                "ad-growth-operations",
                "给我设计一个每周 paid media review loop，作为定时任务只读检查并通知异常",
                "references/loop-contract.md",
                "循环必须保持只读并报告重复项",
            ),
        )
        for name, request, reference, boundary in cases:
            skill = runtime.skill_loader.get(name)
            assert skill is not None, name
            assert skill.get_tools() == [], name

            context = runtime.tool_selector._triggered_skill_context(request)

            assert f"[skill guidance: {name}]" in context
            assert reference in context
            assert boundary in context

        ad_management_context = runtime.tool_selector._triggered_skill_context(
            "查询 Google Ads campaign 列表以及每个 campaign 的预算"
        )
        for name, _request, _reference, _boundary in cases:
            assert f"[skill guidance: {name}]" not in ad_management_context
    finally:
        runtime.close(wait=True)


def test_growth_seo_and_geo_skills_route_as_advisory_context():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        cases = (
            (
                "growth-strategy",
                "我们想拓展获客增长渠道，除了广告还能做哪些增长途径？",
                "references/channel-portfolio.md",
                "先定位漏斗瓶颈",
            ),
            (
                "seo-growth",
                "帮我做网站 SEO 技术审查，检查 robots.txt、sitemap、canonical 和收录",
                "references/organic-search-audit.md",
                "不是自然搜索难度",
            ),
            (
                "generative-search-visibility",
                "帮我评估 GEO 和 ChatGPT 搜索中的品牌引用可见度",
                "references/visibility-measurement.md",
                "不承诺排名或被引用",
            ),
        )

        for name, request, reference, boundary in cases:
            skill = runtime.skill_loader.get(name)
            assert skill is not None, name
            assert skill.get_tools() == [], name

            context = runtime.tool_selector._triggered_skill_context(request)

            assert f"[skill guidance: {name}]" in context
            assert reference in context
            assert boundary in context
            assert "不会新增 Tool、权限或账户范围" in context

        keyword_context = runtime.tool_selector._triggered_skill_context(
            "帮我做 SEO 关键词研究和自然搜索主题聚类"
        )
        assert "[skill guidance: keyword-research]" in keyword_context
        assert "[skill guidance: seo-growth]" in keyword_context
        assert "先区分自然搜索与付费搜索" in keyword_context
    finally:
        runtime.close(wait=True)


def test_builtin_knowledge_explainer_guides_explanations_without_routing_queries():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        skill = runtime.skill_loader.get("knowledge-explainer")
        assert skill is not None
        assert skill.get_tools() == []

        context = runtime.tool_selector._triggered_skill_context(
            "定向设置详解"
        )
        assert "[skill guidance: knowledge-explainer]" in context
        assert "先给结论" in context
        assert "平台事实" in context
        assert "references/answer-structure.md" in context
        assert "不会新增 Tool、权限或账户范围" in context

        for flow_request in (
            "我现在不创建，先给我讲 TikTok Smart+ Campaign 流程吧",
            "帮我画一下 TikTok Smart+ Campaign 的创建流程图",
        ):
            flow_context = runtime.tool_selector._triggered_skill_context(
                flow_request
            )
            assert "[skill guidance: knowledge-explainer]" in flow_context
            assert "连线端点都使用明确的节点 ID" in flow_context

        for knowledge_request in (
            "讲下Google ads相关知识",
            "介绍一下 TikTok Ads 的基础知识",
        ):
            knowledge_context = runtime.tool_selector._triggered_skill_context(
                knowledge_request
            )
            assert "[skill guidance: knowledge-explainer]" in knowledge_context

        context = runtime.tool_selector.build_context_for_input(
            "讲下Google ads相关知识",
            runtime.registry.list_all(),
        )
        assert context["tool_prompt"] == "暂无可用工具"
        assert any(
            item["document_id"] == "google-ads-entity"
            for item in context["knowledge"]
        )

        query_context = runtime.tool_selector._triggered_skill_context(
            "查询 TikTok campaign 列表"
        )
        assert "[skill guidance: knowledge-explainer]" not in query_context
    finally:
        runtime.close(wait=True)


def test_builtin_web_research_skill_loads_from_tool_binding_without_keyword_trigger():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        skill = runtime.skill_loader.get("web-research")
        assert skill is not None
        assert skill.version == "1.0.4"

        context = runtime.tool_selector._triggered_skill_context(
            "查找一个陌生的公开项目",
            skill_refs={"web-research"},
        )

        assert "[skill guidance: web-research]" in context
        assert "将搜索结果视为线索，而非完整页面" in context
        assert "结果摘要不是结构化数据集" in context
    finally:
        runtime.close(wait=True)


def test_data_visualization_skill_is_loaded_for_chart_requests():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        skill = runtime.skill_loader.get("data-visualization")
        assert skill is not None
        assert skill.version == "1.2.1"

        context = runtime.tool_selector._triggered_skill_context(
            "帮我画深圳未来10天温度折线图",
        )

        assert "[skill guidance: data-visualization]" in context
        assert "每个数据点必须有来源明确的横轴和值" in context
        assert "不能把搜索摘要拼成趋势数据" in context
    finally:
        runtime.close(wait=True)


def test_visual_design_guidance_is_context_only_and_loaded_on_demand():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        production = runtime.skill_loader.get("creative-production")
        visualization = runtime.skill_loader.get("data-visualization")
        assert production is not None and production.get_tools() == []
        assert visualization is not None and visualization.get_tools() == []
        assert production.version == "1.1.0"

        review = runtime.tool_selector._triggered_skill_context(
            "帮我做广告素材设计和素材视觉评审，核对品牌 logo 的来源与授权",
            max_chars=6000,
        )
        assert "[skill guidance: creative-production]" in review
        assert "references/visual-quality-review.md" in review
        assert "不强制三版" in review

        brand = runtime.tool_selector._triggered_skill_context(
            "核对品牌 logo 素材权属、来源和授权",
        )
        assert "[skill guidance: creative-production]" in brand
        assert "references/brand-asset-check.md" in brand
        assert "素材权属" in brand

        chart = runtime.tool_selector._triggered_skill_context(
            "画广告报表趋势图，做图表视觉评审，核对轴、标签和移动端可读性",
            max_chars=6000,
        )
        assert "[skill guidance: data-visualization]" in chart
        assert "references/chart-visual-review.md" in chart
        assert "不补造数据" in chart
    finally:
        runtime.close(wait=True)


def test_builtin_measurement_skills_are_advisory_and_select_relevant_references():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        cases = (
            (
                "experimentation-design",
                "设计广告 A/B experiment，定义假设、MDE、power、多重比较和停止规则",
                "references/test-design.md",
                "不能判断统计胜出",
            ),
            (
                "measurement-attribution",
                "Google 和 Meta 的 attribution conversions 对不上，比较 MTA、MMM、incrementality 和 holdout",
                "references/attribution-and-incrementality.md",
                "不能把平台归因解释为增量",
            ),
            (
                "measurement-instrumentation",
                "检查 conversion tracking QA，排查事件丢失、重复上报、GA4/平台回传差异和 PII",
                "references/conversion-qa-runbook.md",
                "不配置或执行外部 tracking",
            ),
        )

        for name, request, reference, boundary in cases:
            skill = runtime.skill_loader.get(name)
            assert skill is not None, name
            assert skill.get_tools() == [], name

            context = runtime.tool_selector._triggered_skill_context(request)

            assert f"[skill guidance: {name}]" in context
            assert reference in context
            assert boundary in context
    finally:
        runtime.close(wait=True)


def test_builtin_growth_skills_are_advisory_and_select_relevant_references():
    runtime = AdvertisingComposition(require_llm=False, offline_mode=True)
    try:
        cases = (
            (
                "referral-growth",
                "设计老客户邀请新客户的 referral program，并核算奖励成本和增量 CAC",
                "references/referral-unit-economics.md",
                "不触发奖励、支付、外联",
            ),
            (
                "lifecycle-retention",
                "用户注册后 activation rate 低、次月 retention 下滑，设计 onboarding 和 win-back 实验",
                "references/lifecycle-measurement.md",
                "不发送消息、不修改用户记录",
            ),
            (
                "content-distribution",
                "规划下季度 content strategy，安排主题集群和 organic social 内容复用",
                "references/content-portfolio.md",
                "不自动发布或安排内容",
            ),
            (
                "offer-economics",
                "评估这个电商广告折扣 offer 的毛利成本和 break-even CAC",
                "references/offer-unit-economics.md",
                "不修改广告预算、商品价格、网站、优惠码或平台促销",
            ),
        )

        for name, request, reference, boundary in cases:
            skill = runtime.skill_loader.get(name)
            assert skill is not None, name
            assert skill.get_tools() == [], name

            context = runtime.tool_selector._triggered_skill_context(request)

            assert f"[skill guidance: {name}]" in context
            assert reference in context
            assert boundary in context
    finally:
        runtime.close(wait=True)


def test_standard_skill_directory_is_versioned_and_published(tmp_path):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines(), root=str(tmp_path / "managed"))

    draft = manager.create_version(
        "tenant-a", "business-growth", "1.0.0", _files(), "user-a"
    )
    assert draft["status"] == "draft"
    assert set(draft["files"]) == set(_files())

    detailed = manager.get_version(
        "tenant-a", "business-growth", "1.0.0", include_files=True
    )
    assert detailed["files"]["scripts/check.py"]["encoding"] == "base64"

    runtime = AdvertisingComposition(require_llm=False, persistence_store=store, offline_mode=True)
    published = manager.publish(
        "tenant-a", "business-growth", "1.0.0", runtime=runtime
    )
    assert published["status"] == "published"
    assert "business-growth" in runtime.get_managed_skills()
    assert not any(
        tool.skill == "business-growth" for tool in runtime.registry.list_all()
    )
    context = runtime.tool_selector.build_context_for_input(
        "规划一个跨渠道投放", runtime.registry.list_all(), tenant_id="tenant-a"
    )
    assert "Ask for objective" in context["expert_knowledge"]
    assert "must never be imported" not in context["expert_knowledge"]
    assert (tmp_path / "managed").exists()


def test_new_version_archives_previous_release_and_active_lookup_is_scoped(tmp_path):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines(), root=str(tmp_path / "managed"))
    manager.create_version("tenant-a", "business-growth", "1.0.0", _files(), "u1")
    manager.publish("tenant-a", "business-growth", "1.0.0")
    manager.create_version(
        "tenant-a", "business-growth", "1.1.0", {
            **_files(),
            "SKILL.md": _files()["SKILL.md"].replace("1.0.0", "1.1.0"),
        }, "u1"
    )
    manager.publish("tenant-a", "business-growth", "1.1.0")

    active = manager.get_version("tenant-a", "business-growth")
    assert active["version"] == "1.1.0"
    assert [item["version"] for item in manager.list_versions("tenant-a", "business-growth")] == [
        "1.1.0", "1.0.0"
    ]
    assert manager.get_version("tenant-b", "business-growth") is None


def test_unpublish_removes_release_but_keeps_version_for_explicit_rollback(tmp_path):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines(), root=str(tmp_path / "managed"))
    manager.create_version("tenant-a", "business-growth", "1.0.0", _files(), "u1")

    runtime = AdvertisingComposition(require_llm=False, persistence_store=store, offline_mode=True)
    manager.publish("tenant-a", "business-growth", "1.0.0", runtime=runtime)
    assert "business-growth" in runtime.get_managed_skills("tenant-a")

    unpublished = manager.unpublish(
        "tenant-a", "business-growth", "1.0.0", runtime=runtime
    )

    assert unpublished["status"] == "archived"
    assert manager.get_version("tenant-a", "business-growth") is None
    assert manager.get_version("tenant-a", "business-growth", "1.0.0")["status"] == "archived"
    assert "business-growth" not in runtime.get_managed_skills("tenant-a")

    # Re-publishing the immutable archived snapshot is the explicit rollback
    # path; it must restore both the release pointer and Runtime context.
    rolled_back = manager.publish(
        "tenant-a", "business-growth", "1.0.0", runtime=runtime
    )
    assert rolled_back["status"] == "published"
    assert manager.get_version("tenant-a", "business-growth")["version"] == "1.0.0"
    assert "business-growth" in runtime.get_managed_skills("tenant-a")


def test_publication_serializes_runtime_activation_and_release_pointer(tmp_path):
    """Separate HTTP manager facades cannot diverge Runtime and SQLite state."""
    store = AdAgentStore(":memory:")
    manager_a = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines(), root=str(tmp_path / "managed"))
    manager_b = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines(), root=str(tmp_path / "managed"))
    manager_a.create_version("tenant-a", "release-skill", "1.0.0", _files("release-skill"), "u1")
    manager_a.create_version(
        "tenant-a", "release-skill", "2.0.0",
        {**_files("release-skill"), "SKILL.md": _files("release-skill")["SKILL.md"].replace("1.0.0", "2.0.0")},
        "u1",
    )

    class RecordingRuntime:
        def __init__(self):
            self.first_entered = threading.Event()
            self.release_first = threading.Event()
            self.active = 0
            self.max_active = 0
            self._lock = threading.Lock()
            self.loaded_versions = []

        def load_managed_skill(self, path, **_kwargs):
            with self._lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                first = not self.loaded_versions
            if first:
                self.first_entered.set()
                self.release_first.wait(timeout=2)
            self.loaded_versions.append(Path(path).name)
            with self._lock:
                self.active -= 1
            return True

    runtime = RecordingRuntime()
    errors = []

    def publish(manager, version):
        try:
            manager.publish("tenant-a", "release-skill", version, runtime=runtime)
        except Exception as exc:  # pragma: no cover - assertion below reports it
            errors.append(exc)

    first = threading.Thread(target=publish, args=(manager_a, "1.0.0"))
    second = threading.Thread(target=publish, args=(manager_b, "2.0.0"))
    first.start()
    assert runtime.first_entered.wait(timeout=2)
    second.start()
    # The second request has its own manager, so only a shared publication
    # lock can keep it from activating while the first request is in flight.
    time.sleep(0.05)
    assert runtime.max_active == 1
    runtime.release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert errors == []
    assert runtime.max_active == 1
    assert runtime.loaded_versions == ["1_0_0", "2_0_0"]
    assert manager_a.get_version("tenant-a", "release-skill")["version"] == "2.0.0"


@pytest.mark.parametrize(
    "files, message",
    [
        ({"references/only.md": "missing entry"}, "SKILL.md"),
        ({"../SKILL.md": "bad"}, "unsafe Skill file path"),
        ({"SKILL.md": "---\nname: wrong\ndescription: x\n---\n"}, "does not match"),
    ],
)
def test_invalid_standard_skill_package_is_rejected(files, message):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
    with pytest.raises(SkillPackageError, match=message):
        manager.create_version("tenant-a", "business-growth", "1.0.0", files, "u1")


def test_managed_skills_are_isolated_by_tenant_on_shared_runtime():
    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(require_llm=False, persistence_store=store, offline_mode=True)
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
    first_files = _files("first-skill")
    first_files["SKILL.md"] = first_files["SKILL.md"].replace(
        "platform: multi_platform\n", "platform: multi_platform\naliases: [tenant-a-only]\n"
    ).replace(
        "# Campaign planning", "# Tenant A planning"
    )
    second_files = _files("second-skill")
    second_files["SKILL.md"] = second_files["SKILL.md"].replace(
        "# Campaign planning", "# Tenant B planning"
    )
    manager.create_version("tenant-a", "first-skill", "1.0.0", first_files, "u1")
    manager.publish("tenant-a", "first-skill", "1.0.0", runtime=runtime)
    manager.create_version("tenant-b", "second-skill", "1.0.0", second_files, "u2")
    manager.publish("tenant-b", "second-skill", "1.0.0", runtime=runtime)

    tenant_a_context = runtime.tool_selector.build_context_for_input(
        "规划一个跨渠道投放", runtime.registry.list_all(), tenant_id="tenant-a"
    )
    tenant_b_context = runtime.tool_selector.build_context_for_input(
        "规划一个跨渠道投放", runtime.registry.list_all(), tenant_id="tenant-b"
    )
    assert "first-skill" in tenant_a_context["expert_knowledge"]
    assert "Tenant A planning" in tenant_a_context["expert_knowledge"]
    assert "second-skill" not in tenant_a_context["expert_knowledge"]
    assert "second-skill" in tenant_b_context["expert_knowledge"]
    assert "Tenant B planning" in tenant_b_context["expert_knowledge"]
    assert "first-skill" not in tenant_b_context["expert_knowledge"]
    assert set(runtime.get_managed_skills("tenant-a")) == {"first-skill"}
    assert set(runtime.get_managed_skills("tenant-b")) == {"second-skill"}
    assert runtime.skill_loader.get("first-skill") is None
    assert runtime.skill_loader.get("second-skill") is None
    assert not hasattr(runtime, "intent_parser")
    assert "tenant-a-only" not in tenant_b_context["expert_knowledge"]


def test_separate_in_memory_stores_do_not_share_materialized_skill_cache():
    first_store = AdAgentStore(":memory:")
    second_store = AdAgentStore(":memory:")
    first = ManagedSkillManager(first_store, evaluation_engines=advertising_evaluation_engines())
    second = ManagedSkillManager(second_store, evaluation_engines=advertising_evaluation_engines())

    assert first.root != second.root
    first_store.close()
    second_store.close()


def test_publish_does_not_commit_when_runtime_activation_fails():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
    manager.create_version("tenant-a", "broken-skill", "1.0.0", _files("broken-skill"), "u1")

    class BrokenRuntime:
        def load_managed_skill(self, *_args, **_kwargs):
            raise ValueError("invalid managed context")

    with pytest.raises(SkillPackageError, match="release was not published"):
        manager.publish("tenant-a", "broken-skill", "1.0.0", runtime=BrokenRuntime())
    record = manager.get_version("tenant-a", "broken-skill", "1.0.0")
    assert record["status"] == "draft"
    assert manager.get_version("tenant-a", "broken-skill") is None


def test_materialized_skill_cache_rejects_tampering(tmp_path):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines(), root=str(tmp_path / "managed"))
    manager.create_version("tenant-a", "tamper-check", "1.0.0", _files("tamper-check"), "u1")
    record = store.get_skill_version("tenant-a", "tamper-check", "1.0.0")

    materialized = manager._materialize(record)
    (materialized / "SKILL.md").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(SkillPackageError, match="snapshot digest mismatch"):
        manager._materialize(record)


def test_evaluation_payload_scrubs_echoed_environment_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret-value")
    monkeypatch.setenv("META_ACCESS_TOKEN", "meta-secret-value")
    payload = _safe_evaluation_payload({
        "stdout": "OPENAI_API_KEY=openai-secret-value META_ACCESS_TOKEN=meta-secret-value",
    })
    assert "openai-secret-value" not in payload["stdout"]
    assert "meta-secret-value" not in payload["stdout"]
    assert payload["stdout"].count("<redacted>") == 2


def test_skill_up_environment_is_minimal_and_engine_scoped(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret-value")
    monkeypatch.setenv("META_ACCESS_TOKEN", "meta-secret-value")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret-value")
    runtime_env = ManagedSkillManager._evaluation_environment("ad-agent-runtime")
    claude_env = ManagedSkillManager._evaluation_environment("claude_sdk")

    assert "OPENAI_API_KEY" not in runtime_env
    assert "META_ACCESS_TOKEN" not in runtime_env
    assert "ANTHROPIC_API_KEY" not in runtime_env
    assert claude_env["ANTHROPIC_API_KEY"] == "anthropic-secret-value"
    assert "OPENAI_API_KEY" not in claude_env
    assert "META_ACCESS_TOKEN" not in claude_env


def test_skill_up_config_is_data_only_and_uses_standard_package_files():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
    files = {
        **_files("evaluated-skill"),
        "evals/eval.yaml": (
            "schema_version: v1alpha1\n"
            "environment:\n  type: none\n"
            "mcp:\n  servers: []\n"
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: ad-agent-runtime\n"
            "cases:\n  files:\n    - evals/cases/basic.yaml\n"
        ),
        "evals/cases/basic.yaml": (
            "id: basic\ninput:\n  prompt: 'Explain the campaign plan'\n"
            "expect:\n  exit_code: 0\n"
            "judge:\n  type: rule_based\n"
            "  success:\n    - output_contains:\n        all: ['campaign']\n"
        ),
    }
    record = manager.create_version(
        "tenant-a", "evaluated-skill", "1.0.0", files, "u1"
    )
    eval_path, config = manager._validate_eval_config(
        store.get_skill_version("tenant-a", "evaluated-skill", "1.0.0")
    )
    assert str(eval_path) == "evals/eval.yaml"
    assert config["engine"]["name"] == "ad-agent-runtime"
    assert record["evaluation_status"] == "not_run"


def test_skill_with_evaluation_suite_cannot_publish_before_passing(tmp_path):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines(), root=str(tmp_path / "managed"))
    files = {
        **_files("gated-skill"),
        "evals/eval.yaml": (
            "schema_version: v1alpha1\n"
            "environment:\n  type: none\n"
            "mcp:\n  servers: []\n"
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: ad-agent-runtime\n"
            "cases:\n  files: [evals/cases/basic.yaml]\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    manager.create_version("tenant-a", "gated-skill", "1.0.0", files, "u1")
    with pytest.raises(SkillPackageError, match="must pass skill-up"):
        manager.publish("tenant-a", "gated-skill", "1.0.0")


def test_skill_package_rejects_credential_assignments_in_context_files():
    manager = ManagedSkillManager(AdAgentStore(":memory:"), evaluation_engines=advertising_evaluation_engines())
    files = {
        **_files("credential-skill"),
        "references/auth.md": "Runtime-owned config only\naccess_token: YOUR_TOKEN\n",
    }
    with pytest.raises(SkillPackageError, match="forbidden credential field assignment"):
        manager.create_version("tenant-a", "credential-skill", "1.0.0", files, "u1")


def test_skill_package_rejects_service_account_file_assignments():
    manager = ManagedSkillManager(AdAgentStore(":memory:"), evaluation_engines=advertising_evaluation_engines())
    files = {
        **_files("service-account-skill"),
        "references/auth.md": "service_account_file: /tmp/provider.json\n",
    }
    with pytest.raises(SkillPackageError, match="forbidden credential field assignment"):
        manager.create_version("tenant-a", "service-account-skill", "1.0.0", files, "u1")


def test_skill_up_config_allows_platform_managed_claude_sdk_with_safe_kwargs():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
    files = {
        **_files("claude-skill"),
        "evals/eval.yaml": (
            "schema_version: v1alpha1\n"
            "environment:\n  type: none\n"
            "mcp:\n  servers: []\n"
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n"
            "  name: claude_sdk\n"
            "  model:\n    provider: anthropic\n    name: claude-test\n"
            "  kwargs:\n"
            "    max_tokens: 512\n"
            "    file_paths: inputs/brief.txt\n"
            "cases:\n  files: [evals/cases/basic.yaml]\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    record = manager.create_version("tenant-a", "claude-skill", "1.0.0", files, "u1")
    _, config = manager._validate_eval_config(
        store.get_skill_version("tenant-a", "claude-skill", "1.0.0")
    )
    assert config["engine"]["name"] == "claude_sdk"
    assert config["engine"]["kwargs"]["max_tokens"] == 512
    assert record["evaluation_status"] == "not_run"


def test_skill_up_config_rejects_custom_engines_and_judge_scripts():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
    files = {
        **_files("unsafe-eval"),
        "evals/eval.yaml": (
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: unsafe\n  custom:\n    transport: local\n"
            "cases:\n  files: [evals/cases/basic.yaml]\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    record = manager.create_version(
        "tenant-a", "unsafe-eval", "1.0.0", files, "u1"
    )
    with pytest.raises(SkillPackageError, match="Custom Engine"):
        manager._validate_eval_config(
            store.get_skill_version("tenant-a", "unsafe-eval", "1.0.0")
        )


def test_managed_skill_eval_rejects_external_cli_engines():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
    files = {
        **_files("external-engine"),
        "evals/eval.yaml": (
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: codex\n"
            "cases:\n  files: [evals/cases/basic.yaml]\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    manager.create_version("tenant-a", "external-engine", "1.0.0", files, "u1")
    with pytest.raises(SkillPackageError, match="platform-managed engine"):
        manager._validate_eval_config(
            store.get_skill_version("tenant-a", "external-engine", "1.0.0")
        )


def test_skill_up_evaluation_is_persisted_for_an_immutable_version(tmp_path, monkeypatch):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines(), root=str(tmp_path / "managed"))
    files = {
        **_files("runnable-eval"),
        "evals/eval.yaml": (
            "schema_version: v1alpha1\n"
            "environment:\n  type: none\n"
            "mcp:\n  servers: []\n"
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: ad-agent-runtime\n"
            "cases:\n  files:\n    - evals/cases/basic.yaml\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    manager.create_version("tenant-a", "runnable-eval", "1.0.0", files, "u1")
    fake_bin = tmp_path / "skill-up"
    fake_bin.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "if sys.argv[1] == 'validate': sys.exit(0)\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output-dir') + 1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'result.json').write_text('{}')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_bin.chmod(0o755)
    monkeypatch.setenv("SKILL_UP_BIN", str(fake_bin))

    run = manager.start_evaluation("tenant-a", "runnable-eval", "1.0.0")
    for _ in range(500):
        current = manager.get_evaluation("tenant-a", run["run_id"])
        if current and current["status"] in {"passed", "failed", "error"}:
            break
        time.sleep(0.01)
    assert current["status"] == "passed"
    version = manager.get_version("tenant-a", "runnable-eval", "1.0.0")
    assert version["evaluation_status"] == "passed"
    assert version["evaluation_run_id"] == run["run_id"]
    materialized = manager._materialize(store.get_skill_version(
        "tenant-a", "runnable-eval", "1.0.0"
    ))
    assert not list(materialized.glob(".skill-up-eval-*.yaml"))


def test_skill_up_allows_only_one_active_evaluation_per_version(tmp_path, monkeypatch):
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines(), root=str(tmp_path / "managed"))
    files = {
        **_files("single-flight-eval"),
        "evals/eval.yaml": (
            "schema_version: v1alpha1\n"
            "environment:\n  type: none\n"
            "mcp:\n  servers: []\n"
            "skills:\n  - source: local_path\n    path: .\n"
            "engine:\n  name: ad-agent-runtime\n"
            "cases:\n  files: [evals/cases/basic.yaml]\n"
        ),
        "evals/cases/basic.yaml": "id: basic\ninput:\n  prompt: test\n",
    }
    manager.create_version("tenant-a", "single-flight-eval", "1.0.0", files, "u1")
    fake_bin = tmp_path / "skill-up"
    fake_bin.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys, time\n"
        "if sys.argv[1] == 'validate': sys.exit(0)\n"
        "time.sleep(0.15)\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output-dir') + 1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'result.json').write_text('{}')\n",
        encoding="utf-8",
    )
    fake_bin.chmod(0o755)
    monkeypatch.setenv("SKILL_UP_BIN", str(fake_bin))

    first = manager.start_evaluation("tenant-a", "single-flight-eval", "1.0.0")
    with pytest.raises(SkillPackageError, match="already has an evaluation"):
        manager.start_evaluation("tenant-a", "single-flight-eval", "1.0.0")
    assert manager.get_evaluation("tenant-a", first["run_id"])["status"] in {
        "queued", "running", "passed", "failed", "error"
    }


def test_interrupted_skill_up_evaluation_is_recovered_and_retryable():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
    manager.create_version("tenant-a", "recoverable-eval", "1.0.0", _files("recoverable-eval"), "u1")
    version = store.get_skill_version("tenant-a", "recoverable-eval", "1.0.0")
    run = store.claim_skill_evaluation("old-run", version["version_id"], "tenant-a")
    assert run["status"] == "queued"

    with store._lock:
        store._get_conn().execute(
            "UPDATE skill_evaluation_runs SET updated_at = ? WHERE run_id = ?",
            ("2000-01-01T00:00:00", "old-run"),
        )
        store._get_conn().commit()

    assert manager.recover_interrupted_evaluations(stale_after_seconds=900) == 1
    recovered = manager.get_evaluation("tenant-a", "old-run")
    assert recovered["status"] == "error"
    assert "interrupted" in recovered["error"]
    version = manager.get_version("tenant-a", "recoverable-eval", "1.0.0")
    assert version["evaluation_status"] == "error"

    retry = store.claim_skill_evaluation("new-run", version["version_id"], "tenant-a")
    assert retry["run_id"] == "new-run"


def test_skill_evaluation_updates_are_tenant_and_run_scoped():
    store = AdAgentStore(":memory:")
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
    manager.create_version("tenant-a", "scoped-eval", "1.0.0", _files("scoped-eval"), "u1")
    version = store.get_skill_version("tenant-a", "scoped-eval", "1.0.0")
    store.claim_skill_evaluation("run-a", version["version_id"], "tenant-a")

    assert store.update_skill_evaluation_run(
        "run-a", "tenant-b", "running"
    ) is False
    assert store.set_skill_evaluation(
        version["version_id"], "tenant-b", "running", run_id="run-a"
    ) is False
    assert store.get_skill_evaluation("run-a", "tenant-a")["status"] == "queued"
    assert store.get_skill_version("tenant-a", "scoped-eval", "1.0.0")[
        "evaluation_status"
    ] == "queued"

    assert store.update_skill_evaluation_run(
        "run-a", "tenant-a", "running"
    ) is True
    assert store.set_skill_evaluation(
        version["version_id"], "tenant-a", "running", run_id="run-a"
    ) is True


def test_skill_up_never_imports_user_skill_plugin(tmp_path, monkeypatch):
    """Managed Skill evaluation must remain context-only even with tools.py."""
    from agents.evals.advertising import skill_up_engine

    skill_dir = tmp_path / "managed-skill"
    skill_dir.mkdir()
    marker = tmp_path / "plugin-imported"
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: evaluated-context\n"
        "description: Context-only evaluation fixture\n"
        "platform: multi_platform\n"
        "---\n\nUse the registered provider Tools.\n",
        encoding="utf-8",
    )
    (skill_dir / "tools.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('imported')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_EVAL_SKILLS_ROOT", str(skill_dir))
    monkeypatch.setenv(
        "AD_AGENT_BASE_SKILLS_ROOT",
        str(Path(__file__).resolve().parents[2] / "skills" / "advertising"),
    )

    result = skill_up_engine.run(
        {
            "case_id": "managed-plugin-boundary",
            "prompt": "规划一个跨渠道投放",
            "workspace": str(tmp_path / "workspace"),
        },
        model_adapter=ScriptedHarnessModel(
            ModelTurn(content="只使用平台注册的 Tools；当前没有提交执行计划。")
        ),
    )

    assert result["metadata"]["runtime_execution_mode"] == "dry_run"
    assert not marker.exists()


def test_runtime_turn_uses_request_tenant_managed_context():
    from agents.agent_platform.governance.identity.principal import RequestPrincipal

    store = AdAgentStore(":memory:")
    runtime = AdvertisingComposition(require_llm=False, persistence_store=store, offline_mode=True)
    manager = ManagedSkillManager(store, evaluation_engines=advertising_evaluation_engines())
    manager.create_version("tenant-a", "tenant-skill", "1.0.0", _files("tenant-skill"), "u1")
    manager.publish("tenant-a", "tenant-skill", "1.0.0", runtime=runtime)

    model = ScriptedHarnessModel(ModelTurn(content="查询范围未包含已发布的其他租户 Skill。"))
    runtime.platform_application.agent.model = model
    runtime.run(
        "查询 Meta campaign",
        principal=RequestPrincipal(
            user_id="u2",
            tenant_id="tenant-b",
            permissions=frozenset({"ads.read"}),
        ),
    )
    assert model.messages
    assert "tenant-skill" not in str(model.messages[0])


@pytest.mark.parametrize("permissions", ["ads.read", {"ads.read": True}, ["ads.read", 1]])
def test_request_principal_rejects_malformed_permission_claims(permissions):
    from agents.agent_platform.governance.identity.principal import RequestPrincipal

    with pytest.raises(ValueError, match="permissions"):
        RequestPrincipal(user_id="u1", permissions=permissions)
