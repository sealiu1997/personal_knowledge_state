# PKS P0 Kernel Implementation Plan

> English version first. 中文版在后。The Chinese version is the primary review surface for product and architecture decisions.

> Calibration note, 2026-05-10: this is a historical P0 plan. The current core design treats Fact as `type=factual` Claim, treats all Markdown as Claim projections, and merges Content Pack with `PKS.md`. Use `docs/core-design/` and the P1 plan for current terminology.

> 校准说明，2026-05-10：本文是历史 P0 计划。当前核心设计将 Fact 视为 `type=factual` Claim，将所有 Markdown 视为 Claim 投影，并把 Content Pack 与 `PKS.md` 合并为同一概念。当前术语以 `docs/core-design/` 和 P1 计划为准。

---

# English Version

## Purpose

P0 builds the first usable PKS Kernel. The Kernel is the control layer that manages both **Claims** and **Capsules**. Context Packs, `PKS.md`, CLI output, and future MCP/Web UI views are projections over Kernel-managed state, not sources of truth.

The goal is not to build a full personal knowledge app in P0. The goal is to make the core knowledge-state model hard to corrupt and easy to extend.

Authoritative source: [`docs/core-design/pks_product_plan_v2.md`](../core-design/pks_product_plan_v2.md)

## 1. Claim Data Structure Design

Claim is the atomic unit of long-term knowledge. PKS should not store durable knowledge as loose paragraphs because paragraphs are hard to verify, expire, supersede, or dispute precisely. A Claim must be small enough to be checked and structured enough to support conflict detection.

P0 should make the Claim schema stable before building richer workflows.

Core fields:

- `claim_id`: stable identifier.
- `subject`, `predicate`, `object`: semantic triple used for conflict detection and querying.
- `qualifier`: optional scope, condition, and temporal limit.
- `content`: human-readable statement, generated or manually written.
- `type`: `factual`, `inference`, `preference`, or `constraint`.
- `domain`: `content`, `dev`, or `research`.
- `tags`: lightweight grouping.
- `evidence`: mandatory list of evidence items.
- `status`: lifecycle state.
- `confidence`: confidence score from `0.0` to `1.0`.
- `created_at`, `created_by`, `valid_from`, `valid_until`, `last_verified`: provenance and lifecycle metadata.
- `supersedes`, `superseded_by`: replacement tracking.
- `project`: owning project or capsule id.

Evidence fields:

- `source_ref`: file, manual source, URL, journal reference, or other source locator.
- `relation`: `supports`, `weak_supports`, `contradicts`, or `supersedes`.
- `excerpt`: exact source snippet used for integrity checks.

Design rules:

- A Claim without evidence is invalid.
- `(subject, predicate)` is the conflict key.
- Same `(subject, predicate)` with different `object` is a potential conflict unless explicitly modeled as a scoped complement.
- `supersedes` must point to a Claim with the same `(subject, predicate)`.
- TasteAndStyle is represented as normal `Claim(type=preference)`, not as a separate preference file format.
- `stale` is a computed property, not a `ClaimStatus`. An accepted Claim can become stale while still being accepted. `pks health` and Context Pack generation compute staleness from `last_verified`, domain-level `stale_after_days`, and evidence integrity results.

## 2. Capsule Class Design

Capsule is the project knowledge-state container. It does not replace the project folder. It records the current state, boundary, claims, journal, and domain-specific modules for a project.

Capsule hierarchy follows v2:

```text
BaseCapsule
├── ContentCapsule + TasteAndStyle
│   ├── ArticleCapsule
│   ├── VideoCapsule
│   └── GameCapsule
├── DevCapsule + TasteAndStyle
│   ├── SoftwareCapsule
│   └── PluginCapsule
└── ResearchCapsule + TasteAndStyle
    ├── DisciplineCapsule
    └── ModelCapsule
```

BaseCapsule minimum structure:

```text
project.yaml
PKS_PROJECT.md
claims/
journal.md
```

`project.yaml` owns machine-readable metadata, including project path, repository URL, and `tracking:` configuration.

Domain extensions:

- ContentCapsule: `outline.md`, `facts.md`
- DevCapsule: `architecture.md`, `tasks.md`
- ResearchCapsule: `terminology.md`, `hypotheses.md`

Storage principle:

- PKS data lives outside project folders, under PKS home.
- Project folders may receive a generated `PKS.md` projection.
- `context.md` is not persisted.
- Domain-level TasteAndStyle Claims live under the domain area and are injected into relevant Context Packs.

The first `pks new` should be form-style: explicit fields, predictable output, and easy tests. It should not try to understand the user. Humans or Agents do the thinking first, then call `pks new` with precise parameters.

## 3. Kernel Module Design

The P0 Kernel manages Capsule and Claim state through explicit modules. CLI is only an adapter.

Recommended modules:

- `ProjectRegistry`: register, create, load, update, list, and resolve project Capsules and their domain modules.
- `ClaimEngine`: read/write Claims as durable YAML assets, validate Claims, detect conflicts, validate supersession, filter context-eligible Claims, and mark lifecycle changes. Any `ClaimStore` implementation should stay internal to this module unless it becomes independently useful.
- `ReviewStrategy`: minimal P0 rules for accept/manual-review/reject decisions. It reads domain-level `claim_policy.yaml` to apply `auto_accept_threshold`, manual-review requirements, and lifecycle policy.
- `ProjectTracker`: implement v2's A + C tracking: Git Diff plus Evidence integrity checks.
- `ContextEngine`: generate Context Pack from Capsule state and accepted non-stale Claims.
- `ProjectionEngine`: generate project-folder `PKS.md`.
- `AuditLog`: record important state changes in a minimal append-only log.
- `SnapshotManager`: use Git for snapshots where appropriate.

SQLite is infrastructure for indexed lookup, not a separate Kernel module. Introduce it when Claim or tracking queries need indexed access.

The Kernel facade should expose use-case methods such as:

- `create_capsule`
- `load_capsule`
- `list_capsules`
- `submit_claim`
- `accept_claim`
- `expire_claim`
- `supersede_claim`
- `mark_claim_stale`
- `mark_claim_disputed`
- `list_claims`
- `check_evidence`
- `health_check`
- `sync_project`
- `generate_pks_new_params`
- `render_context`
- `render_projection`

## 4. Notes And Constraints

- v2 is the main line. Do not invent behavior that contradicts it.
- When a design detail is unclear, stop and ask rather than filling in product policy.
- PKS must track project folders without taking them over.
- Project tracking in P0 should use A + C: Git Diff for active tracking, Evidence integrity checks as passive fallback.
- Non-Git projects degrade to Evidence integrity checks.
- Agent writes to long-term state must go through candidate/review paths, even if P0 only implements a minimal version.
- Tests should exercise Kernel behavior directly before CLI behavior.
- Current implementation repository should be initialized as a Git repository.

## 5. Implementation Steps

1. Initialize the implementation repository as Git and commit the current baseline after review.
2. Redesign core schemas around Claim, Evidence, Qualifier, Capsule, ProjectMetadata, TrackingConfig, DomainPolicy, and TasteAndStyle Claim.
3. Implement PKS home and durable Capsule storage layout.
4. Implement Kernel facade and module boundaries.
5. Implement ClaimEngine with internal YAML-backed storage.
6. Implement form-style `pks new`.
7. Implement Context Pack and `PKS.md` projection generation so the core loop can run: create Capsule, add/accept Claim, generate context.
8. Add minimal Claim CLI commands: add, accept, list, health.
9. Implement ProjectTracker with Git Diff plus Evidence integrity checks.
10. Add audit/logging and snapshot hooks where P0 state changes need traceability.
11. Add SQLite-backed index when Claim or tracking queries require indexed access.
12. Run full verification and update README only after behavior is real.

## 6. Acceptance Criteria

- The repository is initialized as a Git software project.
- Core schemas express Claim, Capsule, Domain policy, and tracking concepts clearly.
- Kernel can create, load, and list Capsules without CLI.
- Kernel can submit, validate, accept, list, mark stale, and detect conflicts for Claims.
- Kernel can expire Claims, supersede Claims, and produce a health check that summarizes stale, expired, disputed, and superseded Claims.
- Claim evidence is mandatory and checked by `pks health`.
- Domain-level `claim_policy.yaml` is loaded and used by ReviewStrategy and stale calculation.
- TasteAndStyle is implemented as Claims.
- `pks new` creates a Capsule from explicit form-style fields.
- Project tracking supports Git Diff plus Evidence integrity checks.
- Context Pack excludes candidate, stale, disputed, expired, and superseded Claims.
- `PKS.md` can be generated but is never read as source of truth.
- CLI commands call Kernel APIs instead of mutating storage directly.
- Tests cover schema validation, Capsule storage, Kernel workflows, Claim conflict detection, tracking, and projection behavior.

---

# 中文版

## 目的

P0 要构建第一版可用的 PKS Kernel。Kernel 是控制层，负责同时管理 **Claim** 和 **Capsule**。Context Pack、`PKS.md`、CLI 输出，以及未来的 MCP/Web UI 视图，都是 Kernel 所管理状态的投影，不是事实源。

P0 的目标不是做完整个人知识库应用，而是先把核心知识状态模型做硬、做稳，让它不容易被污染，并且后续容易扩展。

权威来源：[`docs/core-design/pks_product_plan_v2.md`](../core-design/pks_product_plan_v2.md)

## 1. Claim 数据结构设计

Claim 是长期知识的原子单位。PKS 不能把长期知识存成松散段落，因为段落很难被精确验证、过期、替代或争议化。Claim 必须足够小，能被检查；也必须足够结构化，能支持冲突检测和查询。

P0 应该先把 Claim schema 稳住，再做更复杂的工作流。

核心字段：

- `claim_id`：稳定标识符。
- `subject`、`predicate`、`object`：语义三元组，用于冲突检测和查询。
- `qualifier`：可选的适用范围、前提条件和时间限定。
- `content`：人类可读的自然语言主张，可生成也可手写。
- `type`：`factual`、`inference`、`preference`、`constraint`。
- `domain`：`content`、`dev`、`research`。
- `tags`：轻量分组。
- `evidence`：强制证据列表。
- `status`：生命周期状态。
- `confidence`：`0.0` 到 `1.0` 的置信度。
- `created_at`、`created_by`、`valid_from`、`valid_until`、`last_verified`：来源与生命周期元信息。
- `supersedes`、`superseded_by`：替代关系。
- `project`：所属项目或胶囊 id。

Evidence 字段：

- `source_ref`：文件、手工来源、URL、journal 引用或其他来源定位。
- `relation`：`supports`、`weak_supports`、`contradicts`、`supersedes`。
- `excerpt`：用于完整性检查的原文摘录。

设计规则：

- 没有 evidence 的 Claim 是非法的。
- `(subject, predicate)` 是冲突检测 key。
- 相同 `(subject, predicate)` 但不同 `object` 是潜在冲突，除非明确建模为不同 scope 下的互补主张。
- `supersedes` 必须指向 `(subject, predicate)` 相同的 Claim。
- TasteAndStyle 使用普通 `Claim(type=preference)` 表示，不单独设计偏好文件格式。
- `stale` 是计算属性，不是 `ClaimStatus`。一条 accepted Claim 可以变 stale，但它仍然是 accepted。`pks health` 和 Context Pack 生成时根据 `last_verified`、领域级 `stale_after_days` 和 evidence 完整性检查结果计算 stale。

## 2. Capsule 类设计

Capsule 是项目知识状态容器。它不替代项目文件夹，而是记录项目当前状态、边界、Claims、journal 和领域特定模块。

Capsule 继承体系遵循 v2：

```text
BaseCapsule
├── ContentCapsule + TasteAndStyle
│   ├── ArticleCapsule
│   ├── VideoCapsule
│   └── GameCapsule
├── DevCapsule + TasteAndStyle
│   ├── SoftwareCapsule
│   └── PluginCapsule
└── ResearchCapsule + TasteAndStyle
    ├── DisciplineCapsule
    └── ModelCapsule
```

BaseCapsule 最小结构：

```text
project.yaml
PKS_PROJECT.md
claims/
journal.md
```

`project.yaml` 负责机器可读元信息，包括项目路径、仓库地址和 `tracking:` 配置。

领域扩展：

- ContentCapsule：`outline.md`、`facts.md`
- DevCapsule：`architecture.md`、`tasks.md`
- ResearchCapsule：`terminology.md`、`hypotheses.md`

存储原则：

- PKS 数据存放在项目文件夹之外，位于 PKS home。
- 项目文件夹可以接收生成的 `PKS.md` 投影。
- 不持久化 `context.md`。
- 领域级 TasteAndStyle Claims 存放在 domain 区域，并注入对应领域项目的 Context Pack。

第一版 `pks new` 应该是填表式命令：字段明确、输出可预期、容易测试。它不负责理解用户；人类或 Agent 先完成思考，再用准确参数调用 `pks new`。

## 3. Kernel 各功能模块设计

P0 Kernel 通过明确模块管理 Capsule 和 Claim 状态。CLI 只是适配层。

建议模块：

- `ProjectRegistry`：注册、创建、读取、更新、列出、解析项目 Capsule 及其领域模块。
- `ClaimEngine`：以 YAML 长期资产形式读写 Claims，校验 Claim、检测冲突、校验替代关系、过滤可进入 context 的 Claims、标记生命周期变化。`ClaimStore` 实现先作为该模块内部细节，除非后续证明它需要独立暴露。
- `ReviewStrategy`：P0 的最小接受/人工审核/拒绝规则。它读取领域级 `claim_policy.yaml`，用于应用 `auto_accept_threshold`、人工审核要求和生命周期策略。
- `ProjectTracker`：实现 v2 的 A + C 跟踪，即 Git Diff 加 Evidence 完整性检查。
- `ContextEngine`：基于 Capsule 状态和 accepted 且非 stale 的 Claims 生成 Context Pack。
- `ProjectionEngine`：生成项目文件夹中的 `PKS.md`。
- `AuditLog`：用最小追加式日志记录重要状态变化。
- `SnapshotManager`：在适合的地方复用 Git 做快照。

SQLite 是索引查询基础设施，不是独立 Kernel 模块。当 Claim 或 tracking 查询需要索引访问时再引入。

Kernel 门面应暴露这些用例方法：

- `create_capsule`
- `load_capsule`
- `list_capsules`
- `submit_claim`
- `accept_claim`
- `expire_claim`
- `supersede_claim`
- `mark_claim_stale`
- `mark_claim_disputed`
- `list_claims`
- `check_evidence`
- `health_check`
- `sync_project`
- `generate_pks_new_params`
- `render_context`
- `render_projection`

## 4. 注意事项

- v2 是主线，不要发明与 v2 冲突的行为。
- 设计细节不清楚时，停下来问，不要自行补产品策略。
- PKS 要跟踪项目文件夹，但不能接管项目文件夹。
- P0 项目跟踪采用 A + C：Git Diff 做主动跟踪，Evidence 完整性检查做被动兜底。
- 非 Git 项目退化为 Evidence 完整性检查。
- Agent 对长期状态的写入必须经过 candidate/review 路径，即使 P0 只实现最小版本。
- 测试应先覆盖 Kernel 行为，再覆盖 CLI 行为。
- 当前实现目录应初始化为 Git 仓库。

## 5. 实现步骤

1. 将当前实现目录初始化为 Git 仓库，review 后提交当前基线。
2. 围绕 Claim、Evidence、Qualifier、Capsule、ProjectMetadata、TrackingConfig、DomainPolicy、TasteAndStyle Claim 重构核心 schema。
3. 实现 PKS home 和长期 Capsule 存储布局。
4. 实现 Kernel 门面和模块边界。
5. 实现 ClaimEngine，内部包含 YAML-backed 存储逻辑。
6. 实现填表式 `pks new`。
7. 实现 Context Pack 和 `PKS.md` 投影生成，让核心闭环先跑通：创建 Capsule、添加/接受 Claim、生成 context。
8. 添加最小 Claim CLI 命令：add、accept、list、health。
9. 实现 ProjectTracker：Git Diff 加 Evidence 完整性检查。
10. 在 P0 状态变化需要可追溯的地方添加 audit/logging 和 snapshot hook。
11. 当 Claim 或 tracking 查询需要索引访问时，引入 SQLite-backed index。
12. 跑完整验证；只有行为真实可用后再更新 README。

## 6. 验收标准

- 当前实现目录已经是 Git 软件项目。
- 核心 schema 清楚表达 Claim、Capsule、Domain policy 和 tracking 概念。
- Kernel 不依赖 CLI 就能创建、读取和列出 Capsules。
- Kernel 能提交、校验、接受、列出、标记 stale，并检测 Claim 冲突。
- Kernel 能显式过期 Claim、替代 Claim，并生成包含 stale、expired、disputed、superseded 统计的健康检查。
- Claim evidence 是强制字段，并由 `pks health` 检查。
- 领域级 `claim_policy.yaml` 会被加载，并用于 ReviewStrategy 和 stale 计算。
- TasteAndStyle 以 Claim 形式实现。
- `pks new` 能通过显式填表字段创建 Capsule。
- 项目跟踪支持 Git Diff 与 Evidence 完整性检查。
- Context Pack 排除 candidate、stale、disputed、expired、superseded Claims。
- `PKS.md` 可以生成，但永远不会被当作事实源读取。
- CLI 命令调用 Kernel API，而不是直接修改存储文件。
- 测试覆盖 schema 校验、Capsule 存储、Kernel 工作流、Claim 冲突检测、项目跟踪和投影行为。
