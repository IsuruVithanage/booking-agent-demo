"""Track B1: a minimal agent that calls its LLM Provider exactly the way
the LLM Configuration panel's own Python integration snippet says to --
no workarounds, no manual patches. Whatever happens here is what any real
customer following the docs would experience.
"""

import os
from typing import Any

from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel, Field

app = FastAPI()

url = os.environ.get("OPENAI_URL")
apikey = os.environ.get("OPENAI_API_KEY")

client = OpenAI(
    # The doc's own sample snippet uses api_key="" here, which current
    # openai-python releases reject outright ("Missing credentials") --
    # they now treat an empty string as no key provided. Real auth is
    # carried entirely by the API-Key header below; this value is never
    # actually used, just needs to be non-empty to satisfy the SDK.
    base_url=url,
    api_key="unused",
    default_headers={"API-Key": apikey, "Authorization": ""},
)


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
    completion = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": req.message}],
    )
    return ChatResponse(response=completion.choices[0].message.content or "")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
