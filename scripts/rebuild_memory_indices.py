#!/usr/bin/env python3
"""Backup, repair, and rebuild AgentMesh memory/vector state."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair AgentMesh long-term/RAG/vector state")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-reindex", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=700)
    parser.add_argument("--overlap", type=int, default=100)
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from agentmesh.service.rag_ops_service import rag_ops_service

    if args.dry_run:
        overview = rag_ops_service.get_overview()
        stats = overview.get("stats", {})
        with sqlite3.connect(rag_ops_service.memory_db.db_path) as mem:
            cur = mem.cursor()
            cur.execute(
                """
                SELECT COUNT(*)
                FROM memory_items
                WHERE scope='knowledge_base' AND kind='long_term_profile'
                """
            )
            migrate_long_term_items = int((cur.fetchone() or [0])[0] or 0)
        print(f"[plan] migrate_long_term_items={migrate_long_term_items}")
        print(f"[plan] orphan_doc_chunks={int(stats.get('orphan_doc_chunks') or 0)}")
        print(f"[plan] indexed_documents_without_active_chunks={int(stats.get('indexed_documents_without_active_chunks') or 0)}")
        print(f"[plan] active_memory_items={int(stats.get('active_memory_items') or 0)}")
        return 0

    result = rag_ops_service.rebuild_indices(
        chunk_size=int(args.chunk_size),
        overlap=int(args.overlap),
        skip_reindex=bool(args.skip_reindex),
    )
    print(f"[ok] backup_files={len(result.get('backup_files') or [])}")
    print(f"[ok] migrated_long_term_items={int(result.get('migrated_long_term_items') or 0)}")
    print(f"[ok] deprecated_orphan_doc_chunks={int(result.get('deprecated_orphan_doc_chunks') or 0)}")
    print(f"[ok] docs_reingested={len(result.get('ingested_docs') or [])}")
    print(f"[ok] cleared_non_target_embeddings={int(result.get('cleared_non_target_embeddings') or 0)}")
    print(f"[ok] rebuilt_embeddings={int(result.get('rebuilt_embeddings') or 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
