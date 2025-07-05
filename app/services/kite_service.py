"""
Kite Connect service for Zerodha integration
"""

import logging
from typing import Dict, Optional, Any
from kiteconnect import KiteConnect

from app.core.database import AsyncSessionLocal, BrokerConnection
from app.core.security import decrypt_data
from app.core.exceptions import BrokerError
from sqlalchemy import select

logger = logging.getLogger(__name__)


class KiteService:
    """Service for Kite Connect API integration"""
    
    def __init__(self):
        self.kite_instances: Dict[int, KiteConnect] = {}
    
    async def generate_access_token(self, api_key: str, api_secret: str, request_token: str) -> dict:
        """Generate access token from request token"""
        try:
            logger.info(f"🔑 Generating access token with API key: {api_key[:8]}...")
            
            kc = KiteConnect(api_key=api_key)
            response = kc.generate_session(request_token, api_secret)
            
            logger.info("✅ Access token generated successfully")
            return response
            
        except Exception as e:
            logger.error(f"❌ Failed to generate access token: {e}")
            raise BrokerError(f"Failed to generate access token: {str(e)}")
    
    async def get_kite_instance(self, broker_connection_id: int) -> KiteConnect:
        """Get or create KiteConnect instance"""
        logger.info(f"🔍 Getting KiteConnect instance for broker connection: {broker_connection_id}")
        
        if broker_connection_id in self.kite_instances:
            logger.info("✅ Using cached KiteConnect instance")
            return self.kite_instances[broker_connection_id]
        
        logger.info("🔍 Fetching broker connection from database...")
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(BrokerConnection).where(
                    BrokerConnection.id == broker_connection_id,
                    BrokerConnection.is_active == True
                )
            )
            broker_connection = result.scalar_one_or_none()
        
        if not broker_connection:
            logger.error("❌ Broker connection not found or inactive")
            raise BrokerError("Broker connection not found or inactive")
        
        logger.info("✅ Broker connection found, initializing KiteConnect...")
        return await self._initialize_kite(broker_connection)
    
    async def _initialize_kite(self, broker_connection: BrokerConnection) -> KiteConnect:
        """Initialize KiteConnect instance"""
        try:
            logger.info("🔍 ===== BROKER CONNECTION DEBUG =====")
            logger.info(f"🔍 Connection ID: {broker_connection.id}")
            logger.info(f"🔍 Broker: {broker_connection.broker_name}")
            logger.info(f"🔍 Has API Key: {bool(broker_connection.api_key)}")
            logger.info(f"🔍 Has Access Token: {bool(broker_connection.access_token)}")
            
            if not broker_connection.api_key:
                raise BrokerError("API key is missing from broker connection")
            
            if not broker_connection.access_token:
                raise BrokerError("Access token is missing from broker connection")
            
            # Check token expiry
            import time
            now = int(time.time())
            if broker_connection.access_token_expires_at and broker_connection.access_token_expires_at < now:
                raise BrokerError("Access token has expired. Please refresh your token.")
            
            # Decrypt credentials
            try:
                api_key = decrypt_data(broker_connection.api_key)
                access_token = decrypt_data(broker_connection.access_token)
                
                logger.info(f"🔍 Decrypted API Key: {api_key[:8]}...")
                logger.info(f"🔍 Decrypted Access Token: {access_token[:8]}...")
                
            except Exception as e:
                logger.error(f"❌ Failed to decrypt credentials: {e}")
                raise BrokerError(f"Failed to decrypt credentials: {str(e)}")
            
            # Create KiteConnect instance
            logger.info("🔍 Creating KiteConnect instance...")
            kc = KiteConnect(api_key=api_key)
            kc.set_access_token(access_token)
            
            # Test connection
            logger.info("🔍 Testing connection with Zerodha...")
            try:
                profile = kc.profile()
                logger.info("✅ Connection test successful!")
                logger.info(f"✅ User: {profile.get('user_name', 'Unknown')}")
                logger.info(f"✅ Email: {profile.get('email', 'Unknown')}")
            except Exception as e:
                logger.error(f"❌ Connection test failed: {e}")
                raise BrokerError(f"Invalid credentials: {str(e)}")
            
            # Cache instance
            self.kite_instances[broker_connection.id] = kc
            logger.info(f"✅ KiteConnect instance cached for connection {broker_connection.id}")
            logger.info("🔍 ===== END BROKER CONNECTION DEBUG =====")
            
            return kc
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Kite instance: {e}")
            raise BrokerError(f"Failed to initialize broker connection: {str(e)}")
    
    async def place_order(self, broker_connection_id: int, order_params: dict) -> dict:
        """Place order with detailed logging"""
        try:
            logger.info("🔍 ===== ORDER PLACEMENT DEBUG =====")
            logger.info(f"🔍 Broker Connection ID: {broker_connection_id}")
            logger.info(f"🔍 Order Parameters: {order_params}")
            
            kc = await self.get_kite_instance(broker_connection_id)
            
            # Validate required parameters
            required_fields = ['tradingsymbol', 'transaction_type', 'quantity']
            for field in required_fields:
                if not order_params.get(field):
                    raise BrokerError(f"{field} is required")
            
            # Prepare order data
            order_data = {
                'exchange': order_params.get('exchange', 'NSE'),
                'tradingsymbol': order_params['tradingsymbol'],
                'transaction_type': order_params['transaction_type'],
                'quantity': int(order_params['quantity']),
                'order_type': order_params.get('order_type', 'MARKET'),
                'product': order_params.get('product', 'MIS'),
                'validity': order_params.get('validity', 'DAY'),
                'disclosed_quantity': order_params.get('disclosed_quantity', 0),
                'trigger_price': order_params.get('trigger_price', 0),
                'squareoff': order_params.get('squareoff', 0),
                'stoploss': order_params.get('stoploss', 0),
                'trailing_stoploss': order_params.get('trailing_stoploss', 0),
                'tag': order_params.get('tag', 'AutoTraderHub')
            }
            
            # Add price for limit orders
            if order_params.get('order_type') == 'LIMIT' and order_params.get('price'):
                order_data['price'] = float(order_params['price'])
            
            logger.info(f"🔍 Final order data: {order_data}")
            
            # Place order
            variety = order_params.get('variety', 'regular')
            logger.info(f"🔍 Order variety: {variety}")
            
            response = kc.place_order(variety, **order_data)
            
            logger.info("✅ Order placed successfully!")
            logger.info(f"✅ Response: {response}")
            logger.info("🔍 ===== END ORDER PLACEMENT DEBUG =====")
            
            return {
                "success": True,
                "order_id": response['order_id'],
                "data": response
            }
            
        except Exception as e:
            logger.error("🔍 ===== ORDER PLACEMENT ERROR DEBUG =====")
            logger.error(f"❌ Failed to place order: {e}")
            logger.error("🔍 ===== END ORDER PLACEMENT ERROR DEBUG =====")
            raise BrokerError(f"Order placement failed: {str(e)}")
    
    async def get_profile(self, broker_connection_id: int) -> dict:
        """Get user profile"""
        try:
            logger.info(f"🔍 Getting profile for broker connection: {broker_connection_id}")
            kc = await self.get_kite_instance(broker_connection_id)
            profile = kc.profile()
            logger.info(f"✅ Profile retrieved: {profile.get('user_name', 'Unknown')}")
            return profile
        except Exception as e:
            logger.error(f"❌ Failed to get profile: {e}")
            raise BrokerError(f"Failed to get profile: {str(e)}")
    
    async def get_positions(self, broker_connection_id: int) -> dict:
        """Get positions with enhanced error handling"""
        try:
            logger.info(f"🔍 Getting positions for broker connection: {broker_connection_id}")
            kc = await self.get_kite_instance(broker_connection_id)
            positions = kc.positions()
            logger.info(f"✅ Positions retrieved: {len(positions.get('net', []))} net positions")
            
            return {
                'net': positions.get('net', []),
                'day': positions.get('day', []),
                'raw': positions
            }
        except Exception as e:
            logger.error(f"❌ Failed to get positions: {e}")
            raise BrokerError(f"Failed to get positions: {str(e)}")
    
    async def get_holdings(self, broker_connection_id: int) -> list:
        """Get holdings with enhanced error handling"""
        try:
            logger.info(f"🔍 Getting holdings for broker connection: {broker_connection_id}")
            kc = await self.get_kite_instance(broker_connection_id)
            holdings = kc.holdings()
            logger.info(f"✅ Holdings retrieved: {len(holdings)} holdings")
            return holdings
        except Exception as e:
            logger.error(f"❌ Failed to get holdings: {e}")
            raise BrokerError(f"Failed to get holdings: {str(e)}")
    
    async def get_orders(self, broker_connection_id: int) -> list:
        """Get orders with enhanced error handling"""
        try:
            logger.info(f"🔍 Getting orders for broker connection: {broker_connection_id}")
            kc = await self.get_kite_instance(broker_connection_id)
            orders = kc.orders()
            logger.info(f"✅ Orders retrieved: {len(orders)} orders")
            return orders
        except Exception as e:
            logger.error(f"❌ Failed to get orders: {e}")
            raise BrokerError(f"Failed to get orders: {str(e)}")
    
    async def get_order_status(self, broker_connection_id: int, order_id: str) -> dict:
        """Get order status with enhanced error handling and retry logic"""
        try:
            logger.info(f"🔍 Getting order status for: {broker_connection_id}, {order_id}")
            kc = await self.get_kite_instance(broker_connection_id)
            
            # Try to get order history first
            try:
                order_history = kc.order_history(order_id)
                logger.info(f"✅ Order history retrieved: {len(order_history)} entries")
                
                if order_history:
                    latest_status = order_history[-1]  # Last entry is latest
                    logger.info(f"✅ Latest order status: {latest_status}")
                    return latest_status
                else:
                    raise BrokerError(f"No order history found for order {order_id}")
                    
            except Exception as history_error:
                logger.warning(f"⚠️ Failed to get order history, trying orders list: {history_error}")
                
                # Fallback: get all orders and find the specific one
                all_orders = kc.orders()
                matching_order = next((order for order in all_orders if order['order_id'] == order_id), None)
                
                if matching_order:
                    logger.info(f"✅ Order found in orders list: {matching_order}")
                    return matching_order
                else:
                    raise BrokerError(f"Order {order_id} not found in broker account")
                    
        except Exception as e:
            logger.error(f"❌ Failed to get order status: {e}")
            raise BrokerError(f"Failed to get order status: {str(e)}")
    
    async def test_connection(self, broker_connection_id: int) -> dict:
        """Test connection with detailed logging"""
        try:
            logger.info("🔍 ===== CONNECTION TEST DEBUG =====")
            logger.info(f"🔍 Testing connection for broker connection: {broker_connection_id}")
            
            profile = await self.get_profile(broker_connection_id)
            
            logger.info("✅ Connection test successful!")
            logger.info(f"✅ User details: {profile.get('user_name', 'Unknown')}")
            logger.info("🔍 ===== END CONNECTION TEST DEBUG =====")
            
            return {
                "success": True,
                "user_name": profile.get('user_name'),
                "user_id": profile.get('user_id'),
                "email": profile.get('email'),
                "broker": profile.get('broker')
            }
        except Exception as e:
            logger.error("🔍 ===== CONNECTION TEST ERROR DEBUG =====")
            logger.error(f"❌ Connection test failed: {e}")
            logger.error("🔍 ===== END CONNECTION TEST ERROR DEBUG =====")
            raise e
    
    async def sync_positions(self, broker_connection_id: int):
        """Sync positions to database"""
        try:
            positions = await self.get_positions(broker_connection_id)
            
            # Here you would implement database sync logic
            # For now, just return the positions
            return positions
            
        except Exception as e:
            logger.error(f"❌ Failed to sync positions: {e}")
            raise e
    
    def clear_cached_instance(self, broker_connection_id: int):
        """Clear cached instance (useful when token is refreshed)"""
        if broker_connection_id in self.kite_instances:
            del self.kite_instances[broker_connection_id]
            logger.info(f"🗑️ Cleared cached KiteConnect instance for connection: {broker_connection_id}")