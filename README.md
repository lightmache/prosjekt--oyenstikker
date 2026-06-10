# prosjekt–øyenstikker

A containerized multi-service data ingestion and retrieval system designed for structured observational datasets, combining API ingestion, object storage, and semantic search.

---

## Overview

This system implements a full pipeline for ingesting, storing, and querying structured and semi-structured data:

- Ingestion API (FastAPI)
- Metadata + vector storage (PostgreSQL + pgvector)
- Object storage (MinIO, S3-compatible)
- Semantic + keyword search interface
- Session-aware query and retrieval endpoints

It is designed as a reproducible research data backend for multi-domain observational datasets.

---

## Core Capabilities

- REST API for structured data ingestion
- Persistent object storage via MinIO (S3-compatible)
- Vector embeddings stored in PostgreSQL using pgvector
- Hybrid search (semantic + metadata filtering)
- Session-based query tracking
- Docker Compose deployment for full stack reproducibility

---

## Architecture

- FastAPI service (`main.py`)
- PostgreSQL + pgvector backend
- MinIO object storage
- Optional ingestion and monitoring utilities
- Docker Compose orchestration for all services

---

## Key Endpoints

- `POST /ingest` – ingest structured documents
- `GET /search` – semantic + metadata search
- `POST /ask` – retrieval-augmented query interface
- `POST /session/new` – session tracking for queries

---

## Running Locally

```bash
docker compose up -d
uvicorn main:app --reload --port 8000
