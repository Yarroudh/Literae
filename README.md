# Agentic RAG Chatbot

Agentic AI showcase project using:

- Gemini
- LangGraph
- LangChain
- Qdrant
- MCP
- Guardrails AI
- FastAPI
- OpenAlex

## Architecture

```text
User
 ↓
FastAPI
 ↓
Input Guardrails
 ↓
LangGraph Agent
 ↓
Gemini
 ↓
MCP Client
 ↓
MCP Tools
 ↓
Qdrant
 ↓
Gemini
 ↓
Output Guardrails
 ↓
Answer + Sources
# Laminar debugging

Laminar tracing is optional and backend-only. Set `LMNR_PROJECT_API_KEY` in `.env`, install the
project dependencies, and restart the API. Each chat request appears as a root trace with a child
span for every LangGraph node; DeepSeek calls are captured through OpenAI SDK instrumentation.

Leave `LMNR_PROJECT_API_KEY` empty to disable tracing. For a self-hosted Laminar deployment, also
set `LMNR_BASE_URL`. Local development sends traces immediately over HTTPS by default, avoiding
delayed batches and blocked gRPC connections. No tracing controls are exposed in the Literae UI.
