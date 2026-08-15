from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


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
def chat(req: ChatRequest) -> ChatResponse:
    return ChatResponse(response=f"echo: {req.message}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
