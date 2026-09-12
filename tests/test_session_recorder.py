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


def test_ensure_session_prints_id(ts_home, ts_cwd):
    env = {
        **dict(**__import__("os").environ),
        "HOME": str(ts_home),
        "USERPROFILE": str(ts_home),
    }
    env.pop("TOKEN_SAVER_SESSION_ID", None)
    r = run_rec(["ensure-session", "--cwd", str(ts_cwd)], env, ts_cwd)
    assert r.returncode == 0
    sid = r.stdout.strip()
    assert sid
    r2 = run_rec(["ensure-session", "--cwd", str(ts_cwd)], env, ts_cwd)
    assert r2.stdout.strip() == sid


def test_record_bad_mechanism(ts_home, ts_cwd):
    env = {
        **dict(**__import__("os").environ),
        "HOME": str(ts_home),
        "USERPROFILE": str(ts_home),
    }
    r = run_rec(
        ["record", "not_a_mech", "--session", "s1", "--payload", "{}"],
        env,
        ts_cwd,
    )
    assert r.returncode == 2


def test_payload_file_equiv(ts_home, ts_cwd, tmp_path):
    env = {
        **dict(**__import__("os").environ),
        "HOME": str(ts_home),
        "USERPROFILE": str(ts_home),
    }
    sid = run_rec(["ensure-session", "--cwd", str(ts_cwd)], env, ts_cwd).stdout.strip()
    payload = {"fused_tools": ["Edit", "Bash"], "note": "x"}
    pf = tmp_path / "p.json"
    pf.write_text(json.dumps(payload), encoding="utf-8")
    r = run_rec(
        ["record", "action_fusion", "--session", sid, "--payload-file", str(pf)],
        env,
        ts_cwd,
    )
    assert r.returncode == 0
