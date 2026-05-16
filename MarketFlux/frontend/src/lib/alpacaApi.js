import api from '@/lib/api';

const alpacaApi = {
  async getStatus() {
    const res = await api.get('/alpaca/status');
    return res.data;
  },

  async getAccount() {
    const res = await api.get('/alpaca/account');
    return res.data;
  },

  async submitOrder(payload) {
    const res = await api.post('/alpaca/orders', payload);
    return res.data;
  },

  async listOrders(status = 'all', limit = 50) {
    const res = await api.get('/alpaca/orders', { params: { status, limit } });
    return res.data;
  },

  async getOrder(orderId) {
    const res = await api.get(`/alpaca/orders/${orderId}`);
    return res.data;
  },

  async cancelOrder(orderId) {
    const res = await api.delete(`/alpaca/orders/${orderId}`);
    return res.data;
  },

  async cancelAllOrders() {
    const res = await api.delete('/alpaca/orders');
    return res.data;
  },

  async getPositions() {
    const res = await api.get('/alpaca/positions');
    return res.data;
  },

  async closePosition(symbol, qty = null) {
    const res = await api.post('/alpaca/positions/close', { symbol, qty });
    return res.data;
  },

  async liquidateAll() {
    const res = await api.post('/alpaca/positions/liquidate');
    return res.data;
  },

  async getPortfolioHistory(period = '1M', timeframe = '1D') {
    const res = await api.get('/alpaca/portfolio-history', { params: { period, timeframe } });
    return res.data;
  },

  async getAsset(symbol) {
    const res = await api.get(`/alpaca/assets/${symbol}`);
    return res.data;
  },
};

export default alpacaApi;
