# PKS P1 Claim Review Implementation Plan

> English version first. 中文版在后。The Chinese version is the primary review surface for product and architecture decisions.

---

# English Version

## Purpose

P1 builds the first complete **Claim candidate and review loop** on top of the P0 Kernel.

P0 made the knowledge-state model durable: Capsules, Claims, Context Packs, `PKS.md`, health checks, tracking, audit logs, and explicit snapshots are now Kernel-managed. P1 should make long-term knowledge writes safer by separating proposed knowledge from accepted knowledge and by giving humans a clear CLI review workflow.

Authoritative sources:

- [`docs/core-design/pks_product_plan_v2.md`](../core-design/pks_product_plan_v2.md)
- [`docs/core-design/pks_kernel_design.md`](../core-design/pks_kernel_design.md)
- [`docs/core-design/pks_claim_design.md`](../core-design/pks_claim_design.md)
- [`docs/core-design/pks_capsule_design.md`](../core-design/pks_capsule_design.md)

## 1. P1 Scope

P1 focuses on **Claim and review**:

- independent Candidate Queue
- review CLI
- explainable ReviewStrategy
- Claim query filters
- domain policy show/validate commands
- design docs and tests synchronized with implementation

P1 does not include:

- Web UI
- MCP Server
- SQLite index
- Policy Engine for file permissions
- Task Contract Engine
- automatic candidate generation by LLM

Those remain future phases.

## 2. Decisions

P1 uses these product decisions:

- Candidates use the same core Claim schema.
- Candidates are stored separately under `capsules/<project_id>/candidates/`.
- `auto_accept` is a recommendation in P1, not an automatic merge.
- Policy-driven automatic merge remains a future goal after the review loop is stable.
- Reject does not persist rejected candidate YAML. Rejection is recorded only in audit log.
- Accepted Claims remain stored under `capsules/<project_id>/claims/`.
- Context Pack and `PKS.md` continue to ignore candidates.

## 3. Architecture

```text
Kernel
├── candidate/
│   ├── CandidateStore       # YAML-backed candidate assets
│   └── CandidateQueue       # submit/list/load/delete candidate Claims
├── review/
│   ├── ReviewStrategy       # explainable decision recommendation
│   └── ReviewEngine         # accept/reject candidate workflow
├── claim/
│   └── ClaimEngine          # accepted Claim lifecycle
├── capsule/
│   └── ProjectRegistry      # capsule path and policy loading
└── audit/
    └── AuditLog             # review accept/reject events
```

Review flow:

```text
submit_candidate
  ↓
candidates/<claim_id>.yaml
  ↓
pks review list/show
  ↓
ReviewStrategy recommendation
  ↓
accept → ClaimEngine accepts into claims/
reject → delete candidate YAML + audit log
```

## 4. Implementation Steps

1. Add `kernel/candidate/` with YAML-backed candidate storage.
2. Add Kernel methods:
   - `submit_candidate`
   - `list_candidates`
   - `load_candidate`
   - `delete_candidate`
   - `review_candidate`
   - `accept_candidate`
   - `reject_candidate`
3. Update Claim submission path:
   - `submit_claim` remains P0-compatible.
   - new agent-facing writes should call `submit_candidate`.
   - P1 CLI should prefer candidate/review commands for new long-term knowledge.
4. Add `ReviewEngine`.
5. Enhance `ReviewStrategy` output:
   - action
   - reason
   - conflicts
   - evidence issues
   - policy notes
6. Add review CLI:
   - `pks review list <project_id>`
   - `pks review show <project_id> <candidate_id>`
   - `pks review accept <project_id> <candidate_id>`
   - `pks review reject <project_id> <candidate_id>`
7. Add Claim query filters:
   - `pks claim list --status`
   - `pks claim list --type`
   - `pks claim list --domain`
   - `pks claim list --tag`
   - `pks claim list --subject`
8. Add policy CLI:
   - `pks policy show <domain>`
   - `pks policy validate <domain>`
9. Update docs:
   - Kernel design
   - Claim design
   - Capsule design if storage layout changes
   - README
10. Add tests and run full verification.

## 5. Acceptance Criteria

- Candidates are stored separately from accepted Claims.
- Rejected candidates are deleted and only recorded in audit log.
- Accepted candidates become accepted Claims under `claims/`.
- `auto_accept` is shown as recommendation but does not auto-merge candidates.
- Review CLI can list, show, accept, and reject candidates.
- Claim list filters work for status, type, domain, tag, and subject.
- Policy CLI can show and validate domain policy.
- Context Pack and `PKS.md` exclude candidates.
- Tests cover candidate storage, review accept/reject, strategy explanations, filters, policy validation, and CLI flows.

---

# 中文版

## 目的

P1 要在 P0 Kernel 之上补齐第一版完整的 **Claim 候选与审核闭环**。

P0 已经把知识状态模型做稳：Capsule、Claim、Context Pack、`PKS.md`、health、tracking、audit 和显式 snapshot 都由 Kernel 管理。P1 的目标是让长期知识写入更安全：把“候选知识”和“已接受知识”分开，并提供清晰的人类审核 CLI。

权威来源：

- [`docs/core-design/pks_product_plan_v2.md`](../core-design/pks_product_plan_v2.md)
- [`docs/core-design/pks_kernel_design.md`](../core-design/pks_kernel_design.md)
- [`docs/core-design/pks_claim_design.md`](../core-design/pks_claim_design.md)
- [`docs/core-design/pks_capsule_design.md`](../core-design/pks_capsule_design.md)

## 1. P1 范围

P1 聚焦 **Claim 与审核**：

- 独立 Candidate Queue
- review CLI
- 可解释的 ReviewStrategy
- Claim 查询筛选
- 领域策略 show/validate 命令
- 实现与设计文档同步

P1 不做：

- Web UI
- MCP Server
- SQLite 索引
- 文件权限 Policy Engine
- Task Contract Engine
- LLM 自动生成候选

这些进入后续阶段。

## 2. 已定决策

P1 采用以下产品口径：

- Candidate 复用 Claim 核心 schema。
- Candidate 独立存放在 `capsules/<project_id>/candidates/`。
- P1 中 `auto_accept` 只是审核建议，不自动合并。
- 策略驱动自动合并是后续明确目标，等审核闭环稳定后再开放。
- Reject 不保留 rejected candidate YAML，只写 audit log。
- Accepted Claim 继续存放在 `capsules/<project_id>/claims/`。
- Context Pack 和 `PKS.md` 继续排除 candidates。

## 3. 架构设计

```text
Kernel
├── candidate/
│   ├── CandidateStore       # YAML candidate 资产
│   └── CandidateQueue       # submit/list/load/delete candidate Claims
├── review/
│   ├── ReviewStrategy       # 可解释审核建议
│   └── ReviewEngine         # accept/reject candidate 流程
├── claim/
│   └── ClaimEngine          # accepted Claim 生命周期
├── capsule/
│   └── ProjectRegistry      # capsule path 与 policy 加载
└── audit/
    └── AuditLog             # review accept/reject 事件
```

审核流程：

```text
submit_candidate
  ↓
candidates/<claim_id>.yaml
  ↓
pks review list/show
  ↓
ReviewStrategy recommendation
  ↓
accept → ClaimEngine 写入 accepted claims/
reject → 删除 candidate YAML + 写 audit log
```

关键边界：

- Candidate Queue 只管理候选，不写 accepted Claim。
- ReviewEngine 负责把 candidate 转成 accepted Claim 或 reject。
- ClaimEngine 继续只管理 accepted Claim 生命周期。
- ReviewStrategy 只给建议和原因，不直接改状态。
- Reject 不落盘保留候选正文，避免 rejected 内容继续污染知识状态。

## 4. 实施步骤

### 4.1 Candidate Queue

新增 `src/pks/kernel/candidate/`：

- `CandidateStore`：读写 `candidates/<claim_id>.yaml`
- `CandidateQueue`：提交、列出、读取、删除 candidate

新增存储结构：

```text
~/.pks/capsules/<project_id>/
├── claims/
└── candidates/
```

`ProjectRegistry.create_capsule` 需要初始化 `candidates/` 目录。

### 4.2 Kernel 用例

新增 Kernel 方法：

- `submit_candidate(project_id, claim)`
- `list_candidates(project_id)`
- `load_candidate(project_id, candidate_id)`
- `delete_candidate(project_id, candidate_id)`
- `review_candidate(project_id, candidate_id)`
- `accept_candidate(project_id, candidate_id)`
- `reject_candidate(project_id, candidate_id)`

保留 `submit_claim` 兼容 P0，但 P1 的 agent-facing 写入应使用 `submit_candidate`。

### 4.3 Review Engine

新增 `ReviewEngine`：

- 读取 candidate。
- 调用 ReviewStrategy。
- accept 时调用 ClaimEngine 写入 accepted Claim。
- reject 时删除 candidate YAML，并写 audit log。
- accept 后删除 candidate YAML，避免重复审核。

ReviewEngine 不直接读写 `project.yaml`，不生成 Context Pack。

### 4.4 ReviewStrategy 增强

ReviewStrategy 输出应包含：

- `action`
- `reason`
- `conflicts`
- `evidence_issues`
- `policy_notes`

建议规则：

- missing evidence：reject recommendation。
- confidence `< 0.3`：reject recommendation。
- 有冲突：manual review。
- `constraint`、TasteAndStyle、架构类 Claim：manual review。
- factual 且超过阈值：auto_accept recommendation。

注意：P1 不因 auto_accept recommendation 自动合并。该 recommendation 的价值是先降低人工判断成本，并为后续策略驱动自动合并积累统计数据。

### 4.5 Review CLI

新增 `pks review`：

- `pks review list <project_id>`
- `pks review show <project_id> <candidate_id>`
- `pks review accept <project_id> <candidate_id>`
- `pks review reject <project_id> <candidate_id>`

输出应展示：

- candidate id
- subject/predicate/object
- content
- type/domain/confidence
- evidence source/excerpt
- ReviewStrategy recommendation
- conflicts
- evidence issues

### 4.6 Claim 查询筛选

增强 `pks claim list`：

- `--status`
- `--type`
- `--domain`
- `--tag`
- `--subject`

筛选只作用于 accepted Claim 存储，不查询 candidates。

### 4.7 Policy CLI

新增 `pks policy`：

- `pks policy show <domain>`
- `pks policy validate <domain>`

`show` 输出领域 `claim_policy.yaml`。

`validate` 校验：

- domain 合法。
- lifecycle type 合法。
- stale_after_days 为正整数或 null。
- auto_accept_threshold 在 `0.0` 到 `1.0` 之间或 null。
- manual_review_types 是合法 Claim type。

### 4.8 文档同步

更新：

- `docs/core-design/pks_kernel_design.md`
- `docs/core-design/pks_claim_design.md`
- `docs/core-design/pks_capsule_design.md`
- `README.md`

必要时新增 `docs/core-design/pks_review_design.md`，专门描述 candidate/review。

## 5. 验收标准

- Candidate 与 accepted Claim 分目录存储。
- reject 后 candidate YAML 被删除，只保留 audit log。
- accept 后 candidate 变为 accepted Claim，并从 candidates 删除。
- `auto_accept` 在 P1 只作为建议展示，不自动合并。
- review CLI 可以 list/show/accept/reject。
- Claim list 支持 status/type/domain/tag/subject 筛选。
- policy CLI 可以 show/validate 领域策略。
- Context Pack 和 `PKS.md` 不包含 candidates。
- 测试覆盖 candidate storage、review accept/reject、策略解释、查询筛选、policy 校验和 CLI 流程。

## 6. 测试计划

Kernel tests：

- 创建 Capsule 时初始化 `candidates/`。
- `submit_candidate` 写入 candidates，不写入 claims。
- `accept_candidate` 写入 claims，删除 candidate。
- `reject_candidate` 删除 candidate，只写 audit。
- `review_candidate` 返回 ReviewStrategy recommendation。
- auto_accept recommendation 不自动合并。
- Context Pack 和 `PKS.md` 排除 candidates。

CLI tests：

- `pks review list/show/accept/reject`
- `pks claim list --status/--type/--domain/--tag/--subject`
- `pks policy show`
- `pks policy validate`

Full verification：

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
```

## 7. 暂缓项

- SQLite index：等查询量上来后再加。
- Web UI：P2 再做 Claim 审核工作台。
- MCP Server：P3 再暴露 Agent 接口。
- Policy Engine：P3 与 Task Contract 一起设计。
- 自动合并 auto_accept：P0/P1 不开放；后续基于领域策略、证据完整性、冲突检测和审计要求开放高置信 Claim 自动合并，以降低人类审核负担。
