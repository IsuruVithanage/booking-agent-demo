from fastapi import FastAPI

from booking import router as booking_router

app = FastAPI(title="Booking Agent API", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(booking_router)
