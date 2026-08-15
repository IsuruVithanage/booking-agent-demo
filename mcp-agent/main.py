"""Track C1: a minimal agent that calls an attached MCP Proxy directly --
no LLM involved at all, so this purely isolates whether the MCP connection
itself works, independent of anything Track B already found about LLM
provider connectivity.
"""

import os
from typing import Any

from fastapi import FastAPI
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field

app = FastAPI()

booking_url = os.environ.get("BOOKING_URL", "")
booking_api_key = os.environ.get("BOOKING_API_KEY", "")

_tools: list = []


@app.on_event("startup")
async def load_tools() -> None:
    global _tools
    if not booking_url:
        return
    client = MultiServerMCPClient(
        {
            "booking": {
                "url": booking_url,
                "transport": "streamable_http",
                "headers": {"API-Key": booking_api_key, "X-API-Key": booking_api_key},
            }
        }
    )
    _tools = await client.get_tools()


class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not _tools:
        return ChatResponse(response="no MCP tools loaded")
    search_tool = next((t for t in _tools if t.name == "search_hotels"), None)
    if not search_tool:
        return ChatResponse(response=f"tools loaded but search_hotels not found: {[t.name for t in _tools]}")
    result = await search_tool.ainvoke({})
    return ChatResponse(response=str(result))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
