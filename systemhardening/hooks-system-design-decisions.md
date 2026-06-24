# Hook System：Agent 系统的扩展性设计

> 拆解 Claude Code 的 Hook System 设计，理解 agent 架构中的扩展点模式

---

## 一、出发点：为什么 agent 系统需要 hooks

一个 agent loop 的核心极简：

```text
收到模型响应 → 解析工具调用 → 执行工具 → 返回结果 → 循环
```

最早的版本里，所有行为都写死在 loop 里。当你想加一个"执行前检查权限"或"执行后记录日志"时，你必须改 loop 本身。改一次可以，改十次 loop 就成了一团乱麻。

Hook 要解决的就是这个问题：**在不修改 loop 的前提下注入自定义行为。**

```text
没有 hooks：改行为 = 改 loop 代码
有 hooks：改行为 = 注册一个 hook 脚本
```

这是软件工程的开闭原则在 agent 架构里的直接应用——对扩展开放，对修改关闭。

---

## 二、我们设计了什么

### 2.1 三个事件点

系统在 agent loop 上开了三个口子：

- **SessionStart**：loop 启动时触发一次。适合：初始化检查、环境验证、加载配置
- **PreToolUse**：每次 tool 执行之前触发。适合：安全检查、参数校验、权限判断
- **PostToolUse**：每次 tool 执行之后触发。适合：日志记录、结果审计、额外信息注入

事件点的选择原则：**覆盖 agent 生命周期的关键节点**。启动、执行前、执行后——三个点就能覆盖绝大多数扩展需求。更完整的系统可以加更多（比如 PostResponse、onError），但 teaching version 保持最小。

### 2.2 三态 exit code 协议

hook 本质上是一个外部脚本（shell 命令），如何和 loop 通信？最简单的方式：退出码。

```text
exit 0 → 继续执行，一切正常
exit 1 → 阻止执行，拒绝当前工具调用
exit 2 → 注入消息，向 conversation 中插入一条信息
```

**exit 0 的隐含能力**：hook 可以通过 stdout 返回 JSON 来和 loop 做结构化通信（见下节）。

**exit 1 的完整流程**：不仅仅是跳过工具执行，还会生成一条 tool_result 告知模型"被 hook 阻止"，让模型理解发生了什么，而不是莫名其妙被跳过。

**exit 2 的消息注入**：消息通过 stderr 传递，loop 将其作为独立的 `[Hook message]` 追加到 results 中。exit 2 不阻止工具执行——它和 exit 1 是正交的。

### 2.3 JSON stdout 扩展协议

exit 0 时，hook 可以通过 stdout 返回 JSON，实现更丰富的交互：

```json
{
  "updatedInput": { "command": "ls -la" },
  "additionalContext": "磁盘占用已达 92%",
  "permissionDecision": "allowed"
}
```

#### updatedInput 字段

PreToolUse hook 检测到某个参数不安全，想修改后再执行。它不是要阻止调用，而是要改参数。这种情况下就应该在 stdout 里返回更新后的输入参数。

#### additionalContext 字段

PostToolUse hook 发现了和当前工具无关但模型应该知道的上下文（比如系统资源告警）。这时候需要独立的信道传给模型，而不是污染 tool output。

#### permissionDecision 字段

hook 代为做出了权限判断（比如命中 IP 白名单），不需要再弹框问用户。hook 可以直接告诉 loop："我已经判断过了，放行。"

这三个字段不是理论推导出来的，是从真实的 hook 使用场景里长出来的需求。

### 2.4 Trust 机制：谁需要信任谁

先厘清 hook 系统的协作关系。

Hook 的出现是为了让 agent loop 可扩展——其他团队可以注入行为而不改 loop。这意味着：

```text
Harness 开发者（你）         ← 写了 agent loop 和 HookManager
     ↓ 提供扩展接口
审计团队 / 安全团队 / 合规团队  ← 写了 hook 脚本
     ↓ 加载到 agent
Harness 开发者（你）         ← 运行这些 hook
```

**信任问题在这里**：你是 harness 开发者，审计团队给了你一个 audit-hook.sh。你加载它之前，需要确认：

1. 它确实做了审计日志工作（功能正确）
2. 它没有偷着删文件（没有恶意行为）
3. 它不会因为一个 bug 阻塞所有 tool call（不影响稳定性）

你需要的是一道门禁：**我 review 过了这些 hook，确认没问题，放行。**

#### Teaching version 的做法

最简单的门禁：一个标记文件。

```text
CLI 模式：用户手动创建 .claude/.claude_trusted → hook 才执行
SDK 模式：主动 import 的调用方自己负责 → 直接放行
```

CLI 模式下，默认不信任任何 hook。你审查完 hook 内容后，touch 这个文件说"可以了"。

SDK 模式是另一条路径：你在自己的程序里 `from hooks_system import HookManager; HookManager(sdk_mode=True)`。你作为代码作者，自己决定加载什么 hook，不需要额外的文件门禁。

#### Production version 的做法

真正的团队协作中，一个标记文件不够。需要更完整的信任链：

**签名验证**：hook 提交时用私钥签名，harness 部署时验签。Git GPG 签名 + CI 校验可以在上线前自动拦截未经审核的 hook。

**声明式权限**：hook 必须在头部声明需要的权限（读文件、写日志、禁止联网等），harness 加载时校验声明的权限是否在白名单内。

**沙箱执行**：hook 跑在受限环境里——只读文件系统、禁止网络、限制 CPU 时间。即使 hook 有恶意行为，也被沙箱隔离。

**分级管控**：不同事件点的信任要求不同。

- PreToolUse 能阻止工具执行，风险最高 → 需要签名 + 代码审查
- PostToolUse 只做记录，风险较低 → 签名即可
- SessionStart 初始化钩子 → 需管理员审批

**Telemetry + 熔断**：记录每个 hook 的执行耗时、退出码、输出大小。某个 hook 连续超时或异常时自动禁用并告警。

### 2.5 Matcher 过滤

hook 定义中有一个 `matcher` 字段，可以按工具名过滤：

```json
{
  "command": "echo 'bash called'",
  "matcher": "bash"
}
```

`*` 匹配所有工具。这避免了每个 hook 都在脚本里自己判断工具类型。

---

## 三、设计解析：HookManager 的内部流程

```text
HookManager.run_hooks(event, context)
  │
  ├─ _check_workspace_trust()          ← 信任门禁
  │    └─ 未信任 → 直接返回空结果
  │
  ├─ 遍历 event 对应的所有 hook 定义
  │    │
  │    ├─ matcher 过滤 ← 不匹配则跳过
  │    │
  │    ├─ subprocess.run(command)       ← 执行 hook 脚本
  │    │
  │    └─ 解析退出码
  │         ├─ 0 → 尝试解析 stdout JSON（updatedInput 等）
  │         ├─ 1 → 标记 blocked，记录阻断原因
  │         └─ 2 → 收集 stderr 作为注入消息
  │
  └─ 返回聚合结果 { blocked, messages, permission_override }
```

loop 侧的使用流程：

```text
for each tool_use block:
    PreToolUse hooks → 检查是否 blocked → 执行 tool → PostToolUse hooks
```

注意一个关键点：PreToolUse hook 如果返回了 `updatedInput`，这个值会写入 `ctx["tool_input"]`，但当前版本的 loop 在调用 handler 时仍引用了原始 `tool_input` 变量。**要让 updatedInput 生效，需要在 handler 调用前从 ctx 取回更新后的值。**

---

## 四、Teaching Version → Production Version：扩展点

当前的实现有意做了简化，以下是几个主要的升级方向：

### 4.1 Trust 机制：从标记文件到完整信任体系

```text
Teaching:   .claude/.claude_trusted 文件存在与否
Production: 签名验证 + 权限粒度 + 审计日志
```

真实系统中，信任机制需要支持：按 hook 粒度授权、按命令内容做安全策略、记录所有 hook 执行轨迹用于审计。

### 4.2 Hook 超时处理

当前超时只是打印一条日志然后继续。生产环境可能需要：可配置超时策略（阻断超时的 hook、重试、降级等）。

### 4.3 更多事件类型

```text
Teaching:   SessionStart / PreToolUse / PostToolUse
Production: 加 PostResponse / onError / onIdle / onCompact
```

事件的粒度决定了系统的灵活性。每个新事件都对应一个新的集成场景。

### 4.4 异步 Hooks

当前 `subprocess.run` 是同步阻塞的。生产环境中，某些 hook（比如审计日志、指标收集）不需要阻塞主流程，应该异步执行。

### 4.5 权限系统集成

`permissionDecision` 目前只是一个字段传递。生产环境需要它和真实的权限系统打通——按规则判断、支持策略引擎、提供审计链路。

### 4.6 参考：Claude Code Agent SDK 的 Hooks 设计

[Claude Code Agent SDK](https://code.claude.com/docs/en/agent-sdk/hooks) 实现了生产级别的 hooks 系统，可以对照理解 teaching version 的简化方向。

#### 事件类型更丰富

```text
Teaching:          SessionStart / PreToolUse / PostToolUse
Claude Code SDK:   PreToolUse / PostToolUse / PostToolUseFailure /
                   UserPromptSubmit / Stop / PreCompact /
                   SubagentStart / SubagentStop /
                   PermissionRequest / Notification
```

多了三类事件：子 agent 生命周期（SubagentStart/Stop）、上下文压缩（PreCompact）、权限请求（PermissionRequest）。每个新事件都对应一个你在运营 agent 时会遇到的实际场景。

#### 编程接口替代 shell 命令

Teaching version 用 `subprocess.run` 执行 shell 脚本。SDK 用回调函数：

```python
async def protect_env_files(input_data, tool_use_id, context):
    file_path = input_data["tool_input"].get("file_path", "")
    if ".env" in file_path:
        return {
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": "Cannot modify .env files",
            }
        }
    return {}
```

回调函数比 shell 脚本更安全（没有命令注入风险）、更容易调试、可以和程序内部状态交互。

#### Matcher 使用正则

Teaching version 的 matcher 只支持精确匹配或 `*`。SDK 支持正则：

```python
HookMatcher(matcher="Write|Edit", hooks=[protect_env_files])
```

这意味着一个 matcher 可以匹配一组工具，表达力更强。

#### 显式的权限决策

Teaching version 用 exit code 1 表示"阻止"。SDK 有明确的 deny + 原因：

```python
{
    "permissionDecision": "deny",
    "permissionDecisionReason": "Cannot modify .env files"
}
```

还支持 `allow`、`deny`、`ask` 三种决策——其中 `ask` 表示 hook 不确定，转交给用户确认。

#### 核心思想一致，但抽象层级不同

```text
Teaching 版本：
    shell 脚本 → exit code → loop 解析退出码 → 决策

Claude Code SDK：
    回调函数 → 返回结构化结果 → SDK 执行决策
```

Teaching version 选择 shell 脚本 + exit code 是因为它直观、无依赖、适合教学。生产环境换成回调函数是因为类型安全、可测试、能和运行时状态交互。

---

## 五、一个验证题：加一个新事件 PostResponse

这是检验对 agent loop 理解程度的好题目。因为要答对这个，你必须清楚：

- agent loop 的 return 条件在哪里
- `stop_reason` 的含义是什么
- 工具调用结果和最终回答在代码路径上的区别

正确答案是加在 [hooks_system.py:213-214](systemhardening/hooks_system.py#L213-L214) 之间：

```text
messages.append({"role": "assistant", "content": response.content})
                                  ↑
                    PostResponse hook 放这里
if response.stop_reason != "tool_use":
    return
```

因为 PostResponse 的语义是"模型返回了非工具调用的响应"——这正好对应 `stop_reason != "tool_use"` 的分支，在 `return` 之前触发。

如果答错位置（比如加在了 for 循环内部），说明没有理清 tool_use 响应和非 tool_use 响应在 loop 中的路径差异。

---

## 六、总结

Hook System 的设计遵循了一条清晰的演进路径：

1. **识别痛点**：每次加功能都要改 loop → 不可扩展
2. **设计扩展点**：在 loop 的关键节点开口子——SessionStart、PreToolUse、PostToolUse
3. **定义通信协议**：三态退出码 + JSON stdout，让外部脚本可以和 loop 通信
4. **补充安全机制**：trust marker 防止恶意 hooks 自动执行
5. **留出演进空间**：teaching version 保持最小，但每个组件都指向了 production 方向的升级路径

这套设计模式不限于 Claude Code。任何 agent 系统——只要它有一个"收到消息 → 决定做什么 → 执行 → 继续"的循环——都可以用同样的思路来做扩展性设计。
