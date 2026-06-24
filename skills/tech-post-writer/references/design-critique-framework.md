# Design Critique Framework

Systematic method for questioning a system's design and converting findings into content.

## Phase 0: Judge First

Before any critique, determine if the design is worth questioning.

### Decision Tree

```
Is this teaching/demo code?
├─ YES → Simplifications are likely intentional
│        └─ Ask: "What concept would be buried if this were production-grade?"
│        └─ Write about: design PHILOSOPHY behind the simplification
│
└─ NO → Production code meant to handle real load
         └─ Ask: "What breaks first under stress?"
         └─ Write about: concrete failure modes and fixes
```

### The Insight Filter

| Critique Type | Insight Value | Write? |
|---|---|---|
| Reveals a hidden design assumption | HIGH — teaches WHY the design is what it is | YES |
| Shows what breaks under production stress | HIGH — teaches robustness thinking | YES |
| "Should use X instead of Y" (tool swap) | LOW — trivia, not insight | NO |
| One-line fix (hardcode → configurable) | LOW — no design lesson | NO |
| Missing feature that contradicts the philosophy | HIGH — reveals intentional tradeoff | YES |
| Missing feature that just hasn't been built yet | MEDIUM — depends on WHY it's missing | MAYBE |

## The 5 Production Lenses

Apply in order. Each lens pierces one layer of the system.

### Lens 1: Threading & Concurrency

```
Key question: "What happens when multiple things happen at the same time?"
Signs you need this lens:
  - Code uses daemon threads
  - Synchronous I/O in a loop
  - No thread pool or concurrency limit
  - Share-nothing architecture (no locks) — is this intentional or accidental?
```

### Lens 2: Message Bus & Transport

```
Key question: "Can messages be lost, duplicated, or corrupted?"
Signs you need this lens:
  - File-based message passing without ACK
  - Read-then-clear pattern (no offset tracking)
  - No file locks on concurrent access
  - No message TTL or deduplication
```

### Lens 3: Protocol Enforcement

```
Key question: "Is the protocol a suggestion or a constraint?"
Signs you need this lens:
  - System prompt says "you should X" but no hard gate
  - Tool can be called without prerequisite conditions
  - Same tool name has different semantics for different roles
  - Timeout is implicit (loop iteration count) not explicit (wall clock)
```

### Lens 4: Error Handling & Resilience

```
Key question: "What happens when something fails silently?"
Signs you need this lens:
  - Bare except: clauses with break/return
  - No retry on transient failures (429, 5xx)
  - No error state for entity lifecycle (only "idle" and "shutdown")
  - Tool errors returned as strings to model — no harness-level handling
```

### Lens 5: State & Persistence

```
Key question: "Process restart → what's lost?"
Signs you need this lens:
  - In-memory dicts/lists as primary state store
  - File writes without atomic rename
  - No migration path for state schema changes
  - Config and runtime state mixed together
```

## P0-P3 Prioritization

When converting critique findings to actionable upgrades:

| Level | Definition | Signal Question |
|-------|-----------|-----------------|
| P0 | Would FAIL in production | "Data lost? Processes hung? Silent crash?" |
| P1 | Would be FRAGILE | "No enforcement? No retry? Recovers incorrectly?" |
| P2 | Would be CONFUSING | "Same name, different meaning? State disappears on restart?" |
| P3 | Would be BLIND | "No metrics? No tracing? No one knows it broke?" |

### The P0 Test

```
If [component] fails right now:
├─ System doesn't notice → P0
├─ System notices but can't recover → P1
├─ System recovers but confusingly → P2
└─ System recovers but invisibly → P3
```

## Structure: The Critique Paragraph

Every design critique in a post should follow this shape:

```
1. What the code does now (concrete, specific)
2. What scenario breaks it (concrete, specific)
3. Why the DESIGN is still correct (fairness)
4. What production would add (actionable)
5. Why the teaching version is simpler (closes the loop)
```

Anti-pattern: "X is bad, should use Y instead" — no insight, no philosophy, just tool preference.

## Relation to Other Angles

- **Angle 6** uses the 5 Lenses to find WHAT breaks
- **Angle 7** uses P0-P3 to prioritize HOW to fix it
- **Angle 3 (Yardstick)** can use critique findings: "Framework X handles P0-P1 but ignores P2-P3. Here's how to evaluate."
- **Angle 5 (Binary Distinction)** often emerges from Lens 3: "This tool name conflates two different operations"
