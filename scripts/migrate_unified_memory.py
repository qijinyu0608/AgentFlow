#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


def _backup_file(src: Path, backup_dir: Path) -> Optional[Path]:
    if not src.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = backup_dir / f"{src.name}.{stamp}.bak"
    shutil.copy2(src, dst)
    return dst


def run(workspace_root: Path, project_root: Path, dry_run: bool = False) -> int:
    agentmesh_db = project_root / "data" / "sqlite" / "agentmesh.db"
    index_db = workspace_root / "memory" / "long-term" / "index.db"
    memory_md = workspace_root / "memory" / "MEMORY.md"

    backup_dir = project_root / "data" / "backups" / "unified-memory"
    print(f"[info] project_root={project_root}")
    print(f"[info] workspace_root={workspace_root}")
    print(f"[info] dry_run={dry_run}")

    if not dry_run:
        db_backup = _backup_file(agentmesh_db, backup_dir)
        idx_backup = _backup_file(index_db, backup_dir)
        print(f"[backup] agentmesh.db => {db_backup}" if db_backup else "[backup] data/sqlite/agentmesh.db not found")
        print(f"[backup] index.db => {idx_backup}" if idx_backup else "[backup] index.db not found")

    if not memory_md.exists():
        print(f"[skip] MEMORY.md not found at {memory_md}")
        return 0

    raw = memory_md.read_text(encoding="utf-8").strip()
    if not raw:
        print("[skip] MEMORY.md is empty")
        return 0

    if dry_run:
        print(f"[dry-run] would import MEMORY.md ({len(raw)} chars) into data/sqlite/agentmesh.db as long_term_profile")
        return 0

    # Lazy import to keep script usable without full runtime during dry-run
    from agentmesh.service.unified_memory_service import unified_memory_service

    snapshot = unified_memory_service.put_long_term_memory(
        meta={
            "migration_source": str(memory_md),
            "migration_note": "Imported from MEMORY.md during unified-memory migration",
        },
        content=raw,
    )
    print(f"[ok] imported long-term memory to data/sqlite/agentmesh.db item_id={snapshot.item_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate MEMORY.md into unified data/sqlite/agentmesh.db memory chain")
    parser.add_argument(
        "--workspace-root",
        default=str(Path.home() / "agentmesh"),
        help="Workspace root that contains memory/MEMORY.md and memory/long-term/index.db",
    )
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Project root that contains data/sqlite/agentmesh.db",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing data")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).expanduser().resolve()
    project_root = Path(args.project_root).expanduser().resolve()
    return run(workspace_root=workspace_root, project_root=project_root, dry_run=bool(args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
