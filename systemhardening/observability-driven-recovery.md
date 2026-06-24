# 观测性驱动的崩溃恢复：为什么观测和恢复必须一起设计

> 观测性告诉你"现在是什么状态、为什么会走到这一步"。
> 崩溃恢复告诉你"基于这个状态，下一步该怎么做"。
> 拆开设计 = 盲目重试 + 只诊断不治疗。合在一起，才是一个能自我修复的 agent 系统。

---

## 0. 一个场景看清分开设计的代价

```
用户: "帮我分析这份 JD 和我的简历差距"

Coordinator 调用 gap_analysis subagent
  → gap_analysis 调用 bash tool，超时
  → harness 没观测到 tool 卡在哪个命令上
  → harness 盲目重试 gap_analysis，一模一样再跑一次
  → 又超时

用户等了 3 分钟，得到: "抱歉，出了点问题"
```

问题出在哪？

- **观测缺失**：不知道 `bash` 卡在哪个命令上、执行了多久、是不是锁了文件
- **恢复盲目**：不知道失败原因，只能原样重试——跟祈祷没区别
- **模型被蒙着眼睛**：Coordinator 不知道 gap_analysis 怎么死的，无法重新规划

**观测和恢复是一体的。观测告诉你该走哪条恢复路径，恢复告诉你观测数据够不够用。**

---

## 1. 统一模型：观测-分类-决策-恢复-验证

```text
                        ┌──────────────────────────────────────┐
                        │         观测-恢复 统一循环            │
                        │                                      │
                        │  ① 观测                              │
                        │  捕获信号 + 附加当时在做什么的上下文    │
                        │     │                                │
                        │     ▼                                │
                        │  ② 分类                              │
                        │  这个错误模型能解决吗？                │
                        │     │                                │
                        │     ├─ 能 → ③a 注入上下文给模型       │
                        │     │        让模型自己调整           │
                        │     │                                │
                        │     └─ 不能 → ③b harness 自己扛       │
                        │              退避/重试/降级           │
                        │     │                                │
                        │     ▼                                │
                        │  ④ 恢复执行                          │
                        │     │                                │
                        │     ▼                                │
                        │  ⑤ 验证 + 记录决策点                 │
                        │  恢复成功了吗？为什么选这条路？        │
                        │  这个决策点是最有价值的观测信号       │
                        └──────────────────────────────────────┘
```

核心原则和崩溃恢复文章完全一致：

> **Harness 的核心职责不是替模型做决定，是给模型足够的信息让它做更好的决定。**

观测性就是"给模型信息"的信息来源。

---

## 2. 四层观测在恢复场景中的具体含义

### ① 执行轨迹层：当时发生了什么

| 信号 | 为什么决定恢复策略 |
| --- | --- |
| **stop_reason** | 是 `max_tokens` 截断？是 `end_turn` 正常结束？还是根本没返回（网络断了）？→ 决定走续写、正常退出、还是退避重试 |
| **最后一轮 tool 调用链** | `gap_analysis → bash("pdftotext") → timeout` — 知道卡在哪一步，才知道该重试 tool、换 tool、还是跳过整个 subagent |
| **最后一条 assistant 消息** | 模型当时说了什么？是停在半句话还是完整输出？→ 决定了续写提示的措辞：直接续上 vs 重新组织 |
| **tool_result 内容** | `"file not found"` vs `"permission denied"` vs `"command not found"` → 三种完全不同的恢复策略：修正路径 / 提权或换方式 / 修正命令 |

### ② Harness 健康度层：系统当时的状态

| 信号 | 为什么决定恢复策略 |
| --- | --- |
| **上下文利用率** | 78% → 还能继续正常执行；97% → 下一次调用必然溢出，必须先压缩再继续，否则连恢复提示都发不出去 |
| **tool 执行延迟** | bash 平均 2s，这次跑了 30s → 不是网络问题，是命令本身卡住了，重试同一个命令毫无意义 |
| **重试计数** | 第 1 次 → 注入信息，让模型调整；第 3 次 → 不再重试，走降级跳过或终止，3 次还不行说明问题不是信息缺口能解决的 |
| **subagent 是否孤儿进程** | 进程还活着只是超时 → kill + 汇报；进程已死 → 直接汇报。处理方式完全不同，Coordinator 需要知道该等还是该收尸 |

### ③ 决策点层：模型和 harness 做了什么选择

这是观测性和恢复结合最紧密的一层——**每次恢复路径的选择，本身就是一个最高价值的决策点**：

| 决策 | 观测依据 | 判断逻辑 |
| --- | --- | --- |
| **选路径 1：续写** | `stop_reason = "max_tokens"` | 模型还有话要说，被硬截断了 → 告诉它继续，别重复 |
| **选路径 2：压缩** | `overlong_prompt` 或利用率 > 90% | 上下文太长 → 压缩翻译后还给模型，不是删掉 |
| **选路径 3：退避** | `connection timeout` / `429` | harness 层问题，模型无法通过改变行为来解决 → 不打扰模型 |
| **选"告诉模型它卡住了"** | 同一 tool 连续 3 次调用，参数几乎不变 | 模型在兜圈子 → 注入纠偏提示，让它换个思路 |
| **选"跳过这个步骤"** | subagent 超时且不可恢复 | 降级策略 → 跳过失败步骤继续执行，比整个请求失败强 |
| **选"终止整个 plan"** | 3 个以上步骤不可恢复 | 不是某个步骤的问题，是整个任务不可行 → 向用户汇报，别硬撑 |

**每个恢复决策的 WHY，就是下一次 eval 和调试的原材料。**

### ④ 质量信号层：这次恢复好不好

这些信号不是单次调用能判断的，需要跨轮次观察：

| 信号 | 坏味道 |
| --- | --- |
| **兜圈子** | 同一个 tool 被连续调用 3+ 次，每次参数几乎一样 → 模型卡住了，注入的提示没生效 |
| **幻觉指示器** | `bash` 返回 "file not found"，但模型继续假装文件存在 → 模型无视 tool_result |
| **过早放弃** | 一个 tool 失败了一次，模型就直接说 "我做不到" → 恢复提示给了，但模型没尝试 |
| **过度努力** | 模型调了 20 个 tool、跑了 5 分钟才回答一个简单问题 → 恢复成本远超任务本身 |
| **恢复成功率** | 某类错误恢复率 < 30% → 恢复策略本身有问题，不是模型的问题 |
| **恢复后任务完成率** | 恢复了，但最终用户需求没完成 → 最坏的情况——"沉默的失败" |
| **自修正率** | 模型发现错误后主动纠正的比例 → 这是高级能力的标志，也是观测质量的反证 |

---

## 3. 错误分类 + 观测信号 + 恢复路径 对照表

这是两篇文章合并后的完整错误分类学：

| 错误类型 | 观测信号 | 谁解决 | 恢复动作 |
| --- | --- | --- | --- |
| **API 截断** | `stop_reason = "max_tokens"` | 模型 + harness | 注入续写提示："继续，别重复" |
| **上下文溢出** | `overlong_prompt` 或利用率 > 90% | 模型 + harness | 压缩→翻译→还给模型 |
| **网络/限流** | `timeout` / `429` | 纯 harness | 指数退避 + jitter，不告诉模型 |
| **模型逻辑兜圈** | 同一 tool 连续 3+ 次调用，参数几乎不变 | 模型 + harness | 注入提示："你卡住了，换个思路" |
| **Tool 执行失败** | `tool_result` 返回非预期内容 | 模型自己 | 不自动重试，让模型看到错误自己决定 |
| **Subagent 卡死** | 超时未返回 / 进程状态异常 | harness + 模型重规划 | 终止 subagent，告诉 Coordinator"这一步失败了" |
| **权限被拒** | Permission Gate deny | 模型 + harness | 告诉模型"为什么被拒"，模型换方式重试 |
| **幻觉式 tool 调用** | tool 参数明显荒谬（不存在的文件） | 模型 + harness | 注入纠正提示："参数不对，请重新检查" |

后四种（逻辑兜圈 / tool 失败 / subagent 卡死 / 幻觉调用）是崩溃恢复文章没有展开的"软崩溃"。它们更隐蔽，更需要观测信号来发现和分类。

---

## 4. 核心决策框架：什么时候告诉模型，什么时候不告诉

判断标准不是错误类型，而是**"模型能否通过改变行为来应对"**：

```text
观测到错误 → 模型能调整吗？
              ├─ 能 → 注入上下文，让模型自己调整
              └─ 不能 → harness 自己扛（退避/重试/降级）
```

| 告诉模型 | 不告诉模型 |
| --- | --- |
| 截断 → 给它续写提示，继续写 | 网络超时 → 退避重试，和模型无关 |
| 上下文太长 → 给摘要，基于摘要继续 | 限流 → 退避 + jitter，纯工程问题 |
| 兜圈子 → 指出"你卡住了，换个思路" | 磁盘满 → 清理 + 重试 |
| 权限被拒 → 告诉"为什么被拒"，它会换方式 | 进程崩溃 → 重启 |
| subagent 挂了 → 汇报"这一步失败了" | 配置错误 → harness 修复 |

这也呼应了 Permission Gate 那篇文章的核心洞察：**告诉模型"为什么被拒"，和告诉模型"为什么出错了"，是完全相同的模式。**

---

## 5. 具体到 resume-editor-agent 的观测点设计

把观测-恢复循环落实到 resume-editor-agent 的执行流程上，每个关键节点埋点：

```text
用户上传 resume + JD
        │
        ▼
┌─ [观测点 1] Coordinator.plan() ────────────────────┐
│  • 输入 token 数 / 上下文利用率                       │
│  • 决策：选了哪些 subagent？跳过了哪些？为什么？       │
│  • plan 生成的耗时                                   │
│  • 如果 plan 生成失败 → 分类为 context_overflow 或    │
│    model_error，走对应的恢复路径                      │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─ [观测点 2] Subagent.run() [× N 个] ───────────────┐
│  • 每个 subagent 的 latency / token 消耗             │
│  • tool 调用次数 / 失败-重试次数                      │
│  • skill 加载耗时                                    │
│  • 是否触发了 context compress                        │
│  • 异常时走分类-恢复：                                 │
│    - subagent 超时 → 降级跳过，告诉 Coordinator       │
│    - tool 兜圈子 → 注入纠偏提示                        │
│    - tool 执行失败 → 不插手，让模型看到错误自己决定    │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─ [观测点 3] Coordinator.aggregate() ───────────────┐
│  • 汇总时的 token 消耗                                │
│  • 最终输出与各 subagent 产出的信息一致性              │
│  • 如果某 subagent 被跳过了，Coordinator 如何弥补？    │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─ [观测点 4] 全局质量信号 ───────────────────────────┐
│  • 总耗时 / 总 token 消耗 / 总 tool 调用次数          │
│  • 有没有 subagent 之间信息冲突？                     │
│  • 用户是否需要 follow-up（意味着输出不完整）？        │
│  • 本次会话触发了多少次恢复？各走了哪条路径？          │
└─────────────────────────────────────────────────────┘
```

> 具体实现代码见 [附录：ObservedCoordinator 参考实现](#附录observedcoordinator-参考实现)

---

## 6. 落地清单：从零到一的设计顺序

```text
第一层：观测基础（必须最先做）
□ 全链路 trace_id，贯穿 Coordinator → subagent → tool
□ stop_reason、token 消耗、tool 调用链 的结构化日志
□ 每个 tool_result 的退出码 + 耗时

第二层：错误分类（观测数据够了才能做）
□ 定义错误分类学（API 截断 / 上下文溢出 / 网络 / 逻辑兜圈 / tool 失败 / ...）
□ 每种错误类型的"该告诉模型 vs 该自己扛"判断标准
□ 3 次重试上限（适用于所有类型）

第三层：恢复路径（分类清楚了才能决策）
□ 注入续写提示（max_tokens）
□ 上下文压缩翻译（overlong_prompt）
□ 指数退避 + jitter（connection / rate limit）
□ 注入纠偏提示（兜圈子 / 幻觉）
□ 降级跳过（subagent 不可恢复时）

第四层：验证 + 持续优化（跑起来之后才能做）
□ 恢复成功率按错误类型统计
□ 恢复后任务完成率（恢复了但没完成任务 = 沉默的失败）
□ 降级频率监控（太高说明某组件不可靠）
□ 恢复耗时的 P50 / P99
```

---

## 7. 一句话总结

> **观测性负责回答"现在是什么状态、为什么会走到这一步"。崩溃恢复负责回答"基于这个状态，下一步该怎么做"。**
>
> 观测和恢复在工程上必须一起设计——你观测的粒度决定了你能给模型多少信息，你给模型的信息质量决定了它自我恢复的上限。
>
> Harness 的核心职责不是替模型做决定，是给模型足够的信息让它做更好的决定。观测性就是"信息"的来源，崩溃恢复就是"传递信息"的管道。

---

## 附录：ObservedCoordinator 参考实现

```python
class ObservedCoordinator:
    """
    观测驱动的 Coordinator：
    每一步都记录决策点，每个错误都走分类-恢复流程
    """

    async def execute_plan(self, resume, jd, goal):
        plan = await self.plan(resume, jd, goal)

        # 观测点 1：规划决策
        self.observe_decision({
            "type": "planning",
            "available": list(self.registry.keys()),
            "selected": [s.id for s in plan.steps],
            "skipped": [s for s in self.registry if s not in plan.steps],
            "reasoning": plan.reasoning,
        })

        results = {}
        for step in plan.steps:
            # 观测点 2：每个 subagent 的执行
            try:
                outcome = await self.run_subagent(step, results)
                results[step.id] = outcome
            except SubagentTimeout as e:
                # 观测点 3：恢复决策
                recovery = self.classify_and_recover(e, step, plan)
                self.observe_decision({
                    "type": "recovery",
                    "error": str(e),
                    "classification": recovery.error_type,
                    "action": recovery.action,
                    "outcome": recovery.result,
                    "impact": f"skipped {step.id}, continuing with remaining steps",
                })

                if recovery.was_degraded:
                    continue  # 跳过失败的步骤，继续执行
                else:
                    break     # 不可恢复，终止 plan

        return self.aggregate(results)

    def classify_and_recover(self, error, step, plan):
        """
        观测 → 分类 → 决策 → 恢复
        """
        if isinstance(error, ContextOverflowError):
            return self.recover_by_compaction(error)
        elif isinstance(error, ToolLoopDetected):
            return self.recover_by_injecting_context(
                "You've been calling the same tool with similar "
                "parameters. The results aren't changing. Try a "
                "different approach or report what you're stuck on."
            )
        elif isinstance(error, SubagentTimeout):
            return self.recover_by_degradation(step, plan)
        elif isinstance(error, ConnectionError):
            return self.recover_by_backoff(error)

    def observe_decision(self, decision):
        """
        记录的不是"发生了什么"，而是"为什么做了这个选择"
        """
        self.trace_log.append({
            "trace_id": self.trace_id,
            "timestamp": time.time(),
            "decision": decision,
            "context": {
                "current_step": self.plan.current_step,
                "token_usage": self.ctx.utilization(),
                "recent_tools": self.tool_trace.last_n(3),
            }
        })
```

---

## 关联阅读

- [error_recovery_xiaohongshu.md](error_recovery_xiaohongshu.md) — 三条恢复路径 + "error 也是信息"的核心洞察
- [permission_gate_tutorial.md](permission_gate_tutorial.md) — 同一个模式：告诉模型"为什么被拒"，模型换方式重试
- [hooks-system-design-decisions.md](hooks-system-design-decisions.md) — Hook 系统中每个决策点的观测和恢复
- [../docs/multi-agent-autonomy-patterns.md](../docs/multi-agent-autonomy-patterns.md) — 四种编排模式在不同错误类型下的恢复策略差异
