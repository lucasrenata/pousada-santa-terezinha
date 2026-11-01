import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../services/api';
import { 
  Search, User, Calendar, MapPin, CreditCard, Hourglass, Upload, 
  CheckCircle2, Copy, Lock, AlertCircle, Coins, Phone, Mail, Plus, Trash2, Globe 
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { useToast } from '../hooks/use-toast';

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
  const { toast } = useToast();
  
  // Controle de Abas / Passos do Fluxo
  const [step, setStep] = useState<'booking' | 'payment'>('booking');
  
  // Informações do Estabelecimento
  const [tenantName, setTenantName] = useState('Nossa Pousada');
  const [tenantInfo, setTenantInfo] = useState<any>(null);

  // Estados dos Quartos e Datas
  const [rooms, setRooms] = useState<Room[]>([]);
  const [roomId, setRoomId] = useState<string | null>(null);
  const [checkInDate, setCheckInDate] = useState<string>('');
  const [checkInTime, setCheckInTime] = useState<string>('');
  const [checkOutDate, setCheckOutDate] = useState<string>('');
  const [checkOutTime, setCheckOutTime] = useState<string>('');
  const [defaultCheckInTime, setDefaultCheckInTime] = useState('14:00');
  const [defaultCheckOutTime, setDefaultCheckOutTime] = useState('12:00');
  const [dailyRate, setDailyRate] = useState<string>('');
  const [mode, setMode] = useState<BookingMode>('normal');
  const [totalGuests, setTotalGuests] = useState<number>(1);
  const [notes, setNotes] = useState<string>('');
  const [companions, setCompanions] = useState<Companion[]>([]);
  const [newCompanion, setNewCompanion] = useState<Companion>({ name: '', age: 0 });

  // Dados do Hóspede
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

  // Busca/Lookup de Cliente
  const [searchQuery, setSearchQuery] = useState('');
  const [searchStatus, setSearchStatus] = useState<'idle' | 'searching' | 'found' | 'not_found'>('idle');

  // Controle de Criação de Reserva e Overlay de Ampulheta
  const [creatingBooking, setCreatingBooking] = useState(false);
  const [createdBooking, setCreatedBooking] = useState<{
    id: number;
    totalAmount: number;
    depositAmount: number;
  } | null>(null);

  // Configurações de Pagamento do Tenant
  const [pixConfig, setPixConfig] = useState<any>(null);
  
  // Controle de Upload de Comprovante PIX
  const [uploadingReceipt, setUploadingReceipt] = useState(false);
  const [receiptFile, setReceiptFile] = useState<File | null>(null);
  const [receiptUploaded, setReceiptUploaded] = useState(false);

  // Controle de Pagamento MP
  const [payingCard, setPayingCard] = useState(false);

  // Alertas Globais
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Funções de Utilitários
  function onlyDigits(s: string) {
    return s.replace(/\D/g, '');
  }
  function formatDateBR(dateStr: string) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    return dateStr;
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
    const remaining = r.remaining_capacity !== undefined ? r.remaining_capacity : r.max_capacity;
    return totalGuests > remaining;
  }
  const datesValid = Boolean(checkInDate && checkInTime && checkOutDate && checkOutTime);

  // Efeito para carregar dados do estabelecimento (Tenant)
  useEffect(() => {
    async function loadTenantData() {
      if (!tenant_id) return;
      try {
        const [tenantResp, settingsResp] = await Promise.all([
          api.get(`/settings/public/tenant/${tenant_id}`),
          api.get(`/settings/public/${tenant_id}`)
        ]);
        if (tenantResp.data) {
          setTenantInfo(tenantResp.data);
          setTenantName(tenantResp.data.name || 'Nossa Pousada');
        }
        if (settingsResp.data) {
          const settings = settingsResp.data;
          const ci = settings.find((s: any) => s.key === 'check_in_time')?.value || '14:00';
          const co = settings.find((s: any) => s.key === 'check_out_time')?.value || '12:00';
          setDefaultCheckInTime(ci);
          setDefaultCheckOutTime(co);
        }
      } catch (err) {
        console.error("Erro ao carregar dados do tenant:", err);
      }
    }
    loadTenantData();
  }, [tenant_id]);

  // Efeito para carregar quartos disponíveis iniciais
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

  // Atualiza disponibilidade dos quartos quando datas/acompanhantes mudam
  const refreshAvailableRooms = useCallback(async () => {
    try {
      if (!checkInDate || !checkInTime || !checkOutDate || !checkOutTime) {
        setRooms([]);
        return;
      }
      const start = new Date(`${checkInDate}T${checkInTime}`).toISOString();
      const end = new Date(`${checkOutDate}T${checkOutTime}`).toISOString();
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
      // mantém lista atual em caso de erro
    }
  }, [checkInDate, checkInTime, checkOutDate, checkOutTime, roomId, mode, companions, totalGuests, tenant_id]);

  useEffect(() => {
    refreshAvailableRooms();
  }, [refreshAvailableRooms]);

  useEffect(() => {
    if (mode === 'normal') {
      setTotalGuests(1 + companions.length);
    }
  }, [mode, companions]);
  
  // Buscar CEP automaticamente
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

  // Função para buscar cadastro por CPF ou Nome
  async function handleSearchGuest(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearchStatus('searching');
    setError(null);
    try {
      const res = await api.get(`/guests/public/lookup?document=${searchQuery}&tenant_id=${tenant_id || 1}`);
      if (res.data) {
        setGuestName(res.data.name || '');
        setGuestEmail(res.data.email || '');
        setGuestPhone(res.data.phone ? formatPhone(res.data.phone) : '');
        setGuestDocument(res.data.document ? formatCPF(res.data.document) : '');
        setGuestBirthDate(res.data.birth_date || '');
        setGuestProfession(res.data.profession || '');
        setAddressZip(res.data.address_zip ? formatCEP(res.data.address_zip) : '');
        setAddressStreet(res.data.address_street || '');
        setAddressNumber(res.data.address_number || '');
        setAddressNeighborhood(res.data.address_neighborhood || '');
        setAddressCity(res.data.address_city || '');
        setAddressState(res.data.address_state || '');
        setSearchStatus('found');
        toast({ title: "Cadastro localizado!", description: "Os dados do hóspede foram preenchidos automaticamente." });
      }
    } catch (err) {
      setSearchStatus('not_found');
      toast({ 
        title: "Não localizado", 
        description: "Preencha todos os campos do formulário para realizar o cadastro.",
        variant: "destructive"
      });
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

  // Ação Única: Criar Reserva
  async function handleCreateBooking(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setError(null);

    try {
      if (!guestName || !guestEmail || !guestPhone || !guestDocument || !guestBirthDate || !guestProfession || !addressZip || !addressStreet || !addressNumber || !addressNeighborhood || !addressCity || !addressState) {
        throw new Error('Por favor, preencha todos os dados do hóspede.');
      }
      if (!isEmailValid(guestEmail)) {
        throw new Error('E-mail informado é inválido.');
      }
      const cpfDigits = onlyDigits(guestDocument);
      if (cpfDigits.length < 9) {
        throw new Error('CPF/Documento inválido.');
      }
      const phoneDigits = onlyDigits(guestPhone);
      if (phoneDigits.length < 10) {
        throw new Error('Telefone inválido.');
      }
      const cepDigits = onlyDigits(addressZip);
      if (cepDigits.length !== 8) {
        throw new Error('CEP informado é inválido.');
      }
      if (!checkInDate || !checkInTime || !checkOutDate || !checkOutTime) {
        throw new Error('Por favor, defina o período de Check-in e Check-out.');
      }
      if (!roomId) {
        throw new Error('Por favor, selecione um quarto disponível.');
      }
      if (!dailyRate || isNaN(parseFloat(dailyRate))) {
        throw new Error('Diária inválida.');
      }
      if (roomId && capacityExceeded()) {
        const r = rooms.find((x) => x.id === roomId);
        const rem = r?.remaining_capacity !== undefined ? r.remaining_capacity : r?.max_capacity ?? 0;
        throw new Error(`Capacidade do quarto excedida. Máximo de vagas disponíveis: ${rem} pessoas.`);
      }

      setCreatingBooking(true);

      const payload = {
        guest: {
          name: guestName,
          email: guestEmail,
          phone: guestPhone,
          document: guestDocument,
          birth_date: guestBirthDate,
          profession: guestProfession,
          address_zip: addressZip,
          address_street: addressStreet,
          address_number: addressNumber,
          address_neighborhood: addressNeighborhood,
          address_city: addressCity,
          address_state: addressState,
        },
        room_id: roomId ?? null,
        check_in_date: new Date(`${checkInDate}T${checkInTime}`).toISOString(),
        check_out_date: new Date(`${checkOutDate}T${checkOutTime}`).toISOString(),
        check_in_time: checkInTime,
        check_out_time: checkOutTime,
        mode,
        total_guests: totalGuests,
        daily_rate: parseFloat(dailyRate),
        notes: notes || null,
        companions,
        tenant_id: parseInt(tenant_id || "1")
      };

      const res = await api.post('/bookings/public', payload);
      const bId = res.data?.booking_id;
      const tAmt = res.data?.total_amount;
      const dAmt = res.data?.deposit_amount;

      setCreatedBooking({
        id: bId,
        totalAmount: tAmt,
        depositAmount: dAmt
      });

      // Mudar para etapa de pagamento
      setStep('payment');
      toast({ title: "Reserva criada com sucesso!", description: "Selecione o método de pagamento do sinal." });
    } catch (err: any) {
      const anyErr = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = anyErr.response?.data?.detail ?? anyErr.message ?? 'Erro ao criar a sua reserva.';
      setError(msg);
    } finally {
      setCreatingBooking(false);
    }
  }

  // Carrega chaves PIX/MP públicas na etapa de pagamento
  useEffect(() => {
    if (step === 'payment' && tenant_id) {
      api.get(`/payments/public/config/${tenant_id}`)
        .then((res) => {
          setPixConfig(res.data);
        })
        .catch((err) => {
          console.error("Erro ao obter dados de pagamento:", err);
        });
    }
  }, [step, tenant_id]);

  // Ação de upload de comprovante de PIX
  async function handleUploadReceipt(e: React.FormEvent) {
    e.preventDefault();
    if (!receiptFile || !createdBooking) return;
    setUploadingReceipt(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', receiptFile);
      const t_id = tenant_id || '1';
      await api.post(`/bookings/${createdBooking.id}/receipt?tenant_id=${t_id}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      setReceiptUploaded(true);
      toast({ title: "Comprovante enviado!", description: "Seu pagamento foi enviado para análise." });
    } catch (err: any) {
      setError('Erro ao enviar o arquivo do comprovante. Tente novamente.');
    } finally {
      setUploadingReceipt(false);
    }
  }

  // Ação de pagar com Cartão via Mercado Pago
  async function handlePayCard() {
    if (!createdBooking) return;
    setPayingCard(true);
    setError(null);
    try {
      const t_id = tenant_id || "1";
      const payRes = await api.post(`/payments/public/${createdBooking.id}/card?tenant_id=${t_id}`);
      const url = payRes.data?.sandbox_init_point || payRes.data?.init_point;
      if (!url) {
        setError('Não foi possível gerar o link de pagamento do Mercado Pago.');
        return;
      }
      window.open(url, '_blank');
      toast({ title: "Mercado Pago Iniciado!", description: "Abriremos a guia de pagamento em uma nova aba." });
    } catch (err: any) {
      setError('Erro ao processar pagamento via cartão.');
    } finally {
      setPayingCard(false);
    }
  }

  const selectedRoomType = rooms.find((r) => r.id === roomId)?.type || 'Quarto Selecionado';

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      
      {/* OVERLAY DE AMPULHETA (CRIANDO RESERVA) */}
      {creatingBooking && (
        <div className="fixed inset-0 bg-slate-900/70 backdrop-blur-md z-50 flex flex-col items-center justify-center text-white animate-in fade-in duration-300">
          <div className="bg-slate-800/90 p-8 rounded-3xl border border-slate-700 flex flex-col items-center gap-6 max-w-sm text-center shadow-2xl animate-in zoom-in duration-300">
            <Hourglass className="w-16 h-16 text-blue-500 animate-spin" />
            <div>
              <h3 className="text-xl font-bold tracking-wide">Criando sua reserva...</h3>
              <p className="text-sm text-slate-400 mt-2 leading-relaxed">
                Por favor, aguarde alguns instantes enquanto processamos seus dados e preparamos a sua acomodação.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* CABEÇALHO DA POUSADA */}
      <div className="bg-gradient-to-r from-blue-600 via-indigo-600 to-violet-600 rounded-3xl p-6 sm:p-8 text-white shadow-lg relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.15),transparent)] pointer-events-none" />
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">{tenantName}</h1>
        {tenantInfo?.address && (
          <p className="text-indigo-100/80 text-xs sm:text-sm mt-1 flex items-center gap-1.5">
            <MapPin className="w-4 h-4 shrink-0" /> {tenantInfo.address}
          </p>
        )}
        <p className="text-indigo-100/95 mt-3 text-xs sm:text-sm max-w-2xl leading-relaxed">
          Garanta já a sua hospedagem. Preencha as informações abaixo e prossiga para a tela de pagamento de sinal para confirmar a sua reserva.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 rounded-2xl border border-red-200 p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
          <span className="text-sm font-medium">{error}</span>
        </div>
      )}

      {message && (
        <div className="bg-green-50 text-green-700 rounded-2xl border border-green-200 p-4 flex items-start gap-3 animate-in fade-in duration-300">
          <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
          <span className="text-sm font-medium">{message}</span>
        </div>
      )}

      {/* PASSO 1: DADOS E CADASTRO */}
      {step === 'booking' && (
        <div className="space-y-6">
          
          {/* PESQUISA DE CADASTRO EXISTENTE */}
          <Card className="shadow-md border-slate-200/80 overflow-hidden bg-slate-50/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Search className="w-4.5 h-4.5 text-blue-600" /> Consultar Cadastro Existente
              </CardTitle>
              <CardDescription>Insira seu CPF ou Nome Completo para carregar seus dados automaticamente.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSearchGuest} className="flex gap-2">
                <div className="relative flex-1">
                  <Input 
                    type="text"
                    placeholder="Digite CPF ou Nome Completo"
                    className="w-full pl-10 bg-white"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  <Search className="absolute left-3 top-3 w-4 h-4 text-slate-400" />
                </div>
                <Button 
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 text-white font-semibold"
                  disabled={searchStatus === 'searching'}
                >
                  {searchStatus === 'searching' ? 'Buscando...' : 'Buscar'}
                </Button>
              </form>

              {searchStatus === 'found' && (
                <div className="flex items-center gap-2 p-3 mt-3 bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-100 text-xs font-semibold animate-in fade-in duration-300">
                  <CheckCircle2 className="w-4.5 h-4.5 text-emerald-600 shrink-0" />
                  <span>Cadastro encontrado! Seus dados foram preenchidos automaticamente abaixo.</span>
                </div>
              )}

              {searchStatus === 'not_found' && (
                <div className="flex items-center gap-2 p-3 mt-3 bg-amber-50 text-amber-700 rounded-xl border border-amber-100 text-xs font-semibold animate-in fade-in duration-300">
                  <AlertCircle className="w-4.5 h-4.5 text-amber-600 shrink-0" />
                  <span>Cadastro não encontrado. Por favor, preencha o formulário abaixo para realizar seu cadastro.</span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* FORMULÁRIO DE CADASTRO E DADOS DA RESERVA */}
          <form onSubmit={handleCreateBooking} className="space-y-6">
            
            {/* DADOS DO HÓSPEDE */}
            <Card className="shadow-md border-slate-200">
              <CardHeader className="pb-3 border-b border-slate-100">
                <CardTitle className="text-lg flex items-center gap-2">
                  <User className="w-5 h-5 text-indigo-600" /> Dados Pessoais
                </CardTitle>
                <CardDescription>Preencha os campos obrigatórios para o seu registro na pousada.</CardDescription>
              </CardHeader>
              <CardContent className="pt-6 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Nome Completo</label>
                    <Input 
                      placeholder="Nome completo do hóspede" 
                      value={guestName} 
                      onChange={(e) => setGuestName(e.target.value)} 
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">E-mail</label>
                    <Input 
                      type="email" 
                      placeholder="seu@email.com" 
                      value={guestEmail} 
                      onChange={(e) => setGuestEmail(e.target.value)} 
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Celular (WhatsApp)</label>
                    <Input 
                      placeholder="(00) 00000-0000" 
                      value={guestPhone} 
                      onChange={(e) => setGuestPhone(formatPhone(e.target.value))} 
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Documento (CPF ou RG)</label>
                    <Input 
                      placeholder="Apenas números ou formatado" 
                      value={guestDocument} 
                      onChange={(e) => setGuestDocument(formatCPF(e.target.value))} 
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Data de Nascimento</label>
                    <Input 
                      type="date" 
                      value={guestBirthDate} 
                      onChange={(e) => setGuestBirthDate(e.target.value)} 
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Profissão</label>
                    <Input 
                      placeholder="Sua profissão" 
                      value={guestProfession} 
                      onChange={(e) => setGuestProfession(e.target.value)} 
                    />
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-100">
                  <h4 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-1.5">
                    <MapPin className="w-4.5 h-4.5 text-indigo-500" /> Endereço Residencial
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="space-y-1.5 col-span-2 sm:col-span-1">
                      <label className="text-xs font-bold text-slate-600 uppercase">CEP</label>
                      <div className="relative">
                        <Input 
                          placeholder="00000-000" 
                          value={addressZip} 
                          onChange={(e) => setAddressZip(formatCEP(e.target.value))} 
                        />
                        {cepLoading && <span className="absolute right-2.5 top-2.5 text-xs text-slate-400">...</span>}
                      </div>
                    </div>
                    <div className="space-y-1.5 col-span-2 sm:col-span-2">
                      <label className="text-xs font-bold text-slate-600 uppercase">Rua/Avenida</label>
                      <Input 
                        value={addressStreet} 
                        onChange={(e) => setAddressStreet(e.target.value)} 
                      />
                    </div>
                    <div className="space-y-1.5 col-span-1">
                      <label className="text-xs font-bold text-slate-600 uppercase">Número</label>
                      <Input 
                        placeholder="Nº" 
                        value={addressNumber} 
                        onChange={(e) => setAddressNumber(e.target.value)} 
                      />
                    </div>
                    <div className="space-y-1.5 col-span-1">
                      <label className="text-xs font-bold text-slate-600 uppercase">Bairro</label>
                      <Input 
                        value={addressNeighborhood} 
                        onChange={(e) => setAddressNeighborhood(e.target.value)} 
                      />
                    </div>
                    <div className="space-y-1.5 col-span-2">
                      <label className="text-xs font-bold text-slate-600 uppercase">Cidade</label>
                      <Input 
                        value={addressCity} 
                        onChange={(e) => setAddressCity(e.target.value)} 
                      />
                    </div>
                    <div className="space-y-1.5 col-span-1">
                      <label className="text-xs font-bold text-slate-600 uppercase">UF</label>
                      <Input 
                        maxLength={2} 
                        value={addressState} 
                        onChange={(e) => setAddressState(e.target.value)} 
                      />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* DADOS DA RESERVA */}
            <Card className="shadow-md border-slate-200">
              <CardHeader className="pb-3 border-b border-slate-100">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Calendar className="w-5 h-5 text-indigo-600" /> Período e Acomodação
                </CardTitle>
                <CardDescription>Defina as datas da estadia e escolha sua suíte ou quarto.</CardDescription>
              </CardHeader>
              <CardContent className="pt-6 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* CHECK-IN */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Data de Entrada (Check-in)</label>
                    <Input
                      type="date"
                      value={checkInDate}
                      onChange={(e) => {
                        const val = e.target.value;
                        setCheckInDate(val);
                        if (val && !checkInTime) {
                          setCheckInTime(defaultCheckInTime);
                        }
                      }}
                    />
                    <p className="text-xs text-slate-500">Selecione o dia do início da sua hospedagem.</p>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Horário de Entrada (Check-in)</label>
                    <Input
                      type="time"
                      value={checkInTime}
                      onChange={(e) => setCheckInTime(e.target.value)}
                    />
                    <p className="text-xs text-slate-500">Horário padrão de entrada: {defaultCheckInTime}.</p>
                  </div>

                  {/* CHECK-OUT */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Data de Saída (Check-out)</label>
                    <Input
                      type="date"
                      value={checkOutDate}
                      onChange={(e) => {
                        const val = e.target.value;
                        setCheckOutDate(val);
                        if (val && !checkOutTime) {
                          setCheckOutTime(defaultCheckOutTime);
                        }
                      }}
                    />
                    <p className="text-xs text-slate-500">Selecione o dia de término da sua hospedagem.</p>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Horário de Saída (Check-out)</label>
                    <Input
                      type="time"
                      value={checkOutTime}
                      onChange={(e) => setCheckOutTime(e.target.value)}
                    />
                    <p className="text-xs text-slate-500 font-medium text-amber-600">Horário padrão de saída: {defaultCheckOutTime}. Saídas após este horário poderão implicar na cobrança de uma diária adicional.</p>
                  </div>

                  {/* MODELO DE RESERVA */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Modelo de Reserva</label>
                    <select
                      className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-950"
                      value={mode}
                      onChange={(e) => setMode(e.target.value as BookingMode)}
                    >
                      <option value="normal">Normal (Família/Individual)</option>
                      <option value="caravana">Caravana (Grupo grande)</option>
                    </select>
                    <p className="text-xs text-slate-500">Selecione 'Normal' para individual/família, ou 'Caravana' para caravanas/grupos grandes.</p>
                  </div>

                  {/* TOTAL DE HÓSPEDES */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Total de Hóspedes</label>
                    <Input
                      type="number"
                      min={1}
                      value={totalGuests}
                      onChange={(e) => setTotalGuests(parseInt(e.target.value) || 1)}
                      readOnly={mode === 'normal'}
                      className={mode === 'normal' ? 'bg-slate-50 cursor-not-allowed' : ''}
                    />
                    <p className="text-xs text-slate-500">
                      {mode === 'normal' 
                        ? 'Definido automaticamente com base nos acompanhantes cadastrados abaixo.'
                        : 'Quantidade total de pessoas na caravana.'
                      }
                    </p>
                  </div>

                  {/* PEDIDOS ESPECIAIS / OBSERVAÇÕES */}
                  <div className="sm:col-span-2 space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Pedidos Especiais / Observações</label>
                    <textarea
                      placeholder="Ex: Cama de solteiro extra, restrições alimentares, andar térreo..."
                      className="flex min-h-[80px] w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                    <p className="text-xs text-slate-500">Qualquer necessidade especial ou preferência pode ser detalhada aqui.</p>
                  </div>
                </div>

                {/* ACOMPANHANTES */}
                {mode === 'normal' && (
                  <div className="pt-4 border-t border-slate-100 space-y-3">
                    <h4 className="text-sm font-bold text-slate-700">Acompanhantes da Viagem</h4>
                    <p className="text-xs text-slate-500">Adicione as pessoas que estarão no mesmo quarto com você.</p>
                    <div className="flex gap-2">
                      <Input
                        placeholder="Nome do acompanhante"
                        value={newCompanion.name}
                        onChange={(e) => setNewCompanion((c) => ({ ...c, name: e.target.value }))}
                        className="flex-1"
                      />
                      <Input
                        type="number"
                        placeholder="Idade"
                        value={newCompanion.age || ''}
                        onChange={(e) => setNewCompanion((c) => ({ ...c, age: parseInt(e.target.value) || 0 }))}
                        className="w-24"
                      />
                      <Button
                        type="button"
                        onClick={addCompanion}
                        className="bg-slate-800 hover:bg-slate-900 text-white font-semibold"
                      >
                        <Plus className="w-4 h-4 mr-1" /> Adicionar
                      </Button>
                    </div>

                    {companions.length > 0 && (
                      <ul className="space-y-2 mt-2">
                        {companions.map((c, idx) => (
                          <li key={`${c.name}-${idx}`} className="flex items-center justify-between bg-slate-50 px-4 py-2 rounded-xl border border-slate-100 text-sm">
                            <span className="text-slate-700 font-medium">{c.name} — <span className="text-xs text-slate-500">{c.age} anos</span></span>
                            <Button
                              type="button"
                              variant="ghost"
                              className="text-red-500 hover:text-red-700 hover:bg-red-50 p-1.5 h-auto rounded-lg"
                              onClick={() => removeCompanion(idx)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {/* ESCOLHA O QUARTO (MANDATORIAMENTE O ÚLTIMO PASSO) */}
                <div className="pt-4 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Escolha o Quarto</label>
                    {!datesValid ? (
                      <div className="rounded-xl border bg-blue-50/50 text-blue-700 p-3 text-xs leading-relaxed">
                        Por favor, selecione as datas de entrada/saída e a quantidade de hóspedes primeiro para que possamos listar os quartos disponíveis.
                      </div>
                    ) : (
                      <>
                        <select
                          className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-950"
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
                          <option value="">Selecione um Quarto</option>
                          {rooms.map((r) => {
                            const isShared = r.remaining_capacity !== undefined && r.remaining_capacity < r.max_capacity;
                            const spots = r.remaining_capacity ?? r.max_capacity;
                            return (
                              <option key={r.id} value={r.id}>
                                Quarto {r.id} - {r.type} (Diária R$ {r.price_per_night} | {isShared ? `COMPARTILHADO: restam apenas ${spots} vagas` : `Privativo: ${r.max_capacity} vagas`})
                              </option>
                            );
                          })}
                        </select>
                        <p className="text-xs text-slate-500">Escolha a acomodação disponível para o período selecionado.</p>
                      </>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-600 uppercase">Valor da Diária (R$)</label>
                    <Input
                      type="number"
                      value={dailyRate}
                      readOnly
                      disabled
                      placeholder="Valor definido pelo quarto"
                      className="bg-slate-50 text-slate-700"
                    />
                    <p className="text-xs text-slate-500">Valor diário associado ao quarto escolhido.</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Button
              type="submit"
              className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-base py-6 rounded-2xl shadow-lg transition-all font-bold flex items-center justify-center gap-2"
            >
              Criar Reserva
            </Button>
          </form>
        </div>
      )}

      {/* PASSO 2: TELA DE PAGAMENTO */}
      {step === 'payment' && createdBooking && (
        <div className="space-y-6 animate-in fade-in duration-300">
          
          {/* CONFIRMAÇÃO E RESUMO DA RESERVA */}
          <Card className="border-emerald-200 bg-emerald-50/20 shadow-md">
            <CardHeader className="pb-3 border-b border-emerald-100">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-100 rounded-full">
                  <CheckCircle2 className="w-6 h-6 text-emerald-600" />
                </div>
                <div>
                  <CardTitle className="text-emerald-800 text-xl font-bold">Reserva Pré-Registrada!</CardTitle>
                  <CardDescription className="text-emerald-700/80">Código de controle da solicitação: #{createdBooking.id}</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm text-slate-700">
                <div className="space-y-2">
                  <p><strong>Titular</strong>: {guestName}</p>
                  <p><strong>Acomodação</strong>: {selectedRoomType} (Quarto {roomId})</p>
                  <p><strong>Nº Hóspedes</strong>: {totalGuests} {totalGuests === 1 ? 'pessoa' : 'pessoas'}</p>
                  <p><strong>Check-in</strong>: {formatDateBR(checkInDate)} às {checkInTime}</p>
                  <p><strong>Check-out</strong>: {formatDateBR(checkOutDate)} às {checkOutTime}</p>
                </div>
                <div className="space-y-2 sm:border-l sm:pl-6 border-slate-200">
                  <p><strong>Valor Total da Estadia</strong>: R$ {createdBooking.totalAmount.toFixed(2)}</p>
                  <p className="text-blue-700 font-bold text-base bg-blue-50 p-2.5 rounded-xl border border-blue-100">
                    Sinal Necessário (Garantia): R$ {createdBooking.depositAmount.toFixed(2)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* COLUNAS DE OPÇÕES DE PAGAMENTO */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* OPÇÃO 1: PIX MANUAL */}
            <Card className="shadow-md border-slate-200 relative overflow-hidden flex flex-col justify-between">
              <div>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Coins className="w-5 h-5 text-amber-500" /> Opção 1: Depósito/PIX Manual
                  </CardTitle>
                  <CardDescription>Transfira o sinal para a chave PIX e envie o comprovante de pagamento.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {pixConfig?.manual_pix_key ? (
                    <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100 space-y-2">
                      <p className="text-xs font-bold text-slate-500 uppercase">Chave PIX da Pousada</p>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-sm text-slate-800 break-all select-all font-bold">{pixConfig.manual_pix_key}</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            navigator.clipboard.writeText(pixConfig.manual_pix_key);
                            toast({ title: "Chave PIX Copiada!" });
                          }}
                          className="text-slate-500 hover:text-slate-700 bg-white shadow-sm border border-slate-100 shrink-0"
                        >
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-slate-500 text-sm italic">Obtendo chave PIX do estabelecimento...</div>
                  )}

                  {!receiptUploaded ? (
                    <form onSubmit={handleUploadReceipt} className="space-y-3 pt-2">
                      <div className="space-y-1.5">
                        <label className="text-xs font-bold text-slate-600 uppercase">Anexar Comprovante (Imagem ou PDF)</label>
                        <div className="relative border-2 border-dashed border-slate-200 rounded-2xl p-4 text-center hover:border-blue-400 transition-all cursor-pointer">
                          <input
                            type="file"
                            accept="image/*,application/pdf"
                            onChange={(e) => setReceiptFile(e.target.files?.[0] || null)}
                            className="absolute inset-0 opacity-0 cursor-pointer"
                          />
                          <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                          <span className="text-sm font-semibold text-slate-600 block">
                            {receiptFile ? receiptFile.name : 'Escolher arquivo do comprovante'}
                          </span>
                        </div>
                      </div>

                      <Button
                        type="submit"
                        className="w-full bg-slate-900 hover:bg-slate-800 text-white font-bold"
                        disabled={!receiptFile || uploadingReceipt}
                      >
                        {uploadingReceipt ? 'Enviando...' : 'Enviar Comprovante PIX'}
                      </Button>
                    </form>
                  ) : (
                    <div className="p-4 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-2xl flex flex-col items-center gap-2 text-center animate-in fade-in duration-300">
                      <CheckCircle2 className="w-10 h-10 text-emerald-600" />
                      <h4 className="font-bold">Comprovante Recebido!</h4>
                      <p className="text-xs text-emerald-700">
                        O financeiro analisará o seu comprovante. Sua estadia está pré-confirmada e avisaremos por e-mail assim que compensado.
                      </p>
                    </div>
                  )}
                </CardContent>
              </div>
            </Card>

            {/* OPÇÃO 2: CARTÃO MERCADO PAGO */}
            <Card className="shadow-md border-slate-200 flex flex-col justify-between">
              <div>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <CreditCard className="w-5 h-5 text-blue-500" /> Opção 2: Pagar com Cartão
                  </CardTitle>
                  <CardDescription>Pague o sinal usando cartão de crédito via Mercado Pago de forma instantânea.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-4 bg-blue-50 text-blue-800 border border-blue-100 rounded-2xl text-xs leading-relaxed flex gap-2">
                    <Lock className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
                    <span>Ambiente criptografado e 100% seguro. O pagamento é processado imediatamente pelo Mercado Pago e sua reserva é confirmada de forma automatizada.</span>
                  </div>

                  <Button
                    onClick={handlePayCard}
                    disabled={payingCard}
                    className="w-full bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-700 hover:to-green-700 text-white text-base py-6 rounded-2xl shadow-md transition-all font-bold flex items-center justify-center gap-2"
                  >
                    {payingCard ? 'Iniciando Cartão...' : <><CreditCard className="w-5 h-5" /> Pagar com Cartão</>}
                  </Button>
                </CardContent>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
