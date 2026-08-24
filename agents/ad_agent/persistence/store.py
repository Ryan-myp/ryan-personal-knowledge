"""
persistence/store.py - SQLite 持久化存储

Tables:
- sessions: session metadata
- tool_calls: tool invocation history (with input/output/status)
- campaign_state: campaign resource state (shared across sessions)
"""

import json
import sqlite3
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class CampaignRecord:
    """Campaign resource record"""
    id: str
    platform: str                    # meta/google/tiktok/dv360
    campaign_id: str                 # platform-side ID
    name: str
    status: str                      # ACTIVE/PAUSED/DRAFT
    objective: Optional[str] = None
    budget_daily: Optional[float] = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['metadata'] = json.dumps(d['metadata']) if d['metadata'] else '{}'
        return d
    
    @classmethod
    def from_row(cls, row) -> "CampaignRecord":
        # Handle both tuple (from DB cursor) and dict inputs
        if isinstance(row, dict):
            d = row
        else:
            columns = ['id', 'platform', 'campaign_id', 'name', 'status',
                       'objective', 'budget_daily', 'created_at', 'updated_at', 'metadata']
            d = dict(zip(columns, row))
        if d.get('metadata'):
            try:
                d['metadata'] = json.loads(d['metadata'])
            except:
                d['metadata'] = {}
        return cls(**d)


@dataclass
class ToolCallRecord:
    """Tool invocation record"""
    id: str
    session_id: str
    turn_id: str
    tool_name: str
    platform: str
    input_data: dict
    output_data: Optional[dict] = None
    success: bool = True
    error: Optional[str] = None
    started_at: str = ""
    ended_at: str = ""
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['input_data'] = json.dumps(d['input_data']) if d['input_data'] else '{}'
        d['output_data'] = json.dumps(d['output_data']) if d['output_data'] else None
        return d
    
    @classmethod
    def from_row(cls, row) -> "ToolCallRecord":
        # Handle both tuple (from DB cursor) and dict inputs
        if isinstance(row, dict):
            d = row
        else:
            columns = ['id', 'session_id', 'turn_id', 'tool_name', 'platform',
                       'input_data', 'output_data', 'success', 'error', 'started_at', 'ended_at']
            d = dict(zip(columns, row))
        for key in ['input_data', 'output_data']:
            if d.get(key):
                try:
                    d[key] = json.loads(d[key])
                except:
                    d[key] = {}
        return cls(**d)


class AdAgentStore:
    """
    Unified persistence layer (SQLite).
    
    Thread-safe: each connection is independent, read/write operations are locked.
    """
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        account_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata TEXT DEFAULT '{}'
    );
    
    CREATE TABLE IF NOT EXISTS tool_calls (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        platform TEXT NOT NULL,
        input_data TEXT NOT NULL,
        output_data TEXT,
        success INTEGER NOT NULL DEFAULT 1,
        error TEXT,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS campaign_state (
        id TEXT PRIMARY KEY,
        platform TEXT NOT NULL,
        campaign_id TEXT NOT NULL,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'DRAFT',
        objective TEXT,
        budget_daily REAL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata TEXT DEFAULT '{}'
    );
    
    CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
    CREATE INDEX IF NOT EXISTS idx_tool_calls_turn ON tool_calls(session_id, turn_id);
    CREATE INDEX IF NOT EXISTS idx_campaigns_platform ON campaign_state(platform, campaign_id);
    CREATE INDEX IF NOT EXISTS idx_campaigns_name ON campaign_state(name);
    """
    
    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-safe database connection (single connection mode)"""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn
    
    def _init_db(self):
        """Initialize table structure"""
        with self._lock:
            conn = self._get_conn()
            conn.executescript(self.SCHEMA)
            conn.commit()
    
    def close(self):
        """Close database connection"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
    
    # -- Session --
    
    def create_session(self, session_id: str, user_id: str, account_id: str = None, 
                       metadata: dict = None) -> None:
        with self._lock:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            sql = "INSERT OR REPLACE INTO sessions (session_id, user_id, account_id, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?)"
            conn.execute(sql, (session_id, user_id, account_id, now, now, json.dumps(metadata or {})))
            conn.commit()
    
    def update_session(self, session_id: str, metadata: dict = None) -> None:
        with self._lock:
            conn = self._get_conn()
            sql = "UPDATE sessions SET updated_at = ?, metadata = ? WHERE session_id = ?"
            conn.execute(sql, (datetime.now().isoformat(), json.dumps(metadata or {}), session_id))
            conn.commit()
    
    def get_session(self, session_id: str) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if row:
                return dict(row)
            return None
    
    def list_sessions(self, user_id: str = None, limit: int = 50) -> List[dict]:
        with self._lock:
            conn = self._get_conn()
            if user_id:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                    (user_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
    
    # -- Tool Calls --
    
    def record_tool_call(self, record: ToolCallRecord) -> None:
        d = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            sql = """INSERT INTO tool_calls 
                     (id, session_id, turn_id, tool_name, platform, input_data, output_data, 
                      success, error, started_at, ended_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            conn.execute(sql, (
                d['id'], d['session_id'], d['turn_id'], d['tool_name'], d['platform'],
                d['input_data'], d['output_data'], int(d['success']), d['error'],
                d['started_at'], d['ended_at']
            ))
            conn.commit()
    
    def list_tool_calls(self, session_id: str, turn_id: str = None, limit: int = 100) -> List[ToolCallRecord]:
        with self._lock:
            conn = self._get_conn()
            if turn_id:
                rows = conn.execute(
                    "SELECT * FROM tool_calls WHERE session_id = ? AND turn_id = ? ORDER BY started_at ASC LIMIT ?",
                    (session_id, turn_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tool_calls WHERE session_id = ? ORDER BY started_at DESC LIMIT ?",
                    (session_id, limit)
                ).fetchall()
            return [ToolCallRecord.from_row(dict(r)) for r in rows]
    
    # -- Campaign State --
    
    def save_campaign(self, record: CampaignRecord) -> None:
        d = record.to_dict()
        with self._lock:
            conn = self._get_conn()
            sql = """INSERT INTO campaign_state 
                     (id, platform, campaign_id, name, status, objective, budget_daily, 
                      created_at, updated_at, metadata)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT(id) DO UPDATE SET
                       status = excluded.status,
                       updated_at = excluded.updated_at,
                       metadata = excluded.metadata"""
            conn.execute(sql, (
                d['id'], d['platform'], d['campaign_id'], d['name'], d['status'],
                d['objective'], d['budget_daily'], d['created_at'], d['updated_at'], d['metadata']
            ))
            conn.commit()
    
    def get_campaign(self, platform: str, campaign_id: str) -> Optional[CampaignRecord]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM campaign_state WHERE platform = ? AND campaign_id = ?",
                (platform, campaign_id)
            ).fetchone()
            return CampaignRecord.from_row(dict(row)) if row else None
    
    def list_campaigns(self, platform: str = None, status: str = None, limit: int = 100) -> List[CampaignRecord]:
        with self._lock:
            conn = self._get_conn()
            if platform and status:
                rows = conn.execute(
                    "SELECT * FROM campaign_state WHERE platform = ? AND status = ? ORDER BY updated_at DESC LIMIT ?",
                    (platform, status, limit)
                ).fetchall()
            elif platform:
                rows = conn.execute(
                    "SELECT * FROM campaign_state WHERE platform = ? ORDER BY updated_at DESC LIMIT ?",
                    (platform, limit)
                ).fetchall()
            elif status:
                rows = conn.execute(
                    "SELECT * FROM campaign_state WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM campaign_state ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [CampaignRecord.from_row(dict(r)) for r in rows]
    
    def update_campaign_status(self, platform: str, campaign_id: str, status: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE campaign_state SET status = ?, updated_at = ? WHERE platform = ? AND campaign_id = ?",
                (status, datetime.now().isoformat(), platform, campaign_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_campaign(self, platform: str, campaign_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "DELETE FROM campaign_state WHERE platform = ? AND campaign_id = ?",
                (platform, campaign_id)
            )
            conn.commit()
            return cursor.rowcount > 0
