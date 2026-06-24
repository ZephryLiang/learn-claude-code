# 8 Thinking Angles — Quick Reference

One card per angle. Before writing, scan this list and pick 3-5.

---

## Angle 1: Counter-Intuition Hook

**One question**: What did I believe before? What surprised me?

**Formula**: "You'd think X, but actually Y"

**Example**: "You'd think Lead and Teammate need two loops. Actually, one loop + different config."

---

## Angle 2: Framework Triangulation

**One question**: Do 2+ mature projects independently converge here?

**Formula**: My finding → Framework A (purest) → Framework B (complete) → Framework C (opinionated) → Conclusion

**Example**: "OpenAI SDK does it with dataclass. Claude SDK does it with YAML. CrewAI does it with Agent class. All three = same loop, different config."

---

## Angle 3: Yardstick Thinking

**One question**: What framework do I use to judge this? Can I give it to readers?

**Formula**: Instead of "X is good", write "X covers sessions 2/4/7, missing 9. Here's why that matters."

**Example**: "Learn-claude-code's 12 sessions are your yardstick. Framework X's multi-agent? That's s04 subagent, not s09 teammate."

---

## Angle 4: Old → New Mapping

**One question**: What pre-LLM concept already solved this structural problem?

**Formula**: NewConcept = OldConcept + whatChanged

**Example**: "JSONL inbox = Erlang mailbox (1986). Same pattern, different actor."

---

## Angle 5: Binary Distinction

**One question**: What two things are being conflated? What's the ONE question that separates them?

**Formula**: "X is really two different things: X₁ and X₂. Here's how to tell them apart."

**Example**: "Multi-agent is really two things: subagent (use and discard) vs teammate (long-lived + inbox). Ask: does it have an idle loop?"

---

## Angle 6: Business Scenario Stress Test

**One question**: WHO needs this, and what exactly would break for them?

**Formula**: Scenario → Hard Requirement → Why Framework Fails → Root Design Assumption

**Example**: "Bug root-cause analysis needs agents to debate each other peer-to-peer. Framework X fails because it's Star topology — all communication flows through orchestrator."

---

## Angle 7: Module-Level Deep Dive

**One question**: What's Layer 1 (teaching), Layer 2 (production), Layer 3 (cutting-edge)?

**Formula**: Teaching version → Production version → Optimization → Learning path

**Example**: "s06 microcompact (truncate) → auto-compact (LLM summary) → Mem0 (vector memory). Learning path: s06 → Mem0 docs → compare."

---

## Angle 8: Personal Project Anchor

**One question**: How would I use this in MY project?

**Formula**: What I learned → My project → Concrete use

**Example**: "s07 Task System → job application tracker → each application is a task with blockedBy dependencies."
