"""SQL dialect conversion for the MySQL persistence adapter."""

import re

def _mysql_schema(sql: str) -> str:
    """Convert the current SQLite DDL to valid InnoDB DDL."""
    # 191 characters keeps composite utf8mb4 indexes within InnoDB's
    # portable 3072-byte limit. Large unindexed text is promoted below.
    sql = re.sub(r"\bTEXT\b", "VARCHAR(191)", sql)
    sql = re.sub(r"\bREAL\b", "DOUBLE", sql)
    sql = re.sub(r"\bINTEGER\b", "BIGINT", sql)
    large_columns = {
        "metadata", "content", "tags", "template_values", "input_data", "output_data", "files",
        "manifest", "evaluation_report", "report", "payload", "result", "error",
        "vector", "expected_behavior", "assertions",
        # External MCP schemas and validation reports are bounded by the
        # control-plane contract, not by the 191-char index-safe fallback.
        "input_schema", "annotations", "validation_report", "description", "last_error",
        "intent_types", "intent_aliases", "skill_refs", "required_permissions", "traits",
        "wikilinks",
    }
    for column in large_columns:
        sql = re.sub(
            rf"(\b{re.escape(column)}\s+)VARCHAR\(191\)",
            r"\1LONGTEXT", sql, flags=re.IGNORECASE,
        )
    sql = re.sub(r"\btitle\s+VARCHAR\(191\)", "title VARCHAR(255)", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bsource_ref\s+VARCHAR\(191\)", "source_ref VARCHAR(1024)", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bendpoint\s+VARCHAR\(191\)", "endpoint VARCHAR(2048)", sql, flags=re.IGNORECASE)
    # Index prefixes are valid for character columns, not numeric columns.
    # In particular execution_event_repairs has UNIQUE(run_id, seq); blindly
    # appending ``(191)`` to ``seq`` makes the generated MySQL DDL invalid.
    prefixable = {
        "run_id", "tenant_id", "skill_name", "version", "plugin_id", "idempotency_key",
        "schedule_id", "scheduled_for",
    }

    def unique_prefix(match: re.Match[str]) -> str:
        columns = [item.strip() for item in match.group(1).split(",")]
        rendered = []
        for column in columns:
            bare = column.strip("`")
            rendered.append(f"{column}(191)" if bare in prefixable else column)
        return "UNIQUE (" + ", ".join(rendered) + ")"
    sql = re.sub(r"UNIQUE\s*\(([^)]*)\)", unique_prefix, sql, flags=re.IGNORECASE)
    # MySQL does not permit literal defaults on LONGTEXT/BLOB columns.
    sql = re.sub(
        r"\bLONGTEXT(\s+NOT\s+NULL)?\s+DEFAULT\s+'[^']*'",
        lambda match: "LONGTEXT" + (match.group(1) or ""),
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"CREATE\s+(UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS",
        r"CREATE \1INDEX", sql, flags=re.IGNORECASE,
    )

    def force_innodb(match: re.Match[str]) -> str:
        statement = match.group(0)
        if re.search(r"\bENGINE\s*=", statement, flags=re.IGNORECASE):
            return statement
        return statement[:-1] + " ENGINE=InnoDB;"

    # Locking/foreign-key semantics are part of this backend contract. Do not
    # silently depend on a server's default storage engine.
    return re.sub(
        r"CREATE\s+TABLE\b.*?;", force_innodb, sql,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _translate_sql(statement: str) -> str:
    """Translate the limited SQLite DML syntax used by ``AdAgentStore``."""
    statement = statement.strip()
    # SQLite uses BEGIN IMMEDIATE for the scheduler's claim transaction;
    # MySQL's equivalent is a normal transaction whose SELECT ... FOR UPDATE
    # statements acquire the row locks.
    statement = re.sub(r"^BEGIN\s+IMMEDIATE$", "BEGIN", statement, flags=re.IGNORECASE)
    statement = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT IGNORE INTO", statement, flags=re.IGNORECASE)
    statement = re.sub(r"\bINSERT\s+OR\s+REPLACE\s+INTO\b", "REPLACE INTO", statement, flags=re.IGNORECASE)
    statement = re.sub(r"\browid\b", "message_id", statement, flags=re.IGNORECASE)
    match = re.search(
        r"ON\s+CONFLICT\s*\([^)]*\)\s+DO\s+UPDATE\s+SET\s+(.+)$",
        statement, flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        assignments = re.sub(
            r"\bexcluded\.([A-Za-z_][A-Za-z0-9_]*)\b",
            r"VALUES(\1)", match.group(1), flags=re.IGNORECASE,
        )
        statement = statement[:match.start()] + "ON DUPLICATE KEY UPDATE " + assignments
    return statement.replace("?", "%s")
