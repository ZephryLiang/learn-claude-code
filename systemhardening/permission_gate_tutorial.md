# Permission Gate 从 0 到 1：在 Agent 和工具之间加一道安检

> 模型决定"做什么"，工具负责"执行"。Permission Gate 是夹在它们之间的安检通道。
>
> **本文分析的是教学版代码**（[permission_gate.py](systemhardening/permission_gate.py)），
> 多处做了刻意简化。文中会用「教学版 → 生产版」的对比说明哪些地方简化了，
> 以及生产环境会怎么处理。文末会汇总所有简化点。

## 目录

1. [先认识 Agent 的工具箱](#1-先认识-agent-的工具箱)
2. [教学版 vs 生产版：提前说明](#2-教学版-vs-生产版提前说明)
3. [为什么需要 Permission Gate](#3-为什么需要-permission-gate)
4. [Permission Gate 的整体架构](#4-permission-gate-的整体架构)
5. [Step 0：Bash 安全检查（bash 专用）](#5-step-0bash-安全检查bash-专用)
6. [Step 1：Deny Rules——硬拒绝规则](#6-step-1deny-rules硬拒绝规则)
7. [Step 2：Mode 快速通道](#7-step-2mode-快速通道)
8. [Step 3：Allow Rules——自动放行规则](#8-step-3allow-rules自动放行规则)
9. [Step 4：Ask User——最终兜底](#9-step-4ask-user最终兜底)
10. [Rules 匹配机制（_matches 详解）](#10-rules-匹配机制matches-详解)
11. [check() 返回后——Agent Loop 如何处理判决结果](#11-check-返回后agent-loop-如何处理判决结果)
12. [总结：完整的 5 步 Pipeline](#12-总结完整的-5-步-pipeline)
13. [动手试试](#13-动手试试)

---

## 1. 先认识 Agent 的工具箱

在理解 Permission Gate 之前，需要先知道 Agent 有哪些类型的工具。因为**不同工具的输入参数不同，直接决定了权限规则该如何设计**。

### 1.1 File I/O 工具

| 工具 | 作用 | 核心参数 |
| --- | --- | --- |
| `read_file` | 读取文件 | `path`, `limit` |
| `write_file` | 写入文件 | `path`, `content` |
| `edit_file` | 编辑文件（替换文本） | `path`, `old_text`, `new_text` |

**特点**：都有 `path` 参数。这意味着权限规则可以通过 `path` 做通配符匹配，比如"只允许读 agents/ 目录下的文件"。

### 1.2 Shell 执行工具

| 工具 | 作用 | 核心参数 |
| --- | --- | --- |
| `bash` | 执行 shell 命令 | `command` |

**特点**：唯一参数是 `command`（要执行的命令字符串）。权限规则必须通过命令**内容**来匹配，而不是文件路径。

### 1.3 为什么分类如此重要

因为不同工具的入参结构不同，匹配策略就不能一刀切：

```python
# 对 read_file 限制路径 —— 合理
{"tool": "read_file", "path": "agents/*", "behavior": "allow"}

# 对 bash 限制路径 —— 无效！bash 根本没有 path 参数
{"tool": "bash", "path": "agents/*", "behavior": "allow"}  # ❌
```

所以设计权限规则时，必须理解每种工具的输入结构。

---

## 2. 教学版 vs 生产版：提前说明

阅读本文前需要知道一个重要前提：**这份代码是教学版（teaching version），不是生产代码。**

源码中有多处明确标注了这一点：

| 源码位置 | 标注 | 含义 |
| --- | --- | --- |
| `BashSecurityValidator` 类 | `The teaching version deliberately keeps this small and easy to read` | 安全规则只有 5 条，生产环境会有几十上百条 |
| `PermissionManager` 类 | `The teaching version keeps the decision path short on purpose` | 决策路径简化，只有 5 步 |
| `is_workspace_trusted()` 函数 | `The teaching version uses a simple marker file` | 信任机制用一个标记文件示意，生产会涉及签名、证书等 |
| Step 2 auto mode 注释 | `# Teaching: fall through to allow rules, then ask` | 明确标记此处是教学简化 |

### 2.1 `is_workspace_trusted()`——一个典型的"教学版信号"

```python
def is_workspace_trusted(workspace: Path = None) -> bool:
    ws = workspace or WORKDIR
    trust_marker = ws / ".claude" / ".claude_trusted"
    return trust_marker.exists()
```

这个方法定义了**但从未在当前代码中实际使用**。它的存在只是为了展示"信任机制可以长什么样"：

| 教学版 | 生产版推测 |
| --- | --- | --- |
| 检查一个标记文件是否存在 | 检查 GPG 签名、硬件认证、远程验证服务 |
| 返回一个简单的 bool | 返回信任等级、过期时间、作用域 |
| 不区分用户/机器 | 绑定设备指纹、生物认证 |

每次看到这种"定义了却没用到"的函数，或者注释里写了 `teaching version` 的地方，都是**作者在说"这里本可以更复杂，但我简化了"**。

### 2.2 本文涉及的主要简化点预览

| 简化点 | 教学版做法 | 生产版方向 |
| --- | --- | --- |
| bash 安全规则 | 5 条硬编码正则 | 可扩展规则引擎、社区规则库 |
| 默认 rules | 3 条 | 按项目类型自动生成 |
| `always` 加 rule | 统一加 `path: "*"` | 按工具类型自动选匹配字段 |
| 信任机制 | `is_workspace_trusted` 未启用 | 完整的信任链验证 |
| `_matches` 的 content 匹配 | 只查 `command` 字段 | 根据 tool 动态映射参数字段 |
| 连续拒绝阈值 | 硬编码为 3 | 可配置、自适应 |

下面进入正题，每个步骤都会标注"这里的简化点"。

---

## 3. 为什么需要 Permission Gate

Agent 的工作方式是：模型（LLM）决定调用什么工具，代码负责执行。

问题是：**模型也可能犯错。** 比如模型可能认为删除文件是合理的操作，但你真的希望它执行吗？

没有 Permission Gate 的时候，agent_loop 是这样工作的：

```python
# 没有权限检查：模型说做什么就做什么
for block in response.content:
    if block.type == "tool_use":
        handler = TOOL_HANDLERS[block.name]  # 直接执行
        output = handler(**(block.input or {}))
```

模型要 `rm -rf /` → 代码直接执行 → 灾难。

加上 Permission Gate 后：

```python
for block in response.content:
    if block.type == "tool_use":
        decision = perms.check(block.name, block.input or {})  # ← 先安检
        if decision["behavior"] == "deny":
            output = f"Permission denied: {decision['reason']}"  # 告诉模型被拒了
        elif decision["behavior"] == "ask":
            if perms.ask_user(block.name, block.input or {}):
                output = handler(...)  # 用户同意了才执行
            else:
                output = "Permission denied by user"
        else:  # allow
            output = handler(...)  # 直接放行
```

**核心转变**：从"模型说了算"变成"安检通过了才能执行"。

---

## 4. Permission Gate 的整体架构

整个系统由 `PermissionManager` 类管理。它在启动时初始化一次：

```python
perms = PermissionManager(mode="default")
```

包含三个核心要素：

| 要素 | 类型 | 说明 |
| --- | --- | --- |
| `rules` | `list[dict]` | 权限规则列表，每条规则包含匹配条件和行为 |
| `mode` | `str` | 三种模式：default / plan / auto |
| `consecutive_denials` | `int` | 连续拒绝计数，用于触发建议 |

当模型调用工具时，每个工具调用都会经过 `check()` 方法。它的返回结果是一个字典：

```python
{"behavior": "allow" | "deny" | "ask", "reason": "为什么做这个决定"}
```

三个可能的判决：

| behavior | 含义 | 后续处理 |
| --- | --- | --- |
| `allow` | 允许执行 | agent_loop 直接调用工具 |
| `deny` | 拒绝执行 | agent_loop 把拒绝原因作为 tool_result 返回给模型 |
| `ask` | 需要用户确认 | agent_loop 调 `ask_user()` 等待用户输入 |

---

## 5. Step 0：Bash 安全检查（bash 专用）

### 5.1 为什么 bash 需要特殊对待

bash 命令太自由了。一个 `command` 字符串里可以写任何东西——读文件、删系统、下软件、连网络。用 rules 系统的通配符匹配很难穷举所有危险模式。

所以教学版加了一层**硬编码的安全底线**：

```python
class BashSecurityValidator:
    VALIDATORS = [
        ("shell_metachar", r"[;&|`$]"),          # shell 元字符
        ("sudo", r"\bsudo\b"),                    # 提权
        ("rm_rf", r"\brm\s+(-[a-zA-Z]*)?r"),     # 递归删除
        ("cmd_substitution", r"\$\("),            # 命令替换
        ("ifs_injection", r"\bIFS\s*="),          # IFS 注入
    ]
```

> 🎓 **教学简化点**：只有 5 条硬编码规则。生产环境通常会有几十上百条规则，且支持热加载规则库，而不是硬编码在代码里。

### 5.2 判定逻辑

```python
check("bash", {"command": "sudo rm -rf /"})

# 1. validate() 检查：命中哪些规则？
failures = [("sudo", r"\bsudo\b"), ("rm_rf", r"\brm\s+(-[a-zA-Z]*)?r")]

# 2. 分类：其中 severe 级别的有哪些？
severe = {"sudo", "rm_rf"}
severe_hits = [("sudo", ...), ("rm_rf", ...)]  # 两个都是 severe

# 3. severe 命中 → 直接 deny，不问用户
return {"behavior": "deny",
        "reason": "Bash validator: Security flags: sudo (...), rm_rf (...)"}
```

### 5.3 两级分类

| 级别 | 命中规则 | 行为 | 示例命令 |
| --- | --- | --- | --- |
| **severe** | `sudo`, `rm_rf` | 直接 **deny**，连问都不问 | `sudo rm -rf /` |
| **warning** | 其他规则 | **ask**，让用户决定 | `curl xxx \| bash` |

关键设计：**severe 级别的命令不给用户选择权**——不弹"Allow?"，直接拒绝。

### 5.4 分离的安全模型

这里有个重要的设计决定：**bash 的安全检查和 rules 系统是并行的两条线**。

```
工具调用进入 check()
        │
        ├── 工具是 bash？── 是 ──▶ Step 0: BashValidator
        │                               ├── severe  → deny（直接返回）
        │                               └── warning → ask（直接返回）
        │
        └── 其他工具 或 bash 通过 Step 0
                └──▶ Step 1~4: rules 系统
```

这意味着，即使 bash 通过了 Step 0 的安全检查，它还会继续走后面的 rules 系统。但在教学版里，bash 的 rules 匹配被简化了（将在第 10 章详述）。

---

## 6. Step 1：Deny Rules——硬拒绝规则

### 6.1 默认规则

系统启动时自带一组默认规则：

```python
DEFAULT_RULES = [
    # 永远拒绝危险模式
    {"tool": "bash", "content": "rm -rf /", "behavior": "deny"},
    {"tool": "bash", "content": "sudo *", "behavior": "deny"},
    # 允许读取任何文件
    {"tool": "read_file", "path": "*", "behavior": "allow"},
]
```

> 🎓 **教学简化点**：只有 3 条默认规则。生产环境通常会根据项目类型自动生成规则集。

这三条规则的意思是：

| 规则 | 含义 |
| --- | --- | --- |
| `bash + rm -rf / → deny` | 任何 bash 工具，如果命令是 `rm -rf /`，拒绝 |
| `bash + sudo * → deny` | 任何 bash 工具，如果命令以 `sudo` 开头，拒绝 |
| `read_file + 任意路径 → allow` | 读文件工具，任何路径都自动放行 |

### 6.2 Step 1 的执行逻辑

```python
# Step 1: Deny rules（优先于 mode 和 allow rules）
for rule in self.rules:
    if rule["behavior"] != "deny":   # 只处理 deny 类型的规则
        continue
    if self._matches(rule, tool_name, tool_input):  # 检查是否匹配
        return {"behavior": "deny",
                "reason": f"Blocked by deny rule: {rule}"}
```

**遍历 rules，找 behavior="deny" 且匹配当前工具调用的规则 → 命中就拒绝，不再继续。**

### 6.3 为什么 deny rules 放在最前面

这是有意为之的设计：**deny rules 高于一切**。无论当前是什么 mode（plan/auto/default），只要规则里写了 deny，就优先拒绝。

```
权重大小：
  deny rules  >  mode  >  allow rules  >  ask_user
（最优先）                              （最后兜底）
```

---

## 7. Step 2：Mode 快速通道

通过 Step 1（没有 deny rule 命中）之后，进入 mode 判断。

三种 mode 对应三种不同的安全策略：

```python
# Step 2: Mode-based decisions
if self.mode == "plan":
    # Plan mode: deny all write operations, allow reads
    if tool_name in WRITE_TOOLS:
        return {"behavior": "deny", "reason": "Plan mode: write operations are blocked"}
    return {"behavior": "allow", "reason": "Plan mode: read-only allowed"}

if self.mode == "auto":
    # Auto mode: auto-allow read-only tools, ask for writes
    if tool_name in READ_ONLY_TOOLS or tool_name == "read_file":
        return {"behavior": "allow", "reason": "Auto mode: read-only tool auto-approved"}
    pass  # Teaching: fall through to allow rules, then ask

# default mode: fall through to Step 3 and Step 4
```

> 🎓 **教学简化点**：auto mode 对 write 操作的处理是"继续往下走 rules → ask"，没有做更精细的自动分类。生产环境可能会对不同类型的 write 做差异化处理。

### 7.1 三种 mode 对照

| Mode | 适用场景 | 读操作 | 写操作 |
| --- | --- | --- | --- |
| **default** | 完全控制 | 走 rules → 最终 ask | 走 rules → 最终 ask |
| **plan** | 审查代码、只读探索 | ✅ 自动允许 | ❌ 直接拒绝 |
| **auto** | 日常开发，信任 read | ✅ 自动允许 | 走 rules → ask |

### 7.2 设计哲学：连续拒绝后的建议

教学版有一个"连续拒绝检测"：

```python
if self.consecutive_denials >= self.max_consecutive_denials:
    print(f"  [{self.consecutive_denials} consecutive denials -- "
          "consider switching to plan mode]")
```

注意它建议的是 **plan mode**（更严），而不是 auto mode（更松）。这是因为：

> **你一直在拒绝 → 说明模型在做你不想要的事 → 建议收紧权限，让模型只能读，不能写**

这是一个安全优先的设计决策。

> 🎓 **教学简化点**：`max_consecutive_denials = 3` 是硬编码的。生产环境应该做成可配置或者自适应阈值。

---

## 8. Step 3：Allow Rules——自动放行规则

进入 Step 3 意味着：Step 1 没有 deny rule 命中，Step 2 的 mode 也决定放行（或 default mode）。

```python
for rule in self.rules:
    if rule["behavior"] != "allow":
        continue
    if self._matches(rule, tool_name, tool_input):
        self.consecutive_denials = 0
        return {"behavior": "allow", "reason": f"Matched allow rule: {rule}"}
```

### 8.1 Allow Rules 的来源

有两种方式产生的 allow rules：

**（1）默认规则**：`read_file` 默认就在 allow rules 里

```python
{"tool": "read_file", "path": "*", "behavior": "allow"}
```

所以读文件永远不会问用户——除非有 deny rule 拦截。

**（2）用户点的 "always"**：当用户对某个工具选择 "always" 时：

```python
# ask_user() 中
if answer == "always":
    self.rules.append({"tool": tool_name, "path": "*", "behavior": "allow"})
    return True
```

这会在 rules 里追加一条永久允许规则，后续同工具调用直接放行，不再问用户。

> 🎓 **教学简化点**：这里统一加 `path: "*"`，无论是什么工具。对 bash 来说 `path` 字段不合适应该用 `content`。详见第 10.4 节。

---

## 9. Step 4：Ask User——最终兜底

如果前面 4 步都没有命中，最终来到 ask_user。

### 9.1 弹窗交互

```python
def ask_user(self, tool_name: str, tool_input: dict) -> bool:
    preview = json.dumps(tool_input, ensure_ascii=False)[:200]
    print(f"\n  [Permission] {tool_name}: {preview}")
    try:
        answer = input("  Allow? (y/n/always): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    ...
```

用户在终端看到的是：

```
[Permission] bash: {"command": "ls -la"}
Allow? (y/n/always):
```

### 9.2 用户三个选项

| 输入 | 含义 | 对后续的影响 |
| --- | --- | --- |
| `y` / `yes` | 这次允许 | 重置连续拒绝计数 |
| `n` / `no` | 这次拒绝 | 连续拒绝计数 +1，满 3 次提示切 plan mode |
| `always` | 永久允许 | 追加一条 allow rule，以后同工具自动放行 |

### 9.3 拒绝后的反馈

当用户拒绝时，不仅仅是返回 False，还会触发连续拒绝检测：

```python
self.consecutive_denials += 1
if self.consecutive_denials >= self.max_consecutive_denials:
    print(f"  [{self.consecutive_denials} consecutive denials -- "
          "consider switching to plan mode]")
```

这个机制有一个重要的设计意图：**当用户一直在拒绝时，不是在责怪用户"你怎么老拒绝"，而是在提示用户"也许你应该换个模式了"。** 责任在模式选择，不在用户。

---

## 10. Rules 匹配机制（_matches 详解）

`_matches` 是 check() 内部最核心的辅助方法，它判断**一条规则是否匹配当前的工具调用**。

```python
def _matches(self, rule: dict, tool_name: str, tool_input: dict) -> bool:
    # 1. Tool name match —— 匹配工具名
    if rule.get("tool") and rule["tool"] != "*":
        if rule["tool"] != tool_name:
            return False

    # 2. Path pattern match —— 匹配文件路径（read/write 工具用）
    if "path" in rule and rule["path"] != "*":
        path = tool_input.get("path", "")
        if not fnmatch(path, rule["path"]):
            return False

    # 3. Content pattern match —— 匹配命令内容（bash 工具用）
    if "content" in rule:
        command = tool_input.get("command", "")
        if not fnmatch(command, rule["content"]):
            return False

    return True  # 全部通过 → 匹配成功
```

### 10.1 三种匹配条件

| 条件字段 | 检查目标 | 用于哪些工具 | 示例 |
| --- | --- | --- | --- |
| `tool` | 工具名 | 所有工具 | `"bash"`, `"read_file"`, `"*"`（通配） |
| `path` | `tool_input["path"]` | read / write / edit | `"agents/*"`, `"*.py"` |
| `content` | `tool_input["command"]` | bash 命令 | `"rm *"`, `"sudo *"` |

### 10.2 AND 逻辑：三条都通过才算匹配

三条条件用 AND 串联——有一条不满足就返回 False，全部通过才返回 True。

规则里没有写的字段自动跳过（不限制）。

### 10.3 三条规则的匹配实例

**规则 1：** `{"tool": "bash", "content": "rm -rf /", "behavior": "deny"}`

```
检查 read_file(path="agents/main.py")：
  tool 条件: rule["tool"]="bash" ≠ "read_file" → 返回 False（不匹配）

检查 bash(command="rm -rf /")：
  tool 条件: "bash" == "bash" → 通过
  path 条件: rule 没有 "path" → 跳过
  content 条件: fnmatch("rm -rf /", "rm -rf /") → 通过
  → 返回 True（匹配成功）
```

**规则 2：** `{"tool": "read_file", "path": "*", "behavior": "allow"}`

```
检查 read_file(path="agents/main.py")：
  tool 条件: "read_file" == "read_file" → 通过
  path 条件: rule["path"]="*" → "path != '*'" 为 False → 跳过
  content 条件: rule 没有 "content" → 跳过
  → 返回 True（匹配成功）
```

**规则 3：** `{"tool": "bash", "content": "sudo *", "behavior": "deny"}`

```
检查 bash(command="ls -la")：
  tool 条件: "bash" == "bash" → 通过
  content 条件: fnmatch("ls -la", "sudo *") → "ls -la" 不以 sudo 开头 → 不匹配
  → 返回 False（不匹配）
```

### 10.4 为什么 "always" 加的是 `path: "*"` 而不是 `content: "*"`——一个教学简化

```python
self.rules.append({"tool": tool_name, "path": "*", "behavior": "allow"})
```

不管对什么工具点 always，都加 `path: "*"`。对 read/write 来说是合理的——所有路径都放行。

但对 **bash** 点 always 时，这个设计就暴露了教学简化的本质。来看 `_matches` 的执行过程：

```python
def _matches(self, rule, tool_name, tool_input):
    # 1. tool 检查
    if rule["tool"] != "*" and rule["tool"] != tool_name:
        return False
    # → "bash" == "bash"  ✅ 通过

    # 2. path 检查 —— key 存在且不为 "*" 才进入
    if "path" in rule and rule["path"] != "*":
        # → rule["path"] = "*"，所以 "!='*'" 是 False
        # → 整个 if 条件不成立，path 检查被绕过  ❗
        #    （不会执行到 tool_input.get("path", "")）

    # 3. content 检查 —— 仅当 rule 有 "content" key 才进入
    if "content" in rule:
        # → rule 没有 "content" 这个 key
        # → 整个 if 条件不成立，content 检查被绕过  ❗

    return True  # 仅靠 tool 名匹配就通过了！
```

所以加了 `always` 之后，bash 的规则匹配结果是：

| 检查步骤 | 结果 |
| --- | --- | --- |
| tool 匹配 | ✅ `"bash" == "bash"` |
| path 检查 | ⏭️ `rule["path"]="*"` → 不进入 if 块，跳过 |
| content 检查 | ⏭️ rule 没有 `content` key → 不进入 if 块，跳过 |
| **最终** | **`return True`——纯靠工具名匹配！** |

**即：对 bash 点 always → 后面的任何 bash 命令都被自动允许，没有任何命令内容过滤。**

`_matches` 的三条 if 条件，有两条因为 `path: "*"` 和没有 `content` 而**根本没有进到检查逻辑里面**。

**教学版简化之处**：

- 代码写死了 `path: "*"`，不管什么工具都加这个字段
- 对 read/write 工具是合理的（所有路径放行）
- 对 bash 工具，应该加 `content: "*"` 而不是 `path: "*"`，但教学版为了统一简化了
- 生产环境应该根据工具类型动态选择匹配字段

---

## 11. check() 返回后——Agent Loop 如何处理判决结果

这是整个 Gate 的"闭环"关键。`check()` 返回判决结果后，`agent_loop` 根据 `behavior` 做三件不同的事：

```python
decision = perms.check(block.name, block.input or {})

if decision["behavior"] == "deny":
    # ① 拒绝：告诉模型被拒了，让它自己决定下一步
    output = f"Permission denied: {decision['reason']}"
    print(f"  [DENIED] {block.name}: {decision['reason']}")

elif decision["behavior"] == "ask":
    # ② 需要用户确认：弹窗等用户输入
    if perms.ask_user(block.name, block.input or {}):
        handler = TOOL_HANDLERS.get(block.name)
        output = handler(**(block.input or {})) if handler else f"Unknown: {block.name}"
        print(f"> {block.name}: {str(output)[:200]}")
    else:
        output = f"Permission denied by user for {block.name}"
        print(f"  [USER DENIED] {block.name}")

else:  # allow
    # ③ 直接放行：执行工具
    handler = TOOL_HANDLERS.get(block.name)
    output = handler(**(block.input or {})) if handler else f"Unknown: {block.name}"
    print(f"> {block.name}: {str(output)[:200]}")

# 三种路径最终都归结为 tool_result 送回给模型
results.append({
    "type": "tool_result",
    "tool_use_id": block.id,
    "content": str(output),
})
```

### 11.1 三种路径的对比

| behavior | 操作 | 终端打印 | tool_result 内容 |
| --- | --- | --- | --- |
| **deny** | 不执行工具 | `[DENIED] bash: Permission denied: ...` | `"Permission denied: Bash validator: ..."` |
| **allow** | 直接执行 | `> bash: ls -la` | 命令的实际输出 |
| **ask + 用户允许** | 执行 | `[Permission] ... Allow? (y/n/always):` → `> bash: ...` | 命令的实际输出 |
| **ask + 用户拒绝** | 不执行 | `[Permission] ... Allow? (y/n): n` → `[USER DENIED]` | `"Permission denied by user for bash"` |

### 11.2 模型视角

无论哪种路径，**最终结果都变成 tool_result 送回给模型**。模型通过 tool_result 的内容感知到发生了什么：

```python
# 模型内部看到的 tool_result

# allow 场景
tool_result: "agents/main.py\n\nimport os\n..."
→ 继续推理

# deny 场景
tool_result: "Permission denied: Bash validator: Security flags: rm_rf (...)"
→ 模型可能说："抱歉，系统不允许执行 rm -rf 操作，这是一种危险命令。"

# 用户拒绝场景
tool_result: "Permission denied by user for bash"
→ 模型可能说："用户拒绝了 ls 命令，我换个方式试试？"
```

**关键理解：Permission Gate 不阻止模型思考，只是告诉模型"这个操作不被允许"。模型仍然可以自主决定下一步——换个方式执行、向用户解释、或者放弃。**

### 11.3 完整终端交互示例

```
s07 >> 帮我看看当前目录有什么文件

模型决定调 bash(command="ls -la")

  check("bash", {"command": "ls -la"})
    Step 0: ls -la → 没有命中任何 validator → 通过
    Step 1: deny rules → 没有匹配 → 通过
    Step 2: mode=default → 继续
    Step 3: allow rules → 没有 bash 的 allow rule 匹配 → 继续
    Step 4: return "ask"

  [Permission] bash: {"command": "ls -la"}
  Allow? (y/n/always): y
  > bash: total 128 ...
```

---

## 12. 总结：完整的 5 步 Pipeline

来看一个完整的执行流程：

```
模型说: 调 bash(command="rm -rf /tmp/test")
                │
                ▼
╔══════════════════════════════════════════════╗
║          check("bash", {command})           ║
║                                              ║
║  Step 0: Bash Validator                      ║
║    "rm -rf /tmp/test"                        ║
║    → rm_rf pattern 命中!                     ║
║    → severe 级别                             ║
║    → return {"behavior": "deny", ...}        ║
║                                              ║
║  ❗ Step 1~4 不执行，直接返回                ║
╚══════════════════════════════════════════════╝
                │
                ▼
agent_loop:
  [DENIED] bash: Permission denied: Bash validator: ...
                │
                ▼
tool_result: "Permission denied: Bash validator: ..."
                │
                ▼
模型收到 tool_result → 自主决定下一步
```

第二个例子——没有安全问题的命令：

```
模型说: 调 read_file(path="agents/main.py")
                │
                ▼
╔══════════════════════════════════════════════╗
║          check("read_file", {path})          ║
║                                              ║
║  Step 0: 不是 bash → 跳过                    ║
║                                              ║
║  Step 1: Deny Rules                          ║
║    遍历 rules → 没有 read_file 的 deny rule  ║
║    → 通过                                     ║
║                                              ║
║  Step 2: Mode (default)                      ║
║    default → 不拦截                          ║
║                                              ║
║  Step 3: Allow Rules                         ║
║    遍历 rules → 找到 allow rule:             ║
║    {"tool":"read_file","path":"*","allow"}   ║
║    → 命中!                                   ║
║    → return {"behavior": "allow", ...}       ║
║                                              ║
║  ✅ Step 4 不执行，直接放行                  ║
╚══════════════════════════════════════════════╝
                │
                ▼
agent_loop: 直接调 run_read()
  > read_file: import os\n...
                │
                ▼
工具执行结果 → 当 tool_result 送回模型
```

### 完整决策树

```
                    check(tool_name, tool_input)
                             │
                             ▼
                    ┌─── 是 bash? ───┐
                    │                 │
                    ▼                 ▼
            BashValidator         跳过 Step 0
                    │
              ┌─────┴──────┐
              │            │
           severe        warning
              │            │
              ▼            ▼
           deny           ask
          返回            返回
                             │
                             ▼
                    Step 1: Deny Rules
                    ┌─────┴──────┐
                    │  命中?      │
                    ├── 是 ──▶ deny (返回)
                    │  否
                    ▼
                    Step 2: Mode
                    ┌─────┬─────┬──────┐
                    │plan │auto │default│
                    ├─────┴─────┴──────┤
                    │  write? → deny   │
                    │  read?  → allow  │
                    │  其他 → 继续     │
                    ▼
                    Step 3: Allow Rules
                    ┌─────┴──────┐
                    │  命中?      │
                    ├── 是 ──▶ allow (返回)
                    │  否
                    ▼
                    Step 4: Ask User
                    ┌─────┴──────┐
                    │  y → allow │
                    │  n → deny  │
                    │always→allow│
                    └────────────┘
```

---

## 13. 动手试试

```bash
python agents/s07_permission_system.py
```

启动后，尝试以下场景理解每一层的效果：

### 场景 1：正常读文件——Step 3 allow rule 放行

```
s07 >> 帮我读一下 agents/s01_agent_loop.py
```

Step 0 跳过（不是 bash）→ Step 1 无 deny → Step 2 mode 放行 → **Step 3 allow rule `read_file + path: *` 命中** → 直接放行，不问用户。

✅ **教学版：allow rule 用了 `path: "*"`，被 `_matches` 跳过不进入 if 检查块，纯靠 tool 名匹配。**

### 场景 2：危险 bash 命令——Step 0 拦截

```
s07 >> 执行 sudo rm -rf /
```

**Step 0 severe 命中** → 直接 deny，连弹窗都没有。

### 场景 3：普通 bash 命令——Step 4 问用户

```
s07 >> 执行 ls -la
```

Step 0 安全 → Step 1 无 deny → Step 2 mode 放行 → Step 3 无 allow rule → **Step 4 弹窗**：

```
Allow? (y/n/always):
```

### 场景 4：点 always——加一条 allow rule（教学简化的典型）

```
s07 >> 执行 ls -la
Allow? (y/n/always): always
```

对 bash 点 always → rules 里追加了 `{"tool": "bash", "path": "*", "allow"}`。

⚠️ **注意这是教学简化**：这条 rule 用 `path: "*"` 而不是 `content: "*"`。`_matches` 执行时：

- `path` 检查：因为 `rule["path"]="*"`，条件 `!= "*"` 为 False → **不进入 if 块，跳过**
- `content` 检查：因为 rule 没有这个 key → **不进入 if 块，跳过**
- 最终**纯靠工具名匹配**，所有后续 bash 命令都在 Step 3 自动放行

生产环境中，对 bash 的 "always" 应该加 `content: "*"` 或者更精细的内容通配规则。

### 场景 5：切 mode

```
s07 >> /mode plan
```

plan mode 下，任何 write 操作（write_file / edit_file / bash）都在 Step 2 直接 deny。

### 场景 6：查看当前 rules

```
s07 >> /rules
```

打印当前所有规则，包括默认规则和 "always" 添加的规则。

---

## 附：教学简化点一览

| 简化点 | 教学版做法 | 生产版方向 |
| --- | --- | --- |
| bash 安全规则 | 5 条硬编码正则 | 可扩展规则引擎、社区规则库 |
| 默认 rules | 3 条 | 按项目类型自动生成 |
| `always` 统一用 `path: "*"` | 不区分工具类型 | 根据 tool 动态选择 `path`/`content` 字段 |
| `_matches` 的 content 匹配 | 写死取 `command` | 根据 tool 动态映射参数字段 |
| 连续拒绝阈值 | 硬编码 3 | 可配置、自适应 |
| `is_workspace_trusted` | 定义了未使用，标记文件示意 | 签名验证、硬件认证 |
| 工具类型 | 4 种（read/write/edit/bash） | 动态注册、自定义工具 |
| 运行时控制 | 终端 REPL + `/mode` `/rules` | Web UI、REST API、WebSocket |

---

> **核心 takeaways：**
>
> 1. Permission Gate 是 agent_loop 和工具执行之间的安检通道
> 2. 5 步 Pipeline：Bash Validator → Deny Rules → Mode → Allow Rules → Ask User
> 3. 前三步自动判定，后一步需要用户交互
> 4. 每次判定都有 behavior + reason，用户和模型双方都知情
> 5. 运行时可以随时切 mode、查 rules，不重启
> 6. 设计哲学：**"Safety is a pipeline, not a boolean."**
> 7. **本文分析的是教学版代码**，每个简化点都已标注并说明了生产环境的处理方向
