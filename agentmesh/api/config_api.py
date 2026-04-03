from __future__ import annotations

import copy
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agentmesh.common.config.config_manager import config, load_config
from agentmesh.common.paths import get_config_path
from agentmesh.skills import SkillManager
from agentmesh.tools.tool_manager import ToolManager


router = APIRouter(prefix="/api/v1", tags=["config"])


class ConfigUpdateRequest(BaseModel):
    # Keep it flexible: we only validate shape lightly here, then merge and write YAML.
    models: Optional[Dict[str, Any]] = Field(default=None, description="models section under config.yaml")
    skills: Optional[Dict[str, Any]] = Field(default=None, description="skills section under config.yaml")
    teams: Optional[Dict[str, Any]] = Field(default=None, description="teams section under config.yaml")


class ConfigValidateRequest(ConfigUpdateRequest):
    include_connectivity: bool = Field(default=True, description="Whether to run provider connectivity probes")


class ConfigApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


def _get_config_path() -> str:
    return os.fspath(get_config_path())


def _redact_api_keys(models_cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Never send secrets to frontend by default.
    out: Dict[str, Any] = copy.deepcopy(models_cfg or {})
    for _, p in out.items():
        if not isinstance(p, dict):
            continue
        if "api_key" in p:
            p["api_key"] = None
    return out


def _redact_embeddings(embeddings_cfg: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = copy.deepcopy(embeddings_cfg or {})
    profiles = out.get("profiles", {})
    if isinstance(profiles, dict):
        for _, profile in profiles.items():
            if isinstance(profile, dict) and "api_key" in profile:
                profile["api_key"] = None
    if "api_key" in out:
        out["api_key"] = None
    return out


def _replace_models(existing_models: Dict[str, Any], update_models: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace the whole `models` block with the providers present in update_models.

    - Providers absent from update_models will be removed from config.yaml.
    - For providers present: if `api_key` is empty, keep the existing api_key.
    """
    out: Dict[str, Any] = {}
    for provider, provider_cfg in (update_models or {}).items():
        if not isinstance(provider_cfg, dict):
            continue

        base = copy.deepcopy((existing_models or {}).get(provider, {})) if isinstance(existing_models, dict) else {}
        if not isinstance(base, dict):
            base = {}

        api_base = provider_cfg.get("api_base")
        if api_base is None:
            # Compatible with camelCase payloads from external callers.
            api_base = provider_cfg.get("baseUrl")
        if api_base is not None:
            base["api_base"] = api_base

        api_key = provider_cfg.get("api_key")
        if api_key is None:
            api_key = provider_cfg.get("apiKey")
        # Frontend sends "" / null to mean "keep existing"
        if api_key is not None and str(api_key).strip() != "":
            base["api_key"] = api_key

        models_list = provider_cfg.get("models")
        if isinstance(models_list, list):
            base["models"] = [str(x) for x in models_list if str(x).strip()]

        out[provider] = base

    return out


def _replace_teams(existing_teams: Dict[str, Any], update_teams: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace the whole `teams` block with the team keys present in update_teams.

    For each team, we update keys in the incoming config, but keep unknown keys from existing config.
    """
    out: Dict[str, Any] = {}
    for team_name, team_cfg in (update_teams or {}).items():
        if not isinstance(team_cfg, dict):
            continue
        base = copy.deepcopy((existing_teams or {}).get(team_name, {})) if isinstance(existing_teams, dict) else {}
        if not isinstance(base, dict):
            base = {}
        base.update(team_cfg)
        out[team_name] = base
    return out


def _replace_skills(existing_skills: Dict[str, Any], update_skills: Dict[str, Any]) -> Dict[str, Any]:
    base = copy.deepcopy(existing_skills or {}) if isinstance(existing_skills, dict) else {}
    update = update_skills if isinstance(update_skills, dict) else {}
    paths = update.get("paths")
    if isinstance(paths, list):
        base["paths"] = [str(x).strip() for x in paths if str(x).strip()]
    elif "paths" in update:
        base["paths"] = []
    for key, value in update.items():
        if key == "paths":
            continue
        base[key] = value
    return base


def _build_candidate_config(existing_cfg: Dict[str, Any], models_update: Dict[str, Any], skills_update: Dict[str, Any], teams_update: Dict[str, Any]) -> Dict[str, Any]:
    cfg_new = copy.deepcopy(existing_cfg or {})
    cfg_new["models"] = _replace_models(cfg_new.get("models", {}), models_update or {})
    cfg_new["skills"] = _replace_skills(cfg_new.get("skills", {}), skills_update or {})
    cfg_new["teams"] = _replace_teams(cfg_new.get("teams", {}), teams_update or {})
    return cfg_new


def _mask_secret(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}{'*' * max(4, len(text) - 8)}{text[-4:]}"


def _collect_known_model_names(models_cfg: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    seen = set()
    for provider_cfg in (models_cfg or {}).values():
        if not isinstance(provider_cfg, dict):
            continue
        for model_name in provider_cfg.get("models", []) or []:
            model_str = str(model_name or "").strip()
            if model_str and model_str not in seen:
                seen.add(model_str)
                names.append(model_str)
    return names


def _build_validation_preview(candidate_cfg: Dict[str, Any]) -> Dict[str, Any]:
    models_cfg = candidate_cfg.get("models", {}) if isinstance(candidate_cfg, dict) else {}
    skills_cfg = candidate_cfg.get("skills", {}) if isinstance(candidate_cfg, dict) else {}
    teams_cfg = candidate_cfg.get("teams", {}) if isinstance(candidate_cfg, dict) else {}

    skill_manager = SkillManager()
    discovered_skills = skill_manager.load_skills(config_dict=candidate_cfg, config_path=_get_config_path())
    discovered_skill_items = list(discovered_skills.values())

    providers = []
    for key, provider_cfg in (models_cfg or {}).items():
        cfg_item = provider_cfg if isinstance(provider_cfg, dict) else {}
        models_list = [str(x).strip() for x in cfg_item.get("models", []) or [] if str(x).strip()]
        providers.append(
            {
                "key": key,
                "api_base": str(cfg_item.get("api_base") or ""),
                "api_key_masked": _mask_secret(cfg_item.get("api_key")),
                "has_api_base": bool(str(cfg_item.get("api_base") or "").strip()),
                "has_api_key": bool(str(cfg_item.get("api_key") or "").strip()),
                "model_count": len(models_list),
                "models": models_list,
                "primary_model": models_list[0] if models_list else "",
            }
        )

    teams = []
    for team_key, team_cfg in (teams_cfg or {}).items():
        team_item = team_cfg if isinstance(team_cfg, dict) else {}
        agents = []
        for agent_cfg in team_item.get("agents", []) or []:
            agent_item = agent_cfg if isinstance(agent_cfg, dict) else {}
            tools = [str(x).strip() for x in agent_item.get("tools", []) or [] if str(x).strip()]
            skills = [str(x).strip() for x in agent_item.get("skills", []) or [] if str(x).strip()]
            agents.append(
                {
                    "name": str(agent_item.get("name") or "").strip(),
                    "model": str(agent_item.get("model") or "").strip(),
                    "tool_count": len(tools),
                    "tools": tools,
                    "skill_count": len(skills),
                    "skills": skills,
                    "max_steps": agent_item.get("max_steps"),
                }
            )
        teams.append(
            {
                "key": team_key,
                "model": str(team_item.get("model") or "").strip(),
                "description": str(team_item.get("description") or "").strip(),
                "rule": str(team_item.get("rule") or "").strip(),
                "max_steps": team_item.get("max_steps"),
                "agent_count": len(agents),
                "agents": agents,
            }
        )

    yaml_preview_cfg = copy.deepcopy(candidate_cfg)
    yaml_preview_cfg["models"] = _redact_api_keys(yaml_preview_cfg.get("models", {}))
    yaml_preview_cfg["embeddings"] = _redact_embeddings(yaml_preview_cfg.get("embeddings", {}))
    yaml_preview = yaml.safe_dump(yaml_preview_cfg, allow_unicode=True, sort_keys=False)

    return {
        "providers": providers,
        "skills": {
            "paths": [str(x).strip() for x in (skills_cfg.get("paths", []) if isinstance(skills_cfg, dict) else []) if str(x).strip()],
            "discovered_count": len(discovered_skill_items),
            "discovered": discovered_skill_items,
        },
        "teams": teams,
        "yaml_preview": yaml_preview,
        "known_models": _collect_known_model_names(models_cfg),
    }


def _validate_candidate_config(candidate_cfg: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    models_cfg = candidate_cfg.get("models", {}) if isinstance(candidate_cfg, dict) else {}
    skills_cfg = candidate_cfg.get("skills", {}) if isinstance(candidate_cfg, dict) else {}
    teams_cfg = candidate_cfg.get("teams", {}) if isinstance(candidate_cfg, dict) else {}
    preview = _build_validation_preview(candidate_cfg)
    known_models = set(preview.get("known_models") or [])

    if not isinstance(models_cfg, dict) or not models_cfg:
        errors.append("models：至少需要一个 provider。")
    if not isinstance(teams_cfg, dict) or not teams_cfg:
        errors.append("teams：至少需要一个 team。")

    manager = ToolManager()
    manager.load_tools()
    known_tools = set((manager.list_tools() or {}).keys())
    skill_manager = SkillManager()
    skill_manager.load_skills(config_dict=candidate_cfg, config_path=_get_config_path())
    known_skills = set((skill_manager.list_skills() or {}).keys())

    if skills_cfg and not isinstance(skills_cfg, dict):
        errors.append("skills：必须是对象结构。")

    for missing_path in skill_manager.missing_paths:
        warnings.append(f"skill 路径不存在：`{missing_path}`。")
    for load_error in skill_manager.load_errors:
        warnings.append(load_error)
    for duplicate_name in skill_manager.duplicate_names:
        warnings.append(f"skill `{duplicate_name}` 存在重复定义，已忽略后续重复项。")
    for skill_name, skill_info in (skill_manager.list_skills() or {}).items():
        for tool_name in skill_info.get("tools", []) or []:
            tool_str = str(tool_name or "").strip()
            if tool_str and tool_str not in known_tools:
                warnings.append(f"skill `{skill_name}` 引用了未知工具 `{tool_str}`。")

    for provider_key, provider_cfg in (models_cfg or {}).items():
        if not str(provider_key or "").strip():
            errors.append("models：provider key 不能为空。")
            continue
        cfg_item = provider_cfg if isinstance(provider_cfg, dict) else {}
        models_list = [str(x).strip() for x in cfg_item.get("models", []) or [] if str(x).strip()]
        if not str(cfg_item.get("api_base") or "").strip():
            warnings.append(f"provider `{provider_key}` 未填写 api_base。")
        if not str(cfg_item.get("api_key") or "").strip():
            warnings.append(f"provider `{provider_key}` 未填写 api_key，保存时会保留旧值；若这是新 provider，请补全密钥。")
        if not models_list:
            warnings.append(f"provider `{provider_key}` 未配置可选 models。")

    for team_key, team_cfg in (teams_cfg or {}).items():
        if not str(team_key or "").strip():
            errors.append("teams：team key 不能为空。")
            continue
        team_item = team_cfg if isinstance(team_cfg, dict) else {}
        team_model = str(team_item.get("model") or "").strip()
        if team_model and team_model not in known_models:
            errors.append(f"team `{team_key}` 使用了未知模型 `{team_model}`。")

        agents = team_item.get("agents", []) or []
        if not agents:
            warnings.append(f"team `{team_key}` 当前没有 agents。")

        seen_agent_names = set()
        for idx, agent_cfg in enumerate(agents):
            agent_item = agent_cfg if isinstance(agent_cfg, dict) else {}
            agent_name = str(agent_item.get("name") or "").strip()
            if not agent_name:
                errors.append(f"team `{team_key}` 的第 {idx + 1} 个 agent 缺少 name。")
            elif agent_name in seen_agent_names:
                warnings.append(f"team `{team_key}` 中存在重复 agent 名称 `{agent_name}`。")
            else:
                seen_agent_names.add(agent_name)

            if not str(agent_item.get("system_prompt") or "").strip():
                errors.append(f"team `{team_key}` / agent `{agent_name or idx + 1}` 缺少 system_prompt。")

            agent_model = str(agent_item.get("model") or "").strip()
            if agent_model and agent_model not in known_models:
                errors.append(f"team `{team_key}` / agent `{agent_name or idx + 1}` 使用了未知模型 `{agent_model}`。")
            if not agent_model and not team_model:
                warnings.append(f"team `{team_key}` / agent `{agent_name or idx + 1}` 没有可继承的模型配置。")

            for tool_name in agent_item.get("tools", []) or []:
                tool_str = str(tool_name or "").strip()
                if tool_str and tool_str not in known_tools:
                    warnings.append(f"team `{team_key}` / agent `{agent_name or idx + 1}` 引用了未知工具 `{tool_str}`。")

            for skill_name in agent_item.get("skills", []) or []:
                skill_str = str(skill_name or "").strip()
                if skill_str and skill_str not in known_skills:
                    errors.append(f"team `{team_key}` / agent `{agent_name or idx + 1}` 引用了未知 skill `{skill_str}`。")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "preview": preview,
    }


def _probe_openai_compatible(api_base: str, api_key: str, model_name: str) -> Dict[str, Any]:
    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0,
        "max_tokens": 1,
    }
    with requests.Session() as session:
        session.trust_env = False
        resp = session.post(url, headers=headers, json=payload, timeout=12)
    return {
        "status_code": resp.status_code,
        "body": resp.text[:500],
    }


def _probe_claude(api_base: str, api_key: str, model_name: str) -> Dict[str, Any]:
    url = f"{api_base.rstrip('/')}/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }
    with requests.Session() as session:
        session.trust_env = False
        resp = session.post(url, headers=headers, json=payload, timeout=12)
    return {
        "status_code": resp.status_code,
        "body": resp.text[:500],
    }


def _probe_provider(provider_name: str, provider_cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg_item = provider_cfg if isinstance(provider_cfg, dict) else {}
    api_base = str(cfg_item.get("api_base") or "").strip()
    api_key = str(cfg_item.get("api_key") or "").strip()
    models_list = [str(x).strip() for x in cfg_item.get("models", []) or [] if str(x).strip()]
    probe = {
        "provider": provider_name,
        "model": models_list[0] if models_list else "",
        "ok": False,
        "skipped": False,
        "message": "",
        "status_code": None,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }

    if not api_base or not api_key or not models_list:
        probe["skipped"] = True
        missing = []
        if not api_base:
            missing.append("api_base")
        if not api_key:
            missing.append("api_key")
        if not models_list:
            missing.append("models")
        probe["message"] = f"跳过连通性测试，缺少：{', '.join(missing)}"
        return probe

    try:
        if provider_name == "claude" and "anthropic" in api_base:
            result = _probe_claude(api_base, api_key, models_list[0])
        else:
            result = _probe_openai_compatible(api_base, api_key, models_list[0])
        probe["status_code"] = result["status_code"]
        probe["ok"] = result["status_code"] == 200
        probe["message"] = "连通成功" if probe["ok"] else result["body"] or f"HTTP {result['status_code']}"
        return probe
    except Exception as exc:
        probe["message"] = f"请求失败：{exc}"
        return probe


@router.get("/config", response_model=ConfigApiResponse)
async def get_config() -> ConfigApiResponse:
    try:
        cfg = config() or {}
        if not cfg:
            load_config()
            cfg = config() or {}
        models_cfg = cfg.get("models", {}) if isinstance(cfg, dict) else {}
        skills_cfg = cfg.get("skills", {}) if isinstance(cfg, dict) else {}
        teams_cfg = cfg.get("teams", {}) if isinstance(cfg, dict) else {}
        skill_manager = SkillManager()
        discovered_skills = list(skill_manager.load_skills().values())

        data = {
            "models": _redact_api_keys(models_cfg),
            "embeddings": _redact_embeddings(cfg.get("embeddings", {}) if isinstance(cfg, dict) else {}),
            "skills": skills_cfg,
            "discovered_skills": discovered_skills,
            "teams": teams_cfg,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        return ConfigApiResponse(code=200, message="success", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {e}")


@router.get("/tools", response_model=ConfigApiResponse)
async def list_tools() -> ConfigApiResponse:
    """
    Return currently available tools discovered by ToolManager.

    data shape:
    {
      "tools": [
        {
          "name": str,
          "description": str,
          "parameters": dict,
          "configured": bool,
          "config": dict
        }
      ]
    }
    """
    try:
        cfg = config() or {}
        if not cfg:
            load_config()
            cfg = config() or {}

        tools_cfg = cfg.get("tools", {}) if isinstance(cfg, dict) else {}
        if not isinstance(tools_cfg, dict):
            tools_cfg = {}

        manager = ToolManager()
        manager.load_tools()
        tools_raw = manager.list_tools() or {}

        items = []
        for name in sorted(tools_raw.keys()):
            info = tools_raw.get(name) or {}
            items.append(
                {
                    "name": name,
                    "description": info.get("description", ""),
                    "parameters": info.get("parameters", {}),
                    "configured": name in tools_cfg,
                    "config": tools_cfg.get(name, {}) if isinstance(tools_cfg.get(name, {}), dict) else {},
                }
            )

        return ConfigApiResponse(code=200, message="success", data={"tools": items, "updated_at": datetime.now().isoformat(timespec="seconds")})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load tools: {e}")


@router.post("/config/validate", response_model=ConfigApiResponse)
async def validate_config(req: ConfigValidateRequest) -> ConfigApiResponse:
    try:
        cfg = config() or {}
        if not cfg:
            load_config()
            cfg = config() or {}
        if not isinstance(cfg, dict):
            raise RuntimeError("config.yaml root should be a mapping")

        candidate_cfg = _build_candidate_config(
            existing_cfg=cfg,
            models_update=req.models if req.models is not None else {},
            skills_update=req.skills if req.skills is not None else {},
            teams_update=req.teams if req.teams is not None else {},
        )
        validation = _validate_candidate_config(candidate_cfg)

        provider_checks = []
        if req.include_connectivity:
            for provider_name, provider_cfg in (candidate_cfg.get("models", {}) or {}).items():
                provider_checks.append(_probe_provider(str(provider_name), provider_cfg if isinstance(provider_cfg, dict) else {}))

        data = {
            **validation,
            "provider_checks": provider_checks,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        return ConfigApiResponse(code=200, message="success", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate config: {e}")


@router.put("/config", response_model=ConfigApiResponse)
async def update_config(req: ConfigUpdateRequest) -> ConfigApiResponse:
    try:
        cfg = config() or {}
        if not cfg:
            load_config()
            cfg = config() or {}
        if not isinstance(cfg, dict):
            raise RuntimeError("config.yaml root should be a mapping")

        models_update = req.models if req.models is not None else {}
        skills_update = req.skills if req.skills is not None else {}
        teams_update = req.teams if req.teams is not None else {}

        cfg_new = _build_candidate_config(cfg, models_update, skills_update, teams_update)

        config_path = _get_config_path()
        with open(config_path, "w", encoding="utf-8") as f:
            # Keep YAML readable for users to re-open.
            yaml.safe_dump(cfg_new, f, allow_unicode=True, sort_keys=False)

        # Reload global_config in-process.
        load_config()

        # Clear team cache so new/updated team definitions take effect immediately.
        try:
            from agentmesh.service.websocket_service import agent_executor  # imported lazily

            if agent_executor is not None:
                agent_executor.teams_cache = {}
                agent_executor.refresh_runtime_metadata()
        except Exception:
            # Best-effort cache clearing. Not critical for saving.
            pass

        return ConfigApiResponse(code=200, message="success", data={"updated_at": datetime.now().isoformat(timespec="seconds")})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {e}")
