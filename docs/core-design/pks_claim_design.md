# PKS Claim 设计

状态：P0 当前实现同步，2026-05-09。

## 定位

Claim 是长期知识的原子单位。PKS 不把长期知识存成自由段落，而是存成可验证、可过期、可替代、可争议化的结构化主张。

## Schema

核心字段：
- `claim_id`
- `subject`、`predicate`、`object`
- `qualifier`
- `content`
- `type`：`factual`、`inference`、`preference`、`constraint`
- `domain`：`content`、`dev`、`research`
- `tags`
- `evidence`
- `status`
- `confidence`
- `created_at`、`created_by`、`valid_from`、`valid_until`、`last_verified`
- `supersedes`、`superseded_by`
- `project`

Evidence 强制存在：
- `source_ref`
- `relation`
- `excerpt`

无 evidence 的 Claim 非法。

## 生命周期

```text
submit_claim
  ↓
ReviewStrategy
  ├── reject
  ├── candidate/manual review
  └── auto accept
        ↓
accepted
  ├── disputed
  ├── expired
  └── superseded
```

状态枚举只包含：
- `candidate`
- `accepted`
- `disputed`
- `expired`
- `superseded`

`stale` 是计算属性，不进入状态枚举。

`mark_claim_stale` 只记录一次 stale 检查结果，不改变 `ClaimStatus`。如果 evidence 失效或超过领域 stale 周期，Claim 会在 health/context/projection 中被视为 stale，但仍保持原状态。

P0 CLI 生命周期命令：
- `pks claim expire <project_id> <claim_id>`
- `pks claim dispute <project_id> <claim_id>`
- `pks claim supersede <project_id> <old_claim_id> ...`

## 冲突规则

冲突 key 是 `(subject, predicate)`。

当前规则：
- 相同 `(subject, predicate)` 且不同 `object`：潜在冲突。
- 新 Claim 被接受时若发现冲突，新旧 Claim 都进入 `disputed`。
- 如果双方 `qualifier` 不同，视作 scoped complement，不自动冲突。
- `supersedes` 必须指向相同 `(subject, predicate)` 的旧 Claim。
- CLI supersede 复用旧 Claim 的 `subject` 和 `predicate`，新 Claim 只要求显式提供新 `object` 与 evidence。

## 审核策略

`ReviewStrategy` 读取领域级 `claim_policy.yaml`：
- confidence `< 0.3`：reject。
- 有冲突：manual review。
- `inference`、`preference`、`constraint` 默认 manual review。
- `factual` 达到领域阈值可 auto accept。

P0 中自动接受只覆盖高置信 factual Claim。

## 存储

项目 Claim：

```text
~/.pks/capsules/<project_id>/claims/<claim_id>.yaml
```

领域 TasteAndStyle Claim：

```text
~/.pks/domains/<domain>/taste_and_style/claims/<claim_id>.yaml
```

TasteAndStyle 不使用特殊格式，本质仍是 `type=preference` 的 Claim。

## Context 过滤

Context Pack 和 `PKS.md` 只输出：
- `accepted`
- 未过期
- 未被替代
- 非 stale

以下不会进入上下文：
- candidate
- disputed
- expired
- superseded
- computed stale

## Evidence 检查

`ProjectTracker` 检查每条 evidence：
- `source_ref=manual` 或 URL：P0 跳过文件完整性检查。
- 文件不存在：evidence issue。
- excerpt 不在文件中：evidence issue。

evidence issue 会使 accepted Claim 在健康检查和 Context 生成中被视为 stale。
