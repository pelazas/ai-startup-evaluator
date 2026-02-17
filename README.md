# CRAG AI Startup Evaluator

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

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000).
