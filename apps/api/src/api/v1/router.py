from fastapi import APIRouter

from src.api.v1 import auth, jobs, projects, scripts

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(scripts.router)
api_router.include_router(jobs.router)
