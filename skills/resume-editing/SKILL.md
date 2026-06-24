---
name: resume-editing
description: |
  Professional resume editing and optimization skill for engineers. Use when users:
  (1) ask to "edit my resume", "improve my resume", or "rewrite my CV"
  (2) want to tailor a resume for a specific job description
  (3) need gap analysis between their resume and target roles
  (4) want quantified achievements, stronger action verbs, or ATS optimization
  (5) ask about resume formatting, structure, or content review
  Keywords: resume, CV, job application, career, ATS, gap analysis, rewrite, tailoring
---

# Resume Editing

Professional resume optimization for software engineers and technical roles. This skill covers the full pipeline: parsing, gap analysis, content rewriting, tailoring, formatting, and final review.

## Core Philosophy

> **A resume is not a biography. It's a targeted marketing document that must pass an ATS filter and convince a human reader in 6 seconds.**

Every edit decision flows from this principle. If a change doesn't help the resume get past the initial screen or make a stronger case in the first glance, don't make it.

## The Resume Editing Pipeline

```
┌──────────┐   ┌──────────┐   ┌───────────┐   ┌────────────┐   ┌──────────┐
│  1. Parse │ → │ 2. Analyze│ → │ 3. Gap    │ → │ 4. Rewrite │ → │ 5. Review│
│  & Import │   │  Current  │   │  Analysis │   │  & Tailor  │   │ & Polish │
└──────────┘   └──────────┘   └───────────┘   └────────────┘   └──────────┘
                                        ← user feedback loop →
```

---

## Phase 1: Parse & Import

Read the resume into a structured representation. Capture ALL content before making any edits.

### What to parse:
- **Contact**: name, phone, email, location, LinkedIn/GitHub/portfolio URLs
- **Summary/Objective**: personal statement
- **Skills**: technical stack, tools, methodologies
- **Experience**: company, title, dates, bullet points for each role
- **Education**: institution, degree, dates
- **Projects**: name, description, tech used, dates
- **Publications/Certifications**: if present

### Parse checklist:
- [ ] Read full resume content
- [ ] Identify all sections and their structure
- [ ] Note any formatting issues (inconsistent bullets, spacing)
- [ ] Capture metadata (file format, length, target role if stated)
- [ ] Identify the resume's current target/objective (if any)

---

## Phase 2: Analyze Current Resume

Evaluate the resume against baseline quality criteria before making changes.

### Scoring dimensions (score 1-5 each):

| Dimension | What to evaluate |
|-----------|-----------------|
| **Impact** | Do bullet points show RESULTS, not just responsibilities? |
| **Specificity** | Are there numbers, percentages, timelines? |
| **Signal density** | Is every line contributing? Any filler? |
| **Structure** | Is information easy to scan? Sections logical? |
| **Action verbs** | Strong openers? (built, designed, led, optimized) vs weak (responsible for, involved in) |
| **ATS readiness** | Can a parser extract all key information? |

### Watch for these anti-patterns:
- **Responsibilities list**: "Responsible for maintaining the API" → "Redesigned the API gateway, reducing p99 latency by 40%"
- **Tech laundry list**: Listing skills without context of how they were used
- **Passive voice**: "Was involved in the migration" → "Led the monolith-to-microservices migration across 12 services"
- **Generic claims**: "Hardworking team player" → no evidence needed, not a biography
- **Missing quantification**: Any achievement without a number attached is suspicious

---

## Phase 3: Gap Analysis

Compare the resume against target job description(s) or role expectations.

### Process:
1. Extract key requirements from JD: required skills, preferred skills, years of experience, domain expertise
2. Map each requirement to the resume: present? implied? missing?
3. Identify **critical gaps** (required skills absent) vs **nice-to-have gaps**
4. Flag **hidden strengths** — skills/experience in the resume that the user hasn't positioned as relevant to this role

### Gap types and responses:

| Gap type | Strategy |
|----------|----------|
| **Missing keyword** | Add if user has the experience but didn't phrase it, add to skills section or context bullets |
| **Missing experience** | Can't fabricate. Reframe adjacent experience or note for cover letter |
| **Under-positioned** | User has the skill but it's buried. Promote to higher visibility |
| **Over-positioned** | Too much detail on irrelevant experience. Condense to free space |
| **Weak evidence** | Claims skill but with weak examples. Rewrite bullets with stronger impact framing |

### Output:
- Gap table: JD requirement → resume status → action needed
- Prioritized rewrite targets (what to fix first for maximum impact)
- Deleted: what to cut (irrelevant filler eating precious space)

---

## Phase 4: Rewrite & Tailor

This is the core editing phase. Apply these techniques systematically.

### 4a. STAR → CAR Transformation

Traditional STAR (Situation, Task, Action, Result) is too verbose for resumes. Use **CAR** (Challenge, Action, Result):

| Format | Template |
|--------|----------|
| **Weak** | Responsible for [task] |
| **Good** | [Action] [what you did] resulting in [outcome] |
| **Strong** | [Challenge/Context] → [Action] → [Quantified Result] |

### 4b. Bullet Point Formula

**Template (for technical roles):**
```
[Strong action verb] [what you built/designed/led] using [key technologies], achieving [quantified impact] by [% or $ or time].
```

Examples:
- ❌ "Maintained the CI/CD pipeline"
- ✅ "Redesigned the CI/CD pipeline with GitHub Actions + ArgoCD, cutting deployment time from 15min to 90s and reducing rollback rate by 60%"

- ❌ "Worked on database optimization"
- ✅ "Optimized PostgreSQL query performance by redesigning indexes and partitioning 4 high-traffic tables, reducing avg query latency from 320ms to 45ms"

### 4c. Action Verb Hierarchy

Start each bullet with the strongest possible verb. Choose based on what you actually did:

| Level | Verbs |
|-------|-------|
| **Built/Architected** | designed, built, architect, implemented, developed, created, established, deployed, launched, constructed |
| **Optimized** | optimized, reduced, improved, accelerated, streamlined, automated, refactored, modernized, consolidated |
| **Led/Owned** | led, directed, managed, drove, owned, spearheaded, orchestrated, coordinated, chaired |
| **Analyzed** | analyzed, evaluated, assessed, audited, benchmarked, modeled, validated, diagnosed |
| **Enabled** | enabled, empowered, mentored, trained, documented, standardized, evangelized |

**Never use**: responsible for, involved in, participated in, worked on, helped with, tasked with.

### 4d. Quantification Cheat Sheet

Strongest → weakest quantification. Always prefer the leftmost column:

| Time saved | Money impact | Scale | Performance | Quality |
|------------|-------------|-------|-------------|---------|
| reduced by X% | saved $XM | served X users | reduced latency by X% | raised accuracy from X% to Y% |
| cut from X to Y | generated $X revenue | processed X records/day | improved throughput by Xx | reduced error rate by X% |
| accelerated by Xx | reduced cost by X% | managed X nodes/services | p99 from Xms to Yms | increased test coverage from X% to Y% |
| automated X hours/week | | scaled from X to Y | handled X concurrent requests | achieved X% uptime |

### 4e. Technical Skills Section

Structure as a table or categorized list — never a paragraph:

```
**Languages**: Python, TypeScript, Go, Rust
**Frameworks**: FastAPI, Next.js, React, LangChain, PyTorch
**Infrastructure**: Kubernetes, Docker, Terraform, AWS (ECS, RDS, Lambda)
**Tools**: Prometheus, Kafka, ELK, Git, ArgoCD
```

### 4f. Length Rules

- **Summary**: 2-3 lines max (or delete entirely — controversial, but often wasted space)
- **Each job**: 3-6 bullets (more recent = more bullets, oldest = condensed)
- **Each bullet**: 1-2 lines. Never wrap to 3+ lines
- **Total resume**: 1 page if <10 years exp, 2 pages max if 10+ years
- **Projects section**: 2-3 key projects, 2-3 bullets each
- **Education**: After first job, just degree + school. Drop GPA, coursework, etc.

### 4g. Tailoring for Specific Roles

| Role type | Emphasize |
|-----------|-----------|
| **SWE (general)** | system design, code quality, scalability, team impact |
| **AI/ML Engineer** | model performance metrics, data pipelines, training infra |
| **AI Agent Engineer** | tool use, function calling, agent loop, context mgmt, orchestration |
| **DevOps/SRE** | reliability metrics, automation, incident response, observability |
| **Staff/Principal** | technical strategy, cross-team impact, mentorship, architecture decisions |
| **Startup** | ownership breadth, speed, resourcefulness, direct user impact |
| **Big Tech** | scale (users/data), collaboration, process, metrics-driven |

---

## Phase 5: Review & Polish

Final quality gate before delivery.

### Technical review:
- [ ] All links (LinkedIn, GitHub, portfolio) resolve correctly
- [ ] Dates are consistent format (YYYY.MM or YYYY.MM—YYYY.MM)
- [ ] No orphaned bullet points or inconsistent spacing
- [ ] All company names, titles, and tech names are correctly capitalized
- [ ] No first-person pronouns (I, my, we) — resume is implied first-person
- [ ] No periods at end of bullet points (modern convention — but be consistent)

### ATS check:
- [ ] No tables (most ATS can't parse them)
- [ ] No images/icons (ATS ignores them)
- [ ] Standard section headers (Experience, Education, Skills — not creative alternatives)
- [ ] No headers/footers with critical info (ATS often misses them)
- [ ] .docx or .pdf? Prefer .docx for ATS, .pdf for human review
- [ ] No text in columns (ATS reads left-to-right, top-to-bottom)
- [ ] Keywords from the JD appear naturally in experience bullets, not just skills section

### Content check:
- [ ] Most impressive achievement is first bullet of each role
- [ ] At least 80% of bullets are quantified
- [ ] No weak openers (responsible for, involved in)
- [ ] Every bullet passes "so what?" test
- [ ] No jargon that a recruiter wouldn't understand
- [ ] Consistent tense: current role = present tense, past roles = past tense

### Final polish:
- [ ] Read the resume aloud — fix awkward phrasing
- [ ] Check for overused words (if "led" appears 5 times, vary it)
- [ ] Verify contact info is prominent and complete
- [ ] Ensure the resume tells a coherent story from first to last entry

---

## Script Execution

When performing resume editing, use the helper scripts:

```bash
# Start fresh: set up the editing environment
python skills/resume-editing/scripts/setup.py --resume <path> [--jd <path>]

# Validate the final output
python skills/resume-editing/scripts/validate.py --resume <path>
```

---

## References

- `references/action-verbs.md` — Complete action verb catalog organized by category
- `references/resume-templates.md` — Proven structural templates for different roles
- `references/ats-guidelines.md` — ATS parser behavior and formatting recommendations
- `references/bullet-examples.md` — Before/after examples for common resume patterns

## Examples

### Before → After: Summary

**Before:**
> Experienced software engineer with 5+ years of experience in backend development. Proficient in Python, Java, and cloud technologies. Looking for challenging opportunities.

**After:**
> Backend engineer with 5+ years building distributed systems at 10M+ user scale. Specialize in Python/Go microservices architecture, PostgreSQL optimization, and Kubernetes deployment. Reduced infrastructure costs by 35% across 3 major platform migrations.

### Before → After: Bullet Point

**Before:**
> Responsible for building and maintaining the API layer for the customer platform.

**After:**
> Designed and implemented RESTful API layer handling 50K+ RPM with FastAPI + PostgreSQL, achieving p99 latency under 200ms and enabling 3 downstream consumer integrations.

---

## Important Constraints

- **Never fabricate experience or qualifications.** Rewriting is about framing existing experience better, not inventing.
- **Never remove dates** to hide employment gaps — honest framing always wins.
- **Never copy-paste JD keywords** verbatim without contextualizing them — ATS detects keyword stuffing.
- **One skill at a time** — complete a full pass for one target role before tailoring for another.
- **Preserve the user's voice** — don't inflate language beyond what the user can defend in an interview.
