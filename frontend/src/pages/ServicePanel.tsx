import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Search, Plus, BedDouble, Wrench, Shield } from 'lucide-react';
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
  const [activeTab, setActiveTab] = useState<'limpeza' | 'manutencao'>('limpeza');

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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Header Estilo Dashboard */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
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
        <div className="space-y-8">
          {/* NAVEGAÇÃO POR ABAS */}
          <div className="flex p-1.5 bg-slate-100 rounded-2xl w-full sm:w-fit gap-1 border border-slate-200 overflow-x-auto scrollbar-hide">
            <button
              onClick={() => setActiveTab('limpeza')}
              className={`flex-1 sm:flex-none flex items-center justify-center gap-3 px-4 sm:px-8 py-3 rounded-xl font-bold transition-all ${
                activeTab === 'limpeza' 
                ? 'bg-white text-yellow-600 shadow-md ring-1 ring-slate-200/50' 
                : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <BedDouble size={18} />
              <span>Aguardando Limpeza</span>
              <span className={`px-2 py-0.5 rounded-lg text-[10px] ${
                activeTab === 'limpeza' ? 'bg-yellow-100 text-yellow-700' : 'bg-slate-200 text-slate-500'
              }`}>
                {cleaningRooms.length}
              </span>
            </button>
            <button
              onClick={() => setActiveTab('manutencao')}
              className={`flex-1 sm:flex-none flex items-center justify-center gap-3 px-4 sm:px-8 py-3 rounded-xl font-bold transition-all ${
                activeTab === 'manutencao' 
                ? 'bg-white text-indigo-600 shadow-md ring-1 ring-slate-200/50' 
                : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Wrench size={18} />
              <span>Manutenção Ativa</span>
              <span className={`px-2 py-0.5 rounded-lg text-[10px] ${
                activeTab === 'manutencao' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-200 text-slate-500'
              }`}>
                {maintenanceRooms.length}
              </span>
            </button>
          </div>

          <div className="min-h-[500px]">
            {activeTab === 'limpeza' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6">
                  {cleaningRooms.map((r) => (
                    <div key={r.id} className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6 group hover:shadow-lg transition-all duration-300 relative overflow-hidden">
                      <div className="absolute top-0 right-0 w-24 h-24 bg-yellow-400/5 rounded-full -mr-8 -mt-8" />
                      
                      <div className="flex items-start justify-between mb-6">
                        <div>
                          <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Unidade</span>
                          <p className="text-4xl font-black text-slate-800">#{r.id}</p>
                        </div>
                        {statusBadge(r.status)}
                      </div>
                      
                      <div className="bg-slate-50 rounded-2xl p-4 mb-6">
                        <div className="flex items-center gap-2 text-slate-600">
                          <BedDouble size={14} className="text-slate-400" />
                          <p className="text-sm font-semibold">{r.type}</p>
                        </div>
                      </div>

                      <button
                        onClick={() => markClean(r.id)}
                        disabled={role !== 'camareira' && role !== 'faxina' && role !== 'admin'}
                        className={`w-full py-4 rounded-2xl text-sm font-black transition-all shadow-md ${
                          (role === 'camareira' || role === 'faxina' || role === 'admin') 
                            ? 'bg-yellow-500 text-white hover:bg-yellow-600 hover:shadow-yellow-200 active:scale-95' 
                            : 'bg-slate-50 text-slate-400 cursor-not-allowed'
                        }`}
                      >
                        CONCLUIR LIMPEZA
                      </button>
                    </div>
                  ))}
                  {cleaningRooms.length === 0 && (
                    <div className="col-span-full py-24 bg-slate-50/50 rounded-3xl border-2 border-dashed border-slate-200 text-center">
                        <div className="bg-white w-16 h-16 rounded-full shadow-sm flex items-center justify-center mx-auto mb-4 border border-slate-200">
                          <p className="text-2xl">✨</p>
                        </div>
                        <p className="text-slate-500 font-bold text-lg">Tudo limpo por aqui!</p>
                        <p className="text-slate-400 text-sm">Não há quartos aguardando faxina no momento.</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'manutencao' && (
              <div className="space-y-10 animate-in fade-in slide-in-from-bottom-2 duration-500">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6">
                  {maintenanceRooms.map((r) => (
                    <div key={r.id} className="bg-white rounded-3xl shadow-sm border border-slate-200 p-6 border-t-8 border-t-slate-500 hover:shadow-lg transition-all relative overflow-hidden group">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex flex-col">
                          <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Unidade</span>
                          <p className="text-4xl font-black text-slate-800">#{r.id}</p>
                        </div>
                        {statusBadge(r.status)}
                      </div>
                      
                      <div className="bg-slate-50 rounded-2xl p-4 mb-6 min-h-[100px] border border-slate-100 group-hover:bg-slate-100 transition-colors">
                        <div className="flex items-center gap-2 mb-2">
                          <Wrench size={12} className="text-slate-400" />
                          <span className="text-[10px] font-bold text-slate-400 uppercase">Relatório Técnico</span>
                        </div>
                        <p className="text-sm text-slate-700 font-medium leading-relaxed italic">"{r.maintenance_note || 'Sem observações detalhadas.'}"</p>
                      </div>

                      <button
                        onClick={() => markClean(r.id)}
                        disabled={role !== 'manutencao' && role !== 'admin' && role !== 'faxina' && role !== 'camareira'}
                        className={`w-full py-4 rounded-2xl text-sm font-black transition-all shadow-md group-hover:scale-[1.02] ${
                          (role === 'manutencao' || role === 'admin' || role === 'faxina' || role === 'camareira') 
                            ? 'bg-slate-800 text-white hover:bg-slate-900 active:scale-95' 
                            : 'bg-slate-50 text-slate-400 cursor-not-allowed border border-slate-100'
                        }`}
                      >
                        LIBERAR QUARTO
                      </button>
                    </div>
                  ))}
                  {maintenanceRooms.length === 0 && (
                    <div className="col-span-full py-24 bg-slate-50/50 rounded-3xl border-2 border-dashed border-slate-200 text-center">
                        <div className="bg-white w-16 h-16 rounded-full shadow-sm flex items-center justify-center mx-auto mb-4 border border-slate-200">
                          <Wrench size={24} className="text-slate-300" />
                        </div>
                        <p className="text-slate-500 font-bold text-lg">Sem manutenções ativas</p>
                        <p className="text-slate-400 text-sm">Toda a infraestrutura está em perfeito estado. 🙌</p>
                    </div>
                  )}
                </div>

                <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl sm:rounded-[2.5rem] p-6 sm:p-8 text-white shadow-2xl relative overflow-hidden border border-slate-700 max-w-4xl">
                    <div className="relative z-10">
                        <div className="flex items-center gap-4 mb-8">
                          <div className="bg-blue-600 p-3 rounded-2xl shadow-lg ring-4 ring-blue-500/20">
                            <Plus size={24} className="text-white" />
                          </div>
                          <div>
                            <h4 className="text-2xl font-black tracking-tight">Interdição Técnica</h4>
                            <p className="text-slate-400 text-xs font-semibold uppercase tracking-widest">Bloquear unidade para reparos</p>
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <div className="space-y-2">
                                <label className="text-[10px] font-black uppercase text-slate-400 ml-1">Selecione o Quarto</label>
                                <select
                                  className="w-full bg-slate-700/50 border border-slate-600 rounded-2xl px-5 py-4 text-white outline-none focus:ring-4 ring-blue-500/30 transition-all font-bold appearance-none cursor-pointer"
                                  value={noteRoomId ?? ''}
                                  onChange={(e) => setNoteRoomId(e.target.value)}
                                >
                                  <option value="" disabled className="bg-slate-900">Qual quarto?</option>
                                  {filteredRooms.map((r) => (
                                    <option key={r.id} value={r.id} className="bg-slate-900">
                                      #{r.id} — {r.type} {r.status === 'ocupado' ? '(OCUPADO)' : ''}
                                    </option>
                                  ))}
                                </select>
                            </div>
                            <div className="md:col-span-2 space-y-2">
                                <label className="text-[10px] font-black uppercase text-slate-400 ml-1">Descrição do Problema</label>
                                <input
                                  className="w-full bg-slate-700/50 border border-slate-600 rounded-2xl px-5 py-4 text-white outline-none focus:ring-4 ring-blue-500/30 transition-all placeholder:text-slate-500 font-medium"
                                  placeholder="Detalhe o que precisa ser consertado..."
                                  value={noteText}
                                  onChange={(e) => setNoteText(e.target.value)}
                                />
                            </div>
                        </div>

                        <div className="flex justify-end mt-8">
                          <button
                            onClick={saveMaintenance}
                            disabled={!noteRoomId || !noteText.trim()}
                            className={`px-6 sm:px-12 py-4 rounded-2xl text-sm font-black transition-all shadow-xl flex items-center gap-3 ${
                              noteRoomId && noteText.trim()
                                ? 'bg-blue-600 text-white hover:bg-blue-700 hover:-translate-y-1 active:scale-95 active:translate-y-0'
                                : 'bg-slate-700 text-slate-500 cursor-not-allowed border border-slate-600'
                            }`}
                          >
                            <Shield size={18} />
                            CONFIRMAR BLOQUEIO
                          </button>
                        </div>
                    </div>
                    <div className="absolute right-0 top-0 w-64 h-64 bg-blue-600/10 rounded-full -mr-32 -mt-32 blur-3xl pointer-events-none" />
                    <div className="absolute -right-12 -bottom-12 opacity-5 rotate-12 pointer-events-none">
                        <Wrench size={240} />
                    </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
