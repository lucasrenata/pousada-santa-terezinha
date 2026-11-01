import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  User, Check, Search, Calendar, BedDouble, ChevronRight, ChevronLeft, 
  FileText, UploadCloud, CreditCard, Phone, Mail, MapPin, Loader2, 
  Plus, Trash2, Copy, Sparkles, AlertCircle 
} from 'lucide-react';
import api from '../services/api';
import { toast } from 'sonner';

type Step = 'cpf_lookup' | 'registration' | 'booking' | 'confirmation';
type BookingMode = 'normal' | 'caravana';

interface Room {
  id: string;
  type: string;
  price_per_night: number;
  max_capacity: number;
}

interface Companion {
  name: string;
  age: number;
}

export default function GuestChatPage() {
  const { tenant_id } = useParams();
  const navigate = useNavigate();

  // Wizard state
  const [step, setStep] = useState<Step>('cpf_lookup');
  const [loading, setLoading] = useState(false);
  const [pousadaName, setPousadaName] = useState('Estabelecimento');
  const [pousadaPhone, setPousadaPhone] = useState('(11) 99999-9999');
  const [pousadaEmail, setPousadaEmail] = useState('contato@pousada.com.br');
  const [pixKey, setPixKey] = useState('Chave CNPJ / Celular da Pousada');
  const [defaultCheckInTime, setDefaultCheckInTime] = useState('14:00');
  const [defaultCheckOutTime, setDefaultCheckOutTime] = useState('12:00');

  // Step 1: CPF
  const [cpf, setCpf] = useState('');
  const [cpfError, setCpfError] = useState('');
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // Step 2: Guest Registration Info
  const [guestName, setGuestName] = useState('');
  const [guestEmail, setGuestEmail] = useState('');
  const [guestPhone, setGuestPhone] = useState('');
  const [guestBirthDate, setGuestBirthDate] = useState('');
  const [guestProfession, setGuestProfession] = useState('');
  const [addressZip, setAddressZip] = useState('');
  const [addressStreet, setAddressStreet] = useState('');
  const [addressNumber, setAddressNumber] = useState('');
  const [addressNeighborhood, setAddressNeighborhood] = useState('');
  const [addressCity, setAddressCity] = useState('');
  const [addressState, setAddressState] = useState('');
  const [cepLoading, setCepLoading] = useState(false);

  // Step 3: Booking Info
  const [checkInDate, setCheckInDate] = useState('');
  const [checkOutDate, setCheckOutDate] = useState('');
  const [mode, setMode] = useState<BookingMode>('normal');
  const [totalGuests, setTotalGuests] = useState(1);
  const [roomId, setRoomId] = useState<string | null>(null);
  const [dailyRate, setDailyRate] = useState('');
  const [notes, setNotes] = useState('');
  const [rooms, setRooms] = useState<Room[]>([]);
  const [roomsLoading, setRoomsLoading] = useState(false);

  // Companions
  const [companions, setCompanions] = useState<Companion[]>([]);
  const [newCompName, setNewCompName] = useState('');
  const [newCompAge, setNewCompAge] = useState('');

  // Step 4: Success / Confirmation
  const [createdBookingId, setCreatedBookingId] = useState<number | null>(null);
  const [totalAmount, setTotalAmount] = useState<number>(0);
  const [uploadingReceipt, setUploadingReceipt] = useState(false);
  const [receiptUploaded, setReceiptUploaded] = useState(false);

  // Format Helper functions
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

  // Load Settings on Start
  useEffect(() => {
    async function loadSettings() {
      try {
        const tenantResp = await api.get(`/settings/public/tenant/${tenant_id}`);
        if (tenantResp.data.name) setPousadaName(tenantResp.data.name);

        const response = await api.get(`/settings/public/${tenant_id}`);
        
        // Telefone, email e pix
        const phoneSet = response.data.find((s: any) => s.key === 'pousada_phone' || s.key === 'phone');
        if (phoneSet) setPousadaPhone(phoneSet.value);

        const emailSet = response.data.find((s: any) => s.key === 'pousada_email' || s.key === 'email');
        if (emailSet) setPousadaEmail(emailSet.value);

        const pixSet = response.data.find((s: any) => s.key === 'pix_key' || s.key === 'pix');
        if (pixSet) setPixKey(pixSet.value);

        // Horários padrão de check-in e check-out (Regras de Negócio)
        const ciTimeSet = response.data.find((s: any) => s.key === 'check_in_time');
        if (ciTimeSet) setDefaultCheckInTime(ciTimeSet.value);

        const coTimeSet = response.data.find((s: any) => s.key === 'check_out_time');
        if (coTimeSet) setDefaultCheckOutTime(coTimeSet.value);

      } catch (err) {
        console.error("Erro ao carregar configurações públicas", err);
      }
    }
    loadSettings();
  }, [tenant_id]);

  // Helper: constrói string datetime-local (YYYY-MM-DDTHH:mm) a partir de uma data e um horário "HH:mm"
  const buildDateTimeLocal = (dateStr: string, timeHHmm: string): string => {
    if (!dateStr) return '';
    // dateStr pode ser apenas "YYYY-MM-DD" ou já ser um datetime-local completo
    const datePart = dateStr.length > 10 ? dateStr.substring(0, 10) : dateStr;
    return `${datePart}T${timeHHmm}`;
  };

  // Lookup Guest by CPF
  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanCPF = onlyDigits(cpf);
    if (cleanCPF.length !== 11) {
      setCpfError('Digite um CPF válido com 11 dígitos');
      return;
    }
    setCpfError('');
    setLoading(true);

    try {
      const res = await api.get(`/guests/public/lookup?document=${cleanCPF}&tenant_id=${tenant_id}`);
      const g = res.data;
      if (g) {
        setGuestName(g.name || '');
        setGuestEmail(g.email || '');
        setGuestPhone(g.phone ? formatPhone(g.phone) : '');
        setGuestBirthDate(g.birth_date || '');
        setGuestProfession(g.profession || '');
        setAddressZip(g.address_zip ? formatCEP(g.address_zip) : '');
        setAddressStreet(g.address_street || '');
        setAddressNumber(g.address_number || '');
        setAddressNeighborhood(g.address_neighborhood || '');
        setAddressCity(g.address_city || '');
        setAddressState(g.address_state || '');
        
        toast.success(`Bem-vindo de volta, ${g.name}! Seus dados foram preenchidos.`);
      }
      setStep('registration');
    } catch (err: any) {
      if (err.response?.status === 404) {
        toast.info('CPF não localizado. Por favor, preencha a ficha cadastral.');
        setStep('registration');
      } else {
        toast.error('Erro ao consultar CPF. Tente novamente.');
      }
    } finally {
      setLoading(false);
    }
  };

  // Fetch ViaCEP for CEP Autocomplete
  const fetchCep = useCallback(async () => {
    const d = onlyDigits(addressZip);
    if (d.length !== 8) return;
    try {
      setCepLoading(true);
      const res = await fetch(`https://viacep.com.br/ws/${d}/json/`);
      const data = await res.json();
      if (data && !data.erro) {
        setAddressStreet(data.logradouro || '');
        setAddressNeighborhood(data.bairro || '');
        setAddressCity(data.localidade || '');
        setAddressState(data.uf || '');
      } else {
        toast.error('CEP não encontrado');
      }
    } catch {
      toast.error('Erro ao buscar endereço pelo CEP');
    } finally {
      setCepLoading(false);
    }
  }, [addressZip]);

  useEffect(() => {
    fetchCep();
  }, [fetchCep]);

  // Load available rooms when dates or guests change
  const refreshAvailableRooms = useCallback(async () => {
    if (!checkInDate || !checkOutDate) {
      setRooms([]);
      return;
    }
    try {
      setRoomsLoading(true);
      const start = new Date(checkInDate).toISOString();
      const end = new Date(checkOutDate).toISOString();
      const guests = mode === 'normal' ? 1 + companions.length : totalGuests;
      const t_id = tenant_id || "1";
      
      const availRes = await api.get(
        `/bookings/availability/public?start=${start}&end=${end}&guests=${guests}&tenant_id=${t_id}`
      );
      const available: Room[] = availRes.data;
      setRooms(available);
      
      // Reset selected room if not available anymore
      if (roomId && !available.find((r) => r.id === roomId)) {
        setRoomId(null);
        setDailyRate('');
      }
    } catch {
      toast.error('Falha ao carregar quartos disponíveis para o período.');
    } finally {
      setRoomsLoading(false);
    }
  }, [checkInDate, checkOutDate, roomId, mode, companions, totalGuests, tenant_id]);

  useEffect(() => {
    refreshAvailableRooms();
  }, [refreshAvailableRooms]);

  // Sync total guests for normal mode
  useEffect(() => {
    if (mode === 'normal') {
      setTotalGuests(1 + companions.length);
    }
  }, [mode, companions]);

  const addCompanion = () => {
    if (!newCompName.trim()) {
      toast.error('Informe o nome do acompanhante');
      return;
    }
    const ageNum = parseInt(newCompAge);
    if (isNaN(ageNum) || ageNum < 0) {
      toast.error('Informe uma idade válida');
      return;
    }
    setCompanions((prev) => [...prev, { name: newCompName.trim(), age: ageNum }]);
    setNewCompName('');
    setNewCompAge('');
    toast.success('Acompanhante adicionado!');
  };

  const removeCompanion = (index: number) => {
    setCompanions((prev) => prev.filter((_, i) => i !== index));
  };

  const handleNextStepFromRegistration = () => {
    const newErrors: Record<string, string> = {};

    if (!guestName.trim()) {
      newErrors.guestName = 'Nome Completo é obrigatório.';
    }
    
    if (!guestEmail.trim()) {
      newErrors.guestEmail = 'E-mail é obrigatório.';
    } else if (!/\S+@\S+\.\S+/.test(guestEmail)) {
      newErrors.guestEmail = 'Digite um formato de e-mail válido (ex: seu@email.com).';
    }

    if (!guestPhone.trim()) {
      newErrors.guestPhone = 'Telefone/WhatsApp é obrigatório.';
    } else if (onlyDigits(guestPhone).length < 10) {
      newErrors.guestPhone = 'Digite um telefone válido com DDD (mínimo 10 dígitos).';
    }

    if (!addressZip.trim()) {
      newErrors.addressZip = 'CEP é obrigatório.';
    } else if (onlyDigits(addressZip).length !== 8) {
      newErrors.addressZip = 'O CEP deve conter exatamente 8 números.';
    }

    if (!addressStreet.trim()) {
      newErrors.addressStreet = 'Rua/Logradouro é obrigatório.';
    }

    if (!addressNumber.trim()) {
      newErrors.addressNumber = 'Número do endereço é obrigatório. Se não houver, digite "S/N".';
    }

    if (!addressCity.trim()) {
      newErrors.addressCity = 'Cidade é obrigatória.';
    }

    if (!addressState.trim()) {
      newErrors.addressState = 'Estado (UF) é obrigatório.';
    } else if (addressState.trim().length !== 2) {
      newErrors.addressState = 'Digite a sigla do estado com 2 letras (ex: SP).';
    }

    if (Object.keys(newErrors).length > 0) {
      setFormErrors(newErrors);
      toast.error('Existem campos obrigatórios em branco ou com formato incorreto. Por favor, verifique os campos marcados em vermelho.');
      return;
    }

    setFormErrors({});

    // Pré-preenche datas com a data de hoje e os horários padrão das Regras de Negócio
    const today = new Date().toISOString().substring(0, 10); // YYYY-MM-DD
    const tomorrow = new Date(Date.now() + 86400000).toISOString().substring(0, 10);
    if (!checkInDate) setCheckInDate(buildDateTimeLocal(today, defaultCheckInTime));
    if (!checkOutDate) setCheckOutDate(buildDateTimeLocal(tomorrow, defaultCheckOutTime));

    setStep('booking');
  };

  // Submit Booking
  const handleBookingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: Record<string, string> = {};

    if (!checkInDate) {
      newErrors.checkInDate = 'A data de Check-in é obrigatória.';
    }
    if (!checkOutDate) {
      newErrors.checkOutDate = 'A data de Check-out é obrigatória.';
    }
    if (checkInDate && checkOutDate) {
      const checkInTime = new Date(checkInDate).getTime();
      const checkOutTime = new Date(checkOutDate).getTime();
      if (checkOutTime <= checkInTime) {
        newErrors.checkOutDate = 'A data de Check-out deve ser posterior à data de Check-in.';
      }
    }
    if (!roomId) {
      newErrors.roomId = 'Você precisa selecionar um quarto disponível para o período.';
    }

    if (Object.keys(newErrors).length > 0) {
      setFormErrors(newErrors);
      toast.error('Não foi possível finalizar a reserva. Por favor, verifique os campos marcados em vermelho.');
      return;
    }

    setFormErrors({});
    setLoading(true);
    try {
      const payload = {
        guest: {
          name: guestName,
          email: guestEmail,
          phone: guestPhone,
          document: cpf,
          birth_date: guestBirthDate ? new Date(guestBirthDate) : null,
          profession: guestProfession || null,
          address_zip: addressZip,
          address_street: addressStreet,
          address_number: addressNumber,
          address_neighborhood: addressNeighborhood || null,
          address_city: addressCity,
          address_state: addressState,
        },
        room_id: roomId,
        check_in_date: new Date(checkInDate).toISOString(),
        check_out_date: new Date(checkOutDate).toISOString(),
        mode,
        total_guests: totalGuests,
        daily_rate: parseFloat(dailyRate),
        notes: notes || null,
        companions: mode === 'normal' ? companions.map(c => ({
          name: c.name,
          age: parseInt(String(c.age)) || 0
        })) : [],
        tenant_id: parseInt(tenant_id || "1")
      };

      const res = await api.post('/bookings/public', payload);
      const data = res.data;
      
      setCreatedBookingId(data.booking_id || data.id);
      
      // Use the correct calculated total amount returned from the backend if available
      if (typeof data.total_amount === 'number') {
        setTotalAmount(data.total_amount);
      } else {
        const days = Math.ceil((new Date(checkOutDate).getTime() - new Date(checkInDate).getTime()) / (1000 * 60 * 60 * 24)) || 1;
        setTotalAmount(days * parseFloat(dailyRate));
      }
      
      toast.success('Reserva solicitada com sucesso!');
      setStep('confirmation');
    } catch (err: any) {
      const msg = err.response?.data?.detail ?? 'Erro ao enviar a reserva. Verifique os dados.';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  // Upload Receipt
  const handleReceiptUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!createdBookingId) {
      toast.error('Nenhuma reserva ativa para anexar o comprovante.');
      return;
    }

    setUploadingReceipt(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      await api.post(`/bookings/${createdBookingId}/receipt?tenant_id=${tenant_id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setReceiptUploaded(true);
      toast.success('Comprovante enviado com sucesso!');
    } catch (err) {
      toast.error('Erro ao enviar comprovante de pagamento.');
    } finally {
      setUploadingReceipt(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col justify-between py-6 px-4 sm:px-6 font-sans">
      
      {/* Header */}
      <header className="max-w-4xl w-full mx-auto flex items-center justify-between mb-8 bg-white border border-slate-200/80 px-6 py-4 rounded-3xl shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-650 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <BedDouble className="text-white" size={20} />
          </div>
          <div>
            <h1 className="font-bold text-slate-800 tracking-tight text-base leading-tight">{pousadaName}</h1>
            <p className="text-[10px] font-black text-indigo-600 uppercase tracking-widest">Portal de Reservas</p>
          </div>
        </div>
        <div className="text-xs bg-indigo-50 text-indigo-700 font-bold px-3 py-1.5 rounded-full border border-indigo-100">
          Suporte Online
        </div>
      </header>

      {/* Main Card */}
      <main className="max-w-4xl w-full mx-auto flex-1 flex items-center justify-center">
        <div className="w-full bg-white rounded-[2rem] border border-slate-200/80 p-6 sm:p-10 shadow-xl shadow-slate-100 flex flex-col space-y-6">
          
          {/* Progress Indicators */}
          {step !== 'confirmation' && (
            <div className="flex items-center justify-between max-w-md mx-auto w-full pb-4">
              <div className="flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                  step === 'cpf_lookup' 
                    ? 'bg-indigo-600 text-white ring-4 ring-indigo-100 shadow-md' 
                    : 'bg-slate-100 text-slate-400 border border-slate-200'
                }`}>
                  1
                </div>
                <span className="text-[10px] font-bold mt-1 text-slate-650">CPF</span>
              </div>
              <div className="flex-1 h-0.5 bg-slate-200 mx-2"></div>
              <div className="flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                  step === 'registration' 
                    ? 'bg-indigo-600 text-white ring-4 ring-indigo-100 shadow-md' 
                    : 'bg-slate-100 text-slate-400 border border-slate-200'
                }`}>
                  2
                </div>
                <span className="text-[10px] font-bold mt-1 text-slate-655">Ficha</span>
              </div>
              <div className="flex-1 h-0.5 bg-slate-200 mx-2"></div>
              <div className="flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                  step === 'booking' 
                    ? 'bg-indigo-600 text-white ring-4 ring-indigo-100 shadow-md' 
                    : 'bg-slate-100 text-slate-400 border border-slate-200'
                }`}>
                  3
                </div>
                <span className="text-[10px] font-bold mt-1 text-slate-655">Reserva</span>
              </div>
            </div>
          )}

          {/* STEP 1: CPF LOOKUP */}
          {step === 'cpf_lookup' && (
            <form onSubmit={handleLookup} className="space-y-6 max-w-md mx-auto w-full py-6">
              <div className="text-center space-y-2">
                <h2 className="text-2xl font-extrabold text-slate-800 tracking-tight">Para começar, digite seu CPF</h2>
                <p className="text-sm text-slate-500">Se você já esteve conosco, buscaremos seus dados automaticamente.</p>
              </div>
              
              <div className="space-y-2">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-650">CPF ou Documento</label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 pl-4 flex items-center text-slate-400">
                    <User size={18} />
                  </span>
                  <input
                    type="text"
                    required
                    value={cpf}
                    onChange={(e) => setCpf(formatCPF(e.target.value))}
                    placeholder="000.000.000-00"
                    className="w-full bg-white border border-slate-350 rounded-2xl pl-12 pr-4 py-3.5 text-sm text-slate-850 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 font-semibold shadow-sm"
                  />
                </div>
                <p className="text-[11px] text-slate-500 font-medium mt-1 leading-relaxed">
                  Digite somente os números do seu CPF. Se você já tem cadastro na pousada, isso irá preencher seus dados automaticamente.
                </p>
                {cpfError && (
                  <p className="text-red-600 text-xs flex items-center gap-1.5 font-semibold mt-1">
                    <AlertCircle size={14} /> {cpfError}
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 active:scale-98 text-white py-3.5 px-4 rounded-2xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/10 transition-all disabled:opacity-50 text-base"
              >
                {loading ? <Loader2 className="animate-spin" size={18} /> : <Search size={18} />}
                Continuar
              </button>
            </form>
          )}

          {/* STEP 2: REGISTRATION FORM */}
          {step === 'registration' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-slate-800">Dados Cadastrais</h2>
                <p className="text-xs text-slate-500 mt-1">Precisamos desses dados para gerar sua ficha de hospedagem nacional (FNRH).</p>
              </div>

              {/* Error Summary Banner */}
              {Object.keys(formErrors).length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex gap-3 shadow-sm">
                  <AlertCircle className="text-red-600 shrink-0 mt-0.5" size={18} />
                  <div>
                    <p className="text-sm font-bold text-red-700 mb-1">Por favor, corrija os campos abaixo antes de continuar:</p>
                    <ul className="text-xs text-red-600 space-y-0.5 list-disc list-inside">
                      {Object.values(formErrors).map((msg, i) => (
                        <li key={i}>{msg}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Nome Completo *</label>
                  <input
                    type="text"
                    value={guestName}
                    onChange={(e) => setGuestName(e.target.value)}
                    placeholder="Ex: João da Silva"
                    className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                      formErrors.guestName 
                        ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500' 
                        : 'border-slate-350 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  />
                  {formErrors.guestName ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5 animate-fade-in">
                      <AlertCircle size={14} /> {formErrors.guestName}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">Digite seu nome completo, igual ao documento de identidade.</p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">E-mail *</label>
                  <input
                    type="email"
                    value={guestEmail}
                    onChange={(e) => setGuestEmail(e.target.value)}
                    placeholder="seu@email.com"
                    className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                      formErrors.guestEmail 
                        ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500' 
                        : 'border-slate-355 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  />
                  {formErrors.guestEmail ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5 animate-fade-in">
                      <AlertCircle size={14} /> {formErrors.guestEmail}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">Informe um e-mail válido para receber a confirmaão da sua reserva. Exemplo: seunome@email.com</p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Telefone / WhatsApp *</label>
                  <input
                    type="text"
                    value={guestPhone}
                    onChange={(e) => setGuestPhone(formatPhone(e.target.value))}
                    placeholder="(00) 90000-0000"
                    className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                      formErrors.guestPhone 
                        ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500' 
                        : 'border-slate-355 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  />
                  {formErrors.guestPhone ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5 animate-fade-in">
                      <AlertCircle size={14} /> {formErrors.guestPhone}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">Informe um número com DDD. De preferência, seu número de WhatsApp para contato rápido.</p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">CPF / RG</label>
                  <input
                    type="text"
                    disabled
                    value={cpf}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-500 cursor-not-allowed font-medium"
                  />
                  <p className="text-[11px] text-slate-550 mt-0.5">Documento usado na busca. Não pode ser alterado aqui.</p>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Data de Nascimento</label>
                  <input
                    type="date"
                    value={guestBirthDate}
                    onChange={(e) => setGuestBirthDate(e.target.value)}
                    className="w-full bg-white border border-slate-355 rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none focus:border-indigo-500 font-medium"
                  />
                  <p className="text-[11px] text-slate-550 mt-0.5">Selecione ou digite sua data de nascimento.</p>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Profissão</label>
                  <input
                    type="text"
                    value={guestProfession}
                    onChange={(e) => setGuestProfession(e.target.value)}
                    placeholder="Profissão"
                    className="w-full bg-white border border-slate-355 rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none focus:border-indigo-500 font-medium"
                  />
                  <p className="text-[11px] text-slate-550 mt-0.5">Informe sua profissão atual. Exemplo: Vendedor, Aposentado, Professor, Estudante.</p>
                </div>

                {/* Address */}
                <div className="md:col-span-2 border-t border-slate-200 pt-4 mt-2">
                  <h3 className="text-sm font-bold text-slate-850 flex items-center gap-1.5">
                    <MapPin className="text-indigo-600" size={16} /> Endereço Residencial
                  </h3>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase flex items-center justify-between">
                    <span>CEP *</span>
                    {cepLoading && <Loader2 className="animate-spin text-indigo-650" size={12} />}
                  </label>
                  <input
                    type="text"
                    value={addressZip}
                    onChange={(e) => setAddressZip(formatCEP(e.target.value))}
                    placeholder="00000-000"
                    className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                      formErrors.addressZip 
                        ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500' 
                        : 'border-slate-355 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  />
                  {formErrors.addressZip ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5 animate-fade-in">
                      <AlertCircle size={14} /> {formErrors.addressZip}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">Seu CEP com 8 dígitos. A busca preencherá o endereço automaticamente.</p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Rua / Logradouro *</label>
                  <input
                    type="text"
                    value={addressStreet}
                    onChange={(e) => setAddressStreet(e.target.value)}
                    placeholder="Ex: Avenida Paulista"
                    className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                      formErrors.addressStreet 
                        ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500' 
                        : 'border-slate-355 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  />
                  {formErrors.addressStreet ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5 animate-fade-in">
                      <AlertCircle size={14} /> {formErrors.addressStreet}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">Nome da rua, avenida, travessa ou praça onde você mora.</p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Número e Complemento *</label>
                  <input
                    type="text"
                    value={addressNumber}
                    onChange={(e) => setAddressNumber(e.target.value)}
                    placeholder="Ex: 123, apto 45"
                    className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                      formErrors.addressNumber 
                        ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500' 
                        : 'border-slate-355 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  />
                  {formErrors.addressNumber ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5 animate-fade-in">
                      <AlertCircle size={14} /> {formErrors.addressNumber}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">Número da sua residência e complemento (se houver, ex: apto 12, bloco B).</p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Bairro</label>
                  <input
                    type="text"
                    value={addressNeighborhood}
                    onChange={(e) => setAddressNeighborhood(e.target.value)}
                    placeholder="Nome do bairro"
                    className="w-full bg-white border border-slate-355 rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none focus:border-indigo-500 font-medium"
                  />
                  <p className="text-[11px] text-slate-550 mt-0.5">Bairro onde você mora.</p>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Cidade *</label>
                  <input
                    type="text"
                    value={addressCity}
                    onChange={(e) => setAddressCity(e.target.value)}
                    placeholder="Cidade"
                    className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                      formErrors.addressCity 
                        ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500' 
                        : 'border-slate-355 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  />
                  {formErrors.addressCity ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5 animate-fade-in">
                      <AlertCircle size={14} /> {formErrors.addressCity}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">Cidade onde você mora.</p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Estado *</label>
                  <input
                    type="text"
                    maxLength={2}
                    value={addressState}
                    onChange={(e) => setAddressState(e.target.value.toUpperCase())}
                    placeholder="Ex: SP"
                    className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                      formErrors.addressState 
                        ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500' 
                        : 'border-slate-355 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  />
                  {formErrors.addressState ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5 animate-fade-in">
                      <AlertCircle size={14} /> {formErrors.addressState}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">Sigla do estado. Exemplo: SP, RJ, MG, PR.</p>
                  )}
                </div>
              </div>

              <div className="flex justify-between items-center border-t border-slate-200 pt-6 mt-4">
                <button
                  type="button"
                  onClick={() => { setFormErrors({}); setStep('cpf_lookup'); }}
                  className="bg-slate-100 hover:bg-slate-200 active:scale-95 text-slate-650 font-bold py-2.5 px-5 rounded-xl text-sm flex items-center gap-1.5 transition-all border border-slate-250"
                >
                  <ChevronLeft size={16} /> Voltar
                </button>
                <button
                  type="button"
                  onClick={handleNextStepFromRegistration}
                  className="bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white font-bold py-2.5 px-6 rounded-xl text-sm flex items-center gap-1.5 transition-all shadow-md shadow-indigo-650/10"
                >
                  Avançar <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}

          {/* STEP 3: BOOKING FORM */}
          {step === 'booking' && (
            <form onSubmit={handleBookingSubmit} className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-slate-800">Configurar sua Reserva</h2>
                <p className="text-xs text-slate-500 mt-1">Informe o período pretendido para listarmos os quartos disponíveis.</p>
              </div>

              {/* Error Summary Banner */}
              {Object.keys(formErrors).length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex gap-3 shadow-sm">
                  <AlertCircle className="text-red-600 shrink-0 mt-0.5" size={18} />
                  <div>
                    <p className="text-sm font-bold text-red-700 mb-1">Atenção! Não foi possível finalizar a reserva:</p>
                    <ul className="text-xs text-red-600 space-y-0.5 list-disc list-inside">
                      {Object.values(formErrors).map((msg, i) => (
                        <li key={i}>{msg}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase flex items-center gap-1">
                    <Calendar size={14} className="text-indigo-650" /> Data de Check-in *
                  </label>
                  <input
                    type="datetime-local"
                    value={checkInDate}
                    onChange={(e) => {
                      const newVal = e.target.value; // YYYY-MM-DDTHH:mm
                      // Se o browser só trocou a data (preservando horario), aceitar normalmente.
                      // Garantimos que o horario padrao seja mantido quando a parte da data muda.
                      const datePart = newVal.substring(0, 10);
                      const timePart = newVal.length >= 16 ? newVal.substring(11, 16) : defaultCheckInTime;
                      setCheckInDate(`${datePart}T${timePart}`);
                      if (newVal) setFormErrors((prev) => { const n = {...prev}; delete n.checkInDate; return n; });
                    }}
                    className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                      formErrors.checkInDate 
                        ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500' 
                        : 'border-slate-355 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  />
                  {formErrors.checkInDate ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5 animate-fade-in">
                      <AlertCircle size={14} /> {formErrors.checkInDate}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">
                      Selecione a data de chegada. O horário padrão de entrada é às <strong>{defaultCheckInTime}</strong>.
                      Se antecipar o horário, poderá ser cobrada uma diária a mais.
                    </p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase flex items-center gap-1">
                    <Calendar size={14} className="text-indigo-650" /> Data de Check-out *
                  </label>
                  <input
                    type="datetime-local"
                    value={checkOutDate}
                    onChange={(e) => {
                      const newVal = e.target.value;
                      const datePart = newVal.substring(0, 10);
                      const timePart = newVal.length >= 16 ? newVal.substring(11, 16) : defaultCheckOutTime;
                      setCheckOutDate(`${datePart}T${timePart}`);
                      if (newVal) setFormErrors((prev) => { const n = {...prev}; delete n.checkOutDate; return n; });
                    }}
                    className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                      formErrors.checkOutDate 
                        ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500' 
                        : 'border-slate-355 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                    }`}
                  />
                  {formErrors.checkOutDate ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5 animate-fade-in">
                      <AlertCircle size={14} /> {formErrors.checkOutDate}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">
                      Selecione a data de saída. O horário padrão de saída é até às <strong>{defaultCheckOutTime}</strong>.
                      Se ultrapassar esse horário, uma diária extra será cobrada.
                    </p>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Modo de Reserva</label>
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value as BookingMode)}
                    className="w-full bg-white border border-slate-355 rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none focus:border-indigo-500 font-medium"
                  >
                    <option value="normal">Normal</option>
                    <option value="caravana">Caravana</option>
                  </select>
                  <p className="text-[11px] text-slate-550 mt-0.5">Escolha 'Normal' se vai cadastrar os acompanhantes um a um. Escolha 'Caravana' se quer apenas informar o total de pessoas.</p>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Total de Pessoas</label>
                  <input
                    type="number"
                    min={1}
                    disabled={mode === 'normal'}
                    value={totalGuests}
                    onChange={(e) => setTotalGuests(parseInt(e.target.value) || 1)}
                    className={`w-full border rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 font-medium ${
                      mode === 'normal' 
                        ? 'bg-slate-50 border-slate-200 text-slate-500 cursor-not-allowed' 
                        : 'bg-white border-slate-355 text-slate-800'
                    }`}
                  />
                  {mode === 'normal' ? (
                    <span className="text-[11px] text-slate-550">
                      Calculado automaticamente baseando-se nos acompanhantes (Titular + Acompanhantes).
                    </span>
                  ) : (
                    <span className="text-[11px] text-slate-550">
                      Informe o número total de pessoas que participarão desta reserva da caravana.
                    </span>
                  )}
                </div>

                {/* Quarto Selector */}
                <div className="md:col-span-2 space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Quarto Disponível *</label>
                  {!checkInDate || !checkOutDate ? (
                    <div className="bg-indigo-50 text-indigo-755 border border-indigo-100 p-3 rounded-xl text-xs font-semibold">
                      Selecione check-in e check-out acima para listar os quartos livres.
                    </div>
                  ) : roomsLoading ? (
                    <div className="flex items-center gap-2 p-3 text-xs text-slate-500 font-semibold bg-slate-50 rounded-xl border border-slate-200">
                      <Loader2 className="animate-spin text-indigo-600" size={14} /> Carregando quartos livres...
                    </div>
                  ) : rooms.length === 0 ? (
                    <div className="bg-red-50 text-red-700 border border-red-200 p-3 rounded-xl text-xs font-semibold flex items-center gap-2">
                      <AlertCircle size={14} className="shrink-0" /> Nenhum quarto disponível para o período selecionado. Tente alterar as datas.
                    </div>
                  ) : (
                    <select
                      value={roomId ?? ''}
                      onChange={(e) => {
                        const val = e.target.value || null;
                        setRoomId(val);
                        if (val) {
                          const r = rooms.find((x) => x.id === val);
                          if (r) setDailyRate(String(r.price_per_night ?? ''));
                          setFormErrors((prev) => { const n = {...prev}; delete n.roomId; return n; });
                        }
                      }}
                      className={`w-full bg-white border rounded-xl px-4 py-2.5 text-sm text-slate-800 focus:outline-none font-medium transition-all ${
                        formErrors.roomId
                          ? 'border-red-500 ring-2 ring-red-100 focus:border-red-500'
                          : 'border-slate-355 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                      }`}
                    >
                      <option value="">Selecione um quarto</option>
                      {rooms.map((r) => (
                        <option key={r.id} value={r.id}>
                          Quarto {r.id} — {r.type} (Diária: R$ {r.price_per_night} • Máx: {r.max_capacity} p.)
                        </option>
                      ))}
                    </select>
                  )}
                  {formErrors.roomId ? (
                    <p className="text-red-600 text-xs font-bold mt-1 flex items-center gap-1.5">
                      <AlertCircle size={14} /> {formErrors.roomId}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-550 mt-0.5">Selecione o quarto desejado para a sua estadia. Apenas quartos livres são listados.</p>
                  )}
                </div>

                {/* Daily Rate View */}
                {roomId && (
                  <div className="md:col-span-2 bg-indigo-50 border border-indigo-100 p-4 rounded-2xl flex justify-between items-center shadow-sm">
                    <div>
                      <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Valor Unitário da Diária</p>
                      <p className="text-2xl font-black text-slate-800">R$ {parseFloat(dailyRate).toFixed(2)}</p>
                    </div>
                    {checkInDate && checkOutDate && (
                      <div className="text-right">
                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                          Total Estimado ({Math.ceil((new Date(checkOutDate).getTime() - new Date(checkInDate).getTime()) / (1000 * 60 * 60 * 24)) || 1} diárias)
                        </p>
                        <p className="text-2xl font-black text-indigo-700">
                          R$ {((Math.ceil((new Date(checkOutDate).getTime() - new Date(checkInDate).getTime()) / (1000 * 60 * 60 * 24)) || 1) * parseFloat(dailyRate)).toFixed(2)}
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Companions Sub-Form */}
                <div className="md:col-span-2 border-t border-slate-200 pt-6 mt-2 space-y-4">
                  <div>
                    <h3 className="text-sm font-bold text-slate-700">Acompanhantes</h3>
                    <p className="text-xs text-slate-500 mt-0.5">Adicione as outras pessoas que se hospedarão no quarto com você. A pousada possui a seguinte política para crianças:</p>
                    <ul className="text-[11px] text-slate-550 list-disc pl-4 mt-1 space-y-0.5">
                      <li>0 a 5 anos = Grátis (Bebês)</li>
                      <li>6 a 12 anos = Paga 50% do valor da diária (Crianças)</li>
                      <li>13 anos ou mais = Paga o valor integral de adulto</li>
                    </ul>
                  </div>

                  <div className="flex flex-col sm:flex-row gap-2">
                    <div className="flex-1 space-y-1">
                      <input
                        type="text"
                        placeholder="Nome do acompanhante"
                        value={newCompName}
                        onChange={(e) => setNewCompName(e.target.value)}
                        className="w-full bg-white border border-slate-355 rounded-xl px-4 py-2 text-sm text-slate-800 focus:outline-none focus:border-indigo-500 font-medium"
                      />
                    </div>
                    <div className="w-full sm:w-24 space-y-1">
                      <input
                        type="number"
                        placeholder="Idade"
                        value={newCompAge}
                        onChange={(e) => setNewCompAge(e.target.value)}
                        className="w-full bg-white border border-slate-355 rounded-xl px-4 py-2 text-sm text-slate-800 focus:outline-none focus:border-indigo-500 font-medium"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={addCompanion}
                      className="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold px-4 py-2 rounded-xl text-sm flex items-center justify-center gap-1 border border-indigo-200 transition-all active:scale-95 shadow-sm"
                    >
                      <Plus size={16} /> Adicionar
                    </button>
                  </div>

                  {companions.length > 0 && (
                    <ul className="space-y-2 bg-slate-50 p-3 rounded-2xl border border-slate-200">
                      {companions.map((c, idx) => (
                        <li key={idx} className="flex items-center justify-between text-xs bg-white px-3 py-2 rounded-xl border border-slate-200 shadow-sm">
                          <span className="font-semibold text-slate-700">{c.name} ({c.age} anos)</span>
                          <button
                            type="button"
                            onClick={() => removeCompanion(idx)}
                            className="text-red-650 hover:text-red-700 font-bold flex items-center gap-0.5"
                          >
                            <Trash2 size={12} /> Remover
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="md:col-span-2 space-y-1">
                  <label className="text-xs font-bold text-slate-700 uppercase">Observações / Solicitações Especiais</label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Ex: Restrição alimentar, preferência por andar alto, etc..."
                    className="w-full bg-white border border-slate-355 rounded-xl px-4 py-2 text-sm text-slate-805 focus:outline-none focus:border-indigo-500 h-20 font-medium"
                  />
                  <p className="text-[11px] text-slate-550 mt-0.5">Use este campo livre para nos informar sobre qualquer necessidade especial (acessibilidade, alimentação, etc.). Este campo é opcional.</p>
                </div>
              </div>

              <div className="flex justify-between items-center border-t border-slate-200 pt-6">
                <button
                  type="button"
                  onClick={() => { setFormErrors({}); setStep('registration'); }}
                  className="bg-slate-100 hover:bg-slate-200 active:scale-95 text-slate-650 font-bold py-2.5 px-5 rounded-xl text-sm flex items-center gap-1.5 transition-all border border-slate-250"
                >
                  <ChevronLeft size={16} /> Voltar
                </button>
                <button
                  type="submit"
                  disabled={loading || !roomId}
                  className="bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white font-bold py-2.5 px-6 rounded-xl text-sm flex items-center gap-1.5 transition-all shadow-lg shadow-indigo-650/10 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {loading ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
                  Confirmar e Solicitar
                </button>
              </div>
            </form>
          )}

          {/* STEP 4: CONFIRMATION / PAYMENTS / UPLOAD */}
          {step === 'confirmation' && (
            <div className="space-y-8 py-4">
              <div className="text-center space-y-3">
                <div className="w-16 h-16 bg-green-500/10 border border-green-500/30 rounded-full flex items-center justify-center mx-auto text-green-600 animate-bounce">
                  <Check size={32} />
                </div>
                <h2 className="text-2xl font-black text-slate-800 tracking-tight font-sans">Reserva Pré-Confirmada!</h2>
                <p className="text-sm text-slate-500 max-w-md mx-auto">
                  Sua solicitação de reserva foi registrada no sistema. Agora, faça o pagamento para garantir sua hospedagem.
                </p>
              </div>

              {/* Booking Summary Voucher */}
              <div className="bg-indigo-50 border border-indigo-100 rounded-3xl p-6 relative overflow-hidden shadow-sm">
                <div className="absolute right-0 bottom-0 translate-x-6 translate-y-6 opacity-5 pointer-events-none text-indigo-550">
                  <Sparkles size={160} />
                </div>
                <div className="flex justify-between items-start border-b border-indigo-200/50 pb-4 mb-4">
                  <div>
                    <span className="text-[9px] font-black uppercase tracking-widest text-indigo-700">Reserva de Hospedagem</span>
                    <p className="text-lg font-black text-slate-800">Código #{createdBookingId}</p>
                  </div>
                  <div className="text-right">
                    <span className="text-[9px] font-black uppercase tracking-widest text-indigo-700">Total da Hospedagem</span>
                    <p className="text-lg font-black text-green-700 font-sans">R$ {totalAmount.toFixed(2)}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                  <div>
                    <span className="text-slate-500 font-bold block mb-0.5">Hóspede</span>
                    <span className="font-semibold text-slate-800">{guestName}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 font-bold block mb-0.5">Quarto</span>
                    <span className="font-semibold text-slate-800">Número {roomId}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 font-bold block mb-0.5">Entrada (Check-in)</span>
                    <span className="font-semibold text-slate-800">
                      {checkInDate ? new Date(checkInDate).toLocaleDateString('pt-BR') : '-'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 font-bold block mb-0.5">Saída (Check-out)</span>
                    <span className="font-semibold text-slate-800">
                      {checkOutDate ? new Date(checkOutDate).toLocaleDateString('pt-BR') : '-'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Pix Instructions */}
              <div className="bg-slate-50 border border-slate-200 p-6 rounded-3xl space-y-4">
                <div className="flex items-center gap-2 text-indigo-700">
                  <CreditCard size={18} />
                  <h3 className="font-bold text-sm text-slate-800">Pagamento via PIX</h3>
                </div>
                
                <p className="text-xs text-slate-650 leading-relaxed font-medium">
                  Realize a transferência do valor total de <strong className="text-slate-800">R$ {totalAmount.toFixed(2)}</strong> utilizando a chave PIX abaixo:
                </p>

                <div className="flex items-center gap-2 bg-white p-3 rounded-2xl border border-slate-250 shadow-sm">
                  <code className="text-xs text-indigo-850 font-mono font-bold break-all flex-1 select-all">
                    {pixKey}
                  </code>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(pixKey);
                      toast.success('Chave PIX copiada para a área de transferência!');
                    }}
                    className="bg-indigo-600 hover:bg-indigo-500 p-2 rounded-xl text-white transition-all active:scale-90 shadow-sm shadow-indigo-650/10"
                    title="Copiar Chave PIX"
                  >
                    <Copy size={14} />
                  </button>
                </div>
              </div>

              {/* Upload area */}
              <div className="bg-slate-50 border border-slate-200 p-6 rounded-3xl space-y-4 text-center">
                <div className="flex items-center gap-2 text-indigo-700 text-left">
                  <UploadCloud size={18} />
                  <h3 className="font-bold text-sm text-slate-800">Enviar Comprovante de Pagamento</h3>
                </div>

                {receiptUploaded ? (
                  <div className="bg-green-500/10 border border-green-500/30 p-6 rounded-2xl text-center space-y-2">
                    <Check className="text-green-600 mx-auto animate-bounce" size={24} />
                    <p className="text-xs text-green-700 font-bold">Comprovante anexado com sucesso!</p>
                    <p className="text-[10px] text-slate-500">Nossa equipe validará o recebimento e enviará o e-mail de confirmação final.</p>
                  </div>
                ) : (
                  <div className="border-2 border-dashed border-slate-300 rounded-2xl p-6 bg-white hover:border-indigo-500 transition-all relative shadow-sm">
                    <input 
                      type="file" 
                      id="receipt-file"
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      accept="image/*,application/pdf"
                      onChange={handleReceiptUpload}
                      disabled={uploadingReceipt}
                    />
                    <div className="space-y-2 pointer-events-none">
                      <UploadCloud className="text-slate-400 mx-auto" size={32} />
                      <p className="text-xs font-bold text-slate-700">
                        {uploadingReceipt ? 'Enviando arquivo...' : 'Clique para selecionar ou arraste o comprovante aqui'}
                      </p>
                      <p className="text-[10px] text-slate-500">Aceitamos arquivos PDF, PNG e JPG.</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Contacts */}
              <div className="flex flex-col sm:flex-row gap-4 justify-between border-t border-slate-200 pt-6 text-xs text-slate-500">
                <div className="flex items-center gap-1.5">
                  <Phone size={14} className="text-indigo-600" />
                  <span>Dúvidas? Ligue para: <strong className="text-slate-700">{pousadaPhone}</strong></span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Mail size={14} className="text-indigo-600" />
                  <span>Fale com a recepção: <strong className="text-slate-700">{pousadaEmail}</strong></span>
                </div>
              </div>

              <div className="text-center pt-2">
                <button
                  onClick={() => window.location.reload()}
                  className="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 px-5 py-2.5 rounded-xl text-xs font-bold transition-all shadow-sm"
                >
                  Fazer Nova Reserva
                </button>
              </div>
            </div>
          )}

        </div>
      </main>

      {/* Footer */}
      <footer className="max-w-4xl w-full mx-auto text-center mt-8 text-[9px] text-slate-400 uppercase tracking-widest">
        © {new Date().getFullYear()} {pousadaName} • Todos os direitos reservados.
      </footer>

    </div>
  );
}
