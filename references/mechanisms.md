# Token Saver — 四大机制原理

本文说明 *为什么* 省 Token，以及每项机制与 SoL-Pi 的对应关系。**CLI 用法见 `SKILL.md`，此处不含命令。**

---

## 1. Action Fusion（编辑与验证合并）

**问题：** Agent 轨迹中最常见的浪费序列是「修改文件 → 收到结果 → 再单独调用 Bash 去测试」。中间这轮模型决策只负责「决定跑什么命令」，本身不产出新信息，却消耗完整推理 Token。

**SoL-Pi 联系：** SoL-Pi 将「动作链」视为可局部融合的局部执行单元；Harness 在底层串行完成 Edit 与验证命令，模型只接收合并后的观测，等价于缩短决策深度。

**为何省 Token：** 每融合一次 Edit→Verify，省掉至少一轮完整模型调用（系统提示 + 工具 schema + 中间 reasoning）。B1 由 Agent 在同轮手动合并并 `record`，审计按次 ×700 估算。

---

## 2. ObservationPack（大文本句柄化）

**问题：** 大文件或长命令输出一旦被 Read 进上下文，后续每一轮都要为整块文本重复付费，即使模型已不再需要全文。

**SoL-Pi 联系：** ObservationPack 将重复出现的大型观测归档为稳定 handle；上下文只保留轻量索引（handle + 脚本 summary），需要精确引用时再分页 recall。

**为何省 Token：** 归档后上下文从数千 token 降至数十 token；recall 按需、小批量、用毕即弃，避免「常驻全文」。审计对 archive 事件的 `approx_tokens` 按 ×0.85 计入节省（不重复计 recall）。

---

## 3. Evidence-Preserving Reducer（长日志先筛后核）

**问题：** 长任务产生大量诊断日志（stderr、堆栈、测试报告）。其中真正驱动下一步决策的可能只有几行，却让旗舰模型从头读整份输出。

**SoL-Pi 联系：** 两阶段流程——廉价 reducer 初筛关键行，主模型核验每条引用可回溯到归档源；核验失败则保留原文，保证证据链。

**为何省 Token：** 将数千行日志压缩为带引用的「收据」，主模型只读压缩结果。理论上可大幅削减诊断类观测的上下文占用。

> **B1 说明：** 本机制在设计中存在，但 **B1 不执行**——无第二模型调用、无 reducer 脚本。配置项 `evidencePreservingReducer.enabled` 被忽略。后续版本（B2+）再实现。

---

## 4. Online Context Compact（在线上下文压缩）

**问题：** 上下文越长，历史材料越像「算力税」；但盲目压缩会打断 KV-cache 复用，重写成本可能高于收益。

**SoL-Pi 联系：** 将已完成的子任务（如完整 Edit→Test 通过）标记为潜在压缩点；仅当上下文使用率超过阈值（默认 60%）且预期节省大于重写成本时才记录压缩事件。

**为何省 Token：** 在子任务边界丢弃已完成段的细节，保留结论与 handle，降低后续每轮 prompt 长度。B1 为启发式 + 手动 `record`（可选 `approx_tokens_saved`），无自动压缩引擎。

---

## 审计与可追溯性

每项节省必须能映射到 `~/.agent/token-saver/archive/<session_id>/events.jsonl` 中的一行事件；`audit.py` 按机制规则汇总，使声称的节省可复现、可核对。
