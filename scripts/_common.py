"""Shared helpers for token-saver CLI scripts."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

EXIT_OK = 0
EXIT_DECLINE = 1
EXIT_USAGE = 2
EXIT_IO = 3
EXIT_CALL = 4
EXIT_STATE = 5


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def runtime_root() -> Path:
    return Path.home() / ".agent" / "token-saver"


def ensure_runtime() -> Path:
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "archive").mkdir(parents=True, exist_ok=True)
    cfg = root / "config.json"
    if not cfg.is_file():
        default = skill_root() / "config.default.json"
        shutil.copy2(default, cfg)
    return root


def approx_tokens(text: str) -> int:
    return math.ceil(len(text.split()) * 1.3)


def load_config() -> dict:
    cfg_path = ensure_runtime() / "config.json"
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def session_dir(session_id: str) -> Path:
    path = runtime_root() / "archive" / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path
