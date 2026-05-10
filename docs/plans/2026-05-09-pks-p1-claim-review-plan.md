# PKS P1 Claim Review Implementation Plan

> English version first. 中文版在后。The Chinese version is the primary review surface for product and architecture decisions.

---

# English Version

## Purpose

P1 builds the first complete **Claim candidate and review loop** on top of the P0 Kernel, after tightening the Claim schema, Markdown projection rules, and Capsule type system.

P0 made the knowledge-state model durable: Capsules, Claims, Content Pack / `PKS.md`, health checks, tracking, audit, and explicit snapshots are now Kernel-managed. P1 should make long-term knowledge writes safer by:
- Enforcing `min_support` rules per Claim type
- Separating proposed knowledge from accepted knowledge
- Making all Markdown strictly Claim projections
- Giving humans a clear CLI review workflow

Authoritative sources:

- [`docs/core-design/pks_product_plan_v2.md`](../core-design/pks_product_plan_v2.md)
- [`docs/core-design/pks_kernel_design.md`](../core-design/pks_kernel_design.md)
- [`docs/core-design/pks_claim_design.md`](../core-design/pks_claim_design.md)
- [`docs/core-design/pks_capsule_design.md`](../core-design/pks_capsule_design.md)
- [`docs/core-design/pks_projection_design.md`](../core-design/pks_projection_design.md)

## 1. P1 Scope

P1 focuses on **Claim structure, review, and projection discipline**:

- Claim `min_support` rules and type hierarchy enforcement
- `supporting_claims` field and type-level validation
- Markdown projection discipline (all MD = Claim collections)
- ProjectionSpec definition and default projection mapping by `capsule_type`
- Projection content/rule edit APIs
- Audit Claim migration
- `project.yaml` runtime metadata boundary
- Independent Candidate Queue
- Review CLI with explainable ReviewStrategy
- Claim query filters
- Domain policy show/validate commands
- Design docs and tests synchronized with implementation

P1 does not include:

- Web UI
- MCP Server
- SQLite index
- Policy Engine for file permissions
- Task Contract Engine
- Automatic candidate generation by LLM
- Automatic candidate merge (auto_accept is recommendation only)

Those remain future phases.

## 2. Decisions

P1 uses these product decisions:

- Candidates use the same core Claim schema.
- Fact is not a separate entity. Fact is `type=factual` Claim.
- Claim types form a support hierarchy: `factual` < `inference` < `preference` < `constraint`.
- Each type has different `min_support` requirements (evidence count, supporting_claims count, total support count).
- Higher-level Claims may cite lower-level Claims as support; lower-level Claims must not cite higher-level Claims as support.
- Candidates are stored separately under `capsules/<project_id>/candidates/`.
- `auto_accept` is a recommendation in P1, not an automatic merge.
- Reject does not persist rejected candidate YAML. Rejection is recorded as an Audit Claim without rejected body text.
- Content Pack and `PKS.md` are one concept. `PKS.md` IS the Content Pack.
- All Markdown files are Claim projections. No free-form text allowed.
- Each Markdown file must have a corresponding ProjectionSpec.
- `capsule_type` determines default ProjectionSpec set.
- `project.yaml` stays as minimal runtime metadata; project stage, goals, deliverables, and constraints become Claims.
- Projection content edits go through Kernel APIs and produce Candidate Claims or Claim patches.

## 3. Architecture

```text
Kernel
├── candidate/
│   ├── CandidateStore       # YAML-backed candidate assets
│   └── CandidateQueue       # submit/list/load/delete candidate Claims
├── review/
│   ├── ReviewStrategy       # explainable decision recommendation (uses min_support)
│   └── ReviewEngine         # accept/reject candidate workflow
├── render/
│   └── ProjectionEngine     # Claim collections → Markdown via ProjectionSpec
├── claim/
│   └── ClaimEngine          # accepted Claim lifecycle + min_support validation
├── capsule/
│   └── ProjectRegistry      # capsule path, policy, capsule_type → ProjectionSpec mapping
├── audit/
│   └── AuditClaimFactory    # review / sync / snapshot events as inference Claims
└── storage/
    └── YamlStore            # YAML read/write infrastructure
```

Review flow:

```text
submit_candidate
  ↓
min_support validation (ClaimEngine)
  ↓ pass
candidates/<claim_id>.yaml
  ↓
pks review list/show
  ↓
ReviewStrategy recommendation (uses claim_policy.yaml + min_support)
  ↓
accept → ClaimEngine accepts into claims/ + Audit Claim
reject → delete candidate YAML + Audit Claim
```

Projection edit flow:

```text
submit_projection_claim / patch_projection_claim
  ↓
min_support validation
  ↓ pass
Candidate Claim (semantic change) or direct update (non-semantic change)
  ↓ review
accepted → regenerate projection
```

## 4. Implementation Steps

### 4.1 Claim Schema: min_support

Add `min_support` to `claim_policy.yaml` and enforce in ClaimEngine:

```yaml
min_support:
  factual:
    evidence: 1
    supporting_claims: 0
    allowed_support_types: []
  inference:
    evidence: 0
    supporting_claims: 0
    evidence_or_claims_min: 1
    allowed_support_types: [factual]
  preference:
    evidence: 1
    supporting_claims: 0
    evidence_or_claims_min: 1
    allowed_support_types: [factual, inference]
    requires_human_source: true
  constraint:
    evidence: 1
    supporting_claims: 1
    evidence_or_claims_min: 2
    allowed_support_types: [factual, inference, preference]
    requires_manual_review: true
```

Implementation:
- Add `SupportingClaim` to Claim model.
- Add `MinSupportRule` to DomainPolicy model.
- Add `validate_min_support(claim, policy)` to ClaimEngine.
- Reject Claims that fail min_support at submission time.

### 4.2 Claim Schema: supporting_claims

Add `supporting_claims` field to Claim:
- Refine Evidence fields with `source_type` and optional `locator`.
- Validate type support hierarchy at submission.
- `factual` cannot cite `inference`, `preference`, `constraint` as support.
- `inference` must have external evidence or accepted factual Claim support.
- `preference` must have human-confirmed source or lower-level Claim support.
- `constraint` must have manual review and clear source or lower-level Claim support.

Schema simplifications (from discussion):
- `qualifier`: simplify from structured (scope/condition/temporal) to free-text string.
- `valid_from`: remove (redundant with `created_at` in most cases).
- `content`: required field — projection Markdown is composed from Claim content fields.
- `confidence`: simplify semantics — human=1.0, Agent self-assessed, Kernel=1.0 for Audit.
- `superseded_by`: keep for now (avoids reverse lookup), mark as derivable in future with SQLite.

### 4.3 Markdown Projection Discipline

Make all Markdown strictly Claim projections:

- Every Markdown file must have a corresponding ProjectionSpec.
- File header: `<!-- Generated from Claims. Do not edit directly. -->`.
- `capsule_type` determines default ProjectionSpec set (see Capsule design).
- `PKS.md` IS the Content Pack (same ProjectionSpec, same engine).
- `PKS_PROJECT.md`, `journal.md`, and domain Markdown are all Claim projections.
- Projection files are never read as sources of truth.
- ProjectionEngine can overwrite any projection file at any time.

### 4.4 Projection Edit APIs

Implement the two content edit interfaces:

**`submit_projection_claim(project_id, projection_id, claim_draft)`:**
1. Receive Claim draft (subject/predicate/object + evidence).
2. Auto-add tags from ProjectionSpec (ensure Claim appears in target projection).
3. Validate min_support.
4. Write to candidates/ as Candidate Claim.
5. Return Candidate ID.

**`patch_projection_claim(project_id, projection_id, claim_id, changes)`:**
1. Load target Claim.
2. Verify Claim belongs to specified projection.
3. Apply changes.
4. Re-validate min_support.
5. If semantic change (subject/predicate/object) → create new Candidate (supersedes old).
6. If non-semantic change (content/tags/qualifier) → direct update + Audit Claim.
7. Regenerate projection.

### 4.5 Capsule Type → ProjectionSpec Mapping

Implement `capsule_type` to default ProjectionSpec mapping:

| capsule_type | Default projections |
|---|---|
| SoftwareCapsule | PKS_PROJECT.md, journal.md, architecture.md, tasks.md |
| PluginCapsule | PKS_PROJECT.md, journal.md, architecture.md |
| ArticleCapsule | PKS_PROJECT.md, journal.md, outline.md, facts.md |
| VideoCapsule | PKS_PROJECT.md, journal.md, outline.md |
| DisciplineCapsule | PKS_PROJECT.md, journal.md, terminology.md, hypotheses.md |
| ModelCapsule | PKS_PROJECT.md, journal.md, hypotheses.md |

Each default projection has a built-in ProjectionSpec (filters, order, group_by).

PKS.md generation: aggregate all projections in inheritance order (Base → Domain → Custom → TasteAndStyle).

### 4.5.1 Multi-level TasteAndStyle

Implement TasteAndStyle at both domain level and type level:

Storage:
- Domain level: `domains/<domain>/taste_and_style/claims/`
- Type level: `domains/<domain>/types/<type>/taste_and_style/claims/`

Injection rules:
- Collect TasteAndStyle Claims from domain level first, then type level.
- Same `(subject, predicate)` conflict: type level overrides domain level.
- All TasteAndStyle Claims require manual review.
- Injected into PKS.md at the end of the aggregation.

### 4.6 Audit Claim Migration

- Create `type=inference` Audit Claims for review, sync, snapshot, lifecycle changes.
- Do not persist rejected candidate body text.
- Replace P0 `audit.log` with Audit Claims.
- Audit Claims use `created_by=kernel`, `tags=["audit"]`.

### 4.7 project.yaml Boundary

Keep only runtime registration fields:
- `project_id`, `name`, `capsule_type`, `domain`
- `external_project_path`, `repository_url`, `tracking`

Migrate to Claims:
- `stage` → `predicate=current_stage`, `type=factual`
- `current_goal` → `predicate=current_goal`, `type=factual`
- `deliverable` → `predicate=expected_deliverable`, `type=factual`
- `constraints` → `type=constraint`

These Claims enter `PKS_PROJECT.md` projection by default.

### 4.8 Candidate Queue

Add `src/pks/kernel/candidate/`:
- `CandidateStore`: read/write `candidates/<claim_id>.yaml`
- `CandidateQueue`: submit, list, load, delete

`ProjectRegistry.create_capsule` must initialize `candidates/` directory.

### 4.9 ReviewEngine

Add `ReviewEngine`:
- Read candidate.
- Call ReviewStrategy (which now checks min_support + policy).
- Accept: write to ClaimEngine + delete candidate + Audit Claim.
- Reject: delete candidate + Audit Claim (no body text).

### 4.10 ReviewStrategy Enhancement

ReviewStrategy output:
- `action`: auto_accept / manual_review / reject
- `reason`: human-readable explanation
- `conflicts`: list of conflicting Claim IDs
- `evidence_issues`: list of evidence problems
- `min_support_status`: pass/fail with details
- `policy_notes`: relevant policy rules applied

### 4.11 Review CLI

- `pks review list <project_id>`
- `pks review show <project_id> <candidate_id>`
- `pks review accept <project_id> <candidate_id>`
- `pks review reject <project_id> <candidate_id>`

### 4.12 Claim Query Filters

- `pks claim list --status`
- `pks claim list --type`
- `pks claim list --domain`
- `pks claim list --tag`
- `pks claim list --subject`
- `pks claim list --predicate` (new)

### 4.13 Policy CLI

- `pks policy show <domain>` — show claim_policy.yaml including min_support
- `pks policy validate <domain>` — validate policy structure and rules

### 4.14 Documentation Sync

Update all core design docs to reflect P1 changes (already done as part of this plan).

## 5. Acceptance Criteria

- Candidates are stored separately from accepted Claims.
- Claim schema validates `min_support` rules per type.
- `supporting_claims` field works with type hierarchy validation.
- Rejected candidates are deleted and only recorded as Audit Claims.
- Accepted candidates become accepted Claims under `claims/`.
- `auto_accept` is shown as recommendation but does not auto-merge.
- All Markdown files have corresponding ProjectionSpecs.
- Markdown files include "Generated from Claims" header.
- `capsule_type` determines default projection set.
- Projection content edit APIs produce Candidate Claims or direct updates.
- Semantic changes go through Candidate → Review path.
- Non-semantic changes update directly with Audit Claim.
- Review CLI can list, show, accept, and reject candidates.
- Claim list filters work for status, type, domain, tag, subject, predicate.
- Policy CLI can show and validate domain policy including min_support.
- `PKS.md` IS the Content Pack (one concept, one engine).
- `project.yaml` contains only runtime registration and tracking metadata.
- Audit events are persisted as `type=inference` Claims.
- Tests cover min_support validation, candidate storage, review accept/reject, projection edit APIs, strategy explanations, filters, policy validation, and CLI flows.

---

# 中文版

## 目的

P1 要在 P0 Kernel 之上补齐第一版完整的 **Claim 候选与审核闭环**，并先收紧 Claim schema、Markdown 投影规则和 Capsule 类型体系。

P0 已经把知识状态模型做稳。P1 的目标是让长期知识写入更安全：
- 强制执行每种 Claim 类型的 `min_support` 规则
- 把"候选知识"和"已接受知识"分开
- 让所有 Markdown 严格成为 Claim 集合的投影
- 提供清晰的人类审核 CLI

## 1. P1 范围

P1 聚焦 **Claim 结构、审核和投影纪律**：

- Claim `min_support` 规则和类型层级强制执行
- `supporting_claims` 字段和类型级校验
- Markdown 投影纪律（所有 MD = Claim 集合，不允许自由文本）
- ProjectionSpec 定义和 `capsule_type` 默认投影映射
- 投影内容/规则编辑接口
- Audit Claim 迁移
- `project.yaml` 运行时元数据边界
- 独立 Candidate Queue
- 可解释的 ReviewStrategy + Review CLI
- Claim 查询筛选
- 领域策略 show/validate 命令

P1 不做：Web UI、MCP Server、SQLite 索引、文件权限 Policy Engine、Task Contract Engine、LLM 自动生成候选、候选自动合并。

## 2. 已定决策

- Candidate 复用 Claim 核心 schema。
- Fact 就是 `type=factual` 的 Claim，不单独成实体。
- Claim 类型形成支撑层级：`factual` < `inference` < `preference` < `constraint`。
- 每种类型有不同的 `min_support` 要求（evidence 数量、supporting_claims 数量、总支撑数）。
- 高层 Claim 可以引用低层 Claim 作为支撑；低层不能引用高层。
- Candidate 独立存放在 `capsules/<project_id>/candidates/`。
- P1 中 `auto_accept` 只是审核建议，不自动合并。
- Reject 不保留 candidate YAML，只写 Audit Claim，不保存 rejected 正文。
- `PKS.md` 就是 Content Pack（一个概念，一套引擎）。
- 所有 Markdown 都是 Claim 投影，不允许自由文本。
- 每个 Markdown 文件必须有对应的 ProjectionSpec。
- `capsule_type` 决定默认 ProjectionSpec 集合。
- `project.yaml` 保留为最小运行时元数据。
- 投影内容编辑通过 Kernel API，产生 Candidate Claim 或 Claim patch。

## 3. 架构设计

```text
Kernel
├── candidate/
│   ├── CandidateStore       # YAML candidate 资产
│   └── CandidateQueue       # submit/list/load/delete
├── review/
│   ├── ReviewStrategy       # 可解释审核建议（使用 min_support）
│   └── ReviewEngine         # accept/reject 流程
├── render/
│   └── ProjectionEngine     # Claim 集合 → Markdown（通过 ProjectionSpec）
├── claim/
│   └── ClaimEngine          # accepted Claim 生命周期 + min_support 校验
├── capsule/
│   └── ProjectRegistry      # capsule path、policy、capsule_type → ProjectionSpec 映射
├── audit/
│   └── AuditClaimFactory    # 事件写成 inference Claim
└── storage/
    └── YamlStore
```

审核流程：

```text
submit_candidate
  ↓
min_support 校验（ClaimEngine）
  ↓ 通过
candidates/<claim_id>.yaml
  ↓
pks review list/show
  ↓
ReviewStrategy recommendation（claim_policy.yaml + min_support）
  ↓
accept → ClaimEngine 写入 claims/ + Audit Claim
reject → 删除 candidate + Audit Claim
```

投影编辑流程：

```text
submit_projection_claim / patch_projection_claim
  ↓
min_support 校验
  ↓ 通过
语素变更 → Candidate Claim（走 review）
非语素变更 → 直接更新 + Audit Claim
  ↓
重新生成投影
```

## 4. 实施步骤

### 4.1 Claim min_support

在 `claim_policy.yaml` 中增加 `min_support` 配置，在 ClaimEngine 中强制执行：

- 新增 `SupportingClaim` 到 Claim model。
- 新增 `MinSupportRule` 到 DomainPolicy model。
- 新增 `validate_min_support(claim, policy)` 到 ClaimEngine。
- 提交时校验，不满足则 reject。

### 4.2 supporting_claims 与类型层级

- Evidence 增加 `source_type` 和可选 `locator`。
- 校验 Claim 类型支撑层级。
- `factual` 不能引用高层 Claim 作为支撑。
- `inference` 必须有外部来源或 accepted factual Claim 支撑。
- `preference` 必须有人类确认来源或低层 Claim 支撑。
- `constraint` 必须人工审核，必须有清晰来源或低层 Claim 支撑。

### 4.3 Markdown 投影纪律

- 每个 Markdown 文件必须有对应的 ProjectionSpec。
- 文件头：`<!-- Generated from Claims. Do not edit directly. -->`。
- `capsule_type` 决定默认 ProjectionSpec 集合。
- `PKS.md` 就是 Content Pack。
- ProjectionEngine 可随时覆盖任何投影文件。

### 4.4 投影编辑接口

实现 `submit_projection_claim` 和 `patch_projection_claim`：

- `submit_projection_claim`：接收 Claim 草稿 → 自动补 tags → 校验 min_support → 写入 candidates。
- `patch_projection_claim`：加载目标 Claim → 验证归属 → 应用变更 → 语素变更走 review，非语素变更直接更新。

### 4.5 capsule_type → ProjectionSpec 映射

实现 `capsule_type` 到默认投影集合的映射。每种 `capsule_type` 有预定义的 ProjectionSpec 集合。

### 4.6 Audit Claim 迁移

- 所有审计事件写成 `type=inference` Claim。
- 替代 P0 的 `audit.log`。
- reject 不保留正文。

### 4.7 project.yaml 边界

- 保留运行时注册字段。
- `stage`/`current_goal`/`deliverable`/`constraints` 迁移为 Claims。
- 迁移后的 Claims 进入 `PKS_PROJECT.md` 投影。

### 4.8 Candidate Queue

新增 `src/pks/kernel/candidate/`。`create_capsule` 初始化 `candidates/` 目录。

### 4.9 ReviewEngine

- 读取 candidate → 调用 ReviewStrategy → accept/reject。
- accept 后删除 candidate YAML。
- reject 后删除 candidate YAML + 写 Audit Claim。

### 4.10 ReviewStrategy 增强

输出包含：`action`、`reason`、`conflicts`、`evidence_issues`、`min_support_status`、`policy_notes`。

### 4.11 Review CLI

`pks review list/show/accept/reject`。

### 4.12 Claim 查询筛选

`pks claim list --status/--type/--domain/--tag/--subject/--predicate`。

### 4.13 Policy CLI

`pks policy show/validate <domain>`。validate 覆盖 min_support 规则合法性。

## 5. 验收标准

- Claim schema 校验 `min_support` 规则。
- `supporting_claims` 字段与类型层级校验工作。
- Candidate 与 accepted Claim 分目录存储。
- reject 后 candidate 被删除，只保留 Audit Claim。
- accept 后 candidate 变为 accepted Claim。
- `auto_accept` 只作为建议，不自动合并。
- 所有 Markdown 文件有对应 ProjectionSpec。
- Markdown 文件包含 "Generated from Claims" 头。
- `capsule_type` 决定默认投影集合。
- 投影编辑接口产生 Candidate Claim 或直接更新。
- 语素变更走 Candidate → Review 路径。
- 非语素变更直接更新 + Audit Claim。
- review CLI 可以 list/show/accept/reject。
- Claim list 支持 status/type/domain/tag/subject/predicate 筛选。
- policy CLI 可以 show/validate（含 min_support）。
- `PKS.md` 就是 Content Pack（一个概念，一套引擎）。
- `project.yaml` 只含运行时注册和 tracking 元数据。
- audit 事件以 `type=inference` Claim 持久化。
- 测试覆盖 min_support 校验、candidate storage、review accept/reject、投影编辑接口、策略解释、查询筛选、policy 校验和 CLI 流程。

## 6. 测试计划

Kernel tests：

- `min_support` 校验：每种 Claim 类型的最低支撑要求。
- `supporting_claims` 类型层级校验。
- Evidence `source_type` / `locator` schema。
- `capsule_type` → 默认 ProjectionSpec 映射。
- 所有 Markdown 由 Claim 集合生成。
- `submit_projection_claim` 产生 Candidate Claim。
- `patch_projection_claim` 语素变更走 review，非语素变更直接更新。
- Audit Claim 覆盖 review accept/reject、snapshot、sync、生命周期变化。
- `project.yaml` 不保留 `stage/current_goal/deliverable/constraints`。
- 创建 Capsule 时初始化 `candidates/`。
- `submit_candidate` 校验 min_support 后写入 candidates。
- `accept_candidate` 写入 claims，删除 candidate。
- `reject_candidate` 删除 candidate，只写 Audit Claim。
- `review_candidate` 返回含 min_support_status 的 recommendation。
- auto_accept recommendation 不自动合并。
- PKS.md 排除 candidates。

CLI tests：

- `pks review list/show/accept/reject`
- `pks claim list --status/--type/--domain/--tag/--subject/--predicate`
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
- 自动合并 auto_accept：P0/P1 不开放；后续基于领域策略、证据完整性、冲突检测和审计要求开放高置信 Claim 自动合并。
- ProjectionSpec 落盘为 YAML 文件：P1 先用代码内置，等自定义投影需求稳定后再落盘。
