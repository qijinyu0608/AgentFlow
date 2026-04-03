from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_bundle_root() -> Path:
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parents[2]


def get_runtime_root() -> Path:
    custom_root = os.environ.get("AGENTMESH_HOME", "").strip()
    if custom_root:
        return Path(custom_root).expanduser().resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_config_path() -> Path:
    return get_runtime_root() / "config.yaml"


def get_config_template_path() -> Path:
    runtime_candidate = get_runtime_root() / "config-template.yaml"
    if runtime_candidate.exists():
        return runtime_candidate
    return get_bundle_root() / "config-template.yaml"


def get_frontend_dist_path() -> Path:
    runtime_candidate = get_runtime_root() / "frontend" / "dist"
    if runtime_candidate.exists():
        return runtime_candidate
    return get_bundle_root() / "frontend" / "dist"
