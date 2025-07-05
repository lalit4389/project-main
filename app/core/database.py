"""
Database Configuration and Models
"""

import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, Float, 
    ForeignKey, Index, create_engine, MetaData
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import relationship, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine
if settings.DATABASE_URL.startswith("sqlite"):
    # For SQLite, use aiosqlite
    async_database_url = settings.DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
    engine = create_async_engine(async_database_url, echo=settings.DEBUG)
else:
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Create sync engine for initial setup
sync_engine = create_engine(
    settings.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://"),
    echo=settings.DEBUG
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# Base class for models
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    mobile_number = Column(String, nullable=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    broker_connections = relationship("BrokerConnection", back_populates="user")
    orders = relationship("Order", back_populates="user")
    positions = relationship("Position", back_populates="user")
    holdings = relationship("Holding", back_populates="user")
    webhook_logs = relationship("WebhookLog", back_populates="user")


class PendingRegistration(Base):
    __tablename__ = "pending_registrations"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=True)
    password = Column(String, nullable=False)
    mobile_number = Column(String, nullable=True)
    name = Column(String, nullable=False)
    identifier = Column(String, nullable=False)
    created_at = Column(Integer, nullable=False)  # Unix timestamp
    expires_at = Column(Integer, nullable=False)  # Unix timestamp


class OTP(Base):
    __tablename__ = "otps"
    
    id = Column(Integer, primary_key=True, index=True)
    identifier = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'email' or 'mobile'
    otp = Column(String, nullable=False)
    purpose = Column(String, nullable=False, default='registration')  # 'registration' or 'password_reset'
    expires_at = Column(Integer, nullable=False)  # Unix timestamp
    created_at = Column(Integer, nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    identifier = Column(String, nullable=False)
    token = Column(String, nullable=False)
    expires_at = Column(Integer, nullable=False)  # Unix timestamp
    created_at = Column(Integer, nullable=False)


class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_name = Column(String, nullable=False)
    connection_name = Column(String, nullable=True)
    api_key = Column(String, nullable=False)
    api_secret = Column(String, nullable=False)
    user_id_broker = Column(String, nullable=True)
    access_token = Column(String, nullable=True)
    public_token = Column(String, nullable=True)
    access_token_expires_at = Column(Integer, nullable=True)  # Unix timestamp
    webhook_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="broker_connections")
    orders = relationship("Order", back_populates="broker_connection")
    positions = relationship("Position", back_populates="broker_connection")
    holdings = relationship("Holding", back_populates="broker_connection")
    webhook_logs = relationship("WebhookLog", back_populates="broker_connection")
    
    # Index for better performance
    __table_args__ = (Index('idx_broker_connections_user_id', 'user_id'),)


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_connection_id = Column(Integer, ForeignKey("broker_connections.id"), nullable=False)
    broker_order_id = Column(String, nullable=True)
    symbol = Column(String, nullable=False)
    exchange = Column(String, nullable=False, default='NSE')
    quantity = Column(Integer, nullable=False)
    order_type = Column(String, nullable=False)  # MARKET, LIMIT, SL, SL-M
    transaction_type = Column(String, nullable=False)  # BUY, SELL
    product = Column(String, nullable=False, default='MIS')  # CNC, MIS, NRML
    price = Column(Float, nullable=True)
    trigger_price = Column(Float, nullable=True)
    executed_price = Column(Float, nullable=True)
    executed_quantity = Column(Integer, default=0)
    status = Column(String, default='PENDING')  # PENDING, OPEN, COMPLETE, CANCELLED, REJECTED
    status_message = Column(Text, nullable=True)
    pnl = Column(Float, default=0)
    webhook_data = Column(Text, nullable=True)  # JSON data from TradingView
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="orders")
    broker_connection = relationship("BrokerConnection", back_populates="orders")
    webhook_logs = relationship("WebhookLog", back_populates="order")


class Position(Base):
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_connection_id = Column(Integer, ForeignKey("broker_connections.id"), nullable=False)
    symbol = Column(String, nullable=False)
    exchange = Column(String, nullable=False, default='NSE')
    quantity = Column(Integer, nullable=False)
    average_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    pnl = Column(Float, default=0)
    pnl_percentage = Column(Float, default=0)
    product = Column(String, nullable=False, default='MIS')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="positions")
    broker_connection = relationship("BrokerConnection", back_populates="positions")


class Holding(Base):
    __tablename__ = "holdings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_connection_id = Column(Integer, ForeignKey("broker_connections.id"), nullable=False)
    symbol = Column(String, nullable=False)
    exchange = Column(String, nullable=False, default='NSE')
    quantity = Column(Integer, nullable=False)
    average_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    pnl = Column(Float, default=0)
    pnl_percentage = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="holdings")
    broker_connection = relationship("BrokerConnection", back_populates="holdings")


class WebhookLog(Base):
    __tablename__ = "webhook_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_connection_id = Column(Integer, ForeignKey("broker_connections.id"), nullable=True)
    payload = Column(Text, nullable=False)
    status = Column(String, nullable=False)  # RECEIVED, PROCESSING, SUCCESS, ERROR
    error_message = Column(Text, nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    processing_time = Column(Integer, nullable=True)  # milliseconds
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="webhook_logs")
    broker_connection = relationship("BrokerConnection", back_populates="webhook_logs")
    order = relationship("Order", back_populates="webhook_logs")


class MarketData(Base):
    __tablename__ = "market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False)
    exchange = Column(String, nullable=False, default='NSE')
    last_price = Column(Float, nullable=True)
    change = Column(Float, nullable=True)
    change_percent = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    open = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Database dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Initialize database
async def init_db():
    """Initialize database tables"""
    logger.info("🔧 Initializing database...")
    
    try:
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ Database tables created successfully")
        
        # Log table information
        table_names = [
            'users', 'pending_registrations', 'otps', 'password_reset_tokens',
            'broker_connections', 'orders', 'positions', 'holdings', 
            'webhook_logs', 'market_data'
        ]
        
        logger.info(f"📊 Created tables: {', '.join(table_names)}")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise