---
name: tech-post-writer
description: |
  Write inspiring, engaging technical posts for Xiaohongshu and similar platforms.
  Use when users ask to "write a post", "create content", "发帖子", "写文章",
  or after a deep technical discussion when insights are worth sharing.
  Also triggers when the user wants to distill a complex technical topic into
  an accessible, thought-provoking piece.
---

# Tech Post Writer

Turn technical insights into posts that make readers think "I never saw it that way."

## The Core Philosophy

Most technical posts fail because they explain WHAT. Great posts succeed because they reshape HOW the reader thinks.

**From**: Here's how X works.
**To**: You thought X was Y. It's actually Z. Here's the proof.

This skill is not a content template. It's a *thinking methodology* — a set of angles you apply to your technical knowledge before you write a single word.

---

## Phase 0: Judge Before You Critique

When discussing a system's design, there's a trap: you spot a limitation and immediately treat it as a flaw. But in teaching code especially, many "limitations" are **intentional simplifications** — removing them would obscure the core insight, not improve the system.

Before applying Angle 6 or Angle 7, run through this judgment:

### The Intent Test

```
Is this teaching/demo code?
├─ YES → The simplification is likely intentional
│        Ask: "What concept would be buried if this were production-grade?"
│        Write about: the design PHILOSOPHY behind the simplification
│        Don't: treat it as a bug
│
└─ NO  → This is production code meant to handle real load
         Ask: "What breaks first under stress?"
         Write about: concrete failure modes and fixes
```

### The Mechanism-vs-Policy Test

Some designs are "mechanism-only" — they provide tools but no enforcement. This is a choice, not a gap.

```
Example: s10's plan_approval protocol
├─ Mechanism (provided): request_id tracking, inbox delivery, FSM states
├─ Policy (NOT provided): no hard block on unapproved tool execution
│
├─ AS a bug: "Teammate can skip approval and run bash directly"
└─ AS a philosophy: "Harness provides mechanism. Model decides policy. That's the point."
```

**Rule**: If the mechanism is present but enforcement is absent, ask "was enforcement intentionally left to the model?" before calling it a gap.

### The Insight Threshold

Some critiques are factually correct but insight-poor. They don't belong in a post:

| Critique | Insight Value | Verdict |
|----------|-------------|---------|
| "JSONL has no ACK, messages could be lost" | HIGH — teaches at-least-once semantics vs at-most-once | WRITE |
| "Should use Redis instead of JSONL" | LOW — just swaps one tool for another | SKIP |
| "daemon=True, process exit kills teammate" | HIGH — reveals the thread lifecycle assumption | WRITE |
| "range(50) is hardcoded, should be configurable" | LOW — trivial fix, no design insight | SKIP |

**Rule**: If the "fix" is a one-line change, it's probably not insight-rich enough. If the fix requires rethinking a design assumption, it's worth writing about.

---

## Phase 1: Mine the Insight (8 Thinking Angles)

Before writing, run your topic through these angles. Not every angle applies to every post. Pick 3-5 that hit hardest.

### Angle 1: Counter-Intuition Hook

**Trigger**: You feel "wait, that's not how I thought it worked."

**What it does**: Finds the gap between what readers assume and what's true.

| Weak Hook | Strong Hook |
|-----------|-------------|
| "How Agent Teams work" | "Lead and Teammate don't need two loops — they need one loop and different config" |
| "What is Agent Harness" | "90% of Harness mechanisms existed before 1990" |

**How to find it**: Ask yourself "What did I believe before I learned this? What surprised me?"

---

### Angle 2: Framework Triangulation

**Trigger**: You ask "Do mature frameworks do this too?"

**What it does**: Validates your insight by showing 2-3 independent projects converged on the same pattern.

**Structure**:
```
My finding → Framework A does it this way (purest)
          → Framework B does it this way (most complete)
          → Framework C does it this way (most opinionated)
Conclusion → They're all converging on the same design principle
```

**Why it works**: Personal insight + independent verification = credibility.

---

### Angle 3: Yardstick Thinking

**Trigger**: You mentally map a new concept onto a framework you already know.

**What it does**: Gives readers a reusable judgment tool, not just information.

**Instead of**: "Framework X is good at multi-agent."
**Write**: "Framework X covers s02/s04/s07, but its multi-agent is s04 subagent, not s09 teammate. Here's how to tell."

**How to find it**: What's the checklist or framework YOU use to evaluate this topic? Externalize it.

---

### Angle 4: Old → New Mapping

**Trigger**: You feel "this 'new' concept reminds me of something from CS history."

**What it does**: Maps novel concepts onto things readers already understand.

```
s06 microcompact  =  logrotate (Unix, 1970s)
s09 JSONL inbox   =  Erlang mailbox (1986)
s10 request_id    =  TCP seq number (1981)
s11 idle loop     =  cron + work stealing
```

**Why it works**: Understanding cost drops to zero. Reader goes "oh, THAT's all it is."

**How to find it**: For each "new" mechanism, ask "What did we use to solve this same structural problem before LLMs?"

---

### Angle 5: Binary Distinction

**Trigger**: You catch yourself or others conflating two things.

**What it does**: Creates clarity through a single dividing line.

| Conflated | Distinction |
|-----------|-------------|
| "Multi-agent" | Subagent (spawn → work → die) vs Teammate (spawn → work → idle → work → ...) |
| "Permission" | Static allow/deny vs Dynamic condition-based |
| "Context compression" | Stateless (logrotate) vs Stateful (vector memory) |

**How to find it**: What two things are people treating as the same thing? What's the one question that separates them?

---

### Angle 6: Production Lens Critique

**Trigger**: You've understood a mechanism and now ask "What would actually break if I deployed this tomorrow?"

**What it does**: Systematically pressure-tests a design through 5 lenses. Each lens asks a different question about the same code.

**Before you start**: Run Phase 0. Teaching code has intentional gaps. Treat them as design philosophy, not bugs.

#### The 5 Lenses

Apply these in order. Not every lens applies to every topic — pick the ones that reveal insight.

**Lens 1: Threading & Concurrency**
```
Question:  "What happens when multiple things happen at the same time?"
Check:     Daemon flags, thread pools, blocking I/O, share-nothing vs share-something
Example:   s10 — teammate does synchronous API call, can't read new inbox messages
           while waiting. Design says: "polling is simple; push would need event loop"
Insight:   Single-threaded = simplest mental model, worst throughput.
           The tension IS the insight.
```

**Lens 2: Message Bus & Transport**
```
Question:  "Can messages be lost, duplicated, or corrupted?"
Check:     ACK mechanism, at-least-once vs at-most-once, file locks, crash recovery
Example:   s10 — JSONL read-then-clear: crash between read and clear = messages lost.
           No ACK, no offset tracking.
Insight:   "Read and drain" is a teaching pattern. Production needs at-least-once delivery
           with explicit commit after successful processing.
```

**Lens 3: Protocol Enforcement**
```
Question:  "Is the protocol a suggestion or a constraint?"
Check:     Hard blocks vs system prompt suggestions, timeout-enforced vs voluntary compliance
Example:   s10 — plan_approval is a tool the model CAN call, not a gate it MUST pass.
           Teammate can call bash() without ever submitting a plan.
Insight:   "Harness provides mechanism, model decides policy." This is a PHILOSOPHY,
           not a bug. Production might add enforcement; the insight is understanding WHY
           teaching code leaves it out.
```

**Lens 4: Error Handling & Resilience**
```
Question:  "What happens when something fails silently?"
Check:     Try/except scopes, retry logic, error states, alerting
Example:   s10 — API call exception → break (exit loop, no retry, no alert).
           Tool error → returned to model as string, loop continues.
Insight:   Teaching code treats errors as terminal. Production needs: retry with backoff,
           dead-letter queues, teammate status = "error" (not just idle/shutdown).
```

**Lens 5: State & Persistence**
```
Question:  "Process restart → what's lost?"
Check:     In-memory vs on-disk, atomic writes, migration paths
Example:   s10 — shutdown_requests and plan_requests are global dicts in memory.
           Process dies → all pending requests gone.
Insight:   The mechanism (request_id correlation, FSM states) is correct. The implementation
           (in-memory dict) is sufficient for a single run. Production adds durability.
```

#### Putting It Together: The Critique Paragraph

```
Teaching version does X → specific scenario breaks it → but the DESIGN is correct
→ here's what production would add → here's WHY the teaching version is simpler
```

**Why it works**: Readers see a critique that's both honest and fair — it acknowledges limits without dismissing the design. This builds credibility more than either pure praise or pure criticism.

**How to find it**: Read the code with one lens at a time. For each lens, ask "What assumption does this make? What happens when that assumption breaks?"

---

### Angle 7: Teaching → Production Upgrade Path

**Trigger**: You think "ok I get the basic mechanism, but how do you optimize it for production?"

**What it does**: Goes from "how it works" to "what changes at each priority level." The key insight: **not everything needs upgrading at once**. Some changes are existential, others are cosmetic.

#### The P0-P3 Framework

```
P0 = Teaching version would FAIL in production (data loss, zombie processes, silent crashes)
P1 = Teaching version would be FRAGILE in production (no enforcement, no retry)
P2 = Teaching version would be ANNOYING in production (same names, different meanings)
P3 = Teaching version would be BLIND in production (no logging, no tracing)
```

#### Example: s10 Team Protocols

```
P0 | Message bus: at-least-once + file lock
   | WHY: JSONL read-then-clear crashes → messages permanently lost
   | COST: Replace simple file I/O with commit-offset tracking
   |
P0 | Thread lifecycle: non-daemon + force-kill timeout
   | WHY: daemon=True + no timeout → teammate can become a zombie
   | COST: Add join(timeout=N), os._exit() as last resort
   |
P1 | Protocol enforcement: tool execution gate
   | WHY: plan_approval is a suggestion, not a constraint
   | COST: Add has_approved_plan() check before write/bash tools
   | NOTE: This changes the philosophy from "model decides" to "harness enforces"
   |
P1 | Error handling: retry + alert
   | WHY: API exceptions silently kill the teammate loop
   | COST: Exponential backoff, dead-letter for unrecoverable errors
   |
P2 | Tool name disambiguation
   | WHY: shutdown_response means "check status" for Lead but "respond" for Teammate
   | COST: Split into shutdown_request_status and shutdown_respond
   |
P2 | State persistence
   | WHY: Tracker dicts in memory, restart = all pending requests lost
   | COST: SQLite or atomic JSON writes
   |
P3 | Structured logging + tracing
   | WHY: Single print() statement, no token tracking, no latency metrics
   | COST: OpenTelemetry, structured log format, per-request trace IDs
```

#### The Pattern

```
Layer 1: teaching version — the mechanism, stripped to its essence
Layer 2: P0 hardening — what MUST change before any real use
Layer 3: P1-P2 hardening — what SHOULD change for robustness
Layer 4: P3 observability — what you add when you have traffic
```

**Why it works**: Readers get a prioritized roadmap, not a vague "make it better." They can see which upgrades are existential and which are nice-to-have. The P0-P3 frame also clarifies WHY the teaching version is simpler — because all that hardening would bury the core mechanism.

**How to find it**: For each component, ask "If this failed right now, would the system notice? Would it recover?" P0 = no notice + no recovery. P1 = notices but can't recover. P2 = recovers but confusingly. P3 = recovers but invisibly.

---

### Angle 8: Personal Project Anchor

**Trigger**: You think "I could use this mechanism in my own project X."

**What it does**: Grounds abstract concepts in personal application.

```
What I learned: s07 Task System (JSON persistence + blockedBy dependency graph)
My project: Job application tracker
Concrete use: Each application is a task. "Interview prep" blockedBy "Resume tailored"
```

**Why it works**: It answers the reader's unspoken question: "Why should I care?"

---

## Phase 2: Structure the Post

Once you've picked your angles (3-5 for a typical post), arrange them:

### Post Anatomy

```
[Title]         ←  Angle 1 (Counter-Intuition Hook) expressed in one line

[Opening]       ←  2-3 sentences grounding the reader in something concrete
                   (a code snippet, a session number, a debugging moment)

[Core Insight]  ←  Angles 4+5 (Old→New Mapping + Binary Distinction)
                   Lay out the mental model shift

[Verification]  ←  Angle 2 (Framework Triangulation)
                   Show 2-3 frameworks proving the pattern is real

[Deepen]        ←  Angles 6+7 (Production Lens Critique + Teaching→Production Path)
                   Push beyond the surface

[Anchor]        ←  Angle 8 (Personal Project)
                   Bring it home

[Takeaway]      ←  3 lines max, one layer each:
                   Practice → Judgment → Cognition
```

### Section Rhythm

Each section follows the same rhythm:
1. State the insight in one bold sentence
2. Show the evidence (code / framework example / scenario)
3. One sentence of interpretation

Keep sections to 3-5 short paragraphs. If a section runs longer, it's two sections.

---

## Phase 3: Platform Adaptation

### Step 1: Choose Output Mode

Not all posts work as native text. Choose based on code density:

```
Post contains code?
├─ 0-1 short snippets → Mode A: NATIVE TEXT
│   Deliver ready-to-paste plain text
│
└─ 2+ code blocks / tables / diagrams → Mode B: MARKDOWN → IMAGE
    Deliver .md master file + tool recommendation
```

### Step 2: Mode A — Native Text

Xiaohongshu does NOT support Markdown. Raw `##`, ` ``` `, and `|table|` render as plain text.

**Rules**:
- *Use \*bold\* for emphasis* (Xiaohongshu native)
- No `##` headers → use emoji + bold sentence as section markers
- No ` ``` ` code blocks → convert to prose description. If essential, render as image
- No tables → use short bullet lists or `key: value` pairs
- Double line breaks for visual separation (NOT `---`)
- Each paragraph ≤ 3 lines on mobile

**Code handling**: If a code snippet is essential, render it as an image (Carbon.sh / Ray.so). Otherwise, describe it in prose with key identifiers in \*bold\*.

### Step 3: Mode B — Markdown → Image Pipeline

Write a clean .md file (tables, code blocks, headers all fine), then recommend one of:

| Tool | Platform | Best For |
| --- | --- | --- |
| **xiaohongshu-text-layout** | Web (跨平台) | 自定义背景、批量导出 |
| **文颜** | Web (跨平台) | 多平台适配、LaTeX、本地处理 |
| **Carbon.sh / Ray.so** | Web (跨平台) | 单段代码截图 |
| **RedBookCards** | ⚠️ Windows only | 12 themes, GUI |

> macOS 优先用前两个。RedBookCards 只发 .exe。

See `references/platform-formats.md` for full details and theme selection guide.

### Content Rhythm (Both Modes)

A Xiaohongshu post should have:
- Section marker (emoji + bold label) every 5-8 paragraphs
- At least one \*bold insight\* per section
- At least one "counter-intuition moment" (Angle 1) in the first scroll
- Hashtags at the end: 4-6 tags mixing broad (#AIAgent) and niche (#ClaudeCode)
- Image ratio: 3:4 (1080×1440px) if posting image cards

---

## Quality Checklist

Before delivering:

```
☐ Phase 0 passed: critique is insight-rich, not nitpicking
☐ Teaching simplifications are framed as design philosophy, not bugs
☐ Hook is counter-intuitive, not descriptive
☐ At least 2 external frameworks validate the core insight
☐ At least 1 Old→New mapping (e.g., "this is just X from 1970s")
☐ At least 1 Binary Distinction (e.g., "X is really two different things")
☐ At least 1 lens from Angle 6 applied (if critique is part of the post)
☐ Production upgrades are P0-P3 prioritized, not a flat list (Angle 7)
☐ Code presented as prose or screenshots, NOT markdown code blocks
☐ Every section has a *bold insight sentence*
☐ Personal project anchor in either the opening or closing
☐ Takeaway is 3 lines: practice → judgment → cognition
☐ Hashtags: 4-6 tags
```

---

## Anti-Patterns

| Pattern | Why It Fails | Fix |
|---------|-------------|-----|
| Title describes the topic | No hook, no click | Title = your Angle 1 in one line |
| Opening with a definition | Boring, no anchor | Open with a code snippet, session number, or debugging moment |
| Feature comparison table | Readers don't remember grids | Replace with one specific scenario that breaks on each framework |
| "In the future, X will..." | Vague and unverifiable | Replace with "Learning path: A → B → C" |
| Teaching what, not how-to-think | Information without transformation | Every section must shift a mental model |
| Markdown in Xiaohongshu | Renders as raw text, ugly | No `##`, no ` ``` `, no `\|table\|`. Only \*bold\* + emoji |

---

## Example: A Complete Post Flow

**Topic**: Agent Teams loop design

**Angles selected**: 1 (Hook), 2 (Triangulation), 3 (Yardstick), 5 (Binary Distinction)

**Post structure**:
```
Opening: "s09 has lead and teammate running two different loops..."
Hook: "You only need ONE loop. The difference is config, not code."
4 config dimensions: tools, permission, system_prompt, inbox_name
Framework triangulation: OpenAI SDK / Claude SDK / CrewAI — all do "same loop, different config"
Binary distinction: Subagent (s04, use-and-discard) vs Teammate (s09, long-lived + inbox)
Takeaway: Loop writes once. Agent is config, not code. 12 Sessions are your yardstick.
```

---

## Resources

- `references/8-angles-cheatsheet.md` — Quick reference card for the 8 thinking angles
- `references/platform-formats.md` — Formatting rules for Xiaohongshu, WeChat, Zhihu
- `references/design-critique-framework.md` — Systematic design critique methodology (Phase 0 + 5 Lenses + P0-P3)
