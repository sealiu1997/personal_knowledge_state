---
name: pks
description: PKS（个人知识状态）是项目的知识状态控制平面。当你在任何由 PKS 管理的项目中工作时使用此 skill（项目根目录下存在 PKS.md 文件）——读取项目上下文、提交有证据支撑的知识、管理项目 Markdown 投影、在源头变更后验证 Claims、或为新项目设置 PKS。
---

# PKS — 个人知识状态

## 核心作用

PKS 管理项目的知识状态，让 Agent 和人类无需阅读所有源码和文档就能快速掌握：
- 项目当前状态和目标
- 关键架构决策和技术选型
- 风格偏好和约定
- 约束和禁止事项
- 经验教训和已知陷阱

所有知识都可以溯源——每条知识都关联到具体的证据来源（代码文件、文档、对话记录等）。

## 结构原理

PKS 有三层核心概念：

```
Evidence（证据：文件引用 + excerpt 原文摘录）
  ↑ 支撑
Claim（主张：结构化的知识单元，有类型和支撑要求）
  ↑ 组织
Capsule（胶囊：按项目组织 Claims 的容器）
  ↑ 投影
Markdown（PKS.md / PKS_PROJECT.md / journal.md / 领域 MD / 自定义 MD）
```

- **Evidence**：知识的来源证据。包含 `source_ref`（来源路径）和 `excerpt`（原文摘录——从源文件精确复制的文本片段，用于自动验证来源是否仍然有效）。
- **Claim**：最小知识单元。由 subject（主体）、predicate（谓语）、object（客体）构成语素结构，加上 content（人类可读描述）和 evidence（证据）。
- **Capsule**：项目知识容器。按 capsule_type 和 domain 组织 Claims，决定默认生成哪些 Markdown 投影。
- **Markdown 投影**：Claims 的可读映射。每个 MD 文件由 ProjectionSpec（投影规则）定义，从 Claims 集合中筛选、排序、渲染生成。PKS.md 是所有投影的聚合。

**关键原则**：所有 PKS 生成的 Markdown 都是 Claim 的投影，不是手写文件。修改知识必须通过提交 Claim，Markdown 会自动重新生成。

## 协作方式

| 角色 | 接口 | 操作 |
|------|------|------|
| Agent | MCP | 查询上下文、提交候选 Claim、提交投影规则和内容、验证 Claim |
| 人类 | Web UI (localhost:8420) | 审核候选、管理 Claims、编辑投影规则、生成 MCP token、查看健康状态 |
| 人类/Agent | CLI | 调试维护、项目创建、快照管理 |

**流程**：Agent 提交 Claim → Kernel 校验 min_support → 进入候选队列 → 人类在 Web UI 审核（accept/reject）→ 接受后自动更新 Markdown 投影。

**Token**：MCP 可写操作需要 token。Token 由人类在 Web UI（localhost:8420/tokens）生成，然后提供给 Agent。如果没有 token，Agent 只能读取。

## 何时使用 PKS

| 时机 | 应该做什么 |
|------|-----------|
| **新项目建立时** | 与人类多轮会话理清需求和目标，然后创建 Capsule + 基础 Claims + 自定义 MD |
| **新知识（fact）产生时** | 发现代码结构、技术选型、模块关系等事实 → 提交 factual Claim |
| **用户提出推论时** | 用户基于事实做出判断 → 提交 inference Claim（引用 factual 作为支撑） |
| **用户提出约束时** | 用户声明"不能做 X"或"必须做 Y" → 提交 constraint Claim |
| **用户表达风格偏好时** | 用户说"我喜欢 X 风格" → 提交 preference Claim |
| **踩坑纠正时** | 发现之前的 Claim 不再成立 → 提交新 Claim supersede 旧的 |
| **功能模块完成时** | 总结该模块的架构决策、关键实现、已知限制 → 提交多条 Claims |
| **源文件变更后** | 检查 reverification issues，确认或更新受影响的 Claims |

## 启动 PKS 服务

```bash
./start.sh          # 同时启动 Web UI + MCP Server
./start.sh mcp      # 仅启动 MCP Server (stdio)
./start.sh web      # 仅启动 Web UI
```

## MCP 连接

```json
{
  "mcpServers": {
    "pks": {
      "command": "./start.sh",
      "args": ["mcp"],
      "env": {}
    }
  }
}
```

备选（直接命令）：
```json
{
  "mcpServers": {
    "pks": {
      "command": "/path/to/.venv/bin/pks",
      "args": ["mcp", "start", "--transport", "stdio"],
      "env": {}
    }
  }
}
```

## MCP 工具

### 只读（无需 token）

| 工具 | 说明 |
|------|------|
| `list_projects()` | 列出所有 PKS 管理的项目 |
| `get_project_context(project_id)` | 获取 PKS.md 内容（完整项目知识状态） |
| `search_claims(project_id, type?, status?, tag?, subject?, predicate?, projection?)` | 搜索 Claims |
| `get_claim(project_id, claim_id)` | 获取单条 Claim 详情 |
| `get_health(project_id)` | 健康报告 |
| `get_reverification_issues(project_id)` | 列出需要重验证的 Claims |

### 可写（需要 token）

| 工具 | 说明 |
|------|------|
| `submit_candidate_claim(token, project_id, claim)` | 提交新知识为候选 |
| `verify_claim(token, project_id, claim_id)` | 确认 Claim 在源头变更后仍然有效 |
| `create_capsule(token, project_id, metadata)` | 通过 MCP 创建新项目 Capsule |

## 新项目启动

新项目开始时，**不要直接创建 Capsule**。应该先与人类进行多轮会话：

1. **理清项目定位**：项目是什么？解决什么问题？目标用户是谁？
2. **确定技术边界**：技术栈、架构风格、关键约束
3. **明确当前阶段**：MVP？开发中？维护期？
4. **规划知识结构**：除了默认 MD（PKS_PROJECT.md、journal.md、领域 MD），是否需要自定义 MD？

确认后再创建：

```bash
# 1. 初始化 PKS home（仅首次）
pks init-home

# 2. 创建 Capsule
pks new <project-id> \
  --name "项目名称" \
  --capsule-type SoftwareCapsule \
  --domain dev \
  --stage "开发中" \
  --current-goal "当前目标" \
  --project-path "/path/to/project" \
  --constraints "约束1,约束2" \
  --yes

# 3. 生成初始投影
pks project projection <project-id> --write

# 4. 启动 MCP
./start.sh mcp
```

可用 capsule 类型：`SoftwareCapsule`、`PluginCapsule`、`ArticleCapsule`、`VideoCapsule`、`GameCapsule`、`DisciplineCapsule`、`ModelCapsule`

可用领域：`dev`、`content`、`research`

## Markdown 投影管理

### 默认投影

每种 capsule_type 有默认的 Markdown 投影（由 ProjectionSpec 定义）：

| capsule_type | 默认投影 |
|--------------|----------|
| SoftwareCapsule | PKS_PROJECT.md, journal.md, architecture.md, tasks.md |
| ArticleCapsule | PKS_PROJECT.md, journal.md, outline.md, facts.md |
| ResearchCapsule | PKS_PROJECT.md, journal.md, terminology.md, hypotheses.md |

### 自定义投影

当默认投影不够用时，可以创建自定义 MD：

1. 定义 ProjectionSpec（指定 filters：哪些 tags/types/predicates 的 Claims 进入这个 MD）
2. 提交 Claims 时使用对应的 tags（确保 Claim 出现在目标 MD 中）
3. PKS 自动根据 ProjectionSpec 渲染 MD

**示例**：项目需要一个 `security.md` 来汇总安全相关知识：
- 创建 ProjectionSpec：`filters.tags = ["security", "vulnerability", "auth"]`
- 后续提交安全相关 Claims 时带上 `tags: ["security"]`
- PKS 自动将这些 Claims 渲染到 `security.md`

### Claim 与 MD 的关系

- 每条 Claim 通过 `tags` 和 `predicate` 决定它出现在哪些 MD 中
- 一条 Claim 可以出现在多个 MD 中（如果它匹配多个 ProjectionSpec 的 filters）
- 修改 MD 内容 = 修改对应的 Claims（通过 `submit_candidate_claim` 或 `patch_projection_claim`）

## 提交 Claims

### 基本格式

```json
{
  "subject": "PKS Kernel",
  "predicate": "uses_pattern",
  "object": "composition over inheritance",
  "content": "PKS Kernel 使用组合模式——ProjectRegistry 组合 PolicyManager、TasteManager 等。",
  "type": "factual",
  "tags": ["architecture"],
  "confidence": 0.9,
  "evidence": [
    {
      "source_ref": "src/pks/kernel/capsule/registry.py",
      "source_type": "file",
      "relation": "supports",
      "excerpt": "self.policy = PolicyManager(self.domains_dir)"
    }
  ]
}
```

- `claim_id`：不要填，PKS 自动生成
- `content`：必填，人类可读的完整描述（投影 MD 的核心内容来源）
- `evidence.excerpt`：从源文件精确复制的文本片段。PKS 用它自动验证来源是否仍然有效——如果源文件中找不到这段文本了，Claim 会被标记为需要重验证
- `tags`：决定 Claim 出现在哪些 MD 投影中

### min_support 要求

| Claim 类型 | Evidence 要求 | Supporting Claims 要求 | 总支撑数 |
|------------|--------------|------------------------|----------|
| `factual` | ≥ 1 | 0 | ≥ 1 |
| `inference` | ≥ 0 | ≥ 0 | ≥ 1（合计） |
| `preference` | ≥ 1（含 manual/conversation 来源） | ≥ 0 | ≥ 1 |
| `constraint` | ≥ 1 | ≥ 1 | ≥ 2 |

### 类型层级

高层可引用低层作为支撑，低层不能引用高层：
- `inference` 可引用 `factual`
- `preference` 可引用 `factual` 或 `inference`
- `constraint` 可引用 `factual`、`inference` 或 `preference`

## 重验证

当源文件变更或支撑 Claim 失效时，PKS 会标记受影响的 Claims 为"待重验证"。

- 调用 `get_reverification_issues(project_id)` 查看待重验证列表
- 如果 Claim 仍然成立：调用 `verify_claim(token, project_id, claim_id)` 确认
- 如果 Claim 不再成立：提交新的候选 Claim supersede 旧的，或留给人类处理

## 规则

1. **不要直接访问 `~/.pks/`**——只通过 MCP 工具操作
2. **不要编辑 PKS.md**——它是从 Claims 自动生成的
3. **始终提供 evidence**——source_ref + excerpt
4. **工作前先读上下文**——调用 `get_project_context`
5. **尊重审核流程**——提交变为候选，人类决定接受
6. **excerpt 要精确**——从源文件原样复制，不要改写或缩写

## 降级处理

- MCP 不可用：告知人类，提供 `./start.sh mcp` 配置说明
- 没有 write token：告知人类从 Web UI (localhost:8420/tokens) 生成 token 并提供给你
- 无法满足 min_support：说明缺少什么支撑，请人类补充 evidence 或 supporting Claims
