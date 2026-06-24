---
target: main page.tsx layout
total_score: 21
p0_count: 2
p1_count: 2
timestamp: 2026-05-14T03-33-15Z
slug: src-app-page-tsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3/4 | Loading dots exist; no compile progress; no cache-vs-fresh distinction |
| 2 | Match System / Real World | 3/4 | Chinese labels are good; workflow order is logical |
| 3 | User Control and Freedom | 2/4 | Rewrite has "apply" but no undo; no cancel on AI calls |
| 4 | Consistency and Standards | 2/4 | Rainbow button colors; JD input required by all tabs but lives in one |
| 5 | Error Prevention | 2/4 | Model switch clears cache without confirmation; no JD guard |
| 6 | Recognition Rather Than Recall | 3/4 | Tabs are legible; cached results survive tab switches |
| 7 | Flexibility and Efficiency | 2/4 | Ctrl+S compile shortcut broken; no keyboard nav |
| 8 | Aesthetic and Minimalist Design | 2/4 | Design spec says viridian green; entire UI is blue |
| 9 | Error Recovery | 1/4 | Raw error text dumps; no retry; no undo on rewrite |
| 10 | Help and Documentation | 1/4 | Zero onboarding; no differentiation between AI tools |
| **Total** | | **21/40** | **Needs improvement** |

## Anti-Patterns Verdict

**MODERATE AI involvement detected.** The three AI tool components (JDAnalysis, Assessment, Remediation) are structurally identical — same layout, same loading pattern, same error handling, only button color differs. This is a generate-and-forget template signature.

**Deterministic scan (6 findings):**
- **bg-black on modal overlay** (AddModelModal.tsx:44) — Pure #000 violates the "tint every extreme" rule
- **5× gray text on colored disabled buttons** — text-zinc-600 on bg-blue-700, bg-purple-700, bg-amber-700, bg-green-700 creates illegible disabled states

## Cognitive Load: HIGH (6 failures)

1. 6 tabs in 480px — no guidance on workflow order
2. Hidden JD dependency chain — Assessment/Remediation/Rewrite require JD text entered elsewhere
3. Model selector foregrounds infrastructure over task
4. Dual upload paths (PDF + LaTeX) with unexplained interaction
5. No workflow state visualization — cached results invisible
6. Rainbow buttons assign false color semantics

## What's Working

1. **Rewrite tab closes the loop** — "apply to editor" is the strongest UX pattern; it's the only tab with a clear action-result-feedback cycle
2. **Dark tonal layering** — three-layer surface hierarchy works well without shadows
3. **Tab loading indicators** — pulsing dot + inline text provide good dual-signal feedback

## Priority Issues

**P0 — Brand Color Violation (entire UI)**
Design system defines viridian green; implementation uses blue-600, blue-400, blue-700 everywhere. Green appears once (JD Analysis button). Results in generic AI-tool look.

**P0 — Ctrl+S Compile Shortcut Broken**
Editor dispatches CustomEvent("compile-pdf") but page.tsx never listens for it. Shortcut does nothing.

**P1 — Rainbow AI Tool Buttons**
Four different button colors (green-700, purple-700, amber-700, blue-700) with no semantic meaning. Violates Rarity Rule.

**P1 — No Undo on Rewrite Apply**
Apply replaces editor content irreversibly. No undo capability.

**P2 — Invisible JD Dependency**
Assessment/Remediation/Rewrite disabled with no explanation of why. User must discover JD textarea lives in a different tab.

**P3 — Raw Error Text Dumps**
LaTeX errors and AI failures shown as raw messages. No actionable guidance.

## Minor Observations

- overflow-x-auto on tabs creates false affordance when all tabs fit
- "Resume AI Editor" header name is generic for a "Nail" brand
- v0.1 tag nearly illegible — use text-zinc-700 or remove
- pre + font-sans pattern breaks structured alignment in results
