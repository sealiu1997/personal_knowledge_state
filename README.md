# Personal Knowledge State / 个人知识状态

PKS is a local-first personal knowledge state control plane.

PKS 是一个本地优先的个人知识状态控制平面。

The authoritative product design is [`docs/core-design/pks_product_plan_v2.md`](docs/core-design/pks_product_plan_v2.md).
Current P0 design notes live beside it:
[`pks_kernel_design.md`](docs/core-design/pks_kernel_design.md),
[`pks_claim_design.md`](docs/core-design/pks_claim_design.md), and
[`pks_capsule_design.md`](docs/core-design/pks_capsule_design.md).

权威产品设计文档是 [`docs/core-design/pks_product_plan_v2.md`](docs/core-design/pks_product_plan_v2.md)。
当前 P0 设计说明位于同目录：
[`pks_kernel_design.md`](docs/core-design/pks_kernel_design.md)、
[`pks_claim_design.md`](docs/core-design/pks_claim_design.md) 和
[`pks_capsule_design.md`](docs/core-design/pks_capsule_design.md)。

Historical inputs are archived under [`docs/history/`](docs/history/), including the original product plan, the architecture/tooling increment, and Li Ziran's article that motivated the problem framing.

历史输入归档在 [`docs/history/`](docs/history/)，包括早期产品规划、架构与工具复用增量文档，以及启发问题框架的李自然文章。

## Current Slice / 当前切片

This repository has started the P0 implementation:

当前仓库已经开始 P0 实施：

- Python package skeleton under `src/pks/`
- `src/pks/` 下的 Python 包骨架
- Pydantic models for project metadata, tracking, domain policy, and evidence-backed Claims
- 项目元信息、跟踪配置、领域策略与证据支撑 Claim 的 Pydantic 模型
- Independent PKS home resolution, defaulting to `~/.pks`
- 独立 PKS home 路径解析，默认是 `~/.pks`
- Kernel modules for Project Registry, Claim Engine, Review Strategy, Tracker, Context, Projection, and Audit Log
- Kernel 模块：项目注册、Claim 引擎、审核策略、项目跟踪、上下文、投影与审计日志
- Kernel code is split by business boundary under `src/pks/kernel/`
- Kernel 代码已按业务边界拆分在 `src/pks/kernel/`
- YAML-backed Capsule and Claim storage with default domain `claim_policy.yaml`
- 基于 YAML 的 Capsule 与 Claim 存储，并生成默认领域 `claim_policy.yaml`
- Domain-level TasteAndStyle Claims are injected into Context Pack and `PKS.md`
- 领域级 TasteAndStyle Claim 会注入 Context Pack 与 `PKS.md`
- Dynamic Markdown Context Pack and generated `PKS.md` projection
- 动态 Markdown Context Pack 与生成式 `PKS.md` 投影
- Typer CLI entrypoint with `init-home`, `new`, `context`, `health`, `claim`, and `project`
- Typer CLI 入口，包含 `init-home`、`new`、`context`、`health`、`claim` 和 `project`

## Local Development / 本地开发

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
```

CLI smoke test:

CLI 冒烟测试：

```bash
.venv/bin/pks --version
.venv/bin/pks init-home --home /private/tmp/pks-smoke-home
.venv/bin/pks new pks --name PKS --capsule-type SoftwareCapsule --domain dev --stage P0 --home /private/tmp/pks-smoke-home --yes
.venv/bin/pks claim add pks --claim-id CLM-001 --subject PKS --predicate stores_state_in --object "independent PKS home" --source-ref manual --excerpt "用户手动设定" --confidence 0.9 --home /private/tmp/pks-smoke-home
.venv/bin/pks context pks --home /private/tmp/pks-smoke-home
.venv/bin/pks health pks --home /private/tmp/pks-smoke-home
```

## Design Boundaries / 设计边界

- PKS state lives outside project folders.
- PKS 状态存放在项目文件夹之外。
- Project folders receive generated projections such as `PKS.md`.
- 项目文件夹只接收 `PKS.md` 这类生成投影。
- Context Packs are generated dynamically and are not persisted as `context.md`.
- Context Pack 动态生成，不以 `context.md` 形式持久化。
- Agents submit candidate knowledge with evidence; they do not directly mutate accepted state.
- Agent 提交带证据的候选知识，不能直接修改 accepted 状态。
