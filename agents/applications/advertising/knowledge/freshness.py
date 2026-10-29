"""Review periods follow declared knowledge type, rather than document wording."""


def review_window_days(metadata, default=180):
    fast = metadata.get("layer") == "api" or metadata.get("knowledge_type") in {
        "policy",
        "api_reference",
    }
    ceiling = min(default, 30) if fast else default
    requested = metadata.get("review_interval_days", ceiling)
    if type(requested) is not int or not 7 <= requested <= 365:
        return ceiling
    return min(ceiling, requested)
