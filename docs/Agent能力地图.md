# Agent 工程师能力地图

以下是对齐 JD 和市场实践的 Agent 系统工程能力全景。分 12 个域，每个域注明你当前的覆盖程度。

---

## 1. Agent Core Loop（核心循环）

**本质：** Model 驱动循环的工程落地

| 子能力 | 你的覆盖 |
|--------|---------|
| 消息组装（System Prompt 动态拼接、多模态消息结构） | △ 隐含 |
| 流式 API 通信（SSE / Streaming 实现） | △ 未明确 |
| Tool 并发调度（多 Tool 并行 + 结果合并） | △ 未体现 |
| 异常兜底（Tool 超时、空结果、异常传播） | ○ 有异步调度经验 |

**关联域：** → [Tool System](#2-tool-system--function-calling工具系统)（Tool 并发调度） → [Error Recovery](#11-error-recovery--resilience错误恢复与系统韧性)（异常兜底） → [Context Management](#3-context-management上下文管理)（消息组装与窗口管理）

**你的 leverage：** 字景数科的 Tool Calling 流水线 + 首都在线的异步编排 → 需要显式关联

---

## 2. Tool System / Function Calling（工具系统）

**本质：** Agent 和外部世界的接口协议

- Tool Registry：工具注册、发现、热加载
- Tool Descriptor Schema：参数描述、返回值契约
- Tool 版本管理、权限控制
- Tool 链式编排与依赖图
- **工具结果结构化 / Error Normalization**：将原始字符串输出转为结构化 JSON（`{tool, success, error: {type, retryable, suggested_action}}`），让模型从"解析错误文本"变为"读取结构化字段做决策"。核心洞察：**模型是决策者，不是解析器**

**关联域：** → [Core Loop](#1-agent-core-loop核心循环)（Tool 调度执行） → [Safety](#10-safety--governance安全与治理)（权限控制） → [MCP](#6-mcp-servermodel-context-protocol)（标准化工具协议） → [Error Recovery](#11-error-recovery--resilience错误恢复与系统韧性)（Tool 超时/异常的结构化传递）

**你的覆盖：** ○ 有 LangChain Tool Calling 使用经验，且对 Tool Result 结构化有独立设计思考（ErrorType 分类：transient/permission/not_found + suggested_action 映射），缺少自研 Tool Registry 设计

---

## 3. Context Management（上下文管理）

**本质：** 在有限窗口内最大化有用信息密度

- Prompt Caching 机制与缓存命中率优化
- Token 精确计算与预算分配
- 多级压缩策略（即时摘要 → 滚动窗口 → 关键信息持久化）
- 长对话场景下的体验保障

**关联域：** → [Error Recovery](#11-error-recovery--resilience错误恢复与系统韧性)（prompt_too_long 压缩恢复路径） → [Memory](#5-memory-system记忆系统)（跨会话持久化） → [System Prompt](#4-system-prompt-engineering系统提示词工程)（Static/Dynamic boundary 缓存策略）

**你的覆盖：** △ 做过 Token 窗口裁剪和关键信息持久化，但 Prompt Caching / 多级压缩无生产经验

---

## 4. System Prompt Engineering（系统提示词工程）

**本质：** System Prompt 不是一个巨大的硬编码字符串，而是一条可组装、可缓存、可演进的 Pipeline

- 6 段式组装：Core Instructions → Tool Listing → Skill Metadata → Memory → CLAUDE.md Chain → Dynamic Context
- Static/Dynamic Boundary 标记：稳定前缀缓存复用，动态后缀按 Turn 替换
- Per-turn System Reminder：将短生命周期上下文（当前时间、IDE 选中内容）注入 user-role 消息，不污染 system prompt
- CLAUDE.md 链式加载：User Global → Project Root → Subdirectory，逐层覆盖
- Skills metadata 注入 vs 按需加载的权衡

**关联域：** → [Context Management](#3-context-management上下文管理)（缓存策略协同） → [Memory](#5-memory-system记忆系统)（CLAUDE.md chain + Skills metadata 注入） → [Hooks](#7-hooks-system钩子系统)（Per-turn System Reminder 注入点）

**你的覆盖：** ○ 有 `system_prompt.py` 完整实现（SystemPromptBuilder + 6 段 Pipeline + CLAUDE.md chain），理解 Static/Dynamic 分离和缓存策略

---

## 5. Memory System（记忆系统）

**本质：** 让 Agent 在会话之外"记住"

- 跨会话持久化（向量数据库 + 结构化存储）
- 自动记忆提取（从对话流中识别值得记住的信息）
- 离线巩固（类似睡眠时记忆整理）
- Memory Scope 层次结构（User / Session / Global）
- 记忆召回准确率优化

**关联域：** → [Context Management](#3-context-management上下文管理)（信息持久化与窗口协同） → [System Prompt](#4-system-prompt-engineering系统提示词工程)（启动时注入） → [Hooks](#7-hooks-system钩子系统)（on_memory_recall / on_memory_store 触发点）

**你的覆盖：** ● 有 `memory_system.py` 完整实现：MemoryManager（frontmatter 解析 + 4 种类型分类 + MEMORY.md 索引重建）+ DreamConsolidator（7 道门闸：频率限制 + 前置条件 + 并发控制）+ Push/Pull 范式设计。理解 Memory 是"决策辅助层"的本质——在 session 启动时帮模型判断什么信息值得知道。可进一步补齐：向量检索召回、Hot/Cold 分层

---

## 6. MCP Server（Model Context Protocol）

**本质：** 标准化的工具/资源暴露协议，让 Agent 发现和使用外部能力

- MCP Server 实现（工具暴露、资源暴露、采样）
- MCP Client 集成（服务发现、调用路由）
- 自定义 MCP Transport（stdio / HTTP / WebSocket）
- MCP vs 自定义 Tool Registry 的设计取舍

**关联域：** → [Tool System](#2-tool-system--function-calling工具系统)（标准化工具暴露协议） → [Safety](#10-safety--governance安全与治理)（权限控制） → [Core Loop](#1-agent-core-loop核心循环)（工具发现与调用路由）

**你的覆盖：** △ 网站 learn.shareai.run 新增了 s19 MCP & Plugin 概念，理解 MCP 是标准化的工具/资源暴露协议。但本地无实现代码，仍属弱项

---

## 7. Hooks System（钩子系统）

**本质：** 在 Agent 生命周期的关键节点插入自定义逻辑

典型 Hook 点：
- pre\_tool\_call / post\_tool\_call
- pre\_response / post\_response
- on\_error / on\_timeout
- on\_memory\_recall / on\_memory\_store
- 用户偏好注入、个性化行为配置

**关联域：** → [Safety](#10-safety--governance安全与治理)（Permission Gate 本质是 Hook Pipeline 的特化） → [Error Recovery](#11-error-recovery--resilience错误恢复与系统韧性)（on_error hook 触发恢复） → [Core Loop](#1-agent-core-loop核心循环)（生命周期注入点） → [Memory](#5-memory-system记忆系统)（on_memory 事件触发）

**你的覆盖：** ● 有 `hooks_system.py` 完整实现：HookManager（SessionStart / PreToolUse / PostToolUse 三事件点）+ 三态 exit code 协议（0=继续, 1=阻止, 2=注入消息）+ JSON stdout 扩展协议（updatedInput / additionalContext / permissionDecision）+ Trust 机制（workspace marker + SDK mode）+ matcher 过滤。理解 Hook 的本质是"开闭原则在 Agent 架构中的应用——不修改 loop 的前提下注入行为"

---

## 8. Subagent / Multi-Agent（多 Agent 协作）

**本质：** 把复杂任务分解给多个 Agent 实体

- Subagent Fork 与生命周期管理
- AgentTool 模式（Agent 本身作为 Tool 被调用）
- 嵌套 Agent（Agent 内再启动 Agent）
- 并发子任务分发与结果聚合
- Inter-agent 通信协议（JSONL mailbox / 共享状态）

**关联域：** → [Error Recovery](#11-error-recovery--resilience错误恢复与系统韧性)（子 agent 故障隔离，单个 subagent 崩溃不影响主 loop） → [Context Management](#3-context-management上下文管理)（独立 messages[] = 天然上下文隔离） → [Core Loop](#1-agent-core-loop核心循环)（AgentTool 模式：Agent 本身作为 Tool 被父 Agent 调用）

**你的覆盖：** ● 有 s04/s09/s10/s11/s12 五个 session 的递进实现：Subagent Fork → JSONL mailbox 通信 → Team Protocols 请求-响应协商 → Autonomous Agents 自主认领 → Worktree 隔离。理解"独立 messages[] 数组隔离上下文"是核心机制。另外可以用 ECS 分布式调度经验类比说明并发子任务分发

---

## 9. Observability & Evaluation（可观测与评测）

**本质：** 让 Agent 行为可理解、可度量、可改进

- Agent Tracing：完整记录 Thought → Action → Observation 链路
- Token 消耗追踪、Tool 调用耗时、首 Token 延迟
- 静默失败检测（Agent 以为成功了但实际没执行）
- Evaluation Harness：自动化评测管道
- 分级评测（Easy / Medium / Hard）

**关联域：** → [Error Recovery](#11-error-recovery--resilience错误恢复与系统韧性)（静默失败检测是触发恢复的前提，Tracing 链路定位恢复点） → [Safety](#10-safety--governance安全与治理)（审计日志依赖 Tracing 链路） → [Production Serving](#12-production-serving生产服务)（C 端体验指标监控） → [Core Loop](#1-agent-core-loop核心循环)（Thought → Action → Observation 全链路 Tracing）

**你的覆盖：** ○ 有完善的可观测基础设施经验（Prometheus / Kafka / ELK），可以直接平移

---

## 10. Safety & Governance（安全与治理）

**本质：** 防止 Agent 做不该做的事

- Permission Gate（安全管道：注入检测 → Deny Rules → Mode 隔离 → Allow Rules → HITL）
- 审计日志（Audit Trail）
- 最小权限执行（Mode-based Sandboxing）
- 连续拒绝自动收紧权限

**关联域：** → [Hooks](#7-hooks-system钩子系统)（Permission Gate 本质是 pre_tool_call hook 的特化 Pipeline） → [Error Recovery](#11-error-recovery--resilience错误恢复与系统韧性)（连续拒绝熔断→权限收紧，与 error recovery 的退避机制同构） → [Tool System](#2-tool-system--function-calling工具系统)（工具级权限控制） → [Observability](#9-observability--evaluation可观测与评测)（审计日志）

**你的覆盖：** ● 有 `permission_gate.py` 完整 5 步 Pipeline：BashValidator（severe/warning 两级分类）→ Deny Rules → Mode 快速通道（plan/auto/default）→ Allow Rules → Ask User。含连续拒绝熔断（3 次→建议切 plan mode）、运行时 mode 切换、always 规则动态追加。另有 `permission_web/` Web UI 演示。核心设计哲学："Safety is a pipeline, not a boolean"

---

## 11. Error Recovery & Resilience（错误恢复与系统韧性）

**本质：** Agent 崩溃后不是"重试"，而是"告诉模型刚才发生了什么，让它自己调整"

三条恢复路径，回答同一个问题——"你告诉了模型什么？"：
- **max_tokens 续写**：注入 CONTINUATION_MESSAGE（"Continue directly, no recap, pick up mid-sentence if needed"），告诉模型"你被截断了，继续就好"，最多 3 次
- **prompt_too_long 压缩**：不是截断（粗暴删除→模型失忆），而是压缩（LLM 摘要→模型拥有完整上下文，只是更短了）
- **connection error 退避**：指数退避 + jitter（防止惊群效应），纯 harness 层扛，不需要告诉模型

核心洞察：
- **Error 也是信息**——对模型来说，error 和 tool_result 没有本质区别，都是信息输入
- 与 Permission Gate 同构——"Harness 的核心职责不是替模型做决定，是给模型足够的信息让它做更好的决定"
- 关键判断力：哪些事该让模型知道（max_tokens / prompt_too_long），哪些事不该打扰模型（connection error）

**关联域：** → [Observability](#9-observability--evaluation可观测与评测)（静默失败检测→触发恢复；Tracing 定位恢复点；没有观测就没有可靠的故障恢复） → [Context Management](#3-context-management上下文管理)（prompt_too_long 压缩恢复路径，LLM 摘要而非粗暴截断） → [Core Loop](#1-agent-core-loop核心循环)（异常兜底，error 和 tool_result 对模型来说都是信息输入） → [Safety](#10-safety--governance安全与治理)（连续拒绝熔断机制同构——都是"检测异常→收紧策略→通知模型"的模式） → [Subagent](#8-subagent--multi-agent多-agent-协作)（子 agent 故障隔离：单个崩溃不影响主 loop）

**你的覆盖：** ● 有 `error_recovery.py` 完整实现（3 条路径 + 3 次重试上限 + 主动 Token 阈值检测自动压缩），理解"信息传递 > 盲目重试"的本质

---

## 12. Production Serving（生产服务）

**本质：** 让 Agent 在真实用户面前稳定运行

- 首 Token 延迟优化（TTFT）
- 流式输出流畅度（流畅度 vs 速度均衡）
- 降级策略（Model 降级、Tool 降级）
- Circuit Breaker 与退避重试
- C 端体验指标监控

**关联域：** → [Observability](#9-observability--evaluation可观测与评测)（C 端体验指标监控：TTFT、流式流畅度、Tool 耗时） → [Error Recovery](#11-error-recovery--resilience错误恢复与系统韧性)（Circuit Breaker、Model/Tool 降级策略） → [Core Loop](#1-agent-core-loop核心循环)（首 Token 延迟优化）

**你的覆盖：** ○ 有高可用服务经验（99.9%），但 C 端 Agent 指标无直接经验

---

## 总结：你的位置

```
  核心循环       ████████░░  80%
  Tool 系统      ████████░░  75%
  Context        ████░░░░░░  40%
  System Prompt  ██████░░░░  60%
  Memory         ███████░░░  70%
  MCP            ███░░░░░░░  30%
  Hooks          ███████░░░  65%
  MultiAgent     ██████░░░░  60%
  可观测         ████████░░  80%
  安全治理       ███████░░░  70%
  Error Recovery ███████░░░  70%
  生产服务       ██████░░░░  60%
```

**策略建议：**
1. **面试中强化**：核心循环、可观测、Memory、Hooks、安全治理、Error Recovery——这些是你有完整代码实现 + 深度设计文档的优势区，要讲深、讲出设计哲学
2. **补课优先级**：MCP（s19 有概念，实现缺失）→ Context Management（多级压缩 + Prompt Caching 生产经验弱）→ Cron/Scheduler（s14 未覆盖）→ Production Serving（C 端 Agent 指标）
3. **话术策略**：MCP/Context/Production 这类弱项，用"底层架构同构性"来兜底——你做过异步编排、做过可观测基础设施、做过状态管理，只是场景从"云实例"换成了"Agent"。Context Management 可以用 s06 的 3 层压缩策略 + s11 Error Recovery 的 auto_compact 来证明你有上下文管理的工程思维，只是缺少 Prompt Caching 的生产调优经验
