import axios from 'axios';

const baseURL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({ 
  baseURL,
  withCredentials: true // Ativa envio de Cookies HttpOnly (Refresh Token) em todas as chamadas
});

// Interceptor de Requisição: Adiciona o Access Token (curto)
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Interceptor de Resposta: Trata Erros 401 (Expire) renovando automaticamente
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Se o erro for 401 e ainda não tentamos o retry
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Tenta renovar o access_token usando o cookie de refresh
        const response = await axios.post(`${baseURL}/auth/refresh`, {}, { withCredentials: true });
        
        if (response.status === 200 || response.status === 201) {
          const { access_token } = response.data;
          
          // Salva o novo token e tenta a requisição original novamente
          localStorage.setItem('token', access_token);
          if (originalRequest.headers) {
             originalRequest.headers.Authorization = `Bearer ${access_token}`;
          }
          return api(originalRequest);
        }
      } catch (refreshError) {
        console.error("Sessão expirada. Redirecionando para login...");
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('tenant_id');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
