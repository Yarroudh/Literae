# Literae architecture

This document describes the active runtime architecture and the complete lifecycle of a chat turn.

## System and deployment architecture

```mermaid
flowchart TB
    User([Researcher])

    subgraph Public[Public edge]
        Caddy[Caddy reverse proxy<br/>HTTPS and TLS]
    end

    subgraph Frontend[Next.js frontend container]
        UI[Research chat UI]
        Filters[Research filters]
        Cards[Publication and author cards]
        Selection[Paper inclusion checkboxes]
        HistoryUI[Conversation history]
        ApiClient[Typed API client<br/>120-second browser timeout]
        UI --> ApiClient
        Filters --> ApiClient
        ApiClient --> Cards
        Cards --> Selection --> ApiClient
        HistoryUI --> ApiClient
    end

    subgraph Backend[FastAPI backend container]
        Routes[REST API<br/>chat, health, conversations]
        InputGuard[Input guardrail]
        Workflow[LangGraph research workflow]
        OutputGuard[Output guardrail]
        HistoryRepo[History repository]
        DeepSeek[DeepSeek V4 Pro client]

        subgraph ResearchBoundary[In-process MCP boundary]
            MCPClient[Typed MCP client]
            MCPServer[MCP research server]
            Tools[Research tool adapter]
            MCPClient -->|structured tool call| MCPServer
            MCPServer --> Tools
        end

        Resilience[Retry and TTL cache]
        OpenAlexClient[OpenAlex client and normalizer]

        Routes --> InputGuard --> Workflow
        Workflow --> DeepSeek
        Workflow --> MCPClient
        Tools --> Resilience --> OpenAlexClient
        Workflow --> OutputGuard --> Routes
        Routes <--> HistoryRepo
    end

    subgraph Data[Data and external services]
        PostgreSQL[(PostgreSQL<br/>conversations and JSONB turns)]
        OpenAlex[(OpenAlex API<br/>works, authors, citations)]
        DeepSeekAPI[(DeepSeek API<br/>planning and generation)]
        Laminar[(Laminar<br/>optional traces)]
    end

    User --> Caddy --> UI
    ApiClient -->|JSON over HTTPS| Caddy
    Caddy --> Routes
    HistoryRepo <--> PostgreSQL
    OpenAlexClient <--> OpenAlex
    DeepSeek <--> DeepSeekAPI
    Workflow -. graph and node spans .-> Laminar
    DeepSeek -. instrumented LLM calls .-> Laminar
```

In production, Caddy, Next.js, FastAPI, and PostgreSQL run as separate Docker Compose services.
MCP is in process: it preserves a typed, discoverable tool boundary without adding another network
hop. The same MCP server can also run independently over standard input/output.

## LangGraph workflow

```mermaid
flowchart TD
    Start([Start turn]) --> Interpret[interpret_request]

    Interpret -->|unambiguous follow-up| LocalPlan[Deterministic context plan]
    Interpret -->|new or ambiguous request| LLMPlan[DeepSeek SearchPlan]
    LocalPlan --> Merge[Merge plan and UI filters]
    LLMPlan --> Merge
    Merge --> Context[resolve_context]
    Context --> Validate[validate_search_plan]
    Validate --> Route[route_request]

    Route -->|topic, author works, more results| Search[search_publications]
    Route -->|researcher profiles| Authors[search_authors]
    Route -->|one work| Details[get_work_details]
    Route -->|similar works| Related[find_related_works]
    Route -->|papers citing work| Citing[get_citing_works]
    Route -->|work reference list| Referenced[get_referenced_works]
    Route -->|current papers| Reuse[Reuse stored results]
    Route -->|invalid or unsupported| Recover[recover_or_clarify]

    Search --> ReviewFallback{Review query<br/>returned zero?}
    ReviewFallback -->|yes| BroadSearch[Retry underlying topic]
    ReviewFallback -->|no| Evidence[select_evidence]
    BroadSearch --> Evidence
    Authors --> Evidence
    Details --> Evidence
    Related --> Evidence
    Citing --> Evidence
    Referenced --> Evidence
    Reuse --> Evidence

    Evidence --> Selection{Paper selection supplied?}
    Selection -->|no, default| AllPapers[Pass every retrieved paper<br/>with evidence scope]
    Selection -->|yes| IncludedPapers[Pass only checked papers<br/>and renumber citations]
    IncludedPapers --> Action
    AllPapers --> Action[execute_research_action]

    Action -->|reference style| RefFormat[Deterministic references]
    Action -->|BibTeX or RIS| Export[Deterministic export]
    Action -->|author overview| AuthorAnswer[DeepSeek author answer]
    Action -->|no abstracts available| MetadataAnswer[Deterministic metadata-only answer]
    Action -->|research synthesis| ResearchAnswer[DeepSeek grounded answer]
    Action -->|no usable results| Recover

    RefFormat --> Verify[verify_answer]
    Export --> Verify
    AuthorAnswer --> Verify
    MetadataAnswer --> Verify
    ResearchAnswer --> Verify
    Verify --> Suggestions[generate_followups]
    Recover --> Suggestions
    Suggestions --> End([Return workflow state])
```

The `ResearchState` carries the message, merged filters, structured plan, search query, page,
publications, authors, previous answer, route, visibility flags, context type, and suggestions. The
graph uses an in-memory LangGraph checkpointer keyed by conversation ID. PostgreSQL separately
provides durable restoration after a backend restart.

## Complete chat-turn sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as Researcher
    participant UI as Next.js chat
    participant API as FastAPI /chat
    participant IG as Input guard
    participant DB as History repository
    participant G as LangGraph
    participant DS as DeepSeek V4 Pro
    participant MCP as MCP research tools
    participant OA as OpenAlex
    participant OG as Output guard

    U->>UI: Submit message and filters
    UI->>UI: Add optimistic user turn and loading state
    UI->>API: POST /chat with message, filters, conversationId,<br/>and optional includedResultIds
    API->>IG: Normalize and validate message
    IG-->>API: Validated message
    API->>DB: Load latest conversation context
    DB-->>API: Previous papers, authors, answer, context type
    API->>G: Run turn with message, filters, and prior context

    alt Unambiguous follow-up on current papers
        G->>G: Build deterministic follow-up plan
        Note over G: Avoid redundant planner and search calls
    else New or ambiguous request
        G->>DS: Interpret request as structured SearchPlan
        DS-->>G: Intent, query, filters, work ID, sort
    end

    G->>G: Merge extracted constraints with UI filters
    Note over G: Explicit UI filters take precedence
    G->>G: Resolve context, validate, and choose route

    alt Search or work exploration route
        G->>MCP: Call typed research tool
        MCP->>OA: HTTP request with normalized filters
        OA-->>MCP: Scholarly records
        MCP-->>G: Validated publications or authors
        opt Focused review search returned no records
            G->>MCP: Retry broader underlying topic
            MCP->>OA: Broader search
            OA-->>MCP: Scholarly records
            MCP-->>G: Validated publications
        end
    else Current-context route
        G->>G: Reuse previous publications or authors
    end

    G->>G: Keep the complete publication set in context
    G->>G: Filter evidence to checked IDs, or all by default
    G->>G: Renumber selected papers and label evidence scopes

    alt Reference or export request
        G->>G: Format all records deterministically
    else All selected papers lack abstracts
        G->>G: Produce safe metadata-only overview
    else Research analysis or synthesis
        G->>DS: Prompt with every publication and grounding rules
        DS-->>G: Grounded answer with numeric citations
    else Author overview
        G->>DS: Prompt with author profile facts
        DS-->>G: Concise author answer
    end

    G->>G: Remove impossible citation markers
    G->>G: Generate contextual follow-up suggestions
    G-->>API: Answer, results, authors, flags, suggestions
    API->>OG: Validate output integrity and citation range
    OG-->>API: Validated answer
    API->>DB: Save complete successful turn as JSONB
    DB-->>API: Saved
    API-->>UI: ChatResponse JSON
    UI->>UI: Validate response and render answer and cards
    UI-->>U: Completed research turn
```

## Routing behavior

| Intent or request | Route | External research call | Answer path |
| --- | --- | --- | --- |
| Topic search | Publication search | `search_publications` | DeepSeek synthesis |
| More papers | Next search page | `search_publications` | DeepSeek synthesis |
| Author's publications | Author-filtered works | `get_author_works` | DeepSeek synthesis |
| Author profile or metrics | Author search | `search_authors` | DeepSeek author answer |
| Work details | One work | `get_work_details` | DeepSeek synthesis |
| Related works | Related-work lookup | `find_related_works` | DeepSeek synthesis |
| Citing works | Citation lookup | `get_citing_works` | DeepSeek synthesis |
| Referenced works | Reference lookup | `get_referenced_works` | DeepSeek synthesis |
| Compare or summarize current papers | Context reuse | None | DeepSeek synthesis |
| Format references | Context reuse | None | Deterministic formatter |
| BibTeX or RIS | Context reuse | None | Deterministic exporter |
| Unsupported or invalid request | Recovery | None | Deterministic recovery |

## Evidence and grounding

By default, every retrieved publication is passed into research generation. When the user changes
the selection, every selected publication is passed instead. Before serialization, each record is
assigned one of two scopes:

- `abstract_and_metadata`: the model may make paper-specific claims supported by that paper's
  abstract or explicit metadata.
- `metadata_only`: the model may mention bibliographic fields, title, and indexed topics, but may not
  infer methods, findings, locations, arguments, or conclusions.

If every selected paper is metadata-only, the graph bypasses generation and returns a deterministic
overview explaining that abstracts or full text are required for substantive analysis. References and
exports use all selected publications and never depend on the model.

By default, every current publication is selected. The user can uncheck papers on the active result
cards. Follow-up requests send the checked OpenAlex IDs as `includedResultIds`; LangGraph filters the
analysis evidence and deterministic exports to that subset while retaining the complete result set in
conversation history. Checked papers are renumbered in result order so answer citations continue to
match the visible cards. At least one paper always remains selected.

## Reliability, persistence, and observability

```mermaid
flowchart LR
    Request[Research operation] --> Cache{TTL cache hit?}
    Cache -->|yes| Cached[Return cached normalized result]
    Cache -->|no| Attempt[Call OpenAlex]
    Attempt -->|success| Store[Normalize and cache]
    Attempt -->|timeout, 429, or 5xx| Retry{Attempts remain?}
    Retry -->|yes| Backoff[Exponential backoff] --> Attempt
    Retry -->|no| Error[Typed API error]
    Store --> Result[Return result]

    Turn[Successful chat turn] --> JSONB[(PostgreSQL JSONB payload)]
    JSONB --> Restore[Restore latest context after restart]

    Graph[Graph and node execution] -. spans .-> Trace[Laminar]
    LLM[Instrumented DeepSeek calls] -. spans .-> Trace
```

The browser aborts a chat request after 120 seconds. FastAPI translates validation, OpenAlex,
DeepSeek, timeout, and output-integrity failures into typed HTTP responses. Only successful turns are
written to history.
