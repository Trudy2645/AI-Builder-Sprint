from fastapi import APIRouter

from app.api.v1.profiles import router as profiles_router

router = APIRouter()
router.include_router(profiles_router)
