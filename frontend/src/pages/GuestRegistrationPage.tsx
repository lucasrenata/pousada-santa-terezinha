import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, useParams } from 'react-router-dom';
import { Bot, User, MapPin, Phone, Mail, CheckCircle, Loader2, ArrowRight, Calendar } from 'lucide-react';
import api from '../services/api';

export default function GuestRegistrationPage() {
  const { tenant_id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pousadaName, setPousadaName] = useState('Pousada System');

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    document: searchParams.get('cpf') || '',
    birth_date: '',
    profession: '',
    cep: '',
    street: '',
    number: '',
    neighborhood: '',
    city: '',
    state: ''
  });

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await api.get('/settings/');
      const nameSetting = response.data.find((s: any) => s.key === 'pousada_name');
      if (nameSetting) setPousadaName(nameSetting.value);
    } catch (err) {
      console.error("Erro ao carregar nome da pousada", err);
    }
  };

  const fetchCep = async (cep: string) => {
    const cleanCep = cep.replace(/\D/g, '');
    if (cleanCep.length === 8) {
      try {
        const res = await fetch(`https://viacep.com.br/ws/${cleanCep}/json/`);
        const data = await res.json();
        if (!data.erro) {
          setFormData(prev => ({
            ...prev,
            street: data.logradouro,
            neighborhood: data.bairro,
            city: data.localidade,
            state: data.uf
          }));
        }
      } catch (err) {
        console.error("Erro ao buscar CEP", err);
      }
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (name === 'cep') fetchCep(value);
  };

  const calculateAge = (birthDate: string) => {
    if (!birthDate) return null;
    const today = new Date();
    const birth = new Date(birthDate);
    if (isNaN(birth.getTime())) return null;
    
    let age = today.getFullYear() - birth.getFullYear();
    const m = today.getMonth() - birth.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) {
        age--;
    }
    return age;
  };

  const age = calculateAge(formData.birth_date);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Usando o endpoint de registro público de hóspedes (sem auth)
      await api.post('/guests/public', {
        name: formData.name,
        email: formData.email,
        phone: formData.phone,
        document: formData.document,
        birth_date: formData.birth_date,
        profession: formData.profession,
        address_zip: formData.cep,
        address_street: formData.street,
        address_number: formData.number,
        address_neighborhood: formData.neighborhood,
        address_city: formData.city,
        address_state: formData.state,
        tenant_id: parseInt(tenant_id || "1")
      });

      setSuccess(true);
      setTimeout(() => navigate(`/${tenant_id || "1"}/atendimento`), 3000);
    } catch (err: any) {
      console.error("Erro ao salvar cadastro:", err);
      setError(err.response?.data?.detail || "Ocorreu um erro ao salvar seus dados. Verifique os campos ou tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="max-w-md mx-auto h-screen flex flex-col items-center justify-center p-6 text-center animate-in zoom-in duration-500">
        <div className="w-20 h-20 bg-green-100 text-green-600 rounded-full flex items-center justify-center mb-6 shadow-lg">
          <CheckCircle size={48} />
        </div>
        <h2 className="text-2xl font-black text-slate-800 mb-2">Cadastro Concluído!</h2>
        <p className="text-slate-500 font-medium mb-8">Agora você pode voltar ao chat e finalizar sua reserva em segundos.</p>
        <button 
          onClick={() => navigate(`/${tenant_id || "1"}/atendimento`)}
          className="w-full bg-slate-900 text-white py-4 rounded-2xl font-bold flex items-center justify-center gap-2 hover:bg-slate-800 transition-all"
        >
          Voltar para o Chat <ArrowRight size={18} />
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 py-12 animate-in slide-in-from-bottom-8 duration-700">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-black text-slate-800 tracking-tight mb-2">Ficha de Hóspede</h1>
        <p className="text-slate-400 font-bold uppercase tracking-widest text-xs flex items-center justify-center gap-2">
           <Bot size={14} className="text-indigo-600" /> {pousadaName}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white/70 backdrop-blur-xl border border-white shadow-2xl rounded-[2.5rem] p-8 sm:p-12 space-y-8">
        
        {/* Seção 1: Identidade */}
        <div className="space-y-6">
          <div className="flex items-center gap-2 text-indigo-600 mb-2">
            <User size={18} />
            <h3 className="font-black uppercase tracking-tight text-sm">Identificação</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2 space-y-1">
              <label className="text-xs font-bold text-slate-400 ml-1">NOME COMPLETO *</label>
              <input 
                name="name" required value={formData.name} onChange={handleInputChange}
                className="w-full bg-slate-50 border-none rounded-2xl px-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                placeholder="Como devemos te chamar?" 
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-400 ml-1">CPF / RG *</label>
              <input 
                name="document" required value={formData.document} onChange={handleInputChange}
                className="w-full bg-slate-50 border-none rounded-2xl px-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                placeholder="000.000.000-00" 
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-400 ml-1 flex items-center justify-between">
                NASCIMENTO *
                {age !== null && age >= 0 && (
                  <span className="text-[10px] bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full">{age} anos</span>
                )}
              </label>
              <div className="relative">
                <Calendar size={16} className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-300" />
                <input 
                  type="date" name="birth_date" required value={formData.birth_date} onChange={handleInputChange}
                  className="w-full bg-slate-50 border-none rounded-2xl pl-12 pr-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-400 ml-1">WHATSAPP *</label>
              <div className="relative">
                <Phone size={16} className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-300" />
                <input 
                  name="phone" required value={formData.phone} onChange={handleInputChange}
                  className="w-full bg-slate-50 border-none rounded-2xl pl-12 pr-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                  placeholder="(00) 00000-0000" 
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-400 ml-1">EMAIL *</label>
              <div className="relative">
                <Mail size={16} className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-300" />
                <input 
                  name="email" type="email" required value={formData.email} onChange={handleInputChange}
                  className="w-full bg-slate-50 border-none rounded-2xl pl-12 pr-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                  placeholder="exemplo@email.com" 
                />
              </div>
            </div>
          </div>
        </div>

        {/* Seção 2: Endereço */}
        <div className="space-y-6 pt-4">
          <div className="flex items-center gap-2 text-indigo-600 mb-2">
            <MapPin size={18} />
            <h3 className="font-black uppercase tracking-tight text-sm">Endereço de Origem</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-400 ml-1">CEP *</label>
              <input 
                name="cep" required value={formData.cep} onChange={handleInputChange}
                className="w-full bg-slate-50 border-none rounded-2xl px-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                placeholder="00000-000" 
              />
            </div>
            <div className="sm:col-span-2 space-y-1">
              <label className="text-xs font-bold text-slate-400 ml-1">RUA / LOGRADOURO *</label>
              <input 
                name="street" required value={formData.street} onChange={handleInputChange}
                className="w-full bg-slate-50 border-none rounded-2xl px-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                placeholder="Av. Exemplo, Rua..." 
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-400 ml-1">NÚMERO *</label>
              <input 
                name="number" required value={formData.number} onChange={handleInputChange}
                className="w-full bg-slate-50 border-none rounded-2xl px-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                placeholder="123" 
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-400 ml-1">BAIRRO *</label>
              <input 
                name="neighborhood" required value={formData.neighborhood} onChange={handleInputChange}
                className="w-full bg-slate-50 border-none rounded-2xl px-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                placeholder="Seu bairro" 
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-400 ml-1">CIDADE *</label>
              <input 
                name="city" required value={formData.city} onChange={handleInputChange}
                className="w-full bg-slate-50 border-none rounded-2xl px-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                placeholder="Sua cidade" 
              />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
             <div className="space-y-1">
                <label className="text-xs font-bold text-slate-400 ml-1">ESTADO *</label>
                <input 
                  name="state" required value={formData.state} onChange={handleInputChange}
                  className="w-full bg-slate-50 border-none rounded-2xl px-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                  placeholder="UF" 
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-400 ml-1">PROFISSÃO</label>
                <input 
                  name="profession" value={formData.profession} onChange={handleInputChange}
                  className="w-full bg-slate-50 border-none rounded-2xl px-5 py-4 text-sm focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                  placeholder="Sua ocupação" 
                />
              </div>
          </div>
        </div>

        {error && <p className="text-center text-red-500 text-sm font-bold bg-red-50 p-4 rounded-2xl">{error}</p>}

        <button 
          type="submit" 
          disabled={loading}
          className="w-full bg-indigo-600 hover:bg-slate-900 text-white py-5 rounded-[1.5rem] font-black text-lg transition-all shadow-xl shadow-indigo-100 flex items-center justify-center gap-3 disabled:opacity-50"
        >
          {loading ? <Loader2 className="animate-spin" /> : 'Finalizar minha ficha'}
        </button>
      </form>
    </div>
  );
}
