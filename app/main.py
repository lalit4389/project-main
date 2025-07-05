"""
FastAPI Main Application
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import setup_logging
from app.core.security import get_password_hash
from app.api.v1.api import api_router
from app.services.order_status_service import OrderStatusService
from app.core.exceptions import AutoTraderException

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize services
order_status_service = OrderStatusService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("🚀 Starting AutoTraderHub API Server")
    logger.info(f"🌐 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🔧 Debug Mode: {settings.DEBUG}")
    
    # Initialize database
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    # Start order status service
    try:
        await order_status_service.start_polling_for_open_orders()
        logger.info("✅ Order status service initialized successfully")
    except Exception as e:
        logger.error(f"⚠️ Order status service initialization failed: {e}")
        # Don't raise, service can still function without real-time updates
    
    logger.info("🚀 ================================")
    logger.info(f"🚀 Server running at http://{settings.HOST}:{settings.PORT}")
    logger.info(f"📊 AutoTraderHub API is ready")
    logger.info(f"🕒 Started at: {datetime.now().isoformat()}")
    logger.info(f"🔄 Order Status Service: Active")
    logger.info("🚀 ================================")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down AutoTraderHub API Server")
    await order_status_service.stop_all_polling()
    logger.info("✅ Graceful shutdown completed")

# Create FastAPI application
app = FastAPI(
    title="AutoTraderHub API",
    description="Automated Trading Platform API",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    # Generate request ID
    request_id = f"{start_time.timestamp():.0f}"
    request.state.request_id = request_id
    
    # Log request
    logger.info(f"🌐 {request.method} {request.url.path} - Request ID: {request_id}")
    
    response = await call_next(request)
    
    # Log response
    process_time = (datetime.now() - start_time).total_seconds() * 1000
    logger.info(f"✅ {request.method} {request.url.path} - {response.status_code} - {process_time:.2f}ms")
    
    return response

# Exception handlers
@app.exception_handler(AutoTraderException)
async def autotrader_exception_handler(request: Request, exc: AutoTraderException):
    logger.error(f"❌ AutoTrader Exception: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "type": "AutoTraderException",
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path),
            "method": request.method,
            "request_id": getattr(request.state, "request_id", None)
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"❌ HTTP Exception: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "type": "HTTPException",
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path),
            "method": request.method,
            "request_id": getattr(request.state, "request_id", None)
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"❌ Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "details": exc.errors(),
            "type": "ValidationError",
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path),
            "method": request.method,
            "request_id": getattr(request.state, "request_id", None)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Unhandled Exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
            "type": "InternalServerError",
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path),
            "method": request.method,
            "request_id": getattr(request.state, "request_id", None)
        }
    )

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    polling_status = order_status_service.get_polling_status()
    
    return {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "database": "connected",
        "order_polling": {
            "active": polling_status["polling_count"],
            "orders": polling_status["active_polling"]
        }
    }

# Include API routes
app.include_router(api_router, prefix="/api")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AutoTraderHub API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower()
    )