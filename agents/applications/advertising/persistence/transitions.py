"""Workflow state transitions shared by persistence operations."""

WORKFLOW_TRANSITIONS = {
    "planned": {"planned", "running", "awaiting_confirmation", "blocked", "failed", "cancelled"},
    "running": {"running", "planned", "awaiting_confirmation", "blocked", "failed", "succeeded", "partially_failed", "recovery_required", "cancelled"},
    "awaiting_confirmation": {"awaiting_confirmation", "running", "blocked", "failed", "cancelled"},
    "partially_failed": {"partially_failed", "recovery_required", "succeeded", "failed", "cancelled"},
    "recovery_required": {"recovery_required", "running", "succeeded", "failed", "cancelled"},
    "blocked": {"blocked", "running", "failed", "recovery_required", "succeeded", "cancelled"},
    "failed": {"failed", "running", "recovery_required", "succeeded", "cancelled"},
    "succeeded": {"succeeded"},
    "cancelled": {"cancelled"},
}


WORKFLOW_ITEM_TRANSITIONS = {
    "planned": {"planned", "awaiting_confirmation", "running", "succeeded", "failed", "unknown", "skipped"},
    "running": {"running", "awaiting_confirmation", "succeeded", "failed", "unknown", "skipped"},
    "awaiting_confirmation": {"awaiting_confirmation", "succeeded", "failed", "unknown"},
    "failed": {"failed", "succeeded", "unknown"},
    "unknown": {"unknown", "succeeded", "failed"},
    "succeeded": {"succeeded"},
    "unsupported": {"unsupported"},
    "skipped": {"skipped"},
}
