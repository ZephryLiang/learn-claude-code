# Production-Grade Agent Harness: 差距分析与改进路线图

> 基于 s01_agent_loop.py 的极简循环，推演到生产级 Harness 所需的全部改进。
> 每个改进点标注了对应 session 的覆盖情况，附行业协议对标与学术论文背书。

---

## 项目 Session 全景结构

本项目经过重构，按关注点组织为四个模块：

```
Core Loop (agents/)               System Hardening (systemhardening/)
├── s01  Basic Loop               ├── s07  Permission System ← NEW
├── s02  Tool Dispatch            ├── s08  Hook System       ← NEW
├── s03  TodoWrite (Planning)     ├── s09  Memory System     ← NEW
├── s04  Subagent                 ├── s10  System Prompt     ← NEW
├── s05  Skill Loading            └── s11  Error Recovery    ← NEW
├── s06  Context Compression
└── s13  Result Normalization ← NEW

Task Runtime (task_runtime/)      Multi-Agent Platform (multiagent_platform/)
├── s12  Task System              ├── s15  Agent Teams       (planned)
├── s13  Background Tasks (planned)├── s16  Team Protocols   (planned)
└── s14  Cron Scheduler  (planned)├── s17  Autonomous Agents (planned)
                                  ├── s18  Worktree Isolation(planned)
                                  └── s19  MCP & Plugin      (planned)
```

---

## 0. 基准：s01 的最小完备集

```
while stop_reason == "tool_use":
    LLM(messages, tools) → execute tools → append results → loop
```

这个循环定义了 Harness 的**三个核心接缝**，所有生产级改进都是在这三个位置插入策略：

```
                    ┌──────────────────┐
                    │  ① LLM 调用前     │  ← token 管理 / 上下文注入 / 模型路由
                    │                  │  ← s06 压缩 / s10 prompt 组装 / s09 memory 注入
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  LLM Inference   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  ② 工具执行前     │  ← 权限检查 / 沙箱隔离 / Hook 拦截
                    │                  │  ← s07 权限 / s08 hook PreToolUse / s12 worktree
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Tool Execution  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  ③ 结果返回后     │  ← 结果归一化 / 事件发出 / Hook 注入 / 错误分类
                    │                  │  ← s13 结构化 error / s08 hook PostToolUse / s11
                    └──────────────────┘
```

---

## 1. 工具协议标准化

### 1.1 结构化错误模型

| 痛点 | s01 现状 | 改进方向 |
|------|---------|---------|
| 所有错误压平成 `"Error: xxx"` 字符串 | `return "Error: Timeout (120s)"` | 结构化 error schema，区分 transient / permanent / permission |
| 模型无法基于错误类型决策 | 模型看到的是非结构化文本 | 模型直接读取 error.type 和 retryable 做决策，无需 NLP 解析 |

**覆盖状态**：✅ 已覆盖 — **s13 Result Normalization** (`agents/s13_result_normalization.py` + `agents/lib/result_normalizer.py`)

**实现**：`ToolResult { success, data, error: { type, message, retryable, suggested_action } }` 在 Harness 接缝③注入。

**行业背书**：

| 标准 | 关键机制 | s13 对应 |
|------|---------|---------|
| **MCP** 2025-11-25 spec (Anthropic) | `isError: true` + `structuredContent`；工具内部错误在 result 中报告，不升级为协议错误 | `ToolResult.success: false` + `error: {...}` |
| **gRPC Error Model** (Google) | 16 个标准 status code + `google.rpc.Status` details + `RetryInfo` / `ErrorInfo` | ErrorType 枚举直接映射 gRPC codes |
| **A2A** (Google) v0.3.0 | Task `FAILED` 状态 + `errorDetails`；transport 错误与 domain 错误分离 | `ToolResult.error` 对应 task-level error details |
| **Anthropic SDK Best Practices** (2025) | 结构化 JSON：`{category, code, message, details, retry_after}` + 显式 `is_error` 标记 | ToolError 包含 `type/code/message/retryable/suggested_action` |

**学术背书**：

| 论文 | 核心发现 | 对 s13 的验证 |
|------|---------|-------------|
| [**PALADIN**](https://arxiv.org/abs/2509.25238) (Sep 2025) | ToolScan taxonomy (55+ failure exemplars)；结构化恢复策略检索 → Recovery Rate 23.75% → **89.86%** | 直接验证了"结构化错误分类驱动模型恢复行为"这一核心假设 |
| [**SHIELDA**](https://arxiv.org/abs/2508.07935) (Aug 2025) | 36 种异常类型 × 12 种 agent artifact 的完整分类法；错误需从 execution 追溯到 reasoning 根因 | s13 的 7 类型覆盖 tool execution 层（SHIELDA 的子集） |
| [**AgentDebug**](https://arxiv.org/abs/2509.25370) (Sep 2025) | 五维故障分类 (memory/reflection/planning/action/system)；AgentErrorBench 首个系统标注失败数据集 | s13 的设计可沿五维分类向上扩展 |

**ErrorType 分类合理性**：

```
s13 ErrorType       gRPC Code               s11 Recovery 策略        驱动不同的模型行为
───────────        ──────────              ─────────────────        ──────────────────
TRANSIENT          UNAVAILABLE              backoff retry            等几秒重试
TIMEOUT            DEADLINE_EXCEEDED        retry_or_split_work      不盲重试，拆分任务
NOT_FOUND          NOT_FOUND                verify_path_or_ref       先查引用，不重试
PERMISSION         PERMISSION_DENIED        escalate_to_user         不动手，升级给人
INVALID_INPUT      INVALID_ARGUMENT         re_read_and_fix          模型自己修正参数
PERMANENT          INTERNAL                 switch_strategy          放弃当前路径
UNKNOWN            UNKNOWN                  analyze_and_decide       模型自行判断
```

7 个类型无冗余——判断标准是每个类型是否驱动**不同的 `suggested_action`**。TIMEOUT 与 TRANSIENT 表面相似，但模型遇到 TIMEOUT 不应简单重试同一超长命令，而应拆分子任务。

---

### 1.2 工具注册与生命周期

| 痛点 | s01 现状 | 改进方向 |
|------|---------|---------|
| 工具定义和实现紧耦合 | `TOOLS` + `TOOL_HANDLERS` 写死 | Tool Registry：动态注册/卸载/发现 |
| 无法按场景裁剪工具集 | 全部工具暴露 | 按 agent type / permission level / task context 动态裁剪 |

**覆盖状态**：⚠️ 部分覆盖 — s02 引入 dispatch map 模式；s04 subagent 按类型裁剪工具集（Explore 无 write 权限）；s05 引入 skill 动态加载概念；s07 Permission Gate 按模式限制工具。但正式的 **Tool Registry** 抽象未实现

### 1.3 工具输入校验

| 痛点 | s01 现状 | 改进方向 |
|------|---------|---------|
| 无输入校验 | `run_bash(kw["command"])` 直接信任模型输出 | JSON Schema → 类型强制 → 安全 sanitize → 校验失败返回结构化错误 |

**覆盖状态**：⚠️ 部分覆盖 — s07 BashSecurityValidator 用 regex 校验 bash 命令（shell metachar, sudo, rm_rf 等），但校验失败后的返回不是 s13 的结构化格式

---

## 2. 安全模型

### 2.1 权限管道 (Permission Pipeline)

| 痛点 | s01 现状 | 改进方向 |
|------|---------|---------|
| 字符串黑名单 | `"rm -rf /" in command` — 极易绕过 | Pipeline: deny rules → mode check → allow rules → ask user |
| 无分层权限 | bash 要么全有要么全无 | READ_ONLY_TOOLS / WRITE_TOOLS 分类 + mode (default/plan/auto) |
| 无用户确认门控 | 无 | ask_user() 交互确认 + y/n/always 三级响应 |

**覆盖状态**：✅ 已覆盖 — **s07 Permission System** (`systemhardening/permission_gate.py`)

**s07 的核心设计**：

```
Tool call → BashSecurityValidator → Deny rules → Mode check → Allow rules → Ask user
              │                        │             │             │            │
              ├─ severe(sudo,rm_rf):   ├─ bypass-    ├─ plan:      ├─ first     ├─ y/yes: allow
              │  immediate deny         │  immune     │  deny writes │  match    ├─ n: track
              └─ others(shell_meta):   │             ├─ auto:       │  wins     └─ always:
                 escalate to ask       │             │  allow reads │             add rule
```

与 s01 的 `dangerous` 黑名单对比：

| 维度 | s01 | s07 |
|------|-----|-----|
| 分类粒度 | 5 个字符串关键词 | 5 个 regex pattern × 2 严重级别 (severe / ask) |
| 决策流 | 黑名单命中 → deny，否则 → 放行 | 四级管道：deny → mode → allow → ask |
| 用户参与 | 无 | y/n/always 交互 + allow rule 持久化 |
| 模式支持 | 无 | default / plan / auto |
| 熔断 | 无 | consecutive_denials ≥ 3 → 建议切换 plan mode |

### 2.2 注入防护

| 痛点 | 改进方向 |
|------|---------|
| 工具结果直接拼接进 prompt | 恶意工具结果需标记和隔离 |
| 无输出过滤 | 模型输出不应直接执行 |

**覆盖状态**：❌ 未覆盖

---

## 3. Hook 系统（扩展点）

### 3.1 事件驱动扩展

| 痛点 | s01 现状 | 改进方向 |
|------|---------|---------|
| 无扩展点 | 修改行为 → 改 agent loop 源码 | Hook 在 loop 外部定义，不改 loop 本身 |
| 无行为拦截 | 无 | PreToolUse 可拦截/修改参数/注入上下文；PostToolUse 可校验结果 |

**覆盖状态**：✅ 已覆盖 — **s08 Hook System** (`systemhardening/hooks_system.py`)

**s08 的核心设计**：

```
Hook Events: SessionStart / PreToolUse / PostToolUse
Hook Exit Code Contract:
  0 → continue (可返回 updatedInput / additionalContext / permissionDecision via stdout JSON)
  1 → block (stderr = reason)
  2 → inject message (stderr → 注入为 user message)
```

---
**Hook 在三个接缝处的部署**：

```
接缝① (LLM 调用前)   → SessionStart hook
接缝② (工具执行前)   → PreToolUse hook (可拦截/改参数/覆盖权限)
接缝③ (结果返回后)   → PostToolUse hook (可校验/注入 context)
```

**与行业对标**：

| 系统 | Hook/Plugin 机制 | s08 对应 |
|------|-----------------|---------|
| Claude Code | PreToolUse / PostToolUse / SessionStart / SessionEnd / Notification / Stop | 教学版仅覆盖前三个事件 |
| Git Hooks | pre-commit / post-commit / pre-push | 相同理念：在关键生命周期点注入外部脚本 |
| VS Code Extensions | ActivationEvents + Extension API | 相同理念：不改核心，通过扩展点注入行为 |

---

## 4. 记忆系统（跨会话持久化）

### 4.1 分层记忆

| 痛点 | s01 现状 | 改进方向 |
|------|---------|---------|
| 无跨会话记忆 | 进程退出 = 全部丢失 | Frontmatter .md 文件持久化；MEMORY.md 索引 |
| 无记忆类型区分 | 无 | user / feedback / project / reference 四种类型 |
| 无记忆治理 | 无 | Dream Consolidator: 合并/去重/裁剪 |

**覆盖状态**：✅ 已覆盖 — **s09 Memory System** (`systemhardening/memory_system.py`)

**s09 的记忆分层**：

```
.memory/
  MEMORY.md          ← 索引 (≤200 行)，每次对话加载
  user_role.md       ← user 类型：用户身份/偏好
  feedback_testing.md ← feedback 类型：用户反馈/修正记录
  incident_board.md   ← project 类型：项目决定/约束
  linear_board.md     ← reference 类型：外部系统指针
```

**设计原则** (来自 s09 源码注释)：

> "Memory only stores cross-session information that is still worth recalling later and is not easy to re-derive from the current repo."

| 应该存入 memory | 不应存入 memory |
|----------------|----------------|
| 用户偏好、重复反馈 | 代码结构（可从 repo 重读） |
| 非显而易见的项目事实 | 临时任务状态 |
| 外部资源指针 | Secrets / 敏感信息 |

---

## 5. System Prompt 工程

### 5.1 分层 Prompt 组装

| 痛点 | s01 现状 | 改进方向 |
|------|---------|---------|
| System prompt 是单字符串 | `SYSTEM = f"You are a coding agent at {os.getcwd()}..."` | 6 层 Pipeline: core → tools → skills → memory → CLAUDE.md → dynamic |
| 静态和动态内容混在一起 | 无区分 | DYNAMIC_BOUNDARY 分离 → 静态部分可跨轮次缓存 |
| 无 CLAUDE.md 链 | 无 | 三级优先级：~/.claude/CLAUDE.md → project/CLAUDE.md → subdir/CLAUDE.md |

**覆盖状态**：✅ 已覆盖 — **s10 System Prompt** (`systemhardening/system_prompt.py`)

**s10 的组装 Pipeline**：

```
Section 1: Core instructions     ← 稳定：agent 身份 + 行为准则
Section 2: Tool listing           ← 半稳定：随 tool registry 变化
Section 3: Skill metadata         ← 半稳定：随 skill 库变化
Section 4: Memory section         ← 缓慢变化：用户跨会话积累
Section 5: CLAUDE.md chain        ← 用户控制：用户/项目/子目录三级
────────── DYNAMIC_BOUNDARY ──────────  ← 缓存边界（静态部分可跨轮次复用）
Section 6: Dynamic context        ← 每轮变化：日期/cwd/platform/model
```

另外 `build_system_reminder()` 生成 `<system-reminder>` 用户消息，用于 per-turn 动态内容注入——这比混入 system prompt 更灵活，且不破坏 prompt 缓存。

---

## 6. 错误恢复（可靠性）

### 6.1 三层恢复策略

| 痛点 | s01 现状 | 改进方向 |
|------|---------|---------|
| API 调用失败直接崩溃 | 无任何错误处理 | 三条恢复路径，优先级匹配 |
| 无重试 | 无 | Exponential backoff + jitter + 熔断 |

**覆盖状态**：✅ 已覆盖 — **s11 Error Recovery** (`systemhardening/error_recovery.py`)

**s11 的三条恢复路径**：

```
LLM response
     │
     ├── stop_reason == "max_tokens" → [Strategy 1: continuation]
     │    注入 "Output limit hit. Continue directly."
     │    最多 3 次 continuation
     │
     ├── API error: overlong_prompt   → [Strategy 2: compact + retry]
     │    触发 auto_compact (LLM summary)，替换 history
     │
     ├── API error: connection/rate   → [Strategy 3: backoff retry]
     │    delay = min(base × 2^attempt, 30s) + jitter
     │    最多 3 次重试
     │
     └── stop_reason == "end_turn"    → [Normal exit]
```

这条与 s13 Result Normalization 互补：s11 处理 **API 层和 transport 层**的恢复，s13 处理 **工具执行层**的错误分类。

---

## 7. 可观测性 (Observability)

### 7.1 三层观测体系

```
┌─────────────────────────────────────────────────────────┐
│ TRACE 层: 一次用户请求的完整生命周期                      │
│ request_id → [LLM call → tool exec → LLM call → ...]    │
│ 每个 step: span_id, parent_span_id, start/end time,      │
│           model, token_count, tool_name, duration_ms     │
├─────────────────────────────────────────────────────────┤
│ METRICS 层: 聚合统计                                     │
│ • Token: input/output per call → 成本归因                │
│ • Tool: success_rate by error_type, P50/P99 latency      │
│ • Session: turns, duration, tool_call_sequence_length    │
├─────────────────────────────────────────────────────────┤
│ AUDIT 层: 不可篡改的操作记录                              │
│ (who, when, what_tool, what_params, what_result)          │
│ 用于: 事后溯源 / 合规 / 安全事件调查                      │
└─────────────────────────────────────────────────────────┘
```

**覆盖状态**：⚠️ 部分覆盖

| 子项 | 覆盖情况 |
|------|---------|
| Trace | s13 ResultNormalizer 内部记录 per-tool error count（雏形）；s08 Hook 可注入 PostToolUse 做日志 |
| Metrics | s13 `ResultNormalizer.error_summary()` 提供 per-tool per-error-type 计数 |
| Audit | s06 transcript JSONL + s11 的 compact 保存完整对话。但审计需不可篡改且结构化 |

**未覆盖的核心 gap**：OpenTelemetry 风格的 trace context 传播（trace_id / span_id 贯穿 LLM 调用和工具执行）。

---

## 8. 模型路由与容错

| 痛点 | s01 现状 | 改进方向 |
|------|---------|---------|
| 单模型硬编码 | `MODEL = os.environ["MODEL_ID"]` | Model Router：按任务类型/成本/延迟选模型 |
| 无重试 | API 调用失败直接崩溃 | Retry with exponential backoff (s11 部分覆盖) |
| 无降级 | 无 | 主模型不可用 → 备选模型 |
| 无 rate limiting | 无 | Token bucket / 并发限制 |

**覆盖状态**：⚠️ 部分覆盖 — s11 实现了 API 层的 backoff retry + compact recovery，但 model routing / fallback / rate limiting 未实现

---

## 9. 任务运行时

### 9.1 持久化任务图

| 痛点 | s01 现状 | 改进方向 |
|------|---------|---------|
| 无任务管理 | 用户每次说一句做一步 | 持久化 task graph (JSON 文件) + dependency resolution |
| 任务只在对话中存在 | 换对话 = 丢失 | 文件持久化，跨对话存活 (s12) |

**覆盖状态**：✅ 已覆盖 — **s12 Task System** (`task_runtime/task_system.py`)

**s12 的任务状态机**：`pending → in_progress → completed | deleted`

每个 task 有 `blockedBy` 和 `blocks` 双向依赖图。task 完成后自动清除所有依赖它的任务的 blockedBy 条目。

### 9.2 后台任务 & 定时调度

**覆盖状态**：⏳ Planned — s13 Background Tasks, s14 Cron Scheduler

---

## 10. 多 Agent 平台

| Session | 机制 | 状态 |
|---------|------|------|
| s15 Agent Teams | 持久 teammate + JSONL mailbox | Planned (原 s09) |
| s16 Team Protocols | shutdown handshake + plan approval | Planned (原 s10) |
| s17 Autonomous Agents | idle cycle + auto-claim + identity re-injection | Planned (原 s11) |
| s18 Worktree Isolation | git worktree + task binding + EventBus | Planned (原 s12) |
| s19 MCP & Plugin | Model Context Protocol 集成 | Planned (NEW) |

---

## 11. 横切关注点总结表

图例：✅=已覆盖  ⚠️=部分覆盖  ❌=未覆盖  ⏳=Planned

| # | 关注点 | 覆盖 Session | 状态 | 缺失 |
|---|--------|-------------|------|------|
| 1 | 工具分发模式 | **s02** Tool Dispatch | ✅ | — |
| 2 | 任务规划 | **s03** TodoWrite | ✅ | — |
| 3 | 子任务隔离 | **s04** Subagent | ✅ | — |
| 4 | 知识注入 | **s05** Skill Loading | ✅ | — |
| 5 | 上下文压缩 | **s06** Context Compression | ✅ | — |
| 6 | **权限系统** | **s07** Permission Gate | ✅ | — |
| 7 | **Hook 扩展点** | **s08** Hook System | ✅ | — |
| 8 | **跨会话记忆** | **s09** Memory System | ✅ | — |
| 9 | **分层 Prompt 组装** | **s10** System Prompt | ✅ | — |
| 10 | **错误恢复** | **s11** Error Recovery | ✅ | — |
| 11 | 持久化任务图 | **s12** Task System | ✅ | — |
| 12 | 异步执行 | s08 Background Tasks (原) | ⏳ | Planned |
| 13 | 定时调度 | s14 Cron Scheduler | ⏳ | Planned |
| 14 | **结构化错误模型** | **s13** Result Normalization | ✅ | — |
| 15 | 多 Agent 协作 | s15-s18 | ⏳ | Planned |
| 16 | MCP & Plugin 集成 | s19 | ⏳ | Planned |
| 17 | **可观测性 (tracing/metrics)** | s13 ErrorSummary + s08 Hook | ⚠️ | OpenTelemetry trace context |
| 18 | **安全沙箱** | s07 Permission + s18 Worktree | ⚠️ | 无容器级沙箱 |
| 19 | **会话持久化与恢复** | s09 Memory + s06 Transcript | ⚠️ | 无正式 session resume |
| 20 | **模型路由/降级** | s11 Backoff + Compact | ⚠️ | 无 model routing / fallback |
| 21 | **依赖注入/配置管理** | 所有 session 共享全局变量模式 | ❌ | 🔴 |
| 22 | **工具注册中心** | s02/s04/s05 各有部分 | ⚠️ | 无统一 Tool Registry |
| 23 | **可测试性/Eval 框架** | 无 | ❌ | 🔴 |
| 24 | **注入防护** | 无 | ❌ | 🟡 |
| 25 | **并发控制** | s11 _claim_lock | ⚠️ | 仅单锁 |

---

## 12. 扩展路径

```
Phase 1 — 可靠性基础 (s11 + s13 已完成)
├── ✅ 结构化错误模型 (s13)
├── ✅ API 层错误恢复 (s11)
├── ⏳ 可观测性: tracing + 结构化日志
├── ⏳ 模型路由: retry + backoff + fallback
└── ⏳ 会话持久化与恢复

Phase 2 — 安全与隔离 (s07 已完成)
├── ✅ 权限管道 (s07)
├── ⏳ Hook-based 安全策略 (s08 延伸)
├── ⏳ 容器级沙箱
└── ⏳ 注入防护

Phase 3 — 工程化
├── ⏳ 依赖注入 / 配置管理重构
├── ⏳ Tool Registry 动态注册
├── ⏳ 可测试性 + Eval 框架
└── ✅ 分层 Prompt 组装 (s10)

Phase 4 — 规模化
├── ⏳ 并发控制 (分布式锁)
├── ⏳ 多租户 session 管理
├── ⏳ Rate limiting & 配额管理
└── ⏳ 完整的审计与合规
```

---

## 13. 关键架构洞察

s01 证明了 **Agent 的本质不是模型，是循环**。所有 session 证明了 **所有增强都是在这个循环的三个接缝处插入策略**：

| 接缝 | 插入的策略 | 对应 Session |
|------|-----------|-------------|
| ① LLM 调用前 | Token 估算 → 压缩决策 (s06)；分层 prompt 组装 (s10)；跨会话记忆注入 (s09)；per-turn system-reminder (s10) | s06, s09, s10 |
| ② 工具执行前 | 权限管道 (s07)；Bash 安全校验 (s07)；PreToolUse Hook 拦截 (s08)；模式检查 (s07) | s07, s08 |
| ③ 结果返回后 | 结构化错误归一化 (s13)；PostToolUse Hook 注入 (s08)；工具结果截断 (s06)；错误恢复 (s11) | s13, s08, s06, s11 |

**架构原则**：

> 在 LLM Inference ↔ Tool Execution 的往返中，Harness 应该在哪个接缝处做什么决策？

- **我应该重试这个 LLM 调用吗？** → 接缝①，错误恢复层 (s11)
- **这个工具调用安全吗？** → 接缝②，权限管道 (s07)
- **这个工具结果应该怎么呈现给模型？** → 接缝③，结果归一化层 (s13)
- **我需要记住什么跨对话？** → 接缝①③，记忆系统 (s09)

**行业共识**：MCP 规范、A2A 协议、gRPC Error Model 三个独立来源的设计原则高度一致——**工具内部错误在 result 中报告（isError），协议级错误在 transport 层处理，两者分离**。s13 的 ToolResult 设计完全对齐这一原则。
