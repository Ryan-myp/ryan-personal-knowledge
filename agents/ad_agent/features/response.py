"""Default ad-agent response renderer.

Presentation is an application feature, not an execution responsibility.
Provider-specific result normalization remains owned by the provider Tool or
the cross-channel feature; this renderer only formats the normalized result
shapes already exposed by those contracts.
"""

from __future__ import annotations

from typing import Any

from ..core.cross_channel import CrossChannelAggregator


class AdAgentResponseRenderer:
    renderer_name = "ad-agent"

    def render(
        self,
        intent: Any,
        results: list[dict[str, Any]],
        needs_confirmation: bool,
        analysis: dict[str, Any] | None = None,
    ) -> str:
        success_count = sum(1 for result in results if result.get("success"))
        fail_count = len(results) - success_count
        ask_params_results = [
            result for result in results
            if result.get("needs_confirmation")
            and result.get("confirmation_payload")
        ]
        if ask_params_results:
            questions = []
            for result in ask_params_results:
                payload = result.get("confirmation_payload", {})
                if payload.get("type") in {"ask_params", "ask_account"}:
                    questions.append(
                        payload.get("question", "请提供必要信息")
                    )
            if questions:
                return "\n\n".join(questions)
        if needs_confirmation:
            return "需要确认：部分操作需要您的确认才能继续。"

        analysis = analysis or {}
        if intent.intent_type in {"cross_channel_overview", "cross_channel_compare"}:
            aggregate = analysis.get("cross_channel_summary")
            if aggregate is None:
                aggregate = CrossChannelAggregator().aggregate(results)
            title = (
                "跨渠道 Campaign 对比"
                if intent.intent_type == "cross_channel_compare"
                else "跨渠道 Campaign 总览"
            )
            reply = CrossChannelAggregator().format_markdown(aggregate, title)
            failures = [
                f"  - {item.get('platform', '?')} {item.get('tool', '')}: "
                f"{item.get('error', 'failed')}"
                for item in results if not item.get("success")
            ]
            if failures:
                reply += "\n\n部分渠道未完成：\n" + "\n".join(failures)
            return reply

        if fail_count > 0 and success_count == 0:
            return self._render_read_failures(results)
        if fail_count > 0:
            return (
                f"已完成 {success_count} 项，另有 {fail_count} 项暂未完成。\n"
                + "\n".join(
                    f"  - {self._friendly_error(result)}"
                    for result in results if not result.get("success")
                )
            )

        simulated_results = [
            result for result in results
            if isinstance(result.get("data"), dict)
            and result["data"].get("simulated")
            and result["data"].get("operation") in {"create", "update", "delete"}
        ]
        if simulated_results and len(simulated_results) == len(results):
            if any(
                item.get("data", {}).get("operation") == "delete"
                for item in simulated_results
            ):
                operation = "删除"
            elif str(getattr(intent, "intent_type", "")).startswith("update"):
                operation = "更新"
            else:
                operation = "创建"
            return (
                f"已为你生成{operation}方案（共 {len(simulated_results)} 个广告资源），"
                "当前只展示预览，尚未修改广告账户。\n"
                + "\n".join(
                    f"  - [{result.get('platform', '?')}] {result['tool']} → "
                    f"{self._planned_identifier(result)}"
                    for result in simulated_results
                )
            )

        is_list_op = any(
            "list" in str(result.get("tool", "")).lower()
            for result in results
        )
        is_get_op = any(
            "get_" in str(result.get("tool", "")).lower()
            or "report" in str(result.get("tool", "")).lower()
            for result in results
        )
        if is_list_op or is_get_op:
            return self._append_analysis(
                self._render_read_results(results), analysis
            )

        reply = (
            f"成功执行 {success_count} 个广告操作：\n"
            + "\n".join(
                f"  - [{result.get('platform', '?')}] {result['tool']}"
                for result in results
            )
        )
        return self._append_analysis(reply, analysis)

    def _append_analysis(self, reply: str, analysis: dict[str, Any]) -> str:
        if analysis.get("cross_channel_insights") is not None:
            reply += self._format_insights(analysis["cross_channel_insights"])
        if analysis.get("cross_channel_budget_plan") is not None:
            reply += self._format_budget_plan(analysis["cross_channel_budget_plan"])
        if analysis.get("cross_channel_export") is not None:
            reply += (
                "\n\n已整理好跨渠道报表，可在结果中查看或下载；不会自动修改广告账户。"
            )
        return reply

    @classmethod
    def _friendly_error(cls, result: dict[str, Any]) -> str:
        """Translate execution details into an operator-facing next step."""
        error = str(result.get("error") or "").lower()
        platform = str(result.get("platform") or "该平台")
        if "provider client" in error or "没有配置" in error or "offline_mode" in error:
            return f"{platform} 广告账户暂时无法读取，请检查账户连接和授权范围。"
        if "缺少必需参数" in str(result.get("error") or ""):
            return f"{platform} 查询还缺少必要信息，请补充查询对象或筛选条件。"
        if "timeout" in error or "timed out" in error:
            return f"{platform} 查询响应超时，请稍后重试。"
        return f"{platform} 查询暂时未完成，请稍后重试或缩小查询范围。"

    @classmethod
    def _render_read_failures(cls, results: list[dict[str, Any]]) -> str:
        platforms = list(dict.fromkeys(
            str(result.get("platform") or "广告平台")
            for result in results
            if not result.get("success") and not result.get("skipped")
        ))
        if not platforms:
            return "这次暂时没有查到可展示的数据，请稍后重试。"
        return "暂时无法完成查询：\n" + "\n".join(
            f"- {cls._friendly_error(result)}"
            for result in results
            if not result.get("success") and not result.get("skipped")
        )

    @staticmethod
    def _render_read_results(results: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for result in results:
            platform = result.get("platform", "")
            tool = result.get("tool", "")
            data = result.get("data", {})
            if not isinstance(data, dict):
                lines.append(f"  [{platform}] {tool}")
                continue
            if "campaigns" in data:
                campaigns = data["campaigns"]
                if not campaigns:
                    lines.append(f"[{platform}] 没有找到 Campaign")
                    continue
                lines.append(f"[{platform}] 找到 {len(campaigns)} 个 Campaign：")
                lines.extend(["| # | 名称 | 状态 | 预算 | 目标 |", "|---|------|------|------|------|"])
                for index, campaign in enumerate(campaigns[:10], 1):
                    name = str(
                        campaign.get("campaign_name")
                        or campaign.get("name")
                        or "N/A"
                    )[:30]
                    status = str(
                        campaign.get("operation_status")
                        or campaign.get("status")
                        or "N/A"
                    )
                    budget = campaign.get("budget") or campaign.get("daily_budget") or 0
                    objective = str(
                        campaign.get("objective")
                        or campaign.get("objective_type")
                        or "N/A"
                    )
                    lines.append(
                        f"| {index} | {name} | {status} | ¥{budget} | {objective} |"
                    )
                if len(campaigns) > 10:
                    lines.append(f"... 还有 {len(campaigns) - 10} 个 Campaign")
            elif "accounts" in data:
                accounts = data["accounts"]
                lines.append(f"[{platform}] 找到 {len(accounts)} 个账户：")
                for index, account in enumerate(accounts[:5], 1):
                    lines.append(f"Account #{index}:")
                    if isinstance(account, dict):
                        lines.extend(
                            f"  {key}: {value}"
                            for key, value in account.items()
                            if value not in (None, "")
                        )
            elif "metrics" in data:
                lines.append(f"[{platform}] 报表数据：")
                metrics = data["metrics"]
                if isinstance(metrics, dict):
                    lines.extend(f"  {key}: {value}" for key, value in metrics.items())
            elif "campaign" in data and isinstance(data["campaign"], dict):
                campaign = data["campaign"]
                lines.extend([
                    f"[{platform}] Campaign 详情：",
                    f"名称: {campaign.get('name') or campaign.get('campaign_name') or campaign.get('id') or 'N/A'}",
                    f"ID: {campaign.get('id', '')}",
                    f"状态: {campaign.get('status') or campaign.get('operation_status') or 'N/A'}",
                    f"目标: {campaign.get('objective') or campaign.get('objective_type') or 'N/A'}",
                ])
            elif "report" in data:
                report = data["report"]
                summary = data.get("summary", {})
                lines.append(f"[{platform}] 报表数据（共 {len(report)} 条记录）：")
                if summary:
                    lines.append(
                        f"汇总：展示 {summary.get('total_impressions', 0):,} | "
                        f"点击 {summary.get('total_clicks', 0):,} | "
                        f"花费 ¥{summary.get('total_spend', 0):.2f}"
                    )
                for index, row in enumerate(report[:5], 1):
                    campaign = row.get("campaign", {}) if isinstance(row, dict) else {}
                    name = (
                        campaign.get("name")
                        or campaign.get("campaign_name")
                        or (row.get("campaign_name") if isinstance(row, dict) else None)
                        or (row.get("campaign_id") if isinstance(row, dict) else None)
                        or f"第 {index} 条记录"
                    )
                    lines.append(f"Campaign #{index}: {name}")
                if len(report) > 5:
                    lines.append(f"... 还有 {len(report) - 5} 条记录")
            else:
                lines.append(
                    f"[{platform}] 暂时没有可展示的数据，"
                    "请稍后重试或缩小查询范围。"
                )
        if lines:
            return "\n".join(lines)
        return "查询已完成，但暂时没有可展示的数据。你可以缩小时间范围或补充查询条件。"

    @staticmethod
    def _planned_identifier(result: dict[str, Any]) -> str:
        data = result.get("data", {})
        if not isinstance(data, dict):
            return "planned"
        return next(
            (str(value) for key, value in data.items() if str(key).endswith("_id")),
            "planned",
        )

    @staticmethod
    def _format_insights(payload: dict[str, Any]) -> str:
        lines = ["\n\n跨渠道表现洞察："]
        insights = payload.get("insights") if isinstance(payload, dict) else []
        if not insights:
            lines.append("暂无可用的渠道指标。")
        else:
            for item in insights:
                if not isinstance(item, dict):
                    continue
                suffix = f" / {item.get('currency')}" if item.get("currency") else ""
                lines.append(
                    f"\n• {item.get('platform', 'unknown')}（数据："
                    f"{item.get('data_status', 'unknown')}{suffix}）"
                )
                lines.extend(
                    f"  - {recommendation}"
                    for recommendation in item.get("recommendations", []) or []
                )
        comparability = payload.get("comparability", {}) if isinstance(payload, dict) else {}
        if isinstance(comparability, dict) and comparability.get("status") == "partial":
            lines.append(f"\n以上结论部分可比：{comparability.get('reason') or '指标不完整'}。")
        lines.append("以上仅为只读分析建议，不会自动修改任何平台 Campaign。")
        return "\n".join(lines)

    @staticmethod
    def _format_budget_plan(payload: dict[str, Any]) -> str:
        lines = ["\n\n跨渠道预算建议："]
        if not isinstance(payload, dict) or payload.get("status") == "blocked":
            lines.append(
                "无法生成预算建议："
                + (payload.get("error", "输入或指标不足") if isinstance(payload, dict) else "输入或指标不足")
            )
            return "\n".join(lines)
        lines.extend(["| 平台 | 建议预算 | 评分依据 | 数据状态 |", "|---|---:|---|---|"])
        for item in payload.get("recommendations", []) or []:
            if not isinstance(item, dict):
                continue
            budget = item.get("recommended_budget")
            budget_text = "N/A" if budget is None else f"{float(budget):.2f}"
            if item.get("currency"):
                budget_text += f" {item['currency']}"
            lines.append(
                f"| {item.get('platform', 'unknown')} | {budget_text} | "
                f"{item.get('evidence', '无足够指标')} | {item.get('data_status', 'unknown')} |"
            )
        if payload.get("unallocated_budget"):
            lines.append(f"\n未分配预算：{float(payload['unallocated_budget']):.2f}")
        lines.append(
            payload.get(
                "disclaimer",
                "这是只读预算建议；不会自动修改任何平台 Campaign。",
            )
        )
        return "\n".join(lines)

    @staticmethod
    def render_chat(user_input: str) -> str:
        text = (user_input or "").lower()
        if any(keyword in text for keyword in ("你好", "hello", "hi", "在吗")):
            return (
                "你好！我是 ad-agent，您的广告投放专家助手。\n\n"
                "我可以帮您创建、查询和分析各广告平台 Campaign，"
                "也可以生成跨渠道预算建议。"
            )
        if any(keyword in text for keyword in ("帮助", "help", "你能做什么", "怎么使用")):
            return (
                "我是广告投放专家助手，支持 Meta、TikTok、Google Ads 和 DV360 "
                "的 Campaign 查询、参数校验、dry-run 创建计划、报表分析与跨渠道管理。"
            )
        return "我还没完全理解你的需求。你可以告诉我想查询或管理哪个平台的什么内容。"
