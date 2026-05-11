# PKS Web UI 适配层：总览

状态：P3 前置设计，2026-05-11。

## 定位

Web UI 是 Kernel 的人类管理界面适配层。它不含业务逻辑，所有操作委托 Kernel。

Web UI 的核心价值：
- 让人类高效审核候选 Claim（比 CLI 的 YAML 阅读体验好）
- 提供多维度的 Claim 浏览（按类型、序号、项目、所属投影）
- 提供 Claim 新建界面（引导用户满足 min_support）
- 管理 MCP token（生成、查看、撤销）
- 展示项目健康状态和维护报告

## 架构约束

```text
Browser → FastAPI route → Kernel method → Storage
                       ← HTML/JSON response
```

- Web UI 是 Kernel 的薄适配层，不含业务逻辑
- 不直接读写存储，所有状态变更通过 Kernel
- 新建/编辑 Claim 统一走 `submit_candidate` 路径（复用现有 review 流程）
- 本地运行，不是云端 SaaS
- 技术栈：FastAPI + Jinja2 + htmx（无前端框架）

## 模块结构

```text
src/pks/web/
├── __init__.py
├── app.py               # FastAPI app factory
├── routes/
│   ├── __init__.py
│   ├── common.py        # 共用工具（kernel_from, templates_from）
│   ├── projects.py      # 项目仪表盘、项目详情
│   ├── candidates.py    # 候选审核（列表、详情、accept/reject/batch）
│   ├── claims.py        # Claim 浏览、详情、新建、编辑
│   ├── maintenance.py   # 维护触发
│   └── tokens.py        # MCP token 管理展示
├── templates/           # Jinja2 HTML 模板
└── static/              # CSS + htmx.min.js
```

## CLI

```bash
pks serve                     # localhost:8420
pks serve --port 9000         # 自定义端口
pks serve --host 0.0.0.0     # 绑定所有接口
```

## 设计原则

1. **所有写入走 Candidate → Review**：Web UI 新建 Claim 提交为 Candidate，不直接写入 accepted。
2. **Kernel 是唯一业务入口**：Web UI 不做校验、不做冲突检测、不做 min_support 判断——这些都由 Kernel 完成。
3. **渐进增强**：htmx 做基础交互，复杂组件（证据链树形图）后续用 Alpine.js 局部增强。
4. **MCP token 展示不管理**：token 的生成/撤销由 MCP 模块负责，Web UI 只展示和提供 regenerate/copy 按钮。

## 当前实现（P2）

- 仪表盘、项目详情、候选审核（单条 accept/reject）、Claim 浏览/详情
- 维护触发 API

## P3 新增

- 批量审核（多选 accept/reject）
- Claim 新建界面（引导式表单）
- Claim 编辑（语素变更 → 候选，非语素 → 直接更新）
- 多维度 Claim 查看（按类型、序号、项目、所属投影）
- 证据链可视化
- 配置管理（领域策略、投影规则）
- MCP token 展示（regenerate/copy）
