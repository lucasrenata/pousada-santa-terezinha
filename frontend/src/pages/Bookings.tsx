import React, { useEffect, useState, useCallback } from 'react';
import api from '../services/api';
import { useLocation } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';

type BookingMode = 'normal' | 'caravana';

interface Guest {
  id: number;
  name: string;
  email: string;
  phone?: string;
  document?: string;
}

interface Room {
  id: number;
  number: string;
  type: string;
  price_per_night: number;
  max_capacity: number;
}

interface Companion {
  name: string;
  age: number;
}

export default function Bookings() {
  const [guests, setGuests] = useState<Guest[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const location = useLocation();
  const navigate = useNavigate();

  const [guestId, setGuestId] = useState<number | null>(null);
  const [roomId, setRoomId] = useState<number | null>(null);
  const [checkInDate, setCheckInDate] = useState<string>('');
  const [checkOutDate, setCheckOutDate] = useState<string>('');
  const [dailyRate, setDailyRate] = useState<string>('');
  const [mode, setMode] = useState<BookingMode>('normal');
  const [totalGuests, setTotalGuests] = useState<number>(1);
  const [notes, setNotes] = useState<string>('');
  const [companions, setCompanions] = useState<Companion[]>([]);
  const [newCompanion, setNewCompanion] = useState<Companion>({ name: '', age: 0 });

  const [createdBookingId, setCreatedBookingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const [docSearch, setDocSearch] = useState('');
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

  async function loadData() {
    try {
      const [g, r] = await Promise.all([api.get('/guests/'), api.get('/rooms/')]);
      setGuests(g.data);
      setRooms(r.data);
    } catch (err) {
      setError('Falha ao carregar hóspedes e quartos');
    }
  }

  useEffect(() => {
    loadData();
  }, []);
  
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const rid = params.get('roomId');
    if (rid) {
      const id = parseInt(rid);
      setRoomId(id);
      const r = rooms.find((x) => x.id === id);
      if (r) setDailyRate(String(r.price_per_night ?? ''));
    }
  }, [location.search, rooms]);
  
  useEffect(() => {
    if (mode === 'normal') {
      setTotalGuests(1 + companions.length);
    }
  }, [mode, companions]);

  const refreshAvailableRooms = useCallback(async () => {
    try {
      if (!checkInDate || !checkOutDate) {
        const r = await api.get('/rooms/');
        setRooms(r.data);
        return;
      }
      const start = new Date(checkInDate).toLocaleDateString('en-CA');
      const end = new Date(checkOutDate).toLocaleDateString('en-CA');
      const guests = mode === 'normal' ? 1 + companions.length : totalGuests;
      const availRes = await api.get(`/bookings/availability?start=${start}&end=${end}&guests=${guests}`);
      const available: Room[] = availRes.data;
      setRooms(available);
      if (roomId && !available.find((r) => r.id === roomId)) {
        setRoomId(null);
        setDailyRate('');
      }
    } catch {
      // Mantém lista atual em caso de falha
    }
  }, [checkInDate, checkOutDate, roomId, mode, companions, totalGuests]);

  useEffect(() => {
    refreshAvailableRooms();
  }, [refreshAvailableRooms]);

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

  async function searchGuest() {
    setError(null);
    try {
      if (!docSearch) throw new Error('Informe CPF/RG para busca');
      const res = await api.get(`/guests/${docSearch}`);
      const g = res.data as Guest;
      setGuestId(g.id);
      setGuestName(g.name);
      setGuestEmail(g.email ?? '');
      setGuestPhone((g as any).phone ?? '');
      setGuestDocument(docSearch);
      setMessage('Hóspede carregado');
    } catch (err: any) {
      setMessage(null);
      setGuestId(null);
      setError(err.response?.data?.detail ?? err.message ?? 'Hóspede não encontrado');
    }
  }

  async function saveGuest() {
    setError(null);
    setMessage(null);
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
      const payload = {
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
      };
      const res = await api.post('/guests/', payload);
      setGuestId(res.data.id);
      setMessage('Hóspede salvo');
    } catch (err: any) {
      const msg = err.response?.data?.detail ?? err.message ?? 'Erro ao salvar hóspede';
      setError(msg);
    }
  }

  function addCompanion() {
    if (!newCompanion.name || !newCompanion.age) return;
    setCompanions((prev) => [...prev, newCompanion]);
    setNewCompanion({ name: '', age: 0 });
  }

  function removeCompanion(index: number) {
    setCompanions((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleCreateBooking(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setError(null);
    try {
      if (!guestId) throw new Error('Selecione ou cadastre um hóspede');
      if (!checkInDate || !checkOutDate) throw new Error('Informe check-in e check-out');
      if (!dailyRate) throw new Error('Informe a diária');
      if (capacityExceeded()) {
        const r = rooms.find((x) => x.id === roomId);
        throw new Error(`Capacidade excedida. Máximo ${r?.max_capacity ?? 0} pessoas`);
      }

      const payload = {
        guest_id: guestId,
        room_id: roomId ?? null,
        check_in_date: new Date(checkInDate).toLocaleDateString('en-CA'),
        check_out_date: new Date(checkOutDate).toLocaleDateString('en-CA'),
        mode,
        total_guests: totalGuests,
        daily_rate: parseFloat(dailyRate),
        notes: notes || null,
        companions
      };

      const res = await api.post('/bookings/', payload);
      setCreatedBookingId(res.data.booking_id);
      setMessage('Reserva criada com sucesso');
    } catch (err: any) {
      const msg = err.response?.data?.detail ?? err.message ?? 'Erro ao criar reserva';
      setError(msg);
    }
  }
  
  function goToSummary() {
    setError(null);
    setMessage(null);
    try {
      if (!guestId) throw new Error('Selecione um hóspede');
      if (!checkInDate || !checkOutDate) throw new Error('Informe check-in e check-out');
      if (!dailyRate) throw new Error('Informe a diária');
      if (capacityExceeded()) {
        const r = rooms.find((x) => x.id === roomId);
        throw new Error(`Capacidade excedida. Máximo ${r?.max_capacity ?? 0} pessoas`);
      }
      const payload = {
        guest_id: guestId!,
        room_id: roomId ?? null,
        check_in_date: new Date(checkInDate).toLocaleDateString('en-CA'),
        check_out_date: new Date(checkOutDate).toLocaleDateString('en-CA'),
        mode,
        total_guests: totalGuests,
        daily_rate: parseFloat(dailyRate),
        notes: notes || null,
        companions
      };
      sessionStorage.setItem('bookingDraft', JSON.stringify(payload));
      navigate('/bookings/summary', { state: { payload } });
    } catch (err: any) {
      const msg = err.message ?? 'Preencha os campos obrigatórios';
      setError(msg);
    }
  }

  async function handleCheckIn() {
    try {
      setMessage(null);
      setError(null);
      if (!createdBookingId) throw new Error('Crie uma reserva primeiro');
      if (!roomId) throw new Error('Selecione um quarto para o check-in');
      await api.post('/bookings/checkin', { booking_id: createdBookingId, room_id: roomId });
      setMessage('Check-in confirmado');
      navigate('/rooms');
    } catch (err: any) {
      const msg = err.response?.data?.detail ?? err.message ?? 'Erro ao realizar check-in';
      setError(msg);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Reservas</h2>
        <p className="text-slate-500">Crie reservas e confirme o check-in vinculando a um quarto.</p>
      </div>

      {error && <div className="bg-red-50 text-red-700 rounded-lg border border-red-200 p-4">{error}</div>}
      {message && <div className="bg-green-50 text-green-700 rounded-lg border border-green-200 p-4">{message}</div>}

      <form onSubmit={handleCreateBooking} className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
        <div className="space-y-3">
          <p className="text-lg font-semibold text-slate-800">Dados do Hóspede</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-slate-600 mb-1">CPF/RG</label>
              <input className="w-full border rounded-lg px-3 py-2" value={docSearch} onChange={(e) => setDocSearch(e.target.value)} placeholder="000.000.000-00" />
            </div>
            <div className="flex items-end">
              <button type="button" onClick={searchGuest} className="w-full px-4 py-2 rounded-lg bg-slate-800 text-white">Buscar</button>
            </div>
          </div>
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
          <div className="flex justify-end">
            <button type="button" onClick={saveGuest} className="px-4 py-2 rounded-lg bg-blue-600 text-white">Salvar Hóspede</button>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Hóspede</label>
            <select
              className="w-full border rounded-lg px-3 py-2"
              value={guestId ?? ''}
              onChange={(e) => setGuestId(parseInt(e.target.value))}
            >
              <option value="" disabled>Selecione</option>
              {guests.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Quarto (opcional)</label>
            <select
              className="w-full border rounded-lg px-3 py-2"
              value={roomId ?? ''}
              onChange={(e) => {
                const val = e.target.value ? parseInt(e.target.value) : null;
                setRoomId(val);
                if (val) {
                  const r = rooms.find((x) => x.id === val);
                  if (r) setDailyRate(String(r.price_per_night ?? ''));
                }
              }}
            >
              <option value="">Sem quarto definido</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.number} - {r.type} (capacidade {r.max_capacity})
                </option>
              ))}
            </select>
          </div>

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
            <label className="block text-sm font-medium text-slate-600 mb-1">Diária (R$)</label>
            <input
              type="number"
              step="0.01"
              className="w-full border rounded-lg px-3 py-2"
              value={dailyRate}
              onChange={(e) => setDailyRate(e.target.value)}
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
            Criar Reserva
          </button>
          <button
            type="button"
            onClick={goToSummary}
            className="bg-slate-800 text-white px-5 py-2 rounded-lg shadow-md hover:bg-slate-900 transition font-semibold"
            title="Ver resumo antes de confirmar"
          >
            Resumo
          </button>
          <button
            type="button"
            onClick={handleCheckIn}
            disabled={!createdBookingId || !roomId}
            className={`px-5 py-2 rounded-lg shadow-md font-semibold transition ${
              createdBookingId && roomId
                ? 'bg-green-600 text-white hover:bg-green-700'
                : 'bg-slate-200 text-slate-500 cursor-not-allowed'
            }`}
            title="Confirma check-in para a reserva criada"
          >
            Check-in
          </button>
        </div>
      </form>
    </div>
  );
}
