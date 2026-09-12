import json
import sys
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def run_op(args, env, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "observation_pack.py"), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )


def _env(home):
    import os

    e = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    e.pop("TOKEN_SAVER_SESSION_ID", None)
    return e


def _events_path(ts_home, session_id):
    return (
        ts_home
        / ".agent"
        / "token-saver"
        / "archive"
        / session_id
        / "events.jsonl"
    )


def _read_event(ts_home, session_id, index=0):
    lines = _events_path(ts_home, session_id).read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[index])


def test_archive_success(ts_home, ts_cwd):
    import _common as c

    # file large enough: >= 2000 tokens under heuristic (~1540 words)
    words = " ".join(["word"] * 1600)
    f = ts_cwd / "big.txt"
    f.write_text(words + "\nline2\nline3\nline4\n", encoding="utf-8")
    r = run_op(["archive", str(f)], _env(ts_home), ts_cwd)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert set(data) >= {"handle", "approx_tokens", "archived_path", "summary"}
    assert Path(data["archived_path"]).is_file()
    assert c.HANDLE_RE.fullmatch(data["handle"])
    assert "(共" in data["summary"] and "行)" in data["summary"]

    sid = (ts_cwd / ".token-saver-session").read_text(encoding="utf-8").strip()
    ev = _read_event(ts_home, sid)
    assert ev["mechanism"] == "observation_pack"
    payload = ev["payload"]
    assert payload["action"] == "archive"
    assert payload["handle"] == data["handle"]
    assert payload["approx_tokens"] == data["approx_tokens"]
    assert payload["source_path"] == str(f.resolve())


def test_archive_below_threshold(ts_home, ts_cwd):
    f = ts_cwd / "small.txt"
    f.write_text("hello\n", encoding="utf-8")
    r = run_op(["archive", str(f)], _env(ts_home), ts_cwd)
    assert r.returncode == 1


def test_archive_missing_file(ts_home, ts_cwd):
    r = run_op(["archive", str(ts_cwd / "nope.txt")], _env(ts_home), ts_cwd)
    assert r.returncode == 4


def test_archive_disabled(ts_home, ts_cwd):
    import _common as c

    c.ensure_runtime()
    cfg_path = c.runtime_root() / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["observationPack"]["enabled"] = False
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    words = " ".join(["word"] * 1600)
    f = ts_cwd / "big2.txt"
    f.write_text(words, encoding="utf-8")
    r = run_op(["archive", str(f)], _env(ts_home), ts_cwd)
    assert r.returncode == 1


def _archive_large(ts_home, ts_cwd, name="big.txt"):
    words = " ".join(["word"] * 1600)
    f = ts_cwd / name
    f.write_text(words + "\nline2\nline3\nline4\n", encoding="utf-8")
    r = run_op(["archive", str(f)], _env(ts_home), ts_cwd)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["handle"]


def test_recall_respects_max_tokens(ts_home, ts_cwd):
    import _common as c

    handle = _archive_large(ts_home, ts_cwd)
    r = run_op(["recall", handle, "--max-tokens", "50"], _env(ts_home), ts_cwd)
    assert r.returncode == 0, r.stderr
    assert c.approx_tokens(r.stdout) <= 50 + 2


def test_recall_unknown_handle(ts_home, ts_cwd):
    import _common as c

    c.ensure_runtime()
    sid = c.resolve_session_id(ts_cwd)
    c.session_dir(sid)
    r = run_op(["recall", "20990101T000000-deadbeef"], _env(ts_home), ts_cwd)
    assert r.returncode == 5


def test_list_empty_and_ordered(ts_home, ts_cwd):
    r = run_op(["list"], _env(ts_home), ts_cwd)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == []

    h1 = _archive_large(ts_home, ts_cwd, "a.txt")
    h2 = _archive_large(ts_home, ts_cwd, "b.txt")
    r = run_op(["list"], _env(ts_home), ts_cwd)
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    assert len(rows) == 2
    assert rows == sorted(rows, key=lambda x: x["handle"])
    handles = [row["handle"] for row in rows]
    assert set(handles) == {h1, h2}
    for row in rows:
        assert set(row) == {"handle", "approx_tokens", "source_path"}
        assert row["approx_tokens"] > 0
        assert row["source_path"].endswith(".txt")
