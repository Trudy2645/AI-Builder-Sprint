from fastapi import APIRouter

from app.api.v1.ai_jobs import router as ai_jobs_router
from app.api.v1.auth import router as auth_router
from app.api.v1.contracts import router as contracts_router
from app.api.v1.documents import router as documents_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.profiles import router as profiles_router
from app.api.v1.public_listings import router as public_listings_router
from app.api.v1.revisions import router as revisions_router
from app.api.v1.seller_listings import router as seller_listings_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(ai_jobs_router)
router.include_router(public_listings_router)
router.include_router(profiles_router)
router.include_router(contracts_router)
router.include_router(documents_router)
router.include_router(revisions_router)
router.include_router(seller_listings_router)
router.include_router(notifications_router)
