# AI Agent 的"协议"到底靠什么实现？

> 拆解 Claude Code 同款架构：协议不是强制执行，而是一场精心设计的"约定"

---

## 先问一个问题

如果你让一个 AI Agent 在干活之前必须先提交计划等审批，它偷偷绕过审批直接干活怎么办？

**答案：没有办法。而且这是故意的。**

---

## Agent = Model + Harness

理解这个之前，得先搞懂一个核心概念。

**Agent = Model + Harness**

- Model = 神经网络（Claude/GPT），负责思考决策
- Harness = 外围代码，给 Model 提供工具、消息通道、上下文

本项目的教学拆分：把 Agent 拆成 Model + Harness 两部分来讲。"The model is the agent, the code is the harness"—— Agent 的能力来自 Model，你的工作是写好 Harness。

所以 Harness 能做的不是"管住" Agent，而是**提供机制让 Agent 自己管自己**。

---

## 两个协议，同一个模式

s10 实现了两个协议，底层用的是同一种 request_id 关联模式。

**Shutdown 协议：关闭队友**

Lead 调用 shutdown_request → 消息投递到 teammate 的 inbox → teammate 读到后决定 approve 还是 reject → 调用 shutdown_response 回复 → Lead 查询 tracker 状态确认结果

**Plan Approval 协议：计划审批**

Teammate 调用 plan_approval 提交计划 → 消息投递到 lead 的 inbox → Lead 读到后决定 approve 还是 reject → 调用 plan_approval 回复 → Teammate 收到审批结果

两个协议共享同一个 FSM：**pending → approved 或 rejected**。底层都是 request_id 关联请求和响应。

---

## 同名工具，不同角色，不同语义

这是整个设计最精彩的部分。

| 工具 | Lead 调用时 | Teammate 调用时 |
| --- | --- | --- |
| shutdown_request | 发起关闭请求 | (没有这个工具) |
| shutdown_response | 查询关闭状态（只读） | 做出决策（批准/拒绝） |
| plan_approval | 审批计划（批准/拒绝） | 提交计划（等待审批） |

同一个 `plan_approval`：

- Teammate 调用时 = "我提交一个计划"
- Lead 调用时 = "我批准/拒绝这个计划"

**一个工具名，两个角色，语义完全相反。** 这不是 bug，是设计——协议双方用同一个动词完成对称的交互。

---

## 最颠覆认知的一点

**协议完全依赖模型的 tool_use 调用。Harness 层没有做任何拦截。**

teammate 收到 shutdown_request 后，模型可以：

- 调用 shutdown_response(approve=true) —— 同意关闭
- 调用 shutdown_response(approve=false) —— 拒绝关闭
- 直接调用 bash() 继续干活 —— 完全无视
- 输出一段文字后 stop —— 也不关，状态变 idle

System prompt 里写的是 "Submit plans via plan_approval before major work"，本质上是一句**建议**，不是约束。

**机制 vs 策略，一个关键判断：**

- 机制（Harness 提供）：request_id 追踪、inbox 投递、FSM 状态
- 策略（Model 决定）：什么时候提交计划、什么时候同意关闭
- 当 bug 看："Teammate 可以跳过审批直接跑 bash"
- 当哲学看："Harness 提供机制，Model 决定策略。这就是设计意图。"

---

## Harness 做了什么 vs 没做什么

| 做了什么（机制） | 没做什么（策略） |
| --- | --- |
| request_id 关联追踪 | 未审批计划拦截 |
| FSM 状态记录 | shutdown 超时强制终止 |
| JSONL inbox 消息通道 | 协议违规检测或惩罚 |
| 工具定义分发给对应角色 | 任何形式的强制执行 |

---

## JSONL 消息总线

Teammate 之间的通信就是一个 JSONL 文件，每条消息一行：

{"type":"shutdown_request", "from":"lead", "request_id":"a1b2c3d4"}
{"type":"shutdown_response", "from":"coder", "request_id":"a1b2c3d4", "approve":true}
{"type":"plan_approval_response", "from":"coder", "request_id":"e5f6g7h8", "plan":"refactor utils.py"}

读后即清空。没有消息队列，没有事件总线，没有 ACK 机制。

---

## 如果部署到生产环境呢？

用 5 个 lens 系统化审视这个设计：

**Lens 1: 线程 & 并发**

问题：teammate 同步阻塞等 API 返回，期间新消息看不到。教学意图：轮询是最简单的模型，push 需要事件循环。生产化：消息到达后 abort 当前 API 调用，注入新消息后重试。

**Lens 2: 消息总线**

问题：JSONL 读后即清空，读到一半崩溃 = 消息永久丢失。教学意图："read and drain" 足够演示协议流程。生产化：at-least-once 语义，处理成功后再 commit offset。

**Lens 3: 协议执行**

问题：plan_approval 是工具调用，不是代码门禁。教学意图：展示"模型自觉遵守约定"的哲学。生产化：工具执行前加 has_approved_plan() 检查。注意：这改变了从"模型决定"到"Harness 执行"的哲学。

**Lens 4: 错误处理**

问题：API 调用异常直接 break 退出，无重试无告警。教学意图：保持流程简洁，不被错误处理分支淹没。生产化：指数退避重试 + dead-letter + teammate 状态加 "error"。

**Lens 5: 状态持久化**

问题：shutdown_requests 和 plan_requests 是内存 dict，重启全丢。教学意图：单次运行足够，机制本身（request_id + FSM）是正确的。生产化：SQLite 或原子 JSON 写入。

---

## 生产化改造优先级

不是所有东西都要一次改完：

**P0 — 会出事的**

消息总线 at-least-once + 文件锁，否则崩溃 = 消息丢失。线程生命周期非 daemon + 超时强杀，否则僵尸 teammate 无人清理。

**P1 — 脆弱的**

协议执行：工具调用前加门禁，plan_approval 从建议变成约束。错误处理：重试 + 告警，API 异常不再静默 kill。

**P2 — 别扭的**

工具名消歧：shutdown_response 拆成 shutdown_respond 和 shutdown_status。状态持久化：tracker dict 落磁盘，重启不丢。

**P3 — 看不见的**

结构化日志 + 追踪，知道谁调了谁、花了多久、token 消耗。

---

## 这是一种哲学

> 模型不是被管控的对象，而是被信任的协作者。

Harness 的职责：

1. 给模型装配合适的工具
2. 提供清晰的通信渠道
3. 追踪请求-响应的关联关系
4. 然后**退后一步**，让模型自己做决定

**"The model is the agent, the code is the harness."**

你写的代码不是在管理 AI，而是在给 AI 搭舞台。舞台好了，表演自然精彩。

---

`#AI架构` `#Agent设计` `#ClaudeCode` `#技术拆解` `#AI编程` `#协议设计` `#Harness工程`
