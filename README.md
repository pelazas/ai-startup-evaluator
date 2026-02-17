# AI startup audit

Initial MVP project scaffold with monorepo structure:

- `/frontend`: Next.js 14 app
- `/backend`: FastAPI + SQLAlchemy + Alembic app
- `docker-compose.yml`: PostgreSQL 15 with pgvector

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 18+

## Environment

Copy `.env.example` to `.env` and update values as needed.

Required variables:

- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_ALGORITHM`
- `JWT_EXPIRE_DAYS`
- `OPEN_ROUTER_API_KEY`
- `COHERE_API_KEY`
- `NEXT_PUBLIC_API_BASE_URL`

## Run PostgreSQL

```bash
docker compose up -d postgres
```

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Health endpoint:

```bash
curl http://localhost:8000/health
```

## Document Pipeline (Raw -> Processed -> Seed -> Vector DB)

This is the end-to-end flow for document ingestion:

1. Put source files in:

- `backend/raw_documents/`
- Supported formats: `.pdf`, `.txt`, `.md`

2. Preprocess raw documents into normalized + classified outputs:

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/preprocess_documents.py --rules-only --review-threshold 0.30
```

Outputs:

- Processed docs: `backend/processed_documents/<collection>/<doc_id>/`
- Review queue (low confidence): `backend/processed_documents/review_queue/`
- Ingestion-ready seed docs: `backend/seed_documents/<collection>/`

3. Ingest seed docs into pgvector collections:

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/ingest_seed_collections.py --embedding-model openai/text-embedding-3-small --verify
```

Notes:

- `--verify` runs vector and keyword search checks after ingestion.
- Use `--append` to keep existing rows.
- Use `--resume` to continue from checkpoints in `backend/.ingestion_state/checkpoints/`.
- Current vector columns are 1024-dim; if model dims differ, ingestion auto-adapts by truncate/pad.

4. Optional: Scrape YC companies as raw input:

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/scrape_yc_companies.py
```

This writes a raw markdown export to `backend/raw_documents/`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000).
