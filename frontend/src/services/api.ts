import axios from 'axios';
const baseURL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8003';
const api = axios.create({ baseURL });

// Interceptor: Adiciona o Token em toda requisição automaticamente
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
