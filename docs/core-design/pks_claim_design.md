# PKS Claim 设计

状态：P1 设计优化，2026-05-10。

## 定位

Claim 是长期知识和审计记录的唯一原子单位。

PKS 不单独设计 Fact 实体。Fact 就是最基础的 Claim，即 `type=factual` 的 Claim。Capsule 只负责按项目组织 Claims、策略和投影。

所有 Markdown 都是 Claim 集合的投影输出。人或 Agent 通过 Kernel 的投影接口修改内容；Kernel 将修改规范为 Claim 创建、Claim patch 或 Candidate Claim，再重新生成投影。

## Claim ID 生成规则

Claim ID 格式：`<type_code>-<global_sequence>`

| type | code | 示例 |
|------|------|------|
| factual | F | `F-00042` |
| inference | I | `I-00017` |
| preference | P | `P-00003` |
| constraint | C | `C-00008` |

**规则：**
- `type_code` 由 Claim 类型决定，创建后不可变（type 不可变）。
- `global_sequence` 是全局自增序号，存储在 `~/.pks/config.yaml` 的计数器中。
- 全局唯一：不区分项目或领域，所有 Claim（项目 Claim、TasteAndStyle Claim、Audit Claim）共用同一个计数器。
- Audit Claim 也是 inference，使用 `I-xxxxx` 格式。
- 序号位数不固定，按需增长（`F-1`、`F-42`、`F-10000` 都合法）。

**设计依据：**
- ID 不编码时间戳（`created_at` 字段已有）。
- ID 不编码作用域（存储路径隐式表达归属）。
- ID 不编码可变元数据（status、confidence 会变，编码进 ID 会导致引用失效）。
- type 是唯一不可变的枚举元数据，编码进 ID 提供可读性。

## 知识分层模型

PKS 的知识结构是自底向上构建的：

```text
Evidence（证据）
  ↑ 支撑
Fact（事实 = type:factual 的 Claim）
  ↑ 支撑
Inference / Preference / Constraint（推断 / 偏好 / 约束）
  ↑ 组织
Capsule（项目知识状态容器）
  ↑ 投影
Markdown（PKS.md / PKS_PROJECT.md / journal.md / 领域 MD）
```

每一层只能被下层支撑，不能被上层支撑。这保证了知识链的可追溯性：从任何一条高层 Claim 出发，都能向下追溯到具体的 Evidence。

## 类型层级

Claim 类型同时表达语义和支撑层级：

| 层级 | 类型 | 含义 | 支撑要求 | 创建者 |
|------|------|------|----------|--------|
| 0 | `factual` | 事实性观察 | 至少 1 条 evidence | 人类或 Agent |
| 1 | `inference` | 基于事实的推断 | 至少 1 条 evidence 或 accepted factual Claim | 人类或 Agent，必须有来源 |
| 2 | `preference` | 偏好、风格、取舍 | 至少 1 条 evidence + 人类确认来源，或由低层 Claim 支撑 | 人类为主，Agent 只能提交候选 |
| 3 | `constraint` | 约束、禁止、边界 | 至少 2 条支撑（evidence 或低层 Claim），必须人工审核 | 人类为主，Agent 只能提交候选 |

**层级规则：**
- 高层 Claim 可以引用低层 Claim 作为支撑；低层 Claim 不能引用高层 Claim 作为支撑。
- 同层 Claim 可以互相关联（`relation: supports`），但不能互相作为主要支撑。
- 层级越高，要求的支撑越多、审核越严格。

## 最低支撑要求（min_support）

每种 Claim 类型有不同的最低支撑要求。这些要求由领域策略 `claim_policy.yaml` 定义，以下是默认值：

```yaml
# 默认 min_support 规则
min_support:
  factual:
    evidence: 1                    # 至少 1 条外部 evidence
    supporting_claims: 0           # 不要求低层 Claim 支撑
    allowed_support_types: []      # factual 不能引用任何 Claim 类型作为支撑
  inference:
    evidence: 0                    # evidence 和 supporting_claims 至少满足一个
    supporting_claims: 0
    evidence_or_claims_min: 1      # evidence + supporting_claims 总数 ≥ 1
    allowed_support_types:         # 只能引用 factual 作为支撑
      - factual
  preference:
    evidence: 1                    # 至少 1 条 evidence（人类确认来源）
    supporting_claims: 0
    evidence_or_claims_min: 1
    allowed_support_types:         # 可以引用 factual 和 inference
      - factual
      - inference
    requires_human_source: true    # evidence 中必须有人类来源
  constraint:
    evidence: 1                    # 至少 1 条 evidence
    supporting_claims: 1           # 至少 1 条低层 Claim 支撑
    evidence_or_claims_min: 2      # 总支撑数 ≥ 2
    allowed_support_types:         # 可以引用 factual、inference、preference
      - factual
      - inference
      - preference
    requires_manual_review: true   # 必须人工审核
```

**校验逻辑：**

```text
validate_support(claim):
  rule = policy.min_support[claim.type]

  # 1. evidence 数量检查
  if len(claim.evidence) < rule.evidence:
    reject("insufficient evidence")

  # 2. supporting_claims 数量检查
  if len(claim.supporting_claims) < rule.supporting_claims:
    reject("insufficient supporting claims")

  # 3. 总支撑数检查
  total = len(claim.evidence) + len(claim.supporting_claims)
  if total < rule.evidence_or_claims_min:
    reject("insufficient total support")

  # 4. 支撑类型层级检查
  for sc in claim.supporting_claims:
    referenced = load_claim(sc.claim_id)
    if referenced.type not in rule.allowed_support_types:
      reject(f"cannot cite {referenced.type} as support for {claim.type}")

  # 5. 人类来源检查
  if rule.requires_human_source:
    if not any(e.source_type in ["manual", "conversation"] for e in claim.evidence):
      reject("requires human source evidence")
```

## Schema

Claim 字段保持正交：语素结构表达"说了什么"，类型表达"这是什么知识"，支撑字段表达"凭什么相信"，生命周期字段表达"当前是否可用"。

| 字段 | 作用 | 正交维度 | 必须/可选 | 示例 |
|------|------|----------|-----------|------|
| `claim_id` | 稳定标识（全局自增 + type code） | 标识 | 必须 | `F-00042` |
| `subject` | 主体，Claim 关于什么 | 语素 | 必须 | `PKS Markdown` |
| `predicate` | 关系，Claim 断言什么 | 语素 | 必须 | `is_projection_of` |
| `object` | 客体，Claim 的值 | 语素 | 必须 | `accepted claims` |
| `qualifier` | 限定条件（自由文本） | 语素限定 | 可选 | `dev capsule · MVP 阶段` |
| `content` | 人类可读表述，投影 Markdown 的核心内容来源 | 展示 | 必须 | `PKS.md 是 Capsule 所有投影的聚合` |
| `type` | Claim 类型，决定支撑要求 | 分类 | 必须 | `factual`、`inference`、`preference`、`constraint` |
| `domain` | 所属领域，决定生命周期策略 | 分类 | 必须 | `dev` |
| `tags` | 查询、投影、策略分组 | 分类 | 必须 | `["projection", "p1"]` |
| `supporting_claims` | 被本 Claim 引用的低层 Claim | 支撑 | 与 evidence 不可同时为空 | `F-00007 supports` |
| `evidence` | 外部或手工来源 | 支撑 | 与 supporting_claims 不可同时为空 | `source_type: file` |
| `status` | 生命周期状态 | 生命周期 | 必须 | `candidate`、`accepted` |
| `confidence` | 创建者自评，用于审核分流 | 生命周期 | 必须 | `1.0`（人类默认） |
| `created_at` | 创建时间 | 来源 | 必须 | `2026-05-10T10:00:00+08:00` |
| `created_by` | 创建者 | 来源 | 必须 | `human`、`kernel`、`agent:codex` |
| `valid_until` | 失效日期 | 生命周期 | 可选 | `null`（无限期有效） |
| `last_verified` | 最近校验日期 | 生命周期 | 可选 | `2026-05-10` |
| `supersedes` | 被本 Claim 替代的 Claim | 关系 | 可选 | `F-00001` |
| `superseded_by` | 替代本 Claim 的 Claim | 关系 | 可选（可反向查询） | `F-00050` |
| `project` | 所属 Capsule | 归属 | 必须 | `pks` |

**已精简的字段：**
- `qualifier`：从结构化（scope/condition/temporal）简化为自由文本。Kernel 只用它判断"两条 Claim 是否在谈同一个 scope"，不需要理解内部结构。
- `valid_from`：已移除。绝大多数情况下等于 `created_at`。如需"预设生效日期"，用 `qualifier` 表达。

**confidence 语义：**
- 人类创建：默认 1.0（人类对自己的主张负责）
- Agent 创建：由 Agent 自评（0.3~0.9）
- Kernel 创建（Audit）：固定 1.0
- Kernel 不计算或修改 confidence，它只是 ReviewStrategy 的分流输入

### SupportingClaim

`supporting_claims` 引用已存在的低层 Claim。它不是独立知识实体，只表达 Claim 之间的支撑关系。

| 字段 | 作用 | 示例 |
|------|------|------|
| `claim_id` | 被引用 Claim | `F-00007` |
| `relation` | 支撑关系 | `supports` |
| `note` | 可选说明 | `作为本条推断的事实前提` |

```yaml
supporting_claims:
  - claim_id: F-00007
    relation: supports
    note: "作为本条推断的事实前提"
```

### Evidence

`evidence` 表示外部或手工来源，是 Claim 可信度的基础。

| 字段 | 作用 | 示例 |
|------|------|------|
| `source_ref` | 来源定位 | `src/pks/kernel/facade.py` |
| `source_type` | 来源类型，决定可检查性 | `file`、`url`、`manual`、`command`、`conversation`、`kernel_event` |
| `relation` | 证据关系 | `supports`、`weak_supports`、`contradicts`、`supersedes` |
| `excerpt` | 可检查摘录 | `class Kernel:` |
| `locator` | 可选细定位 | `line:32`、`commit:abc123` |

```yaml
evidence:
  - source_ref: "src/pks/kernel/facade.py"
    source_type: file
    relation: supports
    excerpt: "class Kernel:"
    locator: "line:32"
```

**source_type 语义：**

| source_type | 含义 | 可检查性 | 适用场景 |
|-------------|------|----------|----------|
| `file` | 项目文件引用 | 高：可检查文件存在性和 excerpt 匹配 | 代码、文档引用 |
| `url` | 外部 URL | 中：可检查 URL 可达性 | 外部文档、API 文档 |
| `manual` | 人工手动输入 | 低：只能信任人类 | 口头决策、经验判断 |
| `command` | 命令执行结果 | 高：可重新执行验证 | 测试结果、系统状态 |
| `conversation` | 对话记录 | 低：依赖对话上下文 | 讨论结论、需求确认 |
| `kernel_event` | Kernel 内部事件 | 高：系统自动生成 | Audit Claim 专用 |

## 创建规则

按类型分别定义创建规则：

| 类型 | 创建者 | evidence 要求 | supporting_claims 要求 | 审核要求 |
|------|--------|---------------|------------------------|----------|
| `factual` | 人类或 Agent | ≥ 1 条 | 不要求 | 低（可 auto_accept） |
| `inference` | 人类或 Agent，必须有来源 | ≥ 0 条（但总支撑 ≥ 1） | ≥ 0 条（但总支撑 ≥ 1） | 中（建议人工确认） |
| `preference` | 人类为主 | ≥ 1 条（含人类来源） | ≥ 0 条 | 中到高 |
| `constraint` | 人类为主 | ≥ 1 条 | ≥ 1 条 | 高（必须人工审核） |

**通用规则：**
- 无 `evidence` 且无 `supporting_claims` 的 Claim 非法。
- `factual` Claim 不能把 `inference`、`preference`、`constraint` 当作支撑。
- `inference` Claim 不能只靠一句无来源判断创建。
- `preference` Claim 如果表示用户偏好，必须有人工确认来源。
- `constraint` Claim 必须人工审核；Agent 只能提交 candidate。
- Audit Claim 由 Kernel 创建，`type=inference`，`created_by=kernel`。
- TasteAndStyle 本质是 `type=preference` 的 Claim，不使用特殊格式。

## Audit Claim

审计记录也是 Claim，`type=inference`。Kernel 从操作事件推断出"某个状态变化发生过"，并把它写成不可手工接受的系统 Claim。

Audit Claim 不保存 rejected candidate 正文，只记录动作、对象 id、时间、操作者和最小 evidence。

```yaml
claim_id: I-00201
subject: "review candidate I-00042"
predicate: "was_rejected_by"
object: "human"
content: "Candidate I-00042 was rejected by human review."
type: inference
domain: dev
tags: ["audit", "review"]
status: accepted
confidence: 1.0
created_by: kernel
project: pks
evidence:
  - source_ref: "kernel_event:review.reject"
    source_type: kernel_event
    relation: supports
    excerpt: "candidate_id=I-00042 actor=human action=reject"
    locator: "2026-05-10T10:00:00+08:00"
```

## 生命周期

```text
submit_candidate
  ↓
ReviewStrategy（基于 min_support + 领域策略）
  ├── reject recommendation（支撑不足 / 层级违规 / confidence < 0.3）
  ├── manual review（有冲突 / constraint / TasteAndStyle）
  └── auto_accept recommendation（factual + 超阈值 + 支撑充分）
        ↓ 人工确认；后续阶段可策略自动合并
accepted
  ├── disputed（新证据矛盾 / 项目文件变更）
  ├── expired（valid_until 到期）
  └── superseded（被新 Claim 替代）
```

状态枚举只包含：
- `candidate`
- `accepted`
- `disputed`
- `expired`
- `superseded`

`stale` 是计算属性，不进入状态枚举。

`mark_claim_stale` 只记录一次 stale 检查结果，不改变 `ClaimStatus`。如果 evidence 失效或超过领域 stale 周期，Claim 会在 health、PKS.md 和 projection 中被视为 stale，但仍保持原状态。

P0/P1 不开启候选 Claim 自动合并。P1 中 `auto_accept` 只作为审核建议；后续在 candidate/review 闭环稳定后，再基于领域策略开放高置信 factual Claim 自动合并。

## 冲突规则

冲突 key 是 `(subject, predicate)`。

当前规则：
- 相同 `(subject, predicate)` 且不同 `object`：潜在冲突。
- 新 Claim 被接受时若发现冲突，新旧 Claim 都进入 `disputed`。
- 如果双方 `qualifier` 不同，视作 scoped complement，不自动冲突。
- `supersedes` 必须指向相同 `(subject, predicate)` 的旧 Claim。
- 支撑关系不能违反类型层级。

## 审核策略

`ReviewStrategy` 读取领域级 `claim_policy.yaml`，并同时考虑 Claim 类型和 `min_support`：

- `min_support` 不满足：reject recommendation。
- confidence `< 0.3`：reject recommendation。
- 类型层级违规：reject recommendation。
- 有冲突：manual review。
- `constraint`、TasteAndStyle、架构边界类 Claim：manual review。
- `factual` 达到领域阈值且 `min_support` 满足：auto_accept recommendation。

P1 不因 auto_accept recommendation 自动合并 candidate。自动合并是后续阶段用于降低人工审核负担的能力。

## 存储

项目 Claim：

```text
~/.pks/capsules/<project_id>/claims/<claim_id>.yaml
```

领域 TasteAndStyle Claim：

```text
~/.pks/domains/<domain>/taste_and_style/claims/<claim_id>.yaml
```

P1 Candidate Claim 独立存放：

```text
~/.pks/capsules/<project_id>/candidates/<claim_id>.yaml
```

Audit Claim 与普通 accepted Claim 使用同一存储，通过 `type=inference` 与 `tags: ["audit"]` 区分。

## Context 与投影过滤

`PKS.md` 是 Content Pack 本身。两者是同一概念，使用同一套 projection 规则。

默认面向 Agent 的上下文投影只输出：
- `accepted`
- 未过期
- 未被替代
- 非 stale

以下不会进入默认上下文：
- candidate
- disputed
- expired
- superseded
- computed stale

其他 Markdown 投影可以定义自己的 Claim 过滤规则。人或 Agent 通过 Kernel 接口编辑投影内容；未经 Kernel 接受的修改不改变长期状态。

## Evidence 检查

`ProjectTracker` 检查每条 evidence：
- `source_type=manual` 或 `conversation`：P0/P1 跳过本地文件完整性检查。
- `source_type=file`：文件不存在 → evidence issue；excerpt 不在文件中 → evidence issue。
- `source_type=command`：后续可重新执行验证。
- `source_type=url`：后续可检查 URL 可达性。

evidence issue 会使 accepted Claim 在健康检查和默认 Context 生成中被视为 stale。
