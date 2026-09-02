from fastapi import APIRouter

from src.api.internal import jobs, projects, scripts, shots

internal_router = APIRouter(prefix="/internal/v1")
internal_router.include_router(projects.router)
internal_router.include_router(scripts.router)
internal_router.include_router(jobs.router)
internal_router.include_router(shots.router)
