from fastapi import APIRouter
from app.api.endpoints import feeds, entries

api_router = APIRouter()

# Pievienojam maršrutus no atsevišķiem galapunktiem
api_router.include_router(feeds.router, prefix="/feeds", tags=["feeds"])
api_router.include_router(entries.router, prefix="/entries", tags=["entries"])