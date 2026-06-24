# 一次搞懂 Multi-Agent 的 4 种编排模式：从教学代码到大厂框架

> 从 learn-claude-code 的 12 个教学 session 出发，对照 CrewAI、AutoGen、LangGraph 三大框架，彻底说清 Multi-Agent 的 4 种编排模式及其选型逻辑。

---

## 0. 四种模式速览

```text
┌──────────────────────────────────────────────────────────────────────┐
│                   Multi-Agent 4 种编排模式                            │
│                                                                      │
│  ① Orchestrator-Workers    ② Routing / Hand-off                     │
│     ┌──────┐                   ┌──────────┐                         │
│     │ Orch │                   │  Router  │                         │
│     └──┬┬┬─┘                   └─┬──┬──┬──┘                         │
│        │││      Workers          │  │  │    Specialists              │
│     ┌──┘│└──┐                ┌──┘  │  └──┐                          │
│     ▼   ▼   ▼                ▼     ▼     ▼                          │
│                                                                      │
│  ③ Pipeline / Sequential     ④ Group Chat / Swarm                   │
│     ┌───┐  ┌───┐  ┌───┐       ┌─────★─────┐                         │
│     │ A │→│ B │→│ C │        │  Public   │                         │
│     └───┘  └───┘  └───┘       │  Channel  │                         │
│                                │┌──┐┌──┐┌──┐│                        │
│                                ││A ││B ││C ││                        │
│                                │└──┘└──┘└──┘│                        │
│                                └────────────┘                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 1. Orchestrator-Workers（中心化编排者-工作者）

**一句话：一个主管拆解任务、分配、汇总。**

### 1.1 教学实现

**resume-editor-agent** 的 Coordinator + Subagent Registry 就是教科书级的实现：

```python
# Coordinator 读 registry，动态规划，派发任务
plan = coordinator_plan(resume, jd, goal, registry)  # ① 拆解
for step in plan.steps:                               # ② 派发
    subagent = registry[step.id]                      #    选对应的 expert
    result = await subagent.run(inputs=cache)         # ③ 执行
    cache[step.id] = result                           # ④ 汇总
emit("all_done", cache)                               # ⑤ 输出
```

5 个 sub-agent 各有专属 skill 和 tool（gap_analysis 加载 `SKILL.md`，company_analysis 用 `web_search`，rewrite 用 `compile_latex`），Coordinator 看完用户输入后**自己决定**用哪些、按什么顺序。

### 1.2 大厂框架对应

| 框架 | 实现方式 |
|---|---|
| **CrewAI** | `Process.hierarchical` — Manager Agent 运行时读 agents 的 role + tasks，动态决定分配 |
| **AutoGen v0.2** | `GroupChatManager` — 每轮对话后隐式选择下一个发言 agent |
| **LangGraph** | Supervisor pattern — 一个 supervisor node 读 state，`add_conditional_edges` 路由到 worker |

```python
# LangGraph Supervisor 示例
def supervisor(state):
    if state["next"] == "researcher":
        return "research_node"
    elif state["next"] == "coder":
        return "coding_node"
    return END

graph.add_conditional_edges("supervisor", supervisor, {...})
```

### 1.3 特点

- **可控性最高** — 每一步谁做什么、输入输出是什么，全链路可审计
- **瓶颈明显** — Coordinator 本身消耗大量 token做规划，且是单点
- **适合**：简历分析、数据报告生成、复杂多步骤审核流程

---

## 2. Routing / Hand-off（路由/转交）

**一句话：一个路由 Agent 分类意图，然后完整交班给专业 Agent。**

### 2.1 教学实现

learn-claude-code 的 s02（Tool Dispatch）是路由的雏形：

```python
# s02: 按 tool name 路由到不同 handler
TOOL_HANDLERS = {
    "bash":      lambda **kw: _run_bash(kw["command"]),
    "read_file": lambda **kw: _run_read(kw["path"]),
    ...
}
# 模型决定用哪个 tool → 路由到对应 handler
```

更完整的体现在 s10 的 **request-response 协议**：

```python
# Agent A 向 Agent B 发 request → Agent B 判断是否接受 → 处理 → 返回
BUS.send("alice", "bob", "请审查这段代码", "plan_approval_response",
         {"request_id": req_id, "plan": plan_text})
```

本质就是路由：发起方不需要知道 B 的内部逻辑，只需要知道 "B 能处理这类请求"。

### 2.2 大厂框架对应

| 框架 | 实现方式 |
|---|---|
| **LangGraph** | `add_conditional_edges("classifier", route_fn, {"billing": "billing_agent", "tech": "tech_agent"})` |
| **AutoGen v0.4** | Topic 订阅 — Agent 声明 "我处理这类消息"，消息到达时框架自动路由 |
| **OpenAI Swarm** | 原生 handoff 原语 — `agent.transfer_to_agent(target_agent)` |

```python
# OpenAI Swarm 风格
def billing_agent(request):
    if request.type == "tech_support":
        return tech_agent  # handoff
    return process_billing(request)
```

### 2.3 特点

- **高并发低延迟** — 路由完成即交班，不需中心节点持续参与
- **边界模糊时危险** — Agent A → B → A → B → ... 循环路由死锁
- **适合**：企业多功能客服（售前→销售→技术支持，各司其职）

### 2.4 与 Orchestrator 的关键区别

| | Orchestrator-Workers | Routing/Hand-off |
|---|---|---|
| 中心节点 | 全程参与（规划→分配→汇总） | 只做一次分类，然后退出 |
| 下游协作 | 结果回给 Coordinator 汇总 | 下游 Agent 直接面向用户 |
| Token 消耗 | Coordinator 是瓶颈 | 路由后零开销 |

---

## 3. Pipeline / Sequential（管道/顺序）

**一句话：A 的输出是 B 的输入，固定流水线。**

### 3.1 教学实现

learn-claude-code s03（TodoWrite / Planning）的核心就是顺序执行：

```python
# s03: 先规划步骤 → 再逐个执行
plan = model_creates_plan(user_request)  # [{id:1, subject:"..."}, ...]
for step in plan:
    execute(step)  # 严格顺序，上一步的输出进入下一步的 context
```

resume-editor-agent 的 plan 执行也是 Sequential：

```text
gap_analysis → assessment → remediation → rewrite
     ↓              ↓              ↓           ↓
  输出进入cache  输出进入cache  输出进入cache  最终输出
```

每一步的产出是下一步的输入，这一步的精确性直接影响下一步的质量。

### 3.2 大厂框架对应

| 框架 | 实现方式 |
|---|---|
| **CrewAI** | `Process.sequential` — task 列表按定义顺序逐一执行 |
| **LangGraph** | `add_edge("A", "B").add_edge("B", "C")` — 线性 graph |
| **AutoGen v0.2** | `SequentialConversationAgent` — 预定义发言顺序 |

```python
# CrewAI Sequential
crew = Crew(agents=[gap, assess, rewrite], tasks=[t1, t2, t3],
            process=Process.sequential)
# 严格按 t1 → t2 → t3 执行
```

### 3.3 特点

- **逻辑完全确定** — 每一步的输入输出可预测、可验证
- **错误链式放大** — 前序步骤出错，后续全部偏掉
- **适合**：代码生成流水线（需求→设计→编码→测试）、CI/CD

### 3.4 与 Orchestrator 的关键区别

| | Orchestrator-Workers | Pipeline/Sequential |
|---|---|---|
| 任务顺序 | 动态规划 | 固定预定义 |
| 灵活性 | Coordinator 可跳过/替换步骤 | 严格线性 |
| 适用 | 任务种类多变 | 流程固定，每次都要全跑 |

Pipeline 是 Orchestrator 的退化形式 — 当 "动态规划" 的收益为零时，去掉 Coordinator 直接写死顺序更高效。

---

## 4. Group Chat / Swarm / Mesh（群聊/网络协作）

**一句话：去中心化，所有 Agent 在一个公共频道自主发言、竞争、辩论。**

### 4.1 教学实现

s09/s11 就是群聊模式的教学实现。核心机制是 **JSONL inbox（公共频道）**：

```python
# s11: teammate 在 idle phase 中自主找活干
while idle_timeout not reached:
    # ① 检查 inbox — 有没有人找我？
    inbox = BUS.read_inbox(name)
    if inbox:
        resume WORK

    # ② 扫 task board — 有没有没认领的活？
    unclaimed = scan_unclaimed_tasks()
    if unclaimed:
        claim_task(unclaimed[0]["id"], name)  # 我认领了！
        resume WORK

# timeout → 自主 shutdown
```

关键设计：

- **公共频道**：`.team/inbox/` 下每个 agent 一个 `.jsonl` 文件，所有人可以往任何人的 inbox 写消息
- **自主决策**：每个 agent 自己决定要不要处理、什么时候处理
- **无中心调度**：teammate `alice` 和 `bob` 之间直接通信，不走 lead

### 4.2 大厂框架对应

| 框架 | 实现方式 |
|---|---|
| **AutoGen v0.4** | EventBus + Topic 订阅 — agent 声明感兴趣的 topic，消息到达时自主决定是否发言 |
| **LangGraph** | Send API — `[Send("node", {...}) for t in state["topics"]]` 多实例并行 |
| **CrewAI** | 也在探索 swarm 模式（目前不如前两者成熟） |

```python
# AutoGen v0.4 Topic 订阅
@agent.subscribe("code_review")
async def review_handler(agent, message):
    # agent 自己决定要不要参与
    if agent.can_handle(message):
        return await agent.review(message)

# LangGraph Send API
def continue_to_workers(state):
    return [Send("worker", {"task": t}) for t in state["tasks"]]
```

### 4.3 特点

- **涌现性最强** — agent 之间的交互可能产生意想不到的好结果
- **极难控制** — 容易无限循环对话，token 消耗爆炸
- **调试困难** — 谁说了什么、为什么说、谁该说但没说，全链路不可预测
- **适合**：多专家联合会诊、创意头脑风暴、需要对抗性辩论的场景

---

## 5. 四种模式全景对照

```text
                    控制性 ←──────────────────→ 涌现性
                    (可预测)                    (不可预测)

  ① Orchestrator    ② Routing        ③ Pipeline       ④ Group Chat
  ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
  │ 中心规划  │      │ 一次分类  │      │ 固定流水  │      │ 去中心化  │
  │ 动态分配  │      │ 完整交班  │      │ 顺序执行  │      │ 自主协作  │
  │ 统一汇总  │      │ 直接对话  │      │ 严格依赖  │      │ 公共频道  │
  └──────────┘      └──────────┘      └──────────┘      └──────────┘

  教学代码          教学代码            教学代码            教学代码
  resume-editor-    s02 tool dispatch  s03 todo_write     s09/s11 teams
  agent             s10 protocols      s_full sequential  autonomous agents

  框架代表          框架代表            框架代表            框架代表
  CrewAI Hier.      LangGraph cond.    CrewAI Seq.        AutoGen v0.4
  LangGraph Super.  OpenAI Swarm       LangGraph linear   LangGraph Send
  AutoGen v0.2      AutoGen handoff                       CrewAI (探索中)
```

---

## 6. 框架选型速查表

| 场景 | 推荐模式 | 推荐框架 | 原因 |
|---|---|---|---|
| 任务种类多变，需动态规划 | ① Orchestrator | CrewAI Hierarchical / LangGraph Supervisor | 中心节点统一决策 |
| 多功能客服，按意图分流 | ② Routing | LangGraph conditional edges / OpenAI Swarm | 一次路由，后续零开销 |
| 代码生成/CI/CD 固定流程 | ③ Pipeline | CrewAI Sequential / LangGraph linear | 逻辑确定，结果可预测 |
| 多专家会诊/创意讨论 | ④ Group Chat | AutoGen v0.4 Topic / LangGraph Send | 涌现性最强，但需控制成本 |
| 混合场景 | ① + ③ 或 ① + ④ | LangGraph（最灵活） | 规划层集中 + 执行层分布 |

---

## 7. 核心总结

```text
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ① Orchestrator」② Routing」③ Pipeline」④ Group Chat              │
│                                                                  │
│  这四种模式本质上是"控制 vs 涌现"光谱上的四个点                     │
│                                                                  │
│  没有银弹。框架只是提供了原语，选型取决于你的任务拓扑：              │
│  • 有向无环依赖 → ① 或 ③                                         │
│  • 树状分类 → ②                                                   │
│  • 网状协作 → ④                                                   │
│                                                                  │
│  教学代码的价值：每增加一种模式，只增加 100 行左右的 harness 代码  │
│  理解原理后，任何框架都能用                                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 附：learn-claude-code 12 Sessions 的模式映射

| Session | 机制 | 对应模式 |

|---|---|---|
| s01 | Agent Loop（基础循环） | 所有模式的基础 |
| s02 | Tool Dispatch（工具分发） | ② Routing 雏形 |
| s03 | TodoWrite（规划系统） | ③ Pipeline 雏形 |
| s04 | Subagent（子代理隔离） | ① Orchestrator 基础 |
| s05 | Skill Loading（技能加载） | ① 的 skill 注入 |
| s06 | Context Compact（上下文压缩） | 全部模式的工程支撑 |
| s07 | Task System（任务持久化） | ③ 的任务持久化 |
| s08 | Background Tasks（异步执行） | ① 的异步 sub-agent |
| s09 | Agent Teams（团队通信） | ④ Group Chat 基础 |
| s10 | Team Protocols（团队协议） | ② + ④（协商路由） |
| s11 | Autonomous Agents（自主代理） | ④ 完整实现 |
| s12 | Worktree Isolation（工作隔离） | 全部模式的隔离支持 |

---

## 参考文献与链接

### 综述论文

| 论文 | 链接 | 要点 |
|---|---|---|
| **LLMs Working in Harmony: A Survey on the Technological Aspects of Building Effective LLM-Based Multi Agent Systems** (2025.04) | [arxiv.org/abs/2504.01963](https://arxiv.org/abs/2504.01963) | 覆盖 AutoGen/CAMEL/CrewAI/MetaGPT/LangGraph 的架构、记忆、规划、框架 |
| **Multi-Agent Collaboration Mechanisms: A Survey of LLMs** (2025.01) | [arxiv.org/abs/2501.06322](https://arxiv.org/abs/2501.06322) | 协作维度分类：actors/types/structures/strategies/protocols |
| **AI Agent Systems: Architectures, Applications, and Evaluation** (2025) | [arxiv.org/abs/2601.01743](https://arxiv.org/abs/2601.01743) | Agent 架构分类学：single vs multi-agent, centralized vs decentralized |
| **From Standalone LLMs to Integrated Intelligence: A Survey of Compound AI Systems** (2025.06) | [arxiv.org/abs/2506.04565](https://arxiv.org/abs/2506.04565) | Compound AI 系统多维分类，含编排中心化架构 |
| **Beyond Pipelines: A Survey of the Paradigm Shift toward Model-Native Agentic AI** (2025.10) | [arxiv.org/abs/2510.16720](https://arxiv.org/abs/2510.16720) | 从 pipeline 编排到模型原生 multi-agent 协作的范式转移 |

### 框架论文与官方文档

#### AutoGen (Microsoft)

| 资源 | 链接 |
| --- | --- |
| AutoGen 论文：Enabling Next-Gen LLM Applications via Multi-Agent Conversation | [arxiv.org/abs/2308.08155](https://arxiv.org/abs/2308.08155) |
| 官方文档 — Core Architecture & Agent Runtime | [microsoft.github.io/autogen](https://microsoft.github.io/autogen) |
| v0.4 Topic/Subscription 设计模式 — Handoffs | [microsoft.github.io/autogen/.../handoffs](https://microsoft.github.io/autogen/0.4.6/user-guide/core-user-guide/design-patterns/handoffs.html) |
| v0.4 Team Orchestration 文档 | [deepwiki.com/microsoft/autogen/4.1-team-orchestration](https://deepwiki.com/microsoft/autogen/4.1-team-orchestration) |
| GitHub 仓库 | [github.com/microsoft/autogen](https://github.com/microsoft/autogen) |

#### CrewAI

| 资源 | 链接 |
| --- | --- |
| 官方文档 — Crews & Processes | [docs.crewai.com](https://docs.crewai.com) |
| GitHub 仓库 | [github.com/crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) |
| 社区论坛（大量实践案例） | [community.crewai.com](https://community.crewai.com) |
| Hierarchical Process 详解 | [docs.crewai.com/concepts/crews](https://docs.crewai.com/concepts/crews) |

#### LangGraph (LangChain)

| 资源 | 链接 |
| --- | --- |
| Supervisor 库 (Python) | [github.com/langchain-ai/langgraph-supervisor-py](https://github.com/langchain-ai/langgraph-supervisor-py) |
| Supervisor 库 (JS) | [npm: @langchain/langgraph-supervisor](https://www.npmjs.com/package/@langchain/langgraph-supervisor) |
| LangGraph 官方文档 — Multi-Agent | [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph) |
| Send API 并行执行 | [langchain-ai.github.io/langgraph/concepts/low_level/#send](https://langchain-ai.github.io/langgraph/concepts/low_level/#send) |

#### OpenAI Swarm / Agents SDK

| 资源 | 链接 |
| --- | --- |
| OpenAI Swarm GitHub（实验性/教育性） | [github.com/openai/swarm](https://github.com/openai/swarm) |
| OpenAI Cookbook — Orchestrating Agents (Routines & Handoffs) | [github.com/openai/openai-cookbook](https://github.com/openai/openai-cookbook) |
| PyPI 包 | [pypi.org/project/openai-swarm](https://pypi.org/project/openai-swarm) |
| OpenAI Agents SDK（生产级继承者） | [platform.openai.com/docs/guides/agents](https://platform.openai.com/docs/guides/agents) |

### 博客与深度分析

| 文章 | 链接 |
| --- | --- |
| Deep Dive into AutoGen Multi-Agent Patterns 2025 | [sparkco.ai/blog/deep-dive-into-autogen-multi-agent-patterns-2025](https://sparkco.ai/blog/deep-dive-into-autogen-multi-agent-patterns-2025) |

| LangGraph Supervisor 多智能体系统教程 | [blog.csdn.net/cfrzs/article/details/151816700](https://blog.csdn.net/cfrzs/article/details/151816700) |
| Day 3: Multi-Agent Systems — The Supervisor Pattern | [dev.to/ravidasari/day-3-multi-agent-systems-the-supervisor-pattern](https://dev.to/ravidasari/day-3-multi-agent-systems-the-supervisor-pattern-20ba) |

### 教学参考

| 资源 | 链接 |
| --- | --- |
| learn-claude-code（本文教学代码来源，shareAI-lab 逆向工程） | [github.com/shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) |
| Anthropic 工程博客 — Effective harnesses for agents | [anthropic.com/engineering](https://www.anthropic.com/engineering) |
| LangChain 论坛 — Parallel execution with supervisor pattern | [forum.langchain.com/t/parallel-execution-with-supervisor-pattern](https://forum.langchain.com/t/parallel-execution-with-supervisor-pattern/1665) |
