"""
API v1 router
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, broker, orders, webhook

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(broker.router, prefix="/broker", tags=["broker"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(webhook.router, prefix="/webhook", tags=["webhook"])