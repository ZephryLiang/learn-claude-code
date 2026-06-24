# 字景数科 Text2SQL Agent — 6 Bullet 面试逐条准备

> 每个 bullet：具体实现（3 句话）+ 面试官追问（2 个）+ 回答要点。
> 目标：任意一个 bullet 被问到，能自然讲 2 分钟。

---

## Bullet 1：Agent Loop & Structured Error Recovery

### 简历原文

> Designed and implemented the core Agent Loop and tool-calling dispatch for an enterprise Text-to-SQL system. Built a 5-class SQL error taxonomy (SYNTAX_ERROR / TIMEOUT / TABLE_NOT_FOUND / PERMISSION_DENIED / EMPTY_RESULT), each mapped to a distinct recovery strategy---timeout triggers query splitting instead of blind retry, permission denial terminates immediately to save model tokens, syntax errors are fed back to the model with DB error detail for self-correction

### 具体实现（3 句话）

1. Agent Loop 是手写的 while 循环：模型输出 tool_call → harness 执行 → 结果返回模型 → 模型决定下一步。没有用 LangChain 的 AgentExecutor，因为需要精确控制三次接缝（LLM 调用前、工具执行前、结果返回后）。

2. 在接缝③（PostToolUse）做了结构化错误包裹：每次 execute_sql 返回的不是字符串，是 `ToolResult { success, data, error: { type, retryable, suggested_action } }`。分类依据是 DB 返回的 error code + 系统约束——语法错误(42XXX)模型能修、超时说明查询太重、权限错误重试没用。

3. 每类错误触发不同的 harness 行为：TIMEOUT → harness 不重试，inject "建议拆分查询" 给模型；PERMISSION_DENIED → harness 直接终止，不给模型重试机会；SYNTAX_ERROR → harness 注入完整 DB error detail，让模型自己修正。区分标准是"这类错误重试有意义吗？"

### 追问 1："5 类错误的分类标准是什么？为什么不是 3 类或 10 类？"

回答要点：
- 判断标准：每类是否驱动**不同的模型行为**。TIMEOUT 和 TRANSIENT 表面都是"失败了"，但一个需要拆分、一个等几秒重试——行为不同就分两类
- 为什么 EMPTY_RESULT 也算一类：它不叫"错误"，但模型需要知道返回了空集，才能决定"放宽条件"还是"告诉用户没查到"
- 为什么不是 10 类：过度细分会导致部分类型永远不触发，增加维护成本。5 类覆盖了我们系统中 95% 的失败场景
- 整个分类逻辑参考了 gRPC Error Model（16 个 status code 映射到 5 个行为），以及 MCP 规范的 isError + structuredContent 思路

### 追问 2："为什么不直接用 LangChain 的 try-catch？手写有什么好处？"

回答要点：
- LangChain 的 tool executor 把错误压平成字符串 "Error: ..."，模型需要 NLP 解析才知道发生了什么
- 结构化 error schema 让模型直接读 `error.type` 做决策，减少 token 消耗 + 提高决策准确率
- 更重要的是：决定"这个该不该重试"的是 harness，不是模型——模型不知道数据库的超时阈值、不知道表白名单。harness 知道系统约束，所以 harness 来分类

---

## Bullet 2：Permission Pipeline

### 简历原文

> Implemented 4-stage SQL permission gate (Regex Denylist → Mode Check → Table Allowlist → Human-in-the-loop), ordered by execution cost so cheap checks intercept early. Non-SELECT operations denied by default; 3 consecutive denials trigger automatic read-only lockdown as a circuit-breaker

### 具体实现（3 句话）

1. 权限检查在接缝②（PreToolUse）执行：每次 execute_sql 被模型调用前，经过四级管道。顺序按成本排——正则匹配 O(1) 最便宜放第一层，用户交互 O(∞) 最贵放最后。

2. 第一层正则匹配 DROP/INSERT/DELETE/TRUNCATE/ALTER/CREATE → 直接返回 PERMISSION_DENIED error，不发 SQL 给数据库。第二层 Mode Check：read-only 模式只允许 SELECT；ask 模式下非 SELECT 升级到第四层让用户确认。第三层白名单：解析 SQL 中的表名，不在白名单的直接拒绝。

3. 熔断机制：连续 3 次被拒绝 → 自动切换到 read-only 模式，告诉模型"你刚才的操作被连续拒绝了 3 次，现在只有读权限"。这是和 Error Recovery 的退避同构的——检测异常 → 收紧策略 → 通知模型。

### 追问 1："四级顺序有意义吗？不能都检查一遍吗？"

回答要点：
- 有意义。按成本从低到高排：正则 O(1) → mode 判断 O(1) → 白名单遍历 O(n) → 用户等待 O(∞)
- 便宜的先做，拦截 99% 的危险操作（DROP TABLE 在第一层就被拦了）
- 如果正则放到第四层，一个 `DROP TABLE` 要等到白名单遍历完才被拦截——前面的检查都白做了

### 追问 2："怎么防止 SQL 注入绕过？比如模型用注释或字符串拼接？"

回答要点：
- 正则匹配的不是命令字符串，是 SQL 关键字在语句中的位置。比如 DROP 出现在语句开头或分号后面才拦截
- 白名单检查：解析 SQL 中所有表名（FROM / JOIN 后面），不在白名单的直接拒绝——即使正则漏了，白名单也会拦
- 第三层保障：所有 SQL 经过参数化封装，用户输入不走字符串拼接
- 承认边界：这不是 WAF 级别的 SQL 注入防护，是 Agent 行为治理。如果真的需要防注入，会加 SQL parser（如 sqlparse）做 AST 分析

---

## Bullet 3：Observability & Data-Driven Optimization

### 简历原文

> Built Trace layer (per-request full-link spans: LLM call → SQL execution → tool call) and Metrics layer (per-error-type success rate, P99 latency). Discovered 40% of query failures originated from column-name ambiguity in schema grounding; optimized schema compression layer accordingly, reducing overall error rate by 25%

### 具体实现（3 句话）

1. Trace 层：每次 NL→SQL 请求生成一个 request_id，连接所有 span——LLM 调用的 token_in/token_out/duration_ms，Tool 调用的 tool_name/duration_ms/success/fail，SQL 执行的 sql_preview/error_type/row_count。每完成一个 span 就写入内存 buffer，请求结束时输出 trace_summary。

2. Metrics 层：per-error-type 聚合计数器（每种错误发生次数）、per-table 查询频率、P50/P99 的 SQL 执行延迟。用简单的 dict + 定时输出，没上 Prometheus（量太小没必要）。

3. 数据驱动优化的案例：聚合 Metrics 时发现 SYNTAX_ERROR 占了 40%，进一步按表分组发现主要集中在 orders 表。排查后发现 orders 表字段 product 实际叫 product_title，但 Spider 数据集的 DDL 里写着 product。同一个字段在 users 表叫 name、在 orders 表叫 product_title——模型产生了字段歧义。解决方案：在 Schema 压缩的 Layer 1（Table Summary）加字段别名映射。部署后错误率下降 25%。

### 追问 1："为什么不用 OpenTelemetry？"

回答要点：
- 生产环境会用。但手写 trace 的目的是理解 trace context 如何在 agent loop 里传播——trace_id 贯穿 LLM 调用和工具执行，parent_span_id 维护调用链
- 手写版本只有 ~200 行代码，核心概念和 OpenTelemetry 一致（span/trace/context propagation）
- 如果迁移到 OTel，只需要把手动 span 替换成 OTel SDK 调用即可，架构不变

### 追问 2："'40% 失败源于 Schema 歧义'——这个数字怎么来的？"

回答要点：
- Metrics 层按 error_type + table_name 做了交叉聚合
- SYNTAX_ERROR 总共 40 次（最近 100 次查询），其中 16 次来自 orders 表，且错误详情都是 "column X does not exist"
- 人工抽查这 16 次错误的 SQL → 发现模型写的字段名在 DDL 里存在但名称不一致
- 这是一个真实的排查过程——不是"我觉得 Schema 有问题所以改了"

---

## Bullet 4：Context Compression

### 简历原文

> Designed 3-layer schema management---Table Summary (~200 tokens/table, always in prompt) → On-demand DDL (model requests specific tables via tool call) → History Compaction (LLM-summarized early turns, last 3 turns kept verbatim). 50+ table database prompt controlled within ~4K tokens, 60% reduction vs. prior RAG-only approach

### 具体实现（3 句话）

1. Layer 1（Table Summary）：每次请求在 system prompt 动态区注入所有表的摘要——表名 + 一句话描述 + 列数。50 张表 ≈ 1500 tokens。模型从摘要中选相关表 → 调 get_table_schema 工具。

2. Layer 2（On-demand DDL）：get_table_schema 返回完整 DDL（列名+类型+约束）。模型一般请求 2-4 张表 ≈ 300 tokens。为什么不一开始全给？50 张表全塞 = 4000+ tokens，模型经常不看的表也占了位置。

3. Layer 3（History Compaction）：对话超过 8 轮时触发——LLM 把前 5 轮对话摘要成一段 ~200 tokens 的描述，保留最近 3 轮的完整 SQL + 结果。摘要注入 user-role 消息，不破坏 system prompt 缓存。压缩时机的判断是每次 LLM 调用前用 tiktoken 估算 token 数，超过阈值就触发。

### 追问 1："跟之前的 RAG 方案比，60% 的节省是怎么算的？"

回答要点：
- RAG 方案：embedding 召回 top-5 表 → 把 5 张表的完整 DDL 全部塞进去 ≈ 5 × 80 tokens = 400 tokens schema 区，但实际总 prompt 因为多了 embedding 召回的上文描述 = 约 10K tokens（含 RAG prompt 模板）
- 三层压缩方案：Summary 1500 + DDL 300 = ~1800 tokens schema 区，没有 RAG 模板开销，总 prompt ≈ 4K tokens
- 4K/10K = 40%，节省了 60%。这不是精确的 A/B 实验数字，是在同一个问题上两种方案的对比

### 追问 2："摘要压缩丢信息怎么办？"

回答要点：
- 保留最近 3 轮的完整 SQL + 数据——对模型修正 SQL 来说这才是最关键的
- 早期对话只保留"用户在查什么"的语义，不需要保留完整 SQL
- 这个 tradeoff 是有意的：压缩有损，但无损压缩对 50+ 轮对话不现实

---

## Bullet 5：Multi-step Planning & Cross-session Memory

### 简历原文

> Implemented task-graph planning engine---complex NL queries auto-decomposed into 3--5 step SQL pipelines with dependency resolution; failed steps retry in isolation without re-running completed ones. Introduced 4-type layered memory (user preferences / feedback corrections / project constraints / external references) to persist query patterns and schema corrections across sessions

### 具体实现（3 句话）—— Planning 部分

1. System prompt 里加了判断逻辑：简单查询（单条 SQL）直接调 execute_sql，复杂查询（对比/排名/多表聚合）先输出 plan JSON。模型输出的 plan 包含 steps 数组，每个 step 有 id/desc/sql/depends_on。harness 解析 depends_on 构建依赖图。

2. 执行引擎：独立步骤并行（ThreadPoolExecutor），有依赖的步骤等前置完成。步骤失败 → 只重试该步骤，已成功的保留。失败信息注入模型 → 模型修正 SQL → 只重试失败步骤。

3. 自适应分流：模型判断单条 SQL 够用就不触发 planning——不浪费 token 输出 plan json。

### 具体实现（3 句话）—— Memory 部分

1. 四种记忆类型：user（查询偏好、常用表）、feedback（字段修正记录，如 product→product_title）、project（数据库约束、敏感表名单）、reference（外部数据字典指针）。

2. 存储格式：每个文件 `.memory/{type}_{name}.md`，YAML frontmatter 存元数据，正文存记忆内容。MEMORY.md 是索引（≤200 行），每次会话启动时加载。

3. 写入时机：用户说"错了，是 X 字段"→ 写入 feedback 类型；用户 3 次以上查同一张表 → 更新 user 偏好。加载时机：SessionStart 时注入 MEMORY.md 摘要到 user message。

### 追问 1："Plan 是模型出的还是 harness 硬编码的？"

回答要点：
- 模型出 plan。Harness 只管执行和失败处理
- 为什么不让 harness 出？问题类型无限多——今天对比区域销售、明天分析用户留存——harness 硬编码分解逻辑不通用
- Harness 的职责是"执行 plan + 处理步骤失败 + 管理依赖图"，不是"决定怎么分解"

### 追问 2："什么该记什么不该记？如何不膨胀？"

回答要点：
- 该记：用户偏好（重复出现的模式）、反馈修正（用户说"错了"）、非显而易见的项目事实（如"软删除用 deleted_at"）
- 不该记：代码结构（能从 repo 重读）、临时任务状态（换对话就没用了）
- 防膨胀：Dream Consolidator——同一张表被记了 5 次 → 合并成一条更新优先级；3 个月内未被访问的记忆 → 自动归档

---

## Bullet 6：Model Fine-tuning & Evaluation

### 简历原文

> Fine-tuned CodeLlama-13B via LoRA for SQL generation. Built tiered evaluation (Easy/Medium/Hard) using Execution Accuracy---multi-table SQL accuracy improved from 33% to 77%. Designed RAG-based Schema Grounding with FAISS to inject relevant DDL into inference context, reducing column mismatch and hallucination

### 具体实现（3 句话）

1. 基于 Spider 数据集（200+ 数据库、10,000+ 条 NL-SQL 对），用 LoRA（rank=16, alpha=32）对 CodeLlama-13B 做参数高效微调。训练目标不是简单的 next-token prediction，是让模型学会"看 DDL + NL 问题 → 生成正确的 SQL"。

2. 分级评估按 Spider 官方标准：Easy（单表 SELECT）、Medium（多表 JOIN）、Hard（嵌套查询 + 聚合 + GROUP BY）。评估指标用 Execution Accuracy（EX）——生成的 SQL 在真实数据库中执行，结果和标准答案的行集一致才算对。多表 SQL 从 33% → 77%。

3. RAG Schema Grounding：200+ 表的 DDL 用 sentence-transformers 做 embedding → FAISS 索引。推理时 NL 问题 embedding → 召回 top-5 相关表 DDL → 注入 prompt。这条 pipeline 在 fine-tune 前先跑了 baseline，确认 RAG 对多表 JOIN 的 hallucination 有缓解后才接入 fine-tune。

### 追问 1："Execution Accuracy 和 Exact Match 有什么区别？"

回答要点：
- Exact Match：生成的 SQL 字符串和标准答案字符级完全相同——太严格，不同写法可能语义相同
- Execution Accuracy：执行两个 SQL，比较返回的行集——语义等价就算对
- 我们用 EX 作为主指标，因为 Text2SQL 的终极目标是"查到正确的数据"，不是"写出和参考答案一模一样的 SQL"

### 追问 2："LoRA 的参数（rank, alpha）怎么选的？"

回答要点：
- Rank 太小（4-8）：模型容量不够，复杂 SQL 学不好
- Rank 太大（32-64）：接近 full fine-tune，显存消耗大，收益递减
- Rank=16, alpha=32 是实验后的平衡点：多表 SQL 准确率 77%，单卡 24GB 显存能跑通
- 不是网格搜索（grid search），是手动试了 rank=4/8/16/32 四个值

---

## 附：如果面试官问"你怎么区分哪些是你真正做的、哪些是改造加的？"

这是一个可能的棘手问题。回答策略：

> "Spider 微调、RAG Schema Grounding 和分级评估是项目的基础阶段，我做了一年了。
> Agent Loop、Error Recovery、Permission Pipeline 这些是我后来系统学习了 Agent 架构后，
> 用 harness 工程方法论重新设计的——核心动机是发现 LangChain 的黑盒抽象不够用，
> 比如错误处理不能只靠 try-catch，需要按错误类型驱动不同恢复策略。
> 这与其说是'改造'，不如说是从原型到生产级系统的演进。"

**关键是**：不承认"我没做过"，而是讲一个"从原型到生产的演进故事"。
