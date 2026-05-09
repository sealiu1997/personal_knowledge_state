# PKS Capsule 设计

状态：P0 当前实现同步，2026-05-09。

## 定位

Capsule 是项目知识状态容器。它记录项目边界、当前目标、Claims、领域模块和跟踪配置，但不替代项目文件夹。

PKS 状态存放在 PKS home，项目文件夹只接收生成投影 `PKS.md`。

## ProjectMetadata

当前机器可读元信息：
- `project_id`
- `name`
- `capsule_type`
- `domain`
- `stage`
- `current_goal`
- `deliverable`
- `constraints`
- `external_project_path`
- `repository_url`
- `tracking`

`tracking` 包含：
- `project_path`
- `git_remote`
- `watched_paths`
- `auto_watch_evidence`
- `last_synced_commit`

`external_project_path` 与 `tracking.project_path` 会同步为同一项目根。

## 存储布局

```text
~/.pks/
├── config.yaml
├── capsules/
│   └── <project_id>/
│       ├── project.yaml
│       ├── PKS_PROJECT.md
│       ├── journal.md
│       ├── claims/
│       └── <domain modules>
└── domains/
    ├── dev/
    │   ├── claim_policy.yaml
    │   └── taste_and_style/
    │       └── claims/
    ├── content/
    └── research/
```

BaseCapsule 文件：
- `project.yaml`
- `PKS_PROJECT.md`
- `journal.md`
- `claims/`

领域扩展：
- content：`outline.md`、`facts.md`
- dev：`architecture.md`、`tasks.md`
- research：`terminology.md`、`hypotheses.md`

## 创建流程

`pks new` 是填表式命令。用户或 Agent 必须传入明确字段；命令只校验和落盘，不推断产品意图。

创建时：
- 初始化 PKS home。
- 创建 Capsule 目录。
- 写入 `project.yaml`。
- 初始化 `PKS_PROJECT.md`、`journal.md`、`claims/`。
- 生成领域模块文件。
- 确保领域 `claim_policy.yaml` 和 TasteAndStyle Claim 目录存在。

## 领域策略

每个领域都有默认 `claim_policy.yaml`。P0 用它控制：
- factual auto accept threshold。
- 各 Claim 类型的 stale 周期。
- 默认人工审核类型。

策略属于领域，不属于单个项目。

## 投影

`PKS.md` 是项目文件夹内的生成投影：
- 可写入项目根。
- 包含项目摘要、边界、accepted non-stale Claims、PKS 胶囊路径。
- 永远不作为事实源读取。

Context Pack 与 `PKS.md` 使用同一组 eligible Claims。

## 项目跟踪

P0 支持两种检查：
- evidence 完整性检查：确认 `source_ref` 文件存在且包含 `excerpt`。
- Git diff watched paths：记录 `last_synced_commit`，同步时返回变更路径。

非 Git 项目退化为 evidence 完整性检查。
