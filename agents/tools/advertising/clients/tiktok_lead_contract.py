"""Lead destination validation shared by the TikTok schema and payload adapter."""

LEAD_DESTINATION_GOALS = {
    "INSTANT_PAGE": ["LEAD_GENERATION"],
    "EXTERNAL_WEBSITE": ["CONVERT"],
}


def validate_lead_group(data: dict) -> None:
    if data.get("promotion_type") != "LEAD_GENERATION":
        raise ValueError("Lead 消息/电话目的地尚未接入完整参数合同；请选择表单获客")
    destination = data.get("promotion_target_type")
    if destination not in LEAD_DESTINATION_GOALS:
        raise ValueError("Lead promotion_target_type 必须是 INSTANT_PAGE 或 EXTERNAL_WEBSITE")
    if data.get("optimization_goal") not in LEAD_DESTINATION_GOALS[destination]:
        raise ValueError(f"Lead optimization_goal 与 {destination} 不匹配")
    if data.get("billing_event") != "OCPM":
        raise ValueError("Lead 表单获客 billing_event 必须是 OCPM")
    if destination == "EXTERNAL_WEBSITE":
        for field in ("pixel_id", "optimization_event"):
            if not data.get(field):
                raise ValueError(f"Lead EXTERNAL_WEBSITE requires {field}")


def validate_lead_ad(data: dict) -> None:
    # Old saved native-form templates did not carry destination context.
    # Preserve those only when they provide the explicit Instant Page.
    destination = data.get("promotion_target_type")
    if not destination and data.get("page_list"):
        destination = "INSTANT_PAGE"
    if destination not in LEAD_DESTINATION_GOALS:
        raise ValueError("Lead ad requires promotion_target_type=INSTANT_PAGE or EXTERNAL_WEBSITE")
    if destination == "INSTANT_PAGE" and not data.get("page_list"):
        raise ValueError("Lead INSTANT_PAGE requires page_list")
    if destination == "EXTERNAL_WEBSITE" and not (
        data.get("landing_page_url") or data.get("landing_page_url_list")
    ):
        raise ValueError("Lead EXTERNAL_WEBSITE requires landing_page_url or landing_page_url_list")
