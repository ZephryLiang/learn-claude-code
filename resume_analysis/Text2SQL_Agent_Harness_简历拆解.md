# Text2SQL Agent Harness — 简历 Bullet 逐条拆解

> 每个 bullet 不是"我做了什么功能"，而是"我做了哪个 Agent 工程决策，对应能力地图的哪个机制"。
> 面试官问任何一个 bullet，你都能展开：**为什么这样做 → 不这样做会怎样 → 技术上的取舍**。

---

## Bullet 1：结构化错误恢复

### 简历原文

> 设计 5 类结构化 SQL 错误模型（语法/超时/表不存在/权限/空结果），每类对应不同恢复策略，错误恢复成功率从无分类时的 ~30% 提升至 ~85%

### 能力地图对应

| 维度 | 对应 session | 你实现了什么 |
|------|------------|------------|
| 结构化错误模型 | **s13** Result Normalization | `ToolResult { success, data, error: { type, retryable, suggested_action } }` |
| 分类驱动恢复 | **s11** Error Recovery | 5 类错误 → 5 条不同恢复路径，不是"所有错误都重试" |
| 接缝位置 | 接缝③（结果返回后） | 工具执行完后，在结果注入模型之前做分类+策略决策 |

### 每一类错误的 Agent 工程逻辑

```
TRANSIENT (暂时性连接失败)
  ↓
  模型看到的结果: { "success": false, "error": { "type": "TRANSIENT", "retryable": true } }
  模型决策: 等 2 秒后重试同一个 SQL
  为什么不盲重试: 在 harness 层做 backoff retry（exponential + jitter），
                 不让模型消耗 token 来自己判断"要不要重试"

SYNTAX_ERROR (SQL 语法错误)
  ↓
  模型看到的结果: { "success": false, "error": { "type": "SYNTAX_ERROR", "retryable": false, 
                  "suggested_action": "MODIFY_SQL", "db_error_detail": "...syntax error at 'FROM'" } }
  模型决策: 根据 db_error_detail 修正 SQL 语法
  为什么不需要 harness 介入: 这是模型能力范围内的事，把详细错误信息给模型就行

TIMEOUT (查询超时 > 30s)
  ↓
  模型看到的结果: { "success": false, "error": { "type": "TIMEOUT", "retryable": false,
                  "suggested_action": "SPLIT_QUERY", "timeout_seconds": 30 } }
  模型决策: 拆分查询（加 LIMIT / 缩小时间范围 / 分步查）
  为什么不能重试: 超时说明查询本身太重，重试只会再超时一次，
                正确的策略是拆分——这是 Agent 工程判断，不是模型能决定的

TABLE_NOT_FOUND
  ↓
  模型看到的结果: { "success": false, "error": { "type": "TABLE_NOT_FOUND", "retryable": false,
                  "suggested_action": "LOAD_SCHEMA", "attempted_table": "users_2023" } }
  harness 侧自动动作: 触发 get_table_schema 工具，把可用表名列表注入上下文
  模型决策: 根据真实表名修正 SQL
  为什么不能重试: 表名错了重试 100 次也没用，需要工具辅助

PERMISSION_DENIED (试图写操作)
  ↓
  模型看到的结果: { "success": false, "error": { "type": "PERMISSION_DENIED", "retryable": false,
                  "suggested_action": "ASK_USER" } }
  为什么不让模型继续: 直接终止当前 chain，不消耗模型 token 尝试"换个方式绕过"
```

### 面试中可以展开的方向

- **为什么不是简单的 try-catch？** → 因为 try-catch 把所有错误压平了，模型需要 NLP 解析字符串才知道发生了什么。结构化 error schema 让模型直接读 `error.type` 做决策，减少 token 消耗 + 提高决策准确率
- **为什么 5 类而不是 3 类或 10 类？** → 判断标准是：每类是否驱动**不同的模型行为**。TIMEOUT 和 TRANSIENT 表面都是"失败了"，但一个需要拆分、一个需要重试——行为不同就分两类。空结果不算"错误"但需要模型知道"结果集为空"来做下一步判断
- **Error type 谁定义的？** → harness 定义（不是模型猜），因为错误的可重试性取决于系统约束（表白名单、超时阈值、SQL 语法校验规则），不是模型能知道的

---

## Bullet 2：权限管道

### 简历原文

> 实现四级 SQL 权限管道（黑名单→模式检查→表白名单→用户门控），所有非 SELECT 默认拒绝，敏感表查询需用户交互确认

### 能力地图对应

| 维度 | 对应 session | 你实现了什么 |
|------|------------|------------|
| 权限管道 | **s07** Permission System | 四级 Pipeline：deny → mode → allow → ask |
| 安全校验 | **s07** BashSecurityValidator | SQL 语义级校验（DROP/INSERT/DELETE 正则） |
| 用户门控 | **s07** ask_user() | y/n/always 三级响应 |
| 接缝位置 | 接缝②（工具执行前） | 在 execute_sql 真正执行前插入权限检查 |

### 四级管道的每一层

```
Level 1: 正则黑名单 → 直接拒绝，不进入后续流程
  匹配: DROP TABLE, INSERT INTO, DELETE FROM, TRUNCATE, ALTER, CREATE
  行为: 立即返回 PERMISSION_DENIED error，不发 SQL 给数据库
  为什么放第一层: 零成本、零延迟，拦截 99% 的危险操作

Level 2: Mode Check → 模式决定基础权限
  read-only mode:  只允许 SELECT，其他全部拒绝
  ask mode:        对非 SELECT 语句升级到 Level 4（用户确认）
  为什么需要: 不同场景不同策略——demo 时用 read-only，开发调试时用 ask

Level 3: Table 白名单 → 限制查询范围
  配置: allowed_tables = ["users", "orders", "products"]
  行为: 解析 SQL 中的表名，不在白名单的返回 PERMISSION_DENIED
  为什么需要: Schema 50 张表但不都让查，敏感表（salary, user_passwords）永远不可访问

Level 4: 用户交互门控 → 最后一道防线
  触发条件: 敏感表查询 / ask mode 下的 DML / 模型请求过多数据
  行为: ask_user("模型想查询 employees.salary，允许吗？") → y/n/always
        y → 允许本次    n → 拒绝并记录    always → 加白名单规则
  为什么放最后: 用户交互成本高（阻塞 loop），只在必要时触发
```

### 面试中可以展开的方向

- **为什么不用 LangChain 的权限？** → LangChain 没有内置权限管道，它的 tool 执行是直接透传的。手写 loop 才能在每个 tool call 前插入权限检查
- **四级的顺序有意义吗？** → 有——按成本从低到高排：正则匹配 O(1) → mode 判断 O(1) → 白名单 O(n) → 用户交互 O(∞)。便宜的拦截先做，不让简单的危险操作走到用户那里
- **怎么防止 SQL 注入/绕过的？** → 正则匹配的是 SQL 关键字而非命令字符串、解析表名做白名单校验、非白名单表直接拒绝——三层组合防御，不是单点
- **"熔断机制"有吗？** → 连续 3 次 deny → 自动切换到 read-only mode（你能力地图 s07 里的 consecutive_denials 熔断逻辑）

---

## Bullet 3：可观测性

### 简历原文

> 建立 Trace/Metrics 两层观测体系，基于观测数据发现 40% 失败源于 Schema 歧义，针对性优化后错误率下降 25%

### 能力地图对应

| 维度 | 对应 session | 你实现了什么 |
|------|------------|------------|
| Trace 层 | 能力地图 §7（⚠️ 部分覆盖） | per-request 全链路 span 记录 |
| Metrics 层 | **s13** ErrorSummary | per-error-type 聚合统计 |
| 数据驱动优化 | — | 用观测数据找到根因 → 针对性改进 |

### Trace 层：单次请求的完整链路

```
Request #a3f2b1: "查一下上个月注册的用户中，买过手机的"
  │
  ├─ [LLM Call #1] span_id=1a
  │   model: claude-sonnet-4-6
  │   tokens: {in: 2847, out: 156, cache_hit: 2100}
  │   duration_ms: 1203
  │   tool_calls: [get_table_schema("users"), get_table_schema("orders")]
  │
  ├─ [Tool: get_table_schema] span_id=1b, parent=1a
  │   input: {"table": "users"}
  │   duration_ms: 45
  │   result: "OK, 12 columns, 3 indexes"
  │
  ├─ [Tool: get_table_schema] span_id=1c, parent=1a
  │   input: {"table": "orders"}
  │   duration_ms: 38
  │   result: "OK, 8 columns"
  │
  ├─ [LLM Call #2] span_id=2a
  │   tokens: {in: 3350, out: 243}
  │   duration_ms: 1845
  │   tool_calls: [execute_sql("SELECT ... FROM users JOIN orders ...")]
  │
  ├─ [Tool: execute_sql] span_id=2b, parent=2a
  │   sql_preview: "SELECT u.name, o.product FROM users u JOIN orders o ..."
  │   error: { type: "SYNTAX_ERROR", detail: "column o.product does not exist" }
  │   duration_ms: 120
  │
  ├─ [LLM Call #3] span_id=3a
  │   model 读取错误信息 → 修正 SQL: "o.product_name"
  │
  ├─ [Tool: execute_sql] span_id=3b, parent=3a
  │   duration_ms: 85
  │   row_count: 234
  │   success: true
  │
  └─ Trace Summary:
      total_duration_ms: 3756
      llm_calls: 3
      total_tokens: 6596
      sql_executions: 2 (1 failed → 1 success)
      avg_llm_latency_ms: 1389
```

### Metrics 层：聚合统计

```
per-error-type 成功率（最近 100 次）:
  SYNTAX_ERROR:      23% → 修正后 %?
  TABLE_NOT_FOUND:   12% → 修正后 %?
  EMPTY_RESULT:      18%
  TIMEOUT:            5%
  PERMISSION_DENIED:  3%

per-table 查询频率:
  users:      42
  orders:     38
  products:   15
  inventory:   5

P99 SQL 执行延迟:
  users JOIN orders:  3200ms  ← 瓶颈
  users lookup:         85ms
```

### 面试中可以展开的方向

- **为什么不用 OpenTelemetry？** → 生产环境会用，但手写 trace 的目的是理解 trace context 如何在 agent loop 中传播。`trace_id` 贯穿 LLM 调用和工具执行，`parent_span_id` 维护调用链——这就已经在做 OpenTelemetry 的核心概念了
- **观测数据怎么反哺系统改进？** → 发现 40% 失败来自 Schema 歧义（users.name vs orders.customer_name 同义不同名）→ 在 Schema 压缩层加了字段别名映射 → 错误率下降 25%。这是数据驱动的工程决策，不是凭感觉改代码
- **Trace 和 Metrics 有什么区别？** → Trace 回答"这次请求发生了什么"，Metrics 回答"过去 1000 次请求的整体趋势"。两个用途——单个问题排查用 Trace，系统优化用 Metrics

---

## Bullet 4：Schema 上下文压缩

### 简历原文

> 设计三层 Schema 上下文管理（摘要→按需加载→历史压缩），将 50+ 表数据库的 prompt 控制在 ~4K token，对比 RAG 方案上下文占用减少 60%

### 能力地图对应

| 维度 | 对应 session | 你实现了什么 |
|------|------------|------------|
| 上下文压缩 | **s06** Context Compression | 三层策略：summary → lazy-load → history compact |
| Token 管理 | 接缝①（LLM 调用前） | 在调用 LLM 之前精确控制注入多少 Schema 信息 |
| 对比 RAG | 你已有的 Spider 经验 | 两种方案做同一个问题，能讲 tradeoff |

### 三层 Schema 管理的具体设计

```
Layer 1: Table Summary（始终在 prompt 中，~200 tokens/表）

  首次请求时注入：
  "数据库包含以下表：users(用户信息, 12列), orders(订单记录, 8列),
   products(商品信息, 15列), inventory(库存, 6列), ..."
  
  总共 50 表 × ~30 tokens/行 = ~1500 tokens
  模型从中选择相关表 → 调用 get_table_schema("users", "orders")

Layer 2: On-demand DDL（模型主动请求时才加载）

  模型调 get_table_schema("users") →
  harness 返回完整 DDL:
  "users: id INT PK, name VARCHAR, email VARCHAR, phone VARCHAR,
   registered_at DATETIME, status ENUM('active','inactive'), ..."
  
  单表 DDL ~80 tokens，模型一般请求 2-4 张表 = ~300 tokens
  为什么要 load-on-demand: 不要一开始塞全部 DDL，50 张表全塞 = 4000+ tokens

Layer 3: History Compaction（对话超 N 轮触发）

  当 messages > N 轮后:
  - LLM 摘要前 N-3 轮的对话: "用户之前查询了用户注册统计，结果包含 234 行，
    模型发现 orders 表缺少 product 字段后修正了 SQL"
  - 保留最近 3 轮的完整 SQL + 结果
  - 摘要注入用户消息层（不破坏 system prompt 缓存）
```

### RAG vs 上下文压缩：两种方案的对比（你独有的叙事）

你在 Spider 项目中用了 RAG 做 Schema 提取，现在用了上下文压缩。面试时可以讲清楚两者的定位差异：

| 维度 | RAG（Spider 方案） | 三层压缩（Agent 方案） |
|------|-------------------|----------------------|
| Schema 选择 | 检索时决定（embedding → top-k 表） | 模型运行时决定（读 summary → 主动请求 DDL） |
| 优势 | embedding 召回比关键词匹配准 | 模型自己判断，不用预设 k 值 |
| 劣势 | top-k 可能漏掉模型需要的表 | 多一次 tool call（get_table_schema） |
| 适用场景 | Schema 非常大（500+ 表），k 固定 | Schema 中等（50-200 表），模型需要精确控制 |
| 上下文效率 | 不需要 tool call，但 embed 有延迟 | 额外 tool call 成本 ~40ms, ~50 tokens |

**重点叙事**：你两种都做过，能判断什么时候该用哪种。这不是"我用了 X 技术"，而是"我根据场景选了 X"。

### 面试中可以展开的方向

- **怎么知道压缩到了 ~4K token？** → 每次 LLM 调用前用 tiktoken 估算 token 数，超过阈值时触发压缩。不是在猜
- **摘要压缩丢信息怎么办？** → 保留最近 3 轮的完整 SQL + 数据，对模型修正 SQL 来说这才是最关键的信息。早期对话只保留"用户在查什么"的语义就够了
- **为什么不直接用 Anthropic 的 prompt caching？** → 三层压缩和 prompt caching 是互补的，不是替代。system prompt 中的 Layer 1（table summary）可以 cached，Layer 2（DDL）随 tool call 变化不能 cache

---

## Bullet 5：多步查询规划

### 简历原文

> 实现多步查询规划：复杂 NL 问题自动分解为 3-5 步 SQL pipeline，每步独立执行、失败隔离重试，跨步骤结果自动传递与汇总

### 能力地图对应

| 维度 | 对应 session | 你实现了什么 |
|------|------------|------------|
| 任务规划 | **s03** TodoWrite | 模型先输出 JSON plan，每步一个 task + 依赖关系 |
| 步骤间依赖 | **s12** Task System | `blockedBy` / `blocks` 依赖图，前置步骤未完成 → 后续步骤不执行 |
| 执行隔离 | **s11** Error Recovery | 某步失败 → 只重试那一步，不从头来 |
| 接缝位置 | 接缝①（LLM 调用后） + 接缝③（结果返回后） | 模型输出 plan 后 → harness 逐步骤驱动执行 → 每步结果决定下一步行为 |

### 多步规划的完整流程

```
用户: "对比各区域销售额，找出每个区域的 top 3 产品"

  Step 0: 规划阶段（接缝①：模型输出 plan）

  模型看到 system prompt 中的规划指令 →
  输出结构化 Plan JSON:
  {
    "steps": [
      {"id": 1, "desc": "获取所有区域列表", 
       "tool": "execute_sql", "sql": "SELECT DISTINCT region FROM stores", 
       "depends_on": []},
      {"id": 2, "desc": "每个区域的总销售额", 
       "tool": "execute_sql", "sql": "SELECT region, SUM(amount) FROM orders...", 
       "depends_on": []},
      {"id": 3, "desc": "每个区域按产品排名", 
       "tool": "execute_sql", "sql": "SELECT region, product, RANK() OVER (PARTITION BY region ORDER BY SUM(amount) DESC)...", 
       "depends_on": [1, 2]},
      {"id": 4, "desc": "过滤 top 3", 
       "tool": "execute_sql", "sql": "SELECT * FROM (...) WHERE rank <= 3", 
       "depends_on": [3]},
      {"id": 5, "desc": "汇总结果生成自然语言回答", 
       "tool": "none", 
       "depends_on": [4]}
    ]
  }

  Step 1-5: 执行阶段（接缝③：每步执行完回调）

  harness 解析 depends_on 图：
    Step 1 ──independent──▶ 直接执行 ✓
    Step 2 ──independent──▶ 直接执行 ✓
    Step 3 ──blocked by [1,2]──▶ 等 1 和 2 完成 → 执行 ✓
    Step 4 ──blocked by [3]──▶ 等 3 完成 → 执行 ✓（但 Step 3 SQL 语法错了）
                                   │
                                   └─→ 只重试 Step 3（SQL 加引号），Step 1/2 不重跑
    Step 3 重试成功 → Step 4 自动解锁 → 执行 ✓
    Step 5 ──blocked by [4]──▶ 等 4 完成 → 模型汇总，不调 tool ✓
```

### 关键设计决策

**决策 1：plan 是模型出还是 harness 出？**

```
方案 A: harness 硬编码分解逻辑 → 不通用，换一个问题类型就废了
方案 B: 模型输出 plan → 利用模型的推理能力，任何问题类型都能分解

选了 B。harness 的职责是"执行 plan"+"处理步骤失败"，不是"决定怎么分解"。
```

**决策 2：依赖图怎么处理？**

```
最简单的实现:
  for step in plan["steps"]:
    result = execute(step)
  
问题: 
  - Step 1 和 Step 2 没有依赖，可以并行
  - Step 3 依赖 Step 1 和 2，必须等两者都完成
  
正确实现:
  1. 扫描所有 step，找到 depends_on=[] 的 → 并行执行（ThreadPoolExecutor）
  2. 每完成一个 step → 检查哪些 step 的 blockedBy 解除了
  3. 解除的 step → 进入执行队列
  4. 某 step 失败 → 只把依赖它的 step 标记为 blocked，不阻塞其他独立 step
  
这本质上是 s12 Task System 的依赖解析逻辑。
```

**决策 3：步骤失败怎么处理？**

```
Step 3 执行失败（SQL 语法错误）:
  - 不重试 Step 1 和 Step 2（它们成功了，没有理由重跑）
  - Step 3 的错误注入模型 → 模型修正 SQL → 重试 Step 3
  - Step 4 和 Step 5 对应的就是"新的 Step 3 输出"，自动继��执行
  
harness 做的事:
  step.status = FAILED
  → 注入错误上下文: "Step 3 failed with SYNTAX_ERROR: ... Please fix the SQL."
  → 模型返回修正后的 SQL
  → step.status = IN_PROGRESS → 重新执行
  → step.status = COMPLETED
  → 清理 steps[4].blockedBy 中的 3
```

**决策 4：什么时候触发 planning，什么时候直接执行？**

```
简单查询（模型判断 1 条 SQL 能搞定）:
  "查一下用户表中注册最早的 10 个用户"
  → 不触发 planning，直接 execute_sql

复杂查询（模型判断需要多步才触发）:
  system prompt 中加判断逻辑:
  "If the user's question can be answered with a single SQL query, use execute_sql 
   directly. If it requires multiple steps (e.g., comparison, ranking, multi-table 
   aggregation with conditions), FIRST output a plan JSON with step dependencies."
```

### 面试中可以展开的方向

- **Planning 和 Tool Calling 是什么关系？** → Tool Calling 是执行。Planning 是"执行之前先想好要调几次 tool、顺序是什么"。Planning 的输出是一个 task graph，工具执行是遍历这个 graph
- **模型不会规划怎么办？** → system prompt 中给 2-3 个 few-shot example，展示"什么问题 → 需要分解成几步"。模型看了例子就能模仿。不需要 fine-tune
- **plan 太大（10+ 步）怎么控制？** → 限制 max_steps=5，超过 5 步的 plan → harness 拒绝执行 → 提示模型"你的 plan 太细了，合并一下"
- **为什么不直接用 LangChain 的 AgentExecutor？** → 它没有依赖图的概念，工具调用是线性的。你需要"Step 3 等 Step 1+2 都完成后再跑"→ 手写 harness 才能做到

---

## Bullet 6：跨会话 Memory

### 简历原文

> 引入分层跨会话记忆（user/feedback/project/reference），记录用户查询偏好、Schema 探索历史与修正记录，新会话启动时自动恢复上下文，减少重复探索的 token 消耗

### 能力地图对应

| 维度 | 对应 session | 你实现了什么 |
|------|------------|------------|
| 分层记忆 | **s09** Memory System | 四种记忆类型 + MEMORY.md 索引 |
| 文件持久化 | **s09** frontmatter | .memory/*.md 文件 + YAML frontmatter |
| 启动加载 | 接缝①（LLM 调用前） | SessionStart 时注入 memory 摘要 |
| 运行时写入 | 接缝③（结果返回后） | 每次查询完成后判断"要不要记" |

### 四种记忆，在 Text2SQL 场景下存什么

```
.memory/
├── MEMORY.md                ← 索引文件，每次会话启动时加载
├── user_profile.md          ← user 类型：用户的查询偏好
├── feedback_corrections.md  ← feedback 类型：用户说"错了"时的修正记录
├── schema_constraints.md    ← project 类型：数据库约束、敏感表名单
└── external_sources.md      ← reference 类型：外部数据字典/知识库指针
```

**具体内容示例：**

```yaml
# user_profile.md
---
name: user-query-preferences
description: "用户在 Text2SQL 场景下的查询习惯和偏好"
metadata:
  type: user
---
- preferred_tables: [users, orders, products]  # 用户最常查的表
- common_date_column: registered_at
- aggregation_preference: monthly  # 用户偏好月度聚合
- timezone: Asia/Shanghai
- output_format: table  # 用户偏好表格输出而非文本
- last_query_context: "用户在分析 2024 年各渠道用户留存率"
```

```yaml
# feedback_corrections.md
---
name: schema-corrections
description: "模型理解错误的表/字段名，用户纠正过一次后不再犯"
metadata:
  type: feedback
---
- wrong: users.name → right: users.full_name
  原因: "name 是 full_name 的别名，但 Spider 数据集中用 full_name"
- wrong: orders.price → right: orders.unit_price
  原因: "price 字段实际名为 unit_price，模型多次搞混"
- SQL 偏好: "用户明确说过不要用子查询，要 JOIN"
  为什么记: 用户的编码规范约束，不是语法问题
```

```yaml
# schema_constraints.md
---
name: database-constraints
description: "数据库的物理约束和业务规则"
metadata:
  type: project
---
- 敏感表（永远不可查询）: [salaries, user_passwords, payment_tokens]
- 表名全小写，下划线分隔（Spider 数据集约定）
- orders.status 的合法值: ['pending', 'shipped', 'delivered', 'cancelled']
- 所有表有 created_at 和 updated_at 字段，没在 DDL 里显式写但实际存在
- users.deleted_at IS NULL 才表示活跃用户（软删除约定）
```

### 加载与写入机制

```
SessionStart（接缝①: LLM 调用前）:

  1. 读取 MEMORY.md → 解析索引 → 获取所有 memory 文件的摘要
  2. 与当前查询相关的 memory → 注入 user message:
     "[Memory Loaded]
      User prefers monthly aggregation on users.registered_at.
      Previously corrected: users.name is actually users.full_name.
      Sensitive tables: salaries, user_passwords, payment_tokens.
      Database convention: soft-delete via deleted_at IS NULL."
  3. 模型读完这段 → 就不会再用 users.name 了，也不会去查 salaries 表

Runtime（接缝③: 结果返回后）:

  条件 → 写入动作:
    用户说"错了，是 X 字段" → 写入 feedback_corrections.md → 重建 MEMORY.md 索引
    用户频繁查同一张表 3 次以上 → 写入 user_profile.md (preferred_tables 更新)
    发现新的 schema 约束 → 写入 schema_constraints.md → 重建索引
    用户沉默了（5+ 轮交互无新 memory）→ 触发 DreamConsolidator 去重/合并
```

### 为什么不是全量记忆而是分层

```
如果只有一个 memory 文件（全量）:
  - 每次启动全部加载 → 2000 条记忆 = 5000 tokens → 浪费
  - 难以判断"什么时候该读什么"

分层后:
  - session 启动时: 只加载 MEMORY.md 索引（~200 tokens）+ 与当前查询相关的摘要
  - 需要详细记忆时: 模型可以调用 get_memory("user_preferences") 按需读取
  - 写入时: 自动判断类型 → 写入对应文件 → 更新索引

分层回答了同一个问题: "在 2000 条记忆中，现在该给模型看哪 3 条？"
```

### 面试中可以展开的方向

- **什么该记，什么不该记？** → 这是 s09 的核心设计原则。代码结构不该记（能从 repo 重读）、临时任务状态不该记（换对话就没用了）。该记的是：用户偏好、重复出现的修正、非显而易见的项目事实（如"软删除约定"）、外部资源指针
- **记忆不会膨胀吗？** → Dream Consolidator 做合并去重。同一张表被记录了 5 次 → 合并成一条 + 更新优先级。3 个月没被访问的记忆 → 自动归档。这跟你在 s09 学的 7 道门闸逻辑一样
- **和 RAG 的向量检索什么关系？** → 向量检索解决"找什么"，分层记忆解决"什么时候该看什么"。两者互补：向量检索是 recall 机制，分层是 scope 控制。你两种都懂，能说清楚区别
- **这个和 Prompt Caching 能一起用吗？** → 能。Memory 注入的内容属于"缓慢变化"（s10 的 Section 4），可以放在 system prompt 缓存边界之前。首次注入后 Anthropic 自动缓存 5 分钟，后续请求不消耗 memory token

---

## Hook System 怎么串联所有 Bullet

Hook 不作为独立 bullet 写进简历，但在面试时是串联所有机制的扩展点。面试官问"你的系统怎么扩展的"，你可以画这张图：

```
Agent Loop（不改）
     │
     ├── [PreToolUse] hooks
     │     ├─ validate_sql       ← Bullet 2 权限管道在 Hook 里
     │     └─ start_span         ← Bullet 3 trace 开始
     │
     ├── [PostToolUse] hooks
     │     ├─ classify_error     ← Bullet 1 错误分类在 Hook 里
     │     ├─ end_span           ← Bullet 3 trace 结束
     │     ├─ check_anomaly      ← 异常检测（结果集过大 → 提示模型加 LIMIT）
     │     ├─ update_memory      ← Bullet 6 记忆更新
     │     ├─ audit_log          ← 审计日志
     │     └─ check_compaction   ← Bullet 4 轮次计数 → 触发 compact?
     │
     └── [SessionStart] hooks
           ├─ load_memory_index  ← Bullet 6 启动加载记忆
           └─ inject_user_profile ← Bullet 6 注入用户偏好
```

**为什么不是独立 bullet 但面试要讲：**

- 它证明你的系统不是堆功能——权限、trace、错误分类、记忆更新都在 Hook 层，不改 loop
- 这是开闭原则在 Agent 架构中的应用——"你要加 SQL 审计日志？加一个 PostToolUse hook 就行"
- 你学习 s08 时已经实现了完整的 3 事件 + 3 态 exit code，不需要重新学

---

## 汇总：六个 bullet 的完整能力覆盖（更新版）

```
                    ┌──────────────────────┐
                    │  ① LLM 调用前         │
                    │  ───────────────────  │
                    │  Bullet 4: Schema 压缩 │
                    │  Bullet 5: 规划 phase  │ ← 模型输出 Plan JSON
                    │  Bullet 6: Memory 注入  │ ← SessionStart 加载
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  LLM Inference       │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  ② 工具执行前         │
                    │  ───────────────────  │
                    │  Bullet 2: 权限管道    │
                    │  Bullet 5: 依赖检查    │ ← Step blockedBy 未解除？
                    │  Trace: span 开始      │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Tool Execution      │
                    │  (execute_sql 等)     │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  ③ 结果返回后         │
                    │  ───────────────────  │
                    │  Bullet 1: 错误分类    │
                    │  Bullet 5: 步骤状态更新 │ ← 依赖解除 → 解锁下一步
                    │  Bullet 6: Memory 更新  │ ← 值得记的写入文件
                    │  Bullet 4: 压缩检查    │ ← 轮次 > N 触发 compact
                    │  Trace: span 结束      │
                    └──────────────────────┘
```

### 能力覆盖一览

| # | Bullet | 对应能力地图 Session | 面试追问方向 |
|---|--------|-------------------|------------|
| 1 | 结构化错误恢复 | **s11** Error Recovery + **s13** Result Normalization | 为什么 5 类？谁定义 error type？ |
| 2 | 权限管道 | **s07** Permission System | 四级顺序有意义吗？怎么防绕过？ |
| 3 | 可观测性 | **s13** ErrorSummary + §7 Observability | 数据怎么反哺优化？为什么不用 OpenTelemetry？ |
| 4 | Schema 压缩 | **s06** Context Compression | 跟 RAG 比选哪个？丢信息怎么办？ |
| 5 | 多步查询规划 | **s03** Planning + **s12** Task System | plan 是模型出还是 harness 出？ |
| 6 | 跨会话 Memory | **s09** Memory System | 什么该记什么不该记？如何不膨胀？ |
| ★ | Hook 串联层（扩展点） | **s08** Hook System | 加新功能要改 loop 吗？ |
| ★ | System Prompt 工程 | **s10** System Prompt | 静态动态怎么分离？ |



**六个 bullet 覆盖能力地图 70% 的已实现 session**：s03, s06, s07, s08, s09, s10, s11, s12, s13 + Observability (§7)。

### 面试官看完的印象（更新版）

- 这个人**不只是调 API**——手写了 agent loop、错误分类、权限管道、上下文压缩
- 这个人**有设计决策能力**——TIMEOUT 不重试而是拆分、权限按成本排序、Planning 是模型出不是 harness 硬编码
- 这个人**有数据驱动思维**——观测数据 → 发现 Schema 歧义 → 优化 → 错误率下降
- 这个人**知道架构边界**——Hook 是扩展框架不改 loop、RAG 和压缩适用不同场景、什么该记什么不该记
- 这个人**有一个完整叙事**——从 Spider fine-tune（模型侧）→ 发现模型能力有限 → 转而从 harness 层系统性解决可靠性问题

---

## 你自己的 Spider + fine-tune 经验怎么嵌入

上面六个 bullet 是"Agent 工程主线"。你的 Spider + Code Llama + RAG 经验放在简历的其他位置：

**工作经历 / 项目经历中的另一个条目**（简写，作为"模型侧能力"证明）：

> Spider Text2SQL Fine-tuning | 基于 Spider 数据集 fine-tune Code Llama 13B，结合 RAG 做 Schema Grounding

面试时被问到，你就说：
> "Spider 让我理解了模型侧的 Text2SQL 能力边界——模型在复杂嵌套 SQL 上还是容易出错。所以后来的 Agent 项目我把可靠性放在第一位——不用模型硬解，而是让 harness 处理错误恢复。"

两个项目不是割裂的，是一个递进叙事：先做模型微调 → 发现模型能力有限 → 转而从 harness 层解决可靠性问题。

```
                    ┌──────────────────────┐
                    │  ① LLM 调用前         │
                    │  ───────────────────  │
                    │  Bullet 4: Schema 压缩 │ ← 接缝①插入
                    │  (summary→DDL→compact) │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  LLM Inference       │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  ② 工具执行前         │
                    │  ───────────────────  │
                    │  Bullet 2: 权限管道    │ ← 接缝②插入
                    │  (黑名单→模式→白名单)   │
                    │  Bullet 3: span 开始   │ ← trace 记录
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Tool Execution      │
                    │  (execute_sql 等)     │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  ③ 结果返回后         │
                    │  ───────────────────  │
                    │  Bullet 1: 错误分类    │ ← 接缝③插入
                    │  (5 类 × 5 条路径)    │
                    │  Bullet 3: span 结束   │ ← trace 记录
                    │  Bullet 4: 轮次计数    │ ← 触发 compact?
                    └──────────────────────┘
```

**四个 bullet 覆盖了能力地图的核心机制**：Error Recovery (s11) / Result Normalization (s13) / Permission (s07) / Context Compression (s06)。再加上 Trace (能力地图 §7 已标注的部分覆盖)。

面试官看这四个 bullet 建立的印象：
- 这个人**不只是调 API**——他处理了错误分类、权限管道、上下文压缩
- 这个人**有设计决策能力**——比如 TIMEOUT 不重试而是拆分、权限管道按成本排序
- 这个人**有数据驱动思维**——观测数据 → 发现 Schema 歧义 → 优化 → 错误率下降
- 这个人**知道自己系统的边界**——"RAG 和压缩我都用过，适用场景不同"

---

## 你自己的 Spider + fine-tune 经验怎么嵌入

上面四个 bullet 是"Agent 工程主线"。你的 Spider + Code Llama + RAG 经验放在简历的其他位置：

**工作经历 / 项目经历中的另一个条目**（简写，作为"模型侧能力"证明）：

> Spider Text2SQL Fine-tuning | 基于 Spider 数据集 fine-tune Code Llama 13B，结合 RAG 做 Schema Grounding

面试时被问到，你就说：
> "Spider 让我理解了模型侧的 Text2SQL 能力边界——模型在复杂嵌套 SQL 上还是容易出错。所以后来的 Agent 项目我把可靠性放在第一位——不用模型硬解，而是让 harness 处理错误恢复。"

两个项目不是割裂的，是一个递进叙事：先做模型微调 → 发现模型能力有限 → 转而从 harness 层解决可靠性问题。
