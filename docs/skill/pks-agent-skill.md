# PKS Agent Skill

## What is PKS

PKS (Personal Knowledge State) is a knowledge state control plane for projects. It maintains structured, evidence-backed knowledge using Claims as the atomic unit.

PKS ensures knowledge accuracy through:
- **min_support rules**: each Claim type requires different levels of evidence
- **Candidate → Review flow**: all writes are proposed, humans decide what becomes accepted
- **Evidence tracking**: Claims are linked to verifiable sources

## Your Role

As an Agent, you interact with PKS through its **MCP interface**:
- **Query** project context and existing knowledge (read tools, no token needed)
- **Submit** new knowledge as candidate Claims with evidence (write tools, token required)

You **never** directly modify PKS state. Kernel validates your submissions and humans review them.

## MCP Connection

Configure your MCP client to connect to PKS:

```json
{
  "mcpServers": {
    "pks": {
      "command": "pks",
      "args": ["mcp", "start", "--transport", "stdio"],
      "env": {}
    }
  }
}
```

If PKS is installed in a virtualenv, use the full path (e.g., `/path/to/.venv/bin/pks`).

## MCP Tools

### Read Tools (no token required)

| Tool | Input | Output |
|------|-------|--------|
| `get_project_context(project_id)` | project ID | PKS.md content (full project knowledge state) |
| `search_claims(project_id, ...)` | project ID + optional filters (type, status, tag, subject, predicate, projection) | Claim list |
| `get_claim(project_id, claim_id)` | project ID + claim ID | Single Claim detail |
| `get_health(project_id)` | project ID | Health report (stale/expired/disputed counts) |
| `get_reverification_issues(project_id)` | project ID | Claims needing re-verification after source/support changes |
| `list_projects()` | — | All project IDs and metadata |

### Write Tools (token required)

| Tool | Input | Output |
|------|-------|--------|
| `submit_candidate_claim(token, project_id, claim)` | token + project ID + Claim data | ReviewDecision (auto_accept / manual_review / reject) |
| `verify_claim(token, project_id, claim_id)` | token + project ID + claim ID | Confirmation (updates last_verified) |

The token is provided by the project owner. If you don't have a token, you can only read.

## Submitting Knowledge

When you discover or confirm something about a project, submit it as a candidate Claim:

```json
{
  "subject": "PKS Kernel",
  "predicate": "uses_pattern",
  "object": "composition over inheritance",
  "content": "PKS Kernel uses composition — ProjectRegistry composes PolicyManager, TasteManager, etc.",
  "type": "factual",
  "tags": ["architecture"],
  "confidence": 0.9,
  "evidence": [
    {
      "source_ref": "src/pks/kernel/capsule/registry.py",
      "source_type": "file",
      "relation": "supports",
      "excerpt": "class ProjectRegistry:\n    self.policy = PolicyManager(self.domains_dir)"
    }
  ]
}
```

### min_support Requirements

Your submission must satisfy minimum support rules per Claim type:

| Claim type | Evidence required | Supporting Claims required | Total support |
|------------|-------------------|---------------------------|---------------|
| `factual` | ≥ 1 | 0 | ≥ 1 |
| `inference` | ≥ 0 | ≥ 0 | ≥ 1 (evidence + claims combined) |
| `preference` | ≥ 1 (must include human source) | ≥ 0 | ≥ 1 |
| `constraint` | ≥ 1 | ≥ 1 | ≥ 2 |

If your submission doesn't meet min_support, Kernel rejects it with a clear reason.

### Claim Types

| Type | Code | When to use |
|------|------|-------------|
| `factual` | F | Observable facts in code, docs, or behavior |
| `inference` | I | Deductions based on facts |
| `preference` | P | Style/taste choices (requires human confirmation) |
| `constraint` | C | Boundaries and prohibitions |

### Supporting Claims

Higher-level Claims can reference lower-level accepted Claims as support:
- `inference` can cite `factual` Claims
- `preference` can cite `factual` or `inference` Claims
- `constraint` can cite `factual`, `inference`, or `preference` Claims

Lower-level Claims cannot cite higher-level Claims as support.

## Rules

1. **Always read context first.** Call `get_project_context` before starting work to understand current state.
2. **Always provide evidence.** Every Claim needs at least one evidence item with `source_ref` and `excerpt`.
3. **Use appropriate types.** Don't submit a preference as factual, or an inference without support.
4. **Respect the review process.** Your submissions become candidates. Humans decide acceptance.
5. **Never access PKS files directly.** PKS state lives in `~/.pks/` — interact only through MCP.
6. **Claim IDs are auto-generated.** Don't provide `claim_id` in your submission; Kernel generates it.
7. **Treat re-verification as a review queue.** Call `get_reverification_issues` after source changes. If you can confirm a flagged Claim still holds, use `verify_claim` with a write token; otherwise submit an updated candidate or leave it for human review.

## Understanding PKS.md

When you call `get_project_context`, you receive the project's PKS.md — a generated aggregation of all accepted Claims organized by projection. It contains:

- Project definition and boundaries
- Architecture decisions
- Current stage and goals
- Constraints and prohibitions
- TasteAndStyle preferences

This is the authoritative project knowledge state. Use it to understand the project before making changes.
