import express from 'express';
import { db } from '../database/init.js';
import { authenticateToken } from '../middleware/auth.js';
import kiteService from '../services/kiteService.js';

const router = express.Router();

// Get orders with enhanced filtering and real-time updates
router.get('/', authenticateToken, async (req, res) => {
  try {
    console.log('GET /api/orders - Request Query:', req.query);
    const { page = 1, limit = 50, status, symbol, broker_connection_id, sync = false } = req.query;
    const offset = (page - 1) * limit;

    // If sync is requested, sync orders from broker first
    if (sync === 'true' && broker_connection_id) {
      try {
        await syncOrdersFromBroker(req.user.id, broker_connection_id);
        console.log('Orders synced successfully for connection:', broker_connection_id);
      } catch (syncError) {
        console.error('Failed to sync orders:', syncError);
        // Continue with database query even if sync fails
      }
    }

    let query = `
      SELECT 
        o.*,
        bc.broker_name,
        bc.webhook_url
      FROM orders o
      LEFT JOIN broker_connections bc ON o.broker_connection_id = bc.id
      WHERE o.user_id = ?
    `;
    let params = [req.user.id];

    if (status && status !== 'all') {
      query += ' AND o.status = ?';
      params.push(status.toUpperCase());
    }

    if (symbol) {
      query += ' AND o.symbol LIKE ?';
      params.push(`%${symbol.toUpperCase()}%`);
    }

    if (broker_connection_id) {
      query += ' AND o.broker_connection_id = ?';
      params.push(parseInt(broker_connection_id));
    }

    query += ' ORDER BY o.created_at DESC LIMIT ? OFFSET ?';
    params.push(parseInt(limit), parseInt(offset));

    console.log('Executing orders query:', query, params);
    const orders = await db.allAsync(query, params);
    console.log('Orders fetched from DB:', orders.length, 'orders');

    // Get total count
    let countQuery = 'SELECT COUNT(*) as total FROM orders WHERE user_id = ?';
    let countParams = [req.user.id];

    if (status && status !== 'all') {
      countQuery += ' AND status = ?';
      countParams.push(status.toUpperCase());
    }

    if (symbol) {
      countQuery += ' AND symbol LIKE ?';
      countParams.push(`%${symbol.toUpperCase()}%`);
    }

    if (broker_connection_id) {
      countQuery += ' AND broker_connection_id = ?';
      countParams.push(parseInt(broker_connection_id));
    }

    console.log('Executing count query:', countQuery, countParams);
    const { total } = await db.getAsync(countQuery, countParams);
    console.log('Total orders count:', total);

    // Parse webhook_data for each order
    const enhancedOrders = orders.map(order => {
      let webhook_data = null;
      let status_message = null;
      try {
        webhook_data = order.webhook_data ? JSON.parse(order.webhook_data) : null;
      } catch (e) {
        console.error('Error parsing webhook_data for order ID', order.id, ':', e.message, 'Data:', order.webhook_data);
      }
      try {
        status_message = order.status_message ? JSON.parse(order.status_message) : null;
      } catch (e) {
        console.error('Error parsing status_message for order ID', order.id, ':', e.message, 'Data:', order.status_message);
      }
      return {
        ...order,
        webhook_data,
        status_message
      };
    });

    res.json({
      orders: enhancedOrders,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total,
        pages: Math.ceil(total / limit)
      }
    });
  } catch (error) {
    console.error('Get orders error:', error);
    res.status(500).json({ error: 'Failed to fetch orders' });
  }
});

// Get specific order details with real-time broker data
router.get('/:orderId', authenticateToken, async (req, res) => {
  try {
    const { orderId } = req.params;
    const { sync = false } = req.query;

    // Get order from database
    const order = await db.getAsync(`
      SELECT 
        o.*,
        bc.broker_name,
        bc.webhook_url,
        bc.is_active as broker_active
      FROM orders o
      LEFT JOIN broker_connections bc ON o.broker_connection_id = bc.id
      WHERE o.id = ? AND o.user_id = ?
    `, [orderId, req.user.id]);

    if (!order) {
      return res.status(404).json({ error: 'Order not found' });
    }

    let brokerOrderData = null;

    // If sync is requested and we have a broker order ID, fetch from broker
    if (sync === 'true' && order.broker_order_id && order.broker_connection_id) {
      try {
        if (order.broker_name === 'zerodha') {
          brokerOrderData = await kiteService.getOrderStatus(order.broker_connection_id, order.broker_order_id);
          
          // Update order status if different from broker
          if (brokerOrderData && brokerOrderData.status !== order.status) {
            await db.runAsync(`
              UPDATE orders 
              SET status = ?, executed_price = ?, executed_quantity = ?, status_message = ?, updated_at = CURRENT_TIMESTAMP
              WHERE id = ?
            `, [
              brokerOrderData.status,
              brokerOrderData.average_price || brokerOrderData.price,
              brokerOrderData.filled_quantity || brokerOrderData.quantity,
              JSON.stringify(brokerOrderData),
              orderId
            ]);

            // Update the order object with new data
            order.status = brokerOrderData.status;
            order.executed_price = brokerOrderData.average_price || brokerOrderData.price;
            order.executed_quantity = brokerOrderData.filled_quantity || brokerOrderData.quantity;
            order.status_message = JSON.stringify(brokerOrderData);
          }
        }
      } catch (brokerError) {
        console.error('Failed to fetch order from broker:', brokerError);
        // Continue with database data
      }
    }

    res.json({
      order: {
        ...order,
        webhook_data: order.webhook_data ? JSON.parse(order.webhook_data) : null,
        status_message: order.status_message ? JSON.parse(order.status_message) : null,
        broker_data: brokerOrderData
      }
    });
  } catch (error) {
    console.error('Get order details error:', error);
    res.status(500).json({ error: 'Failed to fetch order details' });
  }
});

// Sync all orders from broker 
router.post('/sync/:brokerConnectionId', authenticateToken, async (req, res) => {
  try {
    const { brokerConnectionId } = req.params;

    // Verify broker connection belongs to user
    const brokerConnection = await db.getAsync(
      'SELECT * FROM broker_connections WHERE id = ? AND user_id = ? AND is_active = 1',
      [brokerConnectionId, req.user.id]
    );

    if (!brokerConnection) {
      return res.status(404).json({ error: 'Broker connection not found' });
    }

    const syncedOrders = await syncOrdersFromBroker(req.user.id, brokerConnectionId);

    res.json({
      message: 'Orders synced successfully',
      syncedCount: syncedOrders.length,
      orders: syncedOrders
    });
  } catch (error) {
    console.error('Sync orders error:', error);
    res.status(500).json({ error: 'Failed to sync orders' });
  }
});

// Get positions with real-time updates
router.get('/positions', authenticateToken, async (req, res) => {
  try {
    console.log('GET /api/orders/positions - Request Query:', req.query);
    const { broker_connection_id, sync = false } = req.query;

    // If sync is requested, sync positions from broker first
    if (sync === 'true' && broker_connection_id) {
      try {
        console.log('Attempting to sync positions for broker_connection_id:', broker_connection_id);
        await kiteService.syncPositions(broker_connection_id);
        console.log('Positions synced successfully for connection:', broker_connection_id);
      } catch (syncError) {
        console.error('Failed to sync positions:', syncError);
        // Continue with database query
      }
    }

    let query = `
      SELECT 
        p.*,
        bc.broker_name
      FROM positions p
      LEFT JOIN broker_connections bc ON p.broker_connection_id = bc.id
      WHERE p.user_id = ?
    `;
    let params = [req.user.id];

    if (broker_connection_id) {
      query += ' AND p.broker_connection_id = ?';
      params.push(parseInt(broker_connection_id));
    }

    query += ' ORDER BY p.updated_at DESC';

    console.log('Executing positions query:', query, params);
    const positions = await db.allAsync(query, params);
    console.log('Positions fetched from DB:', positions.length, 'positions');

    res.json({ positions });
  } catch (error) {
    console.error('Get positions error:', error);
    res.status(500).json({ error: 'Failed to fetch positions' });
  }
});

// Get P&L summary with enhanced calculations
router.get('/pnl', authenticateToken, async (req, res) => {
  try {
    console.log('GET /api/orders/pnl - Request Query:', req.query);
    const { period = '1M', broker_connection_id } = req.query;
    
    // Calculate date range based on period
    let dateFilter = '';
    switch (period) {
      case '1W':
        dateFilter = "AND created_at >= date('now', '-7 days')";
        break;
      case '1M':
        dateFilter = "AND created_at >= date('now', '-1 month')";
        break;
      case '3M':
        dateFilter = "AND created_at >= date('now', '-3 months')";
        break;
      case '6M':
        dateFilter = "AND created_at >= date('now', '-6 months')";
        break;
      case '1Y':
        dateFilter = "AND created_at >= date('now', '-1 year')";
        break;
      default:
        dateFilter = '';
    }

    let brokerFilter = '';
    let params = [req.user.id];
    
    if (broker_connection_id) {
      brokerFilter = 'AND broker_connection_id = ?';
      params.push(parseInt(broker_connection_id));
    }

    // Get total P&L
    const totalPnL = await db.getAsync(
      `SELECT 
        COALESCE(SUM(pnl), 0) as total_pnl,
        COUNT(*) as total_trades,
        COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
        AVG(pnl) as avg_pnl,
        MAX(pnl) as max_profit,
        MIN(pnl) as max_loss
      FROM orders 
      WHERE user_id = ? AND status IN ('COMPLETE', 'EXECUTED') ${dateFilter} ${brokerFilter}`,
      params
    );

    // Get daily P&L for chart
    const dailyPnL = await db.allAsync(
      `SELECT 
        DATE(created_at) as date,
        COALESCE(SUM(pnl), 0) as pnl,
        COUNT(*) as trades,
        COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades
      FROM orders 
      WHERE user_id = ? AND status IN ('COMPLETE', 'EXECUTED') ${dateFilter} ${brokerFilter}
      GROUP BY DATE(created_at)
      ORDER BY date DESC
      LIMIT 30`,
      params
    );

    // Get symbol-wise P&L
    const symbolPnL = await db.allAsync(
      `SELECT 
        symbol,
        COALESCE(SUM(pnl), 0) as total_pnl,
        COUNT(*) as trades,
        AVG(pnl) as avg_pnl
      FROM orders 
      WHERE user_id = ? AND status IN ('COMPLETE', 'EXECUTED') ${dateFilter} ${brokerFilter}
      GROUP BY symbol
      ORDER BY total_pnl DESC
      LIMIT 10`,
      params
    );

    // Calculate win rate and other metrics
    const winRate = totalPnL.total_trades > 0 
      ? (totalPnL.winning_trades / totalPnL.total_trades) * 100 
      : 0;

    const profitFactor = totalPnL.max_loss < 0 
      ? Math.abs(totalPnL.max_profit / totalPnL.max_loss)
      : 0;

    res.json({
      summary: {
        totalPnL: totalPnL.total_pnl || 0,
        totalTrades: totalPnL.total_trades || 0,
        winRate: winRate.toFixed(2),
        winningTrades: totalPnL.winning_trades || 0,
        avgPnL: totalPnL.avg_pnl || 0,
        maxProfit: totalPnL.max_profit || 0,
        maxLoss: totalPnL.max_loss || 0,
        profitFactor: profitFactor.toFixed(2)
      },
      chartData: dailyPnL.reverse(),
      symbolBreakdown: symbolPnL
    });
  } catch (error) {
    console.error('Get P&L error:', error);
    res.status(500).json({ error: 'Failed to fetch P&L data' });
  }
});

// Update order status manually
router.patch('/:orderId/status', authenticateToken, async (req, res) => {
  try {
    const { orderId } = req.params;
    const { status, executed_price, executed_quantity, notes } = req.body;

    // Verify order belongs to user
    const order = await db.getAsync(
      'SELECT * FROM orders WHERE id = ? AND user_id = ?',
      [orderId, req.user.id]
    );

    if (!order) {
      return res.status(404).json({ error: 'Order not found' });
    }

    // Update order
    await db.runAsync(`
      UPDATE orders 
      SET status = ?, executed_price = ?, executed_quantity = ?, 
          status_message = ?, updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `, [
      status,
      executed_price || order.executed_price,
      executed_quantity || order.executed_quantity,
      notes || order.status_message,
      orderId
    ]);

    res.json({ message: 'Order status updated successfully' });
  } catch (error) {
    console.error('Update order status error:', error);
    res.status(500).json({ error: 'Failed to update order status' });
  }
});

// Helper function to sync orders from broker
async function syncOrdersFromBroker(userId, brokerConnectionId) {
  try {
    const brokerConnection = await db.getAsync(
      'SELECT * FROM broker_connections WHERE id = ? AND user_id = ? AND is_active = 1',
      [brokerConnectionId, userId]
    );

    if (!brokerConnection) {
      throw new Error('Broker connection not found');
    }

    let brokerOrders = [];

    if (brokerConnection.broker_name === 'zerodha') {
      // Get orders from Kite Connect
      const kc = await kiteService.getKiteInstance(brokerConnectionId);
      brokerOrders = await kc.getOrders();
    } else {
      // For other brokers, return empty array (implement as needed)
      console.log(`Order sync not implemented for ${brokerConnection.broker_name}`);
      return [];
    }

    const syncedOrders = [];

    for (const brokerOrder of brokerOrders) {
      // Check if order already exists in database
      const existingOrder = await db.getAsync(
        'SELECT id FROM orders WHERE broker_order_id = ? AND broker_connection_id = ?',
        [brokerOrder.order_id, brokerConnectionId]
      );

      if (existingOrder) {
        // Update existing order
        await db.runAsync(`
          UPDATE orders 
          SET status = ?, executed_price = ?, executed_quantity = ?, 
              status_message = ?, updated_at = CURRENT_TIMESTAMP
          WHERE id = ?
        `, [
          brokerOrder.status,
          brokerOrder.average_price || brokerOrder.price,
          brokerOrder.filled_quantity || 0,
          JSON.stringify(brokerOrder),
          existingOrder.id
        ]);

        syncedOrders.push({ ...brokerOrder, database_id: existingOrder.id, action: 'updated' });
      } else {
        // Create new order record
        const result = await db.runAsync(`
          INSERT INTO orders (
            user_id, broker_connection_id, broker_order_id, symbol, exchange,
            quantity, order_type, transaction_type, product, price, trigger_price,
            executed_price, executed_quantity, status, status_message
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `, [
          userId,
          brokerConnectionId,
          brokerOrder.order_id,
          brokerOrder.tradingsymbol,
          brokerOrder.exchange,
          brokerOrder.quantity,
          brokerOrder.order_type,
          brokerOrder.transaction_type,
          brokerOrder.product,
          brokerOrder.price,
          brokerOrder.trigger_price || null,
          brokerOrder.average_price || null,
          brokerOrder.filled_quantity || 0,
          brokerOrder.status,
          JSON.stringify(brokerOrder)
        ]);

        syncedOrders.push({ ...brokerOrder, database_id: result.lastID, action: 'created' });
      }
    }

    // Update last sync time
    await db.runAsync(
      'UPDATE broker_connections SET last_sync = CURRENT_TIMESTAMP WHERE id = ?',
      [brokerConnectionId]
    );

    console.log(`✅ Synced ${syncedOrders.length} orders for broker connection ${brokerConnectionId}`);
    return syncedOrders;
  } catch (error) {
    console.error('Failed to sync orders from broker:', error);
    throw error;
  }
}

export default router;