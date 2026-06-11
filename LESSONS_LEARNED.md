# Prosjekt Øyenstikker — Engineering Lessons

## Data Persistence Requires Explicit Volume Configuration

Docker containers do not persist data by default across `docker compose down`. For the first several weeks of development the PostgreSQL knowledge base survived restarts because the container was never fully stopped — only restarted. The first explicit teardown wiped the database. Resolution: added a named `pgdata` volume to `docker-compose.yml`. Lesson: never assume container filesystem persistence without a declared volume.

## Compressed HTTP Responses Require Explicit Handling

The web search endpoint initially returned empty results despite a successful HTTP connection. Diagnosis revealed the upstream service was returning brotli-compressed responses that the parsing library could not decode. Resolution: removed brotli from the `Accept-Encoding` request header and installed the brotli decoding library as a fallback. Lesson: always inspect raw response encoding before assuming a parser failure is a structural problem.

## Repository Hygiene Prevents Scope Creep

Multiple unrelated projects accumulated in the same local directory, leading to a commit that included firmware files, session data, and experimental files in a repository intended for a focused infrastructure project. Resolution: reverted the commit and established clear separation between projects. Lesson: one repository, one scope.

## Static File Serving Order Matters in FastAPI

Mounting a static file handler at the root path intercepts all unmatched routes, including API endpoints defined after the mount call. Resolution: removed the root mount and served the frontend as a standalone HTML file. Lesson: in FastAPI, route specificity and registration order determine which handler wins.

## GPU Inference Runs Through Ollama Not PyTorch
The GTX 1070 (CC 6.1, 8GB VRAM) cannot execute CUDA kernels via the current PyTorch build (compiled for CC >= 7.5). This produced a misleading error during testing. However, all LLM inference runs through Ollama which uses its own CUDA runtime and fully utilizes the GPU at 81% utilization during generation with 3.6-4.4GB VRAM per model. Do not attempt to fix the PyTorch CC 6.1 warning by reinstalling PyTorch — the load-bearing GPU work is already happening correctly through Ollama. Only one model fits in 8GB VRAM at a time; Ollama handles eviction automatically. PyTorch is only used for the embedding model (all-MiniLM-L6-v2) which runs correctly on CPU as a fallback.
