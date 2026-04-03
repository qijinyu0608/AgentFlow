import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List
import os

import yaml

from agentmesh.common.paths import get_config_path, get_runtime_root

PROJECT_ROOT = get_runtime_root()
CONFIG_PATH = get_config_path()


def _default_db_path(filename: str) -> str:
    new_path = PROJECT_ROOT / "data" / "sqlite" / filename
    legacy_path = PROJECT_ROOT / filename
    if new_path.exists() or not legacy_path.exists():
        return str(new_path)
    return str(legacy_path)


def _resolve_db_path(path_value: str) -> str:
    p = Path(path_value).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return str(p)


def _load_database_cfg() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict):
            return data.get("database", {}) or {}
    except Exception:
        return {}
    return {}


def _build_db_paths() -> dict:
    cfg = _load_database_cfg()
    legacy = os.environ.get("AGENTMESH_DB_PATH") or cfg.get("db_path") or _default_db_path("agentmesh.db")
    conversation = (
        os.environ.get("AGENTMESH_CONVERSATION_DB_PATH")
        or cfg.get("conversation_db_path")
        or _default_db_path("conversation.db")
    )
    memory = (
        os.environ.get("AGENTMESH_MEMORY_DB_PATH")
        or cfg.get("memory_db_path")
        or _default_db_path("memory.db")
    )
    vector = (
        os.environ.get("AGENTMESH_VECTOR_DB_PATH")
        or cfg.get("vector_db_path")
        or _default_db_path("vector.db")
    )
    return {
        "conversation": _resolve_db_path(str(conversation)),
        "memory": _resolve_db_path(str(memory)),
        "vector": _resolve_db_path(str(vector)),
    }


CONVERSATION_SCHEMA: List[str] = [
    """
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        task_status TEXT NOT NULL,
        task_name TEXT NOT NULL,
        task_content TEXT NOT NULL,
        submit_time TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(task_status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_submit_time ON tasks(submit_time)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_name ON tasks(task_name)",
    """
    CREATE TABLE IF NOT EXISTS workflow_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        agent TEXT NOT NULL,
        phase TEXT NOT NULL,
        status TEXT NOT NULL,
        content TEXT NOT NULL,
        ts TIMESTAMP NOT NULL,
        raw_json TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_workflow_events_task_seq ON workflow_events(task_id, seq)",
    "CREATE INDEX IF NOT EXISTS idx_workflow_events_task_ts ON workflow_events(task_id, ts)",
    """
    CREATE TABLE IF NOT EXISTS conversations (
        conversation_id TEXT PRIMARY KEY,
        title TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at)",
    """
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        ts TIMESTAMP NOT NULL,
        seq INTEGER NOT NULL,
        meta_json TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_conv_messages_conv_seq ON conversation_messages(conversation_id, seq)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_conv_messages_conv_seq ON conversation_messages(conversation_id, seq)",
    "CREATE INDEX IF NOT EXISTS idx_conv_messages_conv_ts ON conversation_messages(conversation_id, ts)",
    """
    CREATE TABLE IF NOT EXISTS conversation_summaries (
        conversation_id TEXT PRIMARY KEY,
        summary TEXT NOT NULL,
        window_start_seq INTEGER NOT NULL DEFAULT 0,
        window_end_seq INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        meta_json TEXT DEFAULT '{}'
    )
    """,
]


MEMORY_SCHEMA: List[str] = [
    """
    CREATE TABLE IF NOT EXISTS memory_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT,
        scope TEXT NOT NULL DEFAULT 'conversation',
        kind TEXT NOT NULL DEFAULT 'fact',
        content TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        source_message_id INTEGER,
        confidence REAL DEFAULT 0.5,
        tags_json TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_memory_items_conv_status ON memory_items(conversation_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_memory_items_scope_kind ON memory_items(scope, kind)",
    """
    CREATE TABLE IF NOT EXISTS rag_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT NOT NULL,
        file_ext TEXT NOT NULL,
        mime_type TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        file_hash TEXT NOT NULL,
        storage_path TEXT NOT NULL,
        raw_text TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'uploaded',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_rag_documents_hash ON rag_documents(file_hash)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_documents_hash ON rag_documents(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_rag_documents_status ON rag_documents(status)",
    "CREATE INDEX IF NOT EXISTS idx_rag_documents_created_at ON rag_documents(created_at)",
    """
    CREATE TABLE IF NOT EXISTS rag_document_annotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        paragraph_marks_json TEXT NOT NULL DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(document_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_rag_annotations_doc_id ON rag_document_annotations(document_id)",
    """
    CREATE TABLE IF NOT EXISTS rag_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        token_len INTEGER NOT NULL DEFAULT 0,
        tags_json TEXT NOT NULL DEFAULT '[]',
        is_active INTEGER NOT NULL DEFAULT 1,
        memory_item_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(document_id, chunk_index)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks(document_id, chunk_index)",
    "CREATE INDEX IF NOT EXISTS idx_rag_chunks_memory_item ON rag_chunks(memory_item_id)",
]


VECTOR_SCHEMA: List[str] = [
    """
    CREATE TABLE IF NOT EXISTS memory_embeddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_item_id INTEGER NOT NULL,
        model TEXT NOT NULL,
        vector_blob BLOB NOT NULL,
        dim INTEGER NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(memory_item_id, model)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_memory_embeddings_item ON memory_embeddings(memory_item_id)",
    """
    CREATE TABLE IF NOT EXISTS vector_map (
        chunk_id TEXT PRIMARY KEY,
        vector_id INTEGER UNIQUE NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vector_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
]


class DatabaseManager:
    """Simple SQLite manager for one database domain."""

    def __init__(self, db_path: str, init_sql: List[str]):
        self.db_path = str(Path(db_path))
        self._init_sql = list(init_sql)
        self._init_database()

    def _init_database(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            for statement in self._init_sql:
                cursor.execute(statement)
            conn.commit()

    @staticmethod
    def _configure_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA temp_store = MEMORY")
        return conn

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        self._configure_connection(conn)
        try:
            yield conn
        finally:
            conn.close()

    def execute_query(self, query: str, params: tuple = ()) -> list:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_update(self, query: str, params: tuple = ()) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount

    def execute_insert(self, query: str, params: tuple = ()) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return int(cursor.lastrowid)

    def checkpoint_and_compact(self) -> None:
        with self.get_connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
            conn.commit()


DB_PATHS = _build_db_paths()

conversation_db_manager = DatabaseManager(DB_PATHS["conversation"], CONVERSATION_SCHEMA)
memory_db_manager = DatabaseManager(DB_PATHS["memory"], MEMORY_SCHEMA)
vector_db_manager = DatabaseManager(DB_PATHS["vector"], VECTOR_SCHEMA)

# Backward compatibility for code paths still using db_manager for task/conversation data.
db_manager = conversation_db_manager
