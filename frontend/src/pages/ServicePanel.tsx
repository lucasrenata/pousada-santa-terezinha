import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import api from '../services/api';

type Role = 'admin' | 'recepcionista' | 'camareira' | 'manutencao' | 'faxina';
type RoomStatus = 'disponivel' | 'ocupado' | 'limpeza' | 'manutencao';

interface Room {
  id: number;
  number: string;
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
  const [noteRoomId, setNoteRoomId] = useState<number | null>(null);
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

  async function markClean(roomId: number) {
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
    return rooms.filter((r) => (r.number.toLowerCase().includes(term) || r.type.toLowerCase().includes(term)));
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
    <div>
      <div className="mb-6">
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl p-6 text-white shadow-md flex justify-between items-start">
          <div>
            <h2 className="text-2xl font-bold">Painel de Serviços</h2>
            <p className="opacity-90">Camareira e Manutenção</p>
            <div className="mt-3 flex gap-2">
              <span className="px-2 py-1 text-xs rounded-full bg-white/20 uppercase tracking-tighter">Role: {role || 'Não logado'}</span>
              <span className={`px-2 py-1 text-xs rounded-full ${canMaintain ? 'bg-green-400/30' : 'bg-red-400/30'}`}>
                Permissão: {canMaintain ? 'SIM' : 'NÃO'}
              </span>
            </div>
          </div>
          <button 
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 bg-white/20 hover:bg-white/30 px-4 py-2 rounded-xl transition-all border border-white/10 font-medium text-sm"
          >
            <ArrowLeft size={18} />
            Voltar
          </button>
        </div>
      </div>

      <div className="mb-4">
        <div className="flex items-center bg-white px-3 py-2 rounded-lg shadow-sm border border-slate-200 w-full max-w-md">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filtrar por número ou tipo (ex.: 101, casal, luxo)"
            className="outline-none w-full text-slate-700 bg-transparent"
          />
          {search && (
            <button onClick={() => setSearch('')} className="ml-2 text-slate-500">Limpar</button>
          )}
        </div>
      </div>

      {loading && <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 text-center">Carregando...</div>}

      {!loading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl shadow-sm border border-yellow-300 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-yellow-800">Quartos para Limpeza</h3>
              <span className="text-sm text-yellow-700 bg-yellow-50 px-2 py-1 rounded-lg border border-yellow-200">Total: {cleaningRooms.length}</span>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              {cleaningRooms.map((r) => (
                <div key={r.id} className="border border-yellow-200 rounded-xl p-4 bg-yellow-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium text-yellow-700">Quarto</p>
                      <p className="text-xl font-bold text-yellow-900">{r.number}</p>
                    </div>
                    {statusBadge(r.status)}
                  </div>
                  <p className="text-sm text-yellow-800">Tipo: {r.type} • Cap: {r.max_capacity}</p>
                  <div className="mt-3">
                    <button
                      onClick={() => markClean(r.id)}
                      disabled={role !== 'camareira' && role !== 'faxina' && role !== 'admin'}
                      className={`px-3 py-2 rounded-lg text-sm font-medium border ${
                        (role === 'camareira' || role === 'faxina' || role === 'admin') ? 'bg-blue-600 text-white border-blue-700 hover:bg-blue-700' : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                      }`}
                      title={role === 'camareira' ? 'Liberar após limpeza' : 'Acesso restrito à Camareira'}
                    >
                      Liberar
                    </button>
                  </div>
                </div>
              ))}
              {cleaningRooms.length === 0 && <p className="text-yellow-700">Nenhum quarto aguardando limpeza</p>}
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-stone-300 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-stone-800">Quartos em Manutenção</h3>
              <span className="text-sm text-stone-700 bg-stone-50 px-2 py-1 rounded-lg border border-stone-200">Total: {maintenanceRooms.length}</span>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              {maintenanceRooms.map((r) => (
                <div key={r.id} className="border border-stone-300 rounded-xl p-4 bg-stone-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium text-stone-700">Quarto</p>
                      <p className="text-xl font-bold text-stone-900">{r.number}</p>
                    </div>
                    {statusBadge(r.status)}
                  </div>
                  <p className="text-sm text-stone-700">Obs: {r.maintenance_note || '—'}</p>
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => markClean(r.id)}
                      disabled={role !== 'manutencao' && role !== 'admin'}
                      className={`px-3 py-2 rounded-lg text-sm font-medium border ${
                        (role === 'manutencao' || role === 'admin') ? 'bg-green-600 text-white border-green-700 hover:bg-green-700' : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                      }`}
                      title={role === 'manutencao' ? 'Tornar disponível' : 'Acesso restrito à Manutenção'}
                    >
                      Disponibilizar
                    </button>
                  </div>
                </div>
              ))}
              {maintenanceRooms.length === 0 && <p className="text-stone-700">Nenhum quarto em manutenção</p>}
            </div>

            <hr className="my-6" />

            <div>
              <h4 className="text-sm font-semibold text-stone-800 mb-2">Colocar quarto em manutenção</h4>
              <div className="flex gap-2">
                <select
                  className="border rounded-lg px-3 py-2 w-40"
                  value={noteRoomId ?? ''}
                  onChange={(e) => setNoteRoomId(parseInt(e.target.value))}
                >
                  <option value="" disabled>Selecione o quarto</option>
                  {filteredRooms.filter(r => r.status !== 'ocupado').map((r) => (
                    <option key={r.id} value={r.id}>{r.number} — {r.type}</option>
                  ))}
                </select>
                <input
                  className="border rounded-lg px-3 py-2 flex-1"
                  placeholder="Observação (ex.: torneira com vazamento)"
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                />
                <button
                  onClick={saveMaintenance}
                  disabled={!noteRoomId || !noteText.trim()}
                  className={`px-3 py-2 rounded-lg text-sm font-medium border ${
                    noteRoomId && noteText.trim()
                      ? 'bg-stone-700 text-white border-stone-800 hover:bg-stone-800'
                      : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                  }`}
                >
                  Manutenção
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
