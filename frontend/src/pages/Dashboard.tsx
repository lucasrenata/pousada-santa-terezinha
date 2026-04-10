import { useMemo, useState } from 'react';
import { BedDouble, Search, Plus, Users, Percent, CalendarDays } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useRealTimeRooms } from '../hooks/useRealTimeRooms';
import { useReservations } from '../hooks/useReservations';
import RoomModal from '../components/RoomModal';

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
        <div style={{ width: w(counts.disponivel) }} className="bg-green-500" />
        <div style={{ width: w(counts.ocupado) }} className="bg-red-500" />
        <div style={{ width: w(counts.limpeza) }} className="bg-yellow-500" />
        <div style={{ width: w(counts.manutencao) }} className="bg-slate-500" />
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
        <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-green-500" /> Disponíveis: {counts.disponivel}</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-red-500" /> Ocupados: {counts.ocupado}</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-yellow-500" /> Limpeza: {counts.limpeza}</span>
        <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-slate-500" /> Manutenção: {counts.manutencao}</span>
      </div>
    </div>
  );
}

function NextMovements({ bookings }: { bookings: any[] }) {
  const now = new Date();
  const isToday = (d: Date) =>
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
    
  const fmt = (s: string) => new Date(s).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  
  const upcomingCheckins = bookings
    .filter(b => {
      const d = new Date(b.check_in_date);
      return isToday(d) && b.status?.toUpperCase() === 'CONFIRMADO';
    })
    .sort((a, b) => new Date(a.check_in_date).getTime() - new Date(b.check_in_date).getTime())
    .slice(0, 6);
    
  const upcomingCheckouts = bookings
    .filter(b => {
      const d = new Date(b.check_out_date);
      return isToday(d) && b.status?.toUpperCase() === 'ATIVO';
    })
    .sort((a, b) => new Date(a.check_out_date).getTime() - new Date(b.check_out_date).getTime())
    .slice(0, 6);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4">
        <p className="text-sm font-semibold text-slate-700 mb-2">Próximos Check-ins Hoje</p>
        {upcomingCheckins.length === 0 ? (
          <p className="text-xs text-slate-500">Sem check-ins pendentes para hoje</p>
        ) : (
          <ul className="space-y-2">
            {upcomingCheckins.map((b) => (
              <li key={`ci-${b.id}`} className="flex items-center justify-between text-sm">
                <span className="text-slate-700 font-medium">{b.guest_name}</span>
                <span className="text-slate-500 text-xs">{b.room_number ? `Quarto ${b.room_number}` : '—'}</span>
                <span className="text-blue-600 font-semibold">{fmt(b.check_in_date)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4">
        <p className="text-sm font-semibold text-slate-700 mb-2">Próximos Check-outs Hoje</p>
        {upcomingCheckouts.length === 0 ? (
          <p className="text-xs text-slate-500">Sem check-outs pendentes para hoje</p>
        ) : (
          <ul className="space-y-2">
            {upcomingCheckouts.map((b) => (
              <li key={`co-${b.id}`} className="flex items-center justify-between text-sm">
                <span className="text-slate-700 font-medium">{b.guest_name}</span>
                <span className="text-slate-500 text-xs">{b.room_number ? `Quarto ${b.room_number}` : '—'}</span>
                <span className="text-red-600 font-semibold">{fmt(b.check_out_date)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { rooms, loading: roomsLoading, refetch: refetchRooms } = useRealTimeRooms();
  const { reservations, loading: resLoading } = useReservations();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const navigate = useNavigate();

  const metrics = useMemo(() => {
    const totalRooms = rooms.length || 1;
    const occupied = rooms.filter(r => r.status?.toUpperCase() === 'OCUPADO').length;
    const available = rooms.filter(r => r.status?.toUpperCase() === 'DISPONIVEL').length;
    const cleaning = rooms.filter(r => r.status?.toUpperCase() === 'LIMPEZA').length;
    const maintenance = rooms.filter(r => r.status?.toUpperCase() === 'MANUTENCAO').length;
    const occupancyRate = Math.round((occupied / totalRooms) * 100);

    const now = new Date();
    const activeToday = reservations.filter(b => {
      const ci = new Date(b.check_in_date);
      const co = new Date(b.check_out_date);
      return ci <= now && co >= now && (b.status?.toUpperCase() === 'ATIVO' || b.status?.toUpperCase() === 'CONFIRMADO');
    });

    const guestsOnSite = activeToday.reduce((sum, b) => sum + (b.total_guests || 0), 0);
    const checkInsToday = reservations.filter(b => {
        const ci = new Date(b.check_in_date);
        return ci.toDateString() === now.toDateString();
    }).length;

    const checkOutsToday = reservations.filter(b => {
        const co = new Date(b.check_out_date);
        return co.toDateString() === now.toDateString();
    }).length;

    return { totalRooms, occupied, available, cleaning, maintenance, occupancyRate, guestsOnSite, checkInsToday, checkOutsToday, activeCount: activeToday.length };
  }, [rooms, reservations]);

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
      return <div className="flex h-screen items-center justify-center">Carregando painel...</div>;
  }

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto">
      {/* Barra de Título e Ações */}
      <div className="flex flex-col sm:flex-row gap-4 mb-8 justify-between items-end sm:items-center">
        <div>
          <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Painel Executivo</h2>
          <p className="text-slate-500">Status atual da operação hoteleira.</p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
          <div className="flex items-center bg-white px-4 py-2 rounded-xl shadow-sm border border-slate-200 w-full sm:w-64">
            <Search size={18} className="text-slate-400 mr-2" />
            <input placeholder="Buscar quarto ou hóspede..." className="outline-none w-full text-slate-700 bg-transparent" />
          </div>
          
        </div>
      </div>

      {/* Cards de Métricas */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6 transition-hover hover:shadow-md">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="bg-blue-100 text-blue-700 p-3 rounded-2xl">
                <Percent size={20} />
              </div>
              <p className="text-sm font-semibold text-slate-600">Ocupação</p>
            </div>
            <span className="text-2xl font-black text-slate-800">{metrics.occupancyRate}%</span>
          </div>
          <div className="h-2.5 rounded-full bg-slate-100 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${metrics.occupancyRate < 50 ? 'bg-green-500' : metrics.occupancyRate < 80 ? 'bg-yellow-500' : 'bg-red-600'}`}
              style={{ width: `${metrics.occupancyRate}%` }}
            />
          </div>
          <p className="mt-3 text-xs text-slate-500 font-medium">Equivale a {metrics.occupied} de {metrics.totalRooms} unidades</p>
        </div>

        <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="bg-indigo-100 text-indigo-700 p-3 rounded-2xl">
                <Users size={20} />
              </div>
              <p className="text-sm font-semibold text-slate-600">Hóspedes Ativos</p>
            </div>
            <span className="text-2xl font-black text-slate-800">{metrics.guestsOnSite}</span>
          </div>
          <p className="text-xs text-slate-500 font-medium">Em {metrics.activeCount} reservas ativas no momento</p>
        </div>

        <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="bg-green-100 text-green-700 p-3 rounded-2xl">
                <BedDouble size={20} />
              </div>
              <p className="text-sm font-semibold text-slate-600">Disponibilidade</p>
            </div>
            <span className="text-2xl font-black text-slate-800">{metrics.available}</span>
          </div>
          <div className="flex gap-2">
            <span className="bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded-lg text-[10px] font-bold">LIMPEZA: {metrics.cleaning}</span>
            <span className="bg-slate-50 text-slate-600 px-2 py-0.5 rounded-lg text-[10px] font-bold">MANUT: {metrics.maintenance}</span>
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="bg-orange-100 text-orange-700 p-3 rounded-2xl">
                <CalendarDays size={20} />
              </div>
              <p className="text-sm font-semibold text-slate-600">Turno de Hoje</p>
            </div>
            <div className="flex items-center justify-between gap-2">
                <div className="bg-green-50 text-green-700 px-3 py-2 rounded-xl flex-1 text-center">
                    <p className="text-[10px] font-bold uppercase opacity-70">Check-in</p>
                    <p className="text-lg font-black">{metrics.checkInsToday}</p>
                </div>
                <div className="bg-red-50 text-red-700 px-3 py-2 rounded-xl flex-1 text-center">
                    <p className="text-[10px] font-bold uppercase opacity-70">Check-out</p>
                    <p className="text-lg font-black">{metrics.checkOutsToday}</p>
                </div>
            </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6">
          <p className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
              <div className="w-1.5 h-4 bg-blue-600 rounded-full" />
              Distribuição da Frota
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

      {/* Grid de Quartos Situacionais */}
      <h3 className="text-lg font-bold text-slate-800 mb-4">Mapa de Quartos Ocupados</h3>
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
                <span className="text-xl font-black text-slate-800 group-hover:text-blue-600">#{room.id}</span>
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

      <RoomModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => {
            refetchRooms(); 
        }}
      />
    </div>
  );
}
