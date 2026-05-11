# Personal Knowledge State / 个人知识状态

PKS is a local-first personal knowledge state control plane.

PKS 是一个本地优先的个人知识状态控制平面。

The authoritative product design is [`docs/core-design/pks_product_plan_v2.md`](docs/core-design/pks_product_plan_v2.md).
Current design notes live beside it:
[`pks_kernel_design.md`](docs/core-design/pks_kernel_design.md),
[`pks_claim_design.md`](docs/core-design/pks_claim_design.md),
[`pks_capsule_design.md`](docs/core-design/pks_capsule_design.md), and
[`pks_projection_design.md`](docs/core-design/pks_projection_design.md).

权威产品设计文档是 [`docs/core-design/pks_product_plan_v2.md`](docs/core-design/pks_product_plan_v2.md)。
当前设计说明位于同目录：
[`pks_kernel_design.md`](docs/core-design/pks_kernel_design.md)、
[`pks_claim_design.md`](docs/core-design/pks_claim_design.md)、
[`pks_capsule_design.md`](docs/core-design/pks_capsule_design.md)、
[`pks_projection_design.md`](docs/core-design/pks_projection_design.md)。

Historical inputs are archived under [`docs/history/`](docs/history/), including the original product plan, the architecture/tooling increment, and Li Ziran's article that motivated the problem framing.

历史输入归档在 [`docs/history/`](docs/history/)，包括早期产品规划、架构与工具复用增量文档，以及启发问题框架的李自然文章。

## Current Slice / 当前切片

This repository has completed the P1 claim/review implementation slice:

当前仓库已经完成 P1 Claim 候选与审核实现切片：

- Python package skeleton under `src/pks/`
- `src/pks/` 下的 Python 包骨架
- Pydantic models for project metadata, tracking, domain policy, min_support, supporting Claims, ProjectionSpec, and evidence-backed Claims
- 项目元信息、跟踪配置、领域策略、min_support、supporting Claims、ProjectionSpec 与 evidence 支撑 Claim 的 Pydantic 模型
- Independent PKS home resolution, defaulting to `~/.pks`
- 独立 PKS home 路径解析，默认是 `~/.pks`
- Kernel modules for Project Registry, Claim Engine, Candidate Queue, Review Engine, Review Strategy, Tracker, Projection, Snapshot, and Audit Claims
- Kernel 模块：项目注册、Claim 引擎、候选队列、审核引擎、审核策略、项目跟踪、投影、快照与 Audit Claim
- Kernel code is split by business boundary under `src/pks/kernel/`
- Kernel 代码已按业务边界拆分在 `src/pks/kernel/`
- YAML-backed Capsule, accepted Claim, Candidate Claim, and custom ProjectionSpec storage with default domain `claim_policy.yaml`
- 基于 YAML 的 Capsule、accepted Claim、Candidate Claim 和自定义 ProjectionSpec 存储，并生成默认领域 `claim_policy.yaml`
- Domain-level and type-level TasteAndStyle Claims are injected into `PKS.md`
- 领域级和类型级 TasteAndStyle Claim 会注入 `PKS.md`
- Dynamic `PKS.md` and Capsule projection files are generated from ProjectionSpecs and accepted Claims
- 动态 `PKS.md` 与 Capsule 投影文件由 ProjectionSpec 和 accepted Claims 生成
- Typer CLI entrypoint with `init-home`, `new`, `context`, `health`, `claim`, `review`, `policy`, `project`, and `snapshot`
- Typer CLI 入口，包含 `init-home`、`new`、`context`、`health`、`claim`、`review`、`policy`、`project` 和 `snapshot`

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
.venv/bin/pks new pks --name PKS --capsule-type SoftwareCapsule --domain dev --stage P1 --home /private/tmp/pks-smoke-home --yes
.venv/bin/pks claim add pks --claim-id CLM-001 --subject PKS --predicate stores_state_in --object "independent PKS home" --source-ref manual --excerpt "用户手动设定" --confidence 0.9 --home /private/tmp/pks-smoke-home
.venv/bin/pks review show pks CLM-001 --home /private/tmp/pks-smoke-home
.venv/bin/pks review accept pks CLM-001 --home /private/tmp/pks-smoke-home
.venv/bin/pks context pks --home /private/tmp/pks-smoke-home
.venv/bin/pks health pks --home /private/tmp/pks-smoke-home
.venv/bin/pks policy validate dev --home /private/tmp/pks-smoke-home
.venv/bin/pks project projection-check pks --home /private/tmp/pks-smoke-home
.venv/bin/pks snapshot create --message "smoke snapshot" --home /private/tmp/pks-smoke-home
```

## Design Boundaries / 设计边界

- PKS state lives outside project folders.
- PKS 状态存放在项目文件夹之外。
- Project folders receive generated projections such as `PKS.md`.
- 项目文件夹只接收 `PKS.md` 这类生成投影。
- `PKS.md` is the materialized Content Pack; `context.md` is not persisted.
- `PKS.md` 是落地版 Content Pack；不持久化 `context.md`。
- Markdown files are Claim projections; content and rule changes go through Kernel APIs.
- Markdown 文件是 Claim 投影；内容和规则修改通过 Kernel 接口完成。
- Agents submit candidate knowledge with evidence; they do not directly mutate accepted state.
- Agent 提交带证据的候选知识，不能直接修改 accepted 状态。
