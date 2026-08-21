# Literae

Academic research assistant built with FastAPI, LangGraph, DeepSeek, OpenAlex, MCP, guardrails,
and Laminar tracing.

## Architecture

```text
User -> FastAPI -> Guardrails -> LangGraph -> MCP research tools -> OpenAlex
     -> DeepSeek grounded answer -> Output guardrails -> Answer + research cards
```

LangGraph calls the OpenAlex integration through the official MCP Python SDK. The API uses an
in-process MCP transport, retaining proper discovery and structured tool calls without an additional
network hop. Run `literae-mcp` to expose the same server over stdio for an MCP host or inspector.

See `docs/architecture.md` for the available tools and routing behavior.

## Laminar debugging

Laminar tracing is optional and backend-only. Set `LMNR_PROJECT_API_KEY` in `.env`, install the
project dependencies, and restart the API. Each chat request appears as a root trace with a child
span for every LangGraph node; DeepSeek and MCP calls are captured through OpenTelemetry
instrumentation.

Leave `LMNR_PROJECT_API_KEY` empty to disable tracing. For a self-hosted Laminar deployment, also
set `LMNR_BASE_URL`. No tracing controls are exposed in the Literae UI.
