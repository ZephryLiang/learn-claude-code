# Resume Editor: Agent Architecture Design

> Date: 2026-05-14
> Status: Draft

## 1. Overview

Transform `resume-editor/` from a traditional REST API AI app into an agent-driven system. The core shift: instead of the user manually selecting analysis types and triggering endpoints, an **Agent Loop** plans and executes tasks autonomously, while the user retains full visibility and the ability to intercept at any step.

### Principles

- **User in control** — Agent plans are shown before execution; user can intercept at any step
- **Composable** — Each capability is a self-contained subagent; adding new capabilities needs zero framework changes
- **Progressive transparency** — The agent's thinking, planning, and execution are visible by default
- **Non-blocking intercept** — The agent pipeline doesn't wait for user feedback; user feedback retroactively updates completed steps

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                          │
│  ┌──────────┐ ┌──────────────┐ ┌────────────┐ ┌───────────┐ │
│  │ Upload   │ │ Plan Timeline│ │ Result View│ │ Chat Box  │ │
│  │ Resume/JD│ │ (SSE stream) │ │ (tabs)     │ │ (intercept)│ │
│  └──────────┘ └──────┬───────┘ └──────┬─────┘ └─────┬─────┘ │
└───────────────────────┼───────────────┼──────────────┼───────┘
                        │               │              │
                    SSE/Event        REST GET      POST /intercept
                        │               │              │
┌───────────────────────┼───────────────┼──────────────┼───────┐
│  Backend              ▼               ▼              ▼       │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Agent Runtime                             │  │
│  │                                                       │  │
│  │  POST /api/agent ──→ ┌──────────────┐                  │  │
│  │                      │ Coordinator  │                  │  │
│  │                      │ (Agent Loop) │                  │  │
│  │                      └──────┬───────┘                  │  │
│  │                             │                          │  │
│  │                  ① Plan → SSE (plan event)             │  │
│  │                  ② Execute step → SSE (step events)    │  │
│  │                  ③ Accept intercept → re-run step      │  │
│  │                                                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │            Subagent Registry                     │  │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌───────────┐        │  │  │
│  │  │  │Gap       │ │Assessment│ │Remediation│        │  │  │
│  │  │  │Analysis  │ │          │ │           │        │  │  │
│  │  │  ├──────────┤ ├──────────┤ ├───────────┤        │  │  │
│  │  │  │Rewrite   │ │Company   │ │Deep Search│        │  │  │
│  │  │  │          │ │Analysis  │ │(future)   │        │  │  │
│  │  │  └──────────┘ └──────────┘ └───────────┘        │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │                                                       │  │
│  │  ┌────────────────┐ ┌──────────────┐                  │  │
│  │  │ Tool System    │ │ Skills (s05) │                  │  │
│  │  │ (s02)          │ │ On-demand    │                  │  │
│  │  │ compile/parse/ │ │ knowledge    │                  │  │
│  │  │ web_search/··· │ │ injection    │                  │  │
│  │  └────────────────┘ └──────────────┘                  │  │
│  │                                                       │  │
│  │  ┌────────────────┐ ┌──────────────┐                  │  │
│  │  │ Task System    │ │ Memory       │                  │  │
│  │  │ (s07)          │ │ (cross-      │                  │  │
│  │  │ persistence    │ │  session)    │                  │  │
│  │  └────────────────┘ └──────────────┘                  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                             │
│  Retained REST endpoints:                                    │
│  GET  /api/models   — list models                            │
│  POST /api/parse    — upload/parse file                      │
│  POST /api/compile  — compile LaTeX (also a tool)            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 3. Agent Loop (Coordinator)

The Coordinator is the core engine. It is itself an agent (s01) that:

1. **Plans** — Reads the subagent registry, examines user input (resume + JD + goal), produces an execution plan
2. **Executes** — Iterates through plan steps, spawning subagents sequentially or in parallel
3. **Handles intercepts** — Accepts user feedback on completed steps, re-runs affected subagents
4. **Accumulates context** — Passes results between steps (cache)

### API Entry Point

```
POST /api/agent
  Body: { resume_text, jd_text, goal? }
  Response: SSE stream (see §5)
```

### Coordinator Loop

```
function run_agent(resume, jd, goal):
    plan = coordinator_plan(resume, jd, goal, registry)
    emit("plan", plan)

    cache = {"resume_text": resume, "jd_text": jd, "goal": goal}

    for step in plan.steps:
        # Run subagent
        subagent = registry[step.id]
        result = await subagent.run(inputs=cache, emit=stream_callback)
        cache[step.id] = result
        emit("step_done", {step_id: step.id, result})

        # Pipeline continues immediately — no wait
        # User can intercept at any time via POST /api/intercept
        # Intercept re-runs that specific subagent with feedback context

    emit("all_done", {results: cache})
```

### Planning

Planning is a lightweight LLM call. The coordinator reads the entire subagent registry and decides which subagents are relevant to the user's goal.

```
System prompt:
  "You are a resume analysis coordinator. Available subagents:
   {registry descriptions}
   Given the user's resume, JD, and goal, select subagents to run and order them.
   Only include subagents that are relevant."

Output:
  { steps: [{id, name, deps}], reasoning: "..." }
```

## 4. Agent Runtime Hooks

A lifecycle hook system that allows external logic to inject behavior at key points in the agent runtime without modifying Coordinator code.

### Hook Points

```
Agent Runtime Lifecycle
────────────────────────────────────────────────────────
收到用户请求 ──────────────────────── 不需要（入口，非扩展点）

Coordinator 规划完成 ─────────────── ① on_plan_generated
          │
开始跑 subagent ──────────────────── ② pre_subagent
    │
    ← subagent.run()
    │
subagent 跑完 ────────────────────── ③ post_subagent
          │
用户 intercept ───────────────────── ④ on_intercept
          │
全部完成 ─────────────────────────── ⑤ on_all_done
          │
任一步出错 ───────────────────────── ⑥ on_error
```

### Hook Registry

```python
HOOKS: dict[str, list[Callable]] = {
    "on_plan_generated": [],
    "pre_subagent": [],
    "post_subagent": [],
    "on_intercept": [],
    "on_all_done": [],
    "on_error": [],
}
```

### Hook Signatures

```python
on_plan_generated(plan, ctx)    → plan  (可修改，用于注入额外步骤)
pre_subagent(step, inputs, ctx)  → inputs (可修改，如注入 user preferences)
post_subagent(step, result, ctx) → result (可修改，如保存到数据库)
on_intercept(step_id, feedback, ctx)
on_all_done(results, ctx)
on_error(step_id, error, ctx)
```

### Usage Examples

```python
# 保存分析记录到数据库（C 端刚需）
HOOKS["post_subagent"].append(
    lambda step, result, ctx:
        db.save_analysis(ctx.user_id, step.id, result)
)

# 用用户历史偏好调整 subagent 输入
HOOKS["pre_subagent"].append(
    lambda step, inputs, ctx:
        {**inputs, "style_prefs": memory.load(ctx.user_id)}
)

# 出错时自动降级重试
HOOKS["on_error"].append(
    lambda step_id, error, ctx:
        log.warning(f"{step_id} failed: {error[:100]}")
        if step_id != "rewrite":
            ctx.retry_with_fallback(step_id)
)

# 分析完成推通知
HOOKS["on_all_done"].append(
    lambda results, ctx:
        push_notification(ctx.user_id, "简历分析完成！")
)
```

### Coordinator Loop with Hooks

```
function run_agent(resume, jd, goal):
    plan = coordinator_plan(...)
    plan = HOOKS["on_plan_generated"].fire(plan) or plan  # hook
    emit("plan", plan)

    for step in plan.steps:
        inputs = HOOKS["pre_subagent"].fire(step, cache) or cache  # hook
        result = await subagent.run(inputs=inputs, emit=stream_callback)
        result = HOOKS["post_subagent"].fire(step, result, ctx) or result  # hook
        cache[step.id] = result
        emit("step_done", ...)

    HOOKS["on_all_done"].fire(cache, ctx)  # hook
    emit("all_done", ...)
```

### Design Decisions

| Not a hook | Reason |
| ---------- | ------ |
| `on_subagent_tool_call` | Subagent 内部细节，hook 会打破 context isolation |
| `on_every_chunk` | SSE 已给前端，后端不需要多一层 |
| `on_memory_loaded` | Memory 是框架内部机制 |

## 5. Subagent System

### Subagent Definition

Each subagent is a self-contained unit with:

```python
class SubagentDef:
    id: str                          # "gap_analysis"
    name: str                        # "差距分析"
    description: str                 # "逐项对比简历与JD要求"
    icon: str                        # "📊"
    inputs: list[str]                # required keys from cache
    needed_skills: list[str]         # skill files to inject, optional
    tool_definitions: list[ToolDef]  # tools available to this subagent

    async def run(
        self,
        inputs: dict,
        emit: StreamCallback,
    ) -> dict:
        ...
```

### Initial Subagents

| Subagent | Inputs | Description |
|----------|--------|-------------|
| `gap_analysis` | resume_text, jd_text | Match/missing/repackagable analysis |
| `assessment` | resume_text, jd_text, gap_analysis | Scoring + interview chances |
| `remediation` | resume_text, jd_text, gap_analysis | Learning roadmap |
| `rewrite` | resume_text, jd_text, gap_analysis, assessment | Narrative rewrite |
| `company_analysis` | jd_text | Company health, team, products |

### Subagent Run Method

Each subagent runs an independent agent loop (s04) with its own `messages[]` list and tool set. This prevents context contamination between analysis types.

```python
async def run(self, inputs, emit):
    messages = [
        {"role": "user", "content": self.build_prompt(inputs)}
    ]

    while True:
        response = await client.messages.create(
            model=...,
            system=self.system_prompt + self.load_skills(inputs),
            messages=messages,
            tools=self.tool_definitions,
        )
        messages.append(response)

        if response.stop_reason != "tool_use":
            break

        for block in response.content:
            if block.type == "tool_use":
                result = await execute_tool(block.name, block.input)
                messages.append({"role": "user", "content": tool_result(block.id, result)})

    return {"text": extract_text(response), "thinking": extract_thinking(response)}
```

### Intercept / Re-run

When the user sends feedback on a completed step:

```
POST /api/intercept
  Body: { run_id, step_id, feedback: "..." }
  Response: SSE stream (same event format)

Coordinator:
  1. Load cached result from .tasks/{run_id}/{step_id}/
  2. Re-run subagent with cache + feedback injected as context
  3. Cache new result
  4. Stream updated result to frontend
  5. DO NOT re-run downstream steps (user can trigger manually if needed)
```

The re-run includes the previous result in the subagent's context so it knows what it's revising:

```python
# Injected into subagent system prompt on re-run:
f"""
用户反馈（针对上次结果）：
{feedback}

上次结果（供参考）：
{previous_result}

请基于反馈重新分析。
"""
```

## 5. SSE Event Protocol

Single SSE connection for the entire agent run.

### Events

```
event: plan
data: {
  "type": "plan",
  "run_id": "abc123",
  "steps": [
    {"id": "gap_analysis", "name": "差距分析", "icon": "📊",
     "status": "pending", "deps": []},
    {"id": "assessment", "name": "匹配评估", "icon": "🎯",
     "status": "pending", "deps": ["gap_analysis"]},
  ]
}

event: step_start
data: {"type": "step_start", "run_id": "...", "step_id": "gap_analysis"}

event: step_output
data: {"type": "step_output", "run_id": "...", "step_id": "gap_analysis",
       "text": "...", "thinking": "...", "done": false}

event: step_done
data: {"type": "step_done", "run_id": "...", "step_id": "gap_analysis",
       "text": "...", "thinking": "...", "truncated": false,
       "duration_ms": 2300}

event: step_revised
data: {"type": "step_revised", "run_id": "...", "step_id": "gap_analysis",
       "text": "...", "thinking": "...",
       "feedback": "用户补充了系统设计经验"}

event: all_done
data: {"type": "all_done", "run_id": "...",
       "results": {"gap_analysis": ..., "assessment": ...}}

event: error
data: {"type": "error", "run_id": "...", "step_id": "gap_analysis",
       "error": "..."}
```

## 6. Skills System (s05)

Skills inject specialized knowledge into subagent system prompts. They are loaded on-demand (tool_result injection pattern from s05), not prepended to every call.

```
skills/
  gap_analysis/
    SKILL.md             — "如何逐项对比JD与简历：分类标准、标记方法..."
  assessment/
    SKILL.md             — "评分标准说明：ATS匹配、第一印象..."
  company_analysis/
    SKILL.md             — "公司分析方法论：业务健康度、融资阶段..."
  rewrite/
    SKILL.md             — "叙事重构框架：背景-问题-方案-影响"
```

When a subagent is spawned, the Coordinator checks `needed_skills` and loads the corresponding skill files into the subagent's system prompt.

## 7. Tool System (s02)

Tools available to subagents. Each subagent declares which tools it can use.

| Tool | Description | Used By |
|------|-------------|---------|
| `read_resume` | Read resume from cache | All |
| `read_jd` | Read JD from cache | All |
| `search_keyword` | Extract keyword analysis | gap_analysis |
| `compile_latex` | Compile LaTeX snippet | rewrite |
| `web_search` | Search web for info | company_analysis, deep_search |

### Tool Execution

Deterministic tools (`read_resume`, `read_jd`, `compile_latex`): synchronous, no LLM needed.
Non-deterministic tools (`web_search`): calls external API, returns result as tool_result content.

## 8. Task System (s07)

Every agent run creates a persistent task directory.

```
.tasks/{run_id}/
  plan.json            ← execution plan
  status.json          ← current status of each step
  gap_analysis/
    input.json         ← inputs used
    result.json        ← final result
    thinking.md        ← thinking chain (if available)
  assessment/
    ...
```

### Purpose

- **Recovery**: User closes tab, comes back → `GET /api/agent/{run_id}` restores full state
- **Inspect**: User can revisit previous analysis results across sessions
- **Retry**: Failed subagent can be re-run without restarting entire plan

## 9. Context Compression (s06)

When the user engages in multi-turn conversation after results (e.g., "rewrite this section differently", "analyze another company"), the message list grows. Three-layer compression:

1. **Summarize oldest messages** — truncate thinking chains
2. **Retain recent verbatim** — last N turns preserved exactly
3. **Drop tool call internals** — tool results too large → summarize

Triggered when message list exceeds a threshold (e.g., 50 messages or 80k tokens).

## 10. Background Tasks (s08)

Long-running operations (web search, deep research) can be delegated to background threads.

```
Subagent calls web_search tool
  → Coordinator sees search will take > 5s
  → Spawns background task, emits "running_background" event
  → Agent loop continues (or pauses if blocked on this result)
  → Background completes → result injected back → agent resumes
```

Used initially for `company_analysis` web search. Future: multi-JD batch analysis.

## 11. Memory (cross-session)

Persistent memory stored in `memory/` directory:

```
memory/
  user_profile.md         — extracted from conversations over time
  analysis_history.json   — previous run summaries
```

### Data Sources

| Data | Source | Storage |
|------|--------|---------|
| User background | User fills in on first use, or extracted from resume | `user_profile.md` |
| Style preferences | Implicit: user's feedback on rewrites | `user_profile.md` |
| Recent analyses | Saved from each agent run | `.tasks/{run_id}/` indexed in memory |

### Loading

On agent startup, the Coordinator checks for memory and injects relevant context:

```
System prompt addition:
  "当前用户：xxx
  偏好说明：
  - 偏重量化结果描述
  - 希望保持中文为主 + 英文技术关键词
  上次分析（2026-05-10）：字节跳动 AI Agent 岗位，差距分析已完成"
```

## 12. Frontend Interaction

### Component Architecture

```
Main Page
├── Header
│   ├── Model Selector (last used default)
│   ├── File Upload (existing)
│   └── Theme Toggle
│
├── Input Section (existing)
│   ├── Resume (upload or paste)
│   └── JD (paste)
│
├── Goal Input (new)
│   └── "你的求职目标是什么？" text input
│
├── Plan Timeline (new — replaces manual "run" cards)
│   ├── Plan View: step list with status/icon/duration
│   ├── Execution: live streaming per step
│   └── Intercept: feedback text box per completed step
│
├── Result Panels (modified)
│   ├── Tab bar per completed analysis
│   └── Markdown renderer (existing)
│
└── Editor Drawer (existing)
    └── Monaco LaTeX editor
```

### Plan Timeline Component

```
┌──────────────────────────────────────────────┐
│  开始分析 → 正在规划...                        │  ← initial click
├──────────────────────────────────────────────┤
│  📋 执行计划                                  │  ← plan event received
│                                             │
│  ① 📊 差距分析                    0.3s  ✓   │  ← step_done
│  ② 🎯 匹配评估                    正在运行 ⟳  │
│  ③ 🏢 公司尽调                   准备中 ⏳    │
│  ④ 📋 补足路线                   准备中 ⏳    │
│  ⑤ ✏️ 简历改写                   准备中 ⏳    │
│                                             │
│  ── 对这个结果有补充吗？ ──                   │  ← intercept area
│  [其实我做过系统设计，但简历上没写] [发送]      │     under each done step
└──────────────────────────────────────────────┘
```

### Intercept UX

Every completed step shows an input field:

```
┌─ 差距分析 ✓ ───────────────────────────────┐
│  ...results...                              │
│                                            │
│  ─────────────────────────────────────     │
│  > 对这个结果有补充吗？           [发送]     │
│                                            │
│  ② 匹配评估  [⟳ 正在运行...]               │
└────────────────────────────────────────────┘
```

On submit:
1. Emit `POST /api/intercept` with `{run_id, step_id, feedback}`
2. Step status changes to "重新分析中 ⟳"
3. New results stream in
4. Original results are replaced, not appended

The running pipeline is unaffected — only the intercepted step's output changes.

### Completion Notification (Browser)

When all steps complete and the user is on another tab, notify via browser Notification API.

```
SSE event: all_done  →  前端收到
                          ├── 页面在前台 → 已有 UI 状态
                          └── 页面在后台 → 弹系统通知
```

Implementation:

```typescript
// SSE event listener
sse.addEventListener("all_done", (event) => {
  const result = JSON.parse(event.data);

  if (document.hidden) {
    if (!("Notification" in window)) return;

    if (Notification.permission === "granted") {
      new Notification("简历分析完成", {
        body: `已完成 ${result.steps} 项分析`,
        icon: "/favicon.png",
      });
    } else if (Notification.permission !== "denied") {
      // 只在用户主动触发操作时请求权限
      Notification.requestPermission();
    }
  }
});
```

Permission request timing: on first "开始分析" click (user expects a notification might come), not on page load.

## 14. User Flow

```
1. 打开页面
2. 上传简历 / 粘贴 LaTeX
3. 粘贴 JD
4. (可选) 填写求职目标
5. 点击"开始分析"

   系统：
   ├── Coordinator 规划 → 前端展示 plan
   ├── 逐个执行 subagent → 前端实时显示
   │
   用户随时：
   ├── 对已完步骤追加反馈 → 自动重跑该步
   ├── 查看结果 → 继续对话追问
   ├── 切换到编辑器改简历 → 重新分析
   │
6. 全部完成
7. (可选) 保存、下次再来 → Memory 记住上下文
```

## 15. Project Structure

```
resume-editor-agent/
├── backend/
│   ├── main.py                 # FastAPI entry, routing
│   ├── coordinator.py          # Agent loop
│   ├── subagent.py             # Subagent base class + registry
│   ├── subagents/              # Subagent implementations
│   │   ├── gap_analysis.py
│   │   ├── assessment.py
│   │   ├── remediation.py
│   │   ├── rewrite.py
│   │   └── company_analysis.py
│   ├── tools/                  # Shared tools
│   │   ├── __init__.py
│   │   ├── latex.py            # compile_latex
│   │   ├── search.py           # web_search
│   │   └── resume.py           # read_resume, read_jd
│   ├── skills/                 # Skill files (s05)
│   │   ├── gap_analysis/SKILL.md
│   │   ├── assessment/SKILL.md
│   │   ├── remediation/SKILL.md
│   │   ├── rewrite/SKILL.md
│   │   └── company_analysis/SKILL.md
│   ├── memory/                 # Cross-session memory
│   ├── tasks/                  # Task persistence (s07)
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── app/page.tsx        # Modified with new flow
│   │   ├── components/
│   │   │   ├── PlanTimeline.tsx    # NEW
│   │   │   ├── InterceptInput.tsx  # NEW
│   │   │   ├── GoalInput.tsx       # NEW
│   │   │   ├── Editor.tsx          # EXISTING
│   │   │   ├── Preview.tsx         # EXISTING
│   │   │   └── ... (other existing components)
│   │   └── lib/
│   │       ├── api.ts              # Modified: SSE agent API
│   │       └── utils.ts            # EXISTING
│   └── ...
│
└── design/
    └── 2026-05-14-agent-architecture-design.md
```

## 16. Implementation Order

| Phase | What | Why first |
|-------|------|-----------|
| **1** | Backend: Subagent base class + registry + first subagent (gap_analysis) | Core abstraction, validate the pattern |
| **2** | Backend: Coordinator agent loop + SSE protocol | Get the flow working |
| **3** | Backend: Intercept endpoint | The key UX differentiator |
| **4** | Frontend: PlanTimeline + SSE connection + InterceptInput | User can see and use the new flow |
| **5** | Backend: Port remaining subagents (assessment, remediation, rewrite) | Fill out capabilities |
| **6** | Backend: Skills system | Knowledge injection |
| **7** | Backend: Task persistence (s07) | Reliability |
| **8** | Backend: Memory (cross-session) | Personalization |
| **9** | Frontend: Goal input + result conversation | Multi-turn interaction |
| **10** | Backend: Company analysis subagent + web_search tool | Demonstrate extensibility |
| **11** | Context compression (s06) + background tasks (s08) | Production hardening |
