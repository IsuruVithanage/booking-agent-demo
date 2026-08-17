import uvicorn

from app import app
from config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
