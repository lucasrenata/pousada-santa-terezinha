import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { 
  BedDouble, BarChart3, ShieldCheck, Zap, ArrowRight, CheckCircle2,
  Bot, Calendar, CreditCard, Star, Users, TrendingUp, Lock
} from 'lucide-react';

// ── Paleta de cores ──
const C = {
  primary:    '#2563EB',   // blue-600
  primaryDk:  '#1D4ED8',   // blue-700
  primaryLt:  '#3B82F6',   // blue-500
  accent:     '#EFF6FF',   // blue-50
  accentBdr:  '#BFDBFE',   // blue-200
  bg:         '#F1F5F9',   // slate-100 (cinza claro)
  bgWhite:    '#FFFFFF',
  text:       '#0F172A',   // slate-900
  textMid:    '#475569',   // slate-600
  textLight:  '#94A3B8',   // slate-400
  border:     '#E2E8F0',   // slate-200
  green:      '#10B981',
  amber:      '#F59E0B',
};

export default function Landing() {
  const navigate = useNavigate();
  const [setupFee, setSetupFee] = useState<number | null>(null);

  useEffect(() => {
    api.get('/super/public/pricing')
      .then(res => setSetupFee(res.data.setup_fee))
      .catch(() => setSetupFee(300));
  }, []);

  const formatCurrency = (val: number) =>
    val.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const gradBg = `linear-gradient(135deg, ${C.primary} 0%, ${C.primaryDk} 100%)`;
  const gradShadow = '0 16px 48px rgba(37,99,235,0.35)';

  return (
    <div className="min-h-screen font-sans" style={{ background: C.bg, color: C.text }}>

      {/* ── HEADER ── */}
      <header className="fixed top-0 w-full z-50 backdrop-blur-xl border-b"
        style={{ background: 'rgba(241,245,249,0.88)', borderColor: C.border }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate('/')}>
              <div className="p-1.5 rounded-lg" style={{ background: gradBg }}>
                <Zap size={20} className="text-white fill-white" />
              </div>
              <span className="text-xl font-black tracking-tighter italic" style={{ color: C.text }}>
                PARCER<span style={{ color: C.primary }}>IA</span>
              </span>
            </div>
            <nav className="hidden md:flex items-center gap-8">
              <a href="#funcionalidades" className="text-sm font-medium transition-colors"
                style={{ color: C.textMid }}
                onMouseEnter={e => (e.currentTarget.style.color = C.primary)}
                onMouseLeave={e => (e.currentTarget.style.color = C.textMid)}>
                Funcionalidades
              </a>
              <a href="#precos" className="text-sm font-medium transition-colors"
                style={{ color: C.textMid }}
                onMouseEnter={e => (e.currentTarget.style.color = C.primary)}
                onMouseLeave={e => (e.currentTarget.style.color = C.textMid)}>
                Preços
              </a>
              <button onClick={() => navigate('/login')}
                className="text-sm font-semibold transition-colors"
                style={{ color: C.text }}>
                Entrar
              </button>
              <button onClick={() => navigate('/signup')}
                className="text-sm font-bold px-5 py-2 rounded-full transition-all hover:scale-105 active:scale-95"
                style={{ background: gradBg, color: 'white', boxShadow: '0 8px 24px rgba(37,99,235,0.3)' }}>
                Começar agora
              </button>
            </nav>
            <button onClick={() => navigate('/signup')}
              className="md:hidden text-sm font-bold px-4 py-2 rounded-full"
              style={{ background: gradBg, color: 'white' }}>
              Começar
            </button>
          </div>
        </div>
      </header>

      {/* ── HERO ── */}
      <section className="pt-36 pb-24 px-4 relative overflow-hidden">
        <div className="absolute top-20 left-1/4 w-96 h-96 rounded-full opacity-[0.07] pointer-events-none"
          style={{ background: `radial-gradient(circle, ${C.primary}, transparent)`, filter: 'blur(80px)' }} />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 rounded-full opacity-[0.05] pointer-events-none"
          style={{ background: `radial-gradient(circle, ${C.primaryLt}, transparent)`, filter: 'blur(80px)' }} />

        <div className="max-w-7xl mx-auto">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-flex items-center px-4 py-1.5 rounded-full text-xs font-bold mb-8 border"
              style={{ background: C.accent, color: C.primary, borderColor: C.accentBdr }}>
              <span className="mr-2">✦</span> Inteligência Artificial aplicada à hotelaria
            </div>

            <h1 className="text-5xl md:text-7xl font-black tracking-tight leading-[0.95] mb-6" style={{ color: C.text }}>
              Gerencie sua pousada{' '}
              <span className="italic" style={{
                color: C.primary,
                background: gradBg,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              } as React.CSSProperties}>
                com IA.
              </span>
            </h1>

            <p className="text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed font-medium" style={{ color: C.textMid }}>
              O primeiro sistema de gestão hoteleira com Agentes de IA. Automatize reservas, gerencie finanças e encante seus hóspedes — por uma mensalidade acessível.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <button onClick={() => navigate('/signup')}
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-4 rounded-2xl text-lg font-bold transition-all hover:-translate-y-1 active:scale-95"
                style={{ background: gradBg, color: 'white', boxShadow: gradShadow }}>
                Ativar minha pousada <ArrowRight size={20} />
              </button>
              <button onClick={() => navigate('/login')}
                className="w-full sm:w-auto px-8 py-4 rounded-2xl text-lg font-bold border-2 transition-all hover:bg-white"
                style={{ color: C.text, borderColor: C.border }}>
                Já tenho uma conta
              </button>
            </div>

            {/* Social proof */}
            <div className="mt-12 flex items-center justify-center gap-6 flex-wrap">
              {[
                { icon: <Star size={14} className="fill-current" style={{ color: C.amber }} />, text: '4.9 de satisfação' },
                { icon: <Lock size={14} style={{ color: C.green }} />, text: 'Dados 100% seguros' },
                { icon: <Users size={14} style={{ color: C.primary }} />, text: 'Multiusuário incluso' },
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-2 text-sm font-semibold" style={{ color: C.textMid }}>
                  {item.icon} {item.text}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── FUNCIONALIDADES ── */}
      <section id="funcionalidades" className="py-28 px-4" style={{ background: C.bgWhite }}>
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-black uppercase tracking-widest mb-3" style={{ color: C.primary }}>Funcionalidades</p>
            <h2 className="text-4xl md:text-5xl font-black tracking-tight" style={{ color: C.text }}>
              Tudo para sua pousada{' '}
              <span className="italic" style={{
                color: C.primary,
                background: gradBg,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              } as React.CSSProperties}>
                decolar.
              </span>
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard icon={<BedDouble size={28} style={{ color: C.primary }} />} badge="Essencial"
              title="Gestão de Quartos"
              description="Visão 360° de status, limpeza e manutenção em tempo real. Controle de ocupação com timeline visual." />
            <FeatureCard icon={<Bot size={28} style={{ color: 'white' }} />} badge="IA Exclusivo"
              title="Agente de Reservas IA"
              description="Um agente inteligente que conversa com seus hóspedes, realiza reservas, coleta dados e fecha vendas autonomamente."
              highlight />
            <FeatureCard icon={<BarChart3 size={28} style={{ color: C.green }} />} badge="Financeiro"
              title="Dashboard Financeiro"
              description="Acompanhe receitas, despesas e lucratividade com relatórios automáticos exportáveis em PDF." />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-8">
            <FeatureCard icon={<Calendar size={28} style={{ color: C.amber }} />} badge="Operacional"
              title="Check-in & Check-out"
              description="Fluxo completo de entrada e saída com registro de consumos e checkout financeiro integrado." />
            <FeatureCard icon={<CreditCard size={28} style={{ color: C.primary }} />} badge="Pagamentos"
              title="Mercado Pago Integrado"
              description="Receba via PIX e cartão direto pelo sistema, com confirmação automática e lançamento de receita." />
            <FeatureCard icon={<ShieldCheck size={28} style={{ color: C.green }} />} badge="Segurança"
              title="Multitenant Isolado"
              description="Cada pousada tem seu ambiente 100% isolado com Row Level Security no banco de dados." />
          </div>
        </div>
      </section>

      {/* ── DEPOIMENTOS ── */}
      <section className="py-24 px-4" style={{ background: C.bg }}>
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-xs font-black uppercase tracking-widest mb-3" style={{ color: C.primary }}>Resultados Reais</p>
            <h2 className="text-4xl font-black" style={{ color: C.text }}>O que dizem os gestores</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { name: 'Carlos M.', hotel: 'Pousada Vista Verde', text: 'Reduzi 3 horas de trabalho administrativo por dia. O agente cuida das reservas enquanto durmo.' },
              { name: 'Ana B.', hotel: 'Hotel Serra Alta', text: 'As reservas automáticas via IA aumentaram nossa taxa de ocupação em 40% no primeiro mês.' },
              { name: 'Roberto S.', hotel: 'Pousada do Sol', text: 'Finalmente um sistema que entende o negócio de pousada. O dashboard financeiro é excepcional.' },
            ].map((t, i) => (
              <div key={i} className="p-7 rounded-3xl border" style={{ background: C.bgWhite, borderColor: C.border }}>
                <div className="flex gap-0.5 mb-4">
                  {Array(5).fill(0).map((_, j) => <Star key={j} size={14} className="fill-current" style={{ color: C.amber }} />)}
                </div>
                <p className="text-sm font-medium leading-relaxed mb-6" style={{ color: C.textMid }}>"{t.text}"</p>
                <div>
                  <p className="font-black text-sm" style={{ color: C.text }}>{t.name}</p>
                  <p className="text-xs font-medium" style={{ color: C.textLight }}>{t.hotel}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── PREÇOS ── */}
      <section id="precos" className="py-28 px-4" style={{ background: C.bgWhite }}>
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-black uppercase tracking-widest mb-3" style={{ color: C.primary }}>Investimento</p>
            <h2 className="text-4xl md:text-5xl font-black tracking-tight" style={{ color: C.text }}>
              Simples e transparente.
            </h2>
            <p className="mt-4 text-lg font-medium" style={{ color: C.textMid }}>Um plano único. Para pousadas de todos os tamanhos.</p>
          </div>

          <div className="max-w-lg mx-auto">
            <div className="relative rounded-[40px] p-10 text-white overflow-hidden"
              style={{ background: gradBg, boxShadow: '0 32px 80px rgba(37,99,235,0.4)' }}>
              <div className="absolute top-0 right-0 w-64 h-64 rounded-full opacity-20 pointer-events-none"
                style={{ background: 'radial-gradient(circle, white, transparent)', filter: 'blur(40px)' }} />

              <span className="text-xs font-black uppercase tracking-widest px-3 py-1 rounded-full border border-white/30 bg-white/10">
                ✦ Plano Único Profissional
              </span>

              <div className="mt-8 flex items-baseline gap-2">
                <span className="text-2xl font-bold opacity-80">R$</span>
                <span className="text-7xl font-black italic leading-none">
                  {setupFee !== null ? formatCurrency(setupFee) : '...'}
                </span>
                <span className="text-xl font-semibold opacity-70">/mês</span>
              </div>
              <p className="mt-5 opacity-80 font-medium text-sm leading-relaxed">
                Mensalidade recorrente com todas as funcionalidades inclusas. Cancele quando quiser, sem multa.
              </p>

              <div className="mt-8 space-y-3">
                {[
                  'Ambiente isolado e seguro',
                  'Agente de IA para reservas',
                  'Dashboard financeiro completo',
                  'Integração Mercado Pago',
                  'Usuários ilimitados para sua equipe',
                  'Suporte técnico incluso',
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 bg-white/20">
                      <CheckCircle2 size={12} className="text-white" />
                    </div>
                    <span className="text-sm font-semibold opacity-90">{item}</span>
                  </div>
                ))}
              </div>

              <button onClick={() => navigate('/signup')}
                className="mt-10 w-full py-5 rounded-3xl text-xl font-black transition-all hover:scale-105 active:scale-95"
                style={{ background: 'white', color: C.primary, boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }}>
                Ativar minha pousada agora
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA FINAL ── */}
      <section className="py-24 px-4 text-center" style={{ background: C.bg }}>
        <div className="max-w-3xl mx-auto">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-8"
            style={{ background: gradBg }}>
            <TrendingUp size={28} className="text-white" />
          </div>
          <h2 className="text-4xl md:text-5xl font-black tracking-tight mb-6" style={{ color: C.text }}>
            Pronto para transformar<br />
            <span className="italic" style={{
              color: C.primary,
              background: gradBg,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            } as React.CSSProperties}>
              sua pousada?
            </span>
          </h2>
          <p className="text-lg font-medium mb-10" style={{ color: C.textMid }}>
            Junte-se aos gestores que já automatizaram sua operação com IA.
          </p>
          <button onClick={() => navigate('/signup')}
            className="inline-flex items-center gap-3 px-10 py-5 rounded-2xl text-xl font-black transition-all hover:-translate-y-1 active:scale-95"
            style={{ background: gradBg, color: 'white', boxShadow: gradShadow }}>
            Começar agora <ArrowRight size={22} />
          </button>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="py-12 border-t" style={{ borderColor: C.border, background: C.bgWhite }}>
        <div className="max-w-7xl mx-auto px-4 text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="p-1.5 rounded-lg" style={{ background: gradBg }}>
              <Zap size={18} className="text-white fill-white" />
            </div>
            <span className="text-2xl font-black tracking-tighter italic" style={{ color: C.text }}>
              PARCER<span style={{ color: C.primary }}>IA</span>
            </span>
          </div>
          <p className="text-sm font-medium" style={{ color: C.textLight }}>
            © 2026 ParcerIA Hotelaria Solutions. Todos os direitos reservados.
          </p>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, badge, title, description, highlight = false }: {
  icon: React.ReactNode;
  badge: string;
  title: string;
  description: string;
  highlight?: boolean;
}) {
  const C_primary = '#2563EB';
  const C_bg = '#F1F5F9';
  const C_border = '#E2E8F0';
  const C_text = '#0F172A';
  const C_textMid = '#475569';

  return (
    <div
      className="p-8 rounded-3xl border transition-all duration-300 hover:-translate-y-1 hover:shadow-xl"
      style={{
        background: highlight ? `linear-gradient(135deg, ${C_primary} 0%, #1D4ED8 100%)` : C_bg,
        borderColor: highlight ? 'transparent' : C_border,
        boxShadow: highlight ? '0 16px 48px rgba(37,99,235,0.3)' : undefined,
      }}
    >
      <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-6 shadow-md"
        style={{ background: highlight ? 'rgba(255,255,255,0.2)' : 'white' }}>
        {icon}
      </div>
      <span className="text-[10px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full"
        style={{
          background: highlight ? 'rgba(255,255,255,0.2)' : '#EFF6FF',
          color: highlight ? 'white' : C_primary,
        }}>
        {badge}
      </span>
      <h3 className="text-xl font-black mt-4 mb-3 tracking-tight"
        style={{ color: highlight ? 'white' : C_text }}>
        {title}
      </h3>
      <p className="text-sm font-medium leading-relaxed"
        style={{ color: highlight ? 'rgba(255,255,255,0.8)' : C_textMid }}>
        {description}
      </p>
    </div>
  );
}
