import json
import sys
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _env(home):
    import os

    e = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    e.pop("TOKEN_SAVER_SESSION_ID", None)
    return e


def run_audit(args, env, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "audit.py"), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )


def _seed_events(ts_home, session_id, events):
    import _common as c

    c.ensure_runtime()
    for mechanism, payload in events:
        c.append_event(session_id, mechanism, payload)


def test_audit_estimates(ts_home, ts_cwd):
    sid = "test-session-audit-001"
    _seed_events(
        ts_home,
        sid,
        [
            ("action_fusion", {"fused_tools": ["Edit", "Bash"]}),
            ("action_fusion", {"fused_tools": ["Read", "Grep"]}),
            (
                "observation_pack",
                {
                    "handle": "20260912T170800-a3f9c1d2",
                    "source_path": "/tmp/big.txt",
                    "approx_tokens": 1000,
                    "action": "archive",
                },
            ),
            (
                "observation_pack",
                {
                    "handle": "20260912T170800-a3f9c1d2",
                    "source_path": "/tmp/big.txt",
                    "approx_tokens": 1000,
                    "action": "recall",
                },
            ),
            ("online_compact", {"reason": "context full"}),
            ("online_compact", {"approx_tokens_saved": 100}),
        ],
    )

    r = run_audit(["--session", sid], _env(ts_home), ts_cwd)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "1400" in out  # fusion: 2 * 700
    assert "850" in out  # pack: 1000 * 0.85
    assert "100" in out  # compact estimated
    assert "2350" in out  # total
    assert "unestimated" in out.lower()


def test_audit_json_format(ts_home, ts_cwd):
    sid = "test-session-audit-json"
    _seed_events(
        ts_home,
        sid,
        [
            ("action_fusion", {"fused_tools": ["Edit"]}),
            (
                "observation_pack",
                {
                    "handle": "20260912T170800-b1b2c3d4",
                    "source_path": "/tmp/x.txt",
                    "approx_tokens": 200,
                    "action": "archive",
                },
            ),
            ("online_compact", {"approx_tokens_saved": 50}),
        ],
    )

    r = run_audit(["--session", sid, "--format", "json"], _env(ts_home), ts_cwd)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["session_id"] == sid
    assert data["action_fusion"] == {"count": 1, "tokens_saved": 700}
    assert data["observation_pack"] == {"archive_count": 1, "tokens_saved": 170}
    assert data["online_compact"]["estimated_count"] == 1
    assert data["online_compact"]["unestimated_count"] == 0
    assert data["online_compact"]["tokens_saved"] == 50
    assert data["total_tokens_saved"] == 920
    assert "cost_usd_estimate" in data


def test_audit_missing_session_dir(ts_home, ts_cwd):
    r = run_audit(["--session", "nonexistent-session-id"], _env(ts_home), ts_cwd)
    assert r.returncode == 5
    assert r.stderr.strip()
