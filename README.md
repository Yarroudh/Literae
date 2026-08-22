# Literae

<img src="frontend/public/logo.png" alt="Literae logo" width="80px">

[![Live application](https://img.shields.io/badge/Live-Literae.online-2563EB?style=flat-square&logo=googlechrome&logoColor=white)](https://literae.online)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-1C3C3C?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Google Cloud](https://img.shields.io/badge/Google_Cloud-Compute_Engine-4285F4?style=flat-square&logo=googlecloud&logoColor=white)](https://cloud.google.com/compute)

### Live deployment

Explore the production showcase at **[literae.online](https://literae.online)**.

Literae is deployed on a Google Cloud Compute Engine E2 Standard virtual machine. The Next.js
frontend, FastAPI backend, and PostgreSQL database run as isolated Docker Compose services, while
Caddy provides reverse proxying, automatic TLS certificate management, and HTTPS access. Only the
public HTTP and HTTPS entry points are exposed; application and database traffic remain on the
internal Docker network.

Literae is a conversational academic research assistant for discovering publications, exploring
researchers, analysing groups of papers, and producing reusable references. It combines OpenAlex,
DeepSeek, LangGraph, the Model Context Protocol (MCP), Laminar tracing, and a Next.js interface in one reproducible Docker Compose environment.

> Results may be incomplete or contain metadata inherited from external scholarly records. Verify
> important claims, authorship, publication details, and references against the original publication.

---

## 1. Project Overview

Literae is designed as a research chatbot rather than a conventional search form. A user can begin
with a topic, researcher, institution, source, date range, language, work type, or access requirement,
then continue working with the returned research without repeating the search.

Core capabilities include:

1. Search publications using natural language requests and structured filters.
2. Extract authors and research constraints directly from a prompt.
3. Display publication information with citation count, authors, source, year, access status, citation, topics, DOI, and abstract.
4. Display author information with affiliations, ORCID, OpenAlex profile, works count, citation count,
   h-index, i10-index, and research topics.
5. Preserve conversational context for follow-up analysis, comparison, rewriting, and synthesis.
6. Generate complete APA, MLA, IEEE, Chicago, Harvard, and Vancouver reference lists.
7. Export references as BibTeX or RIS for tools such as Overleaf, Zotero, and Mendeley.
8. Explore an individual work's details, related publications, citing publications, and references.
9. Save conversations history and restore their latest research context after an API restart.
10. Trace LangGraph, DeepSeek, and MCP activity with optional Laminar observability for debugging and performance analysis.

The application is designed for research assistance and is not a substitute for reviewing original publications. It does not provide authoritative bibliographic data, and its results may be incomplete or contain metadata inherited from external scholarly records. Always verify important claims, authorship, publication details, and references against the original publication.

---

## 2. Repository Structure

```text
├── app
│   ├── agent
│   │   ├── graph.py                 # LangGraph workflow and routing
│   │   ├── query_understanding.py   # Structured search plans and intent types
│   │   └── state.py                 # Graph state
│   ├── api
│   │   ├── main.py                  # FastAPI application and dependency wiring
│   │   ├── routes.py                # Chat, health, and history endpoints
│   │   └── schemas.py               # Request and response contracts
│   ├── common
│   │   └── resilience.py            # Retry policy and in-memory TTL cache
│   ├── config
│   │   └── settings.py              # Environment-driven configuration
│   ├── debugging
│   │   └── laminar.py               # Backend-only tracing
│   ├── guardrails
│   │   ├── input.py                 # Length, normalization, and explicit override checks
│   │   └── output.py                # Citation and output integrity checks
│   ├── history
│   │   └── repository.py            # PostgreSQL and in-memory history repositories
│   ├── llm
│   │   └── deepseek.py              # Intent interpretation and grounded generation
│   ├── mcp
│   │   ├── client.py                # Typed MCP research client
│   │   ├── server.py                # MCP server and stdio entry point
│   │   └── tools.py                 # Academic tool contracts and OpenAlex adapter
│   └── retrieval
│       └── openalex.py              # OpenAlex HTTP client and normalization
├── frontend
│   ├── app                          # Next.js application shell and styles
│   ├── components                   # Chat, cards, filters, history, and UI controls
│   ├── lib                          # API client and topic suggestions
│   ├── public                       # Logo and static assets
│   └── Dockerfile
├── tests                            # Agent, API, guardrail, history, MCP, LLM, and retrieval tests
├── docs
│   └── architecture.md
├── Dockerfile                       # FastAPI production image
├── docker-compose.yml               # Frontend, API, and PostgreSQL orchestration
├── pyproject.toml
└── .env.example
```

The empty ingestion and vector search placeholders are intentionally not part of the active
runtime yet. Their planned role is described in the **Next** section.

---

## 3. System Architecture

### Component overview

![Solutions](frontend/public/solutions.png)


| Component | Responsibility |
| --- | --- |
| Next.js | Chat interface, paper and author cards, filters, themes, exports, and history controls |
| FastAPI | Validates requests, runs the research workflow, applies output checks, and exposes history |
| LangGraph | Maintains research state and routes each turn to retrieval, reuse, author, or recovery paths |
| DeepSeek | Produces structured intent plans and grounded natural-language research analysis |
| MCP | Provides a discoverable, typed boundary between the agent and academic research operations |
| OpenAlex | Supplies works, authors, bibliographic metadata, topics, citations, and relationships |
| PostgreSQL | Stores conversation summaries and complete chat turns as durable JSONB records |
| Laminar | Captures optional backend traces for graph nodes, LLM requests, and MCP calls |
| Guardrails | Reject explicit instruction overrides and verify generated citations and exports |
| Docker Compose | Builds and runs the frontend, backend, and database together |

### Request flow

The following diagram shows the flow of a research request through the system.

<img src="frontend/public/flow.png" width="700px" alt="High-level request flow">


---

## 4. LangGraph Research Workflow

The graph separates understanding, retrieval, generation, and verification into nodes:

1. `interpret_request` asks DeepSeek for a validated `SearchPlan`.
2. `resolve_context` determines whether the request refers to current papers, current authors, or a
   new search.
3. `validate_search_plan` checks constraints such as invalid year ranges.
4. `route_request` selects publication search, author search, current-context reuse, work-level
   exploration, or recovery.
5. A selected MCP node obtains structured research data.
6. `select_evidence` bounds the publication context sent to the language model.
7. `execute_research_action` generates an answer or creates deterministic reference exports.
8. `verify_answer` removes impossible citation markers.
9. `recover_or_clarify` returns a clean product response when no valid action can be completed.
10. `generate_followups` suggests actions appropriate to papers or author profiles.

Supported intents include topic search, author publications, bibliography generation, result
analysis, author overview, additional results, work details, related works, citing works, referenced
works, and unsupported requests.

---

## 5. MCP Academic Research Tools

Literae uses the official MCP Python SDK. The API connects to the MCP server in process, retaining
tool discovery and structured protocol calls without adding a network hop. The same server can run
independently over stdio with `literae-mcp`.

| Tool | Purpose |
| --- | --- |
| `search_publications` | Search works using a topic and structured research filters |
| `search_authors` | Resolve researcher profiles and bibliometric metrics |
| `get_author_works` | Retrieve a researcher's publications |
| `get_work_details` | Retrieve one OpenAlex work |
| `find_related_works` | Retrieve works related to a selected publication |
| `get_citing_works` | Retrieve works that cite a selected publication |
| `get_referenced_works` | Retrieve works referenced by a selected publication |

Examples of work-level follow-ups include `Show papers citing [1]`, `Find work related to [3]`, and
`Show the references of this paper`.

---

## 6. Research Filters and Results

The filter popover supports:

| Filter | OpenAlex constraint |
| --- | --- |
| From year / to year | Publication date range |
| Work type | Article, book, dataset, review, and other supported work types |
| Access | Open or closed access |
| Language | ISO 639-1 publication language |
| Author | Resolved to an OpenAlex author identifier |
| Institution | Resolved to an OpenAlex institution identifier |
| Journal or source | Resolved to an OpenAlex source identifier |
| Sort | Relevance, newest, oldest, or most cited |

UI filters override constraints extracted from the message.

Publication numbers correspond to citations such as
`[1]` in the answer and can be referenced in later turns.

---

## 7. Reference Formatting and Exports

The current publication set can be formatted as:

- APA 7
- MLA 9
- IEEE
- Chicago
- Harvard
- Vancouver
- BibTeX
- RIS

The styles are produced deterministically from the returned metadata, which
guarantees that every visible publication is included. BibTeX and RIS are returned in labelled code
blocks with copy and download controls.

Reference metadata is only as accurate as its OpenAlex record. Always verify final bibliographies
against publisher pages or DOI records before submission.

---

## 8. Guardrails and Reliability

### Input protection

- Removes unsafe control characters and surrounding whitespace.
- Enforces a limit of 4,000 for each request message.
- Blocks explicit imperative instruction overrides such as `ignore previous instructions`.
- Uses semantic intent classification for broader out-of-scope requests to avoid brittle phrase lists.

### Output protection

- Rejects empty responses and unfinished Markdown code blocks.
- Rejects citation numbers that do not map to returned publications.
- Verifies complete BibTeX, RIS, and formatted reference outputs.
- Rejects language exposing hidden prompts or internal workflow details.

### Service resilience

- Retries transient OpenAlex timeouts, rate limits, and server failures with exponential backoff.
- Caches repeated OpenAlex operations in memory for a configurable TTL.
- Traces graph and integration failures in Laminar when enabled.

The cache is local to the process and intentionally short lived; it does not replace PostgreSQL history.

---

## 9. Conversation History and PostgreSQL

Every successful turn is stored in two tables:

| Table | Contents |
| --- | --- |
| `conversations` | Conversation ID, generated title, created time, and last update time |
| `conversation_turns` | User query, complete response payload, and creation time |

The response payload is stored as JSONB and includes answers, publications, authors, visibility flags,
context type, and follow-up suggestions. Deleting a conversation cascades to its turns.

The history control in the application header lets users reopen or delete recent chats without adding
a sidebar. When an old conversation continues after an API restart, Literae hydrates its most recent
papers, authors, answer, and context back into LangGraph.

### Automatic database setup

When `DATABASE_URL` is configured, the API creates the required tables and index during startup.
Docker Compose waits for PostgreSQL to become healthy before starting the API.

### Manual PostgreSQL setup

For development without Docker:

```sql
CREATE USER literae WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE literae OWNER literae;
```

Then configure:

```env
DATABASE_URL="postgresql://literae:choose-a-strong-password@localhost:5432/literae"
HISTORY_ENABLED=true
```

The tables are created automatically on the next API startup. Set `HISTORY_ENABLED=false` or leave
`DATABASE_URL` empty to run with history disabled.

### Database inspection and backup

```bash
docker compose exec database psql -U literae -d literae
docker compose exec -T database pg_dump -U literae -d literae > literae-backup.sql
```

Restore a backup into an empty database with:

```bash
docker compose exec -T database psql -U literae -d literae < literae-backup.sql
```

---

## 10. API Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health and version |
| `POST` | `/chat` | Run or continue a research conversation |
| `GET` | `/conversations` | List recent conversations |
| `GET` | `/conversations/{id}` | Restore one conversation and all turns |
| `DELETE` | `/conversations/{id}` | Delete a conversation and its turns |
| `GET` | `/docs` | OpenAPI UI in non-production environments |

Example chat request:

```json
{
  "message": "Find open-access research on urban green spaces after 2020",
  "filters": {
    "fromYear": 2020,
    "openAccess": "open",
    "sort": "cited"
  }
}
```

Send the returned `conversationId` with subsequent requests to preserve context.

---

## 11. Environment Variables

Copy `.env.example` to `.env`.

### Application and model

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `APP_NAME` | No | `Literae API` | API display name |
| `APP_VERSION` | No | `0.1.0` | Health response version |
| `ENVIRONMENT` | No | `development` | Enables docs outside production |
| `CORS_ORIGINS` | No | `["http://localhost:3000"]` | JSON array of allowed browser origins |
| `DEEPSEEK_API_KEY` | Yes | — | DeepSeek API credential |
| `DEEPSEEK_MODEL` | Yes | `deepseek-v4-flash` | DeepSeek chat model |
| `DEEPSEEK_BASE_URL` | Yes | `https://api.deepseek.com` | OpenAI-compatible endpoint |
| `DEEPSEEK_TIMEOUT_SECONDS` | Recommended | `75` | Model timeout |

### OpenAlex and reliability

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `OPENALEX_API_KEY` | Yes | — | OpenAlex API key |
| `OPENALEX_EMAIL` | Yes | — | Contact email for polite API usage |
| `OPENALEX_RESULTS_LIMIT` | Recommended | `25` | Publications returned per page |
| `OPENALEX_TIMEOUT_SECONDS` | Recommended | `15` | OpenAlex timeout |
| `OPENALEX_CACHE_TTL_SECONDS` | No | `300` | In-memory result cache lifetime |
| `SERVICE_RETRY_ATTEMPTS` | No | `3` | Transient OpenAlex attempts |

### PostgreSQL and ports

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `POSTGRES_DB` | Docker | `literae` | Database name |
| `POSTGRES_USER` | Docker | `literae` | Database user |
| `POSTGRES_PASSWORD` | Yes | — | Database password |
| `DATABASE_URL` | Local run | — | Async PostgreSQL connection URL |
| `HISTORY_ENABLED` | No | `true` | Enables persistent history when URL is present |
| `FRONTEND_PORT` | No | `3000` | Published frontend port |
| `API_PORT` | No | `8000` | Published API port |
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000` | Browser-visible API URL compiled into Next.js |

### Laminar tracing

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `LMNR_PROJECT_API_KEY` | No | — | Enables Laminar tracing |
| `LMNR_BASE_URL` | No | Laminar Cloud | Optional self-hosted endpoint |
| `LAMINAR_FORCE_HTTP` | No | `true` | Uses HTTP OTLP export |
| `LAMINAR_DISABLE_BATCH` | No | `true` | Sends local development traces immediately |

Tracing is never appears in the application UI. This is a developer observability feature for debugging and performance analysis.

---

## 12. Docker Services

| Service | Image/build | Port | Responsibility |
| --- | --- | --- | --- |
| `frontend` | Multi-stage Next.js standalone image | `3000` | Literae web interface |
| `api` | Python 3.12 slim image | `8000` | FastAPI, LangGraph, MCP, OpenAlex, and DeepSeek |
| `database` | PostgreSQL 16 Alpine | Internal `5432` | Durable conversation history |

PostgreSQL data is stored in the named volume `literae_postgres_data` and survives container
recreation.

---

## 13. Setup and Execution with Docker

### Step 1 — Prepare the environment

```bash
git clone https://github.com/Yarroudh/Literae
cd Literae
cp .env.example .env
```

At minimum, edit `.env` and set:

```env
DEEPSEEK_API_KEY="your-deepseek-key"
OPENALEX_API_KEY="your-openalex-key"
OPENALEX_EMAIL="you@example.com"
POSTGRES_PASSWORD="a-strong-local-password"
```

If you want to use Laminar tracing, also set `LMNR_PROJECT_API_KEY`.

Keep `NEXT_PUBLIC_API_URL=http://localhost:8000` for the default local ports.

### Step 2 — Build and start everything

```bash
docker compose up --build -d
```

This command builds the frontend and API, starts PostgreSQL, waits for the database and API health
checks, and then starts the frontend.

### Step 3 — Access the services

| Service | URL |
| --- | --- |
| Literae | http://localhost:3000 |
| API health | http://localhost:8000/health |
| API documentation | Disabled in production Compose mode |

### Step 4 — Inspect status and logs

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f frontend
docker compose logs -f database
```

### Step 5 — Stop or rebuild

```bash
docker compose down
docker compose up --build -d
```

`docker compose down` preserves history. Removing the named volume permanently deletes the database;
back it up first if its contents matter.

---

## 14. Local Development without Docker

### Backend

Requirements: Python 3.12+ and a running PostgreSQL instance if history is enabled.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.api.main:app --reload --port 8000
```

Run the standalone MCP stdio server with:

```bash
literae-mcp
```

### Frontend

Requirements: Node.js 22+.

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

The frontend runs at `http://localhost:3000` and calls the API defined by
`NEXT_PUBLIC_API_URL`.

---

## 15. Testing and Quality Checks

Backend:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff format --check app tests
.venv/bin/ruff check app tests
```

Frontend:

```bash
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
```

Validate the Compose file:

```bash
docker compose config
```

The automated tests cover query interpretation, LangGraph routing, MCP discovery and calls, OpenAlex
normalization, retries and caching, guardrails, reference exports, API contracts, and history storage.

---

## 16. Next

The following modifications are deliberately planned rather than represented as current features:

- [ ] Add a Qdrant vector database for uploaded papers, private corpora, and semantic passage
      retrieval—not as a replacement for live OpenAlex discovery.
- [ ] Implement PDF, TXT, and Markdown ingestion with metadata extraction, page-aware chunking,
      embeddings, replacement, and deletion.
- [ ] Add hybrid retrieval that combines OpenAlex publications with passages from uploaded documents.
- [ ] Add document-level citations that link an answer to the exact uploaded page and passage.
- [ ] Add user authentication and isolate PostgreSQL conversations and Qdrant collections per user.
- [ ] Replace automatic startup DDL with versioned database migrations before multi-user deployment.
- [ ] Add Redis-backed distributed caching and request deduplication for multiple API replicas.
- [ ] Add an automated evaluation dataset for routing, retrieval relevance, citation grounding,
      reference completeness, guardrails, latency, and regression tracking.
- [ ] Add streaming responses and cancellable long-running research tasks.
- [ ] Add saved research collections, paper bookmarks, notes, and tags.
- [ ] Add comparison tables, citation-network visualizations, and publication timelines.
- [ ] Add DOI, ORCID, institution, and source disambiguation interfaces.
- [ ] Add optional scholarly providers behind MCP while preserving source attribution and licensing.
- [ ] Add production authentication, rate limiting, secret management, backups, and CI/CD.

---

## 18. Data Sources and Acknowledgements

- OpenAlex provides scholarly works, authors, institutions, sources, topics, and citation metadata.
- DeepSeek provides structured request interpretation and grounded language generation.
- The Model Context Protocol Python SDK provides the research tool boundary.
- LangGraph provides stateful workflow orchestration.
- Laminar provides optional developer observability.

Literae is a research assistance tool, not an authoritative bibliographic database or a substitute for
reviewing original publications.

---
## License

Copyright © 2026 Anass Yarroudh. All rights reserved.

Literae is distributed under the **Literae Source Available License v1.0**. It is source available,
but it is not licensed under an Open Source Initiative approved open-source license.

The license permits viewing and inspecting the source, private cloning, and running an unmodified
copy for personal, academic, educational, research, evaluation, and other noncommercial purposes.
Attribution to **Literae by Anass Yarroudh** is required where applicable.

Without prior written permission from the author, the license does not permit:

- commercial use;
- modification or creation of derivative works;
- redistribution or repository mirroring;
- replicated or competing implementations based on the software; or
- public hosting, deployment, or operation for third-party access.

Commercial licensing and additional permissions may be requested through the
[Literae repository](https://github.com/Yarroudh/Literae).

Read the complete terms in the [LICENSE](LICENSE) file. If this summary conflicts with the license
text, the complete license text governs.
