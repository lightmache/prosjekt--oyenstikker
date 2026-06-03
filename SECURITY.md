# Security Documentation

## What this system does
Self-hosted semantic search and RAG API. Ingests text, stores vector embeddings in PostgreSQL/pgvector, serves LLM-grounded responses via Ollama. All compute is local.

## Controls implemented
- Secrets: all credentials loaded from environment variables via .env, no secrets in source code
- Authentication: /ingest requires X-API-Key header, uses secrets.compare_digest() to prevent timing attacks
- Rate limiting: per-IP sliding window, 30 req/min, returns HTTP 429 on limit exceeded
- Input validation: content capped at 8000 chars, k capped at 20, model name pattern-matched
- Network: PostgreSQL bound to 127.0.0.1:5432 only
- Database: connection pool with transaction rollback on error, parameterized queries throughout

## Known limitations
- HTTPS/TLS: not implemented, add nginx for any network exposure
- Rate limiting is in-memory only, resets on restart
- Audit logging not implemented
- Firewall/OS hardening is host-level, outside application scope

## Generating an API key
python3 -c "import secrets; print(secrets.token_hex(32))"
