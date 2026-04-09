import { useState, useEffect } from 'react';
import { CalendarHeart, Plus, Pencil, Trash2, X, Check, Loader2 } from 'lucide-react';
import api from '../services/api';

interface Event {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  location: string;
  description: string;
  color: string;
}

const MONTHS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];

export default function Events() {
  const [events, setEvents] = useState<Event[]>([]);
  const [year, setYear] = useState(2026);
  const [loading, setLoading] = useState(false);
  const [editingEvent, setEditingEvent] = useState<Event | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ name: '', start_date: '', end_date: '', location: 'Canção Nova - Cachoeira Paulista/SP', description: '', color: '#6366f1' });

  useEffect(() => { loadEvents(); }, [year]);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/events/?year=${year}`);
      setEvents(res.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const seedEvents = async () => {
    if (!confirm(`Isso vai popular o calendário ${year} com todos os eventos da Canção Nova. Continuar?`)) return;
    setLoading(true);
    try {
      await api.post(`/events/seed?year=${year}`);
      await loadEvents();
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const handleSave = async () => {
    try {
      if (editingEvent) {
        await api.put(`/events/${editingEvent.id}`, formData);
      } else {
        await api.post('/events/', formData);
      }
      setShowForm(false);
      setEditingEvent(null);
      setFormData({ name: '', start_date: '', end_date: '', location: 'Canção Nova - Cachoeira Paulista/SP', description: '', color: '#6366f1' });
      await loadEvents();
    } catch (err) { console.error(err); }
  };

  const handleEdit = (e: Event) => {
    setEditingEvent(e);
    setFormData({ name: e.name, start_date: e.start_date, end_date: e.end_date, location: e.location || '', description: e.description || '', color: e.color });
    setShowForm(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Excluir este evento?')) return;
    await api.delete(`/events/${id}`);
    await loadEvents();
  };

  const formatDate = (d: string) => {
    const [, m, day] = d.split('-');
    return `${day}/${m}`;
  };

  const eventsByMonth: Record<number, Event[]> = {};
  events.forEach(e => {
    const month = parseInt(e.start_date.split('-')[1]);
    if (!eventsByMonth[month]) eventsByMonth[month] = [];
    eventsByMonth[month].push(e);
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-3xl font-black text-slate-900 tracking-tight flex items-center gap-3">
            <CalendarHeart className="text-indigo-600" size={32} />
            Calendário de Eventos
          </h2>
          <p className="text-slate-500 font-medium mt-1">Eventos da região sincronizados com suas reservas</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            <button onClick={() => setYear(y => y - 1)} className="px-3 py-2 text-slate-600 hover:bg-slate-50 font-bold text-lg">←</button>
            <span className="px-4 py-2 font-black text-indigo-700 text-lg border-x border-slate-200">{year}</span>
            <button onClick={() => setYear(y => y + 1)} className="px-3 py-2 text-slate-600 hover:bg-slate-50 font-bold text-lg">→</button>
          </div>
          <button onClick={seedEvents} disabled={loading} className="bg-amber-500 hover:bg-amber-600 text-white px-4 py-2.5 rounded-xl font-bold text-sm shadow-lg shadow-amber-100 transition-all disabled:opacity-50">
            {loading ? <Loader2 size={16} className="animate-spin" /> : '🔄 Popular Canção Nova'}
          </button>
          <button onClick={() => { setEditingEvent(null); setFormData({ name: '', start_date: '', end_date: '', location: 'Canção Nova - Cachoeira Paulista/SP', description: '', color: '#6366f1' }); setShowForm(true); }} className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2.5 rounded-xl font-bold text-sm shadow-lg shadow-indigo-100 transition-all flex items-center gap-2">
            <Plus size={16} /> Novo Evento
          </button>
        </div>
      </div>

      {/* Modal Form */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowForm(false)}>
          <div onClick={e => e.stopPropagation()} className="bg-white rounded-3xl shadow-2xl w-full max-w-lg p-8 space-y-5 animate-in zoom-in duration-300">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-black text-slate-800">{editingEvent ? 'Editar Evento' : 'Novo Evento'}</h3>
              <button onClick={() => setShowForm(false)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase">Nome do Evento</label>
                <input value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} className="w-full bg-slate-50 rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-indigo-200 mt-1" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase">Início</label>
                  <input type="date" value={formData.start_date} onChange={e => setFormData({...formData, start_date: e.target.value})} className="w-full bg-slate-50 rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-indigo-200 mt-1" />
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase">Fim</label>
                  <input type="date" value={formData.end_date} onChange={e => setFormData({...formData, end_date: e.target.value})} className="w-full bg-slate-50 rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-indigo-200 mt-1" />
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase">Local</label>
                <input value={formData.location} onChange={e => setFormData({...formData, location: e.target.value})} className="w-full bg-slate-50 rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-indigo-200 mt-1" />
              </div>
              <div className="flex items-center gap-3">
                <label className="text-xs font-bold text-slate-400 uppercase">Cor</label>
                <input type="color" value={formData.color} onChange={e => setFormData({...formData, color: e.target.value})} className="w-10 h-10 rounded-lg border-none cursor-pointer" />
              </div>
            </div>
            <button onClick={handleSave} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-3.5 rounded-xl font-black text-sm transition-all flex items-center justify-center gap-2 shadow-lg shadow-indigo-100">
              <Check size={18} /> {editingEvent ? 'Salvar Alterações' : 'Criar Evento'}
            </button>
          </div>
        </div>
      )}

      {/* Calendar Grid */}
      {loading && events.length === 0 ? (
        <div className="flex justify-center py-20">
          <Loader2 size={32} className="animate-spin text-indigo-400" />
        </div>
      ) : events.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-3xl border border-slate-100 shadow-sm">
          <CalendarHeart size={64} className="mx-auto text-slate-200 mb-4" />
          <h3 className="text-xl font-black text-slate-700 mb-2">Nenhum evento em {year}</h3>
          <p className="text-slate-400 mb-6">Clique em "Popular Canção Nova" para importar automaticamente o calendário completo.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {MONTHS.map((monthName, idx) => {
            const monthNum = idx + 1;
            const monthEvents = eventsByMonth[monthNum] || [];
            if (monthEvents.length === 0) return null;
            return (
              <div key={monthNum} className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden hover:shadow-md transition-shadow">
                <div className="bg-gradient-to-r from-slate-800 to-slate-900 text-white px-5 py-3">
                  <h3 className="font-black text-sm uppercase tracking-widest">{monthName}</h3>
                  <p className="text-[10px] text-slate-400 font-bold">{monthEvents.length} evento{monthEvents.length > 1 ? 's' : ''}</p>
                </div>
                <div className="p-3 space-y-2">
                  {monthEvents.map(e => (
                    <div key={e.id} className="group relative rounded-xl p-3 transition-all hover:shadow-md" style={{ backgroundColor: e.color + '12', borderLeft: `4px solid ${e.color}` }}>
                      <div className="flex justify-between items-start gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="font-bold text-xs text-slate-800 leading-tight truncate">{e.name}</p>
                          <p className="text-[10px] text-slate-500 font-bold mt-1">
                            📅 {formatDate(e.start_date)} → {formatDate(e.end_date)}
                          </p>
                        </div>
                        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                          <button onClick={() => handleEdit(e)} className="p-1.5 rounded-lg bg-white shadow-sm hover:bg-indigo-50 text-indigo-600">
                            <Pencil size={12} />
                          </button>
                          <button onClick={() => handleDelete(e.id)} className="p-1.5 rounded-lg bg-white shadow-sm hover:bg-red-50 text-red-500">
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
