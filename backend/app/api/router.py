from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.evaluations import router as evaluations_router
from app.api.routes.profiles import router as profiles_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
api_router.include_router(evaluations_router, prefix="/evaluations", tags=["evaluations"])
