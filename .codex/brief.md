# Epic Brief — AI Startup Idea Evaluator (MVP)

## Project Status Snapshot (February 17, 2026)

### Done

- Monorepo structure with `/frontend` and `/backend`.
- Docker Compose + PostgreSQL 15 + pgvector, Alembic migrations, SQLAlchemy models.
- Auth foundation (signup/login/logout) and authenticated app shell.
- Profile CRUD (`POST /api/profiles`, `GET /api/profiles/me`, `PUT /api/profiles/me`).
- Profile snapshot create/reuse logic integrated with evaluations.
- Profile UX upgrade:
  - Richer founder classification fields.
  - Timezone is auto-inferred from Location (Open-Meteo geocoding), and read-only.
  - App naming updated to **AI Startup Audit** in navbar/layout.
- Evaluation backend flow implemented:
  - 4-step graph (Intake -> Retrieval -> Critic -> Verdict).
  - SSE progress streaming and final result event.
  - Evaluation persistence with statuses (`pending`, `completed`, `partial`, `failed`).
- Evaluation frontend flow implemented:
  - `/evaluate` idea input + validation.
  - Real-time progress UI.
  - `/evaluations/[id]` results page with verdict badge, radar chart, risks, collapsible dimensions, sources, history modal.

### Missing / Broken (Current Priority)

- Result quality is inconsistent for some runs (all dimensions become unavailable).
- Critic output parsing is currently too brittle when model shape deviates.
- Partial result semantics lead to confusing outcomes (for example, NO-GO with `0/100` from unavailable scores).
- Sources section is hard to read:
  - duplicate entries,
  - raw/opaque IDs,
  - weak provenance visibility.
- Observability is limited for debugging bad evaluations (insufficient per-node diagnostics exposed to UI).

### Next Work (Ordered)

1. Harden critic parsing and fallback behavior so each dimension degrades gracefully instead of collapsing to unavailable.
2. Improve verdict calculation for partial runs (avoid misleading `0/100`; compute from available dimensions and communicate confidence clearly).
3. Deduplicate and format evidence sources (clean labels, capped list, consistent ordering, readable metadata).
4. Add evaluation diagnostics and better error payloads from backend to frontend for transparent failure reasons.
5. Polish results UX for partial outputs (clear badges, actionable messages, and stronger confidence explanation).

## Problem / Opportunity

Technical founders frequently receive **vague, optimistic validation** for startup ideas. That feedback is often ungrounded and fails to surface key risks early (market saturation, GTM feasibility, technical defensibility, founder constraints, and timing).

This product provides an **evidence-weighted stress test**: it retrieves relevant evidence, scores each evaluation dimension, and produces a structured verdict that is intentionally skeptical and explicit about uncertainty.

## Target User

- Primary: **Technical founder** (initially single-user / personal tool, shareable via web UI)
- Secondary (later): other founders/teams who want consistent idea evaluation

## Goals (MVP)

1. **Evidence-grounded evaluation** of a startup idea across 5 dimensions:
  - Market, Technical, Distribution, Founder Fit, Timing
2. Produce a deterministic, structured output:
  - Dimension scores (0–100), overall score, GO/CONDITIONAL/NO-GO, top risks, sources used
3. Provide a **clean wizard UX**:
  - Authentication (Signup/Login) → profile setup (if needed) → idea input → evaluation progress → results
4. **Exportable output**:
  - Generate a **PDF** report suitable for sharing/saving
5. Authenticated persistence:
  - Email/password auth (Signup, Login, Logout)
  - Store profile + evaluation history server-side per user (available across devices)

## Non-Goals (MVP)

- Web fallback / live market scanning
- Corrective routing loops (CRAG / Self-RAG)
- Reranking layer / advanced retrieval optimization
- Team collaboration / org workspaces / sharing evaluations across multiple users (beyond basic auth)
- Advanced account management (email verification, password reset) beyond simple MVP auth
- Complex evidence chunk viewer (MVP shows a simple source list)

## MVP Scope (High-Level Behavior)

### Input

- **Founder Profile** (required before first evaluation; editable anytime from Profile page)
  - Past evaluations remain unchanged (each evaluation stores a profile snapshot)
- **Idea Input**:
  - Freeform description (required)
  - Optional: target customer, problem statement
  - Optional: single-select category fields (startup type + B2B/B2C)

### Core Path

- Intake → retrieval across 5 collections → strategic critic scoring → verdict

### Collections (seed data)

Start with **1–3 key documents per collection**:

- founder_principles
- ai_market_data
- startup_examples
- technical_constraints
- personal_profile (captured via questionnaire)

## Verdict & Scoring Policy (MVP)

- **Weights:** equal (20% each dimension)
- **Overall score:** average of 5 dimension scores
- **Verdict thresholds (moderate):**
  - GO: overall ≥ 70
  - CONDITIONAL: 55–69
  - NO-GO: < 55
- **No “critical dimension forces NO-GO” guardrail** in MVP.
- **Weak evidence behavior:** always produce a verdict, but:
  - Add “Low confidence due to limited evidence”
  - Be more conservative in scoring and rationale

## UX Summary (MVP)

- Wizard steps:
  1. Authentication (Signup/Login)
  2. Profile Setup (required if profile not yet created)
  3. Describe Idea
  4. Evaluation progress (Intake → Retrieval → Critic → Verdict)
  5. Results (progressive disclosure)
- Results first view:
  - Verdict + overall score + radar chart + top risks
- Expandable:
  - Dimension details for all 5 dimensions
- Evidence:
  - Simple “Sources Used” list at the bottom
- History:
  - Shown at bottom of results; “View All” opens modal
- Export:
  - PDF includes results + idea input + short founder profile summary
- Profile management:
  - Profile is editable anytime via a dedicated Profile page
  - Past evaluations remain unchanged (each evaluation stores a profile snapshot)

## Success Criteria (MVP Acceptance)

- A new user can:
  1. Sign up and log in (email + password)
  2. Complete profile setup
  3. Submit an idea
  4. See evaluation progress states
  5. Receive a structured verdict with 5 dimension scores + overall decision
  6. See sources used
  7. Export a PDF report
  8. See their evaluation in their account history and reopen it later (including from another device)
  9. Edit their profile later; profile changes affect future evaluations only
- Verdict policy behaves as specified (weights + thresholds).
- Partial failures show partial results and clearly mark missing dimensions.

## Key Risks / Constraints

- Quality depends on seed corpus breadth; MVP starts minimal by design.
- LLM inference cost/latency variability (via OpenRouter) may affect experience; MVP mitigates with simple progress UI.

## Timeline

- Rapid prototype: **1–2 weeks**.

&nbsp;
