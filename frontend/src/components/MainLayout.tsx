import { useState, useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

import { LayoutDashboard, BedDouble, CalendarDays, CalendarHeart, Package, DollarSign, LogOut, Menu, Settings, Users, Wrench, MessageSquare, ShieldCheck, ShoppingCart } from 'lucide-react';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';

export default function MainLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const role = localStorage.getItem('role');
  const menuItems = [
    { label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard', roles: ['admin', 'recepcionista', 'servico'] },
    { label: 'PDV', icon: ShoppingCart, path: '/pdv', roles: ['admin', 'recepcionista'] },
    { label: 'Quartos', icon: BedDouble, path: '/rooms', roles: ['admin', 'recepcionista', 'servico'] },
    { label: 'Reservas', icon: CalendarDays, path: '/bookings', roles: ['admin', 'recepcionista'] },
    { label: 'Estoque', icon: Package, path: '/inventory', roles: ['admin', 'recepcionista'] },
    { label: 'Financeiro', icon: DollarSign, path: '/finance', roles: ['admin'] },
    { label: 'Eventos', icon: CalendarHeart, path: '/events', roles: ['admin', 'recepcionista'] },
    { label: 'Usuários', icon: Users, path: '/admin/users', roles: ['admin'] },
    { label: 'Configurações', icon: Settings, path: '/settings', roles: ['admin'] },
    { label: 'Serviços', icon: Wrench, path: '/service', roles: ['admin', 'recepcionista', 'servico'] },
    { label: 'Console SaaS', icon: ShieldCheck, path: '/super/dashboard', roles: ['superadmin'] },
  ];

  const filteredMenu = menuItems.filter(item => item.roles.includes(role || 'recepcionista'));

  // Bloqueio de rota no layout (se o cara tentar entrar em rota proibida via URL)
  useEffect(() => {
    const isServiceStaff = role === 'servico' || role === 'manutencao' || role === 'faxina' || role === 'camareira';
    const isRecepcionista = role === 'recepcionista';
    
    // Rotas bloqueadas para recepcionista e serviço
    const forbiddenForRecepcionista = ['/finance', '/admin', '/settings'];
    const permittedForService = ['/service', '/rooms', '/dashboard'];

    if (role && isServiceStaff && !permittedForService.includes(location.pathname)) {
      navigate('/service', { replace: true });
    } else if (role && isRecepcionista && forbiddenForRecepcionista.some(path => location.pathname.startsWith(path))) {
      navigate('/dashboard', { replace: true });
    }
  }, [role, location.pathname, navigate]);


  function handleLogout() {
    localStorage.removeItem('token');
    navigate('/');
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* HEADER SUPERIOR (BARRA NO TOPO) */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          
          {/* LOGO E NOME / MENU HAMBURGUER (MOBILE) */}
          <div className="flex items-center gap-3">
            {/* Menu Hamburguer (Aparece só no Mobile) */}
            <div className="md:hidden">
              <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
                <SheetTrigger asChild>
                  <button className="bg-blue-600 text-white p-2 rounded-lg hover:bg-blue-700 transition">
                    <Menu size={24} />
                  </button>
                </SheetTrigger>
                <SheetContent side="left" className="w-[300px] sm:w-[400px] p-0 flex flex-col">
                  <div className="p-6 border-b border-slate-100 flex items-center gap-3 bg-slate-50">
                    <div className="bg-blue-600 text-white p-2 rounded-lg">
                      <Menu size={20} />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-slate-900 tracking-tight leading-none">ParcerIA</h2>
                      <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mt-1">Hotelaria</p>
                    </div>
                  </div>
                  
                  <nav className="flex-1 overflow-y-auto p-4 space-y-1">
                    {filteredMenu.map((item) => {
                      const isActive = location.pathname === item.path;
                      const Icon = item.icon;
                      
                      return (
                        <button
                          key={item.path}
                          onClick={() => {
                            navigate(item.path);
                            setIsMobileMenuOpen(false); // Fecha o menu ao clicar
                          }}
                          className={`w-full flex items-center px-4 py-3.5 rounded-xl text-sm font-bold transition-all duration-200
                            ${isActive 
                              ? 'bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-200' 
                              : item.path === '/pdv' 
                                ? 'bg-yellow-50 text-yellow-700 border border-yellow-200'
                                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                            }`}
                        >
                          <Icon size={20} className={`mr-3 ${isActive ? 'text-blue-600' : item.path === '/pdv' ? 'text-yellow-600' : 'text-slate-400'}`} />
                          {item.label}
                        </button>
                      );
                    })}
                  </nav>

                  <div className="p-4 border-t border-slate-100">
                    <button 
                      onClick={handleLogout}
                      className="w-full flex items-center justify-center text-red-600 hover:bg-red-50 transition-colors text-sm font-bold px-4 py-3 rounded-xl border border-red-100"
                    >
                      <LogOut size={20} className="mr-2" />
                      Sair do Sistema
                    </button>
                  </div>
                </SheetContent>
              </Sheet>
            </div>

            {/* LOGO Desktop */}
            <div className="hidden md:flex bg-blue-600 text-white p-1.5 rounded-lg">
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
              
              // Especial: Se for o PDV, renderiza com estilo de destaque amarelo
              if (item.path === '/pdv') {
                return (
                  <button 
                    key={item.path}
                    onClick={() => navigate('/pdv')}
                    className="flex items-center bg-[#EAB308] text-[#1E293B] px-6 py-2 ml-2 rounded-xl text-sm font-black transition-all hover:scale-105 active:scale-95 shadow-lg shadow-yellow-200"
                  >
                    <Icon size={18} className="mr-2" />
                    PDV
                  </button>
                );
              }

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

          {/* BOTÕES DE AÇÃO (DIREITA) */}
          <div className="flex items-center gap-3">
            {/* BOTÃO SAIR */}
            <button 
              onClick={handleLogout}
              className="flex items-center text-slate-500 hover:text-red-600 transition-colors text-sm font-medium px-3 py-2 rounded-lg hover:bg-red-50"
            >
              <LogOut size={18} className="mr-2" />
              <span className="hidden sm:inline">Sair</span>
            </button>
          </div>
        </div>
      </header>

      {/* CONTEÚDO DA PÁGINA (AQUI VAI O DASHBOARD, ETC) */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 md:py-8">
        <Outlet /> 
      </main>
    </div>
  );
}
