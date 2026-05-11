# PKS Web UI：API 端点定义

## 约束

- 所有 API 端点委托 Kernel 方法，不含业务逻辑
- 返回 JSON（`/api/` 前缀）或 HTML（页面路由）
- 错误返回标准 HTTP 状态码 + JSON error body

## 端点列表

### 项目

| Method | Path | Kernel Method | 说明 |
|--------|------|---------------|------|
| GET | `/api/projects` | `list_capsules` | 项目列表 |
| GET | `/api/projects/{id}` | `load_capsule` + `health_check` | 项目详情 + 健康 |

### 候选审核

| Method | Path | Kernel Method | 说明 |
|--------|------|---------------|------|
| GET | `/api/projects/{id}/candidates` | `list_candidates` | 候选列表 |
| GET | `/api/projects/{id}/candidates/{cid}` | `load_candidate` + `review_candidate` | 候选详情 + 建议 |
| POST | `/api/projects/{id}/candidates/{cid}/accept` | `accept_candidate` | 接受候选 |
| POST | `/api/projects/{id}/candidates/{cid}/reject` | `reject_candidate` | 拒绝候选 |
| POST | `/api/projects/{id}/candidates/batch-accept` | `accept_candidate` × N | 批量接受 |
| POST | `/api/projects/{id}/candidates/batch-reject` | `reject_candidate` × N | 批量拒绝 |

**Batch 请求体**：
```json
{"ids": ["F-00042", "F-00043", "I-00017"]}
```

**Batch 响应**：
```json
{"accepted": ["F-00042", "F-00043"], "failed": [{"id": "I-00017", "reason": "..."}]}
```

### Claim 管理

| Method | Path | Kernel Method | 说明 |
|--------|------|---------------|------|
| GET | `/api/projects/{id}/claims` | `list_claims` | Claim 列表（支持查询参数） |
| GET | `/api/projects/{id}/claims/{cid}` | `load_claim` | Claim 详情 |
| POST | `/api/projects/{id}/claims` | `submit_candidate` | 新建 Claim（走 candidate 路径） |
| POST | `/api/projects/{id}/claims/{cid}/patch` | `patch_projection_claim` | 编辑 Claim |

**新建 Claim 请求体**：
```json
{
  "claim_id": "F-00099",
  "subject": "PKS",
  "predicate": "uses_stack",
  "object": "Python",
  "content": "PKS 使用 Python 技术栈",
  "type": "factual",
  "tags": ["tech-stack"],
  "confidence": 1.0,
  "evidence": [
    {
      "source_ref": "manual",
      "relation": "supports",
      "excerpt": "用户手动确认"
    }
  ],
  "supporting_claims": []
}
```

**新建 Claim 响应**：ReviewDecision JSON

**Patch 请求体**：
```json
{"changes": {"content": "PKS 使用 Python 3.13 技术栈"}}
```

**Patch 响应**：
- 非语素变更：更新后的 Claim JSON
- 语素变更：ReviewDecision JSON（新 Candidate 已创建）

**Claim 列表查询参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | string | accepted/disputed/expired/superseded |
| `type` | string | factual/inference/preference/constraint |
| `domain` | string | dev/content/research |
| `tag` | string | 按标签筛选 |
| `subject` | string | 按主体筛选 |
| `predicate` | string | 按谓语筛选 |
| `projection` | string | 按投影 ID 筛选（匹配该投影的 Claims） |

### 维护

| Method | Path | Kernel Method | 说明 |
|--------|------|---------------|------|
| POST | `/api/projects/{id}/maintain` | `maintenance.run` | 运行维护 |

**查询参数**：`stale=true/false`、`expiry=true/false`、`evidence=true/false`

**响应**：MaintenanceReport JSON

### MCP Token（展示层）

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/mcp/tokens` | 列出 token（label + 创建时间 + 权限，不返回完整 token） |
| POST | `/api/mcp/tokens` | 生成新 token（返回完整 token，仅此一次） |
| DELETE | `/api/mcp/tokens/{token_id}` | 撤销 token |
| POST | `/api/mcp/tokens/{token_id}/regenerate` | 撤销旧 token + 生成新 token |

**Token 生成请求体**：
```json
{"label": "Claude Code workspace", "permissions": ["read", "write"]}
```

**Token 生成响应**（仅生成时返回完整 token）：
```json
{"token_id": "...", "token": "pks_xxxxxxxxxxxx", "label": "...", "permissions": [...]}
```

**约束**：Token 的生成/撤销逻辑由 MCP 模块实现，Web UI 的 API 路由调用 MCP 模块接口。

### 配置

| Method | Path | Kernel Method | 说明 |
|--------|------|---------------|------|
| GET | `/api/projects/{id}/policy` | `load_policy` | 领域策略 |
| POST | `/api/projects/{id}/policy` | (future) | 更新策略 |
| GET | `/api/projects/{id}/projection-specs` | `list_projections` | 投影规则列表 |

## 错误响应格式

```json
{
  "error": "min_support_failed",
  "detail": "constraint requires at least 1 supporting claim(s)",
  "status_code": 422
}
```

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 404 | 资源不存在 |
| 422 | 校验失败（min_support、类型层级等） |
| 500 | 内部错误 |


### 投影预览与规则管理（P3.1）

| Method | Path | Kernel Method | 说明 |
|--------|------|---------------|------|
| GET | `/api/projects/{id}/projections` | `list_projections` | 投影列表 + 每个的 Claim 计数 |
| GET | `/api/projects/{id}/projections/{pid}/render` | `render_projection(pid)` | 实时渲染单个投影（返回 Markdown） |
| GET | `/api/projects/{id}/projections/{pid}/claims` | `list_claims(projection=pid)` | 该投影匹配的 Claims |
| GET | `/api/projects/{id}/pks-md` | `render_context` | 实时渲染完整 PKS.md |
| POST | `/api/projects/{id}/projections/{pid}/write` | `render_projection(pid, write=True)` | 写入磁盘 |
| POST | `/api/projects/{id}/pks-md/write` | `render_projection(write=True)` | 写入项目根目录 |
| GET | `/api/projects/{id}/projections/{pid}` | `load_projection_spec` | 获取 ProjectionSpec |
| POST | `/api/projects/{id}/projections/{pid}` | `update_projection_spec` | 更新 ProjectionSpec |
| POST | `/api/projects/{id}/projections` | `create_projection_spec` | 新建自定义 ProjectionSpec |
| DELETE | `/api/projects/{id}/projections/{pid}` | `delete_projection_spec` | 删除自定义投影 |
| POST | `/api/projects/{id}/projections/preview` | (临时渲染) | 预览新建临时 spec（不保存） |
| POST | `/api/projects/{id}/projections/{pid}/preview` | (临时渲染) | 预览临时 spec（不保存） |

**预览端点请求体**（临时 spec，用于编辑时实时反馈）：
```json
{
  "include_status": ["accepted"],
  "exclude_stale": true,
  "filters": {
    "types": ["factual", "inference"],
    "tags": ["architecture", "design-decision"],
    "predicates": [],
    "exclude_tags": ["audit"]
  },
  "order": ["type", "created_at"]
}
```

**预览端点响应**：
```json
{
  "markdown": "<!-- Generated from Claims -->\n# Architecture...",
  "claim_count": 5
}
```
