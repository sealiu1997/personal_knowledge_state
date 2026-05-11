# PKS Web UI：Claim 新建界面设计

## 设计目标

让人类通过 Web UI 高效创建合法的 Claim。界面必须：
1. 引导用户满足 min_support 要求（不同类型有不同要求）
2. 提交后走 `submit_candidate` 路径（复用现有 review 流程）
3. 即时反馈校验结果（通过/reject + 原因）

## 流程

```text
用户选择 Claim 类型
  ↓
界面动态显示该类型的 min_support 要求
  ↓
用户填写语素（subject/predicate/object）+ content
  ↓
用户添加 evidence（至少满足 min_support.evidence 要求）
  ↓
用户添加 supporting_claims（如果类型要求）
  ↓
前端预校验 min_support
  ↓ 通过
提交 → Kernel submit_candidate
  ↓
显示 ReviewDecision（auto_accept / manual_review / reject）
```

## 类型选择与动态提示

用户选择 type 后，界面显示对应的 min_support 提示：

| type | 提示内容 |
|------|----------|
| factual | "需要至少 1 条 evidence。不需要 supporting claims。" |
| inference | "需要至少 1 条支撑（evidence 或 accepted factual Claim）。" |
| preference | "需要至少 1 条人类来源的 evidence（manual 或 conversation）。" |
| constraint | "需要至少 1 条 evidence + 1 条 supporting claim（总支撑 ≥ 2）。必须人工审核。" |

## 表单布局

```text
┌─────────────────────────────────────────────────┐
│ 新建 Claim                                       │
├─────────────────────────────────────────────────┤
│ 类型: [factual ▼]                                │
│                                                  │
│ ⓘ 需要至少 1 条 evidence。                        │
├─────────────────────────────────────────────────┤
│ 语素结构                                         │
│ Subject:   [________________]                    │
│ Predicate: [________________]                    │
│ Object:    [________________]                    │
│ Qualifier: [________________] (可选)             │
├─────────────────────────────────────────────────┤
│ Content（人类可读描述）                            │
│ [                                               ]│
│ [                                               ]│
├─────────────────────────────────────────────────┤
│ Evidence ✓ (1/1 满足)                            │
│ ┌─────────────────────────────────────────────┐ │
│ │ Source: [manual          ]                  │ │
│ │ Type:   [manual ▼] (自动推断)               │ │
│ │ Excerpt: [用户手动确认    ]                  │ │
│ │ Locator: [              ] (可选)            │ │
│ └─────────────────────────────────────────────┘ │
│ [+ 添加 Evidence]                                │
├─────────────────────────────────────────────────┤
│ Supporting Claims (0/0 满足)                     │
│ [搜索已有 Claim...] (按 subject/predicate 搜索)  │
│ [+ 添加 Supporting Claim]                        │
├─────────────────────────────────────────────────┤
│ 元数据                                           │
│ Tags: [project, tech-stack]                      │
│ Confidence: [====●=====] 1.0                     │
├─────────────────────────────────────────────────┤
│ [提交为候选]  (min_support ✓ 满足)               │
└─────────────────────────────────────────────────┘
```

## 前端预校验

提交按钮的启用/禁用由前端实时计算：

```javascript
function validateMinSupport(type, evidenceCount, supportingClaimsCount, hasHumanSource) {
  const rules = {
    factual:    { evidence: 1, claims: 0, total: 1, humanSource: false },
    inference:  { evidence: 0, claims: 0, total: 1, humanSource: false },
    preference: { evidence: 1, claims: 0, total: 1, humanSource: true },
    constraint: { evidence: 1, claims: 1, total: 2, humanSource: false },
  };
  const rule = rules[type];
  const issues = [];
  if (evidenceCount < rule.evidence) issues.push(`需要至少 ${rule.evidence} 条 evidence`);
  if (supportingClaimsCount < rule.claims) issues.push(`需要至少 ${rule.claims} 条 supporting claim`);
  if (evidenceCount + supportingClaimsCount < rule.total) issues.push(`总支撑需要 ≥ ${rule.total}`);
  if (rule.humanSource && !hasHumanSource) issues.push('需要人类来源的 evidence');
  return { valid: issues.length === 0, issues };
}
```

注意：前端预校验只是 UX 优化，最终校验由 Kernel 的 `validate_min_support` 执行。

## Supporting Claim 选择器

当用户需要添加 supporting_claims 时：

1. 显示搜索框，支持按 subject/predicate/claim_id 搜索
2. 只显示 accepted 状态的 Claims
3. 只显示 `allowed_support_types` 允许的类型（如 constraint 只能引用 factual/inference/preference）
4. 选中后显示 Claim 摘要（claim_id + content）
5. 可以添加多条

## 提交后反馈

提交后显示 ReviewDecision：

| decision.action | UI 反馈 |
|-----------------|---------|
| `auto_accept` | ✅ "已提交为候选。建议自动接受（factual + 高置信度）。" → 跳转审核页 |
| `manual_review` | ⚠️ "已提交为候选，等待人工审核。" → 跳转审核页 |
| `reject` | ❌ "提交被拒绝：{reason}" → 显示具体 min_support 不满足的细节，留在表单页 |

## Claim ID 生成

用户不需要手动填写 claim_id。提交时由 Kernel 的 `ClaimIdGenerator.next_claim_id(type)` 自动生成。

Web UI 表单不显示 claim_id 字段。

## 与编辑的区别

| 操作 | 路径 | 结果 |
|------|------|------|
| 新建 | `/projects/{id}/claims/new` → `submit_candidate` | 创建新 Candidate |
| 编辑（非语素） | `/projects/{id}/claims/{cid}/edit` → `patch_projection_claim` | 直接更新 |
| 编辑（语素） | `/projects/{id}/claims/{cid}/edit` → `patch_projection_claim` | 创建新 Candidate（supersedes 旧） |

三种操作最终都走 Kernel 接口，Web UI 不做业务判断。
