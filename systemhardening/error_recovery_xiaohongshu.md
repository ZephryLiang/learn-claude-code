# Agent 崩溃了怎么办？大多数人的第一反应都错了

> 碰到 max_tokens —— 重试。API 抽风 —— 重试。上下文炸了 —— 还是重试。
> 但真正的问题不是"重试几次"，而是**模型知不知道刚才发生了什么**。

## Error recovery ≠ 重试机制

写 agent 的人几乎都会遇到这三件事：

▸ 输出被截断
  API 返回：stop_reason = "max_tokens"
  表现：模型话没说完就停了

▸ 上下文过长
  API 返回：overlong_prompt 错误
  表现：对话太长，API 直接拒收

▸ 网络抖动
  API 表现：连接超时 / 速率限制
  表现：调不通模型，agent 直接挂

大部分 harness 的做法：**包个 try-catch，重试，重试，还是重试**。

但这里有一个被忽视的关键问题：

**重试之前，你告诉模型发生了什么吗？**

## 核心洞察：error 也是信息

  ❌ 错误思路：出错了 → 重试 → 同样的输入再丢一次 → 期望结果不同
  ✅ 正确思路：出错了 → 告诉模型"刚才发生了什么" → 让模型自己调整

对模型来说，error 和 tool_result **没有本质区别**——都是信息输入。

tool_result 告诉模型"bash 返回了什么"。
error recovery 告诉模型"调用为什么没成功"。

**信息给到位了，模型自己知道该怎么调整。你不需要替它做决定。**

## 三条恢复路径，回答同一个问题："你告诉了模型什么？"

### 路径 1：max_tokens —— "话没说完，继续说"

API 返回 `stop_reason: "max_tokens"`。模型还有话要说，但被硬截断了。

**大部分人的做法**：啥也不说，直接重试。模型看到自己最后一条消息是半截的，一脸懵。

**正确的做法**：注入一条清晰的续写指令：

  CONTINUATION_MESSAGE = (
      "Output limit hit. Continue directly from where you stopped -- "
      "no recap, no repetition. Pick up mid-sentence if needed."
  )

三个关键设计点：

1. **"Continue directly"** —— 不要重新组织语言，接着往下说
2. **"no recap, no repetition"** —— 别把之前说过的再讲一遍（模型很喜欢这么干）
3. **"mid-sentence if needed"** —— 哪怕停在半句话，也从那里接上

> 这条消息就是告诉模型："你被截断了，不是你的错，继续就好。"

**为什么不是无限续写？** 设置 `MAX_RECOVERY_ATTEMPTS = 3`。3 次还截断，说明任务本身太大了，不是续写能解决的——停下来，拆分任务。

### 路径 2：prompt_too_long —— "对话太长了，这是摘要"

上下文越长，模型越贵、越慢，直到 API 直接拒绝。

**大部分人的做法**：截掉前面的消息，只保留最近的。粗暴删除 → 丢失关键上下文 → 模型开始胡言乱语。

**正确的做法**：压缩，不是截断。

  def auto_compact(messages):
      prompt = (
          "Summarize this conversation for continuity. Include:\n"
          "1) Task overview and success criteria\n"
          "2) Current state: completed work, files touched\n"
          "3) Key decisions and failed approaches\n"
          "4) Remaining next steps\n"
          "Be concise but preserve critical details.\n\n"
          + conversation_text
      )
      summary = client.messages.create(
          model=MODEL, messages=[{"role": "user", "content": prompt}],
          max_tokens=4000,
      ).content[0].text
      return [{"role": "user", "content": (
          "Session continues from previous conversation. "
          f"Summary:\n\n{summary}\n\n"
          "Continue from where we left off."
      )}]

**关键区别**：

  截断（删历史）  →  模型失忆，不知道之前发生了什么
  压缩（翻译历史）→  模型拥有完整上下文，只是更短了

> 你不是删掉信息，你是把信息**翻译成更短的形式**还给模型。

这和人类开会一样：你不希望前面的会议记录全部重读一遍，但你需要一份会议纪要。

### 路径 3：connection error —— "这事模型帮不上忙"

网络断了、API 限流了、服务端抖了——这些是 **harness 层级的问题**，模型无能为力。

**这里不需要告诉模型什么。harness 自己扛。**

  def backoff_delay(attempt):
      delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)  # 1s → 2s → 4s
      jitter = random.uniform(0, 1)                        # 防惊群
      return delay + jitter

为什么加 jitter？假设 100 个 agent 同时遇到限流，同时退避，同时重试 → 又同时被限流。随机抖动把重试时间打散，避免"惊群效应"。

**和前两条路径对比**：

  路径 1：max_tokens
    告诉模型："你被截断了，继续"
    谁解决：模型 + harness

  路径 2：prompt_too_long
    告诉模型："这是摘要，继续工作"
    谁解决：模型 + harness

  路径 3：connection error
    告诉模型：不需要，harness 自己扛
    谁解决：纯 harness 层

> 传给模型的信息，要么帮它调整行为（路径 1、2），要么不打扰它（路径 3）。关键是你**判断**哪些事该让模型知道。

## 完整流程：一个决策循环

  API 返回
      │
      ├─ stop_reason == "max_tokens"
      │       ├─ 重试次数 < 3 → 注入续写提示 → 继续
      │       └─ 重试次数 = 3 → 终止，任务太大需拆分
      │
      ├─ API error
      │       ├─ prompt_too_long → 压缩上下文 → 重试
      │       ├─ connection/rate  → 指数退避 + jitter → 重试
      │       └─ 重试耗尽         → 优雅终止
      │
      └─ stop_reason == "end_turn" → 正常结束

**3 次重试上限贯穿始终**。不是怕重试太多浪费资源，而是：如果 3 次告诉模型"发生了什么"之后它还是走不出来，那说明问题不是信息缺口能解决的。

## 更深一层：这不是巧合

如果你看过 Permission Gate 的设计，会发现同一个模式：

  Permission Gate： tool 被 deny  → 告诉模型"为什么被拒" → 模型换种方式重试
  Error Recovery：   API 出错     → 告诉模型"发生了什么" → 模型自己调整

**Harness 的核心职责不是替模型做决定，是给模型足够的信息让它做更好的决定。**

你是给模型装工具的，不是替模型开工具的。

## 一句话总结

> Error recovery 不是重试魔法，是信息传递。
> 告诉模型发生了什么，它会自己爬起来。

*你还遇到过哪些 agent "自己恢复"或"恢复失败"的场景？评论区聊聊，我帮你分析应该走哪条路径。*
