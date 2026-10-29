"""Bounded feedback review queries within an authorized reviewer's tenant."""

from dataclasses import dataclass
from typing import Any

from agents.agent_platform.evals.regression import RegressionAssertions


@dataclass(frozen=True)
class FeedbackReviewQuery:
    tenant_id: str
    status: str = 'pending'
    page: int = 1
    limit: int = 10
    search: str = ''
    since: str | None = None
    until: str | None = None

    def __post_init__(self):
        if not self.tenant_id.strip():
            raise ValueError('feedback review requires an authenticated tenant')
        if self.status not in {'pending', 'candidate', 'dismissed', 'all'}:
            raise ValueError('unsupported feedback review status')
        if not 1 <= self.page <= 10000 or not 1 <= self.limit <= 100:
            raise ValueError('invalid feedback page or page size')
        if len(self.search) > 200:
            raise ValueError('feedback search exceeds 200 characters')
        if self.since and self.until and self.since >= self.until:
            raise ValueError('start time must be before end time')


_FROM = """FROM conversation_feedback AS feedback
    JOIN sessions AS session ON session.session_id = feedback.session_id
        AND session.tenant_id = feedback.tenant_id"""
_COLUMNS = """feedback.feedback_id, feedback.session_id, feedback.turn_id,
    feedback.user_id, feedback.rating, SUBSTR(feedback.reason, 1, 1000) AS reason,
    feedback.submitted_at, feedback.review_status, feedback.reviewer_id,
    feedback.reviewed_at, SUBSTR(feedback.expected_behavior, 1, 2000) AS expected_behavior,
    feedback.assertions,
    (SELECT SUBSTR(message.content, 1, 4000) FROM conversation_messages AS message
     WHERE message.session_id = feedback.session_id AND message.turn_id = feedback.turn_id
        AND message.role = 'user'
     ORDER BY message.created_at DESC, message.message_id DESC LIMIT 1) AS user_input,
    (SELECT SUBSTR(message.content, 1, 4000) FROM conversation_messages AS message
     WHERE message.session_id = feedback.session_id AND message.turn_id = feedback.turn_id
        AND message.role = 'assistant'
     ORDER BY message.created_at DESC, message.message_id DESC LIMIT 1) AS assistant_reply"""


def _where(filters: FeedbackReviewQuery) -> tuple[str, list[Any]]:
    clauses = ["feedback.tenant_id = ?", "feedback.rating = 'negative'"]
    values: list[Any] = [filters.tenant_id]
    if filters.status != 'all':
        clauses.append('feedback.review_status = ?')
        values.append(filters.status)
    for operator, date in [('>=', filters.since), ('<', filters.until)]:
        if date is not None:
            clauses.append(f'feedback.submitted_at {operator} ?')
            values.append(date)
    if filters.search.strip():
        text = filters.search.strip().replace('!', '!!').replace('%', '!%').replace('_', '!_')
        clauses.append("""(feedback.reason LIKE ? ESCAPE '!'
            OR feedback.expected_behavior LIKE ? ESCAPE '!'
            OR EXISTS (SELECT 1 FROM conversation_messages AS message
                WHERE message.session_id = feedback.session_id
                    AND message.turn_id = feedback.turn_id
                    AND message.role IN ('user', 'assistant')
                    AND message.content LIKE ? ESCAPE '!'))""")
        values.extend([f'%{text}%'] * 3)
    return ' AND '.join(clauses), values


def _item(row: Any) -> dict[str, Any]:
    item = dict(row)
    for field in ['reason', 'expected_behavior', 'user_input', 'assistant_reply']:
        item[field] = str(item[field] or '')
    item['assertions'] = RegressionAssertions.model_validate_json(
        row['assertions'] or '{}',
    ).model_dump(exclude_defaults=True)
    return item


def read_feedback_review_page(connection: Any, filters: FeedbackReviewQuery) -> dict[str, Any]:
    where, values = _where(filters)
    total = int(connection.execute(
        f'SELECT COUNT(*) AS total {_FROM} WHERE {where}', values,
    ).fetchone()['total'])
    pages = max(1, (total + filters.limit - 1) // filters.limit)
    page = min(filters.page, pages)
    rows = connection.execute(
        f'SELECT {_COLUMNS} {_FROM} WHERE {where} '
        'ORDER BY feedback.submitted_at DESC, feedback.feedback_id ASC LIMIT ? OFFSET ?',
        [*values, filters.limit, (page - 1) * filters.limit],
    ).fetchall()
    return {
        'items': [_item(row) for row in rows],
        'pagination': {'page': page, 'limit': filters.limit, 'total': total, 'pages': pages,
                       'has_next': page < pages, 'has_previous': page > 1},
    }
