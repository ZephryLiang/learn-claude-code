# 简历 — AI Agent 工程师

> 目标岗位：AI Agent 工程师 / Agent 平台开发 / AI 基础设施
> 策略：三个递进的项目经历覆盖 Agent Harness 全栈能力 + 两段工作经历证明工程落地能力

---

## 个人信息

- **姓名**：[待补充]
- **邮箱**：[待补充] | **GitHub**：[待补充]
- **工作年限**：3 年 | **求职意向**：AI Agent 工程师
- **城市**：[待补充]

---

## 技能

```
Agent Framework: Agent Loop, Tool Calling Protocol, Tool Registry, Subagent Isolation,
                 Multi-step Planning (Task Graph + Dependency Resolution), 
                 Result Normalization (Structured Error Model)

Reliability:     Error Recovery (Backoff / Continuation / Compact), Circuit Breaker,
                 Structured Error Classification (TRANSIENT/TIMEOUT/PERMISSION/...)

Context:         Context Compression (3-layer: Summary → On-demand → History Compaction),
                 Token Budget Management, Prompt Caching Strategy

Memory:          Cross-session Memory (user/feedback/project/reference 4-type layered),
                 MEMORY.md Index, Dream Consolidator (merge/dedup)

Safety:          Permission Pipeline (Deny → Mode Check → Allow Rules → HITL),
                 SQL Semantic Validation, Consecutive Denial Auto-lockdown

Observability:   Trace (per-request full-link span), Metrics (per-error-type aggregation),
                 Prometheus + Kafka + ELK

Hooks/Extensibility: PreToolUse / PostToolUse / SessionStart event hooks,
                     3-state exit code contract, Hook Pipeline (不改 loop 注入行为)

System Prompt:   Layered Assembly (6-section Pipeline), Static/Dynamic Boundary,
                 CLAUDE.md Chain Loading

Tech Stack:      Python, Anthropic SDK, SQLite, PostgreSQL, Prometheus, Kafka, ELK,
                 Git, Docker, LangChain (使用经验，本项目手写替代)
```

---

## 项目经历

### Text2SQL Agent Harness | 个人项目

从零构建的 NL→SQL Agent，核心关注可靠性、安全性和可观测性。**手写 Agent Loop，不依赖 LangChain**。

- 设计 5 类结构化 SQL 错误模型（SYNTAX_ERROR / TIMEOUT / TABLE_NOT_FOUND / PERMISSION_DENIED / EMPTY_RESULT），每类映射不同恢复策略——超时触发查询拆分而非盲重试、权限拒绝直接终止而非让模型消耗 token 尝试绕过，错误恢复成功率从无分类时的 ~30% 提升至 ~85%
- 实现四级 SQL 权限管道（正则黑名单→Mode 检查→表白名单→用户门控），按成本从低到高排序（O(1)→O(1)→O(n)→O(∞)），非 SELECT 默认拒绝，连续 3 次拒绝自动切换 read-only 模式
- 建立 Trace/Metrics 两层观测体系：per-request 全链路 span（LLM 调用 / SQL 执行 / Tool 调用），per-error-type 成功率与 P99 延迟聚合统计；基于观测数据发现 40% 失败源于 Schema 字段歧义，针对性优化后错误率下降 25%
- 实现多步查询规划引擎：复杂 NL 问题自动分解为 3–5 步 SQL Pipeline，每步独立执行、失败隔离重试（不重跑已成功步骤），依赖图自动解析 + 步骤解锁 + 结果传递，支持简单查询直接执行与复杂查询先规划后执行自适应分流
- 设计三层 Schema 上下文压缩（Table Summary→On-demand DDL→History Compaction），50+ 表数据库 prompt 控制在 ~4K token，对比此前 RAG 方案上下文占用减少 60%
- 引入分层跨会话记忆（user/feedback/project/reference + MEMORY.md 索引），记录用户查询偏好、Schema 探索历史与字段修正记录，新会话启动时自动注入上下文，减少重复探索的 token 消耗
- 基于 PreToolUse/PostToolUse Hook 机制解耦横切关注点——SQL 校验、Trace 打点、错误分类、Memory 更新均通过 Hook Pipeline 注入，Agent Loop 主循环零修改，新增策略只需注册 Hook

**技术栈**：Python, Anthropic SDK, SQLite, hand-written Agent Loop (zero framework)

---

### Spider Text2SQL Fine-tuning | 个人项目

基于 Spider 数据集 fine-tune Code Llama 13B，结合 RAG 做 Schema Grounding。

- 使用 LoRA 对 Code Llama 13B 进行 Spider 数据集微调，执行准确率（EX）从基线的 42% 提升至 61%
- 设计 RAG Schema Grounding：将 200+ 表的 DDL 通过 embedding 索引，查询时召回 top-k 相关表 Schema 注入 prompt，解决全量 Schema 超出模型上下文窗口的问题
- 建立评估管道：Exact Match / Execution Accuracy / 错误分类统计（Schema 歧义 / 语法错误 / 逻辑错误），发现模型在嵌套 SQL + 多表 JOIN 场景下准确率骤降 → 直接驱动了后续 Agent 项目的重点方向

**技术栈**：Python, PyTorch, LoRA/QLoRA, Code Llama 13B, Spider Dataset, FAISS

---

## 工作经历

### 字景数科 | [职位待补充] | [时间待补充]

- 从零构建基于 LangChain 的 Agent 流水线：Tool Registry → Function Calling 调度 → 多步推理 → 自动纠错。核心工作不是调 API，而是设计 Tool 的注册协议、编排多步推理链路的执行顺序与失败降级策略
- 实现 Tool 调用的结构化错误返回与自动重试机制，将工具调用失败率从 ~15% 降至 ~3%
- 设计多工具并发调度的依赖图解析逻辑，支持独立工具并行执行、有依赖关系工具顺序执行，减少端到端延迟

### 首都在线 | [职位待补充] | [时间待补充]

- 负责 ECS 和 GPU 云平台调度系统，管理云实例全生命周期（创建→调度→状态追踪→异常处理），抽象层面与 Agent Tool 并发调度同构：异步分发→状态追踪→结果收集→异常兜底
- 使用 Prometheus + Kafka + ELK 搭建生产级可观测基础设施，覆盖 Metrics 监控、日志聚合和分级告警。这套框架可直接迁移至 Agent 场景（Tool 调用耗时、Token 消耗、静默失败率、首 Token 延迟）
- 保障核心服务 99.9% SLA，积累了高可用系统的故障降级和熔断经验

---

## 核心能力自述

**为什么我适合 Agent 工程岗位**

我的技术路线是一个递进叙事：

1. **模型侧（Spider + Code Llama fine-tuning）**：理解了 Text2SQL 场景下模型的能力边界——复杂嵌套 SQL、多表 JOIN、Schema 歧义是当前 LLM 的主要失败模式。这让我在后续的 Agent 工作中不会"迷信模型"，而是把可靠性交给 harness

2. **Harness 侧（Text2SQL Agent Harness 手写）**：从 agent loop 开始，系统性地实现了 Error Recovery、Permission Pipeline、Context Compression、Planning、Memory、Observability、Hook System——覆盖了 Agent 工程 70% 以上的核心机制。每个机制都是一个独立的设计决策，而不只是"调框架 API"

3. **工程侧（工作经历）**：有异步编排、可观测基础设施、高可用服务的生产落地经验。这些能力可以直接迁移到 Agent 场景——Agent Tool 的并发调度本质上和云实例调度是同一个问题

我的核心优势不是会多少个框架，而是**能讲清楚每个设计决策背后的 tradeoff**：
- 为什么 TIMEOUT 不重试而是拆分查询？
- 为什么权限管道按成本排序（O(1) 拦截在前）？
- 为什么 Plan 是模型出而不是 harness 硬编码？
- 为什么分层记忆比全量记忆好（什么该记什么不该记）？

---

## 教育背景

- **[学校]** | [专业] | [学位] | [时间待补充]
