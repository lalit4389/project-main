import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001/api';

// Create axios instance with better error handling
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  console.log(`🌐 API Request: ${config.method?.toUpperCase()} ${config.url}`);
  return config;
});

// Enhanced response interceptor with better error handling
api.interceptors.response.use(
  (response) => {
    console.log(`✅ API Response: ${response.config.method?.toUpperCase()} ${response.config.url} - ${response.status}`);
    return response;
  },
  (error) => {
    console.error(`❌ API Error: ${error.config?.method?.toUpperCase()} ${error.config?.url}`, error);
    
    if (error.response?.status === 401) {
      localStorage.removeItem('authToken');
      window.location.href = '/login';
    }
    
    // Enhanced error information
    if (error.code === 'ECONNREFUSED' || error.code === 'ERR_NETWORK') {
      console.error('❌ Server connection failed. Please check if the server is running.');
      error.message = 'Unable to connect to server. Please check your connection and try again.';
    }
    
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  getProfile: () => api.get('/auth/me'),
  verifyOtp: ({ identifier, otp }) => api.post('/auth/verify-otp', { identifier, otp }),
  resendOtp: ({ identifier }) => api.post('/auth/resend-otp', { identifier }),
  verifyOtpForReset: ({ identifier, otp }) => api.post('/auth/verify-otp-reset', { identifier, otp }),
  forgotPassword: (data) => api.post('/auth/forgot-password', data),
  resetPassword: ({ resetToken, newPassword }) => api.post('/auth/reset-password', { resetToken, newPassword }),
};

// Enhanced Broker API with new features
export const brokerAPI = {
  getConnections: () => api.get('/broker/connections'),
  getConnection: (id) => api.get(`/broker/connections/${id}`),
  connect: async (data) => {
    try {
      console.log('🔗 Attempting broker connection with data:', { 
        brokerName: data.brokerName, 
        connectionName: data.connectionName,
        hasApiKey: !!data.apiKey, 
        hasApiSecret: !!data.apiSecret,
        userId: data.userId 
      });
      
      const response = await api.post('/broker/connect', data);
      console.log('✅ Broker connection response:', response.data);
      return response;
    } catch (error) {
      console.error('❌ Broker connection failed:', error);
      throw error;
    }
  },
  disconnect: (connectionId) => api.post('/broker/disconnect', { connectionId }),
  deleteConnection: (connectionId) => api.delete(`/broker/connections/${connectionId}`),
  refreshToken: (connectionId) => api.post(`/broker/refresh-token/${connectionId}`),
  completeZerodhaAuth: (connectionId, requestToken) => api.post('/broker/auth/zerodha', { connectionId, requestToken }),
  syncPositions: (connectionId) => api.post(`/broker/sync/positions/${connectionId}`),
  syncHoldings: (connectionId) => api.post(`/broker/sync/holdings/${connectionId}`),
  getMarketData: (connectionId, instruments) => api.get(`/broker/market-data/${connectionId}`, { params: { instruments } }),
  testConnection: (connectionId) => api.post(`/broker/test/${connectionId}`),
};

// Enhanced Orders API with real-time capabilities
export const ordersAPI = {
  getOrders: (params) => api.get('/orders', { params }),
  getOrderDetails: (orderId, params) => api.get(`/orders/${orderId}`, { params }),
  syncOrders: (brokerConnectionId) => api.post(`/orders/sync/${brokerConnectionId}`),
  updateOrderStatus: (orderId, data) => api.patch(`/orders/${orderId}/status`, data),
  getPositions: (params) => api.get('/orders/positions', { params }),
  getPnL: (params) => api.get('/orders/pnl', { params }),
};

// Webhook API
export const webhookAPI = {
  getLogs: (userId, params) => api.get(`/webhook/logs/${userId}`, { params }),
  testWebhook: (userId, webhookId) => api.post(`/webhook/test/${userId}/${webhookId}`),
};

export default api;