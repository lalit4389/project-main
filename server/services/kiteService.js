import { KiteConnect } from 'kiteconnect';
import { db } from '../database/init.js';
import { encryptData, decryptData } from '../utils/encryption.js';
import createLogger from '../utils/logger.js';

const logger = createLogger('KiteService');

class KiteService {
  constructor() {
    this.kiteInstances = new Map(); // Store KiteConnect instances per user
  }

  // Initialize KiteConnect instance for a user
  async initializeKite(brokerConnection) {
    try {
      console.log('🔍 ===== BROKER CONNECTION DEBUG =====');
      console.log('🔍 Raw broker connection data:', {
        id: brokerConnection.id,
        user_id: brokerConnection.user_id,
        broker_name: brokerConnection.broker_name,
        has_api_key: !!brokerConnection.api_key,
        has_access_token: !!brokerConnection.access_token,
        api_key_encrypted_length: brokerConnection.api_key ? brokerConnection.api_key.length : 0,
        access_token_encrypted_length: brokerConnection.access_token ? brokerConnection.access_token.length : 0,
        is_active: brokerConnection.is_active,
        created_at: brokerConnection.created_at,
        updated_at: brokerConnection.updated_at
      });

      if (!brokerConnection.api_key) {
        throw new Error('API key is missing from broker connection');
      }

      if (!brokerConnection.access_token) {
        throw new Error('Access token is missing from broker connection');
      }

      console.log('🔍 Encrypted API Key:', brokerConnection.api_key);
      console.log('🔍 Encrypted Access Token:', brokerConnection.access_token);

      let apiKey, accessToken;
      
      try {
        apiKey = decryptData(brokerConnection.api_key);
        console.log('🔍 Decrypted API Key:', apiKey);
        console.log('🔍 API Key Length:', apiKey ? apiKey.length : 0);
        console.log('🔍 API Key Preview:', apiKey ? `${apiKey.substring(0, 8)}...${apiKey.substring(apiKey.length - 4)}` : 'null');
      } catch (decryptError) {
        console.error('❌ Failed to decrypt API key:', decryptError.message);
        throw new Error(`Failed to decrypt API key: ${decryptError.message}`);
      }

      try {
        accessToken = decryptData(brokerConnection.access_token);
        console.log('🔍 Decrypted Access Token:', accessToken);
        console.log('🔍 Access Token Length:', accessToken ? accessToken.length : 0);
        console.log('🔍 Access Token Preview:', accessToken ? `${accessToken.substring(0, 8)}...${accessToken.substring(accessToken.length - 4)}` : 'null');
      } catch (decryptError) {
        console.error('❌ Failed to decrypt access token:', decryptError.message);
        throw new Error(`Failed to decrypt access token: ${decryptError.message}`);
      }

      console.log('🔍 Creating KiteConnect instance with API Key:', apiKey);
      const kc = new KiteConnect({
        api_key: apiKey,
        debug: process.env.NODE_ENV === 'development'
      });

      console.log('🔍 Setting access token:', accessToken);
      kc.setAccessToken(accessToken);

      // Test the connection immediately
      console.log('🔍 Testing connection with Zerodha...');
      try {
        const profile = await kc.getProfile();
        console.log('✅ Connection test successful!');
        console.log('✅ User Name:', profile.user_name);
        console.log('✅ User ID:', profile.user_id);
        console.log('✅ Email:', profile.email);
        console.log('✅ Broker:', profile.broker);
      } catch (testError) {
        console.error('❌ Connection test failed:', testError);
        console.error('❌ Error details:', {
          message: testError.message,
          status: testError.status,
          error_type: testError.error_type,
          data: testError.data
        });
        throw new Error(`Invalid credentials: ${testError.message}`);
      }

      this.kiteInstances.set(brokerConnection.id, kc);
      logger.info(`KiteConnect instance initialized for broker connection ${brokerConnection.id}`);
      console.log('🔍 ===== END BROKER CONNECTION DEBUG =====');
      return kc;
    } catch (error) {
      logger.error('Failed to initialize Kite instance:', error);
      console.error('❌ Failed to initialize Kite instance:', error);
      throw new Error(`Failed to initialize broker connection: ${error.message}`);
    }
  }

  // Get or create KiteConnect instance
  async getKiteInstance(brokerConnectionId) {
    console.log('🔍 Getting KiteConnect instance for broker connection:', brokerConnectionId);
    
    if (this.kiteInstances.has(brokerConnectionId)) {
      console.log('✅ Using cached KiteConnect instance');
      return this.kiteInstances.get(brokerConnectionId);
    }

    console.log('🔍 Fetching broker connection from database...');
    const brokerConnection = await db.getAsync(
      'SELECT * FROM broker_connections WHERE id = ? AND is_active = 1',
      [brokerConnectionId]
    );

    if (!brokerConnection) {
      console.error('❌ Broker connection not found or inactive');
      throw new Error('Broker connection not found or inactive');
    }

    console.log('✅ Broker connection found, initializing KiteConnect...');
    return await this.initializeKite(brokerConnection);
  }

  // Place order with detailed logging
  async placeOrder(brokerConnectionId, orderParams) {
    try {
      console.log('🔍 ===== ORDER PLACEMENT DEBUG =====');
      console.log('🔍 Broker Connection ID:', brokerConnectionId);
      console.log('🔍 Order Parameters:', JSON.stringify(orderParams, null, 2));
      
      const kc = await this.getKiteInstance(brokerConnectionId);
      
      // Validate required parameters
      if (!orderParams.tradingsymbol) {
        throw new Error('tradingsymbol is required');
      }
      if (!orderParams.transaction_type) {
        throw new Error('transaction_type is required');
      }
      if (!orderParams.quantity) {
        throw new Error('quantity is required');
      }
      
      const orderData = {
        exchange: orderParams.exchange || 'NSE',
        tradingsymbol: orderParams.tradingsymbol,
        transaction_type: orderParams.transaction_type,
        quantity: parseInt(orderParams.quantity),
        order_type: orderParams.order_type || 'MARKET',
        product: orderParams.product || 'MIS',
        validity: orderParams.validity || 'DAY',
        disclosed_quantity: orderParams.disclosed_quantity || 0,
        trigger_price: orderParams.trigger_price || 0,
        squareoff: orderParams.squareoff || 0,
        stoploss: orderParams.stoploss || 0,
        trailing_stoploss: orderParams.trailing_stoploss || 0,
        tag: orderParams.tag || 'AutoTraderHub'
      };

      // Add price for limit orders
      if (orderParams.order_type === 'LIMIT' && orderParams.price) {
        orderData.price = parseFloat(orderParams.price);
      }

      console.log('🔍 Final order data for Kite API:', JSON.stringify(orderData, null, 2));
      
      // The KiteConnect placeOrder method expects variety as first parameter
      const variety = orderParams.variety || 'regular';
      console.log('🔍 Order variety:', variety);
      
      console.log('🔍 Calling kc.placeOrder...');
      const response = await kc.placeOrder(variety, orderData);
      
      console.log('✅ Order placed successfully!');
      console.log('✅ Response:', JSON.stringify(response, null, 2));
      console.log('🔍 ===== END ORDER PLACEMENT DEBUG =====');
      
      logger.info(`Order placed successfully: ${response.order_id}`);
      
      return {
        success: true,
        order_id: response.order_id,
        data: response
      };
    } catch (error) {
      console.log('🔍 ===== ORDER PLACEMENT ERROR DEBUG =====');
      console.error('❌ Failed to place order:', error);
      console.error('❌ Error type:', typeof error);
      console.error('❌ Error properties:', Object.keys(error));
      console.error('❌ Error message:', error.message);
      console.error('❌ Error status:', error.status);
      console.error('❌ Error error_type:', error.error_type);
      console.error('❌ Error data:', error.data);
      console.log('🔍 ===== END ORDER PLACEMENT ERROR DEBUG =====');
      
      logger.error('❌ Failed to place order:', error);
      throw new Error(`Order placement failed: ${error.message}`);
    }
  }

  // Rest of your methods remain the same...
  // (I'll include a few key ones with logging)

  async getProfile(brokerConnectionId) {
    try {
      console.log('🔍 Getting profile for broker connection:', brokerConnectionId);
      const kc = await this.getKiteInstance(brokerConnectionId);
      const profile = await kc.getProfile();
      console.log('✅ Profile retrieved:', profile.user_name);
      return profile;
    } catch (error) {
      console.error('❌ Failed to get profile:', error);
      logger.error('Failed to get profile:', error);
      throw new Error('Failed to get profile');
    }
  }

  // Test connection with detailed logging
  async testConnection(brokerConnectionId) {
    try {
      console.log('🔍 ===== CONNECTION TEST DEBUG =====');
      console.log('🔍 Testing connection for broker connection:', brokerConnectionId);
      
      const profile = await this.getProfile(brokerConnectionId);
      
      console.log('✅ Connection test successful!');
      console.log('✅ User details:', {
        user_name: profile.user_name,
        user_id: profile.user_id,
        email: profile.email,
        broker: profile.broker
      });
      console.log('🔍 ===== END CONNECTION TEST DEBUG =====');
      
      logger.info(`Connection test successful for broker connection ${brokerConnectionId}`);
      return {
        success: true,
        user_name: profile.user_name,
        user_id: profile.user_id,
        email: profile.email
      };
    } catch (error) {
      console.log('🔍 ===== CONNECTION TEST ERROR DEBUG =====');
      console.error('❌ Connection test failed:', error);
      console.log('🔍 ===== END CONNECTION TEST ERROR DEBUG =====');
      
      logger.error(`Connection test failed for broker connection ${brokerConnectionId}:`, error);
      throw error;
    }
  }

  // Add all other methods from your original file here...
  // (getOrderStatus, getOrders, cancelOrder, etc.)
}

export default new KiteService();
