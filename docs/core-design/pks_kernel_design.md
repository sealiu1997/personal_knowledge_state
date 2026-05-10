# PKS Kernel 设计

状态：P1 设计优化，2026-05-10。

## 定位

Kernel 是 PKS 的控制层入口。CLI、未来 MCP 和 Web UI 都只能调用 Kernel 用例方法，不直接读写长期状态文件。

Kernel 负责协调 Capsule、Claim、审核策略、项目跟踪、投影生成和审计 Claim。它不负责理解用户意图，也不接管项目文件夹。

Kernel 的长期状态写入对象只有 Claim 和 Capsule 运行时元数据。Markdown 是投影输出；投影内容和规则的修改必须通过 Kernel 接口。

## 模块结构

```text
src/pks/kernel/
├── facade.py              # Kernel 用例入口
├── capsule/               # Capsule 注册、布局、领域目录、继承映射
├── claim/                 # Claim 生命周期、YAML store、min_support 校验
├── candidate/             # Candidate Queue（P1 新增）
├── review/                # 领域策略驱动的审核判断 + ReviewEngine
├── tracking/              # evidence 完整性与 Git diff 跟踪
├── render/                # ProjectionEngine：Claim 集合投影
├── snapshot/              # 显式 PKS home Git 快照
├── audit/                 # Audit Claim 生成（P1 迁移为 Claim）
└── storage/               # YAML 读写基础设施
```

## 对外用例

`Kernel` 暴露稳定用例方法：

**Capsule 管理：**
- `create_capsule(project: ProjectMetadata)` — 创建 Capsule，生成初始 Claims 和投影
- `load_capsule(project_id)` — 读取 project.yaml
- `update_capsule(project_id, **updates)` — 更新运行时注册字段
- `resolve_capsule(project_id)` — 返回 ProjectMetadata 与 Capsule 路径
- `list_capsules()` — 列出所有 Capsule
- `generate_pks_new_params(**kwargs)` — 校验 pks new 参数，不做语义推断

**Claim 生命周期：**
- `submit_claim(project_id, claim)` — 提交 Claim（P0 兼容路径）
- `load_claim(project_id, claim_id)` — 读取单条 Claim
- `accept_claim(project_id, claim_id)` — 接受 Claim
- `expire_claim(project_id, claim_id)` — 过期 Claim
- `supersede_claim(project_id, old_claim_id, new_claim)` — 替代 Claim
- `mark_claim_stale(project_id, claim_id)` — 标记 stale 检查结果
- `mark_claim_disputed(project_id, claim_id)` — 标记争议
- `list_claims(project_id, **filters)` — 列出 Claims（P1 支持筛选）

**Candidate 与 Review（P1 新增）：**
- `submit_candidate(project_id, claim)` — 提交候选 Claim
- `list_candidates(project_id)` — 列出候选
- `load_candidate(project_id, candidate_id)` — 读取候选
- `delete_candidate(project_id, candidate_id)` — 删除候选
- `review_candidate(project_id, candidate_id)` — 获取审核建议
- `accept_candidate(project_id, candidate_id)` — 接受候选
- `reject_candidate(project_id, candidate_id)` — 拒绝候选

**健康与跟踪：**
- `check_evidence(project_id)` — 检查 evidence 完整性
- `health_check(project_id)` — 健康检查
- `sync_project(project_id)` — Git diff 同步

**投影：**
- `render_context(project_id)` — 返回动态 PKS.md 字符串
- `render_projection(project_id, projection_id?)` — 生成投影文件
- `list_projections(project_id)` — 列出可用投影
- `create_projection_spec(project_id, spec)` — 创建自定义投影规则
- `update_projection_spec(project_id, projection_id, changes)` — 修改投影规则
- `submit_projection_claim(project_id, projection_id, claim_draft)` — 通过投影提交新 Claim
- `patch_projection_claim(project_id, projection_id, claim_id, changes)` — 通过投影修改 Claim

**快照：**
- `create_snapshot(message)` — 创建 PKS home 快照
- `list_snapshots()` — 列出快照

## 调用关系

```text
CLI / MCP / Web UI
        ↓
Kernel facade
        ↓
ProjectRegistry ── project.yaml / domain policy / capsule_type → ProjectionSpec 映射
ClaimEngine     ── ClaimStore + min_support 校验
CandidateQueue  ── CandidateStore（P1）
ReviewEngine    ── ReviewStrategy + ClaimEngine + AuditClaimFactory（P1）
ReviewStrategy  ── claim_policy.yaml（含 min_support）
ProjectTracker  ── project folder / Git / evidence source
ProjectionEngine── ProjectMetadata + Claims + ProjectionSpec
AuditClaimFactory── type=inference Audit Claims（P1）
SnapshotManager ── PKS home Git repo
```

模块之间保持单向依赖：
- CLI 依赖 Kernel；Kernel 不依赖 CLI。
- Render 只接收数据模型和 ProjectionSpec，不读存储。
- ClaimEngine 负责 min_support 校验；ReviewStrategy 负责基于领域策略给出审核建议。
- ProjectTracker 不修改 Claim 状态，只返回 evidence issue 和 diff 结果。
- SnapshotManager 只在显式调用时提交 PKS home；普通状态变更只写 Audit Claim。
- Projection edit API 只能生成 Claim operation draft 或 ProjectionSpec 变更，不直接写长期状态。

## Claim 校验边界

Kernel 负责两层校验：

**结构校验（ClaimEngine）：**
- `min_support` 规则：evidence 数量、supporting_claims 数量、总支撑数。
- 类型层级：`allowed_support_types` 检查。
- 冲突检测：`(subject, predicate)` 冲突 key。
- `supersedes` 一致性：必须指向相同 `(subject, predicate)` 的旧 Claim。

**策略校验（ReviewStrategy）：**
- 基于领域 `claim_policy.yaml` 给出审核建议。
- confidence 阈值判断。
- 人工审核类型判断。
- 冲突处理建议。

两层校验的分工：ClaimEngine 负责"这条 Claim 结构上是否合法"，ReviewStrategy 负责"这条 Claim 应该如何审核"。

## 投影边界

`PKS.md` 就是 Content Pack：

- `render_context` 返回动态 PKS.md 字符串。
- `render_projection` 把同一内容写入项目根 `PKS.md`。
- 两者调用同一套 ProjectionEngine，使用同一套 ProjectionSpec。

Capsule 内的 `PKS_PROJECT.md`、`journal.md` 和领域 Markdown 也必须由 ProjectionEngine 生成。人或 Agent 不直接编辑 Markdown 文件，而是通过 Kernel 的投影接口修改投影内容或规则。

投影内容编辑流程：

```text
submit_projection_claim / patch_projection_claim
  ↓ Kernel
min_support 校验
  ↓ 通过
Candidate Claim / Claim patch
  ↓ review（语素变更）或直接更新（非语素变更）
accepted Claim changes
  ↓ render_projection
updated Markdown
```

投影规则编辑流程：

```text
create_projection_spec / update_projection_spec
  ↓ Kernel
ProjectionSpec validation
  ↓
saved ProjectionSpec
  ↓ render_projection
updated Markdown
```

## Audit 边界

审计记录是 `type=inference` 的 Claim，由 Kernel 自动生成：

- review accept / reject
- claim expire / dispute / supersede
- projection edit accepted / rejected
- snapshot create
- project sync

Audit Claim 不保存 rejected candidate 正文，只保存操作事实和最小 evidence。P0 的 `audit.log` 是过渡实现，P1 后以 Audit Claim 为准。

## CLI 适配

P0 CLI 只调用 Kernel：
- `pks project sync <project_id>`
- `pks claim expire <project_id> <claim_id>`
- `pks claim dispute <project_id> <claim_id>`
- `pks claim supersede <project_id> <old_claim_id> ...`
- `pks snapshot create --message "..."`
- `pks snapshot list`

P1 新增：
- `pks review list/show/accept/reject <project_id> [candidate_id]`
- `pks claim list --status/--type/--domain/--tag/--subject`
- `pks policy show/validate <domain>`

## 健康检查

`health_check` 统计：
- accepted、candidate、disputed、expired、superseded
- computed stale
- evidence issue
- min_support violation（P1 新增）

`stale` 不是 `ClaimStatus`，由领域 `claim_policy.yaml`、`last_verified` 和 evidence 完整性动态计算。

## 当前边界

已实现（P0）：
- YAML-backed Capsule/Claim 存储。
- 领域默认 `claim_policy.yaml`。
- TasteAndStyle Claim 注入 PKS.md。
- Git diff watched paths 同步接口。
- append-only audit log（P0 过渡实现）。
- 显式 SnapshotManager，必要时初始化 PKS home Git repo。

P1 待补齐：
- `min_support` 校验下沉到 ClaimEngine。
- Candidate Queue 与 ReviewEngine。
- 统一 ProjectionEngine，使所有 Markdown 都从 Claim 集合生成。
- 投影内容/规则编辑接口。
- Audit Claim 替代独立 audit log。
- `project.yaml` 字段迁移为 Claims。
- `capsule_type` → 默认 ProjectionSpec 映射。

暂缓：
- SQLite 索引。
- MCP、Web UI。
- 权限策略。
