🧩 Agent Harness 拆穿：90% 是旧东西换皮

Harness 这个概念很新，最近半年 tech blog 都在讲。

但啃完 learn-claude-code 的 12 个 Session 之后，感觉越来越不对劲——*每个"新机制"我都能在 1970-1990 年找到一个祖宗。*

结论：*只有 3 个是真正新的。*


👇 逐个扒皮


👉 s01 · Agent Loop

Harness 版本：while True → LLM call → model 说停才停

祖宗：Event Loop / Game Loop（1980s）。就是 while True: read; process; write 那套。

*唯一的新东西*：循环什么时候退出，不是代码 break，是*模型自己说"我完事了"*（stop_reason != "tool_use"）。控制流从代码手里移交给了模型。


👉 s02 · Permission Gate

Harness 版本：agent 想调 bash → 查权限表 → 通过 / 拒绝

祖宗：Unix sudoers（1970s）

1970s 的 sudoers：alice 只能跑 git 和 npm，bob 什么都能跑。2025 的 agent permission：alice_cfg.permission = Permission(allow=["git", "npm"])。*一模一样。*

以前是人敲命令，sudo 拦人。现在是模型调工具，permission gate 拦模型。拦的对象变了，拦的逻辑没变。


👉 s04 · Subagent

Harness 版本：spawn 子 agent → 独立 context → 返回摘要 → 销毁

祖宗：Unix fork() + waitpid()（1970s）

fork() 创建子进程，独立内存空间，父进程等结果。Subagent 创建子 agent，独立 messages[]，父 agent 拿摘要。

*Subagent = fork() 换了个隔离对象。* 隔离思想完全一样。


👉 s06 · Context Compression

Harness 版本：microcompact（截断旧输出）+ auto-compact（LLM 写摘要）

祖宗：microcompact = logrotate（Unix 1970s）← 旧的

日志轮转：旧日志太长就删旧的留最近的。microcompact 一模一样。

但 *auto-compact 是 LLM 自己写摘要压缩自己的对话历史*——这东西以前真没有，因为没有能理解自然语言的东西。*这个是新的。*


👉 s07 · Task System

Harness 版本：JSON 持久化 + blockedBy 依赖图

祖宗：Makefile（1976）

Makefile 写 app: main.o utils.o 表示 app 依赖两个 .o 文件。Task 2 的 blockedBy: [1] 就是 Make 的 dependency。依赖不满足就不调度。

换了个文件格式，换了个调度对象（从编译任务变成 agent 任务），思想一模一样。


👉 s08 · Background Tasks

Harness 版本：异步执行 → 通知队列 → 注入 LLM 对话

祖宗：Producer-Consumer（Dijkstra 1965）+ Thread Pool

以前：回调函数处理异步结果。现在：回调不是函数，是把结果*写成自然语言*扔进 LLM 对话。模型在下一轮看到"后台任务 X 跑完了，结果是 Y"，自己决定下一步。

*这个"通知注入对话"的方式是新的。*


👉 s09 · Team Messaging

Harness 版本：JSONL inbox → agent 间双向通信

祖宗：Erlang Actor Model（1986）

Erlang 里每个 actor 有自己的 mailbox，Pid ! Message 发送，receive 接收。Agent Teams 里每个 agent 有自己的 JSONL inbox，BUS.send + BUS.read_inbox。

*Agent Teams 就是 Erlang 风格的 Actor 系统，只是 actor 从 Erlang 进程换成了 LLM。*


👉 s10 · Protocols

Harness 版本：request_id 关联请求和响应 + 状态机

祖宗：TCP 三次握手（1981）

TCP 用 sequence number 关联 SYN 和 ACK。Agent 用 request_id 关联 shutdown_request 和 shutdown_response。

*request_id 就是 TCP 的 seq number。*


👉 s11 · Autonomous Loop

Harness 版本：idle 等待 → 扫描任务池 → 自动认领 → 继续工作

祖宗：Cron（1975）+ Work Stealing（1994）

定时醒来 → 扫描待办 → 有活就干 → 没活继续睡 → 超时退出。

*就是 cron + work stealing。*


🆕 真正新的只有 3 个

*auto-compact* — LLM 自己写摘要压缩自己的记忆。以前没有任何东西能理解自然语言来做这件事。

*stop_reason* — 循环什么时候停，不是代码判断，是模型说停。控制流反转。

*通知注入对话* — 异步回调不是函数调用，是把结果写成自然语言放进聊天记录。


🎯 那 Harness 到底新在哪儿

不新在单个机制。新在两件事：

1. *旧零件组装成了新 cockpit*
sudo + Make + Erlang + cron，这些零件以前各自独立。没人把它们组合成一个围绕 LLM 的控制面。Harness = 旧零件拼成一个 cockpit，让 LLM 坐进去开飞机。

2. *控制流反转*
传统程序：代码决定 → 调工具 → 代码判断下一步
Agent Harness：模型决定 → harness 查权限 → 执行 → 结果注入对话 → 模型再决定

代码不再是决策者，代码只是模型的驾驶舱。


📌 两句话总结

*Harness 的每个零件都能在计算机科学史前时代找到祖宗。*

*它新在组合方式和控制权转移。*

The model is the agent. The code is the harness.

#AIAgent #Agent架构 #技术本质 #ClaudeCode #程序员 #系统设计
