import { Outlet } from 'react-router-dom';

export default function GuestLayout() {
  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 overflow-x-hidden selection:bg-indigo-100 selection:text-indigo-900">
      {/* Background Decor - Gradients Suaves */}
      <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top_right,_var(--tw-gradient-stops))] from-indigo-50 via-white to-slate-50 opacity-70" />
      <div className="fixed top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-600 via-blue-500 to-indigo-600 z-50 shadow-sm" />
      
      <main className="relative flex flex-col min-h-screen">
        <div className="flex-1">
          <Outlet />
        </div>
        
        {/* Simple Footer */}
        <footer className="py-6 text-center text-slate-400 text-xs font-medium bg-white/50 backdrop-blur-sm border-t border-slate-100 mt-auto">
          © {new Date().getFullYear()} — Sistema de Atendimento Inteligente ParcerIA
        </footer>
      </main>
    </div>
  );
}
