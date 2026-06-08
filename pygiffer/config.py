import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".pygiffer"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "material_folders": [],
}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()
    merged = DEFAULT_CONFIG.copy()
    merged.update(data)
    if not isinstance(merged.get("material_folders"), list):
        merged["material_folders"] = []
    return merged


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
