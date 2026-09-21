"""Stable API router composition.

Keep route modules focused on one public capability so future deployments can
add authenticated versions without changing the application entrypoint.
"""

from fastapi import APIRouter

from app.api.routes import connector_runs, public_benchmark_runs, system


api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(connector_runs.router)
api_router.include_router(public_benchmark_runs.router)
