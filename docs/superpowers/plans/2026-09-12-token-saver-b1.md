# Token Saver Skill B1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a cross-Harness installable Token Saver Skill (B1) with flat CLI scripts for ObservationPack archive/recall/list, session event recording, and post-session audit — no harness patches, no reducer model.

**Architecture:** Skill root holds `SKILL.md` + `config.default.json`. Shared helpers live in `scripts/_common.py` (imported by inserting `scripts/` on `sys.path`). Three CLIs (`session_recorder.py`, `observation_pack.py`, `audit.py`) write under `Path.home()/.agent/token-saver/`. Tests isolate via temp HOME/USERPROFILE + tmp CWD. Docs split: SKILL = when/how; `references/mechanisms.md` = why only.

**Tech Stack:** Python 3.10+ stdlib only (`argparse`, `json`, `pathlib`, `uuid`, `fcntl`/`msvcrt`); pytest for tests; bash `install.sh` for skill copy.

**Spec:** `docs/superpowers/specs/2026-09-12-token-saver-b1-design.md`

## Global Constraints

- B1 only: no harness interception, no Evidence-Preserving Reducer calls, no hot-reload, no live token meters.
- Runtime root: `Path.home() / ".agent" / "token-saver"`; never require `install.sh` before scripts run.
- Exit codes locked: 0 success, 1 business decline, 2 illegal args, 3 I/O/lock, 4 call error, 5 state error.
- Handle format: `YYYYMMDDTHHMMSS-<8hex>`; events JSONL schema per spec; flock on every append.
- `online_compact` without `approx_tokens_saved` must not inflate audit totals.
- `mechanisms.md` must not contain CLI usage; `SKILL.md` owns CLI/timing/exit codes.
- Stdlib only for runtime scripts; pytest may be the sole test dependency.
- Every claimed saving must map to an `events.jsonl` line.

---

## File structure (locked)

| File | Responsibility |
|------|----------------|
| `config.default.json` | Factory defaults copied to runtime on first use |
| `scripts/_common.py` | Paths, bootstrap, session resolve, tokens, handles, locked JSONL append, exit helpers, load config |
| `scripts/session_recorder.py` | `ensure-session`, `record` CLIs |
| `scripts/observation_pack.py` | `archive`, `recall`, `list` CLIs |
| `scripts/audit.py` | `--session` + `--format text\|json` |
| `scripts/install.sh` | Copy skill tree into detected Agent skill dirs only |
| `SKILL.md` | Behavior: when to call which script + exit handling |
| `references/mechanisms.md` | Principles + SoL-Pi + why saves tokens (no CLI) |
| `README.md` | Install / use / config overview |
| `tests/conftest.py` | Temp HOME + cwd fixtures |
| `tests/test_common_session.py` | T2–T4 session resolution |
| `tests/test_session_recorder.py` | T9–T11 record |
| `tests/test_observation_pack.py` | T1, T5–T8, T15–T16 |
| `tests/test_audit.py` | T12–T13 |

---

### Task 1: Scaffold config, `_common` exits/paths/tokens/bootstrap

**Files:**
- Create: `config.default.json`
- Create: `scripts/_common.py`
- Create: `tests/conftest.py`
- Create: `tests/test_common_bootstrap.py`
- Create: `requirements-dev.txt` (pytest only)

**Interfaces:**
- Consumes: none
- Produces:
  - `EXIT_OK=0`, `EXIT_DECLINE=1`, `EXIT_USAGE=2`, `EXIT_IO=3`, `EXIT_CALL=4`, `EXIT_STATE=5`
  - `skill_root() -> Path`
  - `runtime_root() -> Path`
  - `ensure_runtime() -> Path`  # creates dirs + config.json from default if missing
  - `approx_tokens(text: str) -> int`
  - `load_config() -> dict`
  - `session_dir(session_id: str) -> Path`

- [ ] **Step 1: Write failing tests for bootstrap + tokens**

```python
# tests/conftest.py
import os
import pytest
from pathlib import Path

@pytest.fixture
def ts_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home

@pytest.fixture
def ts_cwd(tmp_path, monkeypatch):
    cwd = tmp_path / "proj"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd
```

```python
# tests/test_common_bootstrap.py
import json
from pathlib import Path
import scripts._common as common  # or import after sys.path insert — see Step 3

def test_ensure_runtime_creates_config(ts_home):
    root = common.ensure_runtime()
    assert root == ts_home / ".agent" / "token-saver"
    cfg = root / "config.json"
    assert cfg.is_file()
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["observationPack"]["tokenThreshold"] == 2000

def test_approx_tokens_heuristic():
    # "a b c" -> 3 words * 1.3 -> ceil 3.9 -> 4
    assert common.approx_tokens("a b c") == 4
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

Run: `pytest tests/test_common_bootstrap.py -v`  
Expected: FAIL import / not found

- [ ] **Step 3: Add `config.default.json` + `_common.py` minimal**

`config.default.json` (exact shape):

```json
{
  "version": 1,
  "actionFusion": {
    "enabled": true,
    "triggerPatterns": ["test", "build", "lint", "check", "run", "pytest", "cargo test", "npm test", "go test"],
    "maxFusionDepth": 3
  },
  "observationPack": {
    "enabled": true,
    "tokenThreshold": 2000,
    "maxHandleSize": 200,
    "archiveDir": "~/.agent/token-saver/archive/"
  },
  "evidencePreservingReducer": {
    "enabled": false,
    "reducerModel": "deepseek-v4-flash",
    "tokenThreshold": 3000,
    "preserveEvidence": true
  },
  "onlineContextCompact": {
    "enabled": true,
    "contextUsageThreshold": 0.6,
    "cacheWriteReadRatio": 12.5,
    "minSavingsRatio": 1.5
  },
  "auditInterval": 10
}
```

In `_common.py`: define exit constants; `skill_root()` = parent of `scripts/`; `runtime_root()`; `ensure_runtime()` copies default config if missing; `approx_tokens` using `math.ceil(len(text.split()) * 1.3)`; `load_config()`; `session_dir`.

Tests should import via:

```python
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import _common as common
```

Prefer this pattern in every test file (or once in `conftest.py`).

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_common_bootstrap.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.default.json scripts/_common.py tests/conftest.py tests/test_common_bootstrap.py requirements-dev.txt
git commit -m "feat: add token-saver runtime bootstrap and token heuristic"
```

---

### Task 2: Session ID resolution (T2–T4)

**Files:**
- Modify: `scripts/_common.py`
- Create: `tests/test_common_session.py`

**Interfaces:**
- Consumes: `ensure_runtime`, Path helpers from Task 1
- Produces:
  - `resolve_session_id(cwd: Path | None = None) -> str`
  - Behavior: env `TOKEN_SAVER_SESSION_ID` wins (no forced write); else upward search with hard stops; else create UUID in original cwd `.token-saver-session`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_common_session.py
import os
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
```

Also add a test that when walking hits a system path name (`tmp`, `var`, `usr` as path parts on Unix, or a dir named like resolved TEMP), creation happens at original cwd — implement `is_system_dir(path)` checking name against frozenset `{"tmp","var","usr","windows","system32"}` casefold, and/or equality to `Path(tempfile.gettempdir()).resolve()`.

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_common_session.py -v`  
Expected: FAIL `resolve_session_id` missing

- [ ] **Step 3: Implement `resolve_session_id`**

Pseudocode to implement exactly:

```python
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
    # create at original
    sid = str(uuid.uuid4())
    (original / ".token-saver-session").write_text(sid + "\n", encoding="utf-8")
    return sid
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_common_session.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/_common.py tests/test_common_session.py
git commit -m "feat: resolve token-saver session id with upward search stops"
```

---

### Task 3: Locked JSONL append + handle helper

**Files:**
- Modify: `scripts/_common.py`
- Create: `tests/test_common_events.py`

**Interfaces:**
- Consumes: `session_dir`, `ensure_runtime`
- Produces:
  - `MECHANISMS = frozenset({"action_fusion","observation_pack","online_compact"})`
  - `new_handle() -> str`  # `datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(4)`
  - `append_event(session_id: str, mechanism: str, payload: dict) -> None`
  - Raises/`SystemExit` mapping: illegal mechanism → caller uses EXIT_USAGE; I/O → EXIT_IO

- [ ] **Step 1: Write failing tests**

```python
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
    assert "timestamp" in obj

def test_concurrent_appends_no_partial_lines(ts_home, ts_cwd):
    common.ensure_runtime()
    sid = common.resolve_session_id(ts_cwd)
    def worker(i):
        common.append_event(sid, "action_fusion", {"fused_tools": ["Edit"], "note": str(i) * 200})
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    path = common.session_dir(sid) / "events.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            json.loads(line)

def test_handle_format():
    h = common.new_handle()
    assert common.HANDLE_RE.fullmatch(h)
```

Define `HANDLE_RE = re.compile(r"^\d{8}T\d{6}-[0-9a-f]{8}$")`.

Lock implementation sketch:

```python
def _lock_file(f):
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

def _unlock_file(f):
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

On Windows, open with `"a+"` and lock carefully (msvcrt locks bytes from current position — seek(0) then lock 1 byte is a common pattern; document in code comment). Prefer opening exclusive append: write line then flush before unlock.

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_common_events.py -v`

- [ ] **Step 3: Implement append + handle**

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add scripts/_common.py tests/test_common_events.py
git commit -m "feat: locked events.jsonl append and handle ids"
```

---

### Task 4: `session_recorder.py` CLI (T10–T11)

**Files:**
- Create: `scripts/session_recorder.py`
- Create: `tests/test_session_recorder.py`

**Interfaces:**
- Consumes: `resolve_session_id`, `append_event`, `MECHANISMS`, exit constants
- Produces CLI:
  - `ensure-session [--cwd PATH]` → stdout one-line session_id, exit 0
  - `record MECHANISM [--session ID] [--payload JSON] [--payload-file PATH]` → exit 0; bad mechanism → 2; bad JSON → 2; I/O → 3

- [ ] **Step 1: Write failing CLI tests**

```python
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

def run_rec(args, env, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "session_recorder.py"), *args],
        capture_output=True, text=True, cwd=cwd, env=env,
    )

def test_ensure_session_prints_id(ts_home, ts_cwd):
    env = {**dict(**__import__("os").environ), "HOME": str(ts_home), "USERPROFILE": str(ts_home)}
    env.pop("TOKEN_SAVER_SESSION_ID", None)
    r = run_rec(["ensure-session", "--cwd", str(ts_cwd)], env, ts_cwd)
    assert r.returncode == 0
    sid = r.stdout.strip()
    assert sid
    r2 = run_rec(["ensure-session", "--cwd", str(ts_cwd)], env, ts_cwd)
    assert r2.stdout.strip() == sid

def test_record_bad_mechanism(ts_home, ts_cwd):
    env = {**dict(**__import__("os").environ), "HOME": str(ts_home), "USERPROFILE": str(ts_home)}
    r = run_rec(["record", "not_a_mech", "--session", "s1", "--payload", "{}"], env, ts_cwd)
    assert r.returncode == 2

def test_payload_file_equiv(ts_home, ts_cwd, tmp_path):
    env = {**dict(**__import__("os").environ), "HOME": str(ts_home), "USERPROFILE": str(ts_home)}
    # ensure runtime + session via ensure-session first
    sid = run_rec(["ensure-session", "--cwd", str(ts_cwd)], env, ts_cwd).stdout.strip()
    payload = {"fused_tools": ["Edit", "Bash"], "note": "x"}
    pf = tmp_path / "p.json"
    pf.write_text(json.dumps(payload), encoding="utf-8")
    r = run_rec(["record", "action_fusion", "--session", sid, "--payload-file", str(pf)], env, ts_cwd)
    assert r.returncode == 0
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement argparse CLI**

```python
#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
# ensure sibling import
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c

def cmd_ensure(args):
    cwd = Path(args.cwd) if args.cwd else None
    print(c.resolve_session_id(cwd))
    return c.EXIT_OK

def cmd_record(args):
    if args.mechanism not in c.MECHANISMS:
        print(f"illegal mechanism: {args.mechanism}", file=sys.stderr)
        return c.EXIT_USAGE
    try:
        if args.payload_file:
            payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
        elif args.payload:
            payload = json.loads(args.payload)
        else:
            payload = {}
    except (OSError, json.JSONDecodeError) as e:
        print(str(e), file=sys.stderr)
        return c.EXIT_USAGE if isinstance(e, json.JSONDecodeError) else c.EXIT_CALL
    sid = args.session or c.resolve_session_id()
    try:
        c.ensure_runtime()
        c.append_event(sid, args.mechanism, payload)
    except OSError as e:
        print(str(e), file=sys.stderr)
        return c.EXIT_IO
    return c.EXIT_OK
```

Wire subparsers `ensure-session` and `record`.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add scripts/session_recorder.py tests/test_session_recorder.py
git commit -m "feat: add session_recorder ensure-session and record CLI"
```

---

### Task 5: `observation_pack.py` archive (T5–T7, T15)

**Files:**
- Create: `scripts/observation_pack.py` (archive subcommand first; recall/list stubs OK if tests only hit archive)
- Create: `tests/test_observation_pack.py` (archive cases)

**Interfaces:**
- Consumes: config, `approx_tokens`, `new_handle`, `append_event`, `resolve_session_id`, `session_dir`
- Produces:
  - `archive` stdout JSON: `handle`, `approx_tokens`, `archived_path`, `summary`
  - `summary` = first 3 lines + `f"(共 {n} 行)"` + suffix hint from extension
  - exit 1 if disabled or below threshold; exit 4 if file missing; on success also `append_event(..., observation_pack, {action: archive, ...})`

- [ ] **Step 1: Write failing tests**

```python
import json, sys, subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

def run_op(args, env, cwd):
    return subprocess.run([sys.executable, str(SCRIPTS / "observation_pack.py"), *args],
                          capture_output=True, text=True, cwd=cwd, env=env)

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
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `archive`**

Threshold: CLI `--threshold` overrides config `observationPack.tokenThreshold`.  
Write body to `session_dir(sid) / f"{handle}.txt"`.

- [ ] **Step 4: Run archive tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add scripts/observation_pack.py tests/test_observation_pack.py
git commit -m "feat: observation_pack archive with summary and thresholds"
```

---

### Task 6: `recall` + `list` (T8, T16)

**Files:**
- Modify: `scripts/observation_pack.py`
- Modify: `tests/test_observation_pack.py`

**Interfaces:**
- Consumes: archived `.txt` + events for metadata
- Produces:
  - `recall`: stdout text slice by `--offset-tokens` / `--max-tokens` (default 500); unknown handle → exit 5; optional recall event
  - `list`: JSON array or NDJSON — **lock to JSON array** on stdout for Agent parse: `[{"handle","approx_tokens","source_path"}, ...]` sorted by handle ascending; empty `[]` exit 0

Token slicing for recall: split archived text with `.split()` words; take slice `[offset : offset+max]`; re-join with spaces (acceptable B1 approximation). For multi-line fidelity alternative: walk characters estimating tokens with same heuristic cumulatively — prefer **word-based slice** and document in SKILL.

- [ ] **Step 1: Write failing tests**

```python
def test_recall_respects_max_tokens(ts_home, ts_cwd):
    # archive then recall with --max-tokens 50
    ...
    r = run_op(["recall", handle, "--max-tokens", "50"], _env(ts_home), ts_cwd)
    assert r.returncode == 0
    assert common.approx_tokens(r.stdout) <= 50 + 2  # small slack OK or exact

def test_recall_unknown_handle(ts_home, ts_cwd):
    # ensure session dir exists via ensure-session + empty
    r = run_op(["recall", "20990101T000000-deadbeef"], _env(ts_home), ts_cwd)
    assert r.returncode == 5

def test_list_empty_and_ordered(ts_home, ts_cwd):
    r = run_op(["list"], _env(ts_home), ts_cwd)
    assert r.returncode == 0
    assert json.loads(r.stdout) == []
    # archive two files (sleep 1s or mock handles if needed) then list length 2 sorted
```

For ordering without sleeping: unit-test list sorting by writing two handle files with known names via helper, or archive twice (handles include seconds — if same second, hex still differs; sort lexicographically equals time order for same-second? timestamp prefix equal then hex order — acceptable).

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement recall + list**

`list` reads archive dir `*.txt` stems as handles; enriches `source_path`/`approx_tokens` from latest matching `observation_pack` archive event in `events.jsonl` (scan once).

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add scripts/observation_pack.py tests/test_observation_pack.py
git commit -m "feat: observation_pack recall by tokens and list handles"
```

---

### Task 7: `audit.py` (T12–T13)

**Files:**
- Create: `scripts/audit.py`
- Create: `tests/test_audit.py`

**Interfaces:**
- Consumes: `events.jsonl` only for estimates (authoritative)
- Produces text report + JSON:

```json
{
  "session_id": "...",
  "action_fusion": {"count": 0, "tokens_saved": 0},
  "observation_pack": {"archive_count": 0, "tokens_saved": 0},
  "online_compact": {"count": 0, "estimated_count": 0, "unestimated_count": 0, "tokens_saved": 0},
  "total_tokens_saved": 0,
  "cost_usd_estimate": 0.0
}
```

Rules: fusion `count*700`; pack sum archive `approx_tokens*0.85`; compact only sum `approx_tokens_saved`; unestimated listed separately in text.

Missing session dir → exit 5 (state), message on stderr.

- [ ] **Step 1: Write failing tests**

```python
def test_audit_estimates(ts_home, ts_cwd):
    # seed events via session_recorder / append_event
    # 2 fusion, 1 archive 1000 tokens, 1 compact without saved, 1 compact with 100
    # expect fusion 1400, pack 850, compact 100, total 2350
    ...

def test_audit_json_format(ts_home, ts_cwd):
    r = run_audit(["--session", sid, "--format", "json"], ...)
    data = json.loads(r.stdout)
    assert "total_tokens_saved" in data
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement audit**

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add scripts/audit.py tests/test_audit.py
git commit -m "feat: audit session token savings text and json"
```

---

### Task 8: Docs — SKILL.md, mechanisms.md, install.sh, README (T14 manual)

**Files:**
- Create: `SKILL.md`
- Create: `references/mechanisms.md`
- Create: `scripts/install.sh`
- Modify: `README.md`

**Interfaces:**
- Consumes: all CLI contracts from Tasks 4–7
- Produces: installable skill docs; install.sh copies only

- [ ] **Step 1: Write `SKILL.md`**

Front matter:

```yaml
---
name: token-saver
description: 为 Agent Harness 节省 Token。B1：ObservationPack 归档/召回、机制事件记账、会话审计。当任务 Token 高或用户要求优化运行成本时使用。
version: 1.0.0
---
```

Must include: ensure-session first; timing table; exit code table (0–5); recall max-tokens ceiling; archive uses script `summary`; online_compact heuristic (>60% and Edit–Test done); missing scripts message; no reducer in B1; main-task-priority on code 3+.

- [ ] **Step 2: Write `references/mechanisms.md`**

Four sections (Action Fusion, ObservationPack, Evidence-Preserving Reducer, Online Context Compact): problem → SoL-Pi link → why tokens drop. Explicit note Reducer exists in design but **not executed in B1**. **Zero CLI commands.**

- [ ] **Step 3: Write `install.sh`**

Port from `exp.txt`: detect `~/.claude`, `~/.openclaw`, `~/.codex`, `~/.config/opencode`; `cp -r` skill root into `.../skills/token-saver`. Do **not** require creating runtime dirs (optional copy of config is OK but not mandatory). If no agents detected, exit 1 with message.

- [ ] **Step 4: Rewrite `README.md`**

Clone → optional `bash scripts/install.sh` → or direct `python scripts/...` → point to SKILL + spec. Document Windows path via `Path.home()`.

- [ ] **Step 5: Manual smoke (T14)**

On a machine with at least one agent dir (or mkdir fake `~/.claude`), run `bash scripts/install.sh` and confirm `SKILL.md` present under target. If bash unavailable on Windows, note in README: Git Bash/WSL, or manual copy.

- [ ] **Step 6: Commit**

```bash
git add SKILL.md references/mechanisms.md scripts/install.sh README.md
git commit -m "docs: add SKILL behavior, mechanisms reference, install script"
```

---

### Task 9: Acceptance sweep + `.gitignore` polish

**Files:**
- Modify: tests as needed to cover any remaining T IDs
- Modify: `.gitignore` (ignore `.token-saver-session`, `__pycache__`, `.pytest_cache`, local archives if any)
- Optional: `tests/test_acceptance_matrix.md` checklist mapping T1–T16 → test names (docs only, no CLI)

- [ ] **Step 1: Run full suite**

Run: `pytest tests/ -v`  
Expected: all PASS (T14 excluded)

- [ ] **Step 2: Fill gaps** if any T ID unmapped — add one test per gap

Mapping reminder:
- T1 → `test_ensure_runtime_creates_config`
- T2–T4 → `test_common_session.py`
- T5–T8,T15–T16 → observation tests
- T9–T11 → events + recorder
- T12–T13 → audit
- T14 → manual

- [ ] **Step 3: Commit**

```bash
git add tests .gitignore
git commit -m "test: complete B1 acceptance coverage T1-T13 T15-T16"
```

---

## Spec coverage self-check

| Spec item | Task |
|-----------|------|
| Flat CLI + config.default.json at root | 1, 4–7 |
| Bootstrap without install | 1 |
| session_id + hard stops + env | 2 |
| Handle format + flock JSONL | 3 |
| session_recorder CLI + payload-file | 4 |
| archive + summary + exits 1/4 + disabled | 5 |
| recall max-tokens + list T16 | 6 |
| audit text/json + no phantom compact | 7 |
| SKILL vs mechanisms split | 8 |
| install.sh copy-only | 8 |
| T1–T16 automation floor | 9 |
| No reducer / no harness | Global + Task 8 notes |

**Placeholder scan:** none intentional.  
**Type consistency:** `resolve_session_id`, `append_event`, `approx_tokens`, exit constants shared via `_common`.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-12-token-saver-b1.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — this session with executing-plans, batched with checkpoints  

Which approach?
