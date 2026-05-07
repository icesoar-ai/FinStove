from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
_CACHE: dict[str, dict[str, Any]] = {}


def _load(name: str) -> dict[str, Any]:
    path = _CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return _interpolate_env(raw)


def _interpolate_env(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _interpolate_env(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_interpolate_env(v) for v in data]
    if isinstance(data, str) and data.startswith("${") and data.endswith("}"):
        return os.environ.get(data[2:-1], "")
    return data


def get_settings() -> dict[str, Any]:
    if "settings" not in _CACHE:
        _CACHE["settings"] = _load("settings")
    return _CACHE["settings"]


def get_providers() -> dict[str, Any]:
    if "providers" not in _CACHE:
        _CACHE["providers"] = _load("providers")
    return _CACHE["providers"]


def get_scoring() -> dict[str, Any]:
    if "scoring" not in _CACHE:
        _CACHE["scoring"] = _load("scoring")
    return _CACHE["scoring"]
