import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, DollarSign, Activity, Copy, CheckCircle, Bot, ExternalLink, Wifi } from 'lucide-react';
import { ordersAPI, brokerAPI } from '../../services/api';
import toast from 'react-hot-toast';

const Overview: React.FC = () => {
  const [webhookCopied, setWebhookCopied] = useState<number | null>(null);
  const [pnlData, setPnlData] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [recentOrders, setRecentOrders] = useState<any[]>([]);
  const [brokerConnections, setBrokerConnections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [pnlResponse, positionsResponse, ordersResponse, connectionsResponse] = await Promise.all([
        ordersAPI.getPnL({ period: '1M' }),
        ordersAPI.getPositions(),
        ordersAPI.getOrders({ limit: 5 }),
        brokerAPI.getConnections()
      ]);

      setPnlData(pnlResponse.data);
      setPositions(positionsResponse.data.positions);
      setRecentOrders(ordersResponse.data.orders);
      const connections = connectionsResponse.data.connections;
      setBrokerConnections(connections);
      
      console.log('=== BROKER CONNECTIONS DEBUG ===');
      console.log('All connections:', connections);
      console.log('Active connections:', connections.filter(c => c.is_active));
      console.log('Active connections with webhook:', connections.filter(c => c.is_active && c.webhook_url));
      console.log('Has active connection with webhook:', connections.some(c => c.is_active && c.webhook_url));
      console.log('================================');
    } catch (error) {
      toast.error('Failed to fetch dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const copyWebhookUrl = (webhookUrl: string, connectionId: number) => {
    navigator.clipboard.writeText(webhookUrl);
    setWebhookCopied(connectionId);
    toast.success('Webhook URL copied!');
    setTimeout(() => setWebhookCopied(null), 2000);
  };

  const stats = [
    {
      title: 'Total P&L',
      value: `₹${pnlData?.summary?.totalPnL?.toLocaleString() || '0'}`,
      change: '+12.3%',
      trend: 'up',
      icon: DollarSign,
      color: 'from-olive-500 to-olive-600'
    },
    {
      title: 'Win Rate',
      value: `${pnlData?.summary?.winRate || '0'}%`,
      change: '+2.1%',
      trend: 'up',
      icon: TrendingUp,
      color: 'from-dark-600 to-dark-700'
    },
    {
      title: 'Active Positions',
      value: positions.length.toString(),
      change: `${positions.filter(p => p.pnl > 0).length} profitable`,
      trend: 'neutral',
      icon: Activity,
      color: 'from-olive-600 to-olive-700'
    },
    {
      title: 'Total Trades',
      value: pnlData?.summary?.totalTrades?.toString() || '0',
      change: 'This month',
      trend: 'up',
      icon: Bot,
      color: 'from-dark-500 to-olive-600'
    }
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-olive-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Enhanced Welcome Section with 3D Effects */}
      <motion.div
        initial={{ opacity: 0, y: 20, rotateX: -10 }}
        animate={{ opacity: 1, y: 0, rotateX: 0 }}
        className="bg-gradient-to-r from-olive-800 to-dark-800 rounded-3xl p-8 text-white relative overflow-hidden"
        style={{ 
          transformStyle: 'preserve-3d',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 40px rgba(138, 156, 112, 0.2)'
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-r from-olive-600/20 to-dark-600/20 backdrop-blur-sm"></div>
        <div className="relative z-10">
          <h1 className="text-3xl md:text-4xl font-bold mb-3">Welcome back, Trader!</h1>
          <p className="text-olive-200">Your automated trading dashboard is ready. Monitor your strategies and performance.</p>
        </div>
        
        {/* 3D Floating Elements */}
        <motion.div
          animate={{ 
            rotateY: [0, 360],
            y: [0, -10, 0]
          }}
          transition={{ 
            duration: 10, 
            repeat: Infinity,
            ease: "linear"
          }}
          className="absolute top-4 right-4 w-16 h-16 bg-olive-500/20 rounded-full backdrop-blur-sm"
          style={{ transform: 'perspective(1000px) rotateX(45deg)' }}
        />
      </motion.div>

      {/* Enhanced Stats Grid with 3D Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 20, rotateY: -15 }}
            animate={{ opacity: 1, y: 0, rotateY: 0 }}
            transition={{ delay: index * 0.1, duration: 0.6 }}
            whileHover={{ 
              scale: 1.05,
              rotateY: 5,
              rotateX: 5,
            }}
            className="group bg-dark-800/50 backdrop-blur-xl rounded-2xl p-6 border border-olive-500/20 hover:border-olive-400/40 transition-all duration-500 shadow-xl"
            style={{ 
              transformStyle: 'preserve-3d',
              boxShadow: '0 20px 40px -12px rgba(0, 0, 0, 0.4), 0 0 30px rgba(138, 156, 112, 0.1)'
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <motion.div 
                className={`w-14 h-14 bg-gradient-to-r ${stat.color} rounded-xl flex items-center justify-center shadow-lg group-hover:animate-pulse-glow`}
                whileHover={{ rotateY: 180 }}
                transition={{ duration: 0.6 }}
              >
                <stat.icon className="w-7 h-7 text-white" />
              </motion.div>
              <div className={`text-sm font-medium px-3 py-1 rounded-full ${
                stat.trend === 'up' ? 'text-olive-300 bg-olive-800/30' :
                stat.trend === 'down' ? 'text-red-300 bg-red-800/30' :
                'text-olive-200 bg-dark-700/30'
              }`}>
                {stat.change}
              </div>
            </div>
            <h3 className="text-2xl font-bold text-white mb-1 group-hover:text-olive-300 transition-colors">{stat.value}</h3>
            <p className="text-olive-200/70">{stat.title}</p>
          </motion.div>
        ))}
      </div>

      {/* Enhanced Broker Connections Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        whileHover={{ scale: 1.01, rotateX: 2 }}
        className="bg-dark-800/50 backdrop-blur-xl rounded-2xl p-6 border border-olive-500/20 shadow-xl"
        style={{ 
          transformStyle: 'preserve-3d',
          boxShadow: '0 20px 40px -12px rgba(0, 0, 0, 0.4)'
        }}
      >
        <h2 className="text-xl font-bold text-white mb-4 flex items-center">
          <Wifi className="w-6 h-6 mr-2 text-olive-400" />
          Active Broker Connections
        </h2>
        
        {brokerConnections.some(connection => connection.is_active) ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {brokerConnections
              .filter(connection => connection.is_active)
              .map((connection, index) => {
                const brokers = [
                  { 
                    id: 'zerodha', 
                    name: 'Zerodha', 
                    logo: '🔥', 
                  },
                  { 
                    id: 'upstox', 
                    name: 'Upstox', 
                    logo: '⚡', 
                  },
                  { 
                    id: '5paisa', 
                    name: '5Paisa', 
                    logo: '💎', 
                  }
                ];
                const broker = brokers.find(b => b.id === connection.broker_name.toLowerCase());
                return (
                  <motion.div
                    key={connection.id}
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="bg-dark-900/50 rounded-2xl p-4 border border-olive-500/20"
                  >
                    <div className="flex items-center space-x-4">
                      <div className="text-4xl">
                        {broker?.logo || '🏦'}
                      </div>
                      <div className="flex-1">
                        <h3 className="font-bold text-white capitalize">{connection.broker_name}</h3>
                        {connection.webhook_url ? (
                          <div className="flex items-center space-x-2 mt-1">
                            <code className="text-sm text-olive-300 break-all font-mono bg-dark-800/50 p-2 rounded">
                              {connection.webhook_url}
                            </code>
                            <motion.button
                              onClick={() => copyWebhookUrl(connection.webhook_url, connection.id)}
                              whileHover={{ scale: 1.05 }}
                              whileTap={{ scale: 0.95 }}
                              className="text-olive-400 hover:text-olive-300"
                            >
                              {webhookCopied === connection.id ? (
                                <CheckCircle className="w-5 h-5" />
                              ) : (
                                <Copy className="w-5 h-5" />
                              )}
                            </motion.button>
                          </div>
                        ) : (
                          <p className="text-olive-400 text-sm mt-1 italic">No webhook URL available</p>
                        )}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
          </div>
        ) : (
          <div className="text-center py-8">
            <Wifi className="w-16 h-16 text-olive-400/50 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">No Active Broker Connections</h3>
            <p className="text-olive-200/70 mb-4">
              Connect a broker account to see active connections here.
            </p>
            <motion.button
              onClick={() => window.location.href = '/dashboard/brokers'}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="inline-flex items-center space-x-2 bg-gradient-to-r from-olive-600 to-olive-700 text-white px-6 py-3 rounded-xl font-medium hover:shadow-lg transition-all"
            >
              <ExternalLink className="w-4 h-4" />
              <span>Connect Broker</span>
            </motion.button>
          </div>
        )}
      </motion.div>

      {/* Enhanced Recent Trades Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        whileHover={{ scale: 1.005 }}
        className="bg-dark-800/50 backdrop-blur-xl rounded-2xl p-6 border border-olive-500/20 shadow-xl"
        style={{ 
          transformStyle: 'preserve-3d',
          boxShadow: '0 20px 40px -12px rgba(0, 0, 0, 0.4)'
        }}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-white">Recent Trades</h2>
          <button 
            onClick={() => window.location.href = '/dashboard/orders'}
            className="text-olive-400 hover:text-olive-300 font-medium transition-colors"
          >
            View All
          </button>
        </div>
        
        {recentOrders.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-olive-500/20">
                  <th className="text-left py-3 px-4 font-semibold text-olive-200">Symbol</th>
                  <th className="text-left py-3 px-4 font-semibold text-olive-200">Type</th>
                  <th className="text-left py-3 px-4 font-semibold text-olive-200">Qty</th>
                  <th className="text-left py-3 px-4 font-semibold text-olive-200">Price</th>
                  <th className="text-left py-3 px-4 font-semibold text-olive-200">P&L</th>
                  <th className="text-left py-3 px-4 font-semibold text-olive-200">Status</th>
                </tr>
              </thead>
              <tbody>
                {recentOrders.map((order, index) => (
                  <motion.tr 
                    key={order.id} 
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="border-b border-olive-500/10 hover:bg-olive-800/10 transition-colors"
                  >
                    <td className="py-3 px-4 font-medium text-white">{order.symbol}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        order.transaction_type === 'BUY' ? 'bg-olive-800/30 text-olive-300' : 'bg-red-800/30 text-red-300'
                      }`}>
                        {order.transaction_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-olive-200">{order.quantity}</td>
                    <td className="py-3 px-4 text-olive-200">₹{order.executed_price || order.price}</td>
                    <td className="py-3 px-4">
                      <span className={`font-medium ${
                        order.pnl > 0 ? 'text-olive-400' : order.pnl < 0 ? 'text-red-400' : 'text-olive-200'
                      }`}>
                        {order.pnl > 0 ? '+' : ''}₹{order.pnl}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        order.status === 'COMPLETE' ? 'bg-olive-800/30 text-olive-300' :
                        order.status === 'OPEN' ? 'bg-yellow-800/30 text-yellow-300' :
                        'bg-dark-700/30 text-olive-200'
                      }`}>
                        {order.status}
                      </span>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8">
            <TrendingUp className="w-16 h-16 text-olive-400/50 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">No Recent Trades</h3>
            <p className="text-olive-200/70">
              Your recent trading activity will appear here once you start placing orders.
            </p>
          </div>
        )}
      </motion.div>
    </div>
  );
};

export default Overview;