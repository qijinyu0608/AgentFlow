from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from agentmesh.common import config
from agentmesh.common.paths import get_config_path
from agentmesh.common.utils.log import logger


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    prompt: str
    tools: List[str]
    source_path: str


class SkillManager:
    """Discover and resolve skill definitions from configured directories."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SkillManager, cls).__new__(cls)
            cls._instance.skill_specs = {}
            cls._instance.search_paths = []
            cls._instance.missing_paths = []
            cls._instance.load_errors = []
            cls._instance.duplicate_names = []
        return cls._instance

    def reset(self):
        self.skill_specs: Dict[str, SkillSpec] = {}
        self.search_paths: List[str] = []
        self.missing_paths: List[str] = []
        self.load_errors: List[str] = []
        self.duplicate_names: List[str] = []

    def _get_default_config_path(self) -> Path:
        return get_config_path()

    def _get_builtin_skills_root(self) -> Path:
        return Path(__file__).resolve().parent

    @staticmethod
    def _normalize_string_list(values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        seen = set()
        result: List[str] = []
        for item in values:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _resolve_search_paths(self, config_dict: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None) -> List[Path]:
        cfg = config_dict if isinstance(config_dict, dict) else (config() or {})
        skills_cfg = cfg.get("skills", {}) if isinstance(cfg, dict) else {}
        configured_paths = self._normalize_string_list((skills_cfg or {}).get("paths", []))

        base_config_path = Path(config_path).resolve() if config_path else self._get_default_config_path()
        base_dir = base_config_path.parent
        candidates: List[Path] = [self._get_builtin_skills_root()]

        for raw_path in configured_paths:
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = base_dir / candidate
            candidates.append(candidate.resolve())

        deduped: List[Path] = []
        seen = set()
        for path in candidates:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(path)
        return deduped

    def _load_skill_file(self, skill_file: Path):
        try:
            with open(skill_file, "r", encoding="utf-8") as handle:
                raw = yaml.safe_load(handle) or {}
        except Exception as exc:
            self.load_errors.append(f"读取 skill 文件失败 `{skill_file}`: {exc}")
            return

        if not isinstance(raw, dict):
            self.load_errors.append(f"skill 文件 `{skill_file}` 必须是对象结构。")
            return

        name = str(raw.get("name") or "").strip()
        description = str(raw.get("description") or "").strip()
        prompt = str(raw.get("prompt") or "").strip()
        if not name or not description or not prompt:
            self.load_errors.append(
                f"skill 文件 `{skill_file}` 缺少必填字段，至少需要 name、description、prompt。"
            )
            return

        if name in self.skill_specs:
            self.duplicate_names.append(name)
            logger.warning("Duplicate skill name '%s' detected at %s, skipping.", name, skill_file)
            return

        tools = self._normalize_string_list(raw.get("tools", []))
        self.skill_specs[name] = SkillSpec(
            name=name,
            description=description,
            prompt=prompt,
            tools=tools,
            source_path=str(skill_file),
        )

    def load_skills(self, config_dict: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        self.reset()
        roots = self._resolve_search_paths(config_dict=config_dict, config_path=config_path)
        self.search_paths = [str(path) for path in roots]

        for root in roots:
            if not root.exists():
                self.missing_paths.append(str(root))
                continue
            if not root.is_dir():
                self.load_errors.append(f"skill 路径 `{root}` 不是目录。")
                continue

            for skill_file in sorted(root.rglob("skill.yaml")):
                self._load_skill_file(skill_file)

        return self.list_skills()

    def list_skills(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "name": spec.name,
                "description": spec.description,
                "prompt": spec.prompt,
                "tools": list(spec.tools),
                "source_path": spec.source_path,
            }
            for name, spec in sorted(self.skill_specs.items(), key=lambda item: item[0])
        }

    def get_skill(self, name: str) -> Optional[SkillSpec]:
        return self.skill_specs.get(str(name or "").strip())

    def resolve_skills(self, names: Optional[List[Any]]) -> Tuple[List[SkillSpec], List[str]]:
        if not isinstance(names, list):
            return [], []

        resolved: List[SkillSpec] = []
        missing: List[str] = []
        seen = set()
        for item in names:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            spec = self.get_skill(name)
            if spec is None:
                missing.append(name)
                continue
            resolved.append(spec)
        return resolved, missing
