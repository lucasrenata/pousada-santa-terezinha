import { useNavigate } from 'react-router-dom';
import { BedDouble, BarChart3, MessageSquare, ShieldCheck, Zap, ArrowRight, CheckCircle2 } from 'lucide-react';

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 font-sans selection:bg-blue-100">
      {/* Header */}
      <header className="fixed top-0 w-full bg-white/80 backdrop-blur-md border-b border-slate-200 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate('/')}>
              <div className="bg-blue-600 p-1.5 rounded-lg shadow-blue-200 shadow-lg">
                <Zap size={20} className="text-white fill-white" />
              </div>
              <span className="text-xl font-black text-slate-800 tracking-tighter italic">PARCER<span className="text-blue-600">IA</span></span>
            </div>
            <nav className="hidden md:flex items-center gap-8">
              <a href="#funcionalidades" className="text-sm font-medium text-slate-600 hover:text-blue-600 transition">Funcionalidades</a>
              <a href="#precos" className="text-sm font-medium text-slate-600 hover:text-blue-600 transition">Preços</a>
              <button 
                onClick={() => navigate('/login')}
                className="text-sm font-semibold text-slate-800 hover:text-blue-600 transition"
              >
                Entrar
              </button>
              <button 
                onClick={() => navigate('/signup')}
                className="bg-blue-600 text-white px-5 py-2 rounded-full text-sm font-bold shadow-blue-200 shadow-xl hover:bg-blue-700 hover:scale-105 active:scale-95 transition-all"
              >
                Começar agora
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center bg-blue-50 text-blue-600 px-4 py-1.5 rounded-full text-xs font-bold mb-8 animate-fade-in border border-blue-100">
            <span className="mr-2">✨</span> IA Generativa aplicada à hotelaria
          </div>
          <h1 className="text-5xl md:text-7xl font-black text-slate-900 tracking-tight leading-[0.9] mb-6">
            Sua pousada no <br /> 
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">piloto automático.</span>
          </h1>
          <p className="text-lg md:text-xl text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed font-medium">
            O primeiro sistema de gestão hoteleira orquestrado por Agentes de IA. Cadastre, venda e encante seus hóspedes com inteligência pura.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button 
              onClick={() => navigate('/signup')}
              className="w-full sm:w-auto bg-blue-600 text-white px-8 py-4 rounded-2xl text-lg font-bold shadow-blue-200 shadow-2xl hover:bg-blue-700 hover:-translate-y-1 transition-all flex items-center justify-center"
            >
              Criar minha conta grátis <ArrowRight size={20} className="ml-2" />
            </button>
            <button className="w-full sm:w-auto bg-white text-slate-800 border-2 border-slate-200 px-8 py-4 rounded-2xl text-lg font-bold hover:bg-slate-50 transition-all">
              Agendar Demo
            </button>
          </div>
        </div>
      </section>

      {/* Mockup Preview */}
      <section className="px-4 pb-20">
        <div className="max-w-5xl mx-auto rounded-3xl overflow-hidden shadow-2xl border-4 border-white transform hover:rotate-1 transition-transform duration-700">
          <img 
            src="https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&q=80&w=2000" 
            alt="Dashboard Preview" 
            className="w-full h-[400px] object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900/60 to-transparent flex items-end p-8">
            <div className="flex gap-4">
               <div className="bg-white/20 backdrop-blur-md px-4 py-2 rounded-xl text-white text-sm font-bold border border-white/30">
                 Quartos: 100% Ocupados
               </div>
               <div className="bg-green-500/80 backdrop-blur-md px-4 py-2 rounded-xl text-white text-sm font-bold">
                 Revenue: +R$ 45.000,00
               </div>
            </div>
          </div>
        </div>
      </section>

      {/* Funcionalidades */}
      <section id="funcionalidades" className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-black text-slate-900 tracking-tight italic">Tudo o que você precisa <br/><span className="text-blue-600">para decolar.</span></h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard 
              icon={<BedDouble className="text-blue-600" size={32} />}
              title="Gestão de Quartos"
              description="Visão 360º de status, limpeza e manutenção em tempo real. Ordem numérica natural e busca inteligente."
            />
            <FeatureCard 
              icon={<MessageSquare className="text-indigo-600" size={32} />}
              title="Customer Agent AI"
              description="Um agente de reservas que fala com seus hóspedes via WhatsApp, faz o resumo da estadia e fecha reservas sozinho."
            />
            <FeatureCard 
              icon={<BarChart3 className="text-blue-500" size={32} />}
              title="Dashboard Financeiro"
              description="Controle de receitas, despesas e lucratividade com relatórios automáticos exportáveis em PDF."
            />
          </div>
        </div>
      </section>

      {/* Preços */}
      <section id="precos" className="py-20 bg-slate-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-6">
               <h2 className="text-4xl font-black text-slate-900 leading-tight">Um preço justo, <br/> para pousadas de <br/> todos os tamanhos.</h2>
               <div className="space-y-4">
                  <CheckItem text="Sem taxa de instalação" />
                  <CheckItem text="Atendimento via WhatsApp incluso" />
                  <CheckItem text="Usuários ilimitados para staff" />
                  <CheckItem text="Seu próprio tenant isolado" />
               </div>
            </div>
            <div className="bg-blue-600 rounded-[40px] p-10 text-white shadow-blue-300 shadow-2xl transform lg:rotate-2">
               <span className="text-xs font-black uppercase tracking-widest bg-white/20 px-3 py-1 rounded-full">Plano Único Profissional</span>
               <div className="mt-6 flex items-baseline gap-2">
                  <span className="text-6xl font-black italic">R$ 199</span>
                  <span className="text-xl font-medium opacity-80">/mês</span>
               </div>
               <p className="mt-4 text-blue-100 font-medium">O teste é por nossa conta. Comece agora sem cartão de crédito.</p>
               <button 
                  onClick={() => navigate('/signup')}
                  className="mt-8 w-full bg-white text-blue-600 py-5 rounded-3xl text-xl font-black hover:bg-blue-50 transition-all shadow-xl"
               >
                  Começar a usar agora
               </button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-slate-200">
         <div className="max-w-7xl mx-auto px-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-4">
               <Zap size={24} className="text-blue-600 fill-blue-600" />
               <span className="text-2xl font-black text-slate-800 tracking-tighter italic">PARCER<span className="text-blue-600">IA</span></span>
            </div>
            <p className="text-slate-500 text-sm font-medium">© 2026 ParcerIA Hotelaria Solutions. Todos os direitos reservados.</p>
         </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <div className="bg-slate-50 p-8 rounded-3xl border border-slate-100 hover:border-blue-200 hover:bg-white hover:shadow-xl transition-all duration-300 group">
      <div className="bg-white w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg mb-6 group-hover:scale-110 transition-transform">
        {icon}
      </div>
      <h3 className="text-xl font-bold text-slate-800 mb-3 tracking-tight">{title}</h3>
      <p className="text-slate-500 text-sm font-medium leading-relaxed">{description}</p>
    </div>
  );
}

function CheckItem({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="bg-blue-100 p-1 rounded-full text-blue-600">
        <CheckCircle2 size={16} />
      </div>
      <span className="font-semibold text-slate-700">{text}</span>
    </div>
  );
}
