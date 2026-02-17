# Seed Documents for Vector Collections

This folder contains ingestion-ready markdown documents and optional metadata sidecar files.

Collections:

- `founder_principles_docs/`
- `ai_market_data_docs/`
- `startup_examples_docs/`
- `technical_constraints_docs/`
- `personal_profile_docs/`

Recommended workflow:

1. Put mixed raw files (`.pdf`, `.txt`, `.md`) into `backend/raw_documents/`.
2. Run preprocessing to extract, normalize, classify, and route into this seed folder.
3. Review low-confidence docs in `backend/processed_documents/review_queue/`.
4. Run ingestion to chunk, embed, and upsert into vector tables.

Preprocess command:

```bash
cd backend
PYTHONPATH=. python scripts/preprocess_documents.py
```

Ingestion command:

```bash
cd backend
PYTHONPATH=. python scripts/ingest_seed_collections.py --verify
```

Useful ingestion flags:

- `--append`: keep existing rows
- `--resume`: resume from checkpoint in `backend/.ingestion_state/checkpoints/`
- `--dry-run`: compute chunks without DB writes
- `--force-reindex`: ignore chunk hash dedupe

Provider config:

- Default provider: OpenRouter
- Required key for default: `OPEN_ROUTER_API_KEY`
- Default embedding model: `cohere/embed-english-v3.0` (1024 dimensions)

Optional provider/model overrides:

```bash
PYTHONPATH=. python scripts/ingest_seed_collections.py --embedding-provider openrouter --embedding-model cohere/embed-english-v3.0 --verify
PYTHONPATH=. python scripts/ingest_seed_collections.py --embedding-provider cohere --embedding-model embed-english-v3.0 --verify
```
