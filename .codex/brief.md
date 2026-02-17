# Epic Brief — AI Startup Idea Evaluator (MVP)

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