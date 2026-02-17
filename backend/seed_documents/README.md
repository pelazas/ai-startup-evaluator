# Seed Documents for Vector Collections

Add markdown documents under these folders:

- `founder_principles_docs/`
- `ai_market_data_docs/`
- `startup_examples_docs/`
- `technical_constraints_docs/`
- `personal_profile_docs/`

Document format:

- Use `# Title` on the first line.
- Use `## Section Heading` for major sections.
- Write normal paragraphs under each section.

Ingestion script behavior:

- Reads all `*.md` files in each folder.
- Splits by markdown sections and semantic chunk boundaries.
- Stores metadata JSONB with `source`, `title`, and `section`.

Run ingestion:

```bash
cd backend
PYTHONPATH=. python scripts/ingest_seed_collections.py --verify
```

Use `--append` to keep existing rows and insert additional chunks.

OpenRouter is the default provider and uses `OPEN_ROUTER_API_KEY`.
Optional provider/model flags:

```bash
PYTHONPATH=. python scripts/ingest_seed_collections.py --embedding-provider openrouter --embedding-model cohere/embed-english-v3.0 --verify
PYTHONPATH=. python scripts/ingest_seed_collections.py --embedding-provider cohere --embedding-model embed-english-v3.0 --verify
```
