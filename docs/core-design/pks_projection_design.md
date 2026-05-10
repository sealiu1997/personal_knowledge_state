# PKS Projection 设计

状态：P1 设计优化，2026-05-10。

## 定位

Projection 是 Claim 集合的 Markdown 映射。它的作用是帮助人类或 Agent 快速理解 Capsule，但它不是长期状态本身。

**核心原则：所有 Markdown 都是 Claim 集合的投影，不允许出现可以随意改动的文字。**

这条原则的目的：
1. 让维护者从高抽象 Markdown 向下拆解到具体 Claim，再从 Claim 追溯 Evidence。
2. 避免 Agent 通过绕过 Kernel 的 Markdown 修改污染 Capsule。
3. 保证 Markdown 内容始终可以从 Claim 集合重新生成，不会出现"MD 里有但 Claim 里没有"的孤立信息。

人或 Agent 不直接修改 Projection 文件。Kernel 提供投影内容和投影规则的编辑接口，所有修改都通过接口转成 Claim 操作或 ProjectionSpec 变更。

## PKS.md 即 Content Pack

`PKS.md` 就是 Content Pack。不再维护两个概念。

**PKS.md 是 Capsule 所有投影的有序聚合**，不是一个独立的 ProjectionSpec：

```text
PKS.md 内容 =
  BaseCapsule 投影（PKS_PROJECT.md 内容）
  + 领域 Capsule 投影（architecture.md / outline.md 等，由 capsule_type 决定）
  + 项目自定义投影
  + TasteAndStyle 注入（领域级 → 类型级，按继承链合并）
```

顺序服从 Capsule 继承关系：Base → Domain → Project Custom → TasteAndStyle。

PKS.md 的生成逻辑不需要自己的 ProjectionSpec，而是按 Capsule 继承顺序拼接所有已定义投影的输出。`render_context` 返回字符串，`render_projection` 写入文件，两者调用同一套 ProjectionEngine。

## 数据流

从 Claim 到 Markdown 的单向数据流：

```text
Evidence + Supporting Claims
  ↓ 支撑
Claim（accepted）
  ↓ ProjectionSpec 过滤 + 排序
Markdown Projection
```

投影内容修改必须通过 Kernel 接口回到 Claim：

```text
人/Agent 想修改 Projection 内容
  ↓
Projection content edit API（submit_projection_claim / patch_projection_claim）
  ↓ Kernel
Claim operation draft
  ├── 新建 Candidate Claim（新增内容）
  ├── Claim patch（修改已有 Claim 的字段）
  └── reject（修改不合法）
      ↓ review / validation
Accepted Claim changes
  ↓ ProjectionEngine regenerate
Updated Markdown
```

**关键约束：Projection 文件本身不是事实源。只有 Kernel 接受后的 Claim 操作会改变长期状态。**

## ProjectionSpec

每个 Markdown 投影由一个显式规则定义。ProjectionSpec 决定哪些 Claims 进入投影、如何排序和分组。

```yaml
projection_id: project-summary
output_path: projections/PKS_PROJECT.md
title: "Project Summary"
description: "项目定义、边界、当前阶段和目标"
include_status:
  - accepted
exclude_stale: true
filters:
  domains:
    - dev
  types:
    - factual
    - inference
    - constraint
  tags:
    - project
    - boundary
    - stage
    - goal
    - deliverable
  predicates: []               # 可选：按 predicate 过滤
order:
  - type                       # 先按类型分组
  - created_at                 # 再按时间排序
group_by: null                 # 可选：按某字段分组展示
template: null                 # 可选：自定义渲染模板
```

ProjectionSpec 字段：

| 字段 | 作用 | 必须 | 示例 |
|------|------|------|------|
| `projection_id` | 投影稳定 id | ✅ | `project-summary` |
| `output_path` | 输出路径（相对于 Capsule） | ✅ | `projections/PKS_PROJECT.md` |
| `title` | Markdown 标题 | ✅ | `Project Summary` |
| `description` | 投影用途说明 | 选配 | `项目定义与边界` |
| `include_status` | 包含的 Claim 状态 | ✅ | `["accepted"]` |
| `exclude_stale` | 是否排除 computed stale | ✅ | `true` |
| `filters` | Claim 过滤条件 | ✅ | 见下 |
| `filters.domains` | 领域过滤 | 选配 | `["dev"]` |
| `filters.types` | 类型过滤 | 选配 | `["factual", "inference"]` |
| `filters.tags` | 标签过滤（OR 逻辑） | 选配 | `["project", "boundary"]` |
| `filters.predicates` | 谓语过滤 | 选配 | `["current_stage", "current_goal"]` |
| `order` | 排序规则 | ✅ | `["type", "created_at"]` |
| `group_by` | 分组展示字段 | 选配 | `"type"` |
| `template` | 自定义渲染模板 | 选配 | `null` |

P1 可以先用代码内置 ProjectionSpec。等自定义投影需求稳定后，再把 ProjectionSpec 落盘为 YAML 文件。

## 基础投影定义

### PKS.md（Content Pack）

PKS.md 不使用独立的 ProjectionSpec。它是所有投影按继承顺序拼接的聚合输出：

1. `PKS_PROJECT.md` 内容（BaseCapsule 投影）
2. 领域投影内容（由 `capsule_type` 决定：architecture.md / outline.md 等）
3. 项目自定义投影内容
4. TasteAndStyle Claims（领域级 → 类型级）

默认排除 candidate、disputed、expired、superseded、computed stale Claims。

输出位置：`<external_project_path>/PKS.md`（项目根目录）。

### PKS_PROJECT.md

```yaml
projection_id: project-summary
output_path: projections/PKS_PROJECT.md
title: "Project Summary"
include_status:
  - accepted
exclude_stale: true
filters:
  tags:
    - project
    - boundary
    - stage
    - goal
    - deliverable
    - constraint
  predicates:
    - current_stage
    - current_goal
    - expected_deliverable
    - project_boundary
order:
  - type
  - created_at
```

包含由 `project.yaml` 迁移出来的项目知识 Claims：当前阶段、当前目标、交付物和约束。

### journal.md

```yaml
projection_id: journal
output_path: projections/journal.md
title: "Project Journal"
description: "决策、经验、进展类 Claim 的时间线投影"
include_status:
  - accepted
exclude_stale: false           # journal 保留 stale 记录，标注 stale 状态
filters:
  types:
    - inference                # 决策推断
    - preference               # 偏好取舍
    - constraint               # 约束变更
  tags:
    - decision
    - experience
    - progress
    - milestone
  exclude_tags:
    - audit                    # 排除 Audit Claim，避免噪音
order:
  - created_at                 # 按时间线排序
group_by: null                 # 不分组，纯时间线
```

journal 不限定 Claim type（除了排除 audit），但以 inference/preference/constraint 为主。factual Claim 通常不进入 journal，除非标记了 decision/progress 标签。

### 领域模块投影

**DevCapsule：**

```yaml
# architecture.md
projection_id: dev-architecture
output_path: projections/architecture.md
title: "Architecture & Decisions"
include_status: [accepted]
exclude_stale: true
filters:
  types: [factual, inference, constraint]
  tags: [architecture, design-decision, tech-stack, boundary]
order: [type, created_at]

# tasks.md
projection_id: dev-tasks
output_path: projections/tasks.md
title: "Tasks & Progress"
include_status: [accepted]
exclude_stale: true
filters:
  tags: [task, todo, in-progress, done]
order: [created_at]
```

**ContentCapsule / ResearchCapsule** 类似，按各自领域的标签和类型过滤。

## Kernel 投影接口

### 投影生成接口

| 接口 | 作用 | 输入 | 输出 |
|------|------|------|------|
| `render_context(project_id)` | 返回动态 PKS.md 字符串 | project_id | Markdown 字符串 |
| `render_projection(project_id, projection_id)` | 生成指定投影文件 | project_id, projection_id | 文件路径 |
| `list_projections(project_id)` | 列出项目内可用投影 | project_id | ProjectionSpec 列表 |

### 投影规则接口

| 接口 | 作用 | 输入 | 输出 |
|------|------|------|------|
| `create_projection_spec(project_id, spec)` | 创建自定义投影规则 | project_id, ProjectionSpec | 保存确认 |
| `update_projection_spec(project_id, projection_id, changes)` | 修改投影规则 | project_id, projection_id, 变更 | 保存确认 |
| `delete_projection_spec(project_id, projection_id)` | 删除自定义投影 | project_id, projection_id | 删除确认 |

### 投影内容编辑接口

这是让"所有 MD 都是 Claim 集合"原则落地的关键接口。

| 接口 | 作用 | 输入 | 输出 |
|------|------|------|------|
| `submit_projection_claim(project_id, projection_id, claim_draft)` | 通过投影提交新 Claim | project_id, projection_id, Claim 草稿 | Candidate Claim |
| `patch_projection_claim(project_id, projection_id, claim_id, changes)` | 通过投影修改已有 Claim | project_id, projection_id, claim_id, 字段变更 | Claim patch 或 Candidate |

**`submit_projection_claim` 行为：**

```text
1. 接收 Claim 草稿（至少包含 subject/predicate/object + evidence）
2. 自动补充 projection_id 对应的默认 tags（确保新 Claim 会出现在该投影中）
3. 校验 min_support 规则
4. 如果校验通过 → 写入 candidates/ 作为 Candidate Claim
5. 如果校验失败 → 返回 reject 原因
6. 返回 Candidate Claim ID，等待 review
```

**`patch_projection_claim` 行为：**

```text
1. 加载目标 Claim
2. 验证该 Claim 确实属于指定 projection（通过 tags/predicates 匹配）
3. 应用字段变更
4. 重新校验 min_support 规则
5. 如果变更涉及 subject/predicate/object（语素变更）：
   - 创建新 Candidate Claim（supersedes 旧 Claim）
   - 等待 review
6. 如果变更只涉及 content/tags/qualifier（非语素变更）：
   - 直接更新 accepted Claim（不需要 review）
   - 写 Audit Claim
7. 重新生成投影
```

**设计原则：**
- 语素变更（改变了 Claim 说的是什么）必须走 Candidate → Review 路径。
- 非语素变更（改变了展示方式或分类）可以直接更新。
- 所有变更都写 Audit Claim。

## 维护规则

- Projection 文件头必须声明 `<!-- Generated from Claims. Do not edit directly. -->`。
- 人或 Agent 通过 Kernel 接口编辑 Projection 内容和规则。
- Projection 文件不作为编辑入口。
- 未通过 Kernel 接受的编辑不会改变长期状态。
- ProjectionEngine 可随时覆盖旧文件。
- 所有自定义 Markdown 必须先定义 ProjectionSpec。
- 如果检测到 Projection 文件被直接修改（hash 不匹配），Kernel 应发出警告并可选择覆盖。

## 投影与理解层次

投影的设计服务于"从上到下理解项目"的目标：

```text
PKS.md（最高抽象：项目是什么、当前在做什么、关键约束）
  ↓ 想了解更多
PKS_PROJECT.md（项目定义、边界、阶段、目标）
  ↓ 想了解具体领域
architecture.md / tasks.md / journal.md（领域细节）
  ↓ 想了解具体主张
单条 Claim（结构化主张 + 支撑链）
  ↓ 想了解证据
Evidence（原始来源、文件引用、摘录）
```

每一层都是下一层的精选投影。读者可以根据自己的理解程度，在任意层停下来，也可以继续向下追溯。
