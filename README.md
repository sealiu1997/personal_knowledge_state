# Personal Knowledge State / 个人知识状态

PKS is a local-first personal knowledge state control plane.

PKS 是一个本地优先的个人知识状态控制平面。

## Status / 状态

**MVP complete (P0–P3.2).** Ready for dogfood.

**MVP 完成（P0–P3.2）。** 可以开始 dogfood。

## Documentation / 文档

| Document | Description |
|----------|-------------|
| [`docs/core-design/pks_product_plan_v2.md`](docs/core-design/pks_product_plan_v2.md) | Authoritative product design / 权威产品设计 |
| [`docs/core-design/pks_kernel_design.md`](docs/core-design/pks_kernel_design.md) | Kernel architecture / 内核架构 |
| [`docs/core-design/pks_claim_design.md`](docs/core-design/pks_claim_design.md) | Claim data structure / Claim 数据结构 |
| [`docs/core-design/pks_capsule_design.md`](docs/core-design/pks_capsule_design.md) | Capsule system / 胶囊体系 |
| [`docs/core-design/pks_projection_design.md`](docs/core-design/pks_projection_design.md) | Projection system / 投影系统 |
| [`docs/core-design/pks_maintenance_design.md`](docs/core-design/pks_maintenance_design.md) | Maintenance engine / 维护引擎 |
| [`docs/adapter/mcp_design.md`](docs/adapter/mcp_design.md) | MCP adapter / MCP 适配层 |
| [`docs/adapter/web/`](docs/adapter/web/) | Web UI adapter / Web UI 适配层 |
| [`skills/pks-agent/SKILL.md`](skills/pks-agent/SKILL.md) | Codex skill wrapper / Codex skill 封装 |

## Features / 功能

- **Kernel**: Claim lifecycle (submit → review → accept/reject), min_support validation, conflict detection, evidence tracking, stale/expiry management, projection generation, audit trail
- **CLI**: Full Kernel access via `pks` command (init-home, new, claim, review, policy, project, snapshot, maintain, mcp, serve)
- **Web UI**: Dashboard, Claim browsing (multi-dimension), Claim creation/editing, batch review, projection preview/editing, evidence tree, config management, MCP token display
- **MCP Server**: Agent access via standard MCP protocol (read tools open, write tools token-gated)
- **Maintenance**: Automated stale scanning, expiry enforcement, evidence re-check
- **Codex Skill**: `pks-agent` skill for MCP-based project context, candidate Claims, and re-verification workflows

## Quick Start / 快速开始

```bash
# Install
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,web,mcp]'

# Initialize PKS home
.venv/bin/pks init-home

# Create a capsule
.venv/bin/pks new my-project \
  --name "My Project" \
  --capsule-type SoftwareCapsule \
  --domain dev \
  --stage "Development" \
  --yes

# Add a claim
.venv/bin/pks claim add my-project \
  --claim-id F-00001 \
  --subject "My Project" \
  --predicate "uses_stack" \
  --object "Python" \
  --source-ref manual \
  --excerpt "Developer confirmed"

# Review and accept
.venv/bin/pks review accept my-project F-00001

# Check health
.venv/bin/pks health my-project

# Start Web UI
.venv/bin/pks serve

# Start MCP Server
.venv/bin/pks mcp start
```

## Development / 开发

```bash
.venv/bin/python -m pytest -q       # 53 tests
.venv/bin/python -m ruff check .    # lint
.venv/bin/python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/pks-agent
```

## Architecture / 架构

```text
┌─────────────────────────────────────────┐
│           External Adapters              │
│  CLI · Web UI · MCP Server              │
└────────────────┬────────────────────────┘
                 │ Kernel API
┌────────────────▼────────────────────────┐
│              Kernel                      │
│  ClaimWorkflow · HealthEngine           │
│  ProjectionService · MaintenanceEngine  │
│  ProjectRegistry (composition)          │
└────────────────┬────────────────────────┘
                 │ YAML Storage
┌────────────────▼────────────────────────┐
│           ~/.pks/                        │
│  capsules/ · domains/ · config.yaml     │
└─────────────────────────────────────────┘
```

Core principle: **Kernel is the only business logic layer.** CLI, Web UI, and MCP are thin adapters that delegate to Kernel.

核心原则：**Kernel 是唯一的业务逻辑层。** CLI、Web UI 和 MCP 都是委托给 Kernel 的薄适配层。

## Design Boundaries / 设计边界

- PKS state lives outside project folders (`~/.pks/`).
- Project folders only receive generated `PKS.md`.
- All Markdown files are Claim projections; edits go through Kernel.
- Agents submit candidate Claims with evidence; they cannot directly mutate accepted state.
- Kernel validates min_support per Claim type; invalid submissions are rejected.
- Token-based MCP auth: read open, write requires token.
