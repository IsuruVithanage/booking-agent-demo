"""Builds the Booking Agent's LangGraph ReAct graph.

Tools come from the Booking MCP server via the AMP MCP Proxy (env vars
injected by AMP's "Tool Configuration" at deploy time) -- this is the
governed path and works end to end.

The LLM calls OpenAI directly with a plain API key (same approach as
samples/hotel-booking-agent in this repo), rather than through an AMP
LLM Provider: the local quick-start build has a reproducible bug where
the per-agent LLM-proxy API key never gets bound to its gateway
Application (gateway logs: "Skipping unresolved API key for application
mapping"), so gateway-routed LLM calls 401 regardless of header/retry.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

SYSTEM_PROMPT = """You are a helpful hotel booking assistant.
Use the available tools to search hotels, check availability, and
create, list, or cancel bookings. Always confirm the hotel, dates,
number of rooms and guests before creating a booking. Dates must be
in YYYY-MM-DD format. If a tool call returns an error, explain it to
the user in plain language and suggest what to try next."""

# Injected by AMP's Tool Configuration when the "booking" MCP proxy is
# attached to this agent (see configure-agent-mcp-proxies.mdx). Falls
# back to a local MCP server for `agent/README.md`'s local-dev flow.
_MCP_URL = os.environ.get("BOOKING_URL", "http://localhost:8000/mcp")
_MCP_API_KEY = os.environ.get("BOOKING_API_KEY", "")

# Plain OpenAI credential, set as a secret env var on the agent.
_LLM_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def _mcp_client() -> MultiServerMCPClient:
    # Header name must match the MCP proxy's own Security config
    # (endpoint.security.apiKey.key) -- "X-API-Key" for the "booking" proxy,
    # not the "API-Key" name shown as a generic example in AMP's docs.
    headers: dict[str, str] = {}
    if _MCP_API_KEY:
        headers["X-API-Key"] = _MCP_API_KEY
    return MultiServerMCPClient(
        {
            "booking": {
                "url": _MCP_URL,
                "transport": "streamable_http",
                "headers": headers,
            }
        }
    )


async def build_agent() -> tuple[Any, MultiServerMCPClient]:
    """Fetches MCP tools and compiles the ReAct agent graph."""
    mcp_client = _mcp_client()
    tools = await mcp_client.get_tools()

    llm = ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=_LLM_API_KEY or "unset",
        temperature=0,
    )

    graph = create_react_agent(
        llm,
        tools,
        prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver(),
    )
    return graph, mcp_client
