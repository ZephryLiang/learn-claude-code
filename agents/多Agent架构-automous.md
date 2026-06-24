# 你以为多 Agent 需要一个调度器？真正自主的 Agent 是自己找活、自己休息、自己认领任务

先想一个问题：你有一个 Lead，5 个 Teammate，任务板上有 10 个未认领的任务。Manual assignment 意味着 Lead 要——挑任务、找空闲 Teammate、组织 prompt、派发——重复 10 次。

**Lead 成了瓶颈。它花在派活上的时间比思考还多。**

啃完 learn-claude-code 第 11 课，看到它怎么消除这个瓶颈的：**干脆不让 Lead 派活了。** 每个 Teammate 自己扫任务板、自己认领、自己决定什么时候干、什么时候停。60 秒没活干就自己退出。

> *"The agent finds work itself."* —— 代码注释原话

---

## 三个基础概念

| 概念 | 一句话 | 代码里长这样 |
| --- | --- | --- |
| **Harness（脚手架）** | 你写的代码 = 身体，提供手、眼、嘴；**模型 = 大脑** | `def _run_bash(cmd): subprocess.run(cmd)` |
| **Agent Loop** | while 循环：问模型 → 执行工具 → 告诉结果 → 再问 | `while True: response = client.messages.create(...)` |
| **Tool（工具）** | 模型不真操作电脑，输出 JSON 说"我想做这个" | `{"name":"read_file","input":{"path":"/src/main.py"}}` |

**模型做决策，脚手架做执行。** 12 节课不涉及任何模型训练，全在教你写脚手架。

---

## 自主性到底"自主"在哪：四个自主权

| 自主权 | 传统程序 | 自主 Agent（s11） |
| --- | --- | --- |
| **找活** | 等待被调用/被分配任务 | 自己扫 `.tasks/`，看到 pending 任务自己认领 |
| **干活** | 按预设流程执行 | 模型自己决定每一步用什么工具、什么顺序 |
| **休息** | 任务结束 = 线程返回 | 模型判断"没活了"→ 主动调 `idle` 工具，进入 IDLE 轮询 |
| **退出** | 外部 kill | 60s IDLE 无活干 → **自己 shutdown** |

这就是 s11 和传统任务队列（Celery、Sidekiq）的本质区别：Worker 不是等消息队列推任务，而是**自己决定**什么时候接活、什么时候休息。

---

## Subagent ≠ Teammate：一次性的不是自主的

| 维度 | Subagent (s04) | Teammate (s09/s11) |
| --- | --- | --- |
| 生命周期 | spawn → 干活 → **死** | spawn → 干活 → 蹲活 → 干活 → ... |
| 自主程度 | 被动，等 lead 喂任务 | **自主**：自己扫描、认领、决策、idle、shutdown |
| 通信 | 无，一次性输入输出 | 有 inbox，持续收发 |
| 类比 | 你叫个人过来，说完他走了 | 你雇了个员工，**他自己找活干** |

**判断标准**：Agent 完成后是消失还是蹲着等下一件事？消失了 = 工具，蹲着 = 自主实体。

---

## 自主的核心引擎：WORK ↔ IDLE 状态机

每一个 Teammate 都跑在独立 daemon 线程里，靠 `_loop` 驱动：

| 维度 | WORK 阶段 | IDLE 阶段 |
| --- | --- | --- |
| 谁在跑 | 模型推理 | 脚手架代码轮询 |
| 消耗 token？ | 是 | **否**（不调 API，不花钱） |
| 做什么 | 标准 Agent Loop，最多 50 轮 | 每 5s 扫 inbox + `.tasks/` |
| 谁决定进入 | — | **模型自己**调用 `idle` 工具 |
| 谁唤醒 | — | 新消息/新任务 → 立刻回 WORK；60s 无活 → 自己 shutdown |

关键在"谁决定进入 IDLE"这一行。System prompt 里只有一句话：*"Use idle tool when you have no more work."*

不是你写的代码判断"活干完了没"——是**模型自己判断**。它看了完整的对话上下文，知道任务是不是真的做完了。判断错了也不怕，IDLE 轮询 5 秒一次兜底。

CS 里这叫 **cron + work stealing**——1975 年 Unix cron 就在做定时轮询，但这次轮询触发的是 LLM 推理。

---

## 自主认领：Pull 模式替代 Push 调度

| 维度 | Push（传统调度器） | Pull（s11 自主 Agent） |
| --- | --- | --- |
| 谁来决策"谁接活" | 中心调度器 | **每个 Agent 自己** |
| 中心需要知道什么 | 谁在线、谁忙、谁擅长什么 | **什么都不用知道** |
| 任务如何分配 | 调度器指派给特定 worker | Agent 自己扫 `.tasks/`，看到就抢 |
| 竞态保护 | 不需要（不会冲突） | `_claim_lock` 保证一人抢到 |
| 类比 | 领导派活 | **Kafka consumer group** |

自主性在这里的体现：**Agent 最清楚自己该不该接活。** Lead 只管 spawn + 往 `.tasks/` 放任务文件，剩下的事 Agent 自己搞定。

---

## 自主通信：没有中心消息队列

```
.team/inbox/
  ├── coder.jsonl      ← 各 Agent 独立邮箱
  ├── reviewer.jsonl
  └── lead.jsonl
```

| 特性 | 实现 | 自主性体现 |
| --- | --- | --- |
| 格式 | JSONL（每行一个 JSON） | 每个 Agent 独立读写自己的 inbox |
| 读取 | 读全部 → **清空** | Agent 决定什么时候读、读了怎么处理 |
| 写入 | 文件末追加一行 | Agent 决定要不要回复、回什么 |
| 本质 | 1986 年 Erlang Actor 模型 | 没有中心 broker，**每个 Actor 自治** |

---

## Lead 和 Teammate 跑的是同一个 Loop

你以为 Lead 和 Teammate 是两套代码？不。**同一个 while 循环，配置不同。**

| 配置维度 | Lead | Teammate |
| --- | --- | --- |
| tools | 14 个（含 spawn、broadcast） | 10 个（无管理权限） |
| system_prompt | "你是团队领导" | "你是 coder，没活就调 idle" |
| messages[] | Lead 的记忆 | 各自独立的记忆 |
| inbox | `lead.jsonl` | 各 Teammate 自己的 JSONL |

OpenAI Swarm、Claude Agent SDK、CrewAI 全是这个模式。

---

## 自主 Agent 的健壮性：压缩后不失忆

自主 Agent 可能在线很久，对话历史不断增长，最终需要压缩。压缩可能丢失 *"你是 coder，角色 backend"* 这条身份信息——Agent 醒来不知道自己是谁，自主性就崩了。

| 方案 | 做法 |
| --- | --- |
| 检测 | messages 被压缩到 ≤3 条 → 触发 |
| 注入 | 重新插入 identity block：*"你是 coder，团队 my-team，继续工作"* |
| 效果 | 无论压缩多少次，醒来都知道自己是谁 |

---

## 生产视角：自主 Agent 的 P0-P3 加固路径

| 级别 | 问题 | 怎么炸 | 修复 |
| --- | --- | --- | --- |
| **P0** 炸 | 消息丢失 | JSONL 读清之间崩溃 → 永久消失 | at-least-once + commit offset |
| **P0** 炸 | 僵尸线程 | daemon=True 无超时，API 卡住 → 永久挂 | join(timeout) + os._exit() |
| **P1** 脆 | 静默死亡 | `except Exception: return` → 没人知道 | 重试 + 死信 + "error" 状态 |
| **P1** 脆 | 协议无强制 | plan_approval 是工具不是闸门，可跳过 | 工具执行前加拦截层 |
| **P2** 乱 | 工具名歧义 | `shutdown_response` 对 Lead/Teammate 语义不同 | 拆成两个名字 |
| **P2** 乱 | 状态纯内存 | 进程重启，所有 pending 请求消失 | SQLite / 原子 JSON |
| **P3** 盲 | 零可观测 | 一个 print()，无指标无 trace | OpenTelemetry |

层级本身比修复方案更重要——不是所有 gap 都要填，P0 先修，P1 加固，P2/P3 按需。

但等一下。上面这些"修复方案"你看仔细了——**没有一个新概念，全是旧工程常识。**

---

## 全部是旧酒，新瓶子是 Agent 的出错模式

| 修复方案 | 旧概念 | 出处 | Agent 场景下变在哪 |
| --- | --- | --- | --- |
| commit offset | Kafka consumer offset | Kafka 2011，思想来自 1970s 数据库 WAL | 丢的不是订单数据，是 **shutdown_request / plan_approved 这类控制指令**。Agent 丢消息 → 决策出错或永久挂起，不是数据不一致 |
| join(timeout) | 线程生命周期管理 | POSIX 1995，《Java 并发编程实战》第六章 | 线程卡住的地方是 **LLM API**，不是数据库。Agent 挂了没人等它 —— 它是自主运行的，**不告警就没人知道会变成僵尸** |
| 指数退避 + 死信 | TCP 拥塞控制 + MQ 死信队列 | Van Jacobson 1988，IBM MQSeries 1990s | 重试的不是一个 HTTP 请求，是**一次 LLM 推理**。messages[] 里失败的半条 assistant 消息留不留？留了污染上下文，不留丢失上下文 |
| 拦截层 | 鉴权中间件、RBAC | Spring Security 2000s | 拦的不是人，是**模型**。人被拦了会用另一种方式，Agent 被拦了可能以为自己"没权限干活"就 idle 了。拦截的同时要**引导模型走正确路径** |
| 原子文件写 | write-temp-then-rename | Unix 1970s 习惯用法 | 多 Agent 抢同一个 task 文件，读写判定三步非原子。生产需要 **compare-and-swap**：`UPDATE WHERE owner IS NULL`，靠 affected rows 判断抢没抢到 |
| OpenTelemetry | Dapper + OpenTracing + OpenCensus | Google 2010，OTel 2021 合并 | Trace 节点不是微服务，是**工具调用**。要追踪的不止延迟，还有 `input_tokens` / `output_tokens`。任务 ID 就是 trace_id |

### 具体落地，一个一个来

**commit offset — "读即清空"改"读完推进指针"**

```
s11：读 inbox.jsonl → 清空 → 处理   ← 读清之间崩溃 = 消息消失
修复：inbox 只追加不删，每个 Agent 维护 inbox_offset.txt 记读到哪了
     处理完一条 → 更新 offset → 再读下一条
     处理到一半崩溃 → offset 不变 → 重启重新处理同一条（at-least-once）
```

同一个机制，但 Agent 场景下你面对的是：重复处理的消息可能是一条 shutdown_request，Agent 收到两次关机请求会不会行为异常？所以 Agent 的 at-least-once 需要额外处理**指令是否幂等**——同一条 shutdown 收两次，回复两次同意就好了，不能关两次。

**join(timeout) — Agent 假死检测**

传统线程卡住有客户端在等 timeout。Agent 线程卡住的判断方式是心跳：

```
Agent 每轮循环更新 heartbeat = now()
看门狗线程每秒扫所有 Agent 的 heartbeat
超过阈值 → 状态标 error → 通知 lead → lead 决定 respawn 还是跳过
```

s11 的状态机只有 working / idle / shutdown，生产加第四个：error。

**指数退避 — 重试的是思考过程**

```
传统：GET /api/orders/123 失败 → 等 2s → 重试（幂等安全）
Agent：messages[] → LLM → 网络断开，你收到了半段回复
      不能直接重试，得判断 stop_reason：
      没收到任何回复 → 原样重试
      收到了部分 tool_use → 保留 assistant msg，当作正常断点，继续下一轮
```

**拦截层 — 拦模型不是拦人**

```
s11：模型调 bash → _exec → 直接执行
生产：模型调 bash → _exec → 检查 has_approved_plan？
     没有 → 不返回 "Error"，返回引导信息：
     "你的 plan_approval 正等待 lead 审批（req_id=abc123）。
      审批通过后可调用 bash。当前有哪些备选操作？"
     引导它调 read_file 或其他不需要审批的工具，别让它 idle
```

**原子认领 — 多 Agent 抢任务**

`_claim_lock` 是进程内锁，Agent 跑在不同进程里就垮了。正确做法：

```sql
UPDATE tasks SET owner='coder', status='in_progress'
WHERE id=3 AND owner IS NULL AND status='pending'
-- affected_rows = 1 → 抢到了
-- affected_rows = 0 → 被别人抢了，继续扫
```

单个 SQL 语句是原子的，不用锁，不会竞态。

**OpenTelemetry — Agent 调用链**

传统 trace 关心"哪个服务慢"。Agent trace 关心"哪个环节烧钱"和"哪个决策点卡住了"：

```
Trace: "Lead 派任务 #3" (root span, task_id 作为 trace_id)
  ├─ coder claim 任务       (5ms)
  ├─ LLM 推理第 1 轮        (2.3s, input=4000t, output=200t)
  ├─ bash 执行命令           (150ms)
  ├─ LLM 推理第 2 轮        (1.8s, input=4500t, output=100t)
  └─ LLM 推理 → 调 idle     (1.2s, input=4800t, output=50t)
```

每轮推理把 `usage.input_tokens/output_tokens` 打到 span 属性上。看面板一眼能知道：哪个 Agent 烧钱最多、哪类任务 token 效率最低。

---

机制全是旧的，变的只有两件事：**出错了影响的是什么**（不是数据一致，是 Agent 行为失控），和**要监控的指标**（不止延迟和错误率，还有 token 消耗、心跳间隔、任务竞态次数）。

---

## 为什么 GIL 不是瓶颈

| 问题 | 真相 |
| --- | --- |
| Python GIL 同一时刻只有一个线程跑代码 | 对 |
| 所以多 Agent 线程是假的 | **错** — 每个线程大部分时间在等 API（网络 I/O，5-30s），I/O 时 GIL 释放 |
| 真正瓶颈 | **API rate limit**（并发请求数上限），不是本地线程调度 |

---

## 我的 Side Project 应用

简历编辑后台流程：分析 JD → 评估简历 → 找 Gap → 改写 → 生成 cover letter。

不用编排引擎。每一步一个自主 Teammate，各有自己的上下文，通过 inbox 传递中间结果。Coordinator 只 spawn + 放 task，不调度。

---

## 三层收获

| 层 | 本质 |
| --- | --- |
| **实践** | Agent Loop = while + messages[] + tools[]。多 Agent = 同 loop + 不同 config |
| **判断** | P0-P3 分层让你区分"教学简化"和"设计缺陷" |
| **认知** | Agent 本质是**自主**，不是被调用。Subagent→Teammate、Push→Pull、代码判断→模型自己 idle——每一步都在把控制权从脚手架还给模型 |

#AI入门 #多Agent架构 #自主Agent #ClaudeCode #源码拆解 #Agent开发
