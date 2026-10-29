"""Cursor metadata for bounded durable replay, including terminal Runs."""


def run_event_page(manager, run_id: str, after_seq: int, limit: int) -> dict:
    # Reserve one row inside the store's 512-row ceiling to detect continuation.
    size = max(1, min(int(limit), 511))
    cursor = max(0, int(after_seq))
    rows = manager.list_execution_run_events(run_id, after_seq=cursor, limit=size + 1)
    events = rows[:size]
    next_seq = max([int(item.get("seq", 0)) for item in events] + [cursor])
    return {
        "events": events,
        "latest_seq": next_seq,
        "next_after_seq": next_seq,
        "has_more": len(rows) > size,
    }
