import json
import threading
from pathlib import Path

import _common as common


def test_append_event_roundtrip(ts_home, ts_cwd):
    common.ensure_runtime()
    sid = common.resolve_session_id(ts_cwd)
    common.append_event(sid, "action_fusion", {"fused_tools": ["Edit", "Bash"]})
    lines = (common.session_dir(sid) / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["session_id"] == sid
    assert obj["mechanism"] == "action_fusion"
    assert obj["payload"] == {"fused_tools": ["Edit", "Bash"]}
    assert "timestamp" in obj


def test_concurrent_appends_no_partial_lines(ts_home, ts_cwd):
    common.ensure_runtime()
    sid = common.resolve_session_id(ts_cwd)
    errors: list[BaseException] = []

    def worker(i):
        try:
            common.append_event(sid, "action_fusion", {"fused_tools": ["Edit"], "note": str(i) * 200})
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"worker exceptions: {errors!r}"
    path = common.session_dir(sid) / "events.jsonl"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 20
    for line in lines:
        json.loads(line)


def test_handle_format():
    h = common.new_handle()
    assert common.HANDLE_RE.fullmatch(h)
