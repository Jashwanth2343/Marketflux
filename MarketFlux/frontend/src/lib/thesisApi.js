import api from '@/lib/api';

const thesisApi = {
  async listTheses() {
    const res = await api.get('/vnext/theses');
    return res.data;
  },

  async getThesis(thesisId) {
    const res = await api.get(`/vnext/theses/${thesisId}`);
    return res.data;
  },

  async createThesis(payload) {
    const res = await api.post('/vnext/theses', payload);
    return res.data;
  },

  async reviseThesis(thesisId, payload) {
    const res = await api.post(`/vnext/theses/${thesisId}/revise`, payload);
    return res.data;
  },

  async createMemo(thesisId, payload) {
    const res = await api.post(`/vnext/theses/${thesisId}/memo`, payload);
    return res.data;
  },

  async getPolicies() {
    const res = await api.get('/vnext/policies');
    return res.data;
  },

  async upsertPolicies(payload) {
    const res = await api.post('/vnext/policies', payload);
    return res.data;
  },

  async openPaperTrade(thesisId, payload) {
    const res = await api.post(`/vnext/theses/${thesisId}/paper-trades`, payload);
    return res.data;
  },

  async updatePaperTrade(tradeId, payload) {
    const res = await api.patch(`/vnext/paper-trades/${tradeId}`, payload);
    return res.data;
  },
};

export default thesisApi;
