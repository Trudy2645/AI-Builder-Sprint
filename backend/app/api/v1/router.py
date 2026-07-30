from fastapi import APIRouter

from app.api.v1.profiles import router as profiles_router
from app.api.v1.public_listings import router as public_listings_router

router = APIRouter()
router.include_router(public_listings_router)
router.include_router(profiles_router)
