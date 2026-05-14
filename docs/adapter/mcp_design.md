# PKS MCP 适配层设计

状态：P3 前置设计，2026-05-11。

## 定位

MCP Server 是 Kernel 的 Agent 接口适配层。它将 Kernel 方法暴露为 MCP 工具，让 Agent 通过标准协议与 PKS 交互。

MCP Server 不含业务逻辑。Agent 的请求由 Kernel 的 min_support/review 机制自然约束——不合法的 Claim 会被 Kernel reject，所有写入都走 Candidate → Review。

## 架构约束

- MCP Server 是 Kernel 的薄适配层：`Agent → MCP Tool → Kernel method → Storage`
- 不含业务逻辑，不直接读写存储
- 使用官方 Python MCP SDK
- 支持 stdio 和 SSE 两种传输方式

## 权限模型

MCP 采用最小权限设计：

### 读写分离

| 权限级别 | 可用工具 | 说明 |
|----------|----------|------|
| 只读 | `get_project_context`、`search_claims`、`get_claim`、`get_health`、`list_projects` | 无需 token |
| 可写 | `submit_candidate_claim` | 需要有效 token |

### Token 管理

- **生成/撤销**：由 MCP 模块负责（`pks mcp token create/list/revoke`）
- **权限校验**：由 Kernel 管理（token 的权限信息存储在 Kernel 可访问的 `~/.pks/config.yaml`）
- **展示**：Web UI 提供 token 列表页面（regenerate/copy 按钮），调用 MCP 模块接口

```yaml
# ~/.pks/config.yaml
mcp_tokens:
  - token_id: "tok_001"
    token_hash: "sha256:..."       # 不存明文，只存 hash
    created_at: "2026-05-11T10:00:00+08:00"
    label: "Claude Code workspace"
    permissions: [read, write]
```

### 设计原则

- Kernel 本身的校验（min_support、review、冲突检测）是主要约束
- Token 只是"谁能调用 MCP 可写接口"的门禁
- MVP 阶段不区分 per-agent 权限，所有持有 write token 的 Agent 权限相同
- Token 明文只在生成时返回一次，之后只存 hash

## MCP 工具定义

### 只读工具

| 工具 | Kernel 方法 | 输入 | 输出 |
|------|-------------|------|------|
| `get_project_context` | `render_context` | `project_id` | PKS.md 内容（字符串） |
| `search_claims` | `list_claims` | `project_id` + 筛选参数 | Claim 列表 |
| `get_claim` | `load_claim` | `project_id`, `claim_id` | 单条 Claim |
| `get_health` | `health_check` | `project_id` | 健康报告 |
| `list_projects` | `list_capsules` | — | 项目列表 |

### 可写工具

| 工具 | Kernel 方法 | 输入 | 输出 |
|------|-------------|------|------|
| `submit_candidate_claim` | `submit_candidate` | `project_id` + Claim 字段 | ReviewDecision |

Agent 提交的 Claim 必须满足 min_support 规则，否则 Kernel 直接 reject。通过 min_support 的 Claim 进入 Candidate Queue，等待人类审核。

## 模块结构

```text
src/pks/mcp/
├── __init__.py
├── server.py          # MCP Server 启动与配置
├── tools/
│   ├── __init__.py
│   ├── read.py        # 只读工具（context/claims/health）
│   └── write.py       # 可写工具（submit_candidate）
├── auth.py            # Token 验证
└── config.py          # MCP 配置加载
```

## CLI

```bash
pks mcp start                    # 启动 MCP server（默认 stdio）
pks mcp start --transport stdio  # stdio 传输（Claude Code、Codex 等）
pks mcp start --transport sse    # SSE 传输（Web Agent）
pks mcp token create --label "Claude Code"  # 生成 token
pks mcp token list               # 列出 token
pks mcp token revoke <token>     # 撤销 token
```

## Agent 使用示例

Agent 通过 MCP 与 PKS 交互的典型流程：

```text
1. Agent 连接 MCP Server（人类提供 token）
2. Agent 调用 get_project_context → 获取项目当前状态
3. Agent 执行工作（代码修改、文档编写等）
4. Agent 调用 submit_candidate_claim → 提交新知识
   - Kernel 校验 min_support
   - 通过 → 进入 Candidate Queue
   - 不通过 → 返回 reject 原因
5. 人类通过 Web UI 或 CLI 审核候选
```

## 后续扩展点

- **P3.2 完整性验证工具**：`verify_claim`（确认 Claim 在源头变更后仍有效）、`get_reverification_issues`（列出需要重验证的 Claims）。详见 [P3.2 计划](../plans/2026-05-14-pks-p3.2-integrity-cascade-plan.md)。
- **更多可写工具**：`submit_projection_claim`（通过投影提交）、`patch_projection_claim`（修改已有 Claim）
- **批量提交**：一次提交多条 Claims
- **上下文感知**：根据 Agent 当前工作文件自动筛选相关 Claims
- **Obsidian MCP**：通过 MCP 让 Obsidian 插件读写 PKS
- **Notion 同步 MCP**：通过 MCP 触发 Notion 同步

这些扩展都是在现有 MCP 框架上增加工具，不改变架构。
