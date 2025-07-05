"""
Order status monitoring service
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Set

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, Order, BrokerConnection
from app.services.kite_service import KiteService

logger = logging.getLogger(__name__)


class OrderStatusService:
    """Service for monitoring order status updates"""
    
    def __init__(self):
        self.active_polling: Dict[str, bool] = {}
        self.polling_tasks: Dict[str, asyncio.Task] = {}
        self.kite_service = KiteService()
    
    async def start_order_status_polling(self, order_id: int, broker_connection_id: int, broker_order_id: str):
        """Start polling for order status updates"""
        polling_key = f"{order_id}-{broker_order_id}"
        
        if polling_key in self.active_polling:
            logger.debug(f"Already polling order {order_id}")
            return
        
        logger.info(f"Starting status polling for order {order_id} (broker order: {broker_order_id})")
        self.active_polling[polling_key] = True
        
        # Create polling task
        task = asyncio.create_task(
            self._poll_order_status(order_id, broker_connection_id, broker_order_id, polling_key)
        )
        self.polling_tasks[polling_key] = task
        
        # Auto-stop after 30 minutes
        asyncio.create_task(self._auto_stop_polling(polling_key, 30 * 60))
    
    async def _poll_order_status(self, order_id: int, broker_connection_id: int, broker_order_id: str, polling_key: str):
        """Poll order status from broker"""
        try:
            while polling_key in self.active_polling:
                try:
                    await self._check_and_update_order_status(order_id, broker_connection_id, broker_order_id, polling_key)
                    await asyncio.sleep(5)  # Poll every 5 seconds
                except Exception as e:
                    logger.error(f"Error polling order {order_id}: {e}")
                    await asyncio.sleep(10)  # Wait longer on error
        except asyncio.CancelledError:
            logger.info(f"Polling cancelled for order {order_id}")
        except Exception as e:
            logger.error(f"Unexpected error in polling for order {order_id}: {e}")
        finally:
            self.stop_polling(polling_key)
    
    async def _check_and_update_order_status(self, order_id: int, broker_connection_id: int, broker_order_id: str, polling_key: str):
        """Check and update order status from broker"""
        async with AsyncSessionLocal() as db:
            try:
                # Get current order
                result = await db.execute(select(Order).where(Order.id == order_id))
                current_order = result.scalar_one_or_none()
                
                if not current_order:
                    logger.warning(f"Order {order_id} not found in database")
                    self.stop_polling(polling_key)
                    return
                
                # Check if order is in final state
                if self.is_final_status(current_order.status):
                    logger.info(f"Order {order_id} already in final state: {current_order.status}")
                    self.stop_polling(polling_key)
                    return
                
                # Get broker connection
                result = await db.execute(
                    select(BrokerConnection).where(
                        BrokerConnection.id == broker_connection_id,
                        BrokerConnection.is_active == True
                    )
                )
                broker_connection = result.scalar_one_or_none()
                
                if not broker_connection:
                    logger.warning(f"Broker connection {broker_connection_id} not found or inactive")
                    self.stop_polling(polling_key)
                    return
                
                # Fetch order status from broker
                broker_order_data = None
                if broker_connection.broker_name.lower() == 'zerodha':
                    broker_order_data = await self.kite_service.get_order_status(broker_connection_id, broker_order_id)
                else:
                    logger.warning(f"Order status polling not implemented for {broker_connection.broker_name}")
                    self.stop_polling(polling_key)
                    return
                
                if not broker_order_data:
                    logger.warning(f"No order data received from broker for order {broker_order_id}")
                    return
                
                # Check if status changed
                new_status = self.map_broker_status(broker_order_data.get('status', ''))
                if new_status != current_order.status:
                    logger.info(f"Order {order_id} status changed: {current_order.status} -> {new_status}")
                    
                    # Update order in database
                    await self._update_order_in_database(db, order_id, broker_order_data, new_status)
                    
                    # If order reached final state, stop polling
                    if self.is_final_status(new_status):
                        logger.info(f"Order {order_id} reached final state: {new_status}")
                        self.stop_polling(polling_key)
                        
                        # Sync positions if completed
                        if new_status == 'COMPLETE':
                            try:
                                await self.kite_service.sync_positions(broker_connection_id)
                                logger.info(f"Positions synced after order {order_id} completion")
                            except Exception as sync_error:
                                logger.error(f"Failed to sync positions after order completion: {sync_error}")
                else:
                    logger.debug(f"Order {order_id} status unchanged: {current_order.status}")
                
            except Exception as e:
                logger.error(f"Error checking order status for {order_id}: {e}")
                
                # If authentication error, stop polling
                if 'Invalid' in str(e) or 'expired' in str(e):
                    logger.warning(f"Authentication error for order {order_id}, stopping polling")
                    self.stop_polling(polling_key)
    
    async def _update_order_in_database(self, db: AsyncSession, order_id: int, broker_order_data: dict, new_status: str):
        """Update order details in database"""
        try:
            update_data = {
                "status": new_status,
                "executed_price": broker_order_data.get('average_price') or broker_order_data.get('price'),
                "executed_quantity": broker_order_data.get('filled_quantity') or broker_order_data.get('quantity', 0),
                "status_message": str(broker_order_data),
                "updated_at": datetime.utcnow()
            }
            
            # Calculate P&L if order is completed
            if new_status == 'COMPLETE' and update_data["executed_price"] and update_data["executed_quantity"]:
                result = await db.execute(select(Order).where(Order.id == order_id))
                order = result.scalar_one_or_none()
                if order:
                    pnl = self._calculate_pnl(order, update_data)
                    update_data["pnl"] = pnl
            
            await db.execute(
                update(Order).where(Order.id == order_id).values(**update_data)
            )
            await db.commit()
            
            logger.info(f"Order {order_id} updated in database with status: {new_status}")
            
        except Exception as e:
            logger.error(f"Failed to update order {order_id} in database: {e}")
            await db.rollback()
            raise
    
    def _calculate_pnl(self, order: Order, update_data: dict) -> float:
        """Calculate P&L for completed orders"""
        try:
            original_price = float(order.price) if order.price else 0
            executed_price = float(update_data["executed_price"]) if update_data["executed_price"] else 0
            quantity = int(update_data["executed_quantity"]) if update_data["executed_quantity"] else 0
            
            if original_price == 0 or executed_price == 0 or quantity == 0:
                return 0
            
            if order.transaction_type == 'BUY':
                # For buy orders, P&L is negative (cost)
                pnl = -(executed_price * quantity)
            else:
                # For sell orders, P&L is positive (revenue)
                pnl = executed_price * quantity
            
            return round(pnl, 2)
        except Exception as e:
            logger.error(f"Error calculating P&L for order {order.id}: {e}")
            return 0
    
    def map_broker_status(self, broker_status: str) -> str:
        """Map broker-specific status to standard status"""
        status_map = {
            'COMPLETE': 'COMPLETE',
            'EXECUTED': 'COMPLETE',
            'OPEN': 'OPEN',
            'PENDING': 'PENDING',
            'CANCELLED': 'CANCELLED',
            'CANCELED': 'CANCELLED',
            'REJECTED': 'REJECTED',
            'FAILED': 'REJECTED'
        }
        
        return status_map.get(broker_status.upper(), 'PENDING')
    
    def is_final_status(self, status: str) -> bool:
        """Check if status is final (no more updates expected)"""
        final_statuses = ['COMPLETE', 'CANCELLED', 'REJECTED']
        return status.upper() in final_statuses
    
    def stop_polling(self, polling_key: str):
        """Stop polling for a specific order"""
        if polling_key in self.active_polling:
            del self.active_polling[polling_key]
        
        if polling_key in self.polling_tasks:
            task = self.polling_tasks[polling_key]
            if not task.done():
                task.cancel()
            del self.polling_tasks[polling_key]
        
        logger.info(f"Stopped polling for order: {polling_key}")
    
    async def _auto_stop_polling(self, polling_key: str, timeout_seconds: int):
        """Auto-stop polling after timeout"""
        await asyncio.sleep(timeout_seconds)
        if polling_key in self.active_polling:
            logger.info(f"Auto-stopping polling for order: {polling_key} after {timeout_seconds} seconds")
            self.stop_polling(polling_key)
    
    async def start_polling_for_open_orders(self):
        """Start polling for all open orders on service startup"""
        try:
            logger.info("Starting polling for all open orders")
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Order, BrokerConnection.broker_name).join(
                        BrokerConnection, Order.broker_connection_id == BrokerConnection.id
                    ).where(
                        Order.status.in_(['OPEN', 'PENDING']),
                        Order.broker_order_id.isnot(None),
                        BrokerConnection.is_active == True
                    )
                )
                open_orders = result.all()
                
                logger.info(f"Found {len(open_orders)} open orders to monitor")
                
                for order, broker_name in open_orders:
                    if order.broker_order_id and order.broker_connection_id:
                        # Start polling with random delay to avoid overwhelming broker API
                        delay = hash(str(order.id)) % 5  # 0-4 second delay
                        asyncio.create_task(self._delayed_start_polling(
                            order.id,
                            order.broker_connection_id,
                            order.broker_order_id,
                            delay
                        ))
                        
        except Exception as e:
            logger.error(f"Error starting polling for open orders: {e}")
    
    async def _delayed_start_polling(self, order_id: int, broker_connection_id: int, broker_order_id: str, delay: int):
        """Start polling with delay"""
        await asyncio.sleep(delay)
        await self.start_order_status_polling(order_id, broker_connection_id, broker_order_id)
    
    def get_polling_status(self) -> dict:
        """Get current polling status"""
        return {
            "active_polling": list(self.active_polling.keys()),
            "polling_count": len(self.active_polling)
        }
    
    async def stop_all_polling(self):
        """Stop all polling (for graceful shutdown)"""
        logger.info("Stopping all order status polling")
        
        # Cancel all tasks
        for polling_key, task in self.polling_tasks.items():
            if not task.done():
                task.cancel()
        
        # Clear all tracking
        self.active_polling.clear()
        self.polling_tasks.clear()
        
        logger.info("All order status polling stopped")