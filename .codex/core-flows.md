# Core User Flows (Current)

## Status (February 18, 2026)

All major MVP flows are implemented end-to-end, including auth, profile, evaluation, results, history, and PDF export.

## Flow 1: Authentication

### Signup

1. User opens `/signup`.
2. Submits email + password.
3. Backend: `POST /api/auth/signup` returns JWT + user payload.
4. Frontend stores token in runtime state and routes:
   - `/profile/setup` if `has_profile=false`
   - `/evaluate` if `has_profile=true`

### Login

1. User opens `/login`.
2. Submits email + password.
3. Backend: `POST /api/auth/login` returns JWT + user payload.
4. Frontend routes using `has_profile`.

### Logout

1. User opens profile menu in top nav.
2. Clicks logout.
3. Frontend clears in-memory token and routes to `/login`.

## Flow 2: Profile Setup / Edit

### Profile setup

1. User without profile is routed to `/profile/setup`.
2. User submits full founder profile.
3. Backend: `POST /api/profiles`.
4. Frontend marks profile complete and routes to `/evaluate`.

### Profile edit

1. Logged-in user opens `/profile/edit` from menu.
2. Backend loads profile via `GET /api/profiles/me`.
3. User updates and saves via `PUT /api/profiles/me`.
4. Note: future evaluations use updated profile; historical evaluations keep snapshot state.

## Flow 3: Start Evaluation

1. User opens `/evaluate`.
2. Fills idea form:
   - required: `idea_description`
   - optional: `target_customer`, `problem_statement`, `startup_type`, `market_type`
   - toggle: `web_enabled` (live web retrieval)
3. Frontend calls `POST /api/evaluations` and consumes SSE stream.

## Flow 4: Evaluation Runtime (SSE)

Node progression emitted to UI:

1. `intake`
2. `retrieval`
3. `web_retrieval` (only if `web_enabled=true`)
4. `critic`
5. `verdict`

Backend returns final `result` payload with:

- scores/verdict/confidence
- dimension analyses
- top risks
- evidence sources + evidence mix
- parse diagnostics
- idea title/summary/founder-fit summary
- tags/folder metadata

## Flow 5: Results Screen

Results page (`/evaluations/[id]`) shows:

- idea title
- verdict badge + overall score
- radar chart
- narrative idea evaluation paragraph
- top 3 risks
- dimension details (expandable)
- resources consulted with hover doc list
- founder-idea fit section
- sources used list with provenance fields
- previous evaluations

## Flow 6: Home Dashboard

Root page (`/`) behavior:

- Logged out: prompt to login
- Logged in: dashboard summary + CTA
- Previous AI ideas shown as compact cards with:
  - verdict badge
  - score pill
  - concise idea text
  - timestamp
  - details link

## Flow 7: History and Re-open

1. User opens previous evaluation from dashboard or results history section.
2. Frontend fetches server result (`GET /api/evaluations/{id}`) and renders same results component.
3. Local history cache is also maintained for instant display.

## Flow 8: PDF Export

1. User clicks "Download PDF Report" on results page.
2. Frontend serializes radar chart SVG to PNG data URL.
3. Frontend calls `POST /api/evaluations/{id}/export` with payload:
   - `chart_image_data_url`
   - optional branding fields (`company_name`, `company_tagline`, `primary_color_hex`, `custom_sections`)
4. Backend generates branded PDF with ReportLab and returns file download.

## Flow 9: Document Pipeline (Operational)

1. Put raw files in `backend/raw_documents/`.
2. Run preprocess:
   - `python scripts/preprocess_documents.py`
3. Route results to:
   - `processed_documents/<collection>/...`
   - `seed_documents/<collection>/...`
   - low-confidence files -> `processed_documents/review_queue/`
4. Run ingestion:
   - `python scripts/ingest_seed_collections.py`
5. Validate retrieval with `--verify` option.

## Key Operational Notes

- Partial runs are supported and surfaced as `status=partial`.
- Failed runs return `status=failed` plus error context.
- Web retrieval is optional and governed by env config (`WEB_SEARCH_ENABLED`, `TAVILY_API_KEY`).
