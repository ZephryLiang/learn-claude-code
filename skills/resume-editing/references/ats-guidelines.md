# ATS (Applicant Tracking System) Guidelines

## What ATS Actually Does

ATS software parses resume text into structured fields (name, email, skills, experience, education) and ranks candidates against job descriptions using keyword matching and weighted scoring. **The parser is the bottleneck.**

## Critical Rules

### Do NOT use:
- **Tables** — Most ATS read left-to-right, top-to-bottom and concatenate table cells into gibberish
- **Images/Icons** — ATS cannot read text embedded in images. Profile photos are parsed as noise
- **Headers/Footers** — Many ATS ignore header/footer content entirely. Keep contact info in the body
- **Columns** — Multi-column layouts confuse column-reading ATS (text from column 2 may be appended to column 1)
- **Text boxes** — Word text boxes are often skipped by parsers
- **Charts/Graphs** — Skill bars ("Python ████████░░ 80%") are invisible to ATS
- **Special characters** — Bullets other than standard (•, -, *) may produce garbled output
- **Abbreviations without expansion** — "Implemented RAG pipeline" without "Retrieval-Augmented Generation" spelled out somewhere
- **Creative section headers** — "Where I've Worked" instead of "Experience" — ATS may not match the standard section name

### DO use:
- **Standard section headers**: Experience, Education, Skills, Projects, Certifications
- **Plain text** or standard formatting — bold, italics are fine, but don't rely on visual cues
- **Standard date formats**: YYYY.MM—YYYY.MM or YYYY—YYYY (consistency matters more than format)
- **Full tech names** at least once: "Amazon Web Services (AWS)" not just "AWS"
- **Standard resume file names**: `FirstName_LastName_Resume.pdf` (not `resume_final_v3(2).pdf`)

## Keyword Strategy

```
JD keyword → Where to place it in resume
─────────────────────────────────────────
Python       → Skills section + experience bullets
Kubernetes   → Skills section + experience bullets
REST API     → Experience bullets (contextualized)
Microservices → Experience bullets (contextualized)
Prompt Engineering → Summary (if senior) or bullet (if hands-on)
```

**Critical: Keywords must appear in CONTEXT, not just in the skills list.**
- "Kubernetes" in skills section = keyword match
- "Deployed 15 microservices on Kubernetes with automated canary deployments" = keyword match + evidence

## ATS Testing

Tools to verify ATS compatibility:
1. **Jobscan** — Compare resume against JD and get a match score
2. **TopResume ATS Test** — Upload and check parsed output
3. **Manual test**: Copy-paste resume into a plain text editor. If the structure survives, it'll survive ATS parsing.

## Common ATS Parsing Failures

| Resume feature | ATS sees | Fix |
|---------------|----------|-----|
| `name@email.com` in header | Missing contact info | Put in body text |
| Text in two columns | Jumbled single column | Single column layout |
| Table with skills | Random character string | Comma-separated list |
| "Sr. Software Engineer" as heading | "Software Engineer" parsed as name | Standard format: Company → Title → Dates |
| Company name in logo image | Missing employer | Type company name in body |
| Education in creative format | Missing education | Standard: Institution, Degree, Year |
