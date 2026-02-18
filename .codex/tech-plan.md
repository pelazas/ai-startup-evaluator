# Technical Architecture Plan (Current Implementation)

## Snapshot (February 18, 2026)

This document reflects the code that is currently running in the repo, not a future target state.

## Stack

### Frontend

- Next.js 14 (App Router)
- React + TypeScript
- Custom CSS (`frontend/app/globals.css`)
- Custom SVG radar chart component (not Chart.js)
- Fetch/Axios-style API helpers in `frontend/lib`

### Backend

- FastAPI
- SQLAlchemy 2.x + Alembic
- PostgreSQL + pgvector
- LangGraph orchestration
- JWT auth via `python-jose`
- Password hashing via passlib+bcrypt
- ReportLab for PDF generation

### AI + Retrieval

- OpenRouter chat completions for:
  - idea structuring
  - critic scoring
  - title/tags/summaries generation
- Embeddings via:
  - OpenRouter embeddings (supported)
  - Cohere (supported in ingestion tooling)
- Hybrid retrieval:
  - vector similarity + full-text search on internal collections
  - optional Tavily web retrieval

## Backend Architecture

## API Routers

- `backend/app/api/routes/auth.py`
  - `POST /api/auth/signup`
  - `POST /api/auth/login`
  - `GET /api/auth/me`
- `backend/app/api/routes/profiles.py`
  - `POST /api/profiles`
  - `GET /api/profiles/me`
  - `PUT /api/profiles/me`
- `backend/app/api/routes/evaluations.py`
  - `POST /api/evaluations` (SSE)
  - `GET /api/evaluations`
  - `GET /api/evaluations/{id}`
  - `POST /api/evaluations/{id}/export`

## Evaluation Graph

Defined in `backend/app/langgraph/graph.py`:

1. `intake`
2. `retrieval`
3. `web_retrieval`
4. `critic`
5. `verdict_step` (emits as `verdict` in SSE)

State shape in `backend/app/langgraph/state.py` includes:

- idea input + profile
- structured idea/title/tags/folder
- internal/web merged chunks
- scores, rationales, diagnostics
- verdict, evidence sources, evidence mix
- summaries

## Retrieval

### Internal

`backend/app/services/retrieval_service.py`:

- per-collection hybrid search
- vector + keyword results merged and deduped
- retrieval metadata:
  - `retrieval_method`
  - `retrieval_reason`

### Web

`backend/app/services/web_search_service.py`:

- Tavily API integration
- guarded by env:
  - `WEB_SEARCH_ENABLED`
  - `TAVILY_API_KEY`
  - timeout/max-results settings
- normalized as collection `web`

## Critic + Verdict Logic

### Critic node (`backend/app/langgraph/nodes/critic.py`)

- normalizes multiple possible LLM output shapes
- handles missing/invalid scores gracefully
- normalizes 1-10 scales into 0-100
- enriches missing rationales from retrieved evidence
- blends founder-fit score with profile heuristic
- emits `parse_diagnostics`

### Verdict node (`backend/app/langgraph/nodes/verdict.py`)

- computes overall + verdict thresholds
- dedupes and formats evidence sources
- computes `evidence_mix` (internal/web totals)
- generates human-readable `idea_summary` and `founder_fit_summary`

## Persistence

`backend/app/services/evaluation_service.py`:

- creates pending evaluation row
- persists normalized scores and analyses
- stores metadata inside `dimension_analyses.__meta__`:
  - `idea_title`, `idea_summary`, `founder_fit_summary`
- stores classification metadata:
  - `idea_tags`, `idea_folder`
- status transitions:
  - `failed` (0 dimensions)
  - `partial` (1-4 dimensions)
  - `completed` (5 dimensions)

## PDF Export

Current export implementation is ReportLab-based (Platypus), not HTML-to-PDF.

`POST /api/evaluations/{id}/export` accepts:

- `chart_image_data_url`
- `company_name`
- `company_tagline`
- `primary_color_hex`
- `custom_sections`

Frontend currently sends the radar chart PNG payload from the rendered SVG.

## Frontend Architecture

## Auth and Shell

- `frontend/contexts/auth-context.tsx`
  - runtime token + user state
  - route decisions on login/signup (`has_profile`)
- `frontend/app/app-shell.tsx`
  - top nav with profile menu

## Pages

- `/` dashboard (`frontend/app/page.tsx`)
- `/login`, `/signup`
- `/profile/setup`, `/profile/edit`
- `/evaluate`
- `/evaluations/[id]`

## Evaluation Client Layer

`frontend/lib/evaluations.ts`:

- SSE stream parsing (`streamEvaluation`)
- local history cache helpers
- fetch single/list/filtered evaluations
- PDF download helper with export payload support

## Data Model Highlights

### Core evaluation fields

- input: idea text + optional fields
- outputs:
  - 5 dimension scores
  - overall score
  - verdict
  - top risks
  - evidence sources
  - diagnostics
- metadata:
  - tags/folder
  - confidence/status/error

### Vector collections

- `founder_principles_docs`
- `ai_market_data_docs`
- `startup_examples_docs`
- `technical_constraints_docs`
- `personal_profile_docs`

Each has embedding + tsvector indexes.

## Ingestion and Data Ops

## Preprocess

`scripts/preprocess_documents.py`:

- reads mixed file types from raw docs
- normalization + classifier routing
- outputs processed + seed docs
- review queue for low-confidence routing

## Ingest

`scripts/ingest_seed_collections.py`:

- semantic chunking (`RecursiveCharacterTextSplitter`)
- adaptive chunk profile by doc size
- embedding provider abstraction (OpenRouter/Cohere)
- retries, checkpoints, optional verification

## Scrapers

- `scripts/scrape_yc_companies.py`
- `scripts/scrape_yc_active_founders.py`

Outputs feed `backend/raw_documents/`.

## Current Technical Risks

1. Strong reliance on external model/output consistency at runtime.
2. Web retrieval can silently degrade when Tavily/network is unavailable.
3. Mixed server + local history sources can diverge temporarily in UI.
4. Limited automated tests around graph nodes and PDF output regressions.

## Recommended Next Engineering Steps

1. Add unit tests for critic normalization, founder-fit blending, and verdict aggregation.
2. Add integration tests for SSE event contract and partial/failed runs.
3. Add PDF export tests (with and without chart payload).
4. Add observability counters for web retrieval success/failure and fallback usage.
