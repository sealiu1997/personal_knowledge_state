# PKS：个人知识状态管理平台 · 产品设计文档 v2

---

## 1. 产品定义

PKS（Personal Knowledge State）是一个本地优先的个人知识状态管理平台。

核心目标：

> 维护一份关于项目的、足够准确且不过时的知识状态，让人和 Agent 通过阅读它，就能快速理解并入手这个项目。

PKS 维护的是项目的**知识状态进行时**——不替代项目中已有的开发文档、API 文档或测试报告，而是一份足够精炼的、随项目演进持续更新的状态摘要。

---

## 2. 核心问题与立场

过去几年的 AI 个人知识库方案（RAG、Agent 记忆、LLM Wiki）始终没有解决同一组底层问题：资料越来越多，系统不一定越来越懂用户；模型不知道哪些判断已过时、哪些有证据、哪些只是临时想法。

根源不在模型能力或存储方案，而在于**没有人为"什么算知道"这件事负责**。

PKS 的立场：

> **模型负责提议，系统负责权威。**

什么能成为长期知识、什么时候失效、谁有权写入，由系统的硬架构保障。

---

## 3. 架构总览：三层解耦

```
┌──────────────────────────────────────────────┐
│                  资产层                        │
│  项目文件夹 · 代码仓库 · 文档 · 素材 · Git    │
└───────────────────┬──────────────────────────┘
                    │ 跟踪 / 索引
┌───────────────────▼──────────────────────────┐
│                控制层（PKS）                    │
│  Kernel · Claim · Policy · Projection         │
│  Task Contract · Candidate · Snapshot · Audit │
└───────────────────┬──────────────────────────┘
                    │ PKS.md / MCP / CLI
┌───────────────────▼──────────────────────────┐
│                  执行层                        │
│  Claude Code · Codex · Cline · Roo Code       │
│  OpenHands · Aider · 其他 Agent               │
└──────────────────────────────────────────────┘
```

**各层职责：**

| 层 | 负责 | 禁止 |
|---|---|---|
| 资产层 | 代码、文档、素材、Git 变更历史 | — |
| 控制层（PKS） | 项目状态、主张、证据、权限、上下文、审核、快照 | 禁止接管或重组项目文件夹结构 |
| 执行层 | 按任务合约执行操作、生成 patch/候选 | 禁止绕过 Candidate Queue 直接修改长期知识状态 |

### 3.1 项目文件夹跟踪

PKS 不接管项目文件夹，但**必须跟踪**项目文件夹的关键变更，防止主张与事实漂移。

#### 跟踪什么

不需要跟踪项目的所有文件，只需要跟踪与已有 Claim 的 `evidence.source_ref` 相关的文件，以及用户在 `project.yaml` 中显式声明的关键文件（架构文档、配置文件等）。

```yaml
# project.yaml 中的跟踪配置
tracking:
  project_path: "~/code/personal_knowledge_state"
  git_remote: "git@github.com:user/repo.git"
  watched_paths:                    # 显式声明要跟踪的文件/目录
    - "docs/architecture.md"
    - "src/core/**"
    - "pyproject.toml"
  auto_watch_evidence: true         # 自动跟踪所有 evidence.source_ref 引用的文件
```

#### 候选实现思路

**思路 A：Git Diff 驱动（推荐起步方案）**

利用项目已有的 Git 历史，PKS 记录上次同步时的 commit hash，下次同步时对比 diff：

```
pks sync <project>
  1. 读取上次记录的 commit hash
  2. git diff <old_hash>..HEAD -- <watched_paths>
  3. 对每个变更文件，查找引用了该文件的 Claim
  4. 如果文件内容与 Claim 的 evidence.excerpt 不再匹配 → 标记 Claim 为 stale
  5. 记录新的 commit hash
```

优势：零额外依赖，复用 Git 基础设施，diff 精确。
局限：只对 Git 项目有效；无法检测语义级变化（文件改了但结论仍成立）。

**思路 B：文件指纹跟踪**

对 watched_paths 中的每个文件计算内容 hash，存入 PKS 数据库。定期或按需比对：

```yaml
# PKS 内部维护的指纹记录
file_fingerprints:
  - path: "docs/architecture.md"
    hash: "sha256:abc123..."
    last_checked: "2026-05-09"
    referenced_by: ["F-00012", "F-00035"]
```

优势：不依赖 Git，适用于任何项目；可以关联到具体 Claim。
局限：只能检测"文件变了"，不能判断"变了什么"。

**思路 C：Evidence 引用完整性检查**

不主动跟踪文件，而是在特定时机（`pks health`、`PKS.md` 生成时）检查所有 accepted Claim 的 `evidence.source_ref` 是否仍然有效：

```
对每条 accepted Claim:
  对每条 evidence:
    1. source_ref 指向的文件是否存在？
    2. excerpt 内容是否仍能在文件中找到？
    3. 如果找不到 → Claim 标记为 stale，附注 "evidence source changed"
```

优势：最简单，不需要额外的跟踪机制。
局限：被动检测，不能实时发现变化。

#### 建议

MVP 采用**思路 A + C 结合**：用 Git Diff 做主动跟踪，用 Evidence 引用检查做被动兜底。非 Git 项目退化为纯思路 C。

---

## 4. 知识胶囊体系

### 4.1 胶囊继承体系

借鉴面向对象编程的类与继承：BaseCapsule 定义最小通用结构，领域胶囊从中派生，具体项目从领域胶囊实例化。

```
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

### 4.2 BaseCapsule 最小结构

BaseCapsule 的长期知识事实源只有 Claims。Markdown 可以存在，但内容和规则修改必须通过 Kernel 投影接口完成。

| 文件 | 职责 | 必须 |
|------|------|------|
| `project.yaml` | 机器可读注册信息（id、类型、领域、外部路径、仓库、tracking） | ✅ |
| `claims/` | accepted Claim 目录，每条 Claim 必须有支撑来源 | ✅ |
| `candidates/` | 待审核 Candidate Claim 目录 | P1 |
| `PKS_PROJECT.md` | 项目定义与边界的 Claim 投影 | ✅ |
| `journal.md` | 决策、经验、进展类 Claim 的时间线投影 | 选配 |

**不存储的文件：**
- `context.md` → 不单独存在；`PKS.md` 就是写入项目根的 Content Pack 投影

### 4.3 领域胶囊扩展模块

各领域在 BaseCapsule 基础上增加正交的领域特有投影：

| 领域 | 扩展模块 | 说明 |
|------|----------|------|
| **ContentCapsule** | `outline.md` · `facts.md` | 大纲类 Claim · factual Claim 核查投影 |
| **DevCapsule** | `architecture.md` · `tasks.md` | 架构/约束/决策 Claim · 任务相关 Claim |
| **ResearchCapsule** | `terminology.md` · `hypotheses.md` | 术语 Claim · 假设与待验证 Claim |

这些 Markdown 文件均由 ProjectionEngine 生成。人或 Agent 通过 Kernel 接口修改投影内容和规则。项目可以定义自定义投影。

### 4.4 project.yaml 边界

`project.yaml` 保留为最小运行时注册表，不全量 Claim 化。它只保存加载 Capsule 所需的 id、类型、领域、外部路径、仓库和 tracking 配置。

项目阶段、目标、交付物和约束迁移为 Claims，并默认进入 `PKS_PROJECT.md` 投影。这样既避免 Kernel 自举循环，又让会演化的项目状态进入 Claim 的 evidence、生命周期、替代和投影机制。

### 4.5 TasteAndStyle 模块

TasteAndStyle 是跨项目的偏好与风格约定，按 Capsule 继承层级组织。每一层派生都可以有自己的 TasteAndStyle，注入时按继承链从上到下合并。

#### 多级 TasteAndStyle

```text
domains/dev/taste_and_style/              ← 领域级（所有 dev 项目共享）
domains/dev/types/software/taste_and_style/  ← 类型级（所有 SoftwareCapsule 共享）
domains/content/taste_and_style/          ← 领域级
domains/content/types/article/taste_and_style/ ← ArticleCapsule 共享
domains/content/types/video/taste_and_style/   ← VideoCapsule 共享
domains/content/types/game/taste_and_style/    ← GameCapsule 共享
```

注入顺序：领域级 → 类型级。同 `(subject, predicate)` 时，更具体的层级覆盖上层。

#### 为什么需要多级

不同 `capsule_type` 之间的偏好差异可能很大：
- `ArticleCapsule` 和 `VideoCapsule` 的内容风格完全不同
- `DisciplineCapsule` 和 `ModelCapsule` 的研究方法论不同
- `SoftwareCapsule` 和 `PluginCapsule` 的差异相对较小

领域级 TasteAndStyle 记录该领域的通用偏好；类型级 TasteAndStyle 记录该类型的特有偏好。

#### 基本组成

TasteAndStyle 的基本组成单元是 Claim（`type: preference`）：

```yaml
# ~/.pks/domains/dev/taste_and_style/claims/P-00001.yaml
claim_id: "P-00001"
subject: "代码风格"
predicate: "prefers"
object: "函数式风格，避免深层继承"
content: "偏好函数式风格，避免深层继承"
type: preference
domain: dev
status: accepted
confidence: 1.0
created_by: human
evidence:
  - source_ref: "manual"
    source_type: manual
    relation: supports
    excerpt: "用户手动设定"
```

#### 规则

- 初始为空
- 惜字如金，只记录真正跨项目通用的偏好
- **强制人工审核**，不允许自动接受
- 尽量手工维护，Agent 只能提交候选建议
- 生成 PKS.md 时，按继承链注入对应层级的 TasteAndStyle Claim
- 同 `(subject, predicate)` 冲突时，类型级覆盖领域级

这替代了全局胶囊的角色——跨项目知识不需要一个独立的"全局知识库"，只需要每个继承层级有一份足够克制的风格共识。且因为它本身就是 Claim，可以复用整个 Claim 系统的生命周期、审核和过期机制。

---

## 5. Claim 系统: 基础数据结构设计

### 5.1 为什么是 Claim

长期知识的基本单位不是文件、段落或 Markdown 页面，而是**主张（Claim）**。

主张是可以被精确验证、反驳、过期和替换的最小知识单元。段落很难被精确反驳——你不能告诉系统「这一大段有点不对」。但你可以说：「这条主张的证据不成立了。」系统就能处理。

PKS 不单独设计 Fact 实体。Fact 是 `type=factual` 的 Claim，是 Claim 层级中最基础的一层。Capsule 是 Claim 的组织与投影容器，不是第三种知识实体。

### 5.1.1 知识分层模型

PKS 的知识结构是自底向上构建的：

```text
Evidence（证据：文件引用、URL、手工输入、命令结果）
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

**从下到上构建**：新项目从 0 开始积攒 Claim，逐步构建 Capsule 和投影。这是知识积累的路径。

**从上到下理解**：后来的维护者或 Agent 从 PKS.md 开始阅读，逐层向下拆解到自己理解为止。这是知识消费的路径。

### 5.2 为什么需要语素分解

Claim 不应只是一段自然语言文本。如果只存 `content: "PKS 使用 Python 技术栈"`，系统能做的事很有限——只能做全文匹配，无法精确判断两条 Claim 是否冲突、是否在谈同一件事。

将 Claim 分解为**主体（subject）、谓语（predicate）、客体（object）、限定条件（qualifier）**，可以解锁三个关键能力：

| 能力 | 原理 | 示例 |
|------|------|------|
| **自动冲突检测** | 相同 (subject, predicate) 不同 object = 潜在冲突 | PKS `uses_stack` Python vs PKS `uses_stack` Node.js |
| **精确替代追踪** | supersedes 可验证是否针对同一 (subject, predicate) | 确保新旧 Claim 说的是同一件事 |
| **结构化查询** | 按 subject / predicate / domain 筛选聚合 | 「所有关于架构的主张」= predicate contains `design/architecture` |

### 5.3 Claim 数据结构

```yaml
claim_id: "F-00042"

# -- 语素结构（必须） --
subject: "PKS MVP"                      # 主体: 关于什么
predicate: "uses_stack"                  # 谓语: 什么关系
object: "Python + FastAPI + SQLite"      # 客体: 具体内容
qualifier: "后端 · 单用户本地部署 · MVP 阶段"  # 限定条件（可选，自由文本）

# -- 自然语言描述（必须，投影 Markdown 的核心内容来源） --
content: "PKS 的 MVP 后端技术栈选择 Python + FastAPI + SQLite（单用户本地部署场景）"

# -- 分类（必须） --
type: factual                 # factual | inference | preference | constraint
domain: dev                   # content | dev | research
tags: ["tech-stack", "mvp"]

# -- 支撑 Claim（可选，高层 Claim 可引用低层 Claim） --
supporting_claims:
  - claim_id: "F-00007"
    relation: supports
    note: "作为技术栈选择的事实前提"

# -- 外部证据（不可与 supporting_claims 同时为空） --
evidence:
  - source_ref: "manual:2026-05-08-tech-decision"
    source_type: manual
    relation: supports         # supports | weak_supports | contradicts | supersedes
    excerpt: "综合考虑本地优先和生态成熟度，选择 Python 栈"
    locator: null              # 可选：行号、commit、hash 等细定位

# -- 生命周期（必须） --
status: accepted              # candidate | accepted | disputed | expired | superseded
confidence: 0.9               # 创建者自评，人类默认 1.0
created_at: "2026-05-08T10:00:00+08:00"
created_by: human             # human | kernel | agent:<agent_name>
valid_until: null              # 可选：null = 无限期有效
last_verified: "2026-05-08"

# -- 关系（可选） --
supersedes: null               # 被本条替代的旧 Claim ID
superseded_by: null            # 替代本条的新 Claim ID（可由反向查询得到）
project: "pks"
```

**字段正交性说明：**

| 维度 | 字段 | 必须/可选 |
|------|------|-----------|
| 标识 | `claim_id` | 必须 |
| 语素 | `subject`, `predicate`, `object` | 必须 |
| 语素限定 | `qualifier` | 可选（自由文本，用于冲突检测时判断 scope） |
| 展示 | `content` | 必须（投影 Markdown 的核心内容来源） |
| 分类 | `type`, `domain`, `tags` | 必须 |
| 支撑 | `supporting_claims`, `evidence` | 不可同时为空 |
| 生命周期 | `status`, `confidence`, `created_at`, `created_by`, `last_verified` | 必须 |
| 生命周期 | `valid_until` | 可选 |
| 关系 | `supersedes`, `superseded_by` | 可选 |
| 归属 | `project` | 必须 |

**已移除的字段：**
- `valid_from`：绝大多数情况下等于 `created_at`，不再单独维护。如果需要"预设生效日期"的场景，用 `qualifier` 表达时间限定。

### 5.4 Claim 类定义（Python）

```python
@dataclass
class Evidence:
    source_ref: str                # 资料索引（强制）
    source_type: str               # file | url | manual | command | conversation | kernel_event
    relation: Relation             # supports | weak_supports | contradicts | supersedes
    excerpt: str                   # 原文摘录
    locator: str | None = None     # 可选：行号、commit、hash、时间点等

@dataclass
class SupportingClaim:
    claim_id: str                  # 被引用的低层 Claim
    relation: Relation
    note: str = ""

class ClaimType(Enum):
    FACTUAL = "factual"
    INFERENCE = "inference"
    PREFERENCE = "preference"
    CONSTRAINT = "constraint"

class ClaimStatus(Enum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    DISPUTED = "disputed"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"

@dataclass
class Claim:
    claim_id: str

    # 语素结构（必须）
    subject: str
    predicate: str
    object: str
    qualifier: str | None = None   # 自由文本限定条件

    # 自然语言（必须，投影 Markdown 的核心内容来源）
    content: str = ""

    # 分类（必须）
    type: ClaimType = ClaimType.FACTUAL
    domain: str = ""
    tags: list[str] = field(default_factory=list)

    # 支撑（两者不可同时为空）
    supporting_claims: list[SupportingClaim] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    # 生命周期（必须）
    status: ClaimStatus = ClaimStatus.CANDIDATE
    confidence: float = 1.0        # 创建者自评，人类默认 1.0
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "human"      # human | kernel | agent:<name>
    valid_until: date | None = None
    last_verified: date | None = None

    # 关系（可选）
    supersedes: str | None = None
    superseded_by: str | None = None
    project: str = ""
```

### 5.5 Claim ID 生成规则

格式：`<type_code>-<global_sequence>`

| type | code |
|------|------|
| factual | F |
| inference | I |
| preference | P |
| constraint | C |

示例：`F-00042`、`I-00017`、`P-00003`、`C-00008`

- 全局自增序号，存储在 `~/.pks/config.yaml` 计数器中。
- 所有 Claim（项目 Claim、TasteAndStyle Claim、Audit Claim）共用同一个计数器。
- type 是唯一不可变的枚举元数据，编码进 ID 提供可读性。
- ID 不编码时间戳、作用域或可变元数据。

### 5.6 冲突检测逻辑

```
当新 Claim 提交时:
  1. 查找所有 (subject, predicate) 相同的已接受 Claim
  2. 如果 object 不同 -> 标记为潜在冲突，两条均进入 disputed
  3. 如果 qualifier 不同但 object 相同 -> 可能是互补，不冲突
  4. 如果新 Claim 声明 supersedes 旧 Claim -> 验证 (subject, predicate) 一致性
```

### 5.7 Claim 类型、支撑层级与默认审核级别

| 层级 | 类型 | 含义 | 支撑规则 | 默认审核 |
|------|------|------|----------|---------|
| 0 | `factual` | 事实性观察 | 直接 evidence；人类可用 manual evidence 创建 | 低（P0/P1 给出 auto_accept 建议；后续可自动合并候选） |
| 1 | `inference` | 推断性判断 | 必须有外部 evidence 或 accepted factual Claim 支撑 | 中（建议人工确认） |
| 2 | `preference` | 个人偏好、风格取舍 | 必须有人类确认来源，或由低层 Claim 支撑 | 中到高 |
| 3 | `constraint` | 约束与禁止 | 必须有清晰来源或低层 Claim 支撑，必须人工审核 | 高（必须人工确认） |

高层 Claim 可以把低层 Claim 作为支撑；低层 Claim 不能把高层 Claim 当作支撑。同层 Claim 可以关联，但不能作为主要 evidence。

### 5.8 领域级生命周期策略

Claim 的生命周期管理应基于领域和类型微调。每个领域胶囊可配置 `claim_policy.yaml`，包含两部分：生命周期策略和最低支撑要求。

```yaml
domain: dev

# -- 生命周期策略 --
lifecycle:
  factual:
    stale_after_days: 180        # 代码事实变化快
    auto_accept_threshold: 0.85
  inference:
    stale_after_days: 90
    auto_accept_threshold: null   # 不自动接受
  preference:
    stale_after_days: null
    auto_accept_threshold: null
  constraint:
    stale_after_days: null        # 约束不自动过期
    auto_accept_threshold: null

# -- 最低支撑要求（按 Claim 类型递进） --
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

manual_review_types: [inference, preference, constraint]

# 对比：content 领域
# domain: content
# lifecycle:
#   factual:
#     stale_after_days: 365       # 内容事实相对稳定
```

**设计原则：** 类型层级越高，要求的支撑越多、审核越严格。这保证了知识链的可靠性——从任何一条高层 Claim 出发，都能向下追溯到具体的 Evidence。

### 5.9 Claim 生命周期

```
候选提出 → 策略审核 → 接受/拒绝
                         ↓
                    长期生效
                         ↓
              定期验证 / 新证据 / 项目变更触发
                         ↓
              过期 / 争议 / 被替代
```

### 5.10 Audit Claim

Audit 也是 Claim，`type=inference`。Kernel 从操作事件推断出“某个状态变化发生过”，并写入 accepted Claim。

Reject 不保存 rejected candidate YAML，也不把 rejected 正文写入 Audit Claim。字段细节见 Claim 设计文档。

---

## 6. Review Strategy Engine

### 6.1 三级审核

| 级别 | 触发条件 | 处理方式 |
|------|----------|----------|
| **自动合并候选** | `type=factual` 且 confidence ≥ 阈值 且有 evidence | 后续阶段开放：策略驱动合并 + Audit Claim |
| **批量审核** | `type=inference/preference` 或置信度中等 | 进入队列，通过 Web UI 或 `pks review` 批量处理 |
| **强制人工** | `type=constraint` 或涉及 guardrails/架构/TasteAndStyle | 逐条确认 |

P0/P1 不开启候选 Claim 自动合并。P1 中 `auto_accept` 只作为 ReviewStrategy 的建议，用于降低人工判断成本；后续在审核闭环稳定后，再基于领域策略、证据完整性、冲突检查和审计要求开放高置信 Claim 的自动合并。

### 6.2 置信度语义

confidence 是 Claim 创建者的自评信号，用于 ReviewStrategy 分流。它不是精确概率，而是粗粒度的审核提示。

**打分规则：**

| 创建者 | 默认 confidence | 含义 |
|--------|----------------|------|
| 人类手动创建 | 1.0 | 人类对自己的主张负责 |
| Agent 提交，有强 evidence | 0.8~0.9 | Agent 有充分依据 |
| Agent 提交，有弱 evidence | 0.5~0.7 | Agent 有一些依据但不确定 |
| Agent 推测，无直接 evidence | 0.3~0.5 | Agent 猜测 |
| Kernel 自动生成（Audit） | 1.0 | 系统事件，确定发生 |

**ReviewStrategy 使用方式：**
- `< 0.3`：建议 reject
- `0.3 ~ 阈值`：进入人工审核队列
- `≥ 阈值`（且 `min_support` 满足）：建议 auto_accept（仅 factual）

Kernel 不计算或修改 confidence。它只是创建者的声明，ReviewStrategy 的输入。

阈值由领域级 `claim_policy.yaml` 配置。

---

## 7. 过期与维护

### 7.1 过期规则

| 规则 | 行为 |
|------|------|
| `valid_until` 到期 | 状态 → `expired` |
| `last_verified` 超过领域阈值 | 标记 `stale`（待重新验证） |
| 新 Claim `supersedes` 旧 Claim | 旧 Claim → `superseded` |
| 项目文件变更与 Claim 矛盾 | 标记 `disputed` |

### 7.2 健康检查

```bash
pks health
# ✓ 42 claims accepted
# ⚠ 3 claims stale (last verified > 90 days)
# ✗ 1 claim expired
# ⚡ 2 claims disputed
```

默认 `PKS.md` 生成时自动排除非 `accepted` 状态的 Claim。

---

## 8. 存储模型：独立存储 + Claim 投影

PKS 数据独立存储，不嵌入项目文件夹。项目通过投影文件 `PKS.md` 引用 PKS。

### 8.1 决策依据

曾考虑将胶囊嵌入项目（`.pks/` 目录），但决定采用独立存储，核心原因：

| 维度 | 嵌入项目 | 独立存储 ✅ |
|------|---------|-----------|
| Agent 误修改风险 | ⚠️ 高——Agent 可"顺手"修改 | ✅ 低——工作区不含 PKS 数据 |
| 独立同步 | ❌ 与项目 Git 混合 | ✅ 独立 Git，可单独同步 |
| 跨项目操作 | ❌ 需遍历所有项目 | ✅ 集中管理 |
| 多设备 | ❌ 每设备每项目独立副本 | ✅ 一份数据，独立同步 |

嵌入方案的优势（心智模型简单、胶囊随项目迁移）可以通过投影机制弥补。

**决定性因素**：PKS 的核心价值是"Agent 不能直接修改长期知识状态"。如果 PKS 数据在 Agent 工作目录里，这个保护就退化为 Prompt 约定——而 Prompt 约定正是 PKS 要替代的东西。

### 8.2 存储结构

```
~/.pks/                          ← PKS 独立存储（Git 管理）
├── capsules/
│   ├── pks-project/             ← 某个项目的胶囊
│   │   ├── project.yaml         ← 运行时注册信息
│   │   ├── claims/
│   │   ├── candidates/
│   │   ├── projections/
│   │   │   ├── PKS_PROJECT.md   ← Claim 投影
│   │   │   └── journal.md       ← Claim 投影
│   └── another-project/
├── domains/
│   ├── dev/
│   │   ├── taste_and_style/     ← 领域级 TasteAndStyle
│   │   │   └── claims/
│   │   ├── types/
│   │   │   ├── software/
│   │   │   │   └── taste_and_style/  ← 类型级 TasteAndStyle
│   │   │   │       └── claims/
│   │   │   └── plugin/
│   │   │       └── taste_and_style/
│   │   │           └── claims/
│   │   └── claim_policy.yaml
│   ├── content/
│   │   ├── taste_and_style/
│   │   │   └── claims/
│   │   ├── types/
│   │   │   ├── article/
│   │   │   │   └── taste_and_style/
│   │   │   │       └── claims/
│   │   │   ├── video/
│   │   │   │   └── taste_and_style/
│   │   │   │       └── claims/
│   │   │   └── game/
│   │   │       └── taste_and_style/
│   │   │           └── claims/
│   │   └── claim_policy.yaml
│   └── research/
└── config.yaml
```

### 8.3 项目引用机制

PKS 在项目文件夹中生成唯一的投影文件 `PKS.md`，作为项目与 PKS 之间的桥梁：

```
my-project/                      ← 项目文件夹
├── src/
├── docs/
├── .git/
└── PKS.md                       ← 唯一投影文件
```

`PKS.md` 是写入项目根的 Capsule 投影聚合。其内容包括：
- 项目简介与当前阶段（精选）
- 关键的已接受 Claim
- 权限边界与禁止事项
- **PKS 胶囊路径**（`~/.pks/capsules/pks-project/`）
- **MCP 接入提示**（便于 Agent 通过受控接口进一步查询）

`PKS.md` **不修改项目已有的 AGENTS.md、CLAUDE.md 或任何其他文件**。所有 Agent 均可自然读取。PKS 可随时重新生成。

所有 Markdown 投影都从 Claim 集合生成。人类或 Agent 通过 Kernel 接口修改投影内容和规则；未经 Kernel 接受的修改不改变长期状态。

---

## 9. PKS.md（Content Pack）与 Agent 接口

### 9.1 PKS.md 即 Content Pack

`PKS.md` 就是 Content Pack。不再维护两个概念——它是 PKS 最直接的价值输出，写入项目根目录，供人和 Agent 阅读。

**PKS.md 是 Capsule 所有投影的有序聚合**，内容按继承顺序拼接：

```text
PKS.md =
  BaseCapsule 投影（PKS_PROJECT.md 内容）
  + 领域 Capsule 投影（architecture.md / outline.md 等）
  + 项目自定义投影
  + TasteAndStyle 注入（领域级 → 类型级）
```

`render_context` 返回动态字符串，`render_projection` 写入文件。两者调用同一套 ProjectionEngine，按 Capsule 继承顺序渲染所有已定义投影并拼接。

`PKS.md` 是独立文件，**不修改项目的 AGENTS.md、CLAUDE.md 或任何其他已有文件**。所有 Agent 均可自然读取。PKS 可随时重新生成。

### 9.2 MCP 接口

PKS 的 MCP Server 暴露意图级接口：

- `get_project_context`
- `search_project`
- `get_task_contract`
- `submit_candidate_claim`
- `submit_patch`
- `request_permission`

Agent 通过 MCP 与 PKS 交互，不直接访问 PKS 文件。

---

## 10. 项目创建流程

### 10.1 `pks new`：填表式命令行

`pks new` 是一个结构化的填表命令，用户（或 Agent）填写核心参数后生成胶囊骨架。

这种设计的优势：
- **易于测试**：输入参数确定，输出可预期
- **人机共用**：人类可以手动填写，Agent 可以在充分理解用户意图后精确填写
- **可脚本化**：支持命令行参数直接传入，也支持交互式逐项填写

### 10.2 核心参数

```bash
pks new \
  --name "个人知识状态管理平台" \
  --domain dev \
  --type software \
  --goal "维护项目知识状态的准确性" \
  --stage "产品设计" \
  --deliverable "本地CLI工具 + MCP Server" \
  --project-path "~/code/personal_knowledge_state" \
  --git-remote "git@github.com:user/pks.git" \
  --constraints "投影内容和规则修改必须经 Kernel 接口" \
  --watched-paths "docs/**,src/core/**,pyproject.toml"
```

交互模式下逐项提示：

```
$ pks new
项目名称: 个人知识状态管理平台
领域 [content/dev/research]: dev
类型 [software/plugin]: software
核心目标: 维护项目知识状态的准确性
当前阶段: 产品设计
最终交付物: 本地CLI工具 + MCP Server
项目路径 (可选): ~/code/personal_knowledge_state
Git 仓库 (可选): git@github.com:user/pks.git
约束/禁止事项 (可选): 投影内容和规则修改必须经 Kernel 接口
跟踪路径 (可选): docs/**,src/core/**

--- 确认 ---
即将创建: DevCapsule > SoftwareCapsule
位置: ~/.pks/capsules/个人知识状态管理平台/
确认创建？[Y/n]: Y

✓ 胶囊已创建
✓ 初始 Claims 已生成
✓ PKS_PROJECT.md 已由 Claims 投影生成
✓ claims/ 目录已初始化
✓ project.yaml 已写入（含跟踪配置）
```

`stage`、`goal`、`deliverable`、`constraints` 是创建输入。Kernel 接受后应生成初始 Claims，不作为长期知识字段留在 `project.yaml`。

### 10.3 Agent 使用场景

Agent 在与用户充分讨论后，可以直接调用参数化命令创建胶囊，无需再次交互：

```bash
# Agent 在理解用户意图后，精确填写参数
pks new --name "..." --domain dev --type software \
  --goal "..." --stage "..." --project-path "..." --yes
```

`--yes` 跳过确认步骤（Agent 已在对话中获得用户确认）。

---

## 11. Web UI

### 11.1 为什么需要 Web UI

仅靠 CLI 存在明显短板：

| 场景 | CLI | Web UI |
|------|-----|--------|
| 审批候选 Claim | YAML 阅读体验差，逐条命令操作繁琐 | 列表视图、一键批量操作、证据预览 |
| Claim 状态总览 | `pks health` 输出纯文本 | 仪表盘、过滤、排序、颜色标记 |
| 证据链浏览 | 需要手动打开多个文件 | 点击跳转、关联展示 |
| 权限管理 | 编辑 YAML 配置 | 表单式配置、即时预览 |
| 项目切换 | 记住项目名，手动切换 | 项目列表、快速导航 |
| 非开发者用户 | 不友好 | 基本可用 |

### 11.2 定位

Web UI 是本地运行的轻量管理界面，不是云端 SaaS。

核心功能：
- **Claim 审核工作台**：候选队列、批量审批、证据预览、冲突标记
- **项目仪表盘**：状态总览、健康度、Claim 统计
- **知识浏览**：Claim 列表/搜索/过滤、证据链可视化
- **配置管理**：权限策略、审核策略、领域策略的可视化编辑

技术方案：Python (FastAPI) + 轻量前端（HTML/JS），本地启动，无需部署。

### 11.3 实现阶段

Web UI 不在 P0，但应纳入 MVP 范围：

- **P0-P1**：CLI 为主，验证核心闭环
- **P2**：Claim 审核工作台 + 项目仪表盘（最小 Web UI）
- **P3+**：完整管理界面

---

## 12. PKS Kernel

### 12.1 内核组件

```
PKS Kernel
├── Project Registry          # 项目注册与胶囊管理
├── Project Tracker           # 项目文件夹跟踪与变更检测
├── Claim Engine              # Claim CRUD、生命周期、冲突检测
├── Review Strategy Engine    # 审核分级与策略执行
├── Projection Engine         # Claim 集合到 Markdown / PKS.md 的投影
├── Policy Engine             # 权限策略
├── Candidate Queue           # 候选写入队列
├── Snapshot Manager          # 快照（复用 Git）
├── Audit Claim Factory       # 审计事件写成 inference Claim
└── Interface Adapters        # CLI / MCP / Web UI API
```

### 12.2 内核原则

1. Agent 不直接接触长期状态——所有写入经过 Candidate → Review → Merge
2. 所有操作绑定 Audit Claim
3. 所有 Markdown 都是 Claim 集合投影，编辑必须经 Kernel 规范
4. 快照复用 Git

---

## 13. 工具复用

PKS 只自研其他工具不负责的部分。

| 能力 | 复用 |
|------|------|
| 版本管理 | Git |
| 人类编辑 | VS Code / Obsidian |
| 代码执行 | Claude Code / Codex / Cline / Roo / OpenHands |
| Agent 接入 | MCP SDK |
| 资料处理 | LlamaIndex / LangGraph（可选） |

---

## 14. 技术栈

| 层 | 选型 |
|---|---|
| 文件资产 | Markdown + YAML + Git |
| 状态数据库 | SQLite |
| Claim 存储 | YAML 文件 + SQLite 索引 |
| 后端 | Python + FastAPI |
| CLI | Typer |
| Schema | Pydantic |
| Agent 接入 | MCP Server |
| Web UI | FastAPI + 轻量前端 |

---

## 15. MVP 分阶段计划

| 阶段 | 目标 | 核心交付 |
|------|------|----------|
| **P0** | Kernel 基线 | Capsule · Claim · `PKS.md` · health · tracking · audit · snapshot · CLI |
| **P1** | Claim 候选与审核闭环 | Claim schema 细化 · Candidate Queue · Review Engine · Review Strategy · `pks review` · Claim 查询筛选 · 领域策略校验 · Markdown 投影纪律 · Audit Claim |
| **P2** | 自动维护 + 最小 Web UI | 过期扫描 · 维护任务 · Claim 审核工作台 · 项目仪表盘 |
| **P3** | Agent 协作 | MCP Server · Policy Engine · Task Contract · Agent 说明文件生成 |

自动合并不属于 P0/P1。P1 先把 candidate/review 作为人工审核主路径跑稳；后续阶段再根据领域策略逐步开放高置信 factual Claim 的自动合并，以降低长期人工审核负担。

MVP 不做：移动端、多用户协作、全自动知识整理、Agent 全权写入、复杂知识图谱。

---

## 16. 设计原则

1. **状态优先**——维护准确的知识状态是系统的唯一核心目标
2. **模型提议，系统权威**——Agent 提交候选，系统决定什么能成为长期知识
3. **Claim 是一等公民**——长期知识的基本单位是结构化主张；Fact 是 factual Claim，不单独成实体
4. **知识自底向上构建**——Evidence 支撑 Fact，Fact 支撑高层 Claim，高层 Claim 组成 Capsule，Capsule 投影为 Markdown
5. **支撑层级递进**——类型越高，要求的支撑越多、审核越严格；低层不能引用高层作为支撑
6. **审核可承受**——通过领域级策略和 `min_support` 分级，控制人工审核量
7. **知识会过期**——系统必须有过期、替代和冲突处理机制
8. **三层解耦**——资产归资产、控制归控制、执行归执行
9. **跟踪不接管**——PKS 跟踪项目文件夹变更，但不重组项目结构
10. **粗糙启动，逐步结构化**——允许最小结构启动，渐进沉淀
11. **投影不是事实源**——所有 Markdown 都是 Claim 集合投影，不允许自由文本，编辑必须经 Kernel 规范
12. **充分引导，确认后行动**——项目创建前先讨论清楚，用户确认后再生成

---

## 17. 成功标准

| 指标 | 验证方式 |
|------|----------|
| 新项目 5 分钟内启动 | `pks new` 端到端计时 |
| Agent 减少重复询问 | 对比有/无 PKS 时的背景提问次数 |
| Claim 可追溯到证据 | 抽查 accepted Claim 的 evidence 完整性 |
| 过期 Claim 能被发现 | `pks health` 标记 stale/expired |
| Agent 无法直接修改核心状态 | 尝试绕过 Candidate Queue 应失败 |
| 审核负担可接受 | P1 先统计 auto_accept 建议比例；后续自动合并启用后，目标为自动合并率 > 60%，人工审核 < 每周 20 条 |
| Claim 审批体验可用 | Web UI 审核工作台可完成批量审批 |
| 真实项目持续使用 | dogfood 超过 30 天 |

---

## 附录：引用与历史资料

以下资料不是本 v2 文档的替代版本，而是问题背景、早期规划和架构增量的来源。实现时以本文档正文为准。

P0 当前实现同步文档：
- [PKS Kernel 设计](./pks_kernel_design.md)
- [PKS Claim 设计](./pks_claim_design.md)
- [PKS Capsule 设计](./pks_capsule_design.md)
- [PKS Projection 设计](./pks_projection_design.md)

- [吹了几年的 AI 个人知识库，为什么还是那么难用？Karpathy 的 Wiki 并不是解决方案…【技术文章】](../history/吹了几年的%20AI%20个人知识库，为什么还是那么难用？Karpathy%20的%20Wiki%20并不是解决方案…【技术文章】.md)：李自然文章，提供“长期知识状态无法稳定运行”的问题背景。
- [个人知识状态库：产品规划文档](../history/personal_knowledge_state_product_plan.md)：早期产品规划，保留项目定位、核心判断和 MVP 原始范围。
- [个人知识状态库：增量设计文档——解耦架构与工具复用](../history/pks_incremental_notes_architecture_and_tooling.md)：补充三层解耦、工具复用、MCP/Agent 接入边界等设计来源。
