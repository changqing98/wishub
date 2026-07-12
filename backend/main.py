from fastapi import FastAPI

from backend.interface.routers import api_router
from backend.shared import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(api_router)
