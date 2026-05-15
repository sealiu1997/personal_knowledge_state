# P3 + P3.1 + P3.2 实施完成记录

来源：
- `docs/core-design/pks_product_plan_v2.md`
- `docs/plans/2026-05-11-pks-p3-agent-collaboration-plan.md`
- `docs/adapter/mcp_design.md`
- `docs/adapter/web/`

## MVP 完成状态

P0 → P3.2 全部完成。系统可用于 dogfood，并已提供 Codex skill 封装。

## 实现总览

| 阶段 | 交付 | 测试 |
|------|------|------|
| P0 | Kernel 基线（Capsule/Claim/投影/健康/跟踪/审计/快照/CLI） | 18 tests |
| P1 | Candidate/Review 闭环 + min_support + 投影纪律 + Audit Claim | 30 tests |
| P2 | 自动维护 + 最小 Web UI + 代码重构（组合模式） | 36 tests |
| P3 | MCP Server + Token 认证 + Web UI 完善（批量审核/Claim 新建/编辑/证据链/配置） | 45 tests |
| P3.1 | 投影预览/编辑 + PKS.md 预览 + 策略编辑 + claims.py 拆分 | 48 tests |
| P3.2 | 支撑链断裂检测 + Evidence 变更级联 + 重验证队列 + CLI/Web/MCP verify | 53 tests |
| Skill | `skills/pks-agent` Codex skill 封装 + `agents/openai.yaml` 元数据 | quick_validate passed |

## 代码统计

- Python 源文件：60
- 总代码行数：~5300
- 测试数量：53
- Lint：全部通过

## 模块结构

```text
src/pks/
├── kernel/              # 核心业务逻辑
│   ├── facade.py        # Kernel 用例入口（薄编排层）
│   ├── health.py        # HealthEngine
│   ├── capsule/         # ProjectRegistry + 子模块（组合模式）
│   ├── claim/           # ClaimEngine + ClaimWorkflow + ClaimStore
│   ├── candidate/       # CandidateQueue + CandidateStore
│   ├── review/          # ReviewEngine + ReviewStrategy
│   ├── render/          # ProjectionEngine + ProjectionService
│   ├── maintenance/     # MaintenanceEngine
│   ├── snapshot/        # SnapshotManager
│   ├── tracking/        # ProjectTracker
│   ├── audit/           # AuditClaimFactory
│   └── storage/         # YAML 读写
├── web/                 # Web UI 适配层
│   ├── app.py           # FastAPI app factory
│   ├── routes/          # 路由（projects/candidates/claims/projections/config/tokens/maintenance）
│   ├── templates/       # Jinja2 模板
│   └── static/          # CSS + htmx
├── mcp/                 # MCP 适配层
│   ├── server.py        # MCP Server
│   ├── tools/           # read + write 工具
│   └── auth.py          # Token 管理
├── cli.py               # CLI 适配层
└── models.py            # Pydantic 数据模型
```

## 验证

```bash
.venv/bin/python -m pytest -q    # 53 passed
.venv/bin/python -m ruff check . # All checks passed
.venv/bin/python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/pks-agent
# Skill is valid!
```

## 下一步

进入 dogfood 阶段：
- 用 PKS 管理 PKS 自身的知识状态
- 用 PKS 管理其他实际项目
- 收集使用反馈，迭代优化
