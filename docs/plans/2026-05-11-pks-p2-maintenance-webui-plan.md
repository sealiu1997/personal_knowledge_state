# PKS P2 Implementation Plan: Auto-Maintenance + Minimal Web UI

> English version first. 中文版在后。The Chinese version is the primary review surface for product and architecture decisions.

---

# English Version

## Purpose

P2 builds on the P1 Claim review loop to add **automated knowledge maintenance** and a **minimal Web UI for Claim review**. It also resolves P1 code debt to keep the codebase clean as complexity grows.

P1 delivered the candidate/review/projection discipline. P2 should make the system self-maintaining (stale detection, expiry scanning, maintenance tasks) and give humans a better review surface than raw CLI.

Authoritative sources:

- [`docs/core-design/pks_product_plan_v2.md`](../core-design/pks_product_plan_v2.md)
- [`docs/core-design/pks_kernel_design.md`](../core-design/pks_kernel_design.md)
- [`docs/core-design/pks_claim_design.md`](../core-design/pks_claim_design.md)
- [`docs/core-design/pks_capsule_design.md`](../core-design/pks_capsule_design.md)
- [`docs/core-design/pks_projection_design.md`](../core-design/pks_projection_design.md)

## 1. P2 Scope

P2 focuses on **automated maintenance and human review experience**:

- P1 code debt resolution (dead code, module splitting, facade slimming)
- Automated stale scanning and expiry enforcement
- Evidence integrity re-check as maintenance task
- `pks maintain` CLI
- Minimal Web UI: Claim review workbench + project dashboard
- `pks serve` CLI

P2 does not include:

- MCP Server
- Policy Engine for file permissions
- Task Contract Engine
- Auto-merge of candidates
- Mobile, multi-user, complex knowledge graph
- Scheduled/cron maintenance (P2 only provides CLI trigger)

Those remain future phases.

## 2. Decisions

- Web UI is a thin adapter over Kernel. No business logic in the web layer.
- Web UI uses FastAPI + Jinja2 + htmx. No frontend framework.
- Web UI is localhost-only, no authentication needed.
- Maintenance tasks are idempotent. Running twice produces the same result.
- Expiry enforcement writes Audit Claims. Stale scan does not (stale is computed, not persisted).
- ProjectRegistry split must not change any public Kernel API.
- No new dependencies beyond FastAPI, uvicorn, Jinja2. htmx is vendored as a static JS file.

## 3. Pre-requisite: P1 Code Debt Resolution (Step 0)

Before adding P2 features, resolve structural issues from P1.

### 3.1 Remove ContextEngine

`ContextEngine` (`kernel/render/context.py`) is dead code. Kernel facade exclusively uses `ProjectionEngine`.

- Delete `src/pks/kernel/render/context.py`
- Remove import from `src/pks/kernel/render/__init__.py`
- Remove `self.context_engine` from `Kernel.__init__`

### 3.2 Remove ClaimEngine.submit_claim

P0 compatibility path no longer called by facade (facade uses `submit_candidate`).

- Remove `ClaimEngine.submit_claim` method

### 3.3 Split ProjectRegistry

Current `ProjectRegistry` (~300 lines) handles too many concerns. Split into focused modules:

```text
kernel/capsule/
├── registry.py          # Capsule CRUD only (create, load, update, list, resolve)
├── policy.py            # DomainPolicy loading and validation
├── taste.py             # TasteAndStyle claim management (domain + type level)
├── projection_specs.py  # ProjectionSpec CRUD and default mapping
├── seeder.py            # Initial Claim seeding on capsule creation
├── id_generator.py      # Global Claim ID generation (config.yaml counter)
└── layout.py            # capsule_type → ProjectionSpec mapping (existing)
```

Each module: single responsibility, < 100 lines.

### 3.4 Slim Kernel Facade

After splitting ProjectRegistry, refactor facade to be a thin orchestrator:
1. Resolve capsule path
2. Delegate to appropriate module
3. Record audit
4. Trigger projection regeneration

Target: < 250 lines, no business logic in facade.

## 4. Automated Maintenance (Step 1)

### 4.1 Maintenance Tasks

| Task | Action | Audit |
|------|--------|-------|
| Stale scan | Check accepted Claims against `stale_after_days` | No (computed property) |
| Expiry enforcement | Claims with `valid_until < today` → `expired` | Yes (Audit Claim per expiry) |
| Evidence re-check | Run `check_evidence`; flag broken evidence | No (reported in health) |
| Projection refresh | Regenerate all projections after changes | No |

### 4.2 MaintenanceEngine

New module: `src/pks/kernel/maintenance/`

```python
class MaintenanceEngine:
    def run_all(self, project_id, today=None) -> MaintenanceReport
    def scan_stale(self, project_id, today=None) -> list[ClaimHealth]
    def enforce_expiry(self, project_id, today=None) -> list[Claim]
    def recheck_evidence(self, project_id) -> list[EvidenceIssue]
```

### 4.3 MaintenanceReport

```python
class MaintenanceReport(BaseModel):
    project_id: str
    stale_found: int = 0
    expired_enforced: int = 0
    evidence_issues_found: int = 0
    projections_refreshed: bool = False
    run_at: datetime
```

### 4.4 CLI

```bash
pks maintain <project_id>           # Run all maintenance tasks
pks maintain <project_id> --stale   # Only stale scan
pks maintain <project_id> --expiry  # Only expiry enforcement
pks maintain <project_id> --evidence # Only evidence re-check
pks maintain --all                  # Run for all projects
```

## 5. Minimal Web UI (Step 2)

### 5.1 Pages

| Page | URL | Function |
|------|-----|----------|
| Dashboard | `/` | Project list, health summary per project |
| Project detail | `/projects/{id}` | Claim stats, recent activity, health |
| Candidate review | `/projects/{id}/review` | Candidate list, one-click accept/reject |
| Candidate detail | `/projects/{id}/review/{cid}` | Full Claim, evidence, recommendation |
| Claim browser | `/projects/{id}/claims` | Filter/sort/search accepted Claims |
| Claim detail | `/projects/{id}/claims/{cid}` | Full Claim with evidence chain |

### 5.2 API Endpoints

```text
GET  /api/projects                              → list_capsules
GET  /api/projects/{id}                         → load_capsule + health_check
GET  /api/projects/{id}/candidates              → list_candidates
GET  /api/projects/{id}/candidates/{cid}        → load_candidate + review_candidate
POST /api/projects/{id}/candidates/{cid}/accept → accept_candidate
POST /api/projects/{id}/candidates/{cid}/reject → reject_candidate
GET  /api/projects/{id}/claims                  → list_claims (query params)
GET  /api/projects/{id}/claims/{cid}            → load_claim
POST /api/projects/{id}/maintain                → run maintenance
```

### 5.3 Module Structure

```text
src/pks/
├── kernel/          # Existing
├── cli.py           # Existing
└── web/
    ├── __init__.py
    ├── app.py       # FastAPI app factory
    ├── routes/
    │   ├── projects.py
    │   ├── candidates.py
    │   ├── claims.py
    │   └── maintenance.py
    ├── templates/   # Jinja2 HTML templates
    │   ├── base.html
    │   ├── dashboard.html
    │   ├── project.html
    │   ├── review.html
    │   ├── candidate.html
    │   ├── claims.html
    │   └── claim.html
    └── static/
        ├── style.css
        └── htmx.min.js
```

### 5.4 CLI

```bash
pks serve                     # Start on localhost:8420
pks serve --port 9000         # Custom port
pks serve --host 0.0.0.0     # Bind all interfaces
```

## 6. Implementation Order

Strict sequential order. Each step must pass tests before proceeding.

| Step | Task | Depends on | Deliverable |
|------|------|------------|-------------|
| 0.1 | Remove ContextEngine | — | Dead code removed |
| 0.2 | Remove ClaimEngine.submit_claim | — | Dead method removed |
| 0.3 | Split ProjectRegistry | 0.1, 0.2 | 6 focused modules |
| 0.4 | Slim Kernel facade | 0.3 | Facade < 250 lines |
| 0.5 | Full test suite + lint | 0.4 | All tests pass, no regressions |
| 1.1 | MaintenanceEngine module | 0.5 | Stale + expiry + evidence |
| 1.2 | MaintenanceReport model | 1.1 | Pydantic model |
| 1.3 | `pks maintain` CLI | 1.2 | CLI with flags |
| 1.4 | Maintenance tests | 1.3 | Unit + integration |
| 2.1 | FastAPI app skeleton | 0.5 | `pks serve` starts |
| 2.2 | API endpoints | 2.1 | All `/api/` routes |
| 2.3 | HTML templates + htmx | 2.2 | Dashboard + review pages |
| 2.4 | Web UI tests | 2.3 | API endpoint tests |
| 3.0 | Full verification | 1.4, 2.4 | All tests pass |

Steps 1.x and 2.x can be developed in parallel after Step 0.x completes.

## 7. Acceptance Criteria

### Code cleanup (Step 0)
- ContextEngine deleted, no dead code in render module.
- ClaimEngine has no unused methods.
- ProjectRegistry split into ≤ 6 focused modules, each < 100 lines.
- Kernel facade < 250 lines, no business logic.
- All existing tests pass unchanged.

### Maintenance (Step 1)
- `pks maintain <project_id>` runs stale scan + expiry enforcement + evidence re-check.
- Expired Claims get `status=expired` + Audit Claim.
- Stale Claims flagged in health report (not status change).
- Evidence issues reported.
- Projections refreshed after maintenance.
- `pks maintain --all` runs for all projects.
- Tests cover each maintenance task independently.

### Web UI (Step 2)
- `pks serve` starts local FastAPI server.
- Dashboard shows project list with health indicators.
- Review page lists candidates with one-click accept/reject.
- Candidate detail shows full Claim, evidence, recommendation.
- Claim browser supports filter by status/type/domain/tag.
- All Web UI actions delegate to Kernel.
- API endpoints have test coverage.

## 8. Testing Plan

### Unit tests
- MaintenanceEngine: stale detection, expiry enforcement, evidence re-check
- Each split module from ProjectRegistry

### Integration tests
- `pks maintain` CLI end-to-end
- Web API endpoints (FastAPI TestClient)
- Full workflow: create → add claims → maintain → verify

### Verification

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
```

## 9. Dependencies

```toml
# pyproject.toml additions
[project.optional-dependencies]
web = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "jinja2>=3.1",
]
```

htmx vendored as static file, not a Python dependency.

## 10. Deferred

- Scheduled maintenance (cron): P2 only provides CLI trigger.
- Batch review in Web UI: P2 does one-at-a-time.
- Claim editing in Web UI: P2 is read + accept/reject only.
- Authentication: localhost-only, no auth.

---

# 中文版

## 目的

P2 在 P1 的 Claim 审核闭环之上，增加**自动化知识维护**和**最小 Web UI 审核界面**。同时解决 P1 遗留的代码债务，保持代码库在复杂度增长时的整洁。

P1 交付了 candidate/review/projection 纪律。P2 要让系统能自我维护（stale 检测、过期扫描、维护任务），并给人类一个比 CLI 更好的审核界面。

权威来源：

- [`docs/core-design/pks_product_plan_v2.md`](../core-design/pks_product_plan_v2.md)
- [`docs/core-design/pks_kernel_design.md`](../core-design/pks_kernel_design.md)
- [`docs/core-design/pks_claim_design.md`](../core-design/pks_claim_design.md)
- [`docs/core-design/pks_capsule_design.md`](../core-design/pks_capsule_design.md)
- [`docs/core-design/pks_projection_design.md`](../core-design/pks_projection_design.md)

## 1. P2 范围

P2 聚焦**自动维护和人类审核体验**：

- P1 代码债务清理（死代码、模块拆分、facade 瘦身）
- 自动 stale 扫描和过期强制执行
- Evidence 完整性重检查
- `pks maintain` CLI
- 最小 Web UI：Claim 审核工作台 + 项目仪表盘
- `pks serve` CLI

P2 不做：MCP Server、文件权限 Policy Engine、Task Contract Engine、候选自动合并、移动端、多用户、复杂知识图谱、定时维护（P2 只提供 CLI 触发）。

## 2. 已定决策

- Web UI 是 Kernel 的薄适配层，不含业务逻辑。
- Web UI 使用 FastAPI + Jinja2 + htmx，不引入前端框架。
- Web UI 仅本地运行，不需要认证。
- 维护任务幂等，重复执行结果一致。
- 过期强制执行写 Audit Claim；stale 扫描不写（stale 是计算属性）。
- ProjectRegistry 拆分不改变任何公开 Kernel API。
- 不引入 FastAPI/uvicorn/Jinja2 之外的新依赖。htmx 作为静态文件 vendor。

## 3. 前置：P1 代码债务清理（Step 0）

在添加 P2 功能之前，先解决 P1 的结构问题。

### 3.1 删除 ContextEngine

`ContextEngine`（`kernel/render/context.py`）是死代码。Kernel facade 只使用 `ProjectionEngine`。

- 删除 `src/pks/kernel/render/context.py`
- 从 `src/pks/kernel/render/__init__.py` 移除导入
- 从 `Kernel.__init__` 移除 `self.context_engine`

### 3.2 删除 ClaimEngine.submit_claim

P0 兼容路径，facade 已不再调用（facade 使用 `submit_candidate`）。

- 删除 `ClaimEngine.submit_claim` 方法

### 3.3 拆分 ProjectRegistry

当前 ProjectRegistry（~300 行）职责过多。拆分为：

```text
kernel/capsule/
├── registry.py          # Capsule CRUD（create/load/update/list/resolve）
├── policy.py            # DomainPolicy 加载与校验
├── taste.py             # TasteAndStyle Claim 管理（领域级 + 类型级）
├── projection_specs.py  # ProjectionSpec CRUD 与默认映射
├── seeder.py            # 创建 Capsule 时的初始 Claim 播种
├── id_generator.py      # 全局 Claim ID 生成（config.yaml 计数器）
└── layout.py            # capsule_type → ProjectionSpec 映射（已有）
```

每个模块：单一职责，< 100 行。

### 3.4 瘦身 Kernel Facade

拆分 ProjectRegistry 后，重构 facade 为薄编排层：
1. 解析 capsule 路径
2. 委托给对应模块
3. 记录 audit
4. 触发投影重新生成

目标：< 250 行，facade 内无业务逻辑。

## 4. 自动维护（Step 1）

### 4.1 维护任务

| 任务 | 动作 | 是否写 Audit |
|------|------|-------------|
| Stale 扫描 | 检查 accepted Claims 的 `stale_after_days` | 否（计算属性） |
| 过期强制执行 | `valid_until < today` → `expired` | 是（每条过期写 Audit Claim） |
| Evidence 重检查 | 运行 `check_evidence`，标记 broken evidence | 否（报告在 health 中） |
| 投影刷新 | 维护后重新生成所有投影 | 否 |

### 4.2 MaintenanceEngine

新模块：`src/pks/kernel/maintenance/`

```python
class MaintenanceEngine:
    def run_all(self, project_id, today=None) -> MaintenanceReport
    def scan_stale(self, project_id, today=None) -> list[ClaimHealth]
    def enforce_expiry(self, project_id, today=None) -> list[Claim]
    def recheck_evidence(self, project_id) -> list[EvidenceIssue]
```

### 4.3 MaintenanceReport

```python
class MaintenanceReport(BaseModel):
    project_id: str
    stale_found: int = 0
    expired_enforced: int = 0
    evidence_issues_found: int = 0
    projections_refreshed: bool = False
    run_at: datetime
```

### 4.4 CLI

```bash
pks maintain <project_id>           # 运行所有维护任务
pks maintain <project_id> --stale   # 仅 stale 扫描
pks maintain <project_id> --expiry  # 仅过期强制执行
pks maintain <project_id> --evidence # 仅 evidence 重检查
pks maintain --all                  # 对所有项目运行
```

## 5. 最小 Web UI（Step 2）

### 5.1 页面

| 页面 | URL | 功能 |
|------|-----|------|
| 仪表盘 | `/` | 项目列表，每个项目的健康摘要 |
| 项目详情 | `/projects/{id}` | Claim 统计、最近活动、健康指标 |
| 候选审核 | `/projects/{id}/review` | 候选列表，一键 accept/reject |
| 候选详情 | `/projects/{id}/review/{cid}` | 完整 Claim、evidence、审核建议 |
| Claim 浏览 | `/projects/{id}/claims` | 按 status/type/domain/tag 筛选排序 |
| Claim 详情 | `/projects/{id}/claims/{cid}` | 完整 Claim 与 evidence 链 |

### 5.2 API 端点

```text
GET  /api/projects                              → list_capsules
GET  /api/projects/{id}                         → load_capsule + health_check
GET  /api/projects/{id}/candidates              → list_candidates
GET  /api/projects/{id}/candidates/{cid}        → load_candidate + review_candidate
POST /api/projects/{id}/candidates/{cid}/accept → accept_candidate
POST /api/projects/{id}/candidates/{cid}/reject → reject_candidate
GET  /api/projects/{id}/claims                  → list_claims（支持查询参数）
GET  /api/projects/{id}/claims/{cid}            → load_claim
POST /api/projects/{id}/maintain                → 运行维护
```

### 5.3 模块结构

```text
src/pks/
├── kernel/          # 已有
├── cli.py           # 已有
└── web/
    ├── __init__.py
    ├── app.py       # FastAPI app 工厂
    ├── routes/
    │   ├── projects.py
    │   ├── candidates.py
    │   ├── claims.py
    │   └── maintenance.py
    ├── templates/   # Jinja2 HTML 模板
    │   ├── base.html
    │   ├── dashboard.html
    │   ├── project.html
    │   ├── review.html
    │   ├── candidate.html
    │   ├── claims.html
    │   └── claim.html
    └── static/
        ├── style.css
        └── htmx.min.js
```

### 5.4 CLI

```bash
pks serve                     # 启动在 localhost:8420
pks serve --port 9000         # 自定义端口
pks serve --host 0.0.0.0     # 绑定所有接口（局域网访问）
```

## 6. 实施顺序

严格顺序执行。每步必须测试通过后再进入下一步。

| 步骤 | 任务 | 依赖 | 交付物 |
|------|------|------|--------|
| 0.1 | 删除 ContextEngine | — | 死代码移除 |
| 0.2 | 删除 ClaimEngine.submit_claim | — | 死方法移除 |
| 0.3 | 拆分 ProjectRegistry | 0.1, 0.2 | 6 个聚焦模块 |
| 0.4 | 瘦身 Kernel facade | 0.3 | Facade < 250 行 |
| 0.5 | 全量测试 + lint | 0.4 | 所有测试通过，无回归 |
| 1.1 | MaintenanceEngine 模块 | 0.5 | Stale + 过期 + evidence |
| 1.2 | MaintenanceReport model | 1.1 | Pydantic model |
| 1.3 | `pks maintain` CLI | 1.2 | CLI 命令 + flags |
| 1.4 | 维护测试 | 1.3 | 单元 + 集成测试 |
| 2.1 | FastAPI app 骨架 | 0.5 | `pks serve` 可启动 |
| 2.2 | API 端点 | 2.1 | 所有 `/api/` 路由 |
| 2.3 | HTML 模板 + htmx | 2.2 | 仪表盘 + 审核页面 |
| 2.4 | Web UI 测试 | 2.3 | API 端点测试 |
| 3.0 | 全量验证 | 1.4, 2.4 | 所有测试通过 |

Step 1.x（维护）和 Step 2.x（Web UI）可在 Step 0.x（债务清理）完成后并行开发。

## 7. 验收标准

### 代码清理（Step 0）
- ContextEngine 已删除，render 模块无死代码。
- ClaimEngine 无未使用方法。
- ProjectRegistry 拆分为 ≤ 6 个聚焦模块，每个 < 100 行。
- Kernel facade < 250 行，无业务逻辑。
- 所有现有测试不变地通过。

### 维护（Step 1）
- `pks maintain <project_id>` 运行 stale 扫描 + 过期强制执行 + evidence 重检查。
- 过期 Claims 获得 `status=expired` + Audit Claim。
- Stale Claims 在 health report 中标记（不改变 status）。
- Evidence issues 被报告。
- 维护后投影被刷新。
- `pks maintain --all` 对所有项目运行。
- 测试独立覆盖每个维护任务。

### Web UI（Step 2）
- `pks serve` 启动本地 FastAPI 服务器。
- 仪表盘展示项目列表和健康指标。
- 审核页面列出候选，支持一键 accept/reject。
- 候选详情展示完整 Claim、evidence、审核建议。
- Claim 浏览支持按 status/type/domain/tag 筛选。
- 所有 Web UI 操作委托给 Kernel（无直接存储访问）。
- API 端点有测试覆盖。

## 8. 测试计划

### 单元测试
- MaintenanceEngine：stale 检测、过期强制执行、evidence 重检查
- ProjectRegistry 拆分后的各模块

### 集成测试
- `pks maintain` CLI 端到端
- Web API 端点（FastAPI TestClient）
- 完整工作流：创建 → 添加 claims → 维护 → 验证状态

### 验证

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
```

## 9. 新增依赖

```toml
# pyproject.toml 新增
[project.optional-dependencies]
web = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "jinja2>=3.1",
]
```

htmx 作为静态文件 vendor，不是 Python 依赖。

## 10. 暂缓项

- 定时维护（cron）：P2 只提供 CLI 触发。
- Web UI 批量审核：P2 逐条操作。
- Web UI Claim 编辑：P2 只读 + accept/reject。
- 认证：仅本地运行，无需认证。
