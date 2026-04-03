#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


TABLES_BY_TARGET: Dict[str, List[str]] = {
    "conversation": [
        "tasks",
        "workflow_events",
        "conversations",
        "conversation_messages",
        "conversation_summaries",
    ],
    "memory": [
        "memory_items",
        "rag_documents",
        "rag_document_annotations",
        "rag_chunks",
    ],
    "vector": [
        "memory_embeddings",
        "vector_map",
        "vector_meta",
    ],
}


def _default_sqlite_dir(root: Path) -> Path:
    return root / "data" / "sqlite"


def _default_backup_dir(source_db: Path) -> Path:
    sqlite_dir = source_db.parent
    if sqlite_dir.name == "sqlite":
        return sqlite_dir.parent / "backups" / "split-db"
    return sqlite_dir / "backups" / "split-db"


def _backup_file(src: Path, backup_dir: Path) -> Path | None:
    if not src.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = backup_dir / f"{src.name}.{stamp}.bak"
    shutil.copy2(src, dst)
    return dst


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def _ensure_table_exists(source: sqlite3.Connection, target: sqlite3.Connection, table: str) -> None:
    if _table_exists(target, table):
        return
    row = source.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if not row or not row["sql"]:
        raise RuntimeError(f"Cannot find source schema for table: {table}")
    target.execute(str(row["sql"]))


def _get_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [str(r["name"]) for r in rows]


def _copy_table(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    table: str,
    dry_run: bool,
) -> Tuple[int, int]:
    if not _table_exists(source, table):
        return 0, 0
    _ensure_table_exists(source=source, target=target, table=table)

    src_cols = _get_columns(source, table)
    dst_cols = _get_columns(target, table)
    cols = [c for c in src_cols if c in dst_cols]
    if not cols:
        return 0, 0

    col_sql = ", ".join(cols)
    rows = source.execute(f"SELECT {col_sql} FROM {table}").fetchall()
    src_count = len(rows)
    if dry_run:
        return src_count, src_count

    target.execute(f"DELETE FROM {table}")
    if rows:
        placeholders = ", ".join(["?"] * len(cols))
        target.executemany(
            f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
            [tuple(r[c] for c in cols) for r in rows],
        )
    dst_count = target.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()["cnt"]
    return int(src_count), int(dst_count)


def _validate_cross_db(memory_conn: sqlite3.Connection, vector_conn: sqlite3.Connection) -> Dict[str, int]:
    embedding_count_row = vector_conn.execute(
        "SELECT COUNT(*) AS cnt FROM memory_embeddings"
    ).fetchone()
    # sqlite cannot join two independent connections; validate in python instead.
    mem_ids = {
        int(r["id"])
        for r in memory_conn.execute("SELECT id FROM memory_items").fetchall()
    }
    orphan = 0
    for r in vector_conn.execute("SELECT memory_item_id FROM memory_embeddings").fetchall():
        mid = int(r["memory_item_id"])
        if mid not in mem_ids:
            orphan += 1
    return {
        "memory_items": len(mem_ids),
        "memory_embeddings": int(embedding_count_row["cnt"] or 0) if embedding_count_row else 0,
        "orphan_embeddings": orphan,
    }


def run(
    source_db: Path,
    conversation_db: Path,
    memory_db: Path,
    vector_db: Path,
    dry_run: bool = False,
) -> int:
    print(f"[info] source={source_db}")
    print(f"[info] conversation_db={conversation_db}")
    print(f"[info] memory_db={memory_db}")
    print(f"[info] vector_db={vector_db}")
    print(f"[info] dry_run={dry_run}")

    if not source_db.exists():
        raise FileNotFoundError(f"Source database not found: {source_db}")

    # Do not accidentally overwrite source in big-bang mode.
    dest_paths = {conversation_db.resolve(), memory_db.resolve(), vector_db.resolve()}
    if source_db.resolve() in dest_paths:
        raise RuntimeError("Destination DB path must differ from source DB path")

    if not dry_run:
        backup_dir = _default_backup_dir(source_db)
        src_bak = _backup_file(source_db, backup_dir)
        conv_bak = _backup_file(conversation_db, backup_dir)
        mem_bak = _backup_file(memory_db, backup_dir)
        vec_bak = _backup_file(vector_db, backup_dir)
        print(f"[backup] source => {src_bak}")
        print(f"[backup] conversation => {conv_bak}")
        print(f"[backup] memory => {mem_bak}")
        print(f"[backup] vector => {vec_bak}")

    source = _connect(source_db)
    conv = _connect(conversation_db)
    mem = _connect(memory_db)
    vec = _connect(vector_db)
    report: List[Tuple[str, str, int, int]] = []
    try:
        conv.execute("PRAGMA foreign_keys=OFF")
        mem.execute("PRAGMA foreign_keys=OFF")
        vec.execute("PRAGMA foreign_keys=OFF")
        if not dry_run:
            conv.execute("BEGIN")
            mem.execute("BEGIN")
            vec.execute("BEGIN")

        target_map = {"conversation": conv, "memory": mem, "vector": vec}
        for target_name, tables in TABLES_BY_TARGET.items():
            target_conn = target_map[target_name]
            for table in tables:
                src_count, dst_count = _copy_table(
                    source=source,
                    target=target_conn,
                    table=table,
                    dry_run=dry_run,
                )
                report.append((target_name, table, src_count, dst_count))

        if not dry_run:
            conv.commit()
            mem.commit()
            vec.commit()

        print("\n[report] table counts")
        all_ok = True
        for target_name, table, src_count, dst_count in report:
            ok = src_count == dst_count
            all_ok = all_ok and ok
            status = "OK" if ok else "MISMATCH"
            print(f"  - {target_name}.{table}: source={src_count}, target={dst_count} [{status}]")

        cross = _validate_cross_db(memory_conn=mem, vector_conn=vec)
        print("\n[report] cross-db check")
        print(f"  - memory_items={cross['memory_items']}")
        print(f"  - memory_embeddings={cross['memory_embeddings']}")
        print(f"  - orphan_embeddings={cross['orphan_embeddings']}")
        if cross["orphan_embeddings"] > 0:
            all_ok = False

        if not all_ok:
            print("\n[result] FAILED: migration validation failed")
            return 1
        print("\n[result] SUCCESS: migration validation passed")
        return 0
    except Exception:
        if not dry_run:
            conv.rollback()
            mem.rollback()
            vec.rollback()
        raise
    finally:
        source.close()
        conv.close()
        mem.close()
        vec.close()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sqlite_dir = _default_sqlite_dir(root)
    parser = argparse.ArgumentParser(
        description="Split single data/sqlite/agentmesh.db into conversation/memory/vector sqlite databases",
    )
    parser.add_argument("--source-db", default=str(sqlite_dir / "agentmesh.db"))
    parser.add_argument("--conversation-db", default=str(sqlite_dir / "conversation.db"))
    parser.add_argument("--memory-db", default=str(sqlite_dir / "memory.db"))
    parser.add_argument("--vector-db", default=str(sqlite_dir / "vector.db"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    return run(
        source_db=Path(args.source_db).expanduser().resolve(),
        conversation_db=Path(args.conversation_db).expanduser().resolve(),
        memory_db=Path(args.memory_db).expanduser().resolve(),
        vector_db=Path(args.vector_db).expanduser().resolve(),
        dry_run=bool(args.dry_run),
    )


if __name__ == "__main__":
    raise SystemExit(main())
