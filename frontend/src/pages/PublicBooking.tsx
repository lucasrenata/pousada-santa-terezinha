import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../services/api';

type BookingMode = 'normal' | 'caravana';

interface Room {
  id: string; // O ID agora é o número do quarto
  type: string;
  price_per_night: number;
  max_capacity: number;
}

interface Companion {
  name: string;
  age: number;
}

export default function PublicBooking() {
  const { tenant_id } = useParams();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [roomId, setRoomId] = useState<string | null>(null);
  const [checkInDate, setCheckInDate] = useState<string>('');
  const [checkOutDate, setCheckOutDate] = useState<string>('');
  const [dailyRate, setDailyRate] = useState<string>('');
  const [mode, setMode] = useState<BookingMode>('normal');
  const [totalGuests, setTotalGuests] = useState<number>(1);
  const [notes, setNotes] = useState<string>('');
  const [companions, setCompanions] = useState<Companion[]>([]);
  const [newCompanion, setNewCompanion] = useState<Companion>({ name: '', age: 0 });

  const [guestName, setGuestName] = useState('');
  const [guestEmail, setGuestEmail] = useState('');
  const [guestPhone, setGuestPhone] = useState('');
  const [guestDocument, setGuestDocument] = useState('');
  const [guestBirthDate, setGuestBirthDate] = useState('');
  const [guestProfession, setGuestProfession] = useState('');
  const [addressZip, setAddressZip] = useState('');
  const [addressStreet, setAddressStreet] = useState('');
  const [addressNumber, setAddressNumber] = useState('');
  const [addressNeighborhood, setAddressNeighborhood] = useState('');
  const [addressCity, setAddressCity] = useState('');
  const [addressState, setAddressState] = useState('');
  const [cepLoading, setCepLoading] = useState(false);
  const [cepError, setCepError] = useState<string | null>(null);

  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function onlyDigits(s: string) {
    return s.replace(/\D/g, '');
  }
  function formatCPF(s: string) {
    const d = onlyDigits(s).slice(0, 11);
    return d
      .replace(/(\d{3})(\d)/, '$1.$2')
      .replace(/(\d{3})(\d)/, '$1.$2')
      .replace(/(\d{3})(\d{1,2})$/, '$1-$2');
  }
  function formatPhone(s: string) {
    const d = onlyDigits(s).slice(0, 11);
    return d
      .replace(/(\d{2})(\d)/, '($1) $2')
      .replace(/(\d{5})(\d{1,4})$/, '$1-$2');
  }
  function formatCEP(s: string) {
    const d = onlyDigits(s).slice(0, 8);
    return d.replace(/(\d{5})(\d{1,3})$/, '$1-$2');
  }
  function isEmailValid(s: string) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
  }
  function capacityExceeded() {
    if (!roomId) return false;
    const r = rooms.find((x) => x.id === roomId);
    if (!r) return false;
    return totalGuests > r.max_capacity;
  }
  const datesValid = Boolean(checkInDate && checkOutDate);

  useEffect(() => {
    loadRooms();
  }, []);

  async function loadRooms() {
    try {
      if (!tenant_id) return;
      const res = await api.get(`/rooms/public?tenant_id=${tenant_id}`);
      setRooms(res.data);
    } catch {
      setError('Falha ao carregar quartos');
    }
  }

  const refreshAvailableRooms = useCallback(async () => {
    try {
      if (!checkInDate || !checkOutDate) {
        setRooms([]);
        return;
      }
      const start = new Date(checkInDate).toISOString();
      const end = new Date(checkOutDate).toISOString();
      const guests = mode === 'normal' ? 1 + companions.length : totalGuests;
      const t_id = tenant_id || "1";
      const availRes = await api.get(`/bookings/availability/public?start=${start}&end=${end}&guests=${guests}&tenant_id=${t_id}`);
      const available: Room[] = availRes.data;
      setRooms(available);
      if (roomId && !available.find((r) => r.id === roomId)) {
        setRoomId(null);
        setDailyRate('');
      }
    } catch {
      // Em caso de falha, mantém lista atual
    }
  }, [checkInDate, checkOutDate, roomId, mode, companions, totalGuests, tenant_id]);

  useEffect(() => {
    refreshAvailableRooms();
  }, [refreshAvailableRooms]);

  useEffect(() => {
    if (mode === 'normal') {
      setTotalGuests(1 + companions.length);
    }
  }, [mode, companions]);
  
  const fetchCep = useCallback(async () => {
    const d = onlyDigits(addressZip);
    if (d.length !== 8) {
      setCepError(null);
      return;
    }
    try {
      setCepLoading(true);
      setCepError(null);
      const res = await fetch(`https://viacep.com.br/ws/${d}/json/`);
      const data = await res.json();
      if (data && !data.erro) {
        setAddressStreet(data.logradouro || '');
        setAddressNeighborhood(data.bairro || '');
        setAddressCity(data.localidade || '');
        setAddressState(data.uf || '');
        setCepError(null);
      } else {
        setCepError('CEP não encontrado');
      }
    } catch {
      setCepError('Falha ao buscar CEP');
    } finally {
      setCepLoading(false);
    }
  }, [addressZip]);
  
  useEffect(() => {
    fetchCep();
  }, [fetchCep]);

  function addCompanion() {
    if (!newCompanion.name || !newCompanion.age) return;
    setCompanions((prev) => [...prev, newCompanion]);
    setNewCompanion({ name: '', age: 0 });
  }

  function removeCompanion(index: number) {
    setCompanions((prev) => prev.filter((_, i) => i !== index));
  }

  async function submitPublic(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setError(null);
    try {
      if (!guestName || !guestEmail || !guestPhone || !guestDocument || !guestBirthDate || !guestProfession || !addressZip || !addressStreet || !addressNumber || !addressNeighborhood || !addressCity || !addressState) {
        throw new Error('Preencha todos os dados do hóspede');
      }
      if (!isEmailValid(guestEmail)) {
        throw new Error('Email inválido');
      }
      const cpfDigits = onlyDigits(guestDocument);
      if (cpfDigits.length < 9) {
        throw new Error('Documento inválido');
      }
      const phoneDigits = onlyDigits(guestPhone);
      if (phoneDigits.length < 10) {
        throw new Error('Telefone inválido');
      }
      const cepDigits = onlyDigits(addressZip);
      if (cepDigits.length !== 8) {
        throw new Error('CEP inválido');
      }
      if (!checkInDate || !checkOutDate) throw new Error('Informe check-in e check-out');
      if (!roomId) throw new Error('Selecione um quarto para definir a diária');
      if (!dailyRate || isNaN(parseFloat(dailyRate))) throw new Error('Diária inválida');
      if (roomId && capacityExceeded()) {
        const r = rooms.find((x) => x.id === roomId);
        throw new Error(`Capacidade excedida. Máximo ${r?.max_capacity ?? 0} pessoas`);
      }

      const payload = {
        guest: {
          name: guestName,
          email: guestEmail,
          phone: guestPhone,
          document: guestDocument,
          birth_date: new Date(guestBirthDate),
          profession: guestProfession,
          address_zip: addressZip,
          address_street: addressStreet,
          address_number: addressNumber,
          address_neighborhood: addressNeighborhood,
          address_city: addressCity,
          address_state: addressState,
        },
        room_id: roomId ?? null,
        check_in_date: new Date(checkInDate).toISOString(),
        check_out_date: new Date(checkOutDate).toISOString(),
        mode,
        total_guests: totalGuests,
        daily_rate: parseFloat(dailyRate),
        notes: notes || null,
        companions,
        tenant_id: parseInt(tenant_id || "1")
      };
      await api.post('/bookings/public', payload);
      setMessage('Solicitação enviada. Aguarde confirmação por email.');
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = anyErr.response?.data?.detail ?? anyErr.message ?? 'Erro ao enviar solicitação';
      setError(msg);
    }
  }
  async function payNowCard() {
    setError(null);
    setMessage(null);
    try {
      if (!checkInDate || !checkOutDate || !guestName || !guestEmail || !guestDocument) {
        setError('Preencha dados do hóspede e as datas');
        return;
      }
      if (!roomId) {
        setError('Selecione um quarto para definir a diária');
        return;
      }
      if (!dailyRate || isNaN(parseFloat(dailyRate))) {
        setError('Diária inválida');
        return;
      }
      const payload = {
        guest: {
          name: guestName,
          email: guestEmail,
          phone: guestPhone,
          document: guestDocument,
          birth_date: guestBirthDate || null,
          profession: guestProfession,
          address_zip: addressZip,
          address_street: addressStreet,
          address_number: addressNumber,
          address_neighborhood: addressNeighborhood,
          address_city: addressCity,
          address_state: addressState,
        },
        room_id: roomId ?? null,
        check_in_date: new Date(checkInDate).toISOString(),
        check_out_date: new Date(checkOutDate).toISOString(),
        mode,
        total_guests: totalGuests,
        daily_rate: parseFloat(dailyRate),
        notes: notes || null,
        companions,
        tenant_id: parseInt(tenant_id || "1")
      };
      const res = await api.post('/bookings/public', payload);
      const bookingId = res.data?.booking_id;
      if (!bookingId) {
        setError('Falha ao criar reserva para pagamento');
        return;
      }
      const t_id = tenant_id || "1";
      const payRes = await api.post(`/payments/public/${bookingId}/card?tenant_id=${t_id}`);
      const url = payRes.data?.sandbox_init_point || payRes.data?.init_point;
      if (!url) {
        setError('Falha ao iniciar pagamento');
        return;
      }
      window.open(url, '_blank');
      setMessage('Abrimos o pagamento em nova aba. Após aprovação, confirmaremos por email.');
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = anyErr.response?.data?.detail ?? anyErr.message ?? 'Erro ao iniciar pagamento';
      setError(msg);
    }
  }
  

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h2 className="text-2xl font-bold text-slate-800 mb-4">Reserva</h2>
      {error && <div className="bg-red-50 text-red-700 rounded-lg border border-red-200 p-4 mb-4">{error}</div>}
      {message && <div className="bg-green-50 text-green-700 rounded-lg border border-green-200 p-4 mb-4">{message}</div>}

      <form onSubmit={submitPublic} className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <div className="space-y-3">
          <p className="text-lg font-semibold text-slate-800">Dados do Hóspede</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Nome</label>
              <input className="w-full border rounded-lg px-3 py-2" value={guestName} onChange={(e) => setGuestName(e.target.value)} placeholder="Nome completo" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Email</label>
              <input type="email" className="w-full border rounded-lg px-3 py-2" value={guestEmail} onChange={(e) => setGuestEmail(e.target.value)} placeholder="seu@email.com" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Telefone</label>
              <input className="w-full border rounded-lg px-3 py-2" value={guestPhone} onChange={(e) => setGuestPhone(formatPhone(e.target.value))} placeholder="WhatsApp" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Documento (CPF/RG)</label>
              <input className="w-full border rounded-lg px-3 py-2" value={guestDocument} onChange={(e) => setGuestDocument(formatCPF(e.target.value))} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Nascimento</label>
              <input type="date" className="w-full border rounded-lg px-3 py-2" value={guestBirthDate} onChange={(e) => setGuestBirthDate(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Profissão</label>
              <input className="w-full border rounded-lg px-3 py-2" value={guestProfession} onChange={(e) => setGuestProfession(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">CEP</label>
              <div className="flex items-center gap-2">
                <input className="w-full border rounded-lg px-3 py-2" value={addressZip} onChange={(e) => setAddressZip(formatCEP(e.target.value))} />
                {cepLoading && <span className="text-slate-500 text-sm">Carregando...</span>}
                {!cepLoading && cepError && <span className="text-red-600 text-sm">{cepError}</span>}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Rua</label>
              <input className="w-full border rounded-lg px-3 py-2" value={addressStreet} onChange={(e) => setAddressStreet(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Número</label>
              <input className="w-full border rounded-lg px-3 py-2" value={addressNumber} onChange={(e) => setAddressNumber(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Bairro</label>
              <input className="w-full border rounded-lg px-3 py-2" value={addressNeighborhood} onChange={(e) => setAddressNeighborhood(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Cidade</label>
              <input className="w-full border rounded-lg px-3 py-2" value={addressCity} onChange={(e) => setAddressCity(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">Estado</label>
              <input className="w-full border rounded-lg px-3 py-2" value={addressState} onChange={(e) => setAddressState(e.target.value)} />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Check-in</label>
            <input
              type="datetime-local"
              className="w-full border rounded-lg px-3 py-2"
              value={checkInDate}
              onChange={(e) => setCheckInDate(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Check-out</label>
            <input
              type="datetime-local"
              className="w-full border rounded-lg px-3 py-2"
              value={checkOutDate}
              onChange={(e) => setCheckOutDate(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Quarto</label>
            {!datesValid ? (
              <div className="rounded-lg border bg-blue-50 text-blue-700 p-3 text-sm">
                Selecione as datas para ver disponibilidade
              </div>
            ) : (
              <select
                className="w-full border rounded-lg px-3 py-2"
                value={roomId ?? ''}
                onChange={(e) => {
                  const val = e.target.value || null;
                  setRoomId(val);
                  if (val) {
                    const r = rooms.find((x) => x.id === val);
                    if (r) setDailyRate(String(r.price_per_night ?? ''));
                  }
                }}
              >
                <option value="">Selecione um quarto</option>
                {rooms.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.id} - {r.type} (capacidade {r.max_capacity})
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Diária (R$)</label>
            <input
              type="number"
              step="0.01"
              className="w-full border rounded-lg px-3 py-2 bg-slate-50 text-slate-700"
              value={dailyRate}
              readOnly
              disabled
              placeholder={roomId ? 'Definida pelo quarto' : 'Selecione um quarto'}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Modo</label>
            <select
              className="w-full border rounded-lg px-3 py-2"
              value={mode}
              onChange={(e) => setMode(e.target.value as BookingMode)}
            >
              <option value="normal">Normal</option>
              <option value="caravana">Caravana</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Total de Pessoas</label>
            <input
              type="number"
              min={1}
              className="w-full border rounded-lg px-3 py-2"
              value={totalGuests}
              onChange={(e) => setTotalGuests(parseInt(e.target.value) || 1)}
              readOnly={mode === 'normal'}
            />
          </div>

          <div className="sm:col-span-2">
            <label className="block text-sm font-medium text-slate-600 mb-1">Observações</label>
            <textarea
              className="w-full border rounded-lg px-3 py-2"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>

        <div className="space-y-3">
          <p className="text-sm font-medium text-slate-600">Acompanhantes</p>
          <div className="flex gap-2">
            <input
              placeholder="Nome"
              className="border rounded-lg px-3 py-2 w-full"
              value={newCompanion.name}
              onChange={(e) => setNewCompanion((c) => ({ ...c, name: e.target.value }))}
            />
            <input
              type="number"
              placeholder="Idade"
              className="border rounded-lg px-3 py-2 w-32"
              value={newCompanion.age || ''}
              onChange={(e) => setNewCompanion((c) => ({ ...c, age: parseInt(e.target.value) || 0 }))}
            />
            <button
              type="button"
              onClick={addCompanion}
              className="bg-slate-800 text-white px-4 py-2 rounded-lg hover:bg-slate-900"
            >
              Adicionar
            </button>
          </div>
          {companions.length > 0 && (
            <ul className="space-y-2">
              {companions.map((c, idx) => (
                <li key={`${c.name}-${idx}`} className="flex items-center justify-between bg-slate-50 px-3 py-2 rounded-lg border">
                  <span className="text-slate-700">{c.name} — {c.age} anos</span>
                  <button
                    type="button"
                    className="text-red-600 hover:text-red-700 text-sm font-medium"
                    onClick={() => removeCompanion(idx)}
                  >
                    remover
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            className="bg-blue-600 text-white px-5 py-2 rounded-lg shadow-md hover:bg-blue-700 transition font-semibold"
          >
            Enviar Solicitação
          </button>
          <button
            type="button"
            onClick={payNowCard}
            className="bg-green-600 text-white px-5 py-2 rounded-lg shadow-md hover:bg-green-700 transition font-semibold"
          >
            Reservar e pagar agora (Cartão)
          </button>
        </div>
      </form>
    </div>
  );
}
