import os
import tempfile
import uuid
from pathlib import Path

import _common as common


def test_ensure_creates_and_reuses(ts_home, ts_cwd):
    a = common.resolve_session_id(ts_cwd)
    b = common.resolve_session_id(ts_cwd)
    assert a == b
    assert (ts_cwd / ".token-saver-session").read_text(encoding="utf-8").strip() == a
    uuid.UUID(a)


def test_env_override_no_writeback(ts_home, ts_cwd, monkeypatch):
    monkeypatch.setenv("TOKEN_SAVER_SESSION_ID", "env-session-fixed")
    sid = common.resolve_session_id(ts_cwd)
    assert sid == "env-session-fixed"
    assert not (ts_cwd / ".token-saver-session").exists()


def test_upward_finds_parent_file(ts_home, tmp_path, monkeypatch):
    root = tmp_path / "repo"
    child = root / "a" / "b"
    child.mkdir(parents=True)
    (root / ".token-saver-session").write_text("parent-sid", encoding="utf-8")
    monkeypatch.chdir(child)
    assert common.resolve_session_id(child) == "parent-sid"


def test_stop_after_8_levels_creates_at_original(ts_home, tmp_path, monkeypatch):
    # Build 10 nested dirs without a session file; resolve from deepest
    p = tmp_path / "deep"
    p.mkdir()
    cur = p
    for i in range(10):
        cur = cur / f"d{i}"
        cur.mkdir()
    monkeypatch.chdir(cur)
    sid = common.resolve_session_id(cur)
    assert (cur / ".token-saver-session").read_text(encoding="utf-8").strip() == sid


def test_git_does_not_stop(ts_home, tmp_path, monkeypatch):
    root = tmp_path / "mono"
    sub = root / "pkg" / "src"
    sub.mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".token-saver-session").write_text("mono-sid", encoding="utf-8")
    monkeypatch.chdir(sub)
    assert common.resolve_session_id(sub) == "mono-sid"


def test_system_dir_stops_upward_search(ts_home, tmp_path, monkeypatch):
    temp_root = Path(tempfile.gettempdir()).resolve()
    # Place project under a path whose parent chain hits a system dir name
    root = tmp_path / "under" / "tmp" / "proj"
    root.mkdir(parents=True)
    deep = root / "src"
    deep.mkdir()
    monkeypatch.chdir(deep)
    sid = common.resolve_session_id(deep)
    assert (deep / ".token-saver-session").read_text(encoding="utf-8").strip() == sid


def test_is_system_dir_by_name():
    assert common.is_system_dir(Path("/some/path/tmp"))
    assert common.is_system_dir(Path("/some/path/VAR"))
    assert not common.is_system_dir(Path("/some/path/project"))


def test_is_system_dir_tempdir():
    temp = Path(tempfile.gettempdir()).resolve()
    assert common.is_system_dir(temp)
