# PKS Capsule 设计

状态：P1 设计优化，2026-05-10。

## 定位

Capsule 是项目知识状态容器。它组织运行时元数据、Claims、候选队列、领域策略和 Markdown 投影，但不替代项目文件夹。

Capsule 不允许长期知识绕过 Claim。所有 Markdown 都是 Claim 集合的投影输出；人或 Agent 应通过 Kernel 的投影接口修改内容或规则。

**Capsule 的本质**：它是快速理解项目现状和运行时的方法。通过 Capsule 的投影（各种 MD），读者可以从上到下逐层理解项目；通过 Capsule 的 Claims，读者可以追溯每条知识的来源和支撑。

## 继承体系

### 概念模型

借鉴面向对象编程的类与继承：BaseCapsule 定义最小通用结构，领域胶囊从中派生，具体项目从领域胶囊实例化。

```text
BaseCapsule（基础原型）
  ├── ContentCapsule（内容创作）  + TasteAndStyle
  │     ├── ArticleCapsule
  │     ├── VideoCapsule
  │     └── GameCapsule
  ├── DevCapsule（程序开发）      + TasteAndStyle
  │     ├── SoftwareCapsule
  │     └── PluginCapsule
  └── ResearchCapsule（课题研究）  + TasteAndStyle
        ├── DisciplineCapsule
        └── ModelCapsule
```

### 实现映射

继承体系在代码中不使用 Python 类继承，而是通过 `capsule_type` + `domain` + 领域策略 + 默认 ProjectionSpec 的组合来实现：

| 继承概念 | 实现方式 |
|----------|----------|
| BaseCapsule 最小结构 | 所有 Capsule 共享的目录布局和必须文件 |
| 领域胶囊（ContentCapsule/DevCapsule/ResearchCapsule） | `domain` 字段决定加载哪个领域的 `claim_policy.yaml` 和 TasteAndStyle |
| 具体类型（SoftwareCapsule/ArticleCapsule 等） | `capsule_type` 字段决定默认 ProjectionSpec 集合 |
| TasteAndStyle | 领域级和类型级 `type=preference` Claims，按继承链注入项目的 PKS.md |
| 领域扩展模块 | `capsule_type` 决定默认生成哪些领域投影（architecture.md / outline.md 等） |

**`capsule_type` 与默认投影的映射：**

| capsule_type | domain | 默认投影 |
|--------------|--------|----------|
| `SoftwareCapsule` | dev | PKS_PROJECT.md, journal.md, architecture.md, tasks.md |
| `PluginCapsule` | dev | PKS_PROJECT.md, journal.md, architecture.md |
| `ArticleCapsule` | content | PKS_PROJECT.md, journal.md, outline.md, facts.md |
| `VideoCapsule` | content | PKS_PROJECT.md, journal.md, outline.md |
| `DisciplineCapsule` | research | PKS_PROJECT.md, journal.md, terminology.md, hypotheses.md |
| `ModelCapsule` | research | PKS_PROJECT.md, journal.md, hypotheses.md |

项目可以在默认投影基础上添加自定义 ProjectionSpec。

## ProjectMetadata

`project.yaml` 是机器可读注册信息，不是项目知识正文。它保留为 Kernel 的启动入口，不全量改造成 Claim 集合。

目标字段：

| 字段 | 作用 | 示例 | 是否 Claim 化 |
|------|------|------|---------------|
| `project_id` | Capsule 稳定 id，用于路径和 CLI | `pks` | 否 |
| `name` | 展示名，不承载项目判断 | `Personal Knowledge State` | 否 |
| `capsule_type` | Capsule 类型，决定默认投影和策略 | `SoftwareCapsule` | 否 |
| `domain` | 领域策略选择 | `dev` | 否 |
| `external_project_path` | 外部项目路径 | `/Users/me/code/pks` | 否 |
| `repository_url` | 关联仓库地址 | `git@github.com:user/pks.git` | 否 |
| `tracking` | 同步和 evidence 检查配置 | 见下表 | 否 |

`tracking` 包含：

| 字段 | 作用 | 示例 |
|------|------|------|
| `project_path` | 被跟踪项目根目录 | `/Users/me/code/pks` |
| `git_remote` | 项目 Git remote | `origin` |
| `watched_paths` | 主动 diff 的关键路径 | `["docs/**", "src/**"]` |
| `auto_watch_evidence` | 是否自动检查 evidence 引用文件 | `true` |
| `last_synced_commit` | 最近同步 commit | `abc123` |

`external_project_path` 与 `tracking.project_path` 会同步为同一项目根。

以下 P0 字段在 P1 迁移为 Claims：

| P0 字段 | Claim 表达 | 默认投影 |
|---------|------------|----------|
| `stage` | `subject=<project>`, `predicate=current_stage` | PKS_PROJECT.md |
| `current_goal` | `predicate=current_goal` | PKS_PROJECT.md |
| `deliverable` | `predicate=expected_deliverable` | PKS_PROJECT.md |
| `constraints` | `type=constraint` | PKS_PROJECT.md |

这些迁移后的 Claims 默认进入 `PKS_PROJECT.md` 投影。迁移后 `project.yaml` 不再保留这些字段。

## 存储布局

```text
~/.pks/
├── config.yaml
├── capsules/
│   └── <project_id>/
│       ├── project.yaml           # 运行时注册信息
│       ├── claims/                # accepted Claims
│       ├── candidates/            # 待审核 Candidate Claims
│       ├── projections/           # Claim 投影输出
│       │   ├── PKS_PROJECT.md
│       │   ├── journal.md
│       │   └── <domain projections>
│       └── projection_specs/      # 自定义 ProjectionSpec（P1 后期）
└── domains/
    ├── dev/
    │   ├── claim_policy.yaml      # 领域策略（含 min_support）
    │   ├── taste_and_style/       # 领域级 TasteAndStyle
    │   │   └── claims/
    │   └── types/
    │       ├── software/
    │       │   └── taste_and_style/  # 类型级 TasteAndStyle
    │       │       └── claims/
    │       └── plugin/
    │           └── taste_and_style/
    │               └── claims/
    ├── content/
    │   ├── claim_policy.yaml
    │   ├── taste_and_style/
    │   │   └── claims/
    │   └── types/
    │       ├── article/
    │       │   └── taste_and_style/
    │       │       └── claims/
    │       ├── video/
    │       │   └── taste_and_style/
    │       │       └── claims/
    │       └── game/
    │           └── taste_and_style/
    │               └── claims/
    └── research/
        ├── claim_policy.yaml
        ├── taste_and_style/
        │   └── claims/
        └── types/
            ├── discipline/
            │   └── taste_and_style/
            │       └── claims/
            └── model/
                └── taste_and_style/
                    └── claims/
```

P0 代码仍会在 Capsule 根目录创建部分 Markdown 文件和 `audit.log`。P1 需要把 Markdown 收口为 Kernel 管理的投影，并把 audit 迁移为 `type=inference`、`tags=["audit"]` 的 Claim。路径可以兼容旧实现，但语义必须改成 Claim-first。

## TasteAndStyle 多级继承

TasteAndStyle 按 Capsule 继承层级组织，每一层派生都可以有自己的 TasteAndStyle：

```text
领域级（domains/<domain>/taste_and_style/）
  ↓ 继承
类型级（domains/<domain>/types/<type>/taste_and_style/）
  ↓ 注入
具体项目的 PKS.md
```

**注入规则：**
- 生成 PKS.md 时，按继承链从上到下收集 TasteAndStyle Claims。
- 领域级先注入，类型级后注入。
- 同 `(subject, predicate)` 冲突时，更具体的层级覆盖上层。
- 所有 TasteAndStyle Claim 强制人工审核，不允许自动接受。

## BaseCapsule 内容

| 项 | 职责 | 事实源 |
|----|------|--------|
| `project.yaml` | 注册信息、路径、跟踪配置 | 否（运行时元数据） |
| `claims/` | accepted Claims | 是（唯一事实源） |
| `candidates/` | 待审核 Candidate Claims | 候选源 |
| `projections/PKS_PROJECT.md` | 项目定义与边界投影 | 否（Claim 投影） |
| `projections/journal.md` | 决策、经验、进展时间线投影 | 否（Claim 投影） |

## 创建流程

`pks new` 是填表式命令。用户或 Agent 必须传入明确字段；命令只校验和落盘，不推断产品意图。

创建时：
1. 初始化 PKS home（如果不存在）。
2. 创建 Capsule 目录。
3. 写入最小 `project.yaml`（只含运行时注册字段）。
4. 创建 `claims/`、`candidates/`、`projections/`。
5. 将用户显式提供的项目定义、阶段、目标、约束转成初始 Claims（`type=factual` 或 `type=constraint`）。
6. 基于 `capsule_type` 确定默认 ProjectionSpec 集合。
7. 基于 Claims 和 ProjectionSpec 生成初始投影文件。
8. 确保领域 `claim_policy.yaml` 和 TasteAndStyle Claim 目录存在。

`pks new` 生成的 Markdown 是阅读投影，不是编辑入口。

## 读取与更新

P0 Kernel 支持：
- `load_capsule`：读取 `project.yaml`。
- `update_capsule`：显式更新 `project.yaml` 运行时注册字段。
- `resolve_capsule`：返回 `ProjectMetadata` 与 Capsule 路径。
- `list_capsules`：列出 PKS home 下所有 Capsule。

P1 需要补齐：
- `stage`、`current_goal`、`deliverable`、`constraints` 迁移为 Claim。
- 元信息更新只修改运行时注册字段。
- 投影内容修改通过 Kernel 接口生成 Candidate Claim 或 Claim patch。
- 投影规则修改通过 Kernel 接口更新 ProjectionSpec。
- 所有 Markdown 刷新均通过 ProjectionEngine。

## 领域策略

每个领域都有默认 `claim_policy.yaml`。策略同时考虑领域和 Claim 类型：

```yaml
domain: dev
lifecycle:
  factual:
    stale_after_days: 180
    auto_accept_threshold: 0.85
  inference:
    stale_after_days: 90
    auto_accept_threshold: null
  preference:
    stale_after_days: null
    auto_accept_threshold: null
  constraint:
    stale_after_days: null
    auto_accept_threshold: null
min_support:
  factual:
    evidence: 1
    supporting_claims: 0
    allowed_support_types: []
  inference:
    evidence: 0
    supporting_claims: 0
    evidence_or_claims_min: 1
    allowed_support_types: [factual]
  preference:
    evidence: 1
    supporting_claims: 0
    evidence_or_claims_min: 1
    allowed_support_types: [factual, inference]
    requires_human_source: true
  constraint:
    evidence: 1
    supporting_claims: 1
    evidence_or_claims_min: 2
    allowed_support_types: [factual, inference, preference]
    requires_manual_review: true
manual_review_types: [inference, preference, constraint]
```

策略属于领域，不属于单个项目。项目可以在领域策略基础上做微调（P2+）。

## Markdown 投影纪律

所有 Capsule 内 Markdown 都遵守同一规则：

- Markdown 是 Claim 集合的阅读投影，不是可以随意编辑的文字。
- 每个 Markdown 文件必须有对应的 ProjectionSpec。
- 人或 Agent 通过 Kernel 接口修改投影内容和规则。
- Kernel 将投影内容修改规范为 Candidate Claim、Claim patch 或 reject。
- ProjectionEngine 可以随时覆盖并重新生成 Markdown。
- 文件头必须声明 `<!-- Generated from Claims. Do not edit directly. -->`。

`journal.md` 是时间线投影，不是自由日记。它包含决策、经验、进展相关的 Claims，按时间排序，排除 Audit Claim。

## 项目跟踪

P0 支持两种检查：
- evidence 完整性检查：确认 `source_ref` 文件存在且包含 `excerpt`。
- Git diff watched paths：记录 `last_synced_commit`，同步时返回变更路径。

非 Git 项目退化为 evidence 完整性检查。

`pks project sync <project_id>` 调用 Kernel `sync_project`。同步会写回 `tracking.last_synced_commit`，但不会修改 Claim 状态。同步结果（哪些文件变了、哪些 Claim 的 evidence 可能受影响）返回给调用者，由调用者决定是否标记 disputed。

## 快照

P0 快照是显式操作：
- `pks snapshot create --message "..."`
- `pks snapshot list`

SnapshotManager 使用 PKS home 自身的 Git 仓库。若 PKS home 尚未初始化 Git，首次显式快照会执行初始化。普通 Capsule 或 Claim 状态变更只写 Audit Claim，不自动提交快照。
