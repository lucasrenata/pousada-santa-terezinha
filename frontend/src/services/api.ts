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
          localStorage.setItem('token', access_token);
          if (originalRequest.headers) {
             originalRequest.headers.Authorization = `Bearer ${access_token}`;
          }
          return api(originalRequest);
        }
      } catch (refreshError: any) {
        // Só redireciona se for erro de autenticação (401/403)
        // Se for erro de rede (servidor reiniciando), NÃO desloga o usuário.
        const isAuthError = refreshError.response?.status === 401 || refreshError.response?.status === 403;
        
        if (isAuthError) {
          console.error("Sessão expirada. Redirecionando para login...");
          const publicRoutes = ['/atendimento', '/registrar', '/book'];
          const isPublicRoute = publicRoutes.some(route => window.location.pathname.includes(route));

          if (!isPublicRoute) {
            localStorage.removeItem('token');
            localStorage.removeItem('role');
            localStorage.removeItem('tenant_id');
            // Só redireciona se não houver um token válido (evita loop de refresh)
            window.location.href = '/login?expired=true';
          }
        }
        
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
