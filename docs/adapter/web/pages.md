# PKS Web UI：页面设计

## 页面总览

| 页面 | URL | 功能 | 阶段 |
|------|-----|------|------|
| 仪表盘 | `/` | 项目列表 + 健康摘要 | P2 ✅ |
| 项目详情 | `/projects/{id}` | Claim 统计、最近活动 | P2 ✅ |
| 候选审核 | `/projects/{id}/review` | 候选列表、accept/reject | P2 ✅ |
| 候选详情 | `/projects/{id}/review/{cid}` | 完整 Claim + 审核建议 | P2 ✅ |
| Claim 浏览 | `/projects/{id}/claims` | 多维度筛选/排序 | P2 ✅（基础）→ P3 增强 |
| Claim 详情 | `/projects/{id}/claims/{cid}` | 完整 Claim + evidence 链 | P2 ✅ |
| Claim 新建 | `/projects/{id}/claims/new` | 引导式新建表单 | P3 |
| Claim 编辑 | `/projects/{id}/claims/{cid}/edit` | 编辑已有 Claim | P3 |
| 证据链 | `/projects/{id}/claims/{cid}/evidence-tree` | 树形可视化 | P3 |
| 配置管理 | `/projects/{id}/config` | 领域策略、投影规则编辑 | P3 |
| MCP Token | `/tokens` | Token 列表、regenerate、copy | P3 |
| 投影列表 | `/projects/{id}/projections` | 所有投影 + Claim 计数 | P3.1 |
| 投影预览 | `/projects/{id}/projections/{pid}` | 实时渲染单个投影 | P3.1 |
| PKS.md 预览 | `/projects/{id}/pks-md` | 完整 PKS.md 聚合预览 | P3.1 |
| 投影规则编辑 | `/projects/{id}/projections/{pid}/edit` | 左右分栏（规则 + 实时预览） | P3.1 |
| 新建投影 | `/projects/{id}/projections/new` | 新建自定义 ProjectionSpec | P3.1 |
| 重验证队列 | `/projects/{id}/reverification` | 待重验证 Claims + 确认/编辑/过期操作 | P3.2 |

---

## 仪表盘 `/`

**数据需求**：`list_capsules()` + 每个项目的 `health_check()`

**展示**：
- 项目卡片列表
- 每张卡片：项目名、domain、capsule_type、accepted/candidate/stale/expired 计数
- 颜色标记：全绿（健康）、黄色（有 stale）、红色（有 expired/disputed）

---

## 候选审核 `/projects/{id}/review`

**数据需求**：`list_candidates()` + 每条的 `review_candidate()`

**交互**：
- 候选列表，每行显示：claim_id、type、content、confidence、recommendation
- 单条操作：accept / reject 按钮
- **P3 批量操作**：checkbox 多选 → 批量 accept / 批量 reject

---

## Claim 浏览 `/projects/{id}/claims`

**数据需求**：`list_claims(project_id, **filters)`

**查看维度**（P3 增强）：

| 维度 | 筛选参数 | UI 呈现 |
|------|----------|---------|
| 按类型 | `--type` | Tab 切换：factual / inference / preference / constraint |
| 按序号 | 默认排序 | 按 claim_id 排序（F-00001, F-00002...） |
| 按项目 | 仪表盘入口 | 已按项目隔离 |
| 按投影 | `--tag` 或 `--predicate` | 下拉选择投影 → 显示该投影包含的 Claims |
| 按状态 | `--status` | Tab 或筛选器：accepted / disputed / expired / superseded |
| 按时间 | 排序 | 最新创建 / 最近验证 |

**交互**：
- 筛选器组合（类型 + 状态 + 投影）
- 搜索框（subject/predicate/content 模糊匹配）
- 点击进入 Claim 详情

---

## Claim 新建 `/projects/{id}/claims/new`

**流程**：用户填写 → 前端预校验 → 提交 `submit_candidate` → 进入 review 队列

**表单字段**：

| 字段 | 输入方式 | 必须 | 说明 |
|------|----------|------|------|
| type | 下拉选择 | ✅ | factual/inference/preference/constraint |
| subject | 文本输入 | ✅ | |
| predicate | 文本输入 | ✅ | |
| object | 文本输入 | ✅ | |
| content | 多行文本 | ✅ | 人类可读描述 |
| qualifier | 文本输入 | 可选 | 限定条件 |
| tags | 标签输入 | 可选 | 逗号分隔或 tag picker |
| confidence | 滑块 | ✅ | 默认 1.0（人类创建） |
| evidence | 动态表单组 | ✅ | 至少一条（见下） |
| supporting_claims | Claim 选择器 | 按类型要求 | 搜索已有 accepted Claims |

**Evidence 子表单**：

| 字段 | 输入方式 | 说明 |
|------|----------|------|
| source_ref | 文本输入 | 文件路径、URL 或 "manual" |
| source_type | 自动推断或下拉 | file/url/manual/command/conversation |
| relation | 下拉 | supports（默认）/ weak_supports |
| excerpt | 多行文本 | 原文摘录 |
| locator | 文本输入（可选） | 行号、commit 等 |

**min_support 引导**：
- 根据选择的 type，动态显示最低支撑要求提示
- 如果 type=constraint，提示"需要至少 1 条 evidence + 1 条 supporting claim"
- 如果 type=preference，提示"需要人类来源的 evidence"
- 提交前前端预校验，不满足时禁用提交按钮并显示原因

**提交后**：
- 显示 ReviewDecision（auto_accept / manual_review / reject）
- 如果 reject，显示原因（min_support 不满足的具体细节）
- 如果通过，跳转到候选审核页面

---

## Claim 编辑 `/projects/{id}/claims/{cid}/edit`

**流程**：加载已有 Claim → 用户修改 → 判断变更类型 → 提交

**变更类型判断**：
- 语素变更（subject/predicate/object）→ 走 `patch_projection_claim`，创建新 Candidate（supersedes 旧 Claim）
- 非语素变更（content/tags/qualifier）→ 走 `patch_projection_claim`，直接更新

**UI 提示**：
- 如果用户修改了 subject/predicate/object，显示警告："语素变更将创建新的候选 Claim，需要重新审核"
- 如果只修改 content/tags/qualifier，显示："非语素变更将直接生效"

---

## 证据链 `/projects/{id}/claims/{cid}/evidence-tree`

**数据需求**：递归加载 Claim → supporting_claims → 每条 supporting claim 的 evidence

**展示**：树形结构

```text
[C-00008] constraint: 投影修改必须经 Kernel
├── evidence: manual — "团队会议决定"
├── [I-00017] inference: Kernel 是唯一写入入口
│   ├── evidence: file — src/pks/kernel/facade.py
│   └── [F-00042] factual: PKS 使用独立存储
│       └── evidence: manual — "设计文档 v2"
└── [P-00003] preference: 偏好结构化主张
    └── evidence: conversation — "与用户讨论确认"
```

---

## MCP Token `/tokens`

**数据需求**：MCP 模块的 token 列表

**展示**：
- Token 列表（label、创建时间、权限级别）
- 每行操作：Copy（复制 token 到剪贴板）、Regenerate（撤销旧 token + 生成新 token）、Revoke（撤销）
- 新建 token 按钮（输入 label → 生成 → 显示一次完整 token）

**约束**：Token 的生成/撤销逻辑在 MCP 模块，Web UI 只调用 MCP 模块的接口展示结果。


---

## 投影列表 `/projects/{id}/projections`

**数据需求**：`list_projections(project_id)` + 每个投影匹配的 Claim 计数

**展示**：
- 表格：projection_id、title、output_path、匹配 Claim 数、类型（默认/自定义）
- 默认投影标记为"内置"，自定义投影标记为"自定义"
- 每行操作：预览、编辑规则、写入文件
- 自定义投影额外操作：删除
- 顶部按钮："新建自定义投影"、"预览 PKS.md"

---

## 投影预览 `/projects/{id}/projections/{pid}`

**数据需求**：`render_projection(project_id, projection_id)` + 匹配的 Claims 列表

**展示**：
- 顶部：投影标题、output_path、规则摘要（filters/order/exclude_stale）
- 主体：渲染后的 Markdown（转为 HTML 展示）
- 侧栏或下方：该投影匹配的 Claim 列表（claim_id + type + content，点击跳转详情）
- 操作按钮："编辑规则"、"写入文件"（触发 `render_projection(write=True)`）

**关键**：预览是实时从 Claims 渲染的，不是读取磁盘文件。用户看到的永远是最新状态。

---

## PKS.md 预览 `/projects/{id}/pks-md`

**数据需求**：`render_context(project_id)`

**展示**：
- 完整的 PKS.md 内容（所有投影按继承顺序聚合 + TasteAndStyle）
- 这就是 Agent 和人类在项目根目录看到的内容
- 操作按钮："重新生成并写入项目目录"

---

## 投影规则编辑 `/projects/{id}/projections/{pid}/edit`

**数据需求**：`load_projection_spec(project_id, projection_id)` + 实时预览

**布局**：左右分栏

```text
┌──────────────────────────┬──────────────────────────────────┐
│ 规则表单                  │ 实时预览                          │
│                          │                                  │
│ Title: [Architecture]    │ <!-- Generated from Claims -->   │
│ Output: [projections/    │ # Architecture & Decisions       │
│          architecture.md]│                                  │
│                          │ - F-00042 [factual] PKS uses...  │
│ Include status:          │ - I-00017 [inference] Kernel...  │
│ [✓] accepted             │ - C-00008 [constraint] 投影...   │
│ [ ] disputed             │                                  │
│                          │ 匹配 Claims: 3                   │
│ Exclude stale: [✓]      │                                  │
│                          │                                  │
│ Filters:                 │                                  │
│ Types: [✓]factual        │                                  │
│        [✓]inference      │                                  │
│        [ ]preference     │                                  │
│        [✓]constraint     │                                  │
│                          │                                  │
│ Tags: [architecture,     │                                  │
│  design-decision,        │                                  │
│  tech-stack, boundary]   │                                  │
│                          │                                  │
│ Predicates: [         ]  │                                  │
│ Exclude tags: [audit]    │                                  │
│                          │                                  │
│ Order: [type, created_at]│                                  │
│                          │                                  │
│ [预览] [保存]            │                                  │
└──────────────────────────┴──────────────────────────────────┘
```

**交互**：
- 修改 filter → 点击"预览"→ 右侧实时更新渲染结果（htmx 局部刷新）
- "保存"调用 `update_projection_spec`（有 Audit Claim）
- 默认投影：projection_id 和 output_path 不可修改，只能改 filters/order
- 自定义投影：所有字段可编辑

**约束**：
- 预览使用临时 spec（不保存），通过 preview 端点实现
- 保存后自动重新生成投影文件

---

## 新建投影 `/projects/{id}/projections/new`

**数据需求**：无（空表单）

**表单字段**：

| 字段 | 输入方式 | 必须 | 说明 |
|------|----------|------|------|
| projection_id | 文本输入 | ✅ | 稳定 ID（kebab-case） |
| output_path | 文本输入 | ✅ | 相对路径，必须 .md 结尾 |
| title | 文本输入 | ✅ | Markdown 标题 |
| description | 文本输入 | 可选 | 投影用途说明 |
| include_status | 多选 | ✅ | accepted / disputed / expired / superseded |
| exclude_stale | 开关 | ✅ | 默认 true |
| filters.types | 多选 | 可选 | factual / inference / preference / constraint |
| filters.tags | 标签输入 | 可选 | 逗号分隔 |
| filters.predicates | 标签输入 | 可选 | 逗号分隔 |
| filters.exclude_tags | 标签输入 | 可选 | 逗号分隔 |
| order | 下拉多选 | ✅ | type / created_at / predicate |

**提交后**：调用 `create_projection_spec` → 跳转到该投影的预览页
