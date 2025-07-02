import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { db } from '../database/init.js';
import { authenticateToken } from '../middleware/auth.js';
import { encryptData, decryptData, testEncryption } from '../utils/encryption.js';
import kiteService from '../services/kiteService.js';
import createLogger from '../utils/logger.js';

const logger = createLogger('WebhookHandler');

const router = express.Router();

// Test encryption on startup
testEncryption();

// Get broker connections with enhanced data
router.get('/connections', authenticateToken, async (req, res) => {
  try {
    const connections = await db.allAsync(`
      SELECT 
        id, broker_name, connection_name, is_active, created_at, last_sync, webhook_url,
        access_token_expires_at,
        CASE WHEN access_token IS NOT NULL AND access_token != '' THEN 1 ELSE 0 END as is_authenticated
      FROM broker_connections 
      WHERE user_id = ?
      ORDER BY created_at DESC
    `, [req.user.id]);

    // Check if access tokens are expired and mark them
    const now = Math.floor(Date.now() / 1000);
    const enhancedConnections = connections.map(conn => ({
      ...conn,
      token_expired: conn.access_token_expires_at && conn.access_token_expires_at < now,
      needs_token_refresh: conn.access_token_expires_at && (conn.access_token_expires_at - now) < 3600 // Less than 1 hour
    }));

    res.json({ connections: enhancedConnections });
  } catch (error) {
    console.error('Get connections error:', error);
    res.status(500).json({ error: 'Failed to fetch connections' });
  }
});

// Get specific broker connection details
router.get('/connections/:id', authenticateToken, async (req, res) => {
  try {
    const connection = await db.getAsync(`
      SELECT 
        id, broker_name, connection_name, is_active, created_at, last_sync, webhook_url,
        user_id_broker, access_token_expires_at,
        CASE WHEN access_token IS NOT NULL AND access_token != '' THEN 1 ELSE 0 END as is_authenticated
      FROM broker_connections 
      WHERE id = ? AND user_id = ?
    `, [req.params.id, req.user.id]);

    if (!connection) {
      return res.status(404).json({ error: 'Broker connection not found' });
    }

    const now = Math.floor(Date.now() / 1000);
    connection.token_expired = connection.access_token_expires_at && connection.access_token_expires_at < now;
    connection.needs_token_refresh = connection.access_token_expires_at && (connection.access_token_expires_at - now) < 3600;

    res.json({ connection });
  } catch (error) {
    console.error('Get connection details error:', error);
    res.status(500).json({ error: 'Failed to fetch connection details' });
  }
});

// Connect broker - Step 1: Store credentials and generate login URL
router.post('/connect', authenticateToken, async (req, res) => {
  try {
    const { brokerName, apiKey, apiSecret, userId, connectionName } = req.body;

    console.log('📡 Broker connection request:', { brokerName, userId, connectionName, hasApiKey: !!apiKey, hasApiSecret: !!apiSecret });

    if (!brokerName || !apiKey || !apiSecret) {
      return res.status(400).json({ error: 'Broker name, API key, and API secret are required' });
    }

    // Check connection limit (max 5 per user)
    const existingConnections = await db.allAsync(
      'SELECT COUNT(*) as count FROM broker_connections WHERE user_id = ? AND is_active = 1',
      [req.user.id]
    );

    if (existingConnections[0].count >= 5) {
      return res.status(400).json({ error: 'Maximum 5 broker connections allowed per user' });
    }

    // Generate unique webhook URL for this connection
    const webhookId = uuidv4();
    const baseUrl = `${req.protocol}://${req.get('host')}`;
    const webhookUrl = `${baseUrl}/api/webhook/${req.user.id}/${webhookId}`;

    console.log('🔗 Generated webhook URL:', webhookUrl);

    // Generate connection name if not provided
    const finalConnectionName = connectionName || `${brokerName} Connection ${Date.now()}`;

    let connectionId;
    
    try {
      // Test encryption before storing
      const testEncrypted = encryptData('test');
      const testDecrypted = decryptData(testEncrypted);
      if (testDecrypted !== 'test') {
        throw new Error('Encryption test failed');
      }

      const encryptedApiKey = encryptData(apiKey);
      const encryptedApiSecret = encryptData(apiSecret);

      // Create new connection
      const result = await db.runAsync(`
        INSERT INTO broker_connections 
        (user_id, broker_name, connection_name, api_key, api_secret, user_id_broker, webhook_url) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `, [req.user.id, brokerName.toLowerCase(), finalConnectionName, encryptedApiKey, encryptedApiSecret, userId, webhookUrl]);
      
      connectionId = result.lastID;
      console.log('✅ Created new broker connection:', connectionId);
    } catch (encryptionError) {
      console.error('❌ Encryption error:', encryptionError);
      return res.status(500).json({ error: 'Failed to encrypt credentials. Please try again.' });
    }

    // For Zerodha, generate login URL with proper redirect URL
    if (brokerName.toLowerCase() === 'zerodha') {
      try {
        const redirectUrl = `${baseUrl}/api/broker/auth/zerodha/callback?connection_id=${connectionId}`;
        
        // Generate Zerodha login URL
        const loginUrl = `https://kite.zerodha.com/connect/login?api_key=${apiKey}&v=3&redirect_url=${encodeURIComponent(redirectUrl)}`;
        
        console.log('🔐 Generated Zerodha login URL for connection:', connectionId);
        
        res.json({ 
          message: 'Broker credentials stored. Please complete authentication.',
          connectionId,
          loginUrl,
          webhookUrl,
          requiresAuth: true,
          redirectUrl,
          connectionName: finalConnectionName
        });
      } catch (error) {
        console.error('❌ Failed to generate login URL:', error);
        res.status(400).json({ error: 'Invalid API key or failed to generate login URL' });
      }
    } else {
      // For other brokers, mark as connected (mock implementation)
      console.log('✅ Connected to broker:', brokerName);
      res.json({ 
        message: 'Broker connected successfully',
        connectionId,
        webhookUrl,
        requiresAuth: false,
        connectionName: finalConnectionName
      });
    }
  } catch (error) {
    console.error('❌ Connect broker error:', error);
    res.status(500).json({ error: 'Failed to connect broker. Please check your credentials and try again.' });
  }
});

// Generate new access token for existing connectio
router.post('/refresh-token/:connectionId', authenticateToken, async (req, res) => {
  try {
    const { connectionId } = req.params;
    const { userId } = req.user.id;
    logger.info('🔄 Refreshing access token for connection:', userId);

    logger.info('🔄 Refreshing access token for connection:', connectionId);

    // Get connection details
    const connection = await db.getAsync(
      'SELECT * FROM broker_connections WHERE id = ? AND user_id = ? ',
      [connectionId, req.user.id]
    );

    logger.info(`✅ DB Result: ${JSON.stringify(connection, null, 2)}`);

    if (!connection) {
      console.warn('❌ No active broker connection found for this user & ID');
    } else {
      console.log('✅ Broker connection data:', JSON.stringify(connection, null, 2));
    }


    if (!connection) {
      return res.status(404).json({ error: 'Broker connection not found' });
    }

    if (connection.broker_name.toLowerCase() === 'zerodha') {
      try {
        logger.info('🔎 Broker type:', connection.broker_name);

        const apiKey = decryptData(connection.api_key);
        const baseUrl = `${req.protocol}://${req.get('host')}`;
        const redirectUrl = `${baseUrl}/api/broker/auth/zerodha/callback?connection_id=${connectionId}&refresh=true`;
        logger.info('🔁 Generated redirect URL:', redirectUrl);
        // Generate Zerodha login URL for token refresh
        const loginUrl = `https://kite.zerodha.com/connect/login?api_key=${apiKey}&v=3&redirect_url=${encodeURIComponent(redirectUrl)}`;
        logger.info('🔐 Final Zerodha login URL:', loginUrl);
        
        logger.info('🔐 Generated Zerodha token refresh URL for connection:', connectionId);
        
        res.json({ 
          message: 'Please complete authentication to refresh your access token.',
          loginUrl,
          requiresAuth: true
        });
      } catch (error) {
        console.error('❌ Failed to generate token refresh URL:', error);
        res.status(400).json({ error: 'Failed to generate token refresh URL' });
      }
    } else {
      // For other brokers, implement their token refresh mechanism
      res.status(400).json({ error: 'Token refresh not implemented for this broker' });
    }
  } catch (error) {
    console.error('❌ Refresh token error:', error);
    res.status(500).json({ error: 'Failed to refresh access token' });
  }
});

// Zerodha OAuth callback handler - This is the redirect URL endpoint
router.get('/auth/zerodha/callback', async (req, res) => {
  try {
    const { request_token, action, status, connection_id, refresh } = req.query;

    console.log('📡 Zerodha callback received:', { request_token, action, status, connection_id, refresh });

    // Check if authentication was successful
    if (action !== 'login' || status !== 'success' || !request_token) {
      return res.status(400).send(`
        <html>
          <head><title>Authentication Failed</title></head>
          <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #dc3545;">❌ Authentication Failed</h1>
            <p>Zerodha authentication was not successful.</p>
            <p>Error: ${status || 'Unknown error'}</p>
            <button onclick="window.close()" style="padding: 10px 20px; background: #6c757d; color: white; border: none; border-radius: 5px; cursor: pointer;">Close Window</button>
          </body>
        </html>
      `);
    }

    if (!connection_id) {
      return res.status(400).send(`
        <html>
          <head><title>Missing Connection ID</title></head>
          <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #dc3545;">❌ Missing Connection ID</h1>
            <p>Connection ID is required for authentication.</p>
            <button onclick="window.close()" style="padding: 10px 20px; background: #6c757d; color: white; border: none; border-radius: 5px; cursor: pointer;">Close Window</button>
          </body>
        </html>
      `);
    }

    // Get broker connection
    const connection = await db.getAsync(
      'SELECT * FROM broker_connections WHERE id = ?',
      [connection_id]
    );

    if (!connection) {
      return res.status(404).send(`
        <html>
          <head><title>Connection Not Found</title></head>
          <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #dc3545;">❌ Connection Not Found</h1>
            <p>Broker connection not found.</p>
            <button onclick="window.close()" style="padding: 10px 20px; background: #6c757d; color: white; border: none; border-radius: 5px; cursor: pointer;">Close Window</button>
          </body>
        </html>
      `);
    }

    try {
      // Decrypt credentials
      const apiKey = decryptData(connection.api_key);
      const apiSecret = decryptData(connection.api_secret);
      
      console.log('🔐 Generating access token for connection:', connection_id);
      
      // Generate access token using KiteConnect
      const accessTokenResponse = await kiteService.generateAccessToken(apiKey, apiSecret, request_token);
      
      if (!accessTokenResponse || !accessTokenResponse.access_token) {
        throw new Error('Failed to generate access token');
      }

      const accessToken = accessTokenResponse.access_token;
      const publicToken = accessTokenResponse.public_token || '';
      
      // Set token expiry (Zerodha tokens expire at 6 AM IST next day)
      const now = new Date();
      const tomorrow = new Date(now);
      tomorrow.setDate(tomorrow.getDate() + 1);
      tomorrow.setHours(6, 0, 0, 0); // 6 AM IST
      const expiresAt = Math.floor(tomorrow.getTime() / 1000);

      // Store access token and public token
      await db.runAsync(`
        UPDATE broker_connections 
        SET access_token = ?, public_token = ?, access_token_expires_at = ?, is_active = 1, updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
      `, [encryptData(accessToken), encryptData(publicToken), expiresAt, connection_id]);

      console.log('✅ Zerodha authentication completed for connection:', connection_id);

      const actionText = refresh === 'true' ? 'Token Refreshed' : 'Authentication Successful';

      // Return success page
      res.send(`
        <html>
          <head>
            <title>${actionText}</title>
            <style>
              body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f8f9fa; }
              .success-container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto; }
              .success-icon { font-size: 48px; margin-bottom: 20px; }
              .success-title { color: #28a745; margin-bottom: 15px; }
              .success-message { color: #6c757d; margin-bottom: 30px; line-height: 1.6; }
              .close-btn { padding: 12px 24px; background: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
              .close-btn:hover { background: #218838; }
            </style>
          </head>
          <body>
            <div class="success-container">
              <div class="success-icon">✅</div>
              <h1 class="success-title">${actionText}!</h1>
              <p class="success-message">
                Your Zerodha account has been successfully ${refresh === 'true' ? 'refreshed' : 'connected'} to AutoTraderHub.<br>
                Access token expires: ${new Date(expiresAt * 1000).toLocaleString()}<br>
                You can now close this window and return to the dashboard.
              </p>
              <button class="close-btn" onclick="window.close()">Close Window</button>
            </div>
            <script>
              // Auto-close after 5 seconds
              setTimeout(() => {
                window.close();
              }, 5000);
            </script>
          </body>
        </html>
      `);

    } catch (authError) {
      console.error('❌ Authentication error:', authError);
      res.status(500).send(`
        <html>
          <head><title>Authentication Error</title></head>
          <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: #dc3545;">❌ Authentication Error</h1>
            <p>Failed to complete authentication: ${authError.message}</p>
            <button onclick="window.close()" style="padding: 10px 20px; background: #6c757d; color: white; border: none; border-radius: 5px; cursor: pointer;">Close Window</button>
          </body>
        </html>
      `);
    }

  } catch (error) {
    console.error('❌ Callback handler error:', error);
    res.status(500).send(`
      <html>
        <head><title>Server Error</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
          <h1 style="color: #dc3545;">❌ Server Error</h1>
          <p>An unexpected error occurred: ${error.message}</p>
          <button onclick="window.close()" style="padding: 10px 20px; background: #6c757d; color: white; border: none; border-radius: 5px; cursor: pointer;">Close Window</button>
        </body>
        </html>
    `);
  }
});

// Disconnect broker
router.post('/disconnect', authenticateToken, async (req, res) => {
  try {
    const { connectionId } = req.body;

    await db.runAsync(
      'UPDATE broker_connections SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?',
      [connectionId, req.user.id]
    );

    res.json({ message: 'Broker disconnected successfully' });
  } catch (error) {
    console.error('Disconnect broker error:', error);
    res.status(500).json({ error: 'Failed to disconnect broker' });
  }
});

// Delete broker connection
router.delete('/connections/:id', authenticateToken, async (req, res) => {
  try {
    const { id } = req.params;

    const result = await db.runAsync(
      'DELETE FROM broker_connections WHERE id = ? AND user_id = ?',
      [id, req.user.id]
    );

    if (result.changes === 0) {
      return res.status(404).json({ error: 'Broker connection not found' });
    }

    res.json({ message: 'Broker connection deleted successfully' });
  } catch (error) {
    console.error('Delete broker connection error:', error);
    res.status(500).json({ error: 'Failed to delete broker connection' });
  }
});

// Mock sync positions
router.post('/sync/positions/:connectionId', authenticateToken, async (req, res) => {
  try {
    const { connectionId } = req.params;

    // Verify connection belongs to user
    const connection = await db.getAsync(
      'SELECT id FROM broker_connections WHERE id = ? AND user_id = ? AND is_active = 1',
      [connectionId, req.user.id]
    );

    if (!connection) {
      return res.status(404).json({ error: 'Broker connection not found' });
    }

    // Try to sync positions using KiteService
    try {
      const positions = await kiteService.getPositions(connectionId);
      res.json({ 
        message: 'Positions synced successfully',
        positions: positions || []
      });
    } catch (syncError) {
      console.error('Failed to sync positions from broker:', syncError);
      // Return mock data if sync fails
      const mockPositions = [
        {
          symbol: 'RELIANCE',
          quantity: 50,
          averagePrice: 2450,
          currentPrice: 2475,
          pnl: 1250,
          pnlPercentage: 1.02
        },
        {
          symbol: 'TCS',
          quantity: -25,
          averagePrice: 3200,
          currentPrice: 3180,
          pnl: 500,
          pnlPercentage: 0.63
        }
      ];

      res.json({ 
        message: 'Positions synced successfully (mock data)',
        positions: mockPositions
      });
    }
  } catch (error) {
    console.error('Sync positions error:', error);
    res.status(500).json({ error: 'Failed to sync positions' });
  }
});

// Enhanced test connection with proper error handling
router.post('/test/:connectionId', authenticateToken, async (req, res) => {
  try {
    const { connectionId } = req.params;

    console.log('🧪 Testing connection for ID:', connectionId);

    // Verify connection belongs to user
    const connection = await db.getAsync(
      'SELECT * FROM broker_connections WHERE id = ? AND user_id = ? AND is_active = 1',
      [connectionId, req.user.id]
    );

    if (!connection) {
      return res.status(404).json({ error: 'Broker connection not found' });
    }

    // Check if access token exists and is not expired
    const now = Math.floor(Date.now() / 1000);
    if (!connection.access_token) {
      return res.status(400).json({ 
        error: 'No access token found. Please authenticate first.',
        needsAuth: true 
      });
    }

    if (connection.access_token_expires_at && connection.access_token_expires_at < now) {
      return res.status(400).json({ 
        error: 'Access token has expired. Please refresh your token.',
        tokenExpired: true 
      });
    }

    try {
      // Test connection using KiteService
      const testResult = await kiteService.testConnection(connectionId);
      
      res.json({ 
        message: 'Broker connection is working',
        profile: testResult,
        tokenExpiresAt: connection.access_token_expires_at,
        tokenExpiresIn: connection.access_token_expires_at - now
      });
    } catch (testError) {
      console.error('❌ Connection test failed:', testError);
      
      // Check if it's a token-related error
      if (testError.message && testError.message.includes('api_key') || testError.message.includes('access_token')) {
        return res.status(401).json({ 
          error: 'Invalid or expired credentials. Please refresh your access token.',
          tokenExpired: true,
          details: testError.message
        });
      }
      
      res.status(500).json({ 
        error: 'Connection test failed',
        details: testError.message
      });
    }
  } catch (error) {
    console.error('Test connection error:', error);
    res.status(500).json({ error: 'Broker connection test failed' });
  }
});

export default router;