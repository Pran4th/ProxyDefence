from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "proxydefence-api",
        "timestamp": datetime.utcnow().isoformat()
    }