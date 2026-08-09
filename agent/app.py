"""Booking Agent — AMP Chat Agent contract.

POST /chat  {"message": str, "session_id": str, "context": dict}
         -> {"response": str}
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from graph import build_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("booking-agent")

_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    graph, mcp_client = await build_agent()
    _state["graph"] = graph
    _state["mcp_client"] = mcp_client
    logger.info("Booking agent ready; MCP tools loaded.")
    yield
    _state.clear()


app = FastAPI(title="Booking Agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: Optional[dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    graph = _state["graph"]
    result = await graph.ainvoke(
        {"messages": [("user", req.message)]},
        config={"configurable": {"thread_id": req.session_id}},
    )
    reply = result["messages"][-1].content
    return ChatResponse(response=reply)
