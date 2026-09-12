---
name: token-saver
description: 为 Agent Harness 节省 Token。B1：ObservationPack 归档/召回、机制事件记账、会话审计。当任务 Token 高或用户要求优化运行成本时使用。
version: 1.0.0
---

# Token Saver Skill

## 启用

用户说「优化 Token」/「节省 Token」，或调用 `/token-saver`（及 Harness 等价技能入口）时启用本 Skill。

## 第一步（每个项目会话一次）

```bash
python3 scripts/session_recorder.py ensure-session
```

stdout 仅输出一行 `session_id`（纯文本）。后续调用可传 `--session <id>`，也可省略（脚本会从 `.token-saver-session` 或 `TOKEN_SAVER_SESSION_ID` 解析）。

**主任务优先：** 任一机制返回退出码 **3 及以上** 时，跳过该机制、继续主任务；不得因省 Token 阻塞编码工作。

## 时机表

| 何时 | 做什么 |
|------|--------|
| Read/输出 ≥ `observationPack.tokenThreshold`（默认 2000）或同一文件读取 ≥2 次 | `python3 scripts/observation_pack.py archive <file_path>`；上下文只保留 handle + 脚本返回的 `summary` |
| 需要原文精确引用 | `python3 scripts/observation_pack.py recall <handle> [--max-tokens N]`；用毕即弃，长期上下文只留 handle |
| Edit/Write 后同轮验证（test/build/lint/check/run/pytest 等） | 同轮合并执行；随后 `python3 scripts/session_recorder.py record action_fusion --payload '{"fused_tools":[...]}'` |
| 上下文使用率 >60% **且** 刚完成完整 Edit→Test 循环 | 可 `record online_compact`（可选 `approx_tokens_saved`） |
| 会话结束或用户询问 | `python3 scripts/audit.py --session <id> [--format text\|json]` |
| 不确定有哪些归档 | `python3 scripts/observation_pack.py list [--session ID]` |

## 脚本契约

### session_recorder.py

- `ensure-session [--cwd PATH]` — stdout：session_id
- `record <mechanism> [--session ID] [--payload JSON] [--payload-file PATH]`
- 合法 mechanism：`action_fusion` | `observation_pack` | `online_compact`

### observation_pack.py

- `archive <file_path> [--session ID] [--threshold N]`
- `recall <handle> [--session ID] [--max-tokens 500] [--offset-tokens 0]`
- `list [--session ID]`

**archive：** stdout JSON 含 `handle`、`approx_tokens`、`archived_path`、`summary`。**必须使用脚本生成的 `summary`**，禁止自行长篇复述文件内容。

**recall：** `--max-tokens` 默认 500，是**上限而非目标**——能少取就少取；仅当需要精确原文时使用；优先多次小 recall，避免一次大 pull；用毕从上下文移除正文，保留 handle。

### audit.py

- `audit.py --session <id> [--format text|json]`

## 退出码（所有脚本）

| 码 | 含义 | Agent 动作 |
|----|------|------------|
| 0 | 成功 | 解析 stdout |
| 1 | 业务拒绝（如低于阈值、`enabled: false`） | 使用原文；不 record |
| 2 | 非法参数 / mechanism 枚举 | 修正参数；最多重试一次 |
| 3 | I/O / 锁 / 权限 | 跳过该机制；继续主任务 |
| 4 | 调用错误（文件缺失、路径无效） | 修正路径；最多重试一次 |
| 5 | 状态错误（未知 handle、会话目录缺失） | 先 `list`；否则重新 Read 源文件 |

Shell 信号（130/143）不在脚本契约内。

## 配置

读取 `~/.agent/token-saver/config.json`（Windows：`%USERPROFILE%\.agent\token-saver\config.json`）。首次运行任一脚本会自动创建运行时目录并复制 `config.default.json`。

- `observationPack.enabled: false` → 不调用 archive/recall
- `actionFusion.enabled: false` → 不 record action_fusion
- `onlineContextCompact.enabled: false` → 不 record online_compact
- **`evidencePreservingReducer`：B1 完全忽略**（即使 `enabled: true` 也不执行、不调用 reducer 模型）

## 脚本缺失

若 `scripts/*.py` 不存在，告知用户运行 `bash scripts/install.sh` 或手动复制本仓库到 Agent 的 `skills/token-saver/`；**禁止臆造行为**。

## stdout / stderr

机器可读结果在 **stdout**；诊断信息在 **stderr**。不要把 stderr 塞进上下文。

## 原理说明

四大机制的设计 rationale 见 [`references/mechanisms.md`](references/mechanisms.md)（不含 CLI 用法）。
