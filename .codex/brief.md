# Epic Brief — AI Startup Audit (Current State)

## Project Snapshot (February 18, 2026)

### What Is Implemented

- Monorepo with:
  - `frontend/` (Next.js 14 + TypeScript)
  - `backend/` (FastAPI + SQLAlchemy + Alembic)
- PostgreSQL 15 + pgvector with:
  - core tables (`users`, `profiles`, `profile_snapshots`, `evaluations`)
  - 5 vector collection tables (`*_docs`) with vector + FTS indexes
- Auth flow is complete:
  - `POST /api/auth/signup`
  - `POST /api/auth/login`
  - `GET /api/auth/me`
  - JWT bearer auth, passlib+bcrypt hashing, protected dependencies
- Profile flow is complete:
  - `POST /api/profiles`
  - `GET /api/profiles/me`
  - `PUT /api/profiles/me`
  - rich founder schema persisted and reused via profile snapshots
- Evaluation flow is live with streaming:
  - `POST /api/evaluations` (SSE progress + final result)
  - graph nodes: `intake -> retrieval -> web_retrieval -> critic -> verdict`
  - statuses: `pending`, `completed`, `partial`, `failed`
- Results UI is implemented:
  - verdict + score + radar chart
  - dimension details and rationale
  - source observability (why used, supporting dimensions)
  - idea title, idea summary, founder-fit summary
  - history view and detail page
- PDF export is implemented:
  - `POST /api/evaluations/{id}/export`
  - ReportLab-based branded PDF
  - accepts chart image payload from frontend and embeds radar chart
- Ingestion pipeline is implemented:
  - raw docs (`pdf/txt/md`) -> preprocess/classify -> seed docs -> chunk/embed/ingest
  - supports Cohere and OpenRouter embedding providers

### Current Product Behavior

- Home (`/`) is a dashboard with previous idea cards and quick action CTA.
- Authenticated users are not forced to `/login`; routing depends on `has_profile`.
- Evaluation input supports optional live web retrieval toggle (`web_enabled`).
- Retrieval is hybrid:
  - internal vector + keyword over 5 collections
  - optional Tavily web search layer
- Critic scores 5 dimensions on 0-100 scale:
  - `market`, `technical`, `distribution`, `founder_fit`, `timing`
- Founder fit includes profile-based heuristic blending to reduce LLM-only noise.
- Verdict thresholds:
  - `GO >= 70`, `CONDITIONAL >= 55`, else `NO-GO`

### High-Value Capabilities Already Present

- Parse diagnostics exposed to frontend for observability
- Evidence mix tracking (`internal_sources`, `web_sources`, `total_sources`)
- Idea tagging/folder classification for filtering (`idea_tags`, `idea_folder`)
- Filtered evaluation listing by tag/folder/query and AI-assisted query parsing

### Known Gaps / Risks

- Some rationale text still falls back to synthetic explanations when critic output is weak.
- Web retrieval quality depends on Tavily availability and network reliability.
- Auth token is runtime-memory only (simple MVP model; no refresh/session persistence).
- Local history is still stored in frontend localStorage in addition to server retrieval.

### Near-Term Priorities

1. Keep improving rationale clarity and source-to-claim traceability.
2. Add tests around critic parsing, founder-fit blending, and export payload handling.
3. Tighten UX consistency between dashboard, evaluate, and results surfaces.
4. Expand seed corpus quality and improve routing/classification confidence.
