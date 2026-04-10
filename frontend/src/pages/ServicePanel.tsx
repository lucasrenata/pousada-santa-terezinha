import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Search, Plus, BedDouble, Wrench } from 'lucide-react';
import api from '../services/api';

type Role = 'admin' | 'recepcionista' | 'camareira' | 'manutencao' | 'faxina';
type RoomStatus = 'disponivel' | 'ocupado' | 'limpeza' | 'manutencao';

interface Room {
  id: string;
  type: string;
  price_per_night: number;
  status: RoomStatus;
  floor?: number;
  max_capacity: number;
  maintenance_note?: string | null;
}

export default function ServicePanel() {
  const navigate = useNavigate();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [noteRoomId, setNoteRoomId] = useState<string | null>(null);
  const [noteText, setNoteText] = useState('');
  const [search, setSearch] = useState('');

  const rawRole = localStorage.getItem('role');
  const role = (rawRole?.toLowerCase() as Role | null) ?? null;
  const canMaintain = ['admin', 'manutencao', 'camareira', 'recepcionista', 'faxina'].includes(role || '');

  async function loadRooms() {
    try {
      setLoading(true);
      const res = await api.get('/rooms/');
      setRooms(res.data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRooms();
  }, []);

  async function markClean(roomId: string) {
    try {
      await api.post(`/rooms/${roomId}/clean`);
      await loadRooms();
      alert('Quarto liberado');
    } catch {
      alert('Falha ao liberar quarto');
    }
  }

  async function saveMaintenance() {
    if (!noteRoomId || !noteText.trim()) return;
    if (!canMaintain) {
      alert(`Você não tem permissão para realizar esta ação. Seu nível atual: ${role}`);
      return;
    }
    try {
      await api.post(`/rooms/${noteRoomId}/maintenance`, null, { params: { note: noteText.trim() } });
      setNoteRoomId(null);
      setNoteText('');
      await loadRooms();
      alert('Quarto marcado em manutenção');
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Falha ao marcar manutenção');
    }
  }

  const filteredRooms = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return rooms;
    return rooms.filter((r) => (r.id.toLowerCase().includes(term) || r.type.toLowerCase().includes(term)));
  }, [rooms, search]);
  const cleaningRooms = useMemo(() => filteredRooms.filter(r => r.status === 'limpeza'), [filteredRooms]);
  const maintenanceRooms = useMemo(() => filteredRooms.filter(r => r.status === 'manutencao'), [filteredRooms]);

  function statusBadge(s: RoomStatus) {
    const base = 'px-2 py-0.5 rounded-full text-xs font-medium';
    if (s === 'disponivel') return <span className={`${base} bg-green-100 text-green-700`}>Disponível</span>;
    if (s === 'ocupado') return <span className={`${base} bg-red-100 text-red-700`}>Ocupado</span>;
    if (s === 'limpeza') return <span className={`${base} bg-yellow-100 text-yellow-800`}>Limpeza</span>;
    return <span className={`${base} bg-stone-200 text-stone-800`}>Manutenção</span>;
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header Estilo Dashboard */}
      <div className="flex flex-col md:flex-row justify-between items-end md:items-center gap-4 mb-8">
        <div>
          <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Painel de Serviços</h2>
          <p className="text-slate-500">Gestão operacional de limpeza e manutenção.</p>
        </div>
        
        <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
          <div className="flex items-center bg-white px-4 py-2.5 rounded-2xl shadow-sm border border-slate-200 flex-1 md:w-80">
            <Search size={18} className="text-slate-400 mr-2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filtrar quarto ou tipo..."
              className="outline-none w-full text-slate-700 bg-transparent font-medium"
            />
          </div>
          <div className="px-4 py-2 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
            <span className="text-xs font-black text-indigo-700 uppercase tracking-tighter">
              Acesso: {role}
            </span>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="bg-white rounded-3xl shadow-sm border border-slate-200 p-16 text-center">
            <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-slate-400 font-medium italic">Sincronizando status dos quartos...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
          
          {/* COLUNA: LIMPEZA */}
          <div className="space-y-6">
            <div className="flex items-center justify-between px-2">
                <div className="flex items-center gap-3">
                    <div className="bg-yellow-100 text-yellow-700 p-2 rounded-xl">
                        <BedDouble size={20} />
                    </div>
                    <h3 className="text-xl font-bold text-slate-800">Aguardando Limpeza</h3>
                </div>
                <span className="bg-white px-3 py-1 rounded-full text-xs font-bold border border-yellow-200 text-yellow-700 shadow-sm">
                    {cleaningRooms.length} unidades
                </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {cleaningRooms.map((r) => (
                <div key={r.id} className="bg-white rounded-3xl shadow-sm border border-slate-200 p-5 group hover:shadow-md transition-all duration-300">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Unidade</span>
                      <p className="text-3xl font-black text-slate-800">#{r.id}</p>
                    </div>
                    {statusBadge(r.status)}
                  </div>
                  
                  <div className="bg-slate-50 rounded-2xl p-3 mb-4">
                    <p className="text-xs font-medium text-slate-500">Categoria: <span className="text-slate-800">{r.type}</span></p>
                  </div>

                  <button
                    onClick={() => markClean(r.id)}
                    disabled={role !== 'camareira' && role !== 'faxina' && role !== 'admin'}
                    className={`w-full py-3 rounded-2xl text-sm font-bold transition-all shadow-sm ${
                      (role === 'camareira' || role === 'faxina' || role === 'admin') 
                        ? 'bg-yellow-500 text-white hover:bg-yellow-600 active:scale-95' 
                        : 'bg-slate-50 text-slate-400 cursor-not-allowed'
                    }`}
                  >
                    Concluir Limpeza
                  </button>
                </div>
              ))}
              {cleaningRooms.length === 0 && (
                <div className="col-span-full py-12 bg-slate-50 rounded-3xl border-2 border-dashed border-slate-200 text-center">
                    <p className="text-slate-400 font-medium italic">Tudo limpo por aqui! ✨</p>
                </div>
              )}
            </div>
          </div>

          {/* COLUNA: MANUTENÇÃO */}
          <div className="space-y-6">
            <div className="flex items-center justify-between px-2">
                <div className="flex items-center gap-3">
                    <div className="bg-stone-100 text-stone-700 p-2 rounded-xl">
                        <Wrench size={20} />
                    </div>
                    <h3 className="text-xl font-bold text-slate-800">Manutenção Ativa</h3>
                </div>
                <span className="bg-white px-3 py-1 rounded-full text-xs font-bold border border-stone-200 text-stone-700 shadow-sm">
                    {maintenanceRooms.length} unidades
                </span>
            </div>

            {/* Listagem Ativa */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {maintenanceRooms.map((r) => (
                <div key={r.id} className="bg-white rounded-3xl shadow-sm border border-slate-200 p-5 border-l-8 border-l-stone-400">
                  <div className="flex items-start justify-between mb-2">
                    <p className="text-2xl font-black text-slate-800">#{r.id}</p>
                    {statusBadge(r.status)}
                  </div>
                  
                  <div className="bg-stone-50 rounded-2xl p-4 mb-4 min-h-[80px]">
                    <p className="text-xs font-bold text-stone-500 uppercase mb-1">Motivo/Nota:</p>
                    <p className="text-sm text-slate-700 font-medium leading-relaxed italic">"{r.maintenance_note || 'Sem observações'}"</p>
                  </div>

                  <button
                    onClick={() => markClean(r.id)}
                    disabled={role !== 'manutencao' && role !== 'admin'}
                    className={`w-full py-3 rounded-2xl text-sm font-bold transition-all ${
                      (role === 'manutencao' || role === 'admin') 
                        ? 'bg-stone-800 text-white hover:bg-stone-900 active:scale-95 shadow-lg' 
                        : 'bg-slate-50 text-slate-400 cursor-not-allowed border border-slate-100'
                    }`}
                  >
                    Liberar Quarto
                  </button>
                </div>
              ))}
              {maintenanceRooms.length === 0 && (
                <div className="col-span-full py-12 bg-slate-50 rounded-3xl border-2 border-dashed border-slate-200 text-center">
                    <p className="text-slate-400 font-medium italic">Sem reparos pendentes. 🙌</p>
                </div>
              )}
            </div>

            {/* Ação de Interdição */}
            <div className="mt-8 bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl p-6 text-white shadow-xl relative overflow-hidden">
                <div className="relative z-10">
                    <h4 className="text-lg font-bold mb-4 flex items-center gap-2">
                        <Plus size={20} className="text-yellow-400" />
                        Nova Interdição Técnica
                    </h4>
                    
                    <div className="space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-[10px] font-black uppercase text-slate-400 ml-1">Quarto</label>
                                <select
                                  className="w-full bg-slate-700/50 border border-slate-600 rounded-2xl px-4 py-3 text-white outline-none focus:ring-2 ring-blue-500 transition-all font-medium"
                                  value={noteRoomId ?? ''}
                                  onChange={(e) => setNoteRoomId(e.target.value)}
                                >
                                  <option value="" disabled className="bg-slate-900">Selecione o alvo</option>
                                  {filteredRooms.map((r) => (
                                    <option key={r.id} value={r.id} className="bg-slate-900">
                                      {r.id} — {r.type} {r.status === 'ocupado' ? '(OCUPADO)' : ''}
                                    </option>
                                  ))}
                                </select>
                            </div>
                            <div className="space-y-1">
                                <label className="text-[10px] font-black uppercase text-slate-400 ml-1">Descrição</label>
                                <input
                                  className="w-full bg-slate-700/50 border border-slate-600 rounded-2xl px-4 py-3 text-white outline-none focus:ring-2 ring-blue-500 transition-all placeholder:text-slate-500"
                                  placeholder="Ex: Ar condicionado vazando"
                                  value={noteText}
                                  onChange={(e) => setNoteText(e.target.value)}
                                />
                            </div>
                        </div>

                        <button
                          onClick={saveMaintenance}
                          disabled={!noteRoomId || !noteText.trim()}
                          className={`w-full py-4 rounded-2xl text-sm font-bold transition-all shadow-lg ${
                            noteRoomId && noteText.trim()
                              ? 'bg-blue-600 text-white hover:bg-blue-700 active:scale-95'
                              : 'bg-slate-700 text-slate-500 cursor-not-allowed border border-slate-600'
                          }`}
                        >
                          Interditar Quarto Imediatamente
                        </button>
                    </div>
                </div>
                {/* Efeito Visual */}
                <div className="absolute -right-8 -bottom-8 opacity-10">
                    <Wrench size={120} />
                </div>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
