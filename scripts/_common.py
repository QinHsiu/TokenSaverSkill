"""Shared helpers for token-saver CLI scripts."""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import uuid
from pathlib import Path

_SYSTEM_DIR_NAMES = frozenset({"tmp", "var", "usr", "windows", "system32"})
_TEMP_DIR = Path(tempfile.gettempdir()).resolve()

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


def is_system_dir(path: Path) -> bool:
    resolved = path.resolve()
    if resolved == _TEMP_DIR:
        return True
    return path.name.casefold() in _SYSTEM_DIR_NAMES


def resolve_session_id(cwd: Path | None = None) -> str:
    env = os.environ.get("TOKEN_SAVER_SESSION_ID")
    if env:
        return env.strip()
    original = (cwd or Path.cwd()).resolve()
    cur = original
    for _ in range(8):
        candidate = cur / ".token-saver-session"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
        parent = cur.parent
        if parent == cur:
            break
        if is_system_dir(parent):
            break
        cur = parent
    sid = str(uuid.uuid4())
    (original / ".token-saver-session").write_text(sid + "\n", encoding="utf-8")
    return sid
