import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def run_rec(args, env, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "session_recorder.py"), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )


def _make_env(ts_home):
    env = {
        **dict(**__import__("os").environ),
        "HOME": str(ts_home),
        "USERPROFILE": str(ts_home),
    }
    env.pop("TOKEN_SAVER_SESSION_ID", None)
    return env


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


def test_ensure_session_prints_id(ts_home, ts_cwd):
    env = _make_env(ts_home)
    r = run_rec(["ensure-session", "--cwd", str(ts_cwd)], env, ts_cwd)
    assert r.returncode == 0
    sid = r.stdout.strip()
    assert sid
    r2 = run_rec(["ensure-session", "--cwd", str(ts_cwd)], env, ts_cwd)
    assert r2.stdout.strip() == sid


def test_record_bad_mechanism(ts_home, ts_cwd):
    env = _make_env(ts_home)
    r = run_rec(
        ["record", "not_a_mech", "--session", "s1", "--payload", "{}"],
        env,
        ts_cwd,
    )
    assert r.returncode == 2


def test_payload_string_and_file_equivalent(ts_home, ts_cwd, tmp_path):
    env = _make_env(ts_home)
    sid = run_rec(["ensure-session", "--cwd", str(ts_cwd)], env, ts_cwd).stdout.strip()
    payload = {"fused_tools": ["Edit", "Bash"], "note": "x"}
    pf = tmp_path / "p.json"
    pf.write_text(json.dumps(payload), encoding="utf-8")

    r_str = run_rec(
        [
            "record",
            "action_fusion",
            "--session",
            sid,
            "--payload",
            json.dumps(payload),
        ],
        env,
        ts_cwd,
    )
    assert r_str.returncode == 0

    r_file = run_rec(
        ["record", "action_fusion", "--session", sid, "--payload-file", str(pf)],
        env,
        ts_cwd,
    )
    assert r_file.returncode == 0

    ev_str = _read_event(ts_home, sid, index=0)
    ev_file = _read_event(ts_home, sid, index=1)
    assert ev_str["mechanism"] == ev_file["mechanism"] == "action_fusion"
    assert ev_str["payload"] == ev_file["payload"] == payload


def test_record_bad_json(ts_home, ts_cwd):
    env = _make_env(ts_home)
    sid = run_rec(["ensure-session", "--cwd", str(ts_cwd)], env, ts_cwd).stdout.strip()
    r = run_rec(
        ["record", "action_fusion", "--session", sid, "--payload", "{not json}"],
        env,
        ts_cwd,
    )
    assert r.returncode == 2
