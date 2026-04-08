import { useEffect, useMemo, useState } from 'react';
import api from '../services/api';
import type { AxiosError } from 'axios';

interface Booking {
  id: number;
  room_number?: string | null;
  guest_name: string;
  status: 'pendente' | 'confirmado' | 'ativo' | 'concluido' | 'cancelado';
  total_amount: number;
  check_in_date: string;
  check_out_date: string;
}

interface Room {
  id: number;
  number: string;
  status: 'disponivel' | 'ocupado' | 'limpeza' | 'manutencao';
}

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}
function endOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}
function toDateOnlyISO(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
function addDays(d: Date, days: number) {
  const c = new Date(d);
  c.setDate(c.getDate() + days);
  return c;
}

export default function Calendar() {
  const [current, setCurrent] = useState(new Date());
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<string>('check_in_date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [search, setSearch] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selectedBooking, setSelectedBooking] = useState<Booking | null>(null);
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null);
  const [newCheckIn, setNewCheckIn] = useState<string>('');
  const [newCheckOut, setNewCheckOut] = useState<string>('');
  const [, setAvailLoading] = useState(false);
  const [, setAvailError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<{ booking: Booking; duration: number } | null>(null);
  const [dragHover, setDragHover] = useState<{ date: Date; valid: boolean } | null>(null);
  const [allRooms, setAllRooms] = useState<Room[]>([]);

  async function refreshAvailableRooms() {
    try {
      setAvailError(null);
      setAvailLoading(true);
      if (!newCheckIn || !newCheckOut) {
        const res = await api.get('/rooms/');
        setRooms(res.data);
        return;
      }
      const start = new Date(newCheckIn).toISOString();
      const end = new Date(newCheckOut).toISOString();
      const avail = await api.get(`/bookings/availability?start=${start}&end=${end}`);
      const available: Room[] = avail.data;
      setRooms(available);
      if (selectedBooking?.room_number) {
        const pre = available.find((r) => r.number === selectedBooking.room_number && r.status === 'disponivel');
        setSelectedRoomId(pre ? pre.id : null);
      }
    } catch {
      setAvailError('Falha ao carregar disponibilidade');
    } finally {
      setAvailLoading(false);
    }
  }

  const monthStart = startOfMonth(current);
  const monthEnd = endOfMonth(current);

  const gridDays = useMemo(() => {
    const startWeekDay = monthStart.getDay(); // 0-6, domingo=0
    const daysInMonth = monthEnd.getDate();
    const cells: Date[] = [];
    // Preencher espaço até o primeiro dia
    for (let i = 0; i < startWeekDay; i++) {
      cells.push(addDays(monthStart, i - startWeekDay));
    }
    // Dias do mês
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push(new Date(current.getFullYear(), current.getMonth(), d));
    }
    // Completar a última linha até múltiplo de 7
    while (cells.length % 7 !== 0) {
      cells.push(addDays(monthEnd, cells.length % 7));
    }
    return cells;
  }, [current, monthStart, monthEnd]);

  async function load() {
    try {
      setError(null);
      const res = await api.get('/bookings/', {
        params: {
          start: toDateOnlyISO(monthStart),
          end: toDateOnlyISO(monthEnd),
        },
      });
      setBookings(res.data);
    } catch {
      setError('Falha ao carregar reservas do calendário');
    }
  }

  useEffect(() => {
    const t = setTimeout(() => {
      load();
      setSelectedDay(null);
    }, 0);
    return () => clearTimeout(t);
  }, [current.getMonth(), current.getFullYear()]);

  function dayHasBookings(day: Date) {
    const dayStart = new Date(day.getFullYear(), day.getMonth(), day.getDate(), 0, 0, 0);
    const dayEnd = new Date(day.getFullYear(), day.getMonth(), day.getDate(), 23, 59, 59);
    return bookings.some((b) => {
      const inDate = new Date(b.check_in_date);
      const outDate = new Date(b.check_out_date);
      return inDate <= dayEnd && outDate >= dayStart;
    });
  }

  const bookingsForSelectedDay = useMemo(() => {
    if (!selectedDay) return [];
    const dayStart = new Date(selectedDay.getFullYear(), selectedDay.getMonth(), selectedDay.getDate(), 0, 0, 0);
    const dayEnd = new Date(selectedDay.getFullYear(), selectedDay.getMonth(), selectedDay.getDate(), 23, 59, 59);
    return bookings.filter((b) => {
      const inDate = new Date(b.check_in_date);
      const outDate = new Date(b.check_out_date);
      return inDate <= dayEnd && outDate >= dayStart;
    });
  }, [selectedDay, bookings]);

  const filteredSortedBookings = useMemo(() => {
    const base = bookingsForSelectedDay.filter((b) => {
      const matchesStatus = filterStatus ? b.status === filterStatus : true;
      const term = search.trim().toLowerCase();
      const matchesSearch = term
        ? (b.guest_name?.toLowerCase().includes(term) ||
           (b.room_number ?? '').toLowerCase().includes(term))
        : true;
      return matchesStatus && matchesSearch;
    });
    const sorted = [...base].sort((a, b) => {
      let av: string | number | Date = '';
      let bv: string | number | Date = '';
      if (sortBy === 'guest_name') {
        av = a.guest_name?.toLowerCase() ?? '';
        bv = b.guest_name?.toLowerCase() ?? '';
      } else if (sortBy === 'room_number') {
        av = (a.room_number ?? '').toLowerCase();
        bv = (b.room_number ?? '').toLowerCase();
      } else if (sortBy === 'total_amount') {
        av = a.total_amount ?? 0;
        bv = b.total_amount ?? 0;
      } else if (sortBy === 'check_out_date') {
        av = new Date(a.check_out_date).getTime();
        bv = new Date(b.check_out_date).getTime();
      } else {
        av = new Date(a.check_in_date).getTime();
        bv = new Date(b.check_in_date).getTime();
      }
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [bookingsForSelectedDay, filterStatus, sortBy, sortDir, search]);
  
  function bookingDurationDays(b: Booking) {
    const start = new Date(b.check_in_date).getTime();
    const end = new Date(b.check_out_date).getTime();
    const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
    return days < 1 ? 1 : days;
  }
  function composeDateWithTime(day: Date, template: Date) {
    return new Date(day.getFullYear(), day.getMonth(), day.getDate(), template.getHours(), template.getMinutes(), template.getSeconds());
  }
  async function ensureRoomsLoaded() {
    if (allRooms.length === 0) {
      const res = await api.get('/rooms/');
      setAllRooms(res.data);
    }
  }
  function getRoomIdByNumber(number?: string | null) {
    if (!number) return null;
    const r = allRooms.find((x) => x.number === number);
    return r ? r.id : null;
  }
  async function validateDrop(day: Date) {
    if (!dragging) return false;
    const origIn = new Date(dragging.booking.check_in_date);
    const newIn = composeDateWithTime(day, origIn);
    const newOut = addDays(newIn, dragging.duration);
    if (!dragging.booking.room_number) {
      return true;
    }
    const start = newIn.toISOString();
    const end = newOut.toISOString();
    try {
      const avail = await api.get(`/bookings/availability?start=${start}&end=${end}`);
      const available: Room[] = avail.data;
      const ok = available.some((r) => r.number === dragging.booking.room_number && r.status === 'disponivel');
      return !!ok;
    } catch {
      return false;
    }
  }
  function isConflictDay(day: Date) {
    if (!selectedBooking || !selectedBooking.room_number) return false;
    const d = bookingDurationDays(selectedBooking);
    const newIn = composeDateWithTime(day, new Date(selectedBooking.check_in_date));
    const newOut = addDays(newIn, d);
    return bookings.some((b) => {
      if (b.id === selectedBooking.id) return false;
      if (b.room_number !== selectedBooking.room_number) return false;
      if (!(b.status === 'confirmado' || b.status === 'ativo')) return false;
      const bi = new Date(b.check_in_date);
      const bo = new Date(b.check_out_date);
      return bo > newIn && bi < newOut;
    });
  }

  function prevMonth() {
    setCurrent(new Date(current.getFullYear(), current.getMonth() - 1, 1));
  }
  function nextMonth() {
    setCurrent(new Date(current.getFullYear(), current.getMonth() + 1, 1));
  }

  async function openBooking(b: Booking) {
    try {
      setSelectedBooking(b);
      setNewCheckIn(new Date(b.check_in_date).toISOString().slice(0,16));
      setNewCheckOut(new Date(b.check_out_date).toISOString().slice(0,16));
      await refreshAvailableRooms();
    } catch {
      alert('Falha ao carregar quartos');
    }
  }

  async function doCheckIn() {
    try {
      if (!selectedBooking || !selectedRoomId) {
        alert('Selecione um quarto disponível');
        return;
      }
      await api.post('/bookings/checkin', { booking_id: selectedBooking.id, room_id: selectedRoomId });
      alert('Check-in confirmado');
      setSelectedBooking(null);
      setSelectedRoomId(null);
      const res = await api.get('/bookings/', { params: { start: toDateOnlyISO(monthStart), end: toDateOnlyISO(monthEnd) } });
      setBookings(res.data);
    } catch (err) {
      const axErr = err as AxiosError<{ detail?: string }>;
      const msg = axErr.response?.data?.detail ?? 'Falha ao confirmar check-in';
      alert(msg);
    }
  }

  useEffect(() => {
    refreshAvailableRooms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [newCheckIn, newCheckOut, selectedBooking?.id]);
  async function doReschedule() {
    try {
      if (!selectedBooking) return;
      if (!newCheckIn || !newCheckOut) {
        alert('Informe novas datas');
        return;
      }
      const payload = {
        booking_id: selectedBooking.id,
        room_id: selectedRoomId ?? null,
        check_in_date: new Date(newCheckIn).toISOString(),
        check_out_date: new Date(newCheckOut).toISOString(),
      };
      await api.post('/bookings/reschedule', payload);
      alert('Reserva remanejada');
      setSelectedBooking(null);
      setSelectedRoomId(null);
      const res = await api.get('/bookings/', { params: { start: toDateOnlyISO(monthStart), end: toDateOnlyISO(monthEnd) } });
      setBookings(res.data);
    } catch (err) {
      const axErr = err as AxiosError<{ detail?: string }>;
      const msg = axErr.response?.data?.detail ?? 'Falha ao remanejar';
      alert(msg);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2">
        <div className="flex items-center justify-between mb-4">
          <button onClick={prevMonth} className="px-3 py-2 rounded-lg border bg-white hover:bg-slate-50">Anterior</button>
          <h2 className="text-xl font-bold text-slate-800">
            {current.toLocaleString('pt-BR', { month: 'long', year: 'numeric' })}
          </h2>
          <button onClick={nextMonth} className="px-3 py-2 rounded-lg border bg-white hover:bg-slate-50">Próximo</button>
        </div>

        {error && <div className="bg-red-50 text-red-700 rounded-lg border border-red-200 p-4 mb-4">{error}</div>}

        <div className="grid grid-cols-7 gap-2">
          {['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'].map((wd) => (
            <div key={wd} className="text-center text-slate-500 font-medium">{wd}</div>
          ))}
          {gridDays.map((d, idx) => {
            const isCurrentMonth = d.getMonth() === current.getMonth();
            const hasBookings = dayHasBookings(d);
            const conflict = isConflictDay(d);
            const isHover = dragHover?.date && d.toDateString() === dragHover.date.toDateString();
            const hoverValid = isHover && dragHover?.valid;
            return (
              <button
                key={`${d.toISOString()}-${idx}`}
                onClick={() => setSelectedDay(d)}
                onDragOver={(e) => { e.preventDefault(); }}
                onDragEnter={async () => {
                  if (dragging) {
                    const ok = await validateDrop(d);
                    setDragHover({ date: d, valid: ok });
                  }
                }}
                onDrop={async () => {
                  if (!dragging) return;
                  const ok = await validateDrop(d);
                  if (!ok) {
                    alert('Conflito de disponibilidade');
                    setDragHover(null);
                    setDragging(null);
                    return;
                  }
                  await ensureRoomsLoaded();
                  const origIn = new Date(dragging.booking.check_in_date);
                  const newIn = composeDateWithTime(d, origIn);
                  const newOut = addDays(newIn, dragging.duration);
                  const roomId = getRoomIdByNumber(dragging.booking.room_number);
                  try {
                    await api.post('/bookings/reschedule', {
                      booking_id: dragging.booking.id,
                      room_id: roomId,
                      check_in_date: newIn.toISOString(),
                      check_out_date: newOut.toISOString(),
                    });
                    alert('Reserva remanejada');
                    setDragging(null);
                    setDragHover(null);
                    const res = await api.get('/bookings/', { params: { start: toDateOnlyISO(monthStart), end: toDateOnlyISO(monthEnd) } });
                    setBookings(res.data);
                  } catch {
                    alert('Falha ao remanejar');
                    setDragging(null);
                    setDragHover(null);
                  }
                }}
                className={`h-20 rounded-lg border flex items-center justify-center transition 
                  ${isCurrentMonth ? 'bg-white' : 'bg-slate-50'}
                  ${hasBookings ? 'ring-2 ring-blue-400' : ''}
                  ${conflict ? 'border-red-400' : ''}
                  ${isHover ? (hoverValid ? 'ring-2 ring-green-500' : 'ring-2 ring-red-500') : ''}
                `}
                title={hasBookings ? 'Dia com reservas' : ''}
              >
                <span className={`text-sm ${isCurrentMonth ? 'text-slate-800' : 'text-slate-400'}`}>
                  {d.getDate()}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <p className="text-lg font-semibold text-slate-800 mb-2">Reservas do dia</p>
        <p className="text-slate-500 mb-4">
          {selectedDay
            ? selectedDay.toLocaleDateString('pt-BR')
            : 'Selecione um dia no calendário'}
        </p>
        <div className="relative mb-4">
          <div className="flex items-center gap-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar por hóspede ou quarto"
              className="flex-1 px-3 py-2 border rounded-lg bg-white"
            />
            <button
              onClick={() => setFiltersOpen(!filtersOpen)}
              className="px-3 py-2 border rounded-lg bg-white"
              title="Abrir filtros e ordenação"
            >
              Filtros
            </button>
          </div>
          {filtersOpen && (
            <div className="absolute right-0 mt-2 w-full sm:w-80 bg-white rounded-xl shadow-lg border border-slate-200 p-4 z-10">
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Status</label>
                  <select
                    value={filterStatus ?? ''}
                    onChange={(e) => setFilterStatus(e.target.value || null)}
                    className="w-full px-3 py-2 border rounded-lg bg-white"
                  >
                    <option value="">Todos os status</option>
                    <option value="pendente">Pendente</option>
                    <option value="confirmado">Confirmado</option>
                    <option value="ativo">Ativo</option>
                    <option value="concluido">Concluído</option>
                    <option value="cancelado">Cancelado</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Ordenar por</label>
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg bg-white"
                  >
                    <option value="check_in_date">Check-in</option>
                    <option value="check_out_date">Check-out</option>
                    <option value="guest_name">Hóspede</option>
                    <option value="room_number">Quarto</option>
                    <option value="total_amount">Total</option>
                  </select>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-500">Ordem</span>
                  <button
                    onClick={() => setSortDir(sortDir === 'asc' ? 'desc' : 'asc')}
                    className="px-3 py-2 border rounded-lg bg-white"
                    title="Alternar ordem"
                  >
                    {sortDir === 'asc' ? 'Asc' : 'Desc'}
                  </button>
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={() => setFiltersOpen(false)}
                    className="px-3 py-2 rounded-lg bg-blue-600 text-white"
                  >
                    Aplicar
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
        <div className="space-y-3">
          {selectedDay && bookingsForSelectedDay.length === 0 && (
            <div className="text-slate-500">Sem reservas para o dia selecionado.</div>
          )}
          {filteredSortedBookings.map((b) => (
            <button
              key={b.id}
              onClick={() => openBooking(b)}
              draggable
              onDragStart={() => {
                setDragging({ booking: b, duration: bookingDurationDays(b) });
              }}
              onDragEnd={() => {
                setDragging(null);
                setDragHover(null);
              }}
              className="border rounded-xl p-3 text-left hover:bg-slate-50 transition"
            >
              <p className="font-semibold text-slate-800">
                {b.guest_name} {b.room_number ? `— Quarto ${b.room_number}` : ''}
              </p>
              <p className="text-slate-600 text-sm">
                {new Date(b.check_in_date).toLocaleString('pt-BR')} até {new Date(b.check_out_date).toLocaleString('pt-BR')}
              </p>
              <p className="text-slate-600 text-sm">Status: {b.status}</p>
              <p className="text-slate-700 text-sm">Total: R$ {b.total_amount?.toFixed(2)}</p>
            </button>
          ))}
        </div>
      </div>
      {selectedBooking && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => { setSelectedBooking(null); setSelectedRoomId(null); }}>
          <div className="bg-white rounded-2xl w-full max-w-lg p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <div>
                <p className="text-sm text-slate-500">Reserva #{selectedBooking.id}</p>
                <h3 className="text-xl font-bold text-slate-800">{selectedBooking.guest_name}</h3>
              </div>
              <button onClick={() => { setSelectedBooking(null); setSelectedRoomId(null); }} className="px-3 py-2 rounded-lg border bg-white">Fechar</button>
            </div>
            <div className="space-y-2 text-sm">
              <p className="text-slate-600">Período: {new Date(selectedBooking.check_in_date).toLocaleString('pt-BR')} — {new Date(selectedBooking.check_out_date).toLocaleString('pt-BR')}</p>
              <p className="text-slate-600">Status: {selectedBooking.status}</p>
              <p className="text-slate-700">Total: R$ {selectedBooking.total_amount?.toFixed(2)}</p>
            </div>
            <div className="mt-4">
              <label className="block text-xs font-medium text-slate-500 mb-1">Quarto</label>
              <select
                value={selectedRoomId ?? ''}
                onChange={(e) => setSelectedRoomId(parseInt(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg bg-white"
              >
                <option value="">Manter quarto atual</option>
                {rooms.filter((r) => r.status === 'disponivel').map((r) => (
                  <option key={r.id} value={r.id}>Quarto {r.number}</option>
                ))}
              </select>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-3">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Novo Check-in</label>
                  <input type="datetime-local" className="w-full px-3 py-2 border rounded-lg bg-white" value={newCheckIn} onChange={(e) => setNewCheckIn(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Novo Check-out</label>
                  <input type="datetime-local" className="w-full px-3 py-2 border rounded-lg bg-white" value={newCheckOut} onChange={(e) => setNewCheckOut(e.target.value)} />
                </div>
              </div>
              <div className="flex gap-2 mt-3">
                <button onClick={doReschedule} className="px-3 py-2 rounded-lg bg-slate-800 text-white">Remanejar</button>
                <button onClick={doCheckIn} className="px-3 py-2 rounded-lg bg-blue-600 text-white">Confirmar Check-in</button>
                <button onClick={() => { setSelectedBooking(null); setSelectedRoomId(null); }} className="px-3 py-2 rounded-lg border bg-white">Cancelar</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
