import { useMemo, useState } from 'react';
import {
  BedDouble, Users, Percent, CalendarDays,
  TrendingUp, DollarSign, ArrowUpRight, RotateCw
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useRealTimeRooms } from '../hooks/useRealTimeRooms';
import { useReservations } from '../hooks/useReservations';
import { useDailySnapshot } from '../hooks/useDailySnapshot';

// ─── Barra de distribuição de quartos ───────────────────────────────────────
interface StatusCounts {
  disponivel: number;
  ocupado: number;
  limpeza: number;
  manutencao: number;
  total: number;
}
function MiniStatusBar({ counts }: { counts: StatusCounts }) {
  const total = counts.total || 1;
  const w = (n: number) => `${Math.round((n / total) * 100)}%`;
  return (
    <div>
      <div className="h-3 rounded-full bg-slate-100 overflow-hidden flex">
        <div style={{ width: w(counts.disponivel) }} className="bg-green-500 transition-all duration-700" />
        <div style={{ width: w(counts.ocupado) }} className="bg-red-500 transition-all duration-700" />
        <div style={{ width: w(counts.limpeza) }} className="bg-yellow-500 transition-all duration-700" />
        <div style={{ width: w(counts.manutencao) }} className="bg-slate-500 transition-all duration-700" />
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-600">
        <span className="inline-flex items-center gap-1.5"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-green-500" /> Disponíveis: <strong>{counts.disponivel}</strong></span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-red-500" /> Ocupados: <strong>{counts.ocupado}</strong></span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-yellow-500" /> Limpeza: <strong>{counts.limpeza}</strong></span>
        <span className="inline-flex items-center gap-1.5"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-slate-500" /> Manutenção: <strong>{counts.manutencao}</strong></span>
      </div>
    </div>
  );
}

// ─── Próximas movimentações ──────────────────────────────────────────────────
function NextMovements({ bookings }: { bookings: any[] }) {
  const now = new Date();
  const isToday = (d: Date) =>
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();

  // Exibe o horário configurado ou "horário padrão"
  const fmtTime = (time?: string) => time ?? '--:--';

  const upcomingCheckins = bookings
    .filter(b => {
      const d = new Date(b.check_in_date + 'T12:00:00'); // evita problema de timezone
      return isToday(d) && b.status?.toUpperCase() === 'CONFIRMADO';
    })
    .slice(0, 5);

  const upcomingCheckouts = bookings
    .filter(b => {
      const d = new Date(b.check_out_date + 'T12:00:00');
      return isToday(d) && b.status?.toUpperCase() === 'ATIVO';
    })
    .slice(0, 5);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Check-ins */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4">
        <p className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
          Próximos Check-ins Hoje
        </p>
        {upcomingCheckins.length === 0 ? (
          <p className="text-xs text-slate-400 italic">Sem check-ins pendentes para hoje</p>
        ) : (
          <ul className="space-y-2">
            {upcomingCheckins.map((b) => (
              <li key={`ci-${b.id}`} className="flex items-center justify-between text-sm">
                <span className="text-slate-700 font-medium truncate max-w-[120px]">{b.guest_name}</span>
                <span className="text-slate-400 text-xs">{b.room_number ? `Qto ${b.room_number}` : '—'}</span>
                <span className="text-blue-600 font-semibold text-xs">{fmtTime(b.check_in_time)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {/* Check-outs */}
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4">
        <p className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
          Próximos Check-outs Hoje
        </p>
        {upcomingCheckouts.length === 0 ? (
          <p className="text-xs text-slate-400 italic">Sem check-outs pendentes para hoje</p>
        ) : (
          <ul className="space-y-2">
            {upcomingCheckouts.map((b) => (
              <li key={`co-${b.id}`} className="flex items-center justify-between text-sm">
                <span className="text-slate-700 font-medium truncate max-w-[120px]">{b.guest_name}</span>
                <span className="text-slate-400 text-xs">{b.room_number ? `Qto ${b.room_number}` : '—'}</span>
                <span className="text-red-500 font-semibold text-xs">{fmtTime(b.check_out_time)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ─── Formatador de moeda ─────────────────────────────────────────────────────
const fmtCurrency = (v: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(v);

// ─── Card genérico ───────────────────────────────────────────────────────────
function MetricCard({ icon, color, label, value, sub }: {
  icon: React.ReactNode; color: string; label: string; value: React.ReactNode; sub?: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`${color} p-3 rounded-2xl`}>{icon}</div>
          <p className="text-sm font-semibold text-slate-600">{label}</p>
        </div>
        <span className="text-2xl font-black text-slate-800">{value}</span>
      </div>
      {sub && <div className="text-xs text-slate-500 font-medium">{sub}</div>}
    </div>
  );
}

// ─── Dashboard principal ─────────────────────────────────────────────────────
export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<'overview' | 'map'>('overview');
  const { rooms, loading: roomsLoading } = useRealTimeRooms();
  const { reservations, loading: resLoading } = useReservations();
  const { snapshot, loading: snapLoading, error: snapError, refetch: refetchSnap } = useDailySnapshot();
  const navigate = useNavigate();

  const metrics = useMemo(() => {
    const totalRooms = rooms.length || 1;
    const occupied = rooms.filter(r => r.status?.toUpperCase() === 'OCUPADO').length;
    const available = rooms.filter(r => r.status?.toUpperCase() === 'DISPONIVEL').length;
    const cleaning = rooms.filter(r => r.status?.toUpperCase() === 'LIMPEZA').length;
    const maintenance = rooms.filter(r => r.status?.toUpperCase() === 'MANUTENCAO').length;
    const occupancyRate = Math.round((occupied / totalRooms) * 100);

    return { totalRooms, occupied, available, cleaning, maintenance, occupancyRate };
  }, [rooms]);

  const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'DISPONIVEL': return 'border-green-500';
      case 'OCUPADO': return 'border-red-500';
      case 'LIMPEZA': return 'border-yellow-500';
      case 'MANUTENCAO': return 'border-slate-500';
      default: return 'border-gray-300';
    }
  };

  if (roomsLoading || resLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-slate-500 text-sm">Carregando painel...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto">

      {/* Cabeçalho */}
      <div className="flex flex-col sm:flex-row gap-2 mb-8 justify-between items-start sm:items-center">
        <div>
          <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Painel Executivo</h2>
          <p className="text-slate-500 text-sm mt-1">
            Status em tempo real · atualizado automaticamente
            <span className="ml-2 inline-block w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          </p>
        </div>
        <button
          onClick={refetchSnap}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 transition-colors px-3 py-1.5 rounded-lg border border-slate-200 hover:border-slate-400"
        >
          <RotateCw size={12} /> Atualizar dados
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 mb-8">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === 'overview'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
        >
          Visão Geral
        </button>
        <button
          onClick={() => setActiveTab('map')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === 'map'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
        >
          Mapa de Quartos
        </button>
      </div>

      {activeTab === 'overview' && (
        <>
          {/* ── Faixa 0: KPI Mestre (Saldo do Mês) ── */}
          <div className="mb-6">
            <div className={`bg-white rounded-[32px] border border-slate-200 p-1 shadow-sm overflow-hidden flex flex-col md:flex-row items-center justify-between group hover:shadow-md transition-all`}>
               <div className="flex items-center gap-6 p-6">
                  <div className={`p-4 rounded-3xl ${snapshot.monthly_net >= 0 ? 'bg-blue-100 text-blue-600' : 'bg-red-100 text-red-600'}`}>
                    <TrendingUp size={32} />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-[2px] mb-1">Resultado Financeiro Acumulado (Mês)</p>
                    <h1 className={`text-4xl font-black tracking-tighter ${snapshot.monthly_net >= 0 ? 'text-blue-600' : 'text-red-600'}`}>
                      {snapLoading ? '---' : fmtCurrency(snapshot.monthly_net)}
                    </h1>
                  </div>
               </div>
               <div className="hidden lg:flex items-center gap-2 pr-12">
                  <div className="text-right">
                    <p className="text-[10px] font-bold text-slate-400 uppercase">Status do Fluxo</p>
                    <p className={`text-xs font-black uppercase ${snapshot.monthly_net >= 0 ? 'text-blue-500' : 'text-red-500'}`}>
                      {snapshot.monthly_net >= 0 ? 'Superávit Operacional' : 'Déficit no Período'}
                    </p>
                  </div>
                  <div className={`w-1 h-8 rounded-full ${snapshot.monthly_net >= 0 ? 'bg-blue-500' : 'bg-red-500'}`} />
               </div>
            </div>
          </div>

          {/* ── Faixa 1: KPIs Operacionais (quartos + hóspedes) ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">

            {/* Ocupação */}
            <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="bg-blue-100 text-blue-700 p-3 rounded-2xl"><Percent size={20} /></div>
                  <p className="text-sm font-semibold text-slate-600">Ocupação</p>
                </div>
                <span className="text-2xl font-black text-slate-800">{metrics.occupancyRate}%</span>
              </div>
              <div className="h-2.5 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-1000 ${metrics.occupancyRate < 50 ? 'bg-green-500' : metrics.occupancyRate < 80 ? 'bg-yellow-500' : 'bg-red-600'
                    }`}
                  style={{ width: `${metrics.occupancyRate}%` }}
                />
              </div>
              <p className="mt-3 text-xs text-slate-500 font-medium">{metrics.occupied} de {metrics.totalRooms} unidades</p>
            </div>

            {/* Hóspedes Ativos */}
            <MetricCard
              icon={<Users size={20} />}
              color="bg-indigo-100 text-indigo-700"
              label="Hóspedes Ativos"
              value={snapshot.guests_on_site}
              sub={`Acomodados em ${metrics.occupied} quarto${metrics.occupied !== 1 ? 's' : ''}`}
            />

            {/* Disponibilidade */}
            <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="bg-green-100 text-green-700 p-3 rounded-2xl"><BedDouble size={20} /></div>
                  <p className="text-sm font-semibold text-slate-600">Disponíveis</p>
                </div>
                <span className="text-2xl font-black text-slate-800">{metrics.available}</span>
              </div>
              <div className="flex gap-2">
                <span className="bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded-lg text-[10px] font-bold">LIMPEZA: {metrics.cleaning}</span>
                <span className="bg-slate-50 text-slate-600 px-2 py-0.5 rounded-lg text-[10px] font-bold">MANUT: {metrics.maintenance}</span>
              </div>
            </div>

            {/* Turno de Hoje */}
            <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6 hover:shadow-md transition-shadow">
              <div className="flex items-center gap-3 mb-4">
                <div className="bg-orange-100 text-orange-700 p-3 rounded-2xl"><CalendarDays size={20} /></div>
                <p className="text-sm font-semibold text-slate-600">Turno de Hoje</p>
              </div>
              <div className="flex items-center justify-between gap-2">
                <div className="bg-green-50 text-green-700 px-3 py-2 rounded-xl flex-1 text-center">
                  <p className="text-[10px] font-bold uppercase opacity-70">Check-in</p>
                  <p className="text-lg font-black">{snapshot.checkins_today}</p>
                </div>
                <div className="bg-red-50 text-red-700 px-3 py-2 rounded-xl flex-1 text-center">
                  <p className="text-[10px] font-bold uppercase opacity-70">Check-out</p>
                  <p className="text-lg font-black">{snapshot.checkouts_today}</p>
                </div>
              </div>
            </div>
          </div>

          {/* ── Faixa 2: KPIs Financeiros Detalhados ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">

            {/* Receita Hoje */}
            <div className={`bg-gradient-to-br from-emerald-600 to-teal-700 rounded-3xl shadow-md p-6 text-white relative overflow-hidden ${snapLoading ? 'opacity-70' : ''}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <DollarSign size={16} className="text-white/80" />
                  <p className="text-xs font-bold uppercase tracking-wider text-white/70">Receita Hoje</p>
                </div>
                <ArrowUpRight size={20} className="text-white/40" />
              </div>
              <p className="text-3xl font-black">{snapLoading ? '—' : fmtCurrency(snapshot.revenue_today)}</p>
              <div className="mt-4 flex items-center gap-2">
                <span className="text-[10px] bg-white/20 px-2 py-0.5 rounded-full font-bold">BRUTO</span>
              </div>
            </div>

            {/* Despesas Hoje */}
            <div className={`bg-gradient-to-br from-red-500 to-rose-700 rounded-3xl shadow-md p-6 text-white relative overflow-hidden ${snapLoading ? 'opacity-70' : ''}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <TrendingUp size={16} className="text-white/80 rotate-180" />
                  <p className="text-xs font-bold uppercase tracking-wider text-white/70">Despesas Hoje</p>
                </div>
                <div className="w-2 h-2 rounded-full bg-white/40" />
              </div>
              <p className="text-3xl font-black">{snapLoading ? '—' : fmtCurrency(snapshot.expense_today)}</p>
              <div className="mt-4">
                {snapshot.overdue_expenses > 0 && (
                  <span className="text-[10px] bg-white/20 text-white px-2 py-0.5 rounded-full font-bold">
                    {snapshot.overdue_expenses} VENCIDAS
                  </span>
                )}
              </div>
            </div>

            {/* Saldo Líquido Dia */}
            <div className={`rounded-3xl shadow-md p-6 text-white relative overflow-hidden transition-all ${snapLoading ? 'opacity-70' : ''} ${snapshot.net_today >= 0 ? 'bg-gradient-to-br from-blue-500 to-indigo-700' : 'bg-gradient-to-br from-orange-600 to-red-700'}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <RotateCw size={16} className="text-white/80" />
                  <p className="text-xs font-bold uppercase tracking-wider text-white/70">Saldo do Dia</p>
                </div>
                <TrendingUp size={16} className="text-white/40" />
              </div>
              <p className="text-3xl font-black">
                {snapLoading ? '—' : fmtCurrency(snapshot.net_today)}
              </p>
              <p className="text-[10px] text-white/60 mt-4 font-medium italic">Receita − Despesas pagas</p>
            </div>

            {/* Ticket Médio */}
            <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6 hover:shadow-md transition-shadow">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Ticket Médio</p>
              <p className="text-3xl font-black text-indigo-600">{snapLoading ? '—' : fmtCurrency(snapshot.avg_ticket)}</p>
              <p className="text-[10px] text-slate-400 mt-4 font-medium">Reservas Ativas</p>
            </div>

          </div>

          {/* ── Faixa 3: Distribuição + Movimentações ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6">
              <p className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                <span className="w-1.5 h-4 bg-blue-600 rounded-full inline-block" />
                Distribuição dos Quartos
              </p>
              <MiniStatusBar counts={{
                disponivel: rooms.filter(r => r.status?.toUpperCase() === 'DISPONIVEL').length,
                ocupado: rooms.filter(r => r.status?.toUpperCase() === 'OCUPADO').length,
                limpeza: rooms.filter(r => r.status?.toUpperCase() === 'LIMPEZA').length,
                manutencao: rooms.filter(r => r.status?.toUpperCase() === 'MANUTENCAO').length,
                total: rooms.length
              }} />
            </div>
            <NextMovements bookings={reservations} />
          </div>
        </>
      )}

      {activeTab === 'map' && (
        <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6 min-h-[400px]">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-bold text-slate-800">Mapa de Quartos Ocupados</h3>
          </div>
          {metrics.occupied === 0 ? (
            <div className="text-center py-16 bg-slate-50 rounded-3xl border-2 border-dashed border-slate-200">
              <p className="text-slate-400 font-medium italic">Todos os quartos estão livres no momento.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
              {rooms.filter(r => r.status?.toUpperCase() === 'OCUPADO').map((room) => (
                <div
                  key={room.id}
                  onClick={() => navigate(`/rooms?roomId=${room.id}`)}
                  className={`p-4 rounded-2xl border-l-[6px] shadow-sm cursor-pointer hover:scale-105 transition-all duration-300 bg-white ${getStatusColor(room.status)} group`}
                >
                  <div className="flex justify-between items-start mb-3">
                    {/* FIX: exibe room.number (número real) e não room.id (id do banco) */}
                    <span className="text-xl font-black text-slate-800 group-hover:text-blue-600">
                      {room.number ?? `#${room.id}`}
                    </span>
                    <BedDouble size={18} className="text-slate-300" />
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs font-bold uppercase tracking-tighter text-slate-400">{room.type}</p>
                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                      <span className="text-[10px] font-black text-red-600 uppercase">Em Uso</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
