# Literae architecture

```text
Chat UI
  -> FastAPI
  -> input guardrails
  -> LangGraph research workflow
       -> query understanding and intent routing
       -> MCP research client
            -> Literae MCP research server
                 -> OpenAlex research tools
       -> grounded answer generation
       -> output guardrails
  -> answer, publication cards, author cards, and follow-ups
```

## MCP research tools

The graph does not call OpenAlex directly. It uses the official MCP Python SDK with an in-process
transport. This preserves MCP tool discovery and structured tool calls without adding a network hop
inside the API process. The same server can later be exposed over Streamable HTTP.

The server currently exposes:

- `search_publications`
- `search_authors`
- `get_author_works`
- `get_work_details`
- `find_related_works`
- `get_citing_works`
- `get_referenced_works`

OpenAlex remains the data provider behind these tools. LangGraph selects `get_author_works` for an
author-publications intent, `search_authors` for researcher profiles, and `search_publications` for
topic discovery. Follow-up transformations reuse the conversation's current publications without
performing another search.
