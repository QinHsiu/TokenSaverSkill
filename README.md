# Token Saver Skill (B1)

Cross-Harness skill that auditably reduces Agent token waste without modifying harness source. Savings map to `events.jsonl` and are reproducible via `audit.py`.

## Install

```bash
git clone <repo-url> token-saver
cd token-saver
bash scripts/install.sh   # optional — copies into detected Agent skill dirs
```

**Targets:** `~/.claude/skills/token-saver`, `~/.openclaw/workspace/skills/token-saver`, `~/.codex/skills/token-saver`, `~/.config/opencode/skills/token-saver`

**Manual copy:** Copy this repo into any Agent `skills/token-saver/` directory. `install.sh` only copies files; it does **not** create `~/.agent/token-saver` (Python scripts bootstrap runtime on first use).

### Windows

- **Runtime root:** `Path.home() / ".agent" / "token-saver"` → `%USERPROFILE%\.agent\token-saver`
- **Install script:** Use [Git Bash](https://git-scm.com/) or WSL:
  ```bash
  "C:\Program Files\Git\bin\bash.exe" scripts/install.sh
  ```
- Or manually copy the folder to `%USERPROFILE%\.claude\skills\token-saver\`

## Use without Agent install

Scripts work standalone from the repo:

```bash
python3 scripts/session_recorder.py ensure-session
python3 scripts/observation_pack.py archive path/to/large.txt
python3 scripts/audit.py --session <uuid> --format text
```

Session id: project file `.token-saver-session` or env `TOKEN_SAVER_SESSION_ID`.

## Docs

| File | Purpose |
|------|---------|
| [`SKILL.md`](SKILL.md) | When/how to call scripts, exit codes, timing |
| [`references/mechanisms.md`](references/mechanisms.md) | Four mechanisms — principles & SoL-Pi mapping (no CLI) |
| [`docs/superpowers/specs/2026-09-12-token-saver-b1-design.md`](docs/superpowers/specs/2026-09-12-token-saver-b1-design.md) | Full B1 spec |

## Enable in Agent

- Claude Code: `/token-saver` or ask to optimize token usage
- OpenClaw: `/skill token-saver`
- Codex: `@token-saver`

## Config

Factory defaults: [`config.default.json`](config.default.json). Live config: `~/.agent/token-saver/config.json` (auto-created on first script run).

## B1 scope

- ObservationPack archive/recall/list, session recording, audit
- No Evidence-Preserving Reducer (second model)
- No harness hooks or automatic context compression

## Tests

```bash
pytest
```
