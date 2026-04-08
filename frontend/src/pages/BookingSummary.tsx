import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../services/api';

interface Payload {
  guest_id: number;
  room_id: number | null;
  check_in_date: string;
  check_out_date: string;
  mode: 'normal' | 'caravana';
  total_guests: number;
  daily_rate: number;
  notes: string | null;
  companions: { name: string; age: number }[];
}

interface Guest {
  id: number;
  name: string;
  email: string;
}

interface Room {
  id: number;
  number: string;
  type: string;
  price_per_night: number;
  max_capacity: number;
}

export default function BookingSummary() {
  const location = useLocation();
  const navigate = useNavigate();
  const statePayload = (location.state as any)?.payload as Payload | undefined;
  const [payload, setPayload] = useState<Payload | null>(statePayload ?? null);
  const [guest, setGuest] = useState<Guest | null>(null);
  const [room, setRoom] = useState<Room | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!payload) {
      const raw = sessionStorage.getItem('bookingDraft');
      if (raw) setPayload(JSON.parse(raw));
    }
  }, []);

  useEffect(() => {
    async function load() {
      if (!payload) return;
      setError(null);
      try {
        const promises = [];
        promises.push(api.get(`/guests/`));
        if (payload.room_id) promises.push(api.get(`/rooms/`));
        const res = await Promise.all(promises);
        const guests = res[0].data as Guest[];
        const g = guests.find((x) => x.id === payload.guest_id) || null;
        setGuest(g);
        if (payload.room_id) {
          const rooms = res[1].data as Room[];
          const r = rooms.find((x: Room) => x.id === payload.room_id) || null;
          setRoom(r);
        } else {
          setRoom(null);
        }
      } catch {
        setError('Falha ao carregar dados relacionados');
      }
    }
    load();
  }, [payload]);

  const totals = useMemo(() => {
    if (!payload) return { days: 0, perDay: 0, total: 0 };
    const ci = new Date(payload.check_in_date);
    const co = new Date(payload.check_out_date);
    const daysRaw = Math.floor((co.getTime() - ci.getTime()) / (1000 * 60 * 60 * 24));
    const days = daysRaw < 1 ? 1 : daysRaw;
    const perDay = (payload.daily_rate || 0) * (payload.total_guests || 1);
    const total = perDay * days;
    return { days, perDay, total };
  }, [payload]);

  async function handleConfirm() {
    if (!payload) return;
    setMessage(null);
    setError(null);
    try {
      await api.post('/bookings/', payload);
      setMessage('Reserva criada com sucesso');
      navigate('/bookings', { replace: true });
    } catch (err: any) {
      const msg = err.response?.data?.detail ?? err.message ?? 'Erro ao criar reserva';
      setError(msg);
    }
  }

  if (!payload) {
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <p className="text-slate-700">Nenhum dado de reserva encontrado.</p>
        <div className="mt-4">
          <button onClick={() => navigate('/bookings/new')} className="px-4 py-2 rounded-lg bg-blue-600 text-white">
            Voltar ao formulário
          </button>
        </div>
      </div>
    );
  }

  const invalidDates = new Date(payload.check_out_date) <= new Date(payload.check_in_date);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Resumo da Reserva</h2>
        <p className="text-slate-500">Revise os dados antes de confirmar.</p>
      </div>

      {error && <div className="bg-red-50 text-red-700 rounded-lg border border-red-200 p-4">{error}</div>}
      {message && <div className="bg-green-50 text-green-700 rounded-lg border border-green-200 p-4">{message}</div>}

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-slate-500">Hóspede</p>
            <p className="font-medium text-slate-800">{guest?.name ?? payload.guest_id}</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Quarto</p>
            <p className="font-medium text-slate-800">
              {room ? `#${room.number} — ${room.type}` : 'Sem quarto definido'}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Check-in</p>
            <p className="font-medium text-slate-800">
              {new Date(payload.check_in_date).toLocaleString('pt-BR')}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Check-out</p>
            <p className={`font-medium ${invalidDates ? 'text-red-600' : 'text-slate-800'}`}>
              {new Date(payload.check_out_date).toLocaleString('pt-BR')}
            </p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Modo</p>
            <p className="font-medium text-slate-800">{payload.mode}</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Total de Pessoas</p>
            <p className="font-medium text-slate-800">{payload.total_guests}</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Diária (R$)</p>
            <p className="font-medium text-slate-800">{payload.daily_rate?.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Total por Dia (R$)</p>
            <p className="font-medium text-slate-800">{totals.perDay.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Dias</p>
            <p className="font-medium text-slate-800">{totals.days}</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Valor Total (R$)</p>
            <p className="font-medium text-slate-800">{totals.total.toFixed(2)}</p>
          </div>
        </div>

        {payload.mode === 'normal' && payload.companions?.length > 0 && (
          <div className="pt-2">
            <p className="text-sm font-medium text-slate-600 mb-2">Acompanhantes</p>
            <ul className="space-y-1">
              {payload.companions.map((c, idx) => (
                <li key={`${c.name}-${idx}`} className="text-slate-700 text-sm">
                  {c.name} — {c.age} anos
                </li>
              ))}
            </ul>
          </div>
        )}

        {payload.notes && (
          <div className="pt-2">
            <p className="text-sm font-medium text-slate-600 mb-1">Observações</p>
            <p className="text-slate-700">{payload.notes}</p>
          </div>
        )}

        <div className="flex gap-3 pt-4">
          <button
            onClick={() => navigate('/bookings/new')}
            className="px-5 py-2 rounded-lg border bg-white"
          >
            Editar
          </button>
          <button
            onClick={handleConfirm}
            disabled={invalidDates}
            className={`px-5 py-2 rounded-lg font-semibold shadow-md transition ${
              invalidDates ? 'bg-slate-200 text-slate-500 cursor-not-allowed' : 'bg-green-600 text-white hover:bg-green-700'
            }`}
          >
            Confirmar Reserva
          </button>
        </div>
      </div>
    </div>
  );
}
