"""Shared helpers for token-saver CLI scripts."""

from __future__ import annotations

import json
import math
import os
import re
import secrets
import shutil
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

_SYSTEM_DIR_NAMES = frozenset({"tmp", "var", "usr", "windows", "system32"})
_TEMP_DIR = Path(tempfile.gettempdir()).resolve()

EXIT_OK = 0
EXIT_DECLINE = 1
EXIT_USAGE = 2
EXIT_IO = 3
EXIT_CALL = 4
EXIT_STATE = 5

MECHANISMS = frozenset({"action_fusion", "observation_pack", "online_compact"})
HANDLE_RE = re.compile(r"^\d{8}T\d{6}-[0-9a-f]{8}$")
_WIN_LOCK_MAX_RETRIES = 50
_WIN_LOCK_BASE_DELAY = 0.001


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


def new_handle() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(4)


def _lock_file(f) -> None:
    if os.name == "nt":
        import msvcrt

        # msvcrt locks from the current file position; seek to start and lock 1 byte.
        # Under thread contention LK_LOCK can raise errno 36; retry with backoff.
        f.seek(0)
        for attempt in range(_WIN_LOCK_MAX_RETRIES):
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError as exc:
                if exc.errno != 36 or attempt == _WIN_LOCK_MAX_RETRIES - 1:
                    raise
                time.sleep(_WIN_LOCK_BASE_DELAY * (2 ** min(attempt, 10)))
    else:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_EX)


def _unlock_file(f) -> None:
    if os.name == "nt":
        import msvcrt

        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def append_event(session_id: str, mechanism: str, payload: dict) -> None:
    if mechanism not in MECHANISMS:
        raise ValueError(f"unknown mechanism: {mechanism!r}")
    ensure_runtime()
    path = session_dir(session_id) / "events.jsonl"
    event = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "session_id": session_id,
        "mechanism": mechanism,
        "payload": payload,
    }
    line = json.dumps(event, ensure_ascii=False) + "\n"
    with open(path, "a+", encoding="utf-8") as f:
        _lock_file(f)
        try:
            f.write(line)
            f.flush()
        finally:
            _unlock_file(f)
