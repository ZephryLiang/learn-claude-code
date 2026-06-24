🤖 Agent Teams 架构：Lead 和 Teammate 的 Loop 到底该写几套？

最近在啃 Anthropic 的 learn-claude-code，一个从零教你搭建 AI Agent 脚手架的教学仓库。12 个 Session 看下来收获很大。

但看到 s09 Agent Teams 的时候，发现一个没说清楚的问题 👇


🔍 问题出在哪

s09 的代码里，Lead 和 Teammate 跑的是*两套不同的 Loop*：

*Lead* → agent_loop()，独立函数
*Teammate* → _teammate_loop()，TeammateManager 的方法

教学拆开讲没问题，每节课只加一个新机制，清晰。

但真实工程里如果 agent 越加越多，Lead 一套代码，Alice 一套，Bob 又一套——*这不是 Agent Teams，这是代码地狱。*


💡 核心答案：Loop 只写一套，改配置区分角色

Lead 和 Teammate 的区别不在代码路径，在 *4 个配置维度*：

*tools* — 你能用什么工具？Lead 有 spawn_teammate，Teammate 没有。工具列表本身就是第一道权限边界。

*permission* — 同一个 bash 工具，Lead 能 sudo，Teammate 不能。同一个工具不同权限，这才是权限门的意义。

*system_prompt* — 你的角色、目标、行为边界。"你是 Team Lead" vs "你是 Alice，coder 角色"。

*inbox_name* — 团队通信里的身份标识。"lead" vs "alice" vs "bob"。

这四个维度恰好对应你学过的 harness 机制：

tools ← s02 Tool Dispatch + s04 Subagent
permission ← s02 Permission Gate + s10 Protocols
system_prompt ← s05 Skill Loading + s03 TodoWrite
inbox_name ← s09 Team Messaging


🧱 统一 Loop 长什么样

Lead 和 Teammate 共享同一个 Agent 类和同一个 loop：

*class Agent* 有三个属性：name（"lead"/"alice"）、cfg（4 个配置维度）、harness（共享基础设施）。

*loop(messages)* 只有一个 while 循环，每次迭代依次做：

① s06 上下文压缩 → harness.compressor.compact(messages)
② s08 后台任务通知注入 → drain_background
③ s09 收件箱 draining → drain_inbox(name)，lead 读 "lead"，alice 读 "alice"
④ s10 检查 shutdown 信号
⑤ LLM 调用 → 传 cfg.system_prompt + cfg.tools
⑥ 如果 stop_reason != "tool_use" → return
⑦ 工具执行 → *每个 tool 调 cfg.permission.allow() 过权限门*

*Lead 跑这个 loop。Alice 也跑这个 loop。换一份 AgentConfig，就换了一个角色。*


🏗️ 三个成熟框架都在这样做

① *OpenAI Agents SDK — 最纯粹*

Agent 是一个 dataclass（纯配置），Runner.run() 是唯一的 agent loop。handoff 发生时不是调用另一个函数，而是换一个 Agent 对象，继续同一个 while 循环。

Lead：triage = Agent(handoffs=[billing, refund])，Teammate：billing = Agent(handoffs=[])。Runner.run(starting_agent=triage) 一套 loop 跑所有。

② *Claude Agent SDK — 最完整*

Subagent *不是代码，是 YAML 配置文件*。底层 agent loop 完全相同，差异来自 YAML 解析后的 AgentDefinition。

allowed-tools: [Read, Grep, Glob] 既是工具列表也是权限边界。permissionMode: acceptEdits 控制审批行为。

⚠️ 关键区分：Claude SDK 的 subagent（YAML）是 s04 用完即焚模式，Agent Teams 才是 s09 的 long-lived + inbox 通信。今天多数框架的 "multi-agent" 其实是前者。

③ *CrewAI — 最角色化*

所有 agent 是同一个 Agent 类，共享同一个 Crew 运行时。role + goal + backstory + tools + allow_* 五个字段决定角色。

*allow_delegation=True* → 你是 Lead，*allow_delegation=False* → 你是 Teammate。一个布尔值就区分了角色。


🔬 拓展思考

*1. CrewAI 用 Mem0 做上下文压缩，特别在哪？*

learn-claude-code 的 s06 是无状态压缩：裁剪旧输出 → 太长就 LLM 摘要。每次独立，不记历史。

CrewAI 2025 引入的 Mem0 是有状态压缩：把 agent 记忆向量化存储，cross-session 可以累积，agent 间可以共享记忆层。更适合 long-lived teammate。

推荐学习路径：搞懂 s06 策略 → 看 Mem0 向量方案 → 对比两者的适用边界。

*2. Subagent 还是 Teammate？*

Subagent：用完即焚、成本低、上下文隔离。适合独立并行任务。Teammate：long-lived、有 inbox、有 idle 循环。适合需要多轮互相 challenge 的场景。

大多数场景 Subagent 就够了。Teammate 成本约 15× token（Claude Agent Teams 实测），还有 idle 轮询、状态恢复、竞态处理一堆坑。

*3. 为什么 long-lived teammate 至今不是主流？*

三个硬骨头：Token 成本（每个 teammate 独立 context）、状态同步（idle → 收消息 → 恢复，上下文不能丢）、会话恢复（线程崩溃后怎么继续）。

Claude Agent Teams（实验阶段）、LangGraph 持久化 StateGraph、OpenAI 2026 年 4 月的 Sandbox 快照恢复，都在啃这些骨头。


📌 三句话总结

*Loop 只写一次。* 教学代码拆开讲机制，生产代码一个 Agent.loop() + 多份 AgentConfig。

*Agent 是配置，不是代码。* 判断框架成熟度，看它的 Agent 定义有多少行代码 vs 多少行配置。

*12 Session 是一把"标尺"。* 之后看任何 agent 框架，能一眼识别它覆盖了哪些 harness 机制，缺失了哪些，以及它的 multi-agent 到底是 subagent 还是 teammate。

#AIAgent #Agent架构 #ClaudeCode #MultiAgent #程序员的日常 #技术分享
