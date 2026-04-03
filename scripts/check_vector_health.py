#!/usr/bin/env python3
"""Check AgentMesh vector retrieval health."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AgentMesh vector retrieval health")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="AgentMesh project root (default: script parent)",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agentmesh.service.rag_ops_service import rag_ops_service

    overview = rag_ops_service.get_overview()
    runtime = overview.get("runtime", {})
    stats = overview.get("stats", {})
    model_distribution = overview.get("model_distribution", [])
    memory_distribution = overview.get("memory_distribution", [])

    print(f"[info] project_root={project_root}")
    print(f"[info] active_embedding_profile={runtime.get('profile') or ''}")
    print(f"[info] configured_embedding_model={runtime.get('model') or ''}")
    print(f"[info] active_memory_items={int(stats.get('active_memory_items') or 0)}")
    print(f"[info] total_memory_embeddings={int(stats.get('total_memory_embeddings') or 0)}")

    if model_distribution:
        print("[info] model_distribution:")
        for row in model_distribution:
            print(
                "  - model={model}, count={count}, dim_range=[{min_dim},{max_dim}]".format(
                    model=row.get("model") or "",
                    count=int(row.get("count") or 0),
                    min_dim=int(row.get("min_dim") or 0),
                    max_dim=int(row.get("max_dim") or 0),
                )
            )
    else:
        print("[warn] no rows in memory_embeddings")

    print("[info] memory_distribution:")
    for row in memory_distribution:
        print(
            "  - scope={scope}, kind={kind}, status={status}, count={count}".format(
                scope=row.get("scope") or "",
                kind=row.get("kind") or "",
                status=row.get("status") or "",
                count=int(row.get("count") or 0),
            )
        )

    covered = int(stats.get("active_model_coverage") or 0)
    total_active = int(stats.get("active_memory_items") or 0)
    residue = int(stats.get("residual_non_current_embeddings_on_active") or 0)
    orphan = int(stats.get("orphan_doc_chunks") or 0)
    rag_mismatch = int(stats.get("indexed_documents_without_active_chunks") or 0)
    print(f"[info] active_model_coverage={covered}/{total_active}")
    print(f"[info] non_current_model_embeddings_on_active={residue}")
    print(f"[info] orphan_doc_chunks={orphan}")
    print(f"[info] indexed_documents_without_active_chunks={rag_mismatch}")

    if total_active > 0 and covered < total_active:
        print("[error] active memory items are not fully covered by the configured embedding model")
        return 2
    if orphan > 0:
        print("[error] orphan doc_chunk items detected")
        return 2
    if rag_mismatch > 0:
        print("[error] indexed documents without active chunks detected")
        return 2
    if residue > 0:
        print("[warn] active memories still contain non-current-model embeddings")

    print("[ok] vector health check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
