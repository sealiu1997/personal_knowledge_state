# PKS Kernel 设计

状态：P2 实施后校准，2026-05-11。

## 定位

Kernel 是 PKS 的控制层入口。CLI、Web UI 和未来 MCP 都只能调用 Kernel 用例方法，不直接读写长期状态文件。

Kernel 负责协调 Capsule、Claim、审核策略、项目跟踪、投影生成、维护和审计。它不负责理解用户意图，也不接管项目文件夹。

Kernel 的长期状态写入对象只有 Claim 和 Capsule 运行时元数据。Markdown 是投影输出；投影内容和规则的修改必须通过 Kernel 接口。

## 模块结构

```text
src/pks/kernel/
├── facade.py              # Kernel 用例入口（薄编排层）
├── health.py              # HealthEngine：stale 计算、evidence 检查、健康报告
├── capsule/               # Capsule 注册与子模块
│   ├── registry.py        # Capsule CRUD（组合所有子模块）
│   ├── policy.py          # PolicyManager：领域策略加载与校验
│   ├── taste.py           # TasteManager：TasteAndStyle Claim 管理
│   ├── projection_specs.py # ProjectionSpecManager：ProjectionSpec CRUD
│   ├── seeder.py          # ProjectSeeder：创建 Capsule 时的初始 Claim 播种
│   ├── id_generator.py    # ClaimIdGenerator：全局 Claim ID 生成
│   └── layout.py          # capsule_type → 默认 ProjectionSpec 映射
├── claim/
│   ├── engine.py          # ClaimEngine：Claim 生命周期、min_support 校验、冲突检测
│   ├── workflow.py        # ClaimWorkflow：Claim 业务流程（submit/review/accept/reject）
│   └── store.py           # ClaimStore：YAML 持久化
├── candidate/
│   ├── queue.py           # CandidateQueue：候选提交/列出/删除
│   └── store.py           # CandidateStore：候选 YAML 存储
├── review/
│   ├── engine.py          # ReviewEngine：accept/reject 流程
│   └── strategy.py        # ReviewStrategy：可解释审核建议
├── render/
│   ├── projection.py      # ProjectionEngine：Claim 集合 → Markdown
│   └── service.py         # ProjectionService：投影编排（render/integrity/spec CRUD/edit API）
├── maintenance/
│   └── engine.py          # MaintenanceEngine：stale 扫描、过期强制执行、evidence 重检查
├── snapshot/
│   └── manager.py         # SnapshotManager：显式 PKS home Git 快照
├── tracking/
│   └── tracker.py         # ProjectTracker：evidence 完整性、Git diff 同步
├── audit/
│   └── factory.py         # AuditClaimFactory：事件写成 inference Claim
└── storage/
    └── yaml.py            # YAML 读写基础设施
```

## 架构原则

### 组合优于继承

`ProjectRegistry` 通过组合（composition）聚合子模块，每个子模块是独立类，构造函数显式声明依赖：

```text
ProjectRegistry
├── PolicyManager(domains_dir)
├── TasteManager(domains_dir)
├── ProjectionSpecManager(capsules_dir)
├── ClaimIdGenerator(home)
└── ProjectSeeder(capsules_dir, id_generator)
```

每个子模块可独立实例化和测试。

### Facade 编排模式

Kernel facade 是薄编排层，不含业务逻辑。每个方法的模式：

```text
1. 委托给对应模块执行业务操作
2. 刷新投影（如果状态发生了变更）
3. 返回结果
```

投影刷新统一由 facade 的 `_refresh_projections` 触发，业务模块（ClaimWorkflow、MaintenanceEngine）不知道投影的存在。

### 单向依赖

```text
CLI / Web UI
      ↓
Kernel facade
      ↓
┌─────────────────────────────────────────────────┐
│ ClaimWorkflow ─── ClaimEngine ─── ClaimStore    │
│ ProjectionService ─── ProjectionEngine          │
│ MaintenanceEngine ─── HealthEngine              │
│ HealthEngine ─── ProjectTracker                 │
│ All ←── ProjectRegistry（子模块组合）            │
└─────────────────────────────────────────────────┘
```

- CLI/Web UI 依赖 Kernel；Kernel 不依赖 CLI/Web UI。
- ClaimWorkflow 不知道 ProjectionService 的存在。
- MaintenanceEngine 不触发投影刷新（由 facade 在调用后统一刷新）。
- HealthEngine 自己构造 ClaimEngine 读取数据，不依赖 ClaimWorkflow。
- ProjectionService 通过 ClaimWorkflow 获取 Claims 列表。

## 对外用例

`Kernel` 暴露稳定用例方法：

**Capsule 管理：**
- `create_capsule(project)` — 创建 Capsule，播种初始 Claims，生成投影
- `load_capsule(project_id)` — 读取 project.yaml
- `update_capsule(project_id, **updates)` — 更新运行时注册字段
- `resolve_capsule(project_id)` — 返回 ProjectMetadata 与 Capsule 路径
- `list_capsules()` — 列出所有 Capsule

**Claim 生命周期：**
- `submit_candidate(project_id, claim)` — 提交候选 Claim
- `list_candidates(project_id)` — 列出候选
- `load_candidate(project_id, candidate_id)` — 读取候选
- `review_candidate(project_id, candidate_id)` — 获取审核建议
- `accept_candidate(project_id, candidate_id)` — 接受候选 + 刷新投影
- `reject_candidate(project_id, candidate_id)` — 拒绝候选 + 刷新投影
- `accept_claim(project_id, claim_id)` — 接受 Claim + 刷新投影
- `load_claim(project_id, claim_id)` — 读取单条 Claim
- `expire_claim(project_id, claim_id)` — 过期 Claim + 刷新投影
- `supersede_claim(project_id, old_claim_id, new_claim)` — 替代 Claim + 刷新投影
- `mark_claim_stale(project_id, claim_id)` — 标记 stale 检查结果
- `mark_claim_disputed(project_id, claim_id)` — 标记争议 + 刷新投影
- `list_claims(project_id, **filters)` — 列出 Claims（支持筛选）

**健康与维护：**
- `health_check(project_id)` — 健康检查
- `sync_project(project_id)` — Git diff 同步
- `maintenance.run(project_id, stale=, expiry=, evidence=)` — 运行维护任务 + 刷新投影

**投影：**
- `render_context(project_id)` — 返回动态 PKS.md 字符串
- `render_projection(project_id, projection_id?, write?)` — 生成投影
- `check_projection_integrity(project_id)` — 检测外部修改
- `list_projections(project_id)` — 列出可用投影
- `create_projection_spec(project_id, spec)` — 创建自定义投影规则
- `update_projection_spec(project_id, projection_id, changes)` — 修改投影规则
- `delete_projection_spec(project_id, projection_id)` — 删除自定义投影
- `submit_projection_claim(project_id, projection_id, claim_draft)` — 通过投影提交新 Claim
- `patch_projection_claim(project_id, projection_id, claim_id, changes)` — 通过投影修改 Claim

**快照：**
- `create_snapshot(message)` — 创建 PKS home 快照
- `list_snapshots()` — 列出快照

**策略：**
- `load_policy(domain)` — 加载领域策略
- `validate_policy(domain)` — 校验领域策略

**TasteAndStyle：**
- `save_taste_claim(claim, capsule_type?)` — 保存 TasteAndStyle Claim

## Claim 校验边界

两层校验分工：

**结构校验（ClaimEngine）：**
- `min_support` 规则：evidence 数量、supporting_claims 数量、总支撑数
- 类型层级：`allowed_support_types` 检查
- 冲突检测：`(subject, predicate)` 冲突 key
- `supersedes` 一致性

**策略校验（ReviewStrategy）：**
- confidence 阈值判断
- 人工审核类型判断
- 冲突处理建议
- min_support 状态纳入决策

## 投影边界

`PKS.md` 是 Capsule 所有投影按继承顺序的聚合：

```text
PKS.md = BaseCapsule 投影 + 领域投影 + 自定义投影 + TasteAndStyle
```

`render_context` 返回字符串，`render_projection(write=True)` 写入文件。两者调用同一套 ProjectionEngine。

投影内容编辑流程：
- 语素变更（subject/predicate/object）→ 创建新 Candidate，走 review
- 非语素变更（content/tags/qualifier）→ 直接更新 + Audit Claim

## Audit 边界

审计记录是 `type=inference` 的 Claim，由 AuditClaimFactory 自动生成：

- review accept / reject
- claim expire / dispute / supersede
- projection edit / spec create / spec update / spec delete
- capsule create / update
- snapshot create
- project sync
- maintenance expiry

## 健康检查

`HealthEngine.health_check` 统计：
- accepted、candidate、disputed、expired、superseded
- computed stale（基于 `last_verified` + 领域 `stale_after_days` + evidence 完整性）
- min_support violations
- evidence issues

`stale` 不是 `ClaimStatus`，是动态计算属性。

## 维护引擎

`MaintenanceEngine` 提供三个独立维护任务：

| 任务 | 方法 | 写 Audit |
|------|------|----------|
| Stale 扫描 | `scan_stale` | 否（计算属性） |
| 过期强制执行 | `enforce_expiry` | 是 |
| Evidence 重检查 | `recheck_evidence` | 否（报告） |

维护后由 facade 统一刷新投影。

## 当前边界

已实现：
- 组合模式的 ProjectRegistry（PolicyManager、TasteManager、ProjectionSpecManager、ClaimIdGenerator、ProjectSeeder）
- ClaimWorkflow 无 callback，facade 编排 render
- HealthEngine 独立（只依赖 registry + tracker）
- MaintenanceEngine 独立（只依赖 registry + tracker）
- ProjectionService（render/integrity/spec CRUD/edit API）
- Web UI（FastAPI + Jinja2 + htmx，纯 Kernel 适配层）
- 全局 Claim ID 生成（`<type_code>-<sequence>`）

暂缓：
- SQLite 索引
- MCP Server
- 权限策略（Policy Engine）
- Task Contract
