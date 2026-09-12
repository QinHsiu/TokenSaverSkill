# Token Saver Skill B1 — Design

**Date:** 2026-09-12  
**Status:** Approved for implementation planning (sections 1–4 locked)  
**Source:** `Temp/skills/token_saver/exp.txt` + B1 scope lock  
**Scope:** B1 only — flat CLI scripts + SKILL behavior instructions + local archive/audit. No harness hooks, no reducer model calls.

## Goal

Deliver a cross-Harness installable Skill that reduces Agent token waste **without modifying harness source**, with every claimed saving traceable to `events.jsonl` and reproducible via `audit.py`.

## Decisions (locked)

| Decision | Choice |
|----------|--------|
| Scope | **B1** (not A pure prompts, not B2 reducer/hot-reload, not C harness middleware) |
| Layout | Flat CLI scripts under `scripts/`; `config.default.json` at skill root |
| Runtime root | `Path.home() / ".agent" / "token-saver"` (Windows: `%USERPROFILE%\.agent\token-saver`) |
| session_id | Project file `.token-saver-session` (UUID); optional `TOKEN_SAVER_SESSION_ID` override |
| Approach | Scheme 1 — independent `argparse` CLIs callable via Bash |

## Package layout

```text
TokenSaverSkill/   # skill root (= installable token-saver package)
├── SKILL.md
├── config.default.json
├── README.md
├── scripts/
│   ├── install.sh
│   ├── observation_pack.py
│   ├── session_recorder.py
│   └── audit.py
├── references/
│   └── mechanisms.md
└── docs/superpowers/specs/
    └── 2026-09-12-token-saver-b1-design.md
```

| Path | Responsibility |
|------|----------------|
| `SKILL.md` | When to call which script; exit-code handling; not a paper rewrite |
| `config.default.json` | Factory defaults (read-only template) |
| `scripts/install.sh` | Copy skill into detected Agent skill dirs only |
| `scripts/observation_pack.py` | archive / recall / list |
| `scripts/session_recorder.py` | ensure-session / record |
| `scripts/audit.py` | Post-session savings estimate |
| `references/mechanisms.md` | Four mechanisms: principles + SoL-Pi mapping + why each saves tokens. **No CLI usage** (that belongs in `SKILL.md` only) |

**Bootstrap:** All three Python scripts mkdir runtime dirs and copy default config on first run. `install.sh` is **not** a runtime prerequisite.

**Doc split:** `references/mechanisms.md` explains *why* (principles, SoL-Pi correspondence, token-saving rationale). `SKILL.md` explains *when/how to call scripts* and exit-code handling. Do not duplicate CLI contracts into `mechanisms.md`.

**Install targets:** Claude Code (`~/.claude/skills/token-saver`), OpenClaw, Codex, OpenCode — detect existing agent dirs and copy.

---

## Data model & CLI contracts

### Runtime directory

```text
~/.agent/token-saver/          # Path.home() based
├── config.json
└── archive/
    └── <session_id>/
        ├── events.jsonl
        └── <handle>.txt
```

### session_id resolution

1. If `TOKEN_SAVER_SESSION_ID` set → use it (do not force write to file).
2. Else search upward from CWD for `.token-saver-session`:
   - **Hard stops** (then create file in **original CWD**): filesystem root; more than **8** parents; system dirs (`/tmp`, `/var`, `/usr`, and Windows equivalents e.g. resolved `%TEMP%`, `C:\Windows`).
   - Encountering `.git` does **not** stop (monorepo may share across nested repos).
3. If found → read trimmed contents.
4. If not found → write new UUID v4 to `.token-saver-session` in original CWD.

### Handle format (locked)

```text
<YYYYMMDDTHHMMSS>-<8hex>
# example: 20260912T170800-a3f9c1d2
# archive file: <handle>.txt
```

### Event schema (`events.jsonl`, one JSON object per line)

```json
{
  "timestamp": "2026-09-12T17:08:00+08:00",
  "session_id": "<uuid>",
  "mechanism": "action_fusion | observation_pack | online_compact",
  "payload": {}
}
```

| mechanism | Required payload fields |
|-----------|-------------------------|
| `action_fusion` | `fused_tools` (array); optional `note` |
| `observation_pack` | `handle`, `source_path`, `approx_tokens`, `action` (`archive` \| `recall`) |
| `online_compact` | optional `reason`, optional `approx_tokens_saved` |

**Concurrency:** `record` must take an exclusive file lock (`fcntl.flock` on Unix; `msvcrt.locking` on Windows), append one line, release immediately.

**Token heuristic:** `approx_tokens = ceil(word_count * 1.3)` where `word_count = len(text.split())`.

### CLI surfaces

**session_recorder.py**

```text
ensure-session [--cwd PATH]     # stdout: session_id only (plain text, one line)
record <mechanism> [--session ID] [--payload JSON] [--payload-file PATH]
```

**observation_pack.py**

```text
archive <file_path> [--session ID] [--threshold N]
recall <handle> [--session ID] [--max-tokens 500] [--offset-tokens 0]
list [--session ID]
```

`archive` stdout JSON (required keys):

```json
{
  "handle": "20260912T170800-a3f9c1d2",
  "approx_tokens": 3200,
  "archived_path": "...",
  "summary": "<first 3 lines + line count + type hint>"
}
```

`summary` is **script-generated**. Agent must place `summary` + handle in context; must not invent its own long paraphrase of the file.

`recall` semantics:

- Default `--max-tokens 500` is a **ceiling**, not a target — pull less when possible.
- Use only when exact source text is needed; **discard after use**; keep handle in long-lived context.
- Prefer additional small recalls over one large pull.

`list` stdout: one entry per handle, ascending by timestamp embedded in handle; each entry includes `handle`, `approx_tokens`, `source_path` (from events or sidecar). Empty session → exit 0 + empty list.

**audit.py**

```text
audit.py --session <id> [--format text|json]
```

Savings rules:

| Mechanism | Estimate |
|-----------|----------|
| `action_fusion` | `count * 700` |
| `observation_pack` | sum of **archive** events' `approx_tokens` × 0.85 (do not double-count recalls) |
| `online_compact` | sum of `approx_tokens_saved` when present; if missing → **exclude from total**, report “N times (unestimated)” |
| Cost (illustrative) | `total_tokens / 1e6 * 15` USD |

### Exit codes (all scripts)

| Code | Meaning | Agent action |
|------|---------|--------------|
| 0 | Success | Parse stdout |
| 1 | Business decline (e.g. below threshold) | Use original text; do not record |
| 2 | Illegal args / mechanism enum | Fix args; retry once |
| 3 | I/O / lock / permission | Skip mechanism; continue main task |
| 4 | Call error (missing file / bad path) | Fix path; retry once |
| 5 | State error (unknown handle / missing session dir) | `list` once; else re-Read source |

Signals (130/143) are **not** part of the script contract; shell-level interrupts stop the whole user task.

**Priority:** Saving tokens must not block the main coding task when a mechanism fails with code 3+.

---

## SKILL.md behavior

### Enable

Natural language (“优化 Token”) or `/token-saver` / harness-equivalent skill invoke.

### First step

`python3 scripts/session_recorder.py ensure-session` once per project session; pass `--session` afterward when convenient.

### Timing map

| When | Do |
|------|----|
| Read/output ≥ `observationPack.tokenThreshold` (default 2000) or same file read ≥2× | `archive`; keep handle + script `summary` only |
| Need exact quote | `recall` with small `--max-tokens`; discard after use |
| Edit/Write then verify Bash (test/build/lint/check/run/pytest/…) | Same-turn fuse; then `record action_fusion` |
| Context usage >60% **and** a full Edit–Test loop just finished | May `record online_compact` (optional `approx_tokens_saved`) |
| Session end / user asks | `audit.py --session <id> [--format json]` |

### Config switches

Read `config.json`. If `observationPack.enabled` / action-fusion guidance is false → Agent must not call those paths.  
`evidencePreservingReducer`: **ignored in B1** even if `enabled: true` (no second model).

### Missing scripts

If `scripts/*.py` missing → tell user to run `install.sh` or copy repo into Agent `skills/`; do not invent behavior.

### stdout vs stderr

Machine results on stdout; diagnostics on stderr. Do not stuff stderr into context.

---

## Testing & non-goals

### Acceptance (all required)

| ID | Pass condition |
|----|----------------|
| T1 | Cold start without install creates runtime dir + default config |
| T2 | `ensure-session` creates UUID file; second call same id |
| T3 | Upward search hard-stops as specified; `.git` does not stop |
| T4 | Env override wins; no forced write-back |
| T5 | `archive` handle format + JSON fields + event line |
| T6 | Below threshold → exit 1; no archive/record |
| T7 | Missing file → exit 4 |
| T8 | `recall` respects max-tokens; unknown handle → exit 5 |
| T9 | Concurrent `record` → no partial JSON lines |
| T10 | Bad mechanism → exit 2 |
| T11 | `--payload-file` ≡ `--payload` |
| T12 | `audit` text estimates per locked rules |
| T13 | `audit --format json` stable parseable |
| T14 | `install.sh` copies only; not runtime prerequisite (manual OK) |
| T15 | `enabled: false` declines archive (exit 1) and SKILL says skip |
| T16 | `list`: empty → exit 0 + empty list; N handles → N rows with handle/approx_tokens/source_path; ascending by handle timestamp |

**Automation floor:** pytest with temp `HOME`/`USERPROFILE` + tmp cwd covering T1–T13 + T16. T14 manual/optional.

### Non-goals (v1)

- No harness source changes; no real tool-call interception
- No Evidence-Preserving Reducer / second model
- No live token meters, config hot-reload, cloud sync, auto-delete archives
- No automatic context compression engine (manual + heuristic record only)
- Dollar savings are illustrative only

### Success definition

A **cross-Harness installable** Skill that, **without modifying harness source**, **auditably** reduces Agent token waste (every saving maps to an `events.jsonl` event; audit is reproducible).

---

## Config default shape

Align with `exp.txt`, factory file at skill root `config.default.json`:

- `actionFusion.enabled`: true (behavior + record; no harness fuse)
- `observationPack.enabled`: true; `tokenThreshold`: 2000; `maxHandleSize`: 200
- `evidencePreservingReducer.enabled`: false (B1 ignore)
- `onlineContextCompact.enabled`: true (heuristic + record only)
- `auditInterval`: 10 (advisory in SKILL; not enforced by scripts in B1)

---

## Implementation note

Shared helpers (path resolve, lock append, token estimate) may be duplicated lightly across the three scripts to keep flat CLIs self-contained, or a tiny `_common.py` beside them **only if** import-by-path stays zero-config for `python3 scripts/foo.py`. Prefer `_common.py` in the same `scripts/` directory imported via relative file path / `sys.path` insert of `scripts/` — still scheme 1, not a packaged module.
