# P0 Kernel 实施校准

来源：
- `docs/core-design/pks_product_plan_v2.md`
- `docs/plans/2026-05-08-pks-p0-implementation-plan.md`
- `docs/core-design/pks_kernel_design.md`
- `docs/core-design/pks_claim_design.md`
- `docs/core-design/pks_capsule_design.md`

## 本轮目标

把现有骨架推进到第一版可运行 Kernel：Kernel 成为 Capsule、Claim、Context Pack、`PKS.md` 投影和健康检查的唯一业务入口；CLI 只调用 Kernel API。

## 模块边界

| 模块 | 责任 |
|---|---|
| `kernel/facade.py` | 对外暴露 P0 用例方法，屏蔽存储细节。 |
| `kernel/capsule/` | 创建、读取、列出 Capsule，并维护领域默认策略与布局。 |
| `kernel/claim/` | YAML 持久化 Claim，提交、接受、过期、争议化、替代和冲突检测。 |
| `kernel/review/` | 读取 `claim_policy.yaml`，给出自动接受、人工审核或拒绝建议。 |
| `kernel/tracking/` | 检查 evidence 引用完整性；Git diff 跟踪 watched paths。 |
| `kernel/render/` | 生成 Context Pack 和 `PKS.md`，排除 candidate、stale、disputed、expired、superseded Claim。 |
| `kernel/snapshot/` | 显式创建和列出 PKS home Git 快照。 |
| `kernel/audit/` | 追加记录重要状态变化。 |
| `kernel/storage/` | YAML 读写基础设施。 |

## 完成判据

- `pks new` 通过显式字段创建 Capsule。
- Kernel 可创建、读取、列出 Capsule。
- Kernel 可提交、接受、列出、过期、争议化、替代 Claim。
- Claim evidence 强制存在，`pks health` 会检查 evidence。
- 领域级 `claim_policy.yaml` 会影响审核与 stale 计算。
- Context Pack 和 `PKS.md` 只输出 accepted 且非 stale 的 Claim。
- CLI 的 `claim add`、`claim accept`、`claim list`、`health`、`project` 类命令只调用 Kernel。
- CLI 已覆盖 `project sync`、`claim expire/dispute/supersede`、`snapshot create/list`。
- 测试覆盖 schema、存储、Kernel 工作流、冲突检测、健康检查、投影。

## 暂缓项

- SQLite 索引：等 Claim 查询量或 tracking 查询需要时再引入。
- Web UI、MCP Server：不属于 P0 本轮实现。
- Snapshot 自动触发：P0 明确不做，避免状态变更产生隐藏 Git 副作用。

## 进度

- [x] 读取权威设计与 P0 计划。
- [x] 跑通现有测试基线。
- [x] 重构 schema 与存储布局。
- [x] 实现 Kernel 模块。
- [x] 接入 CLI。
- [x] 补齐测试与文档状态。
- [x] 严格收口 Snapshot、生命周期 CLI、project sync 和 update/resolve 用例。

## 本轮结果

- 新增 `src/pks/kernel/`，包含 Registry、ClaimEngine、ReviewStrategy、Tracker、Context、Projection、Audit 和 Kernel facade。
- Kernel 已按业务边界拆分为 `capsule/`、`claim/`、`review/`、`tracking/`、`render/`、`audit/`、`storage/`。
- `ProjectMetadata` 已包含 `TrackingConfig`、交付物和约束；领域目录会生成默认 `claim_policy.yaml` 与 TasteAndStyle Claim 目录。
- Context Pack 和 `PKS.md` 投影会注入对应领域的 accepted TasteAndStyle Claim。
- Claim 写入走 `submit_claim`；高置信 factual Claim 可按领域策略自动接受；冲突 Claim 进入人工审核路径。
- `stale` 保持为计算属性，由 `pks health`、Context Pack 和 `PKS.md` 投影共同使用。
- `ProjectTracker` 已支持 evidence 完整性检查和 Git diff watched paths 同步。
- `SnapshotManager` 已支持显式 `create_snapshot` 和 `list_snapshots`。
- CLI 已通过 Kernel 接入 `new`、`context`、`health`、`claim add/accept/list/expire/dispute/supersede`、`project list/sync/projection`、`snapshot create/list`。
- 核心设计文档已同步为 `pks_kernel_design.md`、`pks_claim_design.md`、`pks_capsule_design.md`。

验证：
- `.venv/bin/python -m pytest -q`：18 passed。
- `.venv/bin/python -m ruff check .`：All checks passed。
- CLI smoke：`init-home → new → claim add → context/health` 通过。
