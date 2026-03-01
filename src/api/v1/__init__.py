"""API v1 routers for Phoenix AI Travel Companion."""

from fastapi import APIRouter

from src.api.v1 import auth, chat, poi, preferences, routes, voice

# Create main v1 router
router = APIRouter()

# Include all sub-routers
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(poi.router, prefix="/poi", tags=["POI"])
router.include_router(preferences.router, prefix="/preferences", tags=["Preferences"])
router.include_router(routes.router, prefix="/routes", tags=["Routes"])
router.include_router(voice.router, prefix="/voice", tags=["Voice"])

__all__ = ["router"]
