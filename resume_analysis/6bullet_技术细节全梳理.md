# Text2SQL Agent — 6 Bullet 技术细节全梳理

> 从对话中提取的所有技术细节、澄清点、易混淆概念。每个 bullet 覆盖：做了什么、关键概念、面试可能被追问的点。

---

## Bullet 1：Agent Loop & Structured Error Recovery

### 做了什么

在 Agent Loop 的接缝③（PostToolUse）对每次 SQL 执行结果做结构化包裹。不是返回字符串，是返回 ToolResult JSON。

### 5 类错误

| 错误类型 | 触发条件 | 模型能修吗 | 恢复策略 |
|---------|---------|:---:|------|
| SYNTAX_ERROR | SQL 语法错误 | 能 | 注入 DB 报错详情，模型自修正 |
| TIMEOUT | 查询超时 | 需要拆分 | 不重试，建议模型拆分查询 |
| TABLE_NOT_FOUND | 表名不存在 | 需要工具 | 注入真实表名列表，模型修正 |
| PERMISSION_DENIED | 查了不该查的表 | 不能 | harness 直接终止，不消耗 token |
| EMPTY_RESULT | SQL 正确但 0 行 | — | 通知模型空集，让模型决定下一步 |

### 分类标准："这个错误模型能修吗"

- 能修（语法/字段名）→ 把 DB 错误详情给模型
- 需要工具（表名不存在）→ harness 辅助，加载真实 Schema
- 修不了（权限）→ harness 拦截，不让模型浪费 token
- 重试没用（超时）→ 告诉模型拆分，不盲重试

### 关键概念

- **dispatch_tool**：接缝②，在 tool 真正执行前。根据 tool name 判断：只读 tool（get_table_schema）不进管道，execute_sql 进管道
- **只读 tool 不进管道**：`get_table_schema` 和 `get_table_sample` 不接触数据，不检查权限
- **结构化错误 vs try-catch**：try-catch 压平所有错误成字符串，模型要 NLP 解析。结构化让模型直接读 `error.type` 做决策

### 面试可能追问

- "5 类为什么不是 3 类或 10 类？" → 判断标准：是否驱动不同的模型行为
- "为什么不是 LangChain 的错误处理？" → 不讲 LangChain 坏话，讲自己设计的逻辑
- "Error type 谁定义的？" → harness 定义，因为系统约束（超时阈值、表白名单）不是模型能知道的

---

## Bullet 2：Permission Pipeline

### 做了什么

在接缝②（PreToolUse）对每次 `execute_sql` 调用做四级门控。只读 tool 不进管道。

### 四级管道

| 级别 | 检查内容 | 成本 | 触发条件 |
|------|---------|------|---------|
| 1. 正则黑名单 | DROP/INSERT/DELETE/TRUNCATE/ALTER/CREATE | O(1) | SQL 关键字匹配 |
| 2. Mode Check | read-only 只允许 SELECT，ask 模式升级到 L4 | O(1) | 用户设定模式 |
| 3. Table 白名单 | 解析 SQL 表名，不在列表的直接拒绝 | O(n) | 表名检查 |
| 4. 用户确认 | ask_user("模型想查 X 表，允许吗？") | O(∞) | 新表/ask 模式写操作 |

### 关键概念

- **顺序有意义**：按成本从低到高排，便宜的拦截先做
- **熔断**：连续 3 次拒绝 → 自动切 read-only 模式
- **只对 execute_sql 检查**：get_table_schema 只返回 DDL 文本，不需要权限
- **SQL 注入防护**：正则匹配 SQL 关键字位置 + 表白名单 + 参数化封装。承认这不是 WAF 级别

### 面试可能追问

- "顺序能换吗？" → 不能，便宜的放前面
- "怎么防 SQL 注入绕过？" → 三层：正则+白名单+参数化
- "跟 LangChain 的权限有什么区别？" → LangChain 没内置权限管道，tool 执行是透传的

---

## Bullet 3：Observability & 数据驱动优化

### 做了什么

建立 Trace（单次全链路）和 Metrics（聚合统计），发现 40% 失败源于 Schema 字段歧义，优化错误率降 25%。

### Trace 层

每次请求一个 trace_id，记录：
- LLM 调用：model、token_in/out、duration_ms、tool_calls
- SQL 执行：sql_preview、error_type、duration_ms、row_count
- Tool 调用：tool_name、duration_ms、success/fail

### Metrics 层

- per-error-type 计数
- per-table、per-column 分组
- P50/P99 SQL 延迟
- LLM 调用次数分布、token 消耗
- Context window 占用率（tiktoken / model_max）

### "发现 40% Schema 歧义"的排查过程

1. Metrics 按 error_type 聚合 → SYNTAX_ERROR 占比最高
2. 再按表名 group → orders 表最热
3. 回溯那几条 trace → 模型写 `orders.product`，实际字段叫 `orders.product_title`
4. 同名字段歧义：users.name vs orders.customer_name 同义不同名
5. 修复：Schema 压缩层加字段别名映射
6. 错误率下降 25%

### 关键概念

- **Trace vs Metrics**：Trace 回答"这次请求发生了什么"，Metrics 回答"最近 1000 次什么趋势"
- **不是你手动翻日志**：Metrics 聚合帮你缩小排查范围，然后回溯 Trace 确认根因
- **Context Window 占用率**：每次 LLM 调用前 tiktoken 估算 → 记到 Metrics → 用来调 compact 阈值

### 面试可能追问

- "为什么不用 OpenTelemetry？" → 手写版本 200 行，核心概念和 OTel 一致，换 SDK 架构不变
- "40% 怎么算出来的？" → SYNTAX_ERROR 总共 40 次/100 次，其中 16 次来自 orders 表
- "Metrics 具体怎么实现的？" → 内存 dict，定时输出。不是 Prometheus，量小不需要

---

## Bullet 4：Context Compression

### 做了什么

三层上下文管理，50+ 表 prompt 控制 4K token，60% 节省。

### 三层

| 层 | 内容 | Token 量 | 什么时候加载 |
|----|------|---------|------------|
| Layer 1: Table Summary | 表名 + 一句话描述 + 列数 | ~1500 tokens（50 表） | 每次请求都在 prompt |
| Layer 2: On-demand DDL | 完整 DDL（列名+类型+约束） | ~300 tokens（3 表） | 模型调 get_table_schema tool 时 |
| Layer 3: History Compaction | LLM 摘要早期对话 + 保留最近 3 轮 | ~200 tokens 摘要 | 接缝① tiktoken 超阈值触发 |

### 关键概念

- **触发时机**：每次 LLM 调用前（接缝①）tiktoken 估算 token 数，超阈值（6K）触发 compact
- **compact 过程**：LLM 摘要早期对话 → 作为 user message 注入 → 不破坏 system prompt 缓存
- **丢信息问题**：不追求无损。保留最近 3 轮完整 SQL（模型修正依赖），早期只留"用户在查什么"语义
- **与 RAG 对比**：RAG 把 DDL 全塞进去 → prompt 膨胀。三层方案：先给摘要，模型自己决定需要哪些表
- **60% 节省**：RAG 方案 prompt~10K vs 三层方案 ~4K，4K/10K = 40%，节省 60%

### 面试可能追问

- "什么时候触发压缩？" → 每次 LLM 调用前 tiktoken 估算
- "丢信息怎么办？" → 故意的权衡，最近 3 轮保留完整
- "跟 RAG 方案比 60% 怎么算？" → 两个方案的 prompt 总量对比

---

## Bullet 5：Multi-step Planning & Cross-session Memory

### Multi-step Planning

**做了什么**：复杂 NL 问题自动分解为 3-5 步 SQL Pipeline，有依赖关系。

**流程**：
1. System prompt 指令：简单查询直接调 execute_sql，复杂查询先输出 plan JSON
2. 模型输出：`{ "steps": [{"id": 1, "desc": "...", "tool": "execute_sql", "sql": "...", "depends_on": []}, ...] }`
3. Harness 解析 depends_on 构建依赖图
4. 独立步骤 ThreadPoolExecutor 并行执行
5. 步骤失败 → 只重试该步，已成功的不重跑

**关键概念**：
- **Plan 是模型出的，不是 harness 硬编码** → 问题类型无限多，harness 只管执行和失败处理
- **依赖解除**：Step 1 完成 → 所有依赖 Step 1 的步骤去掉这个依赖 → 依赖为空的解锁
- **步骤混合**：Plan 不全是 SQL 执行，有 get_table_schema 提取表信息 + execute_sql + 纯汇总（tool: none）
- **自适应分流**：模型判断简单就不触发 planning

### Cross-session Memory

**做了什么**：4 种记忆类型，跨会话持久化用户偏好和系统约束。

**四种类型**：
| 类型 | 存什么 | 例子 |
|------|--------|------|
| user | 查询偏好 | 常用表、月度聚合偏好 |
| feedback | 用户修正记录 | product→product_title |
| project | 系统约束 | 敏感表名单、软删除约定 |
| reference | 外部资源指针 | 数据字典位置 |

**关键概念**：
- **加载**：SessionStart 注入 MEMORY.md 索引摘要
- **写入**：PostToolUse 检测值得记的模式（用户说"错了"/3 次以上查同一张表）
- **防膨胀**：合并同主题记忆，3 月未访问自动归档

### 面试可能追问

- "Plan 是模型出的还是你硬编码的？" → 模型出，harness 执行
- "什么该记什么不该记？" → 该记用户偏好/反馈/系统约束，不该记代码结构和临时状态
- "记忆怎么不膨胀？" → 合并去重 + 时间归档

---

## Bullet 6：双模型分工 & Fine-tuning

### 做了什么

通用 LLM 做 Agent 编排 + CodeLlama-13B 专职 SQL 生成。Spider 微调，多表准确率 33%→77%。RAG Schema Grounding。

### 双模型分工

| | 通用 LLM（Agent 核心） | CodeLlama-13B（SQL 生成器） |
|---|---|---|
| 推理时做什么 | 规划、调 tool、看错误、决定重试、把错误喂给 CodeLlama | 根据 NL + DDL + 错误反馈生成/修正 SQL |
| 训练 | 不训练 | 修正成功的数据回流 re-fine-tune |
| 输入 | messages 数组（含 tool results、错误信息） | Prompt（NL + DDL + 可选错误上下文） |

### Fine-tuning 细节

- **数据集**：Spider（200+ 数据库、10,000+ NL-SQL 对）
- **方法**：LoRA rank=16, alpha=32
- **评估**：Execution Accuracy（EX）——执行生成的 SQL，返回行集和标准答案一致就算对，字符串不完全一致也没关系
- **EX vs EM**：Exact Match 比字符串，太严格；EX 比结果集，更实用
- **分级**：Easy（单表）/ Medium（多表 JOIN）/ Hard（嵌套+聚合+GROUP BY）

### RAG Schema Grounding

- 200+ 表 DDL 用 sentence-transformer 做 embedding → FAISS 索引
- 推理时：NL embedding → 召回 top-k 相关表 DDL → 注入 prompt

### Data Flywheel（修正数据回流）

1. CodeLlama 生成 SQL → 执行 → 失败
2. Agent 把错误信息 + 修正提示喂回 CodeLlama
3. CodeLlama 修正成功 → NL-SQL 对自动入库
4. 积累 1000+ 条 → 混入训练集 re-fine-tune
5. 模型越准 → Agent 纠正越少 → 飞轮正循环

### 面试可能追问

- "EX 和 EM 什么区别？" → EM 比字符串，EX 比执行结果
- "LoRA 参数怎么选的？" → 手动试 rank=4/8/16/32，16 是平衡点
- "为什么用两个模型？" → CodeLlama 不需要 Agent 能力，通用 LLM 不需要 SQL 专精。分工明确
- "修正数据怎么回流？" → PostToolUse 检测"同一个 NL 从失败到成功"→ 入库 → 积累 re-fine-tune

---

## 附：三大接缝速查

```
接缝①（LLM 调用前）
  → System Prompt 组装
  → Schema Summary 注入（Context Compression Layer 1）
  → Memory 注入（SessionStart）
  → tiktoken token 估算 → 超阈值触发 compact（Layer 3）

接缝②（工具执行前）
  → dispatch_tool 判断：只读 tool 跳过管道，execute_sql 进管道
  → Permission Pipeline（四级门控）

接缝③（结果返回后）
  → 结构化错误包裹（Error Recovery）
  → Trace span 结束 + Metrics 记录
  → Memory 更新（PostToolUse 检测值得记的模式）
  → 检测"NL 从失败到成功"→ data flywheel 入库
```
