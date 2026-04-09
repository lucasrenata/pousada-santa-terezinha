import { useEffect, useState } from 'react';
import api from '../services/api';
import type { AxiosError } from 'axios';
import { BedDouble, X, CheckCircle, Plus, ShoppingCart, Trash2, Edit } from 'lucide-react';
import RoomModal from '../components/RoomModal';
import { ReservationForm } from '../components/ReservationForm';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import type { Reservation } from '../hooks/useReservations';
import { useNavigate, useLocation } from 'react-router-dom';

type RoomStatus = 'disponivel' | 'ocupado' | 'limpeza' | 'manutencao';

interface Room {
  id: string; // O ID agora é o número do quarto
  type: string;
  price_per_night: number;
  status: RoomStatus;
  floor?: number;
  max_capacity: number;
  maintenance_note?: string | null;
}

interface Product {
  id: number;
  name: string;
  price: number;
  stock_quantity: number;
  barcode?: string | null;
}

export default function Rooms() {
  const navigate = useNavigate();
  const location = useLocation();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRoom, setEditingRoom] = useState<Room | null>(null);
  const [detailsRoom, setDetailsRoom] = useState<Room | null>(null);
  const [selectedRoomForCons, setSelectedRoomForCons] = useState<string | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [activeBooking, setActiveBooking] = useState<{
    id: number;
    guest_name: string;
    check_in_date: string;
    check_out_date: string;
  } | null>(null);
  const [bookingSearchTerm, setBookingSearchTerm] = useState<string>('');
  const [bookingResults, setBookingResults] = useState<Array<{
    id: number;
    room_number?: string | null;
    guest_name: string;
    status: 'pendente' | 'confirmado' | 'ativo' | 'concluido' | 'cancelado';
    total_amount: number;
    check_in_date: string;
    check_out_date: string;
  }>>([]);
  const [maintenanceOpen, setMaintenanceOpen] = useState(false);
  const [maintenanceNote, setMaintenanceNote] = useState('');
  const [barcodeSearch, setBarcodeSearch] = useState('');
  const [isResModalOpen, setIsResModalOpen] = useState(false);
  const [editingReservation, setEditingReservation] = useState<Reservation | null>(null);
  const [currentConsumptions, setCurrentConsumptions] = useState<any[]>([]);

  async function loadRooms() {
    try {
      setLoading(true);
      const response = await api.get('/rooms/');
      setRooms(response.data);
      setError(null);
    } catch {
      setError('Erro ao carregar quartos');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRooms();
  }, []);
  
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const rid = params.get('roomId');
    if (rid && rooms.length > 0) {
      const r = rooms.find((x) => x.id === rid);
      if (r) setDetailsRoom(r);
    }
  }, [location.search, rooms]);
  
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setDetailsRoom(null);
        setSelectedRoomForCons(null);
      }
    }
    if (detailsRoom) {
      window.addEventListener('keydown', onKeyDown);
    }
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [detailsRoom]);

  useEffect(() => {
    async function fetchActive() {
      if (detailsRoom && detailsRoom.status === 'ocupado') {
        try {
          const res = await api.get(`/bookings/active/${detailsRoom.id}`);
          setActiveBooking({
            id: res.data.id,
            guest_name: res.data.guest_name,
            check_in_date: res.data.check_in_date,
            check_out_date: res.data.check_out_date,
          });
        } catch {
          setActiveBooking(null);
        }
      } else {
        setActiveBooking(null);
      }
    }
    fetchActive();
  }, [detailsRoom]);

  async function handleClean(roomId: string) {
    try {
      await api.post(`/rooms/${roomId}/clean`);
      await loadRooms();
      alert('Quarto marcado como limpo');
    } catch {
      alert('Falha ao marcar como limpo');
    }
  }

  async function handleCheckout(roomId: string) {
    try {
      const summary = await api.get(`/bookings/summary/${roomId}`);
      setCheckoutInfo({
        roomId,
        bookingId: summary.data.booking_id,
        dailyTotal: summary.data.daily_total,
        consumptionTotal: summary.data.consumption_total,
        grandTotal: summary.data.grand_total,
      });
      setCheckoutOpen(true);
    } catch (err) {
      const axErr = err as AxiosError<{ detail?: string }>;
      const msg = axErr.response?.data?.detail ?? 'Falha ao preparar check-out';
      alert(msg);
    }
  }

  async function handleDelete(roomId: string) {
    try {
      if (!confirm('Excluir este quarto? Esta ação não pode ser desfeita.')) return;
      await api.delete(`/rooms/${roomId}`);
      await loadRooms();
      alert('Quarto excluído');
    } catch (err) {
      const axErr = err as AxiosError<{ detail?: string }>;
      const msg = axErr.response?.data?.detail ?? 'Falha ao excluir quarto';
      alert(msg);
    }
  }

  async function loadConsumptions(roomId: string) {
    try {
      const res = await api.get(`/bookings/summary/${roomId}`);
      setCurrentConsumptions(res.data.consumptions || []);
    } catch {
      setCurrentConsumptions([]);
    }
  }

  async function openConsumption(roomId: string) {
    try {
      setSelectedRoomForCons(roomId);
      await loadConsumptions(roomId);
      const res = await api.get('/products/', { params: { only_active: true } });
      setProducts(res.data);
      setSelectedProductId(null);
      setQuantity(1);
      setBarcodeSearch('');
    } catch {
      alert('Falha ao carregar produtos');
    }
  }

  function handleBarcodeChange(val: string) {
    setBarcodeSearch(val);
    const found = products.find(p => p.barcode === val);
    if (found) {
      setSelectedProductId(found.id);
      setBarcodeSearch('');
      // foca quantidade ou dá um aviso visual? 
      // por enquanto só seleciona para manter simples e robusto
    }
  }

  async function submitConsumption() {
    try {
      if (!selectedRoomForCons || !selectedProductId || quantity < 1) {
        alert('Selecione produto e informe quantidade válida');
        return;
      }
      await api.post('/products/consumption', {
        room_id: selectedRoomForCons,
        product_id: selectedProductId,
        quantity,
      });
      // alert('Consumo registrado');
      await loadConsumptions(selectedRoomForCons);
      setSelectedProductId(null);
      setQuantity(1);
      setBarcodeSearch('');
      await loadRooms();
    } catch (err) {
      const axErr = err as AxiosError<{ detail?: string }>;
      const msg = axErr.response?.data?.detail ?? 'Erro ao registrar consumo';
      alert(msg);
    }
  }

  async function searchBookings() {
    try {
      if (!bookingSearchTerm.trim()) {
        setBookingResults([]);
        return;
      }
      const res = await api.get('/bookings/');
      const term = bookingSearchTerm.trim().toLowerCase();
      const list = res.data as Array<{
        id: number;
        room_number?: string | null;
        guest_name: string;
        status: 'pendente' | 'confirmado' | 'ativo' | 'concluido' | 'cancelado';
        total_amount: number;
        check_in_date: string;
        check_out_date: string;
      }>;
      const filtered = list.filter((b) => {
        const guest = (b.guest_name ?? '').toLowerCase();
        const room = (b.room_number ?? '').toLowerCase();
        return guest.includes(term) || room.includes(term);
      });
      setBookingResults(filtered);
    } catch {
      alert('Falha ao buscar reservas');
    }
  }

  

  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [checkoutInfo, setCheckoutInfo] = useState<{
    roomId: string;
    bookingId: number;
    dailyTotal: number;
    consumptionTotal: number;
    grandTotal: number;
  } | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<'pix' | 'credito' | 'debito' | 'dinheiro'>('pix');

  async function confirmCheckout() {
    try {
      if (!checkoutInfo) return;
      await api.post(`/bookings/checkout/${checkoutInfo.roomId}`, { payment_method: paymentMethod });
      alert('Check-out realizado');
      setCheckoutOpen(false);
      setCheckoutInfo(null);
      await loadRooms();
    } catch (err) {
      const axErr = err as AxiosError<{ detail?: string }>;
      const msg = axErr.response?.data?.detail ?? 'Falha ao realizar check-out';
      alert(msg);
    }
  }

  function getStatusBadge(status: RoomStatus) {
    const base = 'px-2 py-1 rounded-full text-xs font-medium';
    switch (status) {
      case 'disponivel': return <span className={`${base} bg-green-100 text-green-700`}>Disponível</span>;
      case 'ocupado': return <span className={`${base} bg-red-100 text-red-700`}>Ocupado</span>;
      case 'limpeza': return <span className={`${base} bg-yellow-100 text-yellow-700`}>Limpeza</span>;
      case 'manutencao': return <span className={`${base} bg-stone-200 text-stone-800`}>Manutenção</span>;
      default: return <span className={`${base} bg-slate-100 text-slate-700`}>{status}</span>;
    }
  }
  
  function getCardBorder(status: RoomStatus) {
    switch (status) {
      case 'disponivel': return 'border-2 border-green-500';
      case 'ocupado': return 'border-2 border-red-500';
      case 'limpeza': return 'border-2 border-yellow-500';
      case 'manutencao': return 'border-2 border-stone-600';
      default: return 'border';
    }
  }

  async function submitMaintenance(roomId: string) {
    try {
      await api.post(`/rooms/${roomId}/maintenance`, null, { params: { note: maintenanceNote } });
      alert('Quarto marcado como manutenção');
      setMaintenanceOpen(false);
      setMaintenanceNote('');
      await loadRooms();
      const updated = rooms.find(r => r.id === roomId);
      if (updated) setDetailsRoom(updated);
    } catch {
      alert('Falha ao marcar manutenção');
    }
  }

  async function releaseMaintenance(roomId: string) {
    const ok = confirm('Tem certeza que deseja liberar este quarto?');
    if (!ok) return;
    await handleClean(roomId);
  }

  async function handleEditClick() {
    if (!detailsRoom) return;
    
    // Se estiver ocupado ou com reserva confirmada, tentamos editar a reserva
    if (activeBooking) {
      try {
        const res = await api.get(`/bookings/${activeBooking.id}`);
        setEditingReservation(res.data);
        setIsResModalOpen(true);
      } catch {
        alert('Falha ao carregar detalhes da reserva');
      }
    } else {
      // Caso contrário, edita o quarto
      setEditingRoom(detailsRoom);
      setIsModalOpen(true);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Gestão de Quartos</h2>
          <p className="text-slate-500">Administre ocupação, limpeza e operações de check-out.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center bg-white px-3 py-2 rounded-lg shadow-sm border border-slate-200 w-56">
            <input
              value={bookingSearchTerm}
              onChange={(e) => setBookingSearchTerm(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  searchBookings();
                }
              }}
              placeholder="Buscar reserva..."
              className="outline-none w-full text-slate-700 bg-transparent"
            />
            <button onClick={searchBookings} className="ml-2 text-slate-600">Buscar</button>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center justify-center bg-blue-600 text-white px-4 py-2 rounded-lg shadow-md hover:bg-blue-700 transition font-semibold"
          >
            <Plus size={18} className="mr-2" /> Novo Quarto
          </button>
        </div>
      </div>

      {loading && (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 text-center">
          Carregando...
        </div>
      )}

      {error && (
        <div className="bg-red-50 text-red-700 rounded-lg border border-red-200 p-4 mb-4">
          {error}
        </div>
      )}

      {!loading && rooms.length === 0 && (
        <div className="text-center py-20 bg-white rounded-2xl shadow-sm border border-slate-100">
          <div className="bg-slate-50 p-4 rounded-full inline-block mb-4">
            <BedDouble size={48} className="text-slate-400" />
          </div>
          <h3 className="text-lg font-semibold text-slate-800">Nenhum quarto cadastrado</h3>
          <p className="text-slate-500 mb-6 max-w-md mx-auto">
            Cadastre novos quartos para iniciar o controle de ocupação.
          </p>
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center bg-white px-3 py-2 rounded-lg shadow-sm border border-slate-200 w-full sm:w-64">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar número..."
            className="outline-none w-full text-slate-700 bg-transparent"
          />
        </div>
      </div>

      {bookingResults.length > 0 && (
        <div className="mb-4 bg-white rounded-2xl shadow-sm border border-slate-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-slate-700">Resultados da reserva</p>
            <button
              onClick={() => { setBookingResults([]); setBookingSearchTerm(''); }}
              className="px-3 py-1 rounded-lg border bg-white text-slate-700"
            >
              Fechar
            </button>
          </div>
          <div className="space-y-2">
            {bookingResults.map((b) => (
              <div key={b.id} className="border rounded-lg p-3">
                <p className="font-semibold text-slate-800">
                  {b.guest_name} {b.room_number ? `— Quarto ${b.room_number}` : ''}
                </p>
                <p className="text-slate-600 text-sm">
                  {new Date(b.check_in_date).toLocaleString('pt-BR')} — {new Date(b.check_out_date).toLocaleString('pt-BR')}
                </p>
                <p className="text-slate-600 text-sm">Status: {b.status}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ maxHeight: '70vh', overflowY: 'auto' }} className="grid grid-cols-1 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-2">
        {rooms.filter(r => (search ? String(r.id).includes(search) : true)).map((room) => (
          <div
            key={room.id}
            onClick={() => setDetailsRoom(room)}
            className={`bg-white rounded-md shadow-sm p-2 flex flex-col gap-1 cursor-pointer hover:shadow-md transition overflow-hidden ${getCardBorder(room.status)}`}
          >
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <div className="bg-slate-100 p-1.5 rounded-md">
                  <BedDouble size={16} className="text-slate-600" />
                </div>
                <div>
                  <p className="text-[11px] text-slate-500">Quarto</p>
                  <h3 className="text-sm font-semibold text-slate-800">{room.id}</h3>
                </div>
              </div>
              <div className="flex items-center gap-2">{getStatusBadge(room.status)}</div>
            </div>

          </div>
        ))}
      </div>

      <RoomModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingRoom(null);
        }}
        initialData={editingRoom}
        onSuccess={() => {
          loadRooms();
        }}
      />

      {detailsRoom && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => {
            setDetailsRoom(null);
            setSelectedRoomForCons(null);
          }}
        >
          <div
            className="bg-white rounded-2xl w-full max-w-2xl p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                <div className="bg-slate-100 p-2 rounded-lg">
                  <BedDouble size={22} className="text-slate-600" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Quarto</p>
                  <h3 className="text-xl font-bold text-slate-800">{detailsRoom.id}</h3>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {getStatusBadge(detailsRoom.status)}
                {detailsRoom.status === 'disponivel' && (
                  <button
                    onClick={() => {
                      navigate(`/bookings/new?roomId=${detailsRoom.id}`);
                      setDetailsRoom(null);
                    }}
                    className="px-3 py-2 rounded-lg bg-blue-600 text-white"
                    title="Criar reserva para este quarto"
                  >
                    Reservar
                  </button>
                )}
                <button
                  onClick={() => { setMaintenanceOpen(true); }}
                  className="px-3 py-2 rounded-lg bg-stone-700 text-white"
                  title="Marcar manutenção com observação"
                >
                  Manutenção
                </button>
                <button
                  onClick={handleEditClick}
                  className="px-3 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition"
                  title={activeBooking ? "Editar reserva do hóspede" : "Editar dados do quarto"}
                >
                  <Edit size={18} />
                </button>
                <button
                  onClick={() => handleDelete(detailsRoom.id)}
                  disabled={detailsRoom.status === 'ocupado'}
                  className={`p-2 rounded-lg border ${
                    detailsRoom.status !== 'ocupado'
                      ? 'text-red-600 border-red-300 hover:bg-red-50'
                      : 'text-slate-400 border-slate-200 cursor-not-allowed'
                  }`}
                  title={detailsRoom.status === 'ocupado' ? 'Não é possível excluir quarto ocupado' : 'Excluir quarto'}
                >
                  <Trash2 size={16} />
                </button>
                <button
                  onClick={() => {
                    setDetailsRoom(null);
                    setSelectedRoomForCons(null);
                  }}
                  className="px-3 py-2 rounded-lg border bg-white"
                >
                  Fechar
                </button>
              </div>
            </div>

            {activeBooking && (
              <div className="mb-4 rounded-lg border p-3 bg-slate-50">
                <p className="text-sm text-slate-600">
                  Hóspede: <span className="font-medium text-slate-800">{activeBooking.guest_name}</span>
                </p>
                <p className="text-sm text-slate-600">
                  Período: {new Date(activeBooking.check_in_date).toLocaleString('pt-BR')} — {new Date(activeBooking.check_out_date).toLocaleString('pt-BR')}
                </p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 text-sm text-slate-700 mb-4">
              <div>
                <p className="text-slate-500">Tipo</p>
                <p className="font-medium">{detailsRoom.type}</p>
              </div>
              <div>
                <p className="text-slate-500">Capacidade</p>
                <p className="font-medium">{detailsRoom.max_capacity}</p>
              </div>
              <div>
                <p className="text-slate-500">Diária</p>
                <p className="font-medium">R$ {detailsRoom.price_per_night?.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-slate-500">Andar</p>
                <p className="font-medium">{detailsRoom.floor ?? 1}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 mb-4" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={() => handleCheckout(detailsRoom.id)}
                disabled={detailsRoom.status !== 'ocupado'}
                className={`flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors border ${
                  detailsRoom.status === 'ocupado'
                    ? 'bg-yellow-600 text-white border-yellow-700 hover:bg-yellow-700'
                    : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                }`}
                title={detailsRoom.status === 'ocupado' ? 'Realizar check-out' : 'Disponível apenas quando ocupado'}
              >
                <X size={16} className="mr-2" /> Check-out
              </button>

              <button
                onClick={() => handleClean(detailsRoom.id)}
                disabled={detailsRoom.status !== 'limpeza'}
                className={`flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors border ${
                  detailsRoom.status === 'limpeza'
                    ? 'bg-blue-600 text-white border-blue-700 hover:bg-blue-700'
                    : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                }`}
                title={detailsRoom.status === 'limpeza' ? 'Marcar como limpo' : 'Disponível após check-out'}
              >
                <CheckCircle size={16} className="mr-2" /> Limpo
              </button>

              <button
                onClick={() => releaseMaintenance(detailsRoom.id)}
                disabled={detailsRoom.status !== 'manutencao'}
                className={`flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors border ${
                  detailsRoom.status === 'manutencao'
                    ? 'bg-green-600 text-white border-green-700 hover:bg-green-700'
                    : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                }`}
                title={detailsRoom.status === 'manutencao' ? 'Liberar quarto para uso' : 'Disponível apenas quando em manutenção'}
              >
                <CheckCircle size={16} className="mr-2" /> Liberar
              </button>

              <button
                onClick={() => openConsumption(detailsRoom.id)}
                disabled={detailsRoom.status !== 'ocupado'}
                className={`flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors border ${
                  detailsRoom.status === 'ocupado'
                    ? 'bg-green-600 text-white border-green-700 hover:bg-green-700'
                    : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                }`}
                title={detailsRoom.status === 'ocupado' ? 'Registrar consumo' : 'Disponível apenas quando ocupado'}
              >
                <ShoppingCart size={16} className="mr-2" /> Consumo
              </button>
            </div>

            {detailsRoom.status === 'manutencao' && detailsRoom && (
              <div className="mb-4 rounded-lg border p-3 bg-stone-50">
                <p className="text-sm text-slate-700 font-medium">Observação de manutenção</p>
                <p className="text-sm text-slate-600">{detailsRoom.maintenance_note || 'Sem observação'}</p>
              </div>
            )}

            {maintenanceOpen && (
              <div className="border-t pt-3">
                <p className="text-sm font-medium text-slate-700 mb-2">Informar manutenção</p>
                <textarea
                  className="w-full border rounded-lg px-3 py-2"
                  rows={3}
                  value={maintenanceNote}
                  onChange={(e) => setMaintenanceNote(e.target.value)}
                  placeholder="Ex.: chuveiro queimado, frigobar não gela..."
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => submitMaintenance(detailsRoom.id)}
                    disabled={!maintenanceNote.trim()}
                    className={`px-4 py-2 rounded-lg ${maintenanceNote.trim() ? 'bg-stone-700 text-white' : 'bg-slate-100 text-slate-400 cursor-not-allowed'}`}
                  >
                    Salvar manutenção
                  </button>
                  <button
                    onClick={() => { setMaintenanceOpen(false); setMaintenanceNote(''); }}
                    className="px-4 py-2 rounded-lg border bg-white"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}

            {checkoutOpen && checkoutInfo && (
              <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setCheckoutOpen(false)}>
                <div className="bg-white rounded-2xl w-full max-w-md p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
                  <div className="mb-4">
                    <h3 className="text-lg font-bold text-slate-800">Check-out</h3>
                    <p className="text-sm text-slate-600">Resumo de valores</p>
                  </div>
                  <div className="space-y-2 text-sm">
                    <p className="flex justify-between"><span>Diárias</span><span className="font-semibold">R$ {checkoutInfo.dailyTotal.toFixed(2)}</span></p>
                    <p className="flex justify-between"><span>Consumo</span><span className="font-semibold">R$ {checkoutInfo.consumptionTotal.toFixed(2)}</span></p>
                    <hr />
                    <p className="flex justify-between text-base"><span>Total</span><span className="font-bold">R$ {checkoutInfo.grandTotal.toFixed(2)}</span></p>
                  </div>
                  <div className="mt-4">
                    <label className="block text-xs font-medium text-slate-500 mb-1">Forma de pagamento</label>
                    <select
                      value={paymentMethod}
                      onChange={(e) => setPaymentMethod(e.target.value as typeof paymentMethod)}
                      className="w-full px-3 py-2 border rounded-lg bg-white"
                    >
                      <option value="pix">PIX</option>
                      <option value="debito">Débito</option>
                      <option value="credito">Crédito</option>
                      <option value="dinheiro">Dinheiro</option>
                    </select>
                  </div>
                  <div className="flex gap-2 mt-4">
                    <button onClick={confirmCheckout} className="px-3 py-2 rounded-lg bg-blue-600 text-white">Pagar e Check-out</button>
                    <button onClick={() => setCheckoutOpen(false)} className="px-3 py-2 rounded-lg border bg-white">Cancelar</button>
                  </div>
                </div>
              </div>
            )}
           

            {selectedRoomForCons === detailsRoom.id && (
              <div className="border-t pt-4 mt-2">
                <div className="flex items-center justify-between mb-3 ">
                  <p className="text-sm font-bold text-slate-800 uppercase tracking-wider">Consumos Atuais</p>
                  <span className="text-[10px] text-slate-400 font-bold bg-slate-100 px-2 py-0.5 rounded">Check-in Ativo</span>
                </div>

                {/* Lista de Consumos Existentes */}
                {currentConsumptions.length > 0 ? (
                  <div className="mb-4 max-h-40 overflow-y-auto border border-slate-100 rounded-xl bg-white shadow-inner">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-slate-50 border-b text-slate-500 font-bold uppercase text-[9px]">
                        <tr>
                          <th className="px-3 py-2 text-left">Produto</th>
                          <th className="px-3 py-2 text-center">Qtd</th>
                          <th className="px-3 py-2 text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {currentConsumptions.map((c, i) => (
                          <tr key={i} className="hover:bg-blue-50/30 transition-colors">
                            <td className="px-3 py-2 font-medium text-slate-700">{c.product_name}</td>
                            <td className="px-3 py-2 text-center text-slate-600 font-bold">{c.quantity}</td>
                            <td className="px-3 py-2 text-right text-blue-600 font-bold">R$ {c.total.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="mb-4 p-4 border border-dashed rounded-xl text-center text-slate-400 text-xs italic">
                    Nenhum consumo registrado ainda para este quarto.
                  </div>
                )}

                <p className="text-sm font-bold text-slate-800 mb-3 uppercase tracking-wider">Novo Lançamento</p>
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
                  <div className="sm:col-span-3">
                    <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1">Cód. Barras</label>
                    <input
                      placeholder="Escanear..."
                      className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                      value={barcodeSearch}
                      onChange={(e) => handleBarcodeChange(e.target.value)}
                      autoFocus
                    />
                  </div>
                  
                  <div className="sm:col-span-5">
                    <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1">Produto</label>
                    <select
                      className="border rounded-lg px-3 py-2 w-full bg-white focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                      value={selectedProductId ?? ''}
                      onChange={(e) => setSelectedProductId(parseInt(e.target.value))}
                    >
                      <option value="" disabled>Selecione o produto</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} — R$ {p.price?.toFixed(2)}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="sm:col-span-2">
                    <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1">Qtd</label>
                    <input
                      type="number"
                      min={1}
                      className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                      value={quantity}
                      onChange={(e) => setQuantity(parseInt(e.target.value) || 1)}
                    />
                  </div>

                  <div className="sm:col-span-2 flex items-end gap-2">
                    <button
                      onClick={submitConsumption}
                      className="flex-1 bg-green-600 text-white font-bold h-[38px] rounded-lg hover:bg-green-700 transition shadow-sm"
                    >
                      Lançar
                    </button>
                    <button
                      onClick={() => setSelectedRoomForCons(null)}
                      className="flex-1 bg-white text-slate-400 font-bold h-[38px] rounded-lg border hover:bg-slate-50 transition"
                    >
                      <X size={16} className="mx-auto" />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal de Edição de Reserva */}
      <Dialog open={isResModalOpen} onOpenChange={setIsResModalOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-slate-50 sm:rounded-3xl p-6 sm:p-10 shadow-2xl border-none">
          <DialogHeader>
            <DialogTitle className="text-2xl font-black text-slate-800">Editar Reserva</DialogTitle>
          </DialogHeader>
          <ReservationForm
            reservation={editingReservation}
            onSuccess={() => {
              setIsResModalOpen(false);
              loadRooms();
              // Se tiver um detailsRoom aberto, talvez queira dar um "refresh" nele
              if (detailsRoom) {
                const updated = rooms.find(r => r.id === detailsRoom.id);
                if (updated) setDetailsRoom(updated);
              }
            }}
            onCancel={() => setIsResModalOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
