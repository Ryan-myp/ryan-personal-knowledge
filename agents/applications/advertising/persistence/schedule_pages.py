"""Scoped, bounded schedule browsing queries owned by the persistence layer."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SchedulePageQuery:
    tenant_id: str
    user_id: str
    page: int = 1
    limit: int = 20
    statuses: tuple[str, ...] = ()
    search: str = ''
    schedule_id: str | None = None
    since: str | None = None
    until: str | None = None

    def __post_init__(self):
        if not self.tenant_id or not self.user_id:
            raise ValueError('schedule browsing requires an authenticated scope')
        if not 1 <= self.limit <= 500 or not 1 <= self.page <= 10000:
            raise ValueError('invalid schedule page or page size')
        if len(self.search) > 200:
            raise ValueError('schedule search exceeds 200 characters')
        if self.since and self.until and self.since >= self.until:
            raise ValueError('start time must be before end time')


def _conditions(filters: SchedulePageQuery, runs: bool) -> tuple[str, list[Any]]:
    allowed = ({'queued', 'running', 'succeeded', 'failed', 'partially_failed',
                'awaiting_input', 'cancelled', 'recovery_required', 'skipped'}
               if runs else {'active', 'paused'})
    if set(filters.statuses) - allowed:
        raise ValueError('unsupported schedule status filter')
    clauses = ['s.tenant_id = ?', 's.user_id = ?']
    values: list[Any] = [filters.tenant_id, filters.user_id]
    if filters.statuses:
        clauses.append('s.status IN (' + ','.join('?' for _ in filters.statuses) + ')')
        values.extend(filters.statuses)
    if filters.search.strip():
        columns = ('schedule_run_id', 'task_id', 'error') if runs else ('name', 'prompt')
        clauses.append('(' + ' OR '.join(f"s.{col} LIKE ? ESCAPE '!'" for col in columns) + ')')
        text = filters.search.strip().replace('!', '!!').replace('%', '!%').replace('_', '!_')
        values.extend([f'%{text}%'] * len(columns))
    if runs:
        for column, operator, value in (
            ('schedule_id', '=', filters.schedule_id),
            ('scheduled_for', '>=', filters.since), ('scheduled_for', '<', filters.until),
        ):
            if value is not None:
                clauses.append(f's.{column} {operator} ?')
                values.append(value)
    return ' AND '.join(clauses), values


_SCHEDULE_COLUMNS = """s.schedule_id, s.name, SUBSTR(s.prompt, 1, 280) AS prompt_preview,
    s.cron_expression, s.timezone, s.status, s.next_run_at, s.last_run_at,
    s.last_run_status, s.run_count, s.success_count, s.failure_count,
    (SELECT r.status FROM scheduled_task_runs r WHERE r.schedule_id = s.schedule_id
        AND r.tenant_id = s.tenant_id AND r.user_id = s.user_id
        ORDER BY r.scheduled_for DESC, r.schedule_run_id DESC LIMIT 1) AS latest_run_status,
    EXISTS(SELECT 1 FROM scheduled_task_runs r WHERE r.schedule_id = s.schedule_id
        AND r.tenant_id = s.tenant_id AND r.user_id = s.user_id
        AND r.status IN ('queued', 'running')) AS has_pending_run"""
_RUN_COLUMNS = """s.schedule_run_id, s.schedule_id, s.scheduled_for, s.status,
    s.task_id, s.started_at, s.finished_at, SUBSTR(s.error, 1, 500) AS error, s.created_at"""


def read_schedule_page(conn: Any, filters: SchedulePageQuery, *, runs: bool = False) -> dict:
    """Two database reads per page; no payloads, result blobs or per-row API calls."""
    table = 'scheduled_task_runs' if runs else 'scheduled_tasks'
    where, values = _conditions(filters, runs)
    total = int(conn.execute(
        f'SELECT COUNT(*) AS total FROM {table} s WHERE {where}', values,
    ).fetchone()['total'])
    pages = max(1, (total + filters.limit - 1) // filters.limit)
    page = min(filters.page, pages)
    columns = _RUN_COLUMNS if runs else _SCHEDULE_COLUMNS
    order = ('s.scheduled_for DESC, s.schedule_run_id DESC' if runs
             else 'COALESCE(s.next_run_at, s.updated_at) ASC, s.schedule_id ASC')
    rows = conn.execute(
        f'SELECT {columns} FROM {table} s WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?',
        [*values, filters.limit, (page - 1) * filters.limit],
    ).fetchall()
    return {
        'runs' if runs else 'schedules': [dict(row) for row in rows],
        'pagination': {'page': page, 'limit': filters.limit, 'total': total,
                       'pages': pages, 'has_next': page < pages, 'has_previous': page > 1},
    }
