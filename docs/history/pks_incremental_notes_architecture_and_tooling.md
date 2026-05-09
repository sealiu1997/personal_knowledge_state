# 个人知识状态库：增量设计文档——解耦架构与工具复用

## 1. 本次增量的核心问题

在原始产品规划中，PKS 被定义为一个本地优先、人机共用、项目中心的个人知识状态库。它负责维护项目状态、上下文、任务合约、权限、候选写入、快照和审计。

本次讨论进一步澄清了一个关键问题：

> PKS 不应该成为项目文件夹、编程智能体和编辑器的混合体。它应该和这些系统解耦，并作为项目状态的控制层存在。

因此，本次增量重点补充三个方面：

1. 项目文件夹、Agent 和 PKS 的架构关系；
2. PKS 应如何复用成熟工具，而不是从零实现所有能力；
3. 除 Superpowers 外，还有哪些开源项目和接口值得借鉴或集成。

---

## 2. 三层解耦：项目、PKS、Agent

PKS 的核心架构应明确区分三类对象：

- 项目文件夹；
- PKS 系统；
- 编程智能体或其他 Agent。

三者不应互相绑定，也不应互相替代。

更合理的抽象是：

> 项目文件夹是资产层；  
> PKS 是控制层；  
> Agent 是执行层。

### 2.1 项目文件夹是资产层

项目文件夹保存真实资产，例如：

- 代码；
- 文档；
- 素材；
- 配置；
- 草稿；
- 测试；
- Git 历史。

项目文件夹仍然属于用户、编辑器、IDE、Git 和具体 Agent。PKS 不应该吞掉项目本身，也不应该强制项目按照 PKS 的结构重组。

对于软件项目，真实代码仓库仍然是软件资产的 source of truth。对于文章项目，草稿和资料也可以继续保存在项目文件夹中。PKS 只记录它们和项目状态之间的关系。

### 2.2 PKS 是控制层

PKS 维护的是项目的状态和协作协议，而不是替代项目本身。

它负责：

- 项目元信息；
- 当前目标；
- 长期边界；
- Agent 上下文；
- 任务合约；
- 权限策略；
- 候选写入；
- 快照；
- 审计记录；
- 外部工具连接关系。

PKS 可以通过 `project.yaml` 记录外部项目路径、Git 仓库、默认 Agent、关联文档和上下文生成规则。

换句话说，PKS 不接管项目，而是为项目提供一个稳定的状态控制平面。

### 2.3 Agent 是执行层

Codex、Claude Code、Trae、Cline、Roo Code、OpenHands 等工具都应被视为外部执行器。

Agent 可以：

- 读取 PKS 生成的 Context Pack；
- 接收任务合约；
- 在受控工作区中执行；
- 生成草稿、候选主张或补丁；
- 返回 diff、报告和验证结果。

Agent 不应该直接拥有修改 PKS 长期状态的权限。它的写入应通过 candidate、draft、patch 等中间产物回到 PKS，再由权限策略和人工审核决定是否合并。

### 2.4 三者的连接关系

合理的关系是：

```text
Human / Editor
      ↓
PKS Kernel
      ↓
Context Pack / Task Contract / Policy
      ↓
Agent Adapter / MCP / CLI
      ↓
Agent Execution
      ↓
Workspace / Patch / Candidate
      ↓
Review / Merge / Snapshot
      ↓
Project Folder / PKS State
```

这个结构的核心主张是：

> 项目文件夹负责资产；  
> Git 负责变更；  
> Agent 负责执行；  
> 编辑器负责人工编辑；  
> PKS 负责状态、权限、上下文、任务和审计。

---

## 3. PKS 不应从零实现所有功能

目前规划中的能力较多，如果全部自研，MVP 会变得过重。因此，PKS 应采用“控制平面 + 工具复用”的路线。

PKS 自己只实现其他工具不负责、或者难以统一负责的部分：

- 项目状态；
- 任务合约；
- 权限策略；
- Agent 上下文；
- 候选写入；
- 补丁入口；
- 快照与审计；
- 外部工具适配。

其他成熟能力应尽量复用现有工具。

### 3.1 Git 负责版本和变更

Git 应成为 PKS 的基础依赖之一。

PKS 可以复用 Git 的能力来完成：

- 版本记录；
- diff；
- patch；
- branch；
- worktree；
- merge；
- rollback；
- hooks；
- 变更审计。

这意味着 PKS 不需要自己实现版本系统，也不需要自己管理复杂文件变更。Agent 对项目的修改可以先进入 Git worktree 或临时工作区，再生成 patch，由用户或规则审核后合并。

### 3.2 Obsidian / VS Code 负责人类编辑

PKS 不应一开始自研完整 UI。

Markdown 文件仍然是最适合 MVP 的长期资产格式。用户可以通过 Obsidian、VS Code 或普通文件系统直接查看和编辑项目状态、资料、草稿和候选内容。

Obsidian 尤其适合作为人类知识视图：

- 本地优先；
- Markdown 原生；
- 插件生态成熟；
- 适合项目页、资料页和知识链接。

未来可以开发 Obsidian 插件，但第一版不必依赖插件即可工作。

### 3.3 Notion 适合作为投影，不适合作为底层事实源

Notion 可以作为云端展示、协作看板或发布页面，但不适合作为 PKS 的核心事实源。

原因是 PKS 的底层应保持本地优先、可迁移、可审计，并能被 Agent 以受控方式访问。

因此，Notion 更适合扮演外部投影层，而不是状态内核。

### 3.4 Codex / Claude Code / Cline / Roo Code / OpenHands 负责执行

编程智能体已经具备较强的代码生成、文件编辑、终端操作和调试能力。PKS 不应重复实现这些能力。

更合理的方式是：

- PKS 生成任务上下文；
- Agent 在项目工作区执行；
- PKS 限定执行范围；
- Agent 返回 patch 和报告；
- PKS 负责审核入口和合并流程。

这使 PKS 可以同时兼容多个 Agent，而不是绑定某一个工具。

### 3.5 MCP 负责通用 Agent 接入

MCP 可以作为 PKS 与外部 Agent 的标准连接层。

PKS 的 MCP Server 不应暴露危险的文件级写接口，而应暴露意图级接口，例如：

- `get_project_context`；
- `search_project`；
- `get_task_contract`；
- `submit_candidate_note`；
- `submit_candidate_claim`；
- `submit_patch`；
- `request_permission`。

这样 Agent 可以接入 PKS，但不能绕过 PKS Kernel 直接改长期状态。

---

## 4. AGENTS.md、CLAUDE.md、rules 文件的定位

市面上很多 Agent 已经支持项目级说明文件，例如 AGENTS.md、CLAUDE.md、rules 文件、Cursor rules、Zed rules 等。

这些文件很有用，但它们只是说明层，不是安全层。

PKS 可以自动生成这些兼容文件，使不同 Agent 更容易理解项目背景和工作边界。

例如：

- 为 Codex / OpenAI 风格工具生成 `AGENTS.md`；
- 为 Claude Code 生成 `CLAUDE.md`；
- 为编辑器或 Agent 生成 `.rules/pks.md`；
- 为通用 LLM 生成 `context.md`。

但这些文件只能帮助 Agent 理解规则，不能保证 Agent 遵守规则。

真正的安全边界仍然应该由：

- PKS Kernel；
- Task Contract；
- Policy Engine；
- Git worktree；
- Patch Review；
- Snapshot；
- Audit Log；
- 操作权限控制。

---

## 5. 除 Superpowers 外，可借鉴的项目和接口

Superpowers 的价值在于它把 Agent 工作流程显性化，例如先规划、再执行、再测试、再 review。它证明了“Agent 需要纪律”，但它主要仍然是 skill / workflow 层面的约束。

PKS 要进一步把这些纪律下沉到硬软件架构中。

除此之外，还可以借鉴和复用以下项目与接口。

### 5.1 AGENTS.md

AGENTS.md 可以作为面向 Agent 的项目说明入口。

它的价值在于提供一个较通用的、跨工具的上下文文件格式。PKS 可以把项目状态投影成 AGENTS.md，但不能把它作为权限系统。

### 5.2 OpenHands

OpenHands 适合作为可编程的软件 Agent 执行层参考。

它的价值在于：

- workspace 思路；
- 软件任务执行环境；
- Python / REST API 集成可能；
- 可替代具体聊天式 Agent，成为更底层的执行器。

PKS 可以借鉴它的执行环境设计，尤其是临时 workspace 和任务运行隔离。

### 5.3 Cline / Roo Code

Cline 和 Roo Code 适合做早期集成对象。

它们的价值在于：

- 开源；
- 支持 MCP；
- 支持文件和终端操作；
- 适合与 VS Code 类编辑器协作；
- 模式化工作流较适合和 PKS 的 task contract 对接。

它们可以作为 PKS 的外部执行器，而不是 PKS 的底层依赖。

### 5.4 Aider

Aider 的价值在于 Git-native。

它适合作为轻量命令行代码执行器。PKS 可以把任务上下文交给 Aider，再回收 Git diff 或 patch。

这类工具说明：PKS 不应该自研代码修改能力，而应该围绕 Git 和 patch 做编排。

### 5.5 Continue

Continue 的 AI Review / PR Check 思路值得借鉴。

它说明 review 规则可以文件化、版本化，并作为自动检查在变更流程中运行。

PKS 可以借鉴这一点，把 review 规则变成项目内可维护文件，例如：

- scope check；
- evidence check；
- architecture drift check；
- protected file check；
- context consistency check。

这些检查可以在 Agent 提交 patch 后自动运行。

### 5.6 Sourcegraph Cody

Cody 的价值在于大代码库上下文管理。

它提示我们：复杂仓库不能简单依赖全文塞入上下文，而需要代码搜索、符号检索、调用关系和任务相关上下文投影。

PKS 第一版不一定要实现代码智能索引，但可以预留接口，未来接入 Sourcegraph、LSP 或代码索引服务。

### 5.7 LlamaIndex / LangGraph 等框架

这类框架适合做资料接入、索引、抽取和工作流原型。

它们可以帮助 PKS 实现：

- 文档 ingestion；
- RAG；
- 结构化抽取；
- workflow prototype；
- Agent 工具调用。

但 PKS 的核心状态不应被这些框架托管。它们适合作为资料处理层，而不是权威状态层。

### 5.8 MCP SDK

MCP SDK 是 PKS 对接外部 Agent 的关键工具。

PKS 可以通过 MCP 暴露 resources、tools 和 prompts：

- resources：项目状态、上下文、guardrails；
- tools：搜索、提交候选、提交 patch、请求权限；
- prompts：开启任务、review 候选、提出架构变更。

MCP 是接口层，不是状态层。

---

## 6. 新的架构主张

本次增量后，PKS 的架构主张可以进一步压缩为：

> PKS 不是项目文件夹，也不是 Agent，也不是编辑器。  
> PKS 是项目状态控制平面。

更具体地说：

- 项目文件夹负责真实资产；
- Git 负责版本、diff、patch、worktree 和回滚；
- Agent 负责执行；
- Obsidian / VS Code 负责人类编辑；
- Notion 负责可选云端投影；
- MCP / CLI / API 负责连接；
- PKS Kernel 负责状态、权限、上下文、任务、候选、快照和审计。

这个解耦可以避免 PKS 变成一个大而全的复杂系统，也可以避免它被某一个 Agent、编辑器或项目结构锁死。

---

## 7. 对 MVP 的影响

这次增量意味着 MVP 应进一步收敛。

PKS 第一版不应该做完整平台，而应该做一个轻量控制层。

### 7.1 PKS 第一版应该自研的部分

- Project Capsule；
- Template Engine；
- Context Pack Generator；
- Task Contract；
- Policy Engine；
- Candidate Queue；
- Workspace / Patch Adapter；
- Snapshot / Audit；
- CLI；
- MCP Server。

### 7.2 第一版应该复用的部分

- Git：版本、diff、patch、worktree、回滚；
- Obsidian / VS Code：人类编辑；
- Codex / Claude Code / Cline / Roo / OpenHands：Agent 执行；
- AGENTS.md / CLAUDE.md / rules：Agent 说明文件兼容；
- Continue / CI / Dagger：自动检查和验证；
- Notion：可选投影；
- LlamaIndex / LangGraph：可选资料处理和工作流实验。

### 7.3 第一版要避免的方向

- 不做完整 IDE；
- 不做完整笔记软件；
- 不做全自动 Agent 平台；
- 不做大而全知识图谱；
- 不绑定单一 Agent；
- 不把 Markdown 说明文件当作真正权限系统；
- 不让 Agent 直接修改长期状态。

---

## 8. 结论

本次增量进一步明确了 PKS 的边界。

PKS 的价值不是替代现有工具，而是把现有工具组织进一个更稳定的知识状态协作框架中。

它不应该和 Codex、Claude Code、Obsidian、Git、Notion 竞争，而应该利用它们：

- 用 Git 管变更；
- 用 Obsidian / VS Code 管人类编辑；
- 用 Codex / Claude Code / Cline / Roo / OpenHands 管执行；
- 用 MCP 管连接；
- 用 Notion 管外部展示；
- 用 PKS Kernel 管状态和权限。

因此，PKS 的最小可行形态不是“大一统知识管理平台”，而是：

> 一个轻量、本地优先、可插拔的项目状态控制平面。

它的核心任务是让人类和各种 Agent 能围绕同一份项目状态协作，同时避免长期目标、核心架构和知识状态被模型漂移污染。

