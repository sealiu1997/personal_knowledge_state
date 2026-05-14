# PKS Maintenance 设计

状态：P2 实施后校准，2026-05-11。

## 定位

MaintenanceEngine 负责 Capsule 的自动化知识维护：检测过时的 Claim、强制执行过期、重新验证 Evidence 完整性。

维护是 PKS "知识会过期"原则的执行层。没有维护，Claim 会随时间积累而失去可信度，投影内容会包含过时信息。

## 维护任务

| 任务 | 方法 | 触发 | 动作 | 写 Audit |
|------|------|------|------|----------|
| Stale 扫描 | `scan_stale` | `pks maintain` / Web UI | 识别超过 `stale_after_days` 的 accepted Claims | 否（stale 是计算属性） |
| 过期强制执行 | `enforce_expiry` | `pks maintain` / Web UI | `valid_until < today` → `status=expired` | 是（每条过期写 Audit Claim） |
| Evidence 重检查 | `recheck_evidence` | `pks maintain` / Web UI | 检查文件存在性和 excerpt 匹配 | 否（报告在 health 中） |

维护后由 Kernel facade 统一刷新投影。

## 幂等性

所有维护任务幂等：
- `scan_stale`：只读操作，返回当前 stale 列表。
- `enforce_expiry`：已经是 expired 状态的 Claim 不会重复处理。
- `recheck_evidence`：只读操作，返回当前 evidence issues。

重复执行 `pks maintain` 不会产生副作用。

## 与 HealthEngine 的关系

```text
HealthEngine
├── health_check()      → 完整健康报告（stale + expired + evidence + min_support）
├── stale_claim_ids_for() → 用于投影过滤
├── is_stale()          → 单条 Claim stale 判断
└── check_evidence()    → evidence 完整性检查

MaintenanceEngine
├── scan_stale()        → 调用 HealthEngine.health_check()，过滤 stale
├── enforce_expiry()    → 自己遍历 Claims，调用 ClaimEngine.expire_claim()
└── recheck_evidence()  → 调用 HealthEngine.check_evidence()
```

MaintenanceEngine 依赖 HealthEngine 做检测，但自己负责执行动作（过期强制执行）和审计记录。

## 依赖关系

```text
MaintenanceEngine
├── ProjectRegistry（加载项目、策略）
├── ProjectTracker（evidence 检查）
├── HealthEngine（stale 计算、健康报告）
├── ClaimEngine（过期执行）
└── AuditClaimFactory（审计记录）
```

MaintenanceEngine 不依赖 ClaimWorkflow、ProjectionService 或 Kernel facade。它只做维护逻辑，投影刷新由 facade 在调用后统一处理。

## CLI

```bash
pks maintain <project_id>           # 运行所有维护任务
pks maintain <project_id> --stale   # 仅 stale 扫描
pks maintain <project_id> --expiry  # 仅过期强制执行
pks maintain <project_id> --evidence # 仅 evidence 重检查
pks maintain --all                  # 对所有项目运行
```

## Web UI

```text
POST /api/projects/{id}/maintain    # 运行维护（支持 stale/expiry/evidence 参数）
```

## MaintenanceReport

```python
class MaintenanceReport(BaseModel):
    project_id: str
    stale_found: int = 0
    expired_enforced: int = 0
    evidence_issues_found: int = 0
    projections_refreshed: bool = False
```

## 设计约束

- 维护不改变 stale 状态（stale 是计算属性，不是 ClaimStatus）。
- 过期强制执行只处理 `valid_until < today` 且当前 `status=accepted` 的 Claims。
- 维护不自动合并候选（auto_accept 仍然只是建议）。
- 维护不触发投影刷新（由 facade 在调用后统一处理）。

## 未来扩展

- **定时维护**：P2 只提供 CLI/Web 触发。后续可加 cron 或 daemon 模式。
- **维护报告持久化**：当前只返回 report，不持久化。后续可写入 Audit Claim 或独立日志。
- **智能维护**：基于 Claim 变更频率自动调整 `stale_after_days`。

## P3.2 计划：完整性级联验证

P3.2 将扩展维护引擎，增加两种检测：

### 支撑链断裂检测

当 Claim 的 `supporting_claims` 引用的 Claim 已被 superseded/expired/disputed 时，标记该 Claim 为"待重验证"。

### Evidence 源头变更级联

当 `sync_project` 检测到文件变更时，关联到引用该文件的 Claims，标记为"待重验证"。进一步通过 `supporting_claims` 向上级联传播——所有依赖被标记 Claim 的上层 Claim 也被标记。

### 设计要点

- `needs_reverification` 是计算标记（与 `stale` 同级），不是新的 ClaimStatus。
- 级联仅向上传播，在 `last_verified` 晚于触发事件的 Claim 处停止。
- 不自动 reject，人类或 Agent 通过 `verify_claim` 确认后清除标记。
- 三层接口暴露：Kernel（`verify_claim`）→ CLI（`pks claim verify`）→ MCP（`verify_claim` tool）→ Web UI（重验证队列）。

详见 [`docs/plans/2026-05-14-pks-p3.2-integrity-cascade-plan.md`](../plans/2026-05-14-pks-p3.2-integrity-cascade-plan.md)。
