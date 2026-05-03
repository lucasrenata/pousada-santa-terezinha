import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const Landing = () => {
  const navigate = useNavigate();
  const [price, setPrice] = useState<number | null>(null);

  useEffect(() => {
    api.get('/super/public/pricing')
      .then(res => setPrice(res.data.setup_fee))
      .catch(() => setPrice(450.00)); // Fallback caso a API falhe
  }, []);

  const formatCurrency = (val: number) =>
    val.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 antialiased">
      {/* Navbar */}
      <nav className="fixed w-full z-50 bg-white/95 backdrop-blur-md shadow-xl border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4 md:py-3">
            <div className="flex items-center space-x-2 cursor-pointer" onClick={() => navigate('/')}>
              <div className="w-10 h-10 bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                <span className="text-white font-bold text-lg">P</span>
              </div>
              <span className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">ParcerIA</span>
            </div>
            <div className="hidden md:flex items-center space-x-6">
              <a href="#features" className="text-gray-700 hover:text-indigo-600 font-medium transition-colors duration-200">Funcionalidades</a>
              <a href="#pricing" className="text-gray-700 hover:text-indigo-600 font-medium transition-colors duration-200">Preços</a>
              <button
                onClick={() => navigate('/login')}
                className="text-gray-700 hover:text-indigo-600 font-bold transition-colors duration-200"
              >
                Entrar
              </button>
              <button
                onClick={() => navigate('/signup')}
                className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-2.5 rounded-2xl font-bold hover:from-indigo-700 hover:to-purple-700 shadow-lg hover:shadow-xl transition-all duration-200"
              >
                Começar Agora
              </button>
            </div>
            <button
              onClick={() => navigate('/signup')}
              className="md:hidden bg-indigo-600 text-white px-4 py-2 rounded-xl text-sm font-bold"
            >
              Começar
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-40 pb-24 px-4 sm:px-6 lg:px-8 overflow-hidden">
        <div className="max-w-7xl mx-auto text-center">
          <h1 className="text-5xl md:text-7xl lg:text-8xl font-black bg-gradient-to-r from-gray-900 via-indigo-900 to-purple-900 bg-clip-text text-transparent mb-8 leading-tight">
            Gestão Hoteleira
            <br />
            <span className="text-indigo-600 italic">Redefinida.</span>
          </h1>
          <p className="text-xl md:text-2xl text-gray-600 mb-12 max-w-4xl mx-auto leading-relaxed">
            Dê um cérebro à sua pousada: Integre uma Recepcionista Cognitiva de Próxima Geração com a identidade da sua marca.
          </p>
          <div className="flex flex-col sm:flex-row gap-6 justify-center items-center">
            <button
              onClick={() => navigate('/signup')}
              className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-12 py-6 rounded-3xl text-xl font-bold shadow-2xl hover:shadow-3xl hover:from-indigo-700 hover:to-purple-700 transform hover:-translate-y-1 transition-all duration-300"
            >
              Ativar Minha Pousada Agora
            </button>
            <a href="#features" className="text-indigo-600 px-8 py-4 font-bold text-lg hover:underline transition-all">
              Ver funcionalidades →
            </a>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-32 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-20">
            <h2 className="text-5xl md:text-6xl font-black text-gray-900 mb-6">
              Orquestração Inteligente
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Tudo o que sua pousada precisa para escalar sem aumentar a equipe.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-12">
            {[
              { emoji: '🧠', title: 'Agente de Reservas', desc: 'Sua IA conversa, faz cotações e fecha reservas sozinha pelo WhatsApp e Web.' },
              { emoji: '📊', title: 'Dashboard Premium', desc: 'Controle total de ocupação, financeiro e inventário em uma tela intuitiva.' },
              { emoji: '💳', title: 'Pagamento Nativo', desc: 'Integração com PIX e Mercado Pago para confirmação instantânea de sinal.' }
            ].map((f, i) => (
              <div key={i} className="p-8 rounded-3xl bg-gray-50 border border-gray-100 hover:shadow-xl transition-all duration-300">
                <div className="text-4xl mb-6">{f.emoji}</div>
                <h3 className="text-2xl font-bold text-gray-900 mb-4">{f.title}</h3>
                <p className="text-gray-600 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-32 px-4 sm:px-6 lg:px-8 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-5xl font-black text-gray-900 mb-4">Assinatura Mensal</h2>
            <p className="text-xl text-gray-600">Um único plano profissional com tudo incluso.</p>
          </div>

          <div className="max-w-lg mx-auto">
            <div className="relative rounded-[40px] p-12 text-white overflow-hidden shadow-2xl"
              style={{ background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)' }}>

              <div className="absolute top-0 right-0 w-64 h-64 rounded-full bg-white/10 blur-3xl -mr-20 -mt-20"></div>

              <span className="inline-block px-4 py-1.5 rounded-full bg-white/20 border border-white/30 text-xs font-black uppercase tracking-widest mb-8">
                ✦ Plano Profissional Completo
              </span>

              <div className="flex items-baseline gap-2 mb-6">
                <span className="text-2xl font-bold opacity-80">R$</span>
                <span className="text-8xl font-black italic tracking-tighter">
                  {price !== null ? formatCurrency(price) : '...'}
                </span>
                <span className="text-xl font-bold opacity-70">/mês</span>
              </div>

              <p className="text-lg opacity-90 mb-10 leading-relaxed">
                Acesso ilimitado a todas as ferramentas, incluindo a IA Ana, Gestão Financeira, PDV e suporte prioritário.
              </p>

              <div className="space-y-4 mb-12">
                {[
                  'Agente de IA para WhatsApp/Web',
                  'Gestão Multi-Quartos',
                  'Checkout e PDV Integrado',
                  'Dashboard Financeiro em tempo real',
                  'Backup diário e Segurança RLS'
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center">
                      <span className="text-[10px]">✓</span>
                    </div>
                    <span className="font-semibold">{item}</span>
                  </div>
                ))}
              </div>

              <button
                onClick={() => navigate('/signup')}
                className="w-full py-6 rounded-2xl bg-white text-indigo-600 text-xl font-black shadow-xl hover:scale-105 active:scale-95 transition-all"
              >
                Ativar Minha Pousada
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-20 bg-white border-t border-gray-100">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <div className="flex justify-center items-center gap-2 mb-6">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold">P</span>
            </div>
            <span className="text-2xl font-black tracking-tighter italic text-gray-900">
              PARCER<span className="text-indigo-600">IA</span>
            </span>
          </div>
          <p className="text-gray-500 font-medium">
            © 2026 ParcerIA. Transformando a hotelaria com inteligência.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
