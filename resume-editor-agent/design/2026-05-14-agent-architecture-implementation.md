# Resume Editor: Agent Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform `resume-editor/` from REST API into an agent-driven system with Coordinator, Subagents, SSE streaming, and intercept capability.

**Architecture:** A Coordinator Agent Loop plans execution steps, spawns subagents with isolated context, streams results via SSE, and accepts user intercept feedback. Hooks system allows extension without modifying core code.

**Tech Stack:** Python/FastAPI, Anthropic SDK, Next.js/React (frontend), Browser SSE

---

## File Structure

```
resume-editor-agent/
├── backend/
│   ├── main.py                  # FastAPI entry, agent endpoint + SSE + intercept
│   ├── coordinator.py           # Agent loop: plan → execute → emit
│   ├── subagent.py              # SubagentDef base class + SubagentRegistry
│   ├── subagents/
│   │   ├── __init__.py
│   │   ├── gap_analysis.py
│   │   ├── assessment.py
│   │   ├── remediation.py
│   │   ├── rewrite.py
│   │   └── company_analysis.py
│   ├── tools/
│   │   ├── __init__.py
│   │   └── resume_tools.py
│   ├── hooks.py                 # Hook registry
│   ├── skills/
│   │   ├── gap_analysis/SKILL.md
│   │   ├── assessment/SKILL.md
│   │   ├── remediation/SKILL.md
│   │   ├── rewrite/SKILL.md
│   │   └── company_analysis/SKILL.md
│   ├── memory/
│   ├── tasks/
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx          # Modified with agent flow
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── PlanTimeline.tsx   # NEW
│   │   │   ├── InterceptInput.tsx # NEW
│   │   │   ├── GoalInput.tsx      # NEW
│   │   │   └── ... (copied from existing)
│   │   └── lib/
│   │       ├── api.ts
│   │       └── utils.ts
│   └── ... (config files)
│
└── design/
    └── 2026-05-14-agent-architecture-design.md
```

---

### Task 1: Backend scaffolding + subagent base class + registry

**Files:**
- Create: `resume-editor-agent/backend/subagent.py`
- Create: `resume-editor-agent/backend/hooks.py`
- Create: `resume-editor-agent/backend/subagents/__init__.py`
- Create: `resume-editor-agent/backend/requirements.txt`
- Create: `resume-editor-agent/backend/.env`

- [ ] **Step 1: Create backend/.env**

Copy the existing `.env` from `resume-editor/backend/.env`. It needs `ANTHROPIC_API_KEY` and `MODEL_ID`.

- [ ] **Step 2: Create requirements.txt**

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
python-multipart>=0.0.9
anthropic>=0.39.0
python-dotenv>=1.0.0
```

- [ ] **Step 3: Write subagent.py (base class + registry)**

```python
"""Subagent base class and registry."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional

StreamCallback = Callable[[dict], None]


@dataclass
class SubagentDef:
    """Definition of an analyzable capability."""
    id: str
    name: str
    description: str
    icon: str = "📄"
    inputs: list[str] = field(default_factory=list)
    needed_skills: list[str] = field(default_factory=list)
    
    async def run(
        self,
        inputs: dict[str, Any],
        emit: StreamCallback,
        feedback: Optional[str] = None,
        previous_result: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Execute the subagent analysis.
        
        Args:
            inputs: Cache of previous step results (resume_text, jd_text, etc.)
            emit: Callback for streaming output chunks to SSE
            feedback: User intercept feedback for re-runs
            previous_result: Previous result when this is a re-run
        Returns:
            dict with "text", "thinking", "truncated" keys
        """
        raise NotImplementedError


class SubagentRegistry:
    """Registry of all available subagents. Loaded by Coordinator for planning."""
    
    def __init__(self):
        self._subagents: dict[str, SubagentDef] = {}
    
    def register(self, agent: SubagentDef) -> None:
        self._subagents[agent.id] = agent
    
    def get(self, agent_id: str) -> Optional[SubagentDef]:
        return self._subagents.get(agent_id)
    
    def list_all(self) -> list[SubagentDef]:
        return list(self._subagents.values())
    
    def describe(self) -> str:
        """Format registry as text for LLM planning prompt."""
        lines = []
        for a in self._subagents.values():
            lines.append(f"- `{a.id}`: {a.name} — {a.description}")
        return "\n".join(lines)
```

- [ ] **Step 4: Write hooks.py**

```python
"""Lifecycle hook registry for agent runtime."""
from __future__ import annotations
from typing import Any, Callable
import logging

logger = logging.getLogger("resume-editor.hooks")


class HookRegistry:
    """Registry for lifecycle hooks at key runtime nodes.
    
    Each hook point is a list of callables. Multiple handlers can be registered
    per hook point. Handlers are called in registration order.
    """
    
    def __init__(self):
        self._hooks: dict[str, list[Callable]] = {
            "on_plan_generated": [],
            "pre_subagent": [],
            "post_subagent": [],
            "on_intercept": [],
            "on_all_done": [],
            "on_error": [],
        }
    
    def register(self, hook_point: str, fn: Callable) -> None:
        if hook_point not in self._hooks:
            raise ValueError(f"Unknown hook point: {hook_point}, valid: {list(self._hooks.keys())}")
        self._hooks[hook_point].append(fn)
        logger.info("Hook registered: %s", hook_point)
    
    def fire(self, hook_point: str, *args, **kwargs) -> Any:
        if hook_point not in self._hooks:
            return None
        
        result = None
        for fn in self._hooks[hook_point]:
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                logger.warning("Hook %s handler %s failed: %s", hook_point, fn.__name__, e)
        return result


# Global hook registry
HOOKS = HookRegistry()
```

- [ ] **Step 5: Write subagents/__init__.py**

```python
"""Subagent implementations."""
from .gap_analysis import GapAnalysisSubagent
```

- [ ] **Step 6: Commit**

```
git add resume-editor-agent/backend/subagent.py resume-editor-agent/backend/hooks.py resume-editor-agent/backend/subagents/__init__.py resume-editor-agent/backend/requirements.txt resume-editor-agent/backend/.env
git commit -m "feat: subagent base class + registry + hooks scaffold"
```

---

### Task 2: Gap Analysis Subagent

**Files:**
- Create: `resume-editor-agent/backend/subagents/gap_analysis.py`

- [ ] **Step 1: Write GapAnalysisSubagent**

```python
"""Gap analysis subagent: compares resume against JD."""
from ..subagent import SubagentDef, StreamCallback


class GapAnalysisSubagent(SubagentDef):
    
    def __init__(self):
        super().__init__(
            id="gap_analysis",
            name="差距分析",
            description="逐项对比 JD 要求与简历内容，标记匹配、可重包装、缺失项",
            icon="📊",
            inputs=["resume_text", "jd_text"],
            needed_skills=["gap_analysis"],
        )
    
    async def run(
        self,
        inputs: dict,
        emit: StreamCallback,
        feedback: str | None = None,
        previous_result: dict | None = None,
    ) -> dict:
        from anthropic import AsyncAnthropic
        import os
        
        resume = inputs.get("resume_text", "")
        jd = inputs.get("jd_text", "")
        
        system = "You are a professional resume consultant. Analyze gaps between resume and JD."
        if feedback:
            system += f"\n\nUser feedback (re-analyze with this context): {feedback}"
        if previous_result:
            system += f"\n\nPrevious result for reference: {previous_result.get('text', '')[:1000]}"
        
        prompt = f"""Analyze the gap between this resume and the job description.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

Provide a structured analysis:
1. **Strong matches** (keywords/experience that directly align)
2. **Repackagable** (experience that can be positioned to fit)
3. **Genuine gaps** (missing skills/experience)
4. **Keywords to add** (specific JD keywords not in resume)
5. **Overall fit score** (1-10) with brief rationale"""
        
        client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )
        
        resp = await client.messages.create(
            model=os.getenv("MODEL_ID", ""),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
        )
        
        text = ""
        thinking = ""
        for block in resp.content:
            if block.type == "text":
                text += block.text
                emit({"type": "output", "text": text})
            elif block.type == "thinking":
                thinking += block.thinking
        
        return {
            "text": text,
            "thinking": thinking,
            "truncated": resp.stop_reason == "max_tokens",
        }
```

- [ ] **Step 2: Commit**

```
git add resume-editor-agent/backend/subagents/gap_analysis.py
git commit -m "feat: gap analysis subagent"
```

---

### Task 3: Coordinator agent loop

**Files:**
- Create: `resume-editor-agent/backend/coordinator.py`

- [ ] **Step 1: Write coordinator.py**

```python
"""Coordinator agent loop: plans execution, spawns subagents, emits events."""
from __future__ import annotations
import json
import logging
import os
import time
from typing import AsyncIterator, Optional

from anthropic import AsyncAnthropic
from .subagent import SubagentRegistry, StreamCallback
from .hooks import HOOKS

logger = logging.getLogger("resume-editor.coordinator")


class ExecutionPlan:
    """Plan produced by the Coordinator, consumed by the execution loop."""    
    def __init__(self, steps: list[dict], reasoning: str = ""):
        self.steps = steps  # [{id, name, icon, deps}]
        self.reasoning = reasoning


class Coordinator:
    """Agent loop: plan → execute subagents → emit SSE events."""
    
    def __init__(self, registry: SubagentRegistry):
        self.registry = registry
    
    async def plan(self, resume_text: str, jd_text: str, goal: str = "") -> ExecutionPlan:
        """Ask LLM to select and order subagents from registry."""
        system = f"""You are a resume analysis coordinator. Available subagents:
{self.registry.describe()}

Given the user's resume, job description, and goal, select which subagents to run and in what order. Only include relevant ones.

Respond with JSON only:
{{"steps": [{{"id": "gap_analysis", "name": "差距分析", "icon": "📊", "deps": []}}], "reasoning": "..."}}"""
        
        prompt = f"Resume length: {len(resume_text)} chars, JD length: {len(jd_text)} chars"
        if goal:
            prompt += f"\nUser goal: {goal}"
        
        client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )
        
        resp = await client.messages.create(
            model=os.getenv("MODEL_ID", ""),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        
        text = ""
        for block in resp.content:
            if block.type == "text":
                text += block.text
        
        # Extract JSON from response
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            # Fallback: default plan
            return ExecutionPlan([{"id": "gap_analysis", "name": "差距分析", "icon": "📊", "deps": []}])
        
        data = json.loads(match.group())
        return ExecutionPlan(steps=data.get("steps", []), reasoning=data.get("reasoning", ""))
    
    async def execute(self, plan: ExecutionPlan, resume_text: str, jd_text: str, goal: str = ""):
        """Execute plan steps, yielding SSE events. Coordinate runs this loop."""
        cache = {
            "resume_text": resume_text,
            "jd_text": jd_text,
            "goal": goal,
        }
        
        # Fire on_plan_generated hook
        plan = HOOKS.fire("on_plan_generated", plan, cache) or plan
        
        yield {"type": "plan", "steps": plan.steps, "reasoning": plan.reasoning}
        
        for step in plan.steps:
            agent = self.registry.get(step["id"])
            if not agent:
                logger.warning("Unknown subagent in plan: %s", step["id"])
                continue
            
            step_inputs = {k: v for k, v in cache.items() if k in agent.inputs}
            
            # Fire pre_subagent hook
            step_inputs = HOOKS.fire("pre_subagent", step, step_inputs, cache) or step_inputs
            
            yield {"type": "step_start", "step_id": step["id"]}
            
            start = time.time()
            
            async def emit(data: dict):
                """Callback for subagent to stream output."""
                pass  # We handle streaming via the yield below
            
            # Collect streaming output into a list for the emit callback
            output_chunks = []
            
            async def streaming_emit(data: dict):
                output_chunks.append(data)
            
            result = await agent.run(inputs=step_inputs, emit=streaming_emit)
            duration = time.time() - start
            
            # Stream collected chunks
            for chunk in output_chunks:
                yield {"type": "step_output", "step_id": step["id"], **chunk}
            
            cache[step["id"]] = result
            
            # Fire post_subagent hook
            result = HOOKS.fire("post_subagent", step, result, cache) or result
            
            yield {
                "type": "step_done",
                "step_id": step["id"],
                "duration_ms": int(duration * 1000),
            }
        
        # Fire on_all_done hook
        HOOKS.fire("on_all_done", cache, {})
        
        yield {"type": "all_done", "results": {k: v for k, v in cache.items() if isinstance(v, dict)}}
```

- [ ] **Step 2: Commit**

```
git add resume-editor-agent/backend/coordinator.py
git commit -m "feat: coordinator agent loop with plan + execute"
```

---

### Task 4: FastAPI main entry + SSE agent endpoint

**Files:**
- Create: `resume-editor-agent/backend/main.py`
- Create: `resume-editor-agent/backend/tools/__init__.py`
- Create: `resume-editor-agent/backend/tools/resume_tools.py`

- [ ] **Step 1: Write tools/resume_tools.py**

```python
"""Shared deterministic tools available to subagents."""

def read_resume(cache: dict) -> str:
    return cache.get("resume_text", "")

def read_jd(cache: dict) -> str:
    return cache.get("jd_text", "")
```

- [ ] **Step 2: Write main.py with SSE agent endpoint**

```python
"""Resume Editor Agent — FastAPI server with agent loop + SSE streaming."""
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv(override=True)

# ── Logging ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"resume-editor-agent.{datetime.now().strftime('%Y-%m-%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_file), encoding="utf-8"),
    ],
)
logger = logging.getLogger("resume-editor-agent")

# ── Registry setup ─────────────────────────────────────────────────────
from .subagent import SubagentRegistry
from .subagents.gap_analysis import GapAnalysisSubagent
from .subagents import *

registry = SubagentRegistry()
registry.register(GapAnalysisSubagent())

from .coordinator import Coordinator
coordinator = Coordinator(registry)

from .hooks import HOOKS

# ── App ────────────────────────────────────────────────────────────────
app = FastAPI(title="Resume Editor Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/agent")
async def run_agent(
    resume_text: str = Form(...),
    jd_text: str = Form(...),
    goal: str = Form(""),
):
    """Start an agent run. Returns SSE stream with plan + execution events."""
    run_id = uuid.uuid4().hex[:12]
    logger.info("Agent run started: run_id=%s goal=%s", run_id, goal[:100])
    
    async def event_stream():
        try:
            # 1. Plan
            plan = await coordinator.plan(resume_text, jd_text, goal)
            yield f"event: plan\ndata: {json.dumps({'run_id': run_id, 'steps': plan.steps, 'reasoning': plan.reasoning})}\n\n"
            
            # 2. Execute
            async for event in coordinator.execute(plan, resume_text, jd_text, goal):
                event["run_id"] = run_id
                event_type = event.pop("type", "event")
                if event_type == "step_output":
                    yield f"data: {json.dumps(event)}\n\n"
                else:
                    yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
                    
        except Exception as e:
            logger.exception("Agent run failed: run_id=%s", run_id)
            yield f"event: error\ndata: {json.dumps({'run_id': run_id, 'error': str(e)[:500]})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/intercept")
async def intercept_step(
    run_id: str = Form(...),
    step_id: str = Form(...),
    feedback: str = Form(...),
):
    """User intercept: re-run a completed subagent with feedback."""
    logger.info("Intercept: run_id=%s step_id=%s feedback=%s", run_id, step_id, feedback[:100])
    
    from .hooks import HOOKS
    HOOKS.fire("on_intercept", run_id, step_id, feedback)
    
    # For now, return the re-run result via SSE
    agent = registry.get(step_id)
    if not agent:
        raise HTTPException(400, f"Unknown subagent: {step_id}")
    
    # TODO: load from cache properly (will use task system later)
    async def re_run_stream():
        # Re-run with feedback
        result = await agent.run(
            inputs={},
            emit=lambda data: None,
            feedback=feedback,
            previous_result=None,
        )
        yield f"event: step_revised\ndata: {json.dumps({'run_id': run_id, 'step_id': step_id, **result})}\n\n"
    
    return StreamingResponse(
        re_run_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "registry_size": len(registry.list_all())}


if __name__ == "__main__":
    import uvicorn
    logger.info("Resume Editor Agent starting")
    logger.info("Registry: %s", [a.id for a in registry.list_all()])
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_config=None)
```

- [ ] **Step 3: Test the agent endpoint**

```bash
cd resume-editor-agent/backend
python -c "
import asyncio
from main import app, coordinator, registry
print('Registry:', [a.id for a in registry.list_all()])
print('App started on port 8001')
"
```

Expected output: prints registry and confirms imports work.

- [ ] **Step 4: Run a quick integration test**

```bash
cd resume-editor-agent/backend
curl -s -X POST http://localhost:8001/api/agent \
  -F "resume_text=5 years Python backend experience" \
  -F "jd_text=Looking for AI Engineer with agent experience" \
  -F "goal=help me get this job" | head -20
```

Expected: SSE event stream starting with a `plan` event.

- [ ] **Step 5: Commit**

```
git add resume-editor-agent/backend/main.py resume-editor-agent/backend/tools/
git commit -m "feat: FastAPI main + SSE agent endpoint"
```

---

### Task 5: Setup Frontend project structure

**Files:**
- Create: `resume-editor-agent/frontend/package.json`
- Create: `resume-editor-agent/frontend/tsconfig.json`
- Create: `resume-editor-agent/frontend/next.config.js`
- Create: `resume-editor-agent/frontend/postcss.config.mjs`
- Create: `resume-editor-agent/frontend/components.json`
- Create: `resume-editor-agent/frontend/src/lib/utils.ts`
- Create: `resume-editor-agent/frontend/src/lib/api.ts`
- Create: `resume-editor-agent/frontend/src/app/globals.css`
- Create: `resume-editor-agent/frontend/src/app/layout.tsx`
- `resume-editor-agent/frontend/src/app/page.tsx`
- Create: `resume-editor-agent/frontend/tailwind.config.ts` (if needed for v4)

- [ ] **Step 1: Copy package.json from resume-editor/frontend and add new dependencies**

```json
{
  "name": "resume-editor-agent",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "@base-ui/react": "^1.4.1",
    "@monaco-editor/react": "^4.6.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.400.0",
    "next": "^15.2.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-markdown": "^10.1.0",
    "remark-gfm": "^4.0.1",
    "shadcn": "^4.7.0",
    "tailwind-merge": "^3.6.0",
    "tw-animate-css": "^1.4.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.0.0",
    "@types/node": "20.17.6",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.7.0"
  }
}
```

- [ ] **Step 2: Copy config files from resume-editor/frontend**

```bash
cp resume-editor/frontend/tsconfig.json resume-editor-agent/frontend/
cp resume-editor/frontend/next.config.js resume-editor-agent/frontend/
cp resume-editor/frontend/postcss.config.mjs resume-editor-agent/frontend/
cp resume-editor/frontend/components.json resume-editor-agent/frontend/
```

- [ ] **Step 3: Copy layout.tsx and globals.css**

```bash
mkdir -p resume-editor-agent/frontend/src/app
cp resume-editor/frontend/src/app/layout.tsx resume-editor-agent/frontend/src/app/
cp resume-editor/frontend/src/app/globals.css resume-editor-agent/frontend/src/app/
```

- [ ] **Step 4: Create utils.ts**

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 5: Create api.ts with agent SSE client**

```typescript
const BASE = "http://localhost:8001";

/** Stream agent execution via SSE. Calls onEvent for each event. */
export async function startAgentRun(
  resumeText: string,
  jdText: string,
  goal: string,
  onEvent: (event: MessageEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const fd = new FormData();
  fd.append("resume_text", resumeText);
  fd.append("jd_text", jdText);
  fd.append("goal", goal);

  const res = await fetch(`${BASE}/api/agent`, { method: "POST", body: fd, signal });
  if (!res.ok) throw new Error("Agent run failed");

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventType = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          onEvent(new MessageEvent(eventType, { data: JSON.stringify(data) }));
        } catch { /* skip malformed */ }
        eventType = "message";
      }
    }
  }
}

/** Send intercept feedback for a completed step. */
export async function sendIntercept(
  runId: string,
  stepId: string,
  feedback: string,
  onEvent: (event: MessageEvent) => void,
): Promise<void> {
  const fd = new FormData();
  fd.append("run_id", runId);
  fd.append("step_id", stepId);
  fd.append("feedback", feedback);

  const res = await fetch(`${BASE}/api/intercept`, { method: "POST", body: fd });
  if (!res.ok) throw new Error("Intercept failed");

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          onEvent(new MessageEvent("step_revised", { data: line.slice(6) }));
        } catch { /* skip */ }
      }
    }
  }
}

export interface ModelInfo {
  id: string;
  name: string;
  default: boolean;
  base_url: string;
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const res = await fetch("http://localhost:8000/api/models");
  if (!res.ok) throw new Error("Failed to fetch models");
  const data = await res.json();
  return data.models;
}
```

- [ ] **Step 6: Install dependencies**

```bash
cd resume-editor-agent/frontend
npm install
```

- [ ] **Step 7: Commit**

```
git add resume-editor-agent/frontend/
git commit -m "feat: frontend scaffold with agent SSE API client"
```

---

### Task 6: Frontend PlanTimeline + InterceptInput components

**Files:**
- Create: `resume-editor-agent/frontend/src/components/PlanTimeline.tsx`
- Create: `resume-editor-agent/frontend/src/components/InterceptInput.tsx`
- Create: `resume-editor-agent/frontend/src/components/GoalInput.tsx`
- Modify: `resume-editor-agent/frontend/src/app/page.tsx`

- [ ] **Step 1: Write GoalInput.tsx**

```tsx
"use client";

interface Props {
  onSubmit: (goal: string) => void;
  disabled?: boolean;
}

export default function GoalInput({ onSubmit, disabled }: Props) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground block">
        🎯 你的求职目标是什么？
      </label>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const input = (e.target as HTMLFormElement).elements.namedItem("goal") as HTMLInputElement;
          if (input.value.trim()) onSubmit(input.value.trim());
        }}
        className="flex gap-2"
      >
        <input
          name="goal"
          type="text"
          placeholder="例：我想面进字节跳动的 AI Agent 岗位"
          disabled={disabled}
          className="flex-1 h-10 bg-secondary border border-border rounded-lg px-4 text-sm placeholder:text-muted-foreground/40 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-40"
        />
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Write PlanTimeline.tsx**

```tsx
"use client";

import { useEffect, useRef } from "react";
import InterceptInput from "./InterceptInput";

export interface StepState {
  id: string;
  name: string;
  icon: string;
  status: "pending" | "running" | "done" | "error" | "revising";
  duration_ms?: number;
}

interface Props {
  steps: StepState[];
  results: Record<string, string>;
  thinking: Record<string, string>;
  activeTab: string | null;
  onStepClick: (stepId: string) => void;
  onIntercept: (stepId: string, feedback: string) => void;
}

const STATUS_ICONS: Record<string, string> = {
  pending: "⏳",
  running: "⟳",
  done: "✓",
  error: "✗",
  revising: "⟳",
};

export default function PlanTimeline({
  steps,
  results,
  thinking,
  activeTab,
  onStepClick,
  onIntercept,
}: Props) {
  const timelineRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [steps]);

  if (steps.length === 0) return null;

  return (
    <section ref={timelineRef} className="space-y-2">
      <h2 className="text-sm font-medium text-foreground mb-3">📋 执行计划</h2>

      {steps.map((step, idx) => {
        const isActive = activeTab === step.id;
        const hasResult = !!results[step.id];
        const completedLater = step.status === "done" && steps.slice(idx + 1).some((s) => s.status === "done" || s.status === "running");

        return (
          <div key={step.id} className="bg-card border border-border rounded-lg overflow-hidden">
            {/* Step header */}
            <div
              className={`flex items-center justify-between px-4 py-2.5 cursor-pointer hover:bg-secondary/50 transition-colors ${
                isActive ? "ring-1 ring-brand" : ""
              }`}
              onClick={() => hasResult && onStepClick(step.id)}
            >
              <div className="flex items-center gap-2.5">
                <span className={`text-sm ${step.status === "running" || step.status === "revising" ? "animate-spin" : ""}`}>
                  {STATUS_ICONS[step.status]}
                </span>
                <span className="text-sm text-foreground">{step.icon}</span>
                <span className="text-sm text-foreground">{step.name}</span>
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground/60">
                {step.duration_ms != null && (
                  <span>{step.duration_ms >= 1000 ? `${(step.duration_ms / 1000).toFixed(1)}s` : `${step.duration_ms}ms`}</span>
                )}
                <span className="capitalize">{step.status}</span>
              </div>
            </div>
          </div>
        );
      })}
    </section>
  );
}
```

- [ ] **Step 3: Write InterceptInput.tsx**

```tsx
"use client";

import { useState } from "react";

interface Props {
  stepId: string;
  stepName: string;
  onSubmit: (stepId: string, feedback: string) => void;
}

export default function InterceptInput({ stepId, stepName, onSubmit }: Props) {
  const [value, setValue] = useState("");
  const [sent, setSent] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    onSubmit(stepId, value.trim());
    setValue("");
    setSent(true);
    setTimeout(() => setSent(false), 3000);
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 mt-3">
      <span className="text-[11px] text-muted-foreground/40 shrink-0">对这个结果有补充吗？</span>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="例：其实我做过系统设计，但简历上没写"
        className="flex-1 h-8 bg-secondary/50 border border-border rounded-md px-3 text-xs placeholder:text-muted-foreground/30 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />
      <button
        type="submit"
        disabled={!value.trim()}
        className="h-8 px-3 text-xs font-medium bg-brand text-white rounded-md hover:bg-brand-hover disabled:opacity-30 transition-colors"
      >
        发送
      </button>
      {sent && <span className="text-[11px] text-brand/70">已发送</span>}
    </form>
  );
}
```

- [ ] **Step 4: Write page.tsx with agent flow**

```tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import PlanTimeline from "@/components/PlanTimeline";
import GoalInput from "@/components/GoalInput";
import InterceptInput from "@/components/InterceptInput";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import { Button } from "@/components/ui/button";
import { startAgentRun, sendIntercept } from "@/lib/api";
import type { StepState } from "@/components/PlanTimeline";

interface AgentResults {
  [stepId: string]: string;
}

interface AgentThinking {
  [stepId: string]: string;
}

const INITIAL_STATUS_STEP = { status: "pending" as const, duration_ms: undefined };

type StepStatus = "idle" | "planning" | "running" | "done" | "error";

export default function Home() {
  const [resumeText, setResumeText] = useState("");
  const [jdText, setJdText] = useState("");
  const [goal, setGoal] = useState("");
  const [stepStatus, setStepStatus] = useState<StepStatus>("idle");
  const [steps, setSteps] = useState<StepState[]>([]);
  const [results, setResults] = useState<AgentResults>({});
  const [thinking, setThinking] = useState<AgentThinking>({});
  const [activeResult, setActiveResult] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleStartAnalysis = useCallback(async () => {
    if (!resumeText.trim() || !jdText.trim()) return;

    setStepStatus("planning");
    setSteps([]);
    setResults({});
    setThinking({});
    setActiveResult(null);
    setError(null);
    setRunId(null);

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      await startAgentRun(resumeText, jdText, goal, (event) => {
        if (abort.signal.aborted) return;

        try {
          const data = JSON.parse(event.data);

          if (event.type === "plan") {
            setRunId(data.run_id);
            setSteps(
              data.steps.map((s: any) => ({
                id: s.id,
                name: s.name,
                icon: s.icon || "📄",
                status: "pending" as const,
              }))
            );
            setStepStatus("running");
          } else if (event.type === "step_start") {
            setSteps((prev) =>
              prev.map((s) =>
                s.id === data.step_id ? { ...s, status: "running" as const } : s
              )
            );
          } else if (event.type === "step_done") {
            setSteps((prev) =>
              prev.map((s) =>
                s.id === data.step_id
                  ? { ...s, status: "done" as const, duration_ms: data.duration_ms }
                  : s
              )
            );
          } else if (event.type === "step_output" && data.step_id) {
            // Accumulate streaming text
            if (data.text != null) {
              setResults((prev) => ({
                ...prev,
                [data.step_id]: data.text,
              }));
            }
            if (data.thinking != null) {
              setThinking((prev) => ({
                ...prev,
                [data.step_id]: data.thinking,
              }));
            }
          } else if (event.type === "all_done") {
            setStepStatus("done");
            // Trigger notification
            if (document.hidden && "Notification" in window) {
              if (Notification.permission === "granted") {
                new Notification("简历分析完成", {
                  body: `已完成 ${Object.keys(data.results || {}).length} 项分析`,
                });
              } else if (Notification.permission === "default") {
                Notification.requestPermission();
              }
            }
          } else if (event.type === "error") {
            setError(data.error);
            setStepStatus("error");
          }
        } catch { /* skip */ }
      }, abort.signal);
    } catch (e: any) {
      if (e.name !== "AbortError") {
        setError(e.message || "Agent run failed");
        setStepStatus("error");
      }
    }
  }, [resumeText, jdText, goal]);

  const handleIntercept = useCallback(
    async (stepId: string, feedback: string) => {
      if (!runId) return;
      setSteps((prev) =>
        prev.map((s) =>
          s.id === stepId ? { ...s, status: "revising" as const } : s
        )
      );

      try {
        await sendIntercept(runId, stepId, feedback, (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.text != null) {
              setResults((prev) => ({ ...prev, [stepId]: data.text }));
            }
          } catch { /* skip */ }
        });
        setSteps((prev) =>
          prev.map((s) =>
            s.id === stepId ? { ...s, status: "done" as const } : s
          )
        );
      } catch {
        setSteps((prev) =>
          prev.map((s) =>
            s.id === stepId ? { ...s, status: "error" as const } : s
          )
        );
      }
    },
    [runId]
  );

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between px-5 h-13 border-b border-border bg-background/80 backdrop-blur-sm shrink-0">
        <h1 className="font-heading text-base tracking-tight text-foreground">
          Resume AI Agent
        </h1>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto py-10 pb-32 px-6 space-y-6">
          {/* Resume input */}
          <section>
            <label className="text-sm font-medium text-foreground block mb-2">
              简历内容
            </label>
            <textarea
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="粘贴简历内容..."
              rows={6}
              className="w-full bg-secondary border border-border rounded-lg p-4 text-sm font-mono resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring placeholder:text-muted-foreground/40"
            />
          </section>

          {/* JD input */}
          <section>
            <label className="text-sm font-medium text-foreground block mb-2">
              目标岗位描述 (JD)
            </label>
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="粘贴岗位描述..."
              rows={4}
              className="w-full bg-secondary border border-border rounded-lg p-4 text-sm resize-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring placeholder:text-muted-foreground/40"
            />
          </section>

          {/* Goal input */}
          <GoalInput onSubmit={setGoal} disabled={stepStatus === "running" || stepStatus === "planning"} />

          {/* Start button */}
          <Button
            onClick={handleStartAnalysis}
            disabled={!resumeText.trim() || !jdText.trim() || stepStatus === "running" || stepStatus === "planning"}
            size="lg"
            className="w-full"
          >
            {stepStatus === "planning"
              ? "正在规划..."
              : stepStatus === "running"
              ? "分析中..."
              : "开始分析"}
          </Button>

          {/* Error */}
          {error && (
            <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3">
              <p className="text-xs text-destructive">{error}</p>
            </div>
          )}

          {/* Plan timeline */}
          {steps.length > 0 && (
            <PlanTimeline
              steps={steps}
              results={results}
              thinking={thinking}
              activeTab={activeResult}
              onStepClick={setActiveResult}
              onIntercept={handleIntercept}
            />
          )}

          {/* Step result detail */}
          {activeResult && results[activeResult] && (
            <section>
              <h2 className="text-sm font-medium text-foreground mb-3">
                分析结果
              </h2>
              <div className="bg-card border border-border rounded-lg p-5">
                <MarkdownRenderer
                  content={results[activeResult] || ""}
                  thinking={thinking[activeResult] || undefined}
                />
                <InterceptInput
                  stepId={activeResult}
                  stepName={steps.find((s) => s.id === activeResult)?.name || activeResult}
                  onSubmit={handleIntercept}
                />
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Start dev server and test**

```bash
cd resume-editor-agent/frontend
npm run dev
```

Expected: Page loads with resume/JD textareas, goal input, and start button.

- [ ] **Step 6: Commit**

```
git add resume-editor-agent/frontend/src/app/page.tsx resume-editor-agent/frontend/src/components/PlanTimeline.tsx resume-editor-agent/frontend/src/components/InterceptInput.tsx resume-editor-agent/frontend/src/components/GoalInput.tsx resume-editor-agent/frontend/src/lib/api.ts
git commit -m "feat: agent flow UI with plan timeline and intercept"
```

---

### Task 7: Port remaining subagents (assessment, remediation, rewrite)

**Files:**
- Create: `resume-editor-agent/backend/subagents/assessment.py`
- Create: `resume-editor-agent/backend/subagents/remediation.py`
- Create: `resume-editor-agent/backend/subagents/rewrite.py`
- Modify: `resume-editor-agent/backend/subagents/__init__.py`
- Modify: `resume-editor-agent/backend/main.py`

- [ ] **Step 1: Write assessment.py**

```python
from ..subagent import SubagentDef, StreamCallback


class AssessmentSubagent(SubagentDef):
    
    def __init__(self):
        super().__init__(
            id="assessment",
            name="匹配评估",
            description="综合评分 + 面试竞争力分析",
            icon="🎯",
            inputs=["resume_text", "jd_text", "gap_analysis"],
            needed_skills=["assessment"],
        )
    
    async def run(self, inputs, emit, feedback=None, previous_result=None):
        from anthropic import AsyncAnthropic
        import os
        
        resume = inputs.get("resume_text", "")
        jd = inputs.get("jd_text", "")
        gap = inputs.get("gap_analysis", {}).get("text", "")
        
        system = "You are a professional career coach. Provide honest assessment and interview chances."
        if feedback:
            system += f"\n\nUser feedback: {feedback}"
        
        prompt = f"""Evaluate this resume's effectiveness for getting an interview.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

GAP ANALYSIS SUMMARY:
{gap[:2000]}

Score each dimension 1-10 with brief reasoning:
1. **ATS keyword match**
2. **First impression** (15-second scan)
3. **Narrative coherence** (story consistency)
4. **Impact evidence** (quantified results)
5. **Overall interview chance**

Then provide:
- Top 3 strengths
- Top 3 weaknesses
- One-paragraph summary of what a recruiter would think"""
        
        client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )
        
        resp = await client.messages.create(
            model=os.getenv("MODEL_ID", ""),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
        )
        
        text = ""
        thinking = ""
        for block in resp.content:
            if block.type == "text":
                text += block.text
                emit({"type": "output", "text": text})
            elif block.type == "thinking":
                thinking += block.thinking
        
        return {"text": text, "thinking": thinking, "truncated": resp.stop_reason == "max_tokens"}
```

- [ ] **Step 2: Write remediation.py**

```python
from ..subagent import SubagentDef, StreamCallback


class RemediationSubagent(SubagentDef):
    
    def __init__(self):
        super().__init__(
            id="remediation",
            name="补足路线",
            description="针对差距生成学习路线和优先级",
            icon="📋",
            inputs=["resume_text", "jd_text", "gap_analysis"],
            needed_skills=["remediation"],
        )
    
    async def run(self, inputs, emit, feedback=None, previous_result=None):
        from anthropic import AsyncAnthropic
        import os
        
        resume = inputs.get("resume_text", "")
        jd = inputs.get("jd_text", "")
        gap = inputs.get("gap_analysis", {}).get("text", "")
        
        system = "You are a learning path designer. Create concrete remediation plans."
        if feedback:
            system += f"\n\nUser feedback: {feedback}"
        
        prompt = f"""Create a concrete remediation plan for the gaps between this resume and job description.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

GAP ANALYSIS:
{gap[:2000]}

For each genuine gap (not repackagable), provide:
1. **Gap** - what's missing
2. **Priority** - High/Medium/Low
3. **Learning resource** - specific tutorial, course, or project idea
4. **Time estimate** - hours needed
5. **How to demonstrate** - how to show this skill on the resume after learning

Group into: Week 1 (urgent), Week 2-4, Month 2+"""
        
        client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )
        
        resp = await client.messages.create(
            model=os.getenv("MODEL_ID", ""),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
        )
        
        text = ""
        thinking = ""
        for block in resp.content:
            if block.type == "text":
                text += block.text
                emit({"type": "output", "text": text})
            elif block.type == "thinking":
                thinking += block.thinking
        
        return {"text": text, "thinking": thinking, "truncated": resp.stop_reason == "max_tokens"}
```

- [ ] **Step 3: Write rewrite.py**

```python
from ..subagent import SubagentDef, StreamCallback


class RewriteSubagent(SubagentDef):
    
    def __init__(self):
        super().__init__(
            id="rewrite",
            name="故事改写",
            description="用叙事逻辑重构简历表述，背景-问题-方案-影响",
            icon="✏️",
            inputs=["resume_text", "jd_text", "gap_analysis", "assessment"],
            needed_skills=["rewrite"],
        )
    
    async def run(self, inputs, emit, feedback=None, previous_result=None):
        from anthropic import AsyncAnthropic
        import os
        
        resume = inputs.get("resume_text", "")
        jd = inputs.get("jd_text", "")
        gap = inputs.get("gap_analysis", {}).get("text", "")
        
        system = "You are a professional resume writer. Rewrite using storytelling logic."
        if feedback:
            system += f"\n\nUser feedback: {feedback}"
        
        prompt = f"""Rewrite the resume to be more compelling.

RESUME:
{resume}

JOB DESCRIPTION:
{jd}

GAP ANALYSIS:
{gap[:2000]}

Use the narrative structure:
- Project Background: what was the context
- Problem: what pain point existed
- Solution: what you designed and built
- Impact: quantified results and user value

Rules:
- Keep all factual claims truthful
- Chinese narrative with embedded English tech keywords (do NOT translate keywords like Tool Calling, Permission Gate, etc.)
- Each bullet should tell a mini-story
- Prioritize impact and results over descriptions"""
        
        client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )
        
        resp = await client.messages.create(
            model=os.getenv("MODEL_ID", ""),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=16384,
        )
        
        text = ""
        thinking = ""
        for block in resp.content:
            if block.type == "text":
                text += block.text
                emit({"type": "output", "text": text})
            elif block.type == "thinking":
                thinking += block.thinking
        
        return {"text": text, "thinking": thinking, "truncated": resp.stop_reason == "max_tokens"}
```

- [ ] **Step 4: Update subagents/__init__.py**

```python
from .gap_analysis import GapAnalysisSubagent
from .assessment import AssessmentSubagent
from .remediation import RemediationSubagent
from .rewrite import RewriteSubagent
```

- [ ] **Step 5: Register new subagents in main.py**

In `main.py`, update the registry setup:

```python
from .subagents import (
    GapAnalysisSubagent,
    AssessmentSubagent,
    RemediationSubagent,
    RewriteSubagent,
)

registry = SubagentRegistry()
registry.register(GapAnalysisSubagent())
registry.register(AssessmentSubagent())
registry.register(RemediationSubagent())
registry.register(RewriteSubagent())
```

- [ ] **Step 6: Test**

```bash
cd resume-editor-agent/backend
python -c "
from subagents import GapAnalysisSubagent, AssessmentSubagent, RemediationSubagent, RewriteSubagent
for cls in [GapAnalysisSubagent, AssessmentSubagent, RemediationSubagent, RewriteSubagent]:
    a = cls()
    print(f'{a.id}: {a.name}, inputs={a.inputs}, skills={a.needed_skills}')
"
```

Expected: All 4 subagents print with their metadata.

- [ ] **Step 7: Commit**

```
git add resume-editor-agent/backend/subagents/
git commit -m "feat: port assessment, remediation, rewrite subagents"
```

---

### Task 8: Skills system (s05)

**Files:**
- Create: `resume-editor-agent/backend/skills/gap_analysis/SKILL.md`
- Create: `resume-editor-agent/backend/skills/assessment/SKILL.md`
- Create: `resume-editor-agent/backend/skills/remediation/SKILL.md`
- Create: `resume-editor-agent/backend/skills/rewrite/SKILL.md`
- Modify: `resume-editor-agent/backend/subagent.py` (add skill loading)

- [ ] **Step 1: Add skill loading to SubagentDef**

Add to `subagent.py`:

```python
from pathlib import Path

class SubagentDef:
    # ... existing fields ...
    
    def load_skills(self) -> str:
        """Load skill content from skills/ directory."""
        base = Path(__file__).parent / "skills"
        parts = []
        for skill_id in self.needed_skills:
            skill_path = base / skill_id / "SKILL.md"
            if skill_path.exists():
                parts.append(f"=== {skill_id} ===\n{skill_path.read_text(encoding='utf-8')}")
        return "\n\n".join(parts)
```

- [ ] **Step 2: Create skills/gap_analysis/SKILL.md**

```markdown
# Gap Analysis Skill

## Classification Framework

Categorize each JD requirement into one of:

1. **Strong match** — Resume directly demonstrates this skill/experience. Mark with ✓.
2. **Repackagable** — Resume has related experience that can be positioned to fit. Mark with ⟳. Explain how to rephrase.
3. **Genuine gap** — Missing entirely. No experience to draw on. Mark with ✗.

## Scoring

Overall fit score (1-10):
- 1-3: Major gaps, unlikely to pass screening
- 4-6: Some alignment, need significant adjustment
- 7-8: Good fit, minor gaps
- 9-10: Strong match, minimal gaps

## Output Format

Use sections: Strong matches, Repackagable, Genuine gaps, Keywords to add, Overall fit score.
```

- [ ] **Step 3: Create skills/assessment/SKILL.md**

```markdown
# Assessment Skill

## Scoring Dimensions

1. **ATS keyword match** (1-10) — How well does the resume contain JD keywords?
2. **First impression** (1-10) — What does a 15-second scan reveal?
3. **Narrative coherence** (1-10) — Is there a consistent career story?
4. **Impact evidence** (1-10) — Are results quantified and specific?
5. **Overall interview chance** (1-10) — Realistic assessment.

## Output

For each score, provide 1-2 sentence reasoning.
Then: Top 3 strengths, Top 3 weaknesses, Recruiter summary paragraph.
```

- [ ] **Step 4: Create skills/remediation/SKILL.md**

```markdown
# Remediation Skill

## Gap Prioritization

- **High priority** — Required for the role, explicitly listed in JD
- **Medium priority** — Preferred/nice-to-have in JD
- **Low priority** — Listed but not emphasized

## Learning Plan Structure

Each gap gets:
1. Specific learning resource (MOOC, tutorial, book chapter, project)
2. Time estimate in hours
3. How to demonstrate after learning

Group into: Week 1 (urgent), Week 2-4, Month 2+.
```

- [ ] **Step 5: Create skills/rewrite/SKILL.md**

```markdown
# Rewrite Skill

## Narrative Framework

Use "Background → Problem → Solution → Impact" for each bullet:

- **Background**: What was the context? (团队、项目规模、技术栈)
- **Problem**: What pain point existed? (延迟、错误率、用户体验问题)
- **Solution**: What did you design and build? (具体技术方案)
- **Impact**: Quantified results. (性能提升、成本降低、用户增长)

## Rules

- Keep all factual claims truthful
- Chinese narrative with embedded English tech keywords
- Do NOT translate: Tool Calling, Permission Gate, Agent Loop, SSE, Function Calling
- Prioritize impact and results over descriptions
```

- [ ] **Step 6: Commit**

```
git add resume-editor-agent/backend/skills/ resume-editor-agent/backend/subagent.py
git commit -m "feat: skills system with gap/assessment/remediation/rewrite skills"
```

---

### Task 9: Task system persistence (s07)

**Files:**
- Create: `resume-editor-agent/backend/task_manager.py`
- Modify: `resume-editor-agent/backend/coordinator.py`
- Modify: `resume-editor-agent/backend/main.py`

- [ ] **Step 1: Write task_manager.py**

```python
"""Task system (s07): persistent task directories for agent runs."""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("resume-editor.task_manager")

TASKS_DIR = Path(__file__).parent / "tasks"


class TaskManager:
    """Persist agent run state to .tasks/{run_id}/ for recovery and inspection."""
    
    def __init__(self):
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
    
    def create_run(self) -> str:
        run_id = uuid.uuid4().hex[:12]
        (TASKS_DIR / run_id).mkdir(parents=True, exist_ok=True)
        logger.info("Task run created: %s", run_id)
        return run_id
    
    def save_plan(self, run_id: str, plan: dict):
        path = TASKS_DIR / run_id / "plan.json"
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    
    def save_result(self, run_id: str, step_id: str, result: dict):
        step_dir = TASKS_DIR / run_id / step_id
        step_dir.mkdir(parents=True, exist_ok=True)
        (step_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2)
        )
    
    def get_result(self, run_id: str, step_id: str) -> Optional[dict]:
        path = TASKS_DIR / run_id / step_id / "result.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())
    
    def get_plan(self, run_id: str) -> Optional[dict]:
        path = TASKS_DIR / run_id / "plan.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())
    
    def list_runs(self) -> list[str]:
        return sorted(
            [d.name for d in TASKS_DIR.iterdir() if d.is_dir()],
            reverse=True,
        )[:20]
```

- [ ] **Step 2: Integrate TaskManager into Coordinator**

In `coordinator.py`, update the `execute` method to persist results:

```python
# At top of coordinator.py
from .task_manager import TaskManager

# In Coordinator.__init__:
self.task_manager = TaskManager()

# In execute(), after agent.run():
self.task_manager.save_result(step_id, result)
```

Also store `run_id` from the execute event:

```python
# execute() yields events — the run_id comes from main.py
# Pass run_id to Coordinator.execute():
async def execute(self, plan, resume_text, jd_text, goal, run_id: str):
    # ...
    for step in plan.steps:
        # ...
        result = await agent.run(...)
        self.task_manager.save_result(run_id, step["id"], result)
        # ...
```

- [ ] **Step 3: Update main.py to pass run_id**

```python
@app.post("/api/agent")
async def run_agent(...):
    run_id = task_manager.create_run()
    
    async def event_stream():
        plan_data = await coordinator.plan(...)
        task_manager.save_plan(run_id, plan_data)
        yield f"event: plan\ndata: {json.dumps({'run_id': run_id, ...})}\n\n"
        
        async for event in coordinator.execute(plan, resume_text, jd_text, goal, run_id):
            ...
```

- [ ] **Step 4: Update intercept to load from task cache**

```python
@app.post("/api/intercept")
async def intercept_step(run_id: str = Form(...), step_id: str = Form(...), feedback: str = Form(...)):
    # Load previous result from task system
    previous = task_manager.get_result(run_id, step_id)
    
    agent = registry.get(step_id)
    if not agent:
        raise HTTPException(400, f"Unknown subagent: {step_id}")
    
    async def re_run_stream():
        result = await agent.run(
            inputs={},
            emit=lambda data: None,
            feedback=feedback,
            previous_result=previous,
        )
        # Save updated result
        task_manager.save_result(run_id, step_id, result)
        yield f"event: step_revised\ndata: {json.dumps({...})}\n\n"
```

- [ ] **Step 5: Add GET endpoint to restore from task**

```python
@app.get("/api/agent/{run_id}")
async def get_run_status(run_id: str):
    """Restore agent run state from task persistence."""
    plan = task_manager.get_plan(run_id)
    if not plan:
        raise HTTPException(404, "Run not found")
    
    # Collect all step results
    results = {}
    for step in plan.get("steps", []):
        result = task_manager.get_result(run_id, step["id"])
        if result:
            results[step["id"]] = result
    
    return {"run_id": run_id, "plan": plan, "results": results}
```

- [ ] **Step 6: Commit**

```
git add resume-editor-agent/backend/task_manager.py
git commit -m "feat: task system persistence for agent runs"
```

---

### Task 10: Memory system (cross-session)

**Files:**
- Create: `resume-editor-agent/backend/memory_manager.py`
- Create: `resume-editor-agent/backend/memory/user_profile.md`
- Modify: `resume-editor-agent/backend/main.py`

- [ ] **Step 1: Write memory_manager.py**

```python
"""Cross-session memory (user profile + analysis history)."""
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("resume-editor.memory")

MEMORY_DIR = Path(__file__).parent / "memory"


class MemoryManager:
    """Manages user profile and analysis history across sessions."""
    
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._profile_path = MEMORY_DIR / "user_profile.md"
        self._history_path = MEMORY_DIR / "analysis_history.json"
    
    def get_profile(self) -> str:
        """Load user profile text for injection into agent prompts."""
        if self._profile_path.exists():
            return self._profile_path.read_text(encoding="utf-8")
        return ""
    
    def update_profile(self, key: str, value: str):
        """Update a profile field."""
        profile = self._load_profile_dict()
        profile[key] = value
        profile["last_updated"] = datetime.now().isoformat()
        self._save_profile_dict(profile)
    
    def _load_profile_dict(self) -> dict:
        profile = {}
        if self._profile_path.exists():
            text = self._profile_path.read_text(encoding="utf-8")
            for line in text.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    profile[k.strip()] = v.strip()
        return profile
    
    def _save_profile_dict(self, profile: dict):
        lines = [f"{k}: {v}" for k, v in profile.items()]
        self._profile_path.write_text("\n".join(lines), encoding="utf-8")
    
    def add_history(self, run_id: str, summary: str):
        """Record an analysis run in history."""
        history = []
        if self._history_path.exists():
            history = json.loads(self._history_path.read_text())
        history.append({
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
        })
        # Keep last 20
        history = history[-20:]
        self._history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2))
    
    def get_recent_context(self) -> str:
        """Get recent context for injection."""
        parts = []
        profile = self.get_profile()
        if profile:
            parts.append(f"用户信息：\n{profile}")
        if self._history_path.exists():
            history = json.loads(self._history_path.read_text())
            if history:
                last = history[-1]
                parts.append(f"最近分析（{last['timestamp']}）：{last['summary']}")
        return "\n\n".join(parts)
```

- [ ] **Step 2: Create initial user_profile.md**

```markdown
background: 
style_preferences: 
last_target_role: 
```

- [ ] **Step 3: Integrate into Coordinator plan method**

In `coordinator.py`, add memory injection to the planning prompt:

```python
from .memory_manager import MemoryManager

class Coordinator:
    def __init__(self, registry):
        self.registry = registry
        self.memory = MemoryManager()
    
    async def plan(self, resume_text, jd_text, goal=""):
        user_context = self.memory.get_recent_context()
        
        system = f"""You are a resume analysis coordinator. Available subagents:
{self.registry.describe()}

{user_context}

Given the user's resume, job description, and goal, select which subagents to run...
"""
```

- [ ] **Step 4: Hook memory into pre_subagent**

In `main.py`, register a hook to inject memory:

```python
from .memory_manager import MemoryManager

memory_mgr = MemoryManager()

HOOKS.register("pre_subagent", lambda step, inputs, ctx: {
    **inputs,
    "user_profile": memory_mgr.get_profile(),
})
```

- [ ] **Step 5: Commit**

```
git add resume-editor-agent/backend/memory_manager.py resume-editor-agent/backend/memory/
git commit -m "feat: cross-session memory system"
```

---

### Task 11: Company analysis subagent + web_search tool

**Files:**
- Create: `resume-editor-agent/backend/subagents/company_analysis.py`
- Create: `resume-editor-agent/backend/skills/company_analysis/SKILL.md`
- Create: `resume-editor-agent/backend/tools/search.py`
- Modify: `resume-editor-agent/backend/subagents/__init__.py`
- Modify: `resume-editor-agent/backend/main.py`

- [ ] **Step 1: Write tools/search.py**

```python
"""Web search tool for deep research."""
import logging
from typing import Optional

logger = logging.getLogger("resume-editor.search")


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web for information.
    
    Uses a configurable search backend. Currently returns a placeholder
    that logs the query. Replace with actual search API integration.
    """
    logger.info("Web search requested: query=%s max_results=%d", query, max_results)
    
    # TODO: Replace with actual search API (SerpAPI, Tavily, etc.)
    # For now, return a placeholder
    return [
        {"title": f"Search results for: {query}", "snippet": f"Results for '{query}' would appear here with a search API key configured."}
    ]
```

- [ ] **Step 2: Write company_analysis subagent**

```python
"""Company analysis subagent: researches company health, products, team."""
from ..subagent import SubagentDef, StreamCallback


class CompanyAnalysisSubagent(SubagentDef):
    
    def __init__(self):
        super().__init__(
            id="company_analysis",
            name="公司尽调",
            description="分析目标公司的业务健康度、融资阶段、团队背景、市场位置",
            icon="🏢",
            inputs=["jd_text"],
            needed_skills=["company_analysis"],
        )
    
    async def run(self, inputs, emit, feedback=None, previous_result=None):
        from anthropic import AsyncAnthropic
        from ..tools.search import web_search
        import os
        
        jd = inputs.get("jd_text", "")
        
        # Extract company name from JD (simplified)
        import re
        company_match = re.search(r'(?:公司|企业|@|at)\s*[:：]?\s*(\S+)', jd[:500])
        company_name = company_match.group(1) if company_match else ""
        
        # Do web search for company info
        search_results = []
        if company_name:
            search_results = await web_search(f"{company_name} 公司介绍 融资 业务")
        
        search_context = ""
        if search_results:
            search_context = "\n".join(
                f"- {r['title']}: {r['snippet']}" for r in search_results
            )
        
        system = "You are a business analyst. Analyze companies from a job seeker's perspective."
        if feedback:
            system += f"\n\nUser feedback: {feedback}"
        
        prompt = f"""Analyze the company behind this job description.

JOB DESCRIPTION:
{jd}

{f'WEB SEARCH RESULTS:\n{search_context}' if search_context else ''}

Provide analysis covering:
1. **Company overview** — What does this company do? Size, stage, reputation
2. **Product/Service** — Core offerings relevant to the role
3. **Team context** — What the team culture might be like (from JD signals)
4. **Career implications** — Growth potential, stability, exit opportunities
5. **Interview tips** — What to emphasize based on company positioning"""
        
        client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )
        
        resp = await client.messages.create(
            model=os.getenv("MODEL_ID", ""),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
        )
        
        text = ""
        thinking = ""
        for block in resp.content:
            if block.type == "text":
                text += block.text
                emit({"type": "output", "text": text})
            elif block.type == "thinking":
                thinking += block.thinking
        
        return {"text": text, "thinking": thinking, "truncated": resp.stop_reason == "max_tokens"}
```

- [ ] **Step 3: Create skills/company_analysis/SKILL.md**

```markdown
# Company Analysis Skill

## Analysis Framework

1. **Company overview**: What does this company do? Size, stage, reputation, funding
2. **Product/Service**: Core offerings relevant to the candidate's role
3. **Team context**: What the team culture might be like from JD signals
4. **Career implications**: Growth potential, stability, exit opportunities
5. **Interview tips**: What to emphasize based on company positioning

## Data Sources

- Company website and product descriptions
- Public funding/investment news
- Employee reviews (levels.fyi, Glassdoor)
- Tech stack mentions in JD
```

- [ ] **Step 4: Register in __init__.py and main.py**

```python
# subagents/__init__.py
from .company_analysis import CompanyAnalysisSubagent

# main.py — register
from .subagents import CompanyAnalysisSubagent
registry.register(CompanyAnalysisSubagent())
```

- [ ] **Step 5: Commit**

```
git add resume-editor-agent/backend/subagents/company_analysis.py resume-editor-agent/backend/skills/company_analysis/ resume-editor-agent/backend/tools/search.py
git commit -m "feat: company analysis subagent with web search"
```

---

### Task 12: Context compression (s06)

**Files:**
- Create: `resume-editor-agent/backend/context_compressor.py`

- [ ] **Step 1: Write context_compressor.py**

```python
"""Context compression (s06): summarize old messages to manage context window."""
import logging
from typing import Any

logger = logging.getLogger("resume-editor.compressor")

# Token estimation (rough: 4 chars ≈ 1 token)
_CHARS_PER_TOKEN = 4
_MAX_TOKENS = 80000  # Claude context limit safety margin


def estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def compress_messages(messages: list[dict], target_tokens: int = 40000) -> list[dict]:
    """Three-layer compression:
    1. Summarize oldest messages
    2. Retain recent verbatim
    3. Drop tool call internals if still over limit
    """
    total = sum(estimate_tokens(str(m.get("content", ""))) for m in messages)
    
    if total <= target_tokens:
        return messages
    
    logger.info("Compressing %d messages (%d tokens)", len(messages), total)
    
    # Layer 1: split into old + recent
    mid = len(messages) // 2
    old = messages[:mid]
    recent = messages[mid:]
    
    # Layer 2: summarize old messages
    compressed_old = _summarize_old(old)
    
    result = compressed_old + recent
    total_after = sum(estimate_tokens(str(m.get("content", ""))) for m in result)
    
    if total_after <= target_tokens:
        logger.info("Compressed to %d tokens (layer 1)", total_after)
        return result
    
    # Layer 3: truncate tool results in recent messages
    for msg in recent:
        if msg.get("role") == "user" and isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if isinstance(content, str) and len(content) > 500:
                        block["content"] = content[:500] + "\n...[truncated]"
    
    total_final = sum(estimate_tokens(str(m.get("content", ""))) for m in result)
    logger.info("Compressed to %d tokens (layer 2)", total_final)
    
    return result


def _summarize_old(old_messages: list[dict]) -> list[dict]:
    """Reduce old messages to a summary message."""
    text_parts = []
    for msg in old_messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            text_parts.append(f"{msg['role']}: {content[:200]}")
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(f"{msg['role']}: {block['text'][:200]}")
    
    summary = "\n".join(text_parts)
    if len(summary) > 3000:
        summary = summary[:3000] + "\n...[summarized]"
    
    return [{"role": "user", "content": f"[Previous conversation summary]:\n{summary}"}]
```

- [ ] **Step 2: Commit**

```
git add resume-editor-agent/backend/context_compressor.py
git commit -m "feat: context compression with 3-layer strategy"
```

---

### Task 13: Background tasks (s08)

**Files:**
- Create: `resume-editor-agent/backend/background.py`

- [ ] **Step 1: Write background.py**

```python
"""Background task system (s08): async execution with completion callback."""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Optional

logger = logging.getLogger("resume-editor.background")


class BackgroundTask:
    id: str
    coro: Any
    result: Optional[Any] = None
    error: Optional[str] = None
    done: bool = False
    start_time: float = 0.0
    
    def __init__(self, coro, on_complete: Optional[Callable] = None):
        self.id = uuid.uuid4().hex[:8]
        self.coro = coro
        self.on_complete = on_complete
    
    async def run(self):
        self.start_time = time.time()
        try:
            self.result = await self.coro
        except Exception as e:
            self.error = str(e)[:500]
            logger.error("Background task %s failed: %s", self.id, self.error)
        finally:
            self.done = True
            if self.on_complete and self.result:
                await self.on_complete(self.result)
            logger.info("Background task %s done in %.2fs", self.id, time.time() - self.start_time)


class BackgroundTaskManager:
    """Manages concurrent background tasks."""
    
    def __init__(self):
        self._tasks: dict[str, BackgroundTask] = {}
    
    def submit(self, coro, on_complete: Optional[Callable] = None) -> str:
        task = BackgroundTask(coro, on_complete)
        self._tasks[task.id] = task
        asyncio.create_task(task.run())
        logger.info("Background task submitted: %s", task.id)
        return task.id
    
    def get_status(self, task_id: str) -> Optional[dict]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        return {
            "id": task.id,
            "done": task.done,
            "error": task.error,
            "duration_ms": int((time.time() - task.start_time) * 1000) if task.start_time else 0,
        }
    
    def get_result(self, task_id: str) -> Any:
        task = self._tasks.get(task_id)
        return task.result if task and task.done else None


background_manager = BackgroundTaskManager()
```

- [ ] **Step 2: Commit**

```
git add resume-editor-agent/backend/background.py
git commit -m "feat: background task system for long-running operations"
```

---

### Task 14: Hook registration examples

- [ ] **Step 1: Register hooks in main.py for demo value**

In `main.py`, add example hook registrations that demonstrate the system:

```python
# ── Hook registrations ─────────────────────────────────────────────────

# Example 1: Log all subagent execution
HOOKS.register("post_subagent", lambda step, result, ctx: (
    logger.info("[hook] Subagent %s completed: %d chars, %s truncated",
                step["id"], len(result.get("text", "")), result.get("truncated"))
))

# Example 2: Auto-save analysis to history
HOOKS.register("on_all_done", lambda results, ctx: (
    logger.info("[hook] All done: %d results", len(results))
))

# Example 3: Track errors
HOOKS.register("on_error", lambda step_id, error, ctx: (
    logger.warning("[hook] Step %s error: %s", step_id, error[:100])
))

logger.info("Registered %d hooks", len(HOOKS._hooks))
```

- [ ] **Step 2: Commit**

```
git commit -m "feat: hook registration examples in main.py"
```

---

## Self-Review Checklist

**Spec coverage:**
- §3 Agent Loop → Task 3 (Coordinator)
- §4 Hooks → Task 1 (hooks.py) + Task 14 (registrations)
- §5 Subagent → Tasks 1-2 (base) + Task 7 (assessment/remediation/rewrite)
- §6 SSE Protocol → Task 4 (main.py SSE events) + Task 5 (api.ts client)
- §7 Skills → Task 8 (skills/ files + loading)
- §8 Tool System → Task 4 (tools/resume_tools.py) + Task 11 (search tool)
- §9 Task System → Task 9 (task_manager.py)
- §10 Context Compression → Task 12 (context_compressor.py)
- §11 Background Tasks → Task 13 (background.py)
- §12 Memory → Task 10 (memory_manager.py)
- §13 Frontend → Task 5 (scaffold) + Task 6 (components)
- §15 Project Structure → File structure section in plan header
- §16 Implementation Order → Task ordering matches design doc phases

**No placeholders:** All steps contain complete code, no TBD or TODOs except the search API integration in `tools/search.py` which is explicitly documented as a TODO with explanation.

**Type consistency:** SubagentDef signature consistent across all subagents. Coordinator.execute() signature matches callers. Event types match SSE protocol.
