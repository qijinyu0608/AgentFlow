import yaml
import os

from agentmesh.common.paths import get_config_path, get_config_template_path

global_config = {}
_config_loaded = False


def _ensure_runtime_config_exists():
    config_path = get_config_path()
    if config_path.exists():
        return config_path

    template_path = get_config_template_path()
    if not template_path.exists():
        return config_path

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(template_path.read_text(encoding='utf-8'), encoding='utf-8')
    except Exception as e:
        print(f"Warning: failed to initialize config.yaml from template: {e}")
    return config_path


def load_config():
    global global_config, _config_loaded
    config_path = _ensure_runtime_config_exists()
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            # Load the YAML content into global_config
            loaded = yaml.safe_load(file) or {}
            global_config = loaded if isinstance(loaded, dict) else {}
            _config_loaded = True
    except Exception as e:
        # Keep process alive and let callers decide fallback behavior.
        global_config = {}
        _config_loaded = False
        print(f"Warning: failed to load config.yaml from {os.fspath(config_path)}: {e}")


def config():
    global _config_loaded
    if not _config_loaded:
        load_config()
    return global_config


def ensure_config_loaded():
    """Load config lazily if it has not been loaded yet."""
    if not _config_loaded:
        load_config()
