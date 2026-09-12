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


def test_archive_success(ts_home, ts_cwd):
    # file large enough: >= 2000 tokens under heuristic (~1540 words)
    words = " ".join(["word"] * 1600)
    f = ts_cwd / "big.txt"
    f.write_text(words + "\nline2\nline3\nline4\n", encoding="utf-8")
    r = run_op(["archive", str(f)], _env(ts_home), ts_cwd)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert set(data) >= {"handle", "approx_tokens", "archived_path", "summary"}
    assert Path(data["archived_path"]).is_file()


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
