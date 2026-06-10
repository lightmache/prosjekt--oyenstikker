# prosjekt–øyenstikker

A containerized multi-service data ingestion, storage, observability, and retrieval system for structured observational datasets, integrating API ingestion, object storage, semantic search, infrastructure-as-code deployment, and full-stack observability tooling.

---

## Overview

This system implements an end-to-end infrastructure pipeline for ingesting, storing, observing, and querying structured and semi-structured datasets.

It is designed as a reproducible systems engineering stack combining:

- API-based ingestion and retrieval
- Vector search over embedded metadata
- S3-compatible object storage
- Infrastructure-as-code deployment
- Centralized logging and observability stack
- Lightweight frontend interface for testing and interaction

---

## System Components

### Backend API (FastAPI)
- `POST /ingest` – ingest structured documents
- `GET /search` – semantic + metadata search
- `POST /ask` – retrieval-augmented query interface
- `POST /session/new` – session tracking

---

### Storage Layer
- PostgreSQL + pgvector for hybrid structured + vector search
- MinIO (S3-compatible object storage) for persistent data storage

---

### Infrastructure (Terraform)
- Infrastructure-as-code definitions for full stack provisioning:
  - PostgreSQL + pgvector
  - MinIO object storage
  - Networked service configuration
- Reproducible environment setup using declarative infrastructure definitions

---

### Observability Stack
- **Grafana** – visualization and system dashboards
- **Loki** – centralized log aggregation system
- **Promtail** – log shipping from services into Loki

Provides:
- Centralized logging across services
- Queryable log streams
- Operational visibility into ingestion and retrieval pipelines
- Debugging support for distributed services

---

### Frontend
- Lightweight HTML interface (`oyenstikker.html`)
- Used for testing ingestion, search, and retrieval endpoints
- Development and validation interface for system behavior

---

## Architecture

- FastAPI application (`main.py`)
- PostgreSQL + pgvector backend
- MinIO object storage
- Grafana + Loki + Promtail observability stack
- Terraform infrastructure definitions
- Docker Compose multi-service orchestration
- Static HTML frontend

---

## Running Locally

### 1. Infrastructure (optional Terraform layer)
```bash
terraform init
terraform apply
