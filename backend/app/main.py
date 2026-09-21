"""RetailOps ML application composition.

Route behavior lives in ``app.api`` so the entrypoint remains stable for local
development, tests, and future authenticated deployment adapters.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Evidence-first retail demand and inventory decision support.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(api_router)
