import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, BedDouble, CalendarDays, Package, DollarSign, LogOut, Menu, Settings, Users, Wrench } from 'lucide-react';

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const role = localStorage.getItem('role');
  const menuItems = [
    { label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard', roles: ['admin', 'recepcionista'] },
    { label: 'Quartos', icon: BedDouble, path: '/rooms', roles: ['admin', 'recepcionista'] },
    { label: 'Reservas', icon: CalendarDays, path: '/bookings', roles: ['admin', 'recepcionista'] },
    { label: 'Estoque', icon: Package, path: '/inventory', roles: ['admin', 'recepcionista'] },
    { label: 'Receitas', icon: DollarSign, path: '/finance', roles: ['admin', 'recepcionista'] },
    { label: 'Usuários', icon: Users, path: '/admin/users', roles: ['admin'] },
    { label: 'Configurações', icon: Settings, path: '/settings', roles: ['admin'] },
    { label: 'Serviços', icon: Wrench, path: '/service', roles: ['admin', 'recepcionista', 'manutencao', 'faxina', 'camareira'] },
  ];

  const filteredMenu = menuItems.filter(item => item.roles.includes(role || 'recepcionista'));

  // Bloqueio de rota no layout (se o cara tentar entrar em rota proibida via URL)
  if (role && role !== 'admin' && role !== 'recepcionista' && location.pathname !== '/service') {
    navigate('/service');
  }

  function handleLogout() {
    localStorage.removeItem('token');
    navigate('/');
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* HEADER SUPERIOR (BARRA NO TOPO) */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          
          {/* LOGO E NOME */}
          <div className="flex items-center gap-2">
            <div className="bg-blue-600 text-white p-1.5 rounded-lg">
              <Menu size={24} />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">ParcerIA</h1>
              <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">Hotelaria</p>
            </div>
          </div>

          {/* MENU DE NAVEGAÇÃO (Desktop) */}
          <nav className="hidden md:flex items-center space-x-1">
            {filteredMenu.map((item) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;
              return (
                <button
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
                    ${isActive 
                      ? 'bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-200' 
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                    }`}
                >
                  <Icon size={18} className={`mr-2 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* BOTÃO SAIR */}
          <button 
            onClick={handleLogout}
            className="flex items-center text-slate-500 hover:text-red-600 transition-colors text-sm font-medium px-3 py-2 rounded-lg hover:bg-red-50"
          >
            <LogOut size={18} className="mr-2" />
            <span className="hidden sm:inline">Sair</span>
          </button>
        </div>
      </header>

      {/* CONTEÚDO DA PÁGINA (AQUI VAI O DASHBOARD, ETC) */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet /> 
      </main>
    </div>
  );
}
