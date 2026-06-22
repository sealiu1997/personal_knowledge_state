# PKS P4 Implementation Plan: Market Domain & Knowledge Governance

> 源自 stock-advisor 试运行反馈。对应反馈清单 A1–A6。
>
> **Phase 1 状态: ✅ 已完成** (2026-06-22)
> - P4.1 Market domain: ✅
> - P4.2 Claim metadata: ✅
> - P4.3 Lifecycle 增强 (tag_lifecycle + valid_for_*): ✅
> - P4.4 WebUI 性能 (Dashboard 异步 + Review 分页): ✅

---

## 背景

stock-advisor 作为 PKS 第一个高频写入场景（market_watcher 每 10 分钟扫描），暴露了 PKS 在以下方面的不足：

1. **Domain 不可扩展**：`CapsuleDomain` 是固定 StrEnum (content/dev/research)，无法新增 `market`
2. **Claim 缺少结构化 metadata**：日历事件的前值/预期/实际值被硬编码进字符串
3. **生命周期管理粗糙**：无 per-tag TTL，`valid_until` 未在所有入口暴露
4. **WebUI 性能崩溃**：大 capsule (1000+ claims) 下 Dashboard/Review 超时
5. **缺少临时材料层**：原始新闻不应进入 durable candidate queue
6. **Candidate queue 缺乏治理**：无过滤、去重、batch reject by query

## 分阶段执行

### Phase 1: 基础模型增强（本次实施）

#### P4.1 — Domain 可扩展 + 内置 market（对应 A3）

**当前问题**：

```python
class CapsuleDomain(StrEnum):
    CONTENT = "content"
    DEV = "dev"
    RESEARCH = "research"
```

`ProjectMetadata.domain` 类型为 `CapsuleDomain`，无法接受 `"market"` 等自定义值。

**改动方案**：

1. `CapsuleDomain` 新增 `MARKET = "market"`
2. `DomainPolicy.default_for()` 增加 market 默认 policy：
   - factual: `stale_after_days=30`, `auto_accept_threshold=0.95`
   - inference: `stale_after_days=14`
   - manual_review_types: `[inference, preference, constraint]`
3. `PolicyManager.ensure_domain_dirs()` 和 `DOMAIN_TYPE_SLUGS` 增加 market 条目
4. CLI `pks new --domain market` 可用

**影响范围**：

| 文件 | 改动 |
|------|------|
| `models.py` | `CapsuleDomain` 增加 MARKET |
| `kernel/capsule/policy.py` | `DOMAIN_TYPE_SLUGS` 增加 market；`default_for()` 增加 market 默认值 |
| 测试 | 新增 market domain 创建和 policy 验证用例 |

**验收**：

```bash
pks new market-context --name "Market Context" --capsule-type MarketContext --domain market --stage active --yes
pks policy show market
pks policy validate market
```

#### P4.2 — Claim 增加 metadata 字段（对应 A4）

**当前问题**：日历事件的结构化数据被编码为字符串。

**改动方案**：

1. `Claim` model 增加字段：`metadata: dict[str, Any] = Field(default_factory=dict)`
2. YAML 存储自动序列化 metadata
3. CLI `claim add` 增加 `--metadata` 参数（接受 JSON 字符串）
4. MCP `submit_candidate_claim` 自动透传 metadata
5. WebUI claim 详情页展示 metadata（JSON 格式化显示）

**影响范围**：

| 文件 | 改动 |
|------|------|
| `models.py` | `Claim` 增加 `metadata` 字段 |
| `cli.py` | `claim add` 增加 `--metadata` 选项 |
| `mcp/tools/write.py` | 自动透传（已支持，dict 数据直接传入） |
| `web/templates/claim.html` | 展示 metadata |
| 测试 | metadata 序列化/反序列化验证 |

**验收**：

```bash
pks claim add market-context \
  --claim-id fact-001 \
  --subject economic_calendar \
  --predicate scheduled_event \
  --object "US Core PCE 2026-06-25" \
  --source-ref jin10 \
  --excerpt "美国5月核心PCE物价指数年率" \
  --metadata '{"event_name":"US Core PCE","release_time":"2026-06-25T20:30:00+08:00","previous":"2.8%","consensus":"2.7%","status":"scheduled"}'
```

#### P4.3 — Lifecycle 增强：per-tag TTL + valid_until 全入口（对应 A2）

**当前问题**：

- `LifecycleRule` 只有 `stale_after_days`，无 per-tag override
- CLI `claim add` 不支持 `--valid-until`
- 缺少按 tag 自动计算 `valid_until` 的能力

**改动方案**：

1. `LifecycleRule` 增加 `valid_for_days: int | None` 和 `valid_for_hours: int | None`
2. `DomainPolicy` 增加 `tag_lifecycle: dict[str, LifecycleRule]` — 按 tag override
3. CLI `claim add` 增加 `--valid-until` 参数
4. `Kernel.build_candidate_claim()` 在创建 claim 时，如果未指定 `valid_until`，根据 tag 匹配 `tag_lifecycle` 自动设置
5. `MaintenanceEngine` 在 `enforce_expiry` 中支持基于 `valid_for_*` 的自动过期

Market domain 默认 tag_lifecycle：

```yaml
tag_lifecycle:
  intraday:
    valid_for_hours: 24
  scheduled:
    valid_for_days: 1
  actual_release:
    valid_for_days: 30
  narrative:
    stale_after_days: 14
    valid_for_days: 30
```

**影响范围**：

| 文件 | 改动 |
|------|------|
| `models.py` | `LifecycleRule` 增加 `valid_for_days`, `valid_for_hours`；`DomainPolicy` 增加 `tag_lifecycle` |
| `kernel/capsule/policy.py` | `default_for()` 增加 market tag_lifecycle |
| `kernel/facade.py` | `build_candidate_claim()` 自动推算 valid_until |
| `kernel/maintenance.py` | 按 tag TTL 自动过期 |
| `cli.py` | `claim add` 增加 `--valid-until` |
| `mcp/tools/write.py` | 透传 valid_until |

**验收**：

```bash
# CLI 指定 valid_until
pks claim add market-context --claim-id fact-002 ... --valid-until 2026-06-23

# tag 自动推算
# 带 tag=intraday 的 claim 自动设 valid_until = created_at + 24h
```

#### P4.4 — WebUI 性能修复（对应 A1）

**当前问题**：

1. Dashboard (`GET /`) 同步执行每个 capsule 的 `health_check()`，1000+ claims 时超时
2. Review 页 (`GET /projects/{id}/review`) 对每个 candidate 调用 `review_candidate()`，全量加载

**改动方案**：

**Dashboard**：
1. `GET /` 只展示 capsule metadata + lightweight counters（claim/candidate 计数）
2. 新增 `GET /api/projects/{id}/health` 异步 API
3. Dashboard 前端通过 fetch 异步拉取每个 capsule 的 health
4. Health 结果支持缓存（`_health_cache` + TTL）

**Review 页**：
1. `GET /projects/{id}/review` 支持 query params：`limit`(默认 25)、`offset`、`tag`、`type`、`source`
2. 不在列表页执行 `review_candidate()`，只展示 candidate 基本信息
3. 单条 review decision 在点击详情时才加载
4. batch accept/reject 对选中的 ID 操作

**影响范围**：

| 文件 | 改动 |
|------|------|
| `web/routes/projects.py` | Dashboard 改为 lightweight；新增 health API |
| `web/routes/candidates.py` | Review 页分页；去掉列表级 review_candidate |
| `web/templates/dashboard.html` | 异步加载 health |
| `web/templates/review.html` | 分页 UI + 不预加载 decision |
| `kernel/facade.py` | 新增 `count_candidates()` 等 lightweight 方法 |

**验收**：

- 1000+ claims 下 `GET /` 首屏 < 1s
- `GET /projects/{id}/review?limit=25` < 1s
- 单条 `GET /api/projects/{id}/candidates/{id}` < 500ms

### Phase 2: 知识治理（后续实施）

#### P4.5 — Scratchpad / Material 层（对应 A5）

为 PKS 新增非 durable 临时材料存储。raw news、price snapshots 等进入 scratchpad，不进入 candidate queue。

- 新增 `Material` model
- 新增 `material` CLI subcommand
- 新增 `material` API endpoints
- 支持 per-project/date 存储和 TTL 自动清理
- 支持 promote material → candidate

**延后原因**：stock-advisor B1 可以先用本地 `data/daily_materials/` 目录替代，不被 A5 阻塞。

#### P4.6 — Candidate Queue 治理（对应 A6）

- `pks review list` 增加过滤参数：`--tag`, `--older-than`, `--source`, `--limit`
- `pks review reject-query` 按条件批量 reject
- `pks review dedupe` 按 subject+predicate 去重
- WebUI Review 页支持同等过滤
- API 支持 group by + daily counts

---

## 不在本计划范围

- stock-advisor 侧的改动（见 stock-advisor 改动计划）
- Claim 审计/历史查询优化
- 多用户 / 权限管理

## 依赖关系

```
P4.1 (market domain)  ─┐
P4.2 (metadata)        ├── P4.3 (lifecycle) ── P4.4 (WebUI)
                       │
                       └── P4.5 (scratchpad) ── P4.6 (queue governance)
```

P4.1 和 P4.2 无依赖，可并行实施。P4.3 依赖 P4.1（market 默认 tag_lifecycle）。P4.4 独立但建议在 P4.1-P4.3 之后做（测试时 capsule 已有 market 数据）。
