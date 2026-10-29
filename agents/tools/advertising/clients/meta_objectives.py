"""Current ODAX objectives and compatibility aliases at the Meta boundary."""

META_CANONICAL_OBJECTIVES = (
    "OUTCOME_SALES", "OUTCOME_LEADS", "OUTCOME_TRAFFIC", "OUTCOME_AWARENESS",
    "OUTCOME_ENGAGEMENT", "OUTCOME_APP_PROMOTION",
)
META_OBJECTIVE_ALIASES = {
    "OUTCOME_MESSAGES": "OUTCOME_ENGAGEMENT",
    "APP_INSTALLS": "OUTCOME_APP_PROMOTION",
    "PRODUCT_CATALOG_SALES": "OUTCOME_SALES",
    "CONVERSIONS": "OUTCOME_SALES",
    "TRAFFIC": "OUTCOME_TRAFFIC",
    "LINK_CLICKS": "OUTCOME_TRAFFIC",
}


def normalize_meta_objective(value: str) -> str:
    objective = str(value).strip().upper()
    objective = META_OBJECTIVE_ALIASES.get(objective, objective)
    if objective not in META_CANONICAL_OBJECTIVES:
        raise ValueError("Meta objective 必须是有效的 ODAX 目标")
    return objective
