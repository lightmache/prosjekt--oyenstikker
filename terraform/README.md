# Terraform — Øyenstikker Infrastructure

Defines the Øyenstikker stack as infrastructure-as-code using the Terraform Docker provider.

## What this defines

- Docker network for service isolation
- Named pgdata volume for persistent PostgreSQL storage
- pgvector/pgvector:pg16 container with environment-driven credentials
- Port binding locked to 127.0.0.1 for security

## Usage

```bash
terraform init
terraform plan -var="postgres_password=yourpassword"
terraform apply -var="postgres_password=yourpassword"
```

## Why IaC matters here

The entire database environment — network, storage, container configuration, port bindings — is declared in code. This means the environment can be recreated identically on any host, audited for security posture, and version-controlled alongside the application it supports.
