# Prosjekt Øyenstikker — Build Plan

---

## What Makes Øyenstikker Special

Øyenstikker is not a smarter chatbot. It is a persistent observational memory system. The distinction matters.

Every other tool in the research workflow — Claude, ChatGPT, Copilot — starts each session with no memory of what you observed, what you built, or what you concluded. You re-paste, re-explain, re-contextualize every time. The AI reasons well but forgets immediately.

Øyenstikker does the opposite. It reasons poorly but forgets nothing.

What this means in practice: a numerical value ingested tonight is retrievable by exact string match six months from now with a timestamp and a source path. No summarization, no compression, no narrative drift. The number you stored is the number you get back.

This was demonstrated with minimal ingested data — 131 documents as of June 2026 — and the system already showed three real capabilities:

**Cross-table value retrieval.** Asked "what was the wind speed at the site where the accelerometer was hardest to stabilize" — with no prior context, no named site, no named column — it returned 18 knots, Bergen, ENBR. Correct. The answer required joining two tables on a shared site key and reading a value. The LLM misclassified the domain entirely. The number was right.

**Lossless numerical storage.** The stage-discharge matrix (2.2→420, 3.6→950, 6.9→4250) was ingested as plain text and returned verbatim on retrieval. The exponential acceleration pattern and the inflection point at 3.6 were preserved exactly. Six months from now that matrix is still there, unchanged, queryable by value.

**Provenance chain.** Every MinIO-ingested document carries its source bucket path and timestamp. `minio:oyenstikker-data/airframe-raw/fc-report/analog-readings.txt` ingested at `2026-06-11T01:54:54` is traceable to its origin file. Manual ingests carry session IDs. Nothing is anonymous.

These capabilities exist now, before any interpretation improvements, because they depend on PostgreSQL and pgvector — not on the LLM. The LLM is the weakest layer in the stack. The database is the strongest.

---

## Why This Becomes More Useful Once Interpretation Improves

Right now the gap is this: Øyenstikker retrieves the right document and reasons from the wrong one. It found the Bergen wind speed in context_used and then explained it as Vinton NO2 data. The number was correct. The explanation was invented.

The root causes are known and fixable:

**Semantic gravity wells.** The CIRE atmospheric findings, MAVEN dataset, and course outlines are the densest documents in the knowledge base by token count and vocabulary richness. Every query that touches atmospheric, numerical, or educational language pulls these documents into context alongside the target document. The LLM defaults to the richer text.

Fix: bucket scoping. Tag documents by domain on ingestion. Query only the relevant bucket. Numerical motor data never competes with atmospheric science findings.

**Wrong default model.** phi3:mini (3.8B Q4_0) is the default in fuse.py. It is the most aggressively quantized model in the stack and the most likely to ignore context in favor of training data. llama3.1:8b produced the best result of the June 2026 experiments — correct epistemic behavior, no hallucinated domain, honest "I found a pattern but couldn't interpret it."

Fix: change one line in fuse.py. Default to llama3.1:8b.

**Context window competition.** top_k=3 retrieves three documents. If two of them are semantic gravity wells the LLM has two rich documents and one bare number matrix. It picks the rich documents.

Fix: reduce top_k to 1 for value-anchored queries. One document, no competition.

Once these three fixes are in place the interpretation layer will read what it retrieves instead of reaching past it. The cross-table join result — Bergen, 18 knots — will come back with correct domain classification, not hallucinated Vinton EPA data.

At that point Øyenstikker becomes a genuine research memory system: you observe, it stores, you ask, it retrieves and correctly contextualizes. The loop closes.

---

## How Øyenstikker Behaves

Understanding the actual behavior — not the intended behavior — is essential for using the system correctly and for building on top of it.

**Retrieval is reliable. Interpretation is not.**
The pgvector search layer returns the correct document consistently. This was demonstrated across every experiment. context_used showed the right data every time. The LLM then ignored it approximately 70% of the time in favor of richer competing documents.

**Value-to-date works. Date-to-value does not.**
"What date is on the record containing 3.0 ppb?" → correct answer, January 1 2024.
"What was the NO2 reading on January 3?" → refused, cited training cutoff, ignored retrieved document.
Design queries value-first. The database has no temporal index. Embedding similarity between adjacent dates is nearly identical — the model cannot distinguish January 3 from January 14 by semantic distance alone.

**Superlative queries scan only top-k.**
"What is the highest NO2 value?" returned 3.0 ppb — the highest value among the three retrieved documents, not across all 93 records. pgvector returns top-k by similarity, not by numerical ranking. For max/min/average queries use SQL directly, not the /ask endpoint.

**Cross-table joins work when keyed on a named field.**
"What wind speed corresponds to the site with occasional showers?" — correct. The site name "Stavanger" appears in both tables as a shared key. The LLM can join on it. Unnamed keys, positional references, and implicit relationships do not work.

**The LLM finds the correct numerical pattern and hallucinates the explanation.**
Every experiment confirmed this. The stage-discharge inflection at 3.6 was found. The accelerating growth pattern was found. The inverse correlation in the Volantex analog channels was found. The domain classification — what the numbers represent — was invented from the nearest semantic cluster every time. Trust the numbers. Discard the explanation until bucket scoping is implemented.

**Interpretation improves with elimination.**
When asked to pick from a list of five domains, Øyenstikker eliminated correctly across multiple queries even when each individual answer was wrong. "Not that one, next" worked. This is a usable interaction pattern for domain classification when you know the answer space.

**The SQL layer is always correct.**
```sql
SELECT content FROM documents WHERE content LIKE '%value%';
```
This bypasses the LLM entirely. It always returns what is stored. Use it to verify retrieval before debugging interpretation.

---

## UX Principles

These principles are derived from observed system behavior, not from design theory. Each one has a failure mode that produced it.

**1. The system advises. You act.**
No script, no interface, no automated process modifies a running file without an explicit human confirmation. This principle exists because ChatGPT rewrote a working main.py to fix a problem that didn't exist. The GPU warning was cosmetic. The system was functioning. A tool that acts without being asked broke hours of working infrastructure. Nothing in the Øyenstikker interface enters a command, modifies a file, or changes system state without a keypress from you.

**2. Show state before action.**
Before any operation the interface shows what the current state is. Before ingesting: how many documents are in the database, what was ingested last, what might conflict. Before starting: which services are running, which are not, what will happen if you proceed. Before modifying a file: git status, last commit hash, what changed. The failure mode this prevents: acting on a false premise.

**3. Warn on known failure modes, not on errors.**
The GTX 1070 CC 6.1 PyTorch warning is not an error. It is a known non-fatal compatibility notice. The system runs correctly on cuda:0 despite the warning. The interface distinguishes between warnings that require action and warnings that require acknowledgment. "Do not reinstall PyTorch to fix this" is a valid system message.

**4. Every destructive operation has a named restore point.**
Before modifying fuse.py, docker-compose.yml, or any running infrastructure file, the system creates a tagged git commit. The tag is human-readable: `restore-2026-06-11-working`. One command gets you back. The failure mode this prevents: an AI rewrites a working file, you can't remember what it looked like before.

**5. Query design guidance at the point of entry.**
The interface detects query type as you type and shows expected behavior before you submit. Date-to-value query: warn. Superlative query: suggest SQL instead. Cross-table join with named key: proceed with confidence. The failure mode this prevents: submitting a query that will fail in a known way and spending time debugging the LLM instead of redesigning the question.

**6. The number is the signal. Everything around it is noise.**
When the LLM returns an answer, the interface highlights the numerical values in the response and flags the domain classification as unverified until bucket scoping is implemented. You read the number. You verify the explanation separately. The failure mode this prevents: accepting a hallucinated domain as correct because the number was right.

**7. Provenance is always visible.**
Every retrieved document shows its source path and ingestion timestamp alongside the answer. You always know where the data came from and when it was stored. The failure mode this prevents: trusting a retrieval result without knowing whether it came from your own observations or from a test document or from a legacy ingest.

**8. One command does everything.**
`./manage.py start` is the only command a new user needs to know. It checks prerequisites, starts services in the right order, waits for readiness, reports status, and exits cleanly if everything is already running. The failure mode this prevents: a six-step startup sequence where forgetting one step silently breaks the system.

---

## Build Checklist

### Tier 1 — Protect what works
- [ ] `manage.py` with auto-git-commit before any file modification
- [x] Tagged restore points — `manage.py backup` and `manage.py restore`
- [x] `manage.py doctor` — checks all services, GPU status, warns on known failure modes
- [x] Ingest LESSONS_LEARNED.md and all working commands into Øyenstikker (5 lessons ingested, bucket: infrastructure)
- [x] Document GPU warning permanently — handled by manage.py doctor (INFO message, non-fatal CC 6.1 warning)
- [x] Change default model in fuse.py from phi3:mini to llama3.1:8b

### Tier 2 — Motor data pipeline
- [ ] Standard ingest file format for brushless motor test runs
- [ ] MinIO drop script — one command to log a test run and ingest automatically
- [ ] SQL query reference ingested into Øyenstikker
- [ ] Ingest all working curl commands with outputs
- [ ] Ingest all working SQL queries
- [ ] Ingest every bug fix as a lessons learned entry

### Tier 3 — Make it brainless
- [x] `manage.py start` replaces start.sh with full redundancy
- [ ] Preventative warnings before destructive operations
- [x] Bucket scoping — domain-tagged ingestion, isolated retrieval (job_search_ask.py)
- [x] Reduce top_k to 2 for /ask retrieval (reduces gravity well competition, preserves cross-table join capability)
- [x] Auto-ingest working code snippets on every git commit (.git/hooks/post-commit, bucket: infrastructure)

### Tier 4 — Side panel
- [ ] Side terminal panel — status, warnings, guidance, read-only
- [ ] Panel reads from Øyenstikker knowledge base for context-aware guidance
- [ ] Panel shows git status, last commit, running services, ingested document count
- [ ] Panel catches false premises before you act on them

### Tier 5 — Query interface
- [ ] Query type detector — warns on date-to-value, superlative, unlabeled cross-table
- [ ] Model recommender per query type
- [ ] Numerical value highlighting in LLM responses
- [ ] Domain classification flagged as unverified until bucket scoping is live
- [ ] Provenance visible on every retrieved document

### Tier 6 — Distribution
- [ ] One-pull install from fresh clone
- [ ] Prerequisites checker — reports missing dependencies without installing anything
- [ ] Works on WSL2/Windows, native Linux, macOS
- [ ] Setup guidance in side panel during install flow

### Tier 7 — Cloud deployment
- [ ] Ollama containerized in docker-compose
- [ ] Single `docker compose up` brings full stack including models
- [ ] VPS deployment target with persistent volumes
- [ ] HTTPS via Caddy reverse proxy
- [ ] GitHub Actions auto-deploy on passing CI
- [ ] Environment variables for all credentials

### Tier 8 — Research artifact
- [ ] Live URL, reproducible deployment
- [ ] Methods paper — Prosjekt Øyenstikker as open research infrastructure
- [ ] Zenodo DOI
- [ ] Full independence from external AI API services

---

## GPU Status — June 11 2026

GTX 1070 (CC 6.1, 8GB VRAM) confirmed working for all Ollama LLM inference via WSL CUDA forwarding:

- llama3.1:8b — ~3.6GB VRAM, 81% GPU utilization during generation
- phi4-mini — ~3.6GB VRAM, confirmed on GPU
- mistral 7.2B — ~4.4GB VRAM, confirmed on GPU
- phi3:mini — assumed on GPU, not explicitly tested

PyTorch embedding model (all-MiniLM-L6-v2) runs on CPU due to CC 6.1 kernel execution failure with current PyTorch build. Non-blocking — embedding speed is not the bottleneck.

Only one model fits in VRAM at a time. Ollama handles load/evict automatically.

These specific models are not permanent. As better open models are released they will replace the current stack. The architecture is model-agnostic — any Ollama-compatible model works without code changes. 3 of 4 models confirmed on GPU is the baseline. Future models should be tested with the nvidia-smi dmon method before being added to the default stack.

