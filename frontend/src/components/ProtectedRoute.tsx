import { Navigate, Outlet } from 'react-router-dom';

/**
 * Componente de Proteção de Rotas.
 * Verifica se o usuário possui um token de autenticação válido.
 * Se não tiver, redireciona para a Landing Page (/) para garantir segurança e UX.
 */
const ProtectedRoute = () => {
  const token = localStorage.getItem('token');

  if (!token) {
    // Redireciona para a Landing Page se não estiver logado
    return <Navigate to="/" replace />;
  }

  // Se estiver logado, renderiza as rotas filhas
  return <Outlet />;
};

export default ProtectedRoute;
