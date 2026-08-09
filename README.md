# Booking Agent + Booking MCP Server (WSO2 Agent Manager demo)

Two independently deployable services demonstrating AMP end to end:
a governed MCP tool server, and a chat agent that uses it through the
platform's AI Gateway.

```
mcp-server/   FastMCP server exposing booking tools over streamable-HTTP (/mcp)
agent/        FastAPI + LangGraph chat agent (POST /chat) that calls those
              tools through an AMP MCP Proxy, and calls an LLM through an
              AMP LLM Provider
```

## Local development

Run the MCP server:

```bash
cd mcp-server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PORT=8000 python server.py
```

Run the agent against it directly (bypassing AMP's gateway, for local iteration):

```bash
cd agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
BOOKING_URL=http://localhost:8000/mcp \
OPENAI_API_KEY=sk-... \
uvicorn app:app --port 8080
```

```bash
curl -X POST http://localhost:8080/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Find hotels in Tokyo for Feb 7 to Feb 8, 2026 for 1 guest.","session_id":"demo-1"}'
```

## Deploying on WSO2 Agent Manager

Both services are deployed as Platform-Hosted agents (the MCP server as
`custom-api`, the chat agent as `chat-api`), then wired together with an
MCP Proxy and an LLM Provider. See the team's internal deployment notes
for the exact `amctl` commands used against the local quick-start
install.

### Environment variables

| Service | Variable | Set by |
|---|---|---|
| `agent` | `BOOKING_URL`, `BOOKING_API_KEY` | AMP Tool Configuration (MCP proxy `booking` attached to this agent) |
| `agent` | `OPENAI_URL`, `OPENAI_API_KEY` | AMP `--llm-provider` binding at agent creation |
| `agent` | `OPENAI_MODEL` | optional, defaults to `gpt-4o-mini` |
| `mcp-server` | `PORT` | AMP custom-api port config (default `8000`) |
