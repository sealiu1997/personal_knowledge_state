# PKS Kernel 设计

状态：P0 当前实现同步，2026-05-09。

## 定位

Kernel 是 PKS 的控制层入口。CLI、未来 MCP 和 Web UI 都只能调用 Kernel 用例方法，不直接读写长期状态文件。

Kernel 负责协调 Capsule、Claim、审核策略、项目跟踪、上下文生成、投影生成和审计日志。它不负责理解用户意图，也不接管项目文件夹。

## 模块结构

```text
src/pks/kernel/
├── facade.py              # Kernel 用例入口
├── capsule/               # Capsule 注册、布局、领域目录
├── claim/                 # Claim 生命周期与 YAML store
├── review/                # 领域策略驱动的审核判断
├── tracking/              # evidence 完整性与 Git diff 跟踪
├── render/                # Context Pack 与 PKS.md 投影
├── audit/                 # append-only audit log
└── storage/               # YAML 读写基础设施
```

## 对外用例

`Kernel` 暴露稳定用例方法：
- Capsule：`create_capsule`、`load_capsule`、`list_capsules`
- Claim：`submit_claim`、`accept_claim`、`expire_claim`、`supersede_claim`、`mark_claim_disputed`、`list_claims`
- 健康与跟踪：`check_evidence`、`health_check`、`sync_project`
- 输出：`render_context`、`render_projection`

`generate_pks_new_params` 仅做显式字段校验，不做语义推断。

## 调用关系

```text
CLI / future adapters
        ↓
Kernel facade
        ↓
ProjectRegistry ── project.yaml / domain policy / TasteAndStyle
ClaimEngine     ── ClaimStore / audit.log
ReviewStrategy  ── claim_policy.yaml
ProjectTracker  ── project folder / Git / evidence source
Render engines  ── ProjectMetadata + accepted non-stale Claims
```

模块之间保持单向依赖：
- CLI 依赖 Kernel；Kernel 不依赖 CLI。
- Render 只接收数据模型，不读存储。
- ClaimEngine 不读取领域策略；审核由 Kernel 调 ReviewStrategy。
- ProjectTracker 不修改 Claim 状态，只返回 evidence issue 和 diff 结果。
- `PKS.md` 是输出投影，不参与 Kernel 输入。

## 健康检查

`health_check` 统计：
- accepted、candidate、disputed、expired、superseded
- computed stale
- evidence issue

`stale` 不是 `ClaimStatus`，由领域 `claim_policy.yaml`、`last_verified` 和 evidence 完整性动态计算。

## 当前边界

已实现：
- YAML-backed Capsule/Claim 存储。
- 领域默认 `claim_policy.yaml`。
- TasteAndStyle Claim 注入 Context Pack 和 `PKS.md`。
- Git diff watched paths 同步接口。
- append-only audit log。

暂缓：
- SQLite 索引。
- MCP、Web UI。
- 权限策略与 Candidate Queue 独立模块。
