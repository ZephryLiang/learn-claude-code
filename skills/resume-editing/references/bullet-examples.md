# Bullet Point Before/After Examples

## Backend Engineering

**Before:** Responsible for maintaining the user authentication service.
**After:** Redesigned the authentication service using FastAPI + JWT + Redis session store, reducing login latency by 60% and supporting 100K concurrent users.

**Before:** Worked on database optimization to improve query performance.
**After:** Optimized PostgreSQL query performance by redesigning indexes and partitioning 4 high-traffic tables, reducing avg query latency from 320ms to 45ms.

**Before:** Participated in migrating the monolithic application to microservices.
**After:** Led the monolith-to-microservices migration, decomposing a 200K-line Rails app into 8 independently deployable Go services, reducing deploy-related incidents by 70%.

**Before:** Helped improve the CI/CD pipeline.
**After:** Redesigned the CI/CD pipeline with GitHub Actions + ArgoCD, cutting deployment time from 15min to 90s and reducing rollback rate by 60%.

## AI/ML Engineering

**Before:** Built a chatbot using LangChain.
**After:** Architected an LLM-powered customer support agent using LangChain + RAG (FAISS), serving 50K+ conversations/month with 85% first-response resolution rate.

**Before:** Fine-tuned large language models for better performance.
**After:** Fine-tuned CodeLlama-13B with LoRA, raising multi-table SQL execution accuracy from 33% to 77% on the Spider benchmark.

**Before:** Worked on prompt engineering to improve model outputs.
**After:** Designed a prompt chaining strategy with dynamic few-shot selection, reducing hallucination rate by 40% in production LLM outputs.

**Before:** Built a recommendation system.
**After:** Built a real-time recommendation engine processing 10K events/sec using Kafka + FAISS vector search, improving click-through rate by 25%.

**Before:** Developed a system that uses AI to help non-technical users query databases.
**After:** Developed a text-to-SQL Agent system enabling non-technical users to query enterprise databases via natural language, covering multi-table JOINs and nested subqueries with 95%+ success rate on common patterns.

## Frontend Engineering

**Before:** Upgraded the frontend from the old framework to React.
**After:** Modernized the frontend from AngularJS to Next.js 14 (App Router + Server Components), reducing bundle size by 65% and improving Lighthouse score from 45 to 92.

**Before:** Built reusable components.
**After:** Designed a component library of 40+ reusable UI components (Storybook + Radix UI + Tailwind), adopted by 3 product teams and reducing UI development time by 30%.

**Before:** Fixed performance issues.
**After:** Diagnosed and resolved render performance bottlenecks through React.memo + virtualization (react-window), reducing re-render time from 200ms to 16ms on list-heavy pages.

## DevOps / Infrastructure

**Before:** Responsible for managing Kubernetes clusters.
**After:** Managed 5 production Kubernetes clusters across 3 regions, automating canary deployments and reducing rollback time from 30min to 2min.

**Before:** Set up monitoring for the production environment.
**After:** Built Prometheus + Grafana + ELK observability stack across 50+ services, reducing Mean Time to Detection (MTTD) from hours to under 5 minutes.

**Before:** Automated some deployment tasks.
**After:** Automated the full CI/CD pipeline using Terraform + GitHub Actions, eliminating 10+ hours/week of manual deployment work and achieving 99.95% deployment success rate.

**Before:** Improved system reliability.
**After:** Implemented circuit breaker + rate limiting pattern, improving p99 availability from 99.5% to 99.99% and preventing cascading failures during 3 traffic spikes.

## Engineering Leadership

**Before:** Mentored junior developers.
**After:** Mentored 4 junior engineers through structured onboarding program, with all 4 reaching independent contribution within 3 months (vs. 5-month org average).

**Before:** Led code review process.
**After:** Established code review standards and architecture review process for 15-person engineering org, maintaining >80% code review coverage and reducing production bugs by 45%.

**Before:** Worked on cross-team initiatives.
**After:** Drove cross-team collaboration between Data Platform and Product Engineering teams, delivering the unified analytics API used by 4 product squads.

## Weak Openers → Replace

| Weak | Strong replacement |
|------|-------------------|
| Responsible for [X] | Built / Designed / Led [X] |
| Involved in [X] | Contributed to / Drove / Spearheaded [X] |
| Participated in [X] | Contributed to / Collaborated on [X] |
| Helped with [X] | Enabled / Supported [X] |
| Worked on [X] | Developed / Implemented / Optimized [X] |
| Tasked with [X] | Delivered / Executed / Owned [X] |

## Common Patterns to Fix

### The "Everything + Python" problem
**Before:** Used Python for backend development, data processing, and automation scripts.
**After:** Built the core API in Python (FastAPI), automated ETL pipelines with Python + Airflow, and developed CLI tools for developer productivity — all in Python.

### The "title as verb" problem
**Before:** Led the engineering team.
**After:** Led a team of 5 engineers delivering the payment platform migration, processing $2M+ monthly transaction volume.

### The "obvious technology" problem
**Before:** Used Git for version control.
**After:** Established Git branching strategy (trunk-based development) reducing merge conflicts by 80%.
