CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding VECTOR(384),
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);