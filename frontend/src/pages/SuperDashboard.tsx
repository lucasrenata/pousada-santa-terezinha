import { useState, useEffect } from 'react';
import api from '../services/api';
import { 
  ShieldCheck, 
  Users, 
  Database, 
  Server, 
  RefreshCcw, 
  Activity, 
  Lock, 
  Unlock,
  Package,
  Calendar,
  X,
  CreditCard,
  Target,
  UserCog,
  Trash2,
  AlertTriangle
} from 'lucide-react';
import { useToast } from '../hooks/use-toast';

interface Tenant {
  id: number;
  name: string;
  created_at: string;
  is_active: boolean;
  user_count: number;
  size_mb?: number;
}

interface SystemMetrics {
  ram_total: number;
  ram_used: number;
  ram_percent: number;
  cpu_percent: number;
  status: string;
}

export default function SuperDashboard() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [configData, setConfigData] = useState({ 
    mp_access_token: '', 
    mp_public_key: '', 
    manual_pix_key: '',
    platform_setup_fee: 49.90
  });
  const [showProfile, setShowProfile] = useState(false);
  const [profileData, setProfileData] = useState({ username: '', full_name: '', email: '', password: '' });
  const [passwordError, setPasswordError] = useState('');
  const [deletingTenant, setDeletingTenant] = useState<Tenant | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [tenantsRes, metricsRes] = await Promise.all([
        api.get('/super/tenants'),
        api.get('/super/metrics/system')
      ]);
      setTenants(tenantsRes.data);
      setMetrics(metricsRes.data);
    } catch (err) {
      toast({ title: "Erro ao carregar dados", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  async function calculateStorage() {
    setCalculating(true);
    try {
      const res = await api.get('/super/metrics/storage');
      // Merge storage info into tenants list
      const storageMap = res.data.tenants.reduce((acc: any, t: any) => {
        acc[t.tenant_id] = t.size_mb;
        return acc;
      }, {});
      
      setTenants(prev => prev.map(t => ({
        ...t,
        size_mb: storageMap[t.id] || 0
      })));
      
      toast({ title: "Métricas atualizadas com sucesso!" });
    } catch (err) {
      toast({ title: "Erro ao calcular armazenamento", variant: "destructive" });
    } finally {
      setCalculating(false);
    }
  }

  async function toggleTenant(id: number) {
    try {
      await api.post(`/super/tenants/${id}/toggle`);
      setTenants(prev => prev.map(t => t.id === id ? { ...t, is_active: !t.is_active } : t));
      toast({ title: "Status do tenant alterado" });
    } catch (err) {
      toast({ title: "Erro ao alterar status", variant: "destructive" });
    }
  }

  async function deleteTenant(id: number) {
    try {
      await api.delete(`/super/tenants/${id}`);
      setTenants(prev => prev.filter(t => t.id !== id));
      setDeletingTenant(null);
      toast({ title: "Pousada removida permanentemente.", variant: "destructive" });
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Erro ao remover pousada";
      toast({ title: msg, variant: "destructive" });
      setDeletingTenant(null);
    }
  }

  async function openProfile() {
    try {
      const res = await api.get('/super/profile');
      setProfileData({
        username: res.data.username,
        full_name: res.data.full_name || '',
        email: res.data.email || '',
        password: ''
      });
      setPasswordError('');
      setShowProfile(true);
    } catch {
      toast({ title: "Falha ao carregar perfil master", variant: "destructive" });
    }
  }

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault();
    if (profileData.password) {
      const passRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$/;
      if (!passRegex.test(profileData.password)) {
        setPasswordError('Mínimo 8 caracteres: Maiúscula, Minúscula, Número e Símbolo Especial (!@#$).');
        return;
      }
    }
    
    setLoading(true);
    try {
      const payload: any = {
        full_name: profileData.full_name,
        email: profileData.email,
      };
      if (profileData.password) {
        payload.password = profileData.password;
      }
      
      await api.put('/super/profile', payload);
      toast({ title: "Perfil Master atualizado com sucesso!" });
      setShowProfile(false);
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Erro ao salvar Perfil";
      toast({ title: msg, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  async function openConfig() {
    try {
      const res = await api.get('/super/config');
      setConfigData(res.data);
      setShowConfig(true);
    } catch {
      toast({ title: "Falha ao carregar configurações da plataforma", variant: "destructive" });
    }
  }

  async function handleConfigSave(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await api.put('/super/config', configData);
      toast({ title: "Configurações da Plataforma salvas com sucesso!" });
      setShowConfig(false);
    } catch (err: any) {
      toast({ title: "Erro ao salvar configurações", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  if (loading && tenants.length === 0) {
    return <div className="flex items-center justify-center p-20">Carregando painel de controle...</div>;
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-slate-900 flex items-center gap-2 italic">
            <ShieldCheck className="text-blue-600" size={32} />
            CONSOLE <span className="text-blue-600">SAAS</span>
          </h1>
          <p className="text-slate-500 font-medium">Visão global da infraestrutura e gestão de clientes.</p>
        </div>
        <div className="flex gap-2">
           <button 
             onClick={loadData}
             className="bg-white border-2 border-slate-200 p-2.5 rounded-xl hover:bg-slate-50 transition-all text-slate-600"
             title="Atualizar lista"
           >
             <RefreshCcw size={20} />
           </button>
           <button 
              onClick={calculateStorage}
              disabled={calculating}
              className="bg-blue-600 text-white px-6 py-2.5 rounded-xl font-bold flex items-center gap-2 shadow-lg shadow-blue-200 hover:bg-blue-700 transition-all active:scale-95 disabled:opacity-50"
           >
             <Database size={20} />
             {calculating ? "Calculando..." : "Calcular MB por Hotel"}
           </button>
           <button 
             onClick={openConfig}
             className="bg-blue-50 text-blue-600 border-2 border-blue-100 p-2.5 rounded-xl hover:bg-blue-100 transition-all shadow-sm flex items-center gap-2 font-bold"
             title="Configurações de Faturamento SaaS"
           >
             <CreditCard size={20} />
             <span className="hidden lg:inline">Configurações SaaS</span>
           </button>
           <button 
             onClick={openProfile}
             className="bg-slate-800 text-white p-2.5 rounded-xl hover:bg-slate-900 transition-all shadow-md flex items-center gap-2 font-semibold"
             title="Meu Perfil SaaS"
           >
             <UserCog size={20} />
             <span className="hidden md:inline">Meu Perfil</span>
           </button>
        </div>
      </div>

      {/* Modal Profile */}
      {showProfile && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100] backdrop-blur-sm">
          <div className="bg-white p-6 rounded-3xl shadow-2xl w-full max-w-md mx-4 transform transition-all border outline-none">
            <div className="flex justify-between items-center mb-6">
               <div className="flex items-center gap-3">
                 <div className="bg-slate-800 text-white p-2.5 rounded-xl">
                   <UserCog size={24} />
                 </div>
                 <div>
                   <h2 className="text-xl font-black text-slate-800 italic">Conta Root (SaaS)</h2>
                   <p className="text-xs text-slate-500 font-medium">Gestão de credenciais master</p>
                 </div>
               </div>
               <button onClick={() => setShowProfile(false)} className="text-slate-400 hover:text-slate-700 bg-slate-50 p-2 rounded-full">
                 <X size={20} />
               </button>
            </div>
            
            <form onSubmit={handleProfileSave} className="space-y-4">
              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1">Nome Completo</label>
                <input 
                  required
                  className="w-full border-2 rounded-xl px-4 py-2.5 focus:border-slate-800 outline-none border-slate-200 bg-slate-50"
                  placeholder="Ex: Seu Nome"
                  value={profileData.full_name}
                  onChange={(e) => setProfileData({...profileData, full_name: e.target.value})}
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1">E-mail Corporativo</label>
                <input 
                  type="email"
                  required
                  className="w-full border-2 rounded-xl px-4 py-2.5 focus:border-slate-800 outline-none border-slate-200 bg-slate-50"
                  placeholder="admin@seusaas.com"
                  value={profileData.email}
                  onChange={(e) => setProfileData({...profileData, email: e.target.value})}
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1">Master Login <span className="font-normal text-xs text-slate-400">(Inalterável)</span></label>
                <input 
                  disabled
                  className="w-full border-2 rounded-xl px-4 py-2.5 outline-none border-slate-200 bg-slate-100 text-slate-500 cursor-not-allowed"
                  value={profileData.username}
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1">
                  Nova Senha Segura <span className="font-normal text-xs text-slate-500">(Branco = manter atual)</span>
                </label>
                <input 
                  type="password"
                  className="w-full border-2 rounded-xl px-4 py-2.5 focus:border-slate-800 outline-none border-slate-200 bg-slate-50"
                  placeholder="••••••••"
                  value={profileData.password}
                  onChange={(e) => {
                    setProfileData({...profileData, password: e.target.value});
                    setPasswordError('');
                  }}
                />
                {passwordError && <p className="mt-1.5 text-xs text-red-500 font-bold uppercase">{passwordError}</p>}
              </div>

              <div className="pt-4">
                <button 
                  type="submit" 
                  disabled={loading}
                  className="w-full bg-slate-900 text-white py-3.5 rounded-xl font-black text-lg hover:bg-slate-800 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl shadow-slate-300 disabled:opacity-50"
                >
                  {loading ? 'Salvando...' : 'Atualizar Credenciais'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Config SaaS */}
      {showConfig && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100] backdrop-blur-sm">
          <div className="bg-white p-6 rounded-[32px] shadow-2xl w-full max-w-lg mx-4 transform transition-all border outline-none border-blue-100">
            <div className="flex justify-between items-center mb-6">
               <div className="flex items-center gap-3">
                 <div className="bg-blue-600 text-white p-2.5 rounded-xl shadow-lg shadow-blue-200">
                    <CreditCard size={24} />
                 </div>
                 <div>
                   <h2 className="text-xl font-black text-slate-800 italic uppercase">Configurações Platform</h2>
                   <p className="text-xs text-slate-500 font-medium italic text-blue-600">Gestão de Recebimento de Assinaturas</p>
                 </div>
               </div>
               <button onClick={() => setShowConfig(false)} className="text-slate-400 hover:text-slate-700 bg-slate-50 p-2 rounded-full transition-colors">
                 <X size={20} />
               </button>
            </div>
            
            <div className="mb-6 p-4 bg-blue-50 border border-blue-100 rounded-2xl">
                <p className="text-[11px] text-blue-700 font-bold flex items-center gap-2 leading-tight">
                    <ShieldCheck size={14} className="shrink-0" />
                    As credenciais abaixo serão usadas pela plataforma ParcerIA para processar cobranças automáticas dos seus clientes.
                </p>
            </div>

            <form onSubmit={handleConfigSave} className="space-y-4">
              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1">Mercado Pago Access Token</label>
                <input 
                  type="password"
                  className="w-full border-2 rounded-xl px-4 py-2.5 focus:border-blue-600 outline-none border-slate-200 bg-slate-50 text-xs font-mono"
                  placeholder="APP_USR-..."
                  value={configData.mp_access_token}
                  onChange={(e) => setConfigData({...configData, mp_access_token: e.target.value})}
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1">Mercado Pago Public Key</label>
                <input 
                  className="w-full border-2 rounded-xl px-4 py-2.5 focus:border-blue-600 outline-none border-slate-200 bg-slate-50 text-xs font-mono"
                  placeholder="APP_USR-..."
                  value={configData.mp_public_key}
                  onChange={(e) => setConfigData({...configData, mp_public_key: e.target.value})}
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1">Chave PIX (Backup de Recebimento)</label>
                <input 
                  className="w-full border-2 rounded-xl px-4 py-2.5 focus:border-blue-600 outline-none border-slate-200 bg-slate-50"
                  placeholder="E-mail, CPF ou Chave Aleatória"
                  value={configData.manual_pix_key}
                  onChange={(e) => setConfigData({...configData, manual_pix_key: e.target.value})}
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-slate-700 mb-1">Taxa de Setup (R$)</label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 font-bold text-slate-400">R$</span>
                  <input 
                    type="number"
                    step="0.01"
                    className="w-full border-2 rounded-xl pl-12 pr-4 py-2.5 focus:border-blue-600 outline-none border-slate-100 bg-slate-50 font-black text-slate-700"
                    placeholder="49,90"
                    value={configData.platform_setup_fee}
                    onChange={(e) => setConfigData({...configData, platform_setup_fee: parseFloat(e.target.value) || 0})}
                  />
                </div>
                <p className="text-[10px] text-slate-400 mt-1 font-medium italic">Valor cobrado automaticamente no portal de signup.</p>
              </div>

              <div className="pt-4">
                <button 
                  type="submit" 
                  disabled={loading}
                  className="w-full bg-blue-600 text-white py-3.5 rounded-xl font-black text-lg hover:bg-blue-700 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl shadow-blue-200 disabled:opacity-50"
                >
                  {loading ? 'Salvando...' : 'Salvar Configurações SaaS'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* KPI Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KPICard 
          title="Total de Pousadas" 
          value={tenants.length} 
          icon={<Users className="text-blue-600" />} 
          subtitle="Clientes ativos na plataforma"
        />
        <KPICard 
          title="RAM do Servidor (Total)" 
          value={`${metrics?.ram_used || 0} / ${metrics?.ram_total || 0} GB`} 
          icon={<Server className="text-indigo-600" />} 
          subtitle={`${metrics?.ram_percent || 0}% em uso`}
          progress={metrics?.ram_percent}
        />
        <KPICard 
          title="Carga de CPU" 
          value={`${metrics?.cpu_percent || 0}%`} 
          icon={<Activity className="text-green-600" />} 
          subtitle="Processamento do backend"
        />
        <KPICard 
          title="Saúde do Sistema" 
          value={metrics?.status || "Online"} 
          icon={<ShieldCheck className="text-blue-500" />} 
          subtitle="Todos os serviços operacionais"
          statusColor={metrics?.status === 'Critical' ? 'bg-red-500' : 'bg-green-500'}
        />
      </div>

      {/* Main Content */}
      <div className="bg-white rounded-[32px] shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
        <div className="p-8 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
           <h2 className="text-xl font-black text-slate-800 italic uppercase tracking-tight">Gestão de Ambientes (Tenants)</h2>
           <span className="text-xs font-bold text-slate-400 uppercase bg-white px-3 py-1 rounded-full border border-slate-200">Total: {tenants.length}</span>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 text-slate-400 text-[10px] font-black uppercase tracking-widest">
                <th className="px-8 py-4">ID</th>
                <th className="px-8 py-4">Pousada / Organização</th>
                <th className="px-8 py-4">Adesão</th>
                <th className="px-8 py-4 text-center">Usuários</th>
                <th className="px-8 py-4 text-center">Espaço em Disco</th>
                <th className="px-8 py-4 text-right">Status / Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {tenants.map(t => (
                <tr key={t.id} className="hover:bg-blue-50/30 transition-colors group">
                  <td className="px-8 py-5 text-sm font-black text-slate-400">#{t.id}</td>
                  <td className="px-8 py-5">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center text-blue-600 font-black text-xs">
                        {t.name.substring(0, 2).toUpperCase()}
                      </div>
                      <span className="font-bold text-slate-800">{t.name}</span>
                    </div>
                  </td>
                  <td className="px-8 py-5 text-sm text-slate-500 font-medium">
                    <div className="flex items-center gap-2">
                       <Calendar size={14} className="text-slate-300" />
                       {new Date(t.created_at).toLocaleDateString('pt-BR')}
                    </div>
                  </td>
                  <td className="px-8 py-5 text-center">
                    <div className="inline-flex items-center gap-1 bg-white px-3 py-1 rounded-full border border-slate-100 text-sm font-bold text-slate-600">
                      <Users size={12} className="text-blue-400" />
                      {t.user_count}
                    </div>
                  </td>
                  <td className="px-8 py-5 text-center">
                    {t.size_mb !== undefined ? (
                       <span className={`text-sm font-black ${t.size_mb > 100 ? 'text-red-500' : 'text-slate-600'}`}>
                         {t.size_mb.toFixed(2)} MB
                       </span>
                    ) : (
                       <span className="text-[10px] font-bold text-slate-300 italic">Pendente</span>
                    )}
                  </td>
                  <td className="px-8 py-5 text-right">
                    <div className="flex items-center justify-end gap-2">
                       <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase ${t.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                         {t.is_active ? 'Ativo' : 'Bloqueado'}
                       </span>
                       <button 
                         onClick={() => toggleTenant(t.id)}
                         className={`p-2 rounded-lg border-2 transition-all ${t.is_active ? 'border-red-100 text-red-400 hover:bg-red-50' : 'border-green-100 text-green-400 hover:bg-green-50'}`}
                         title={t.is_active ? "Bloquear acesso" : "Desbloquear acesso"}
                       >
                         {t.is_active ? <Lock size={18} /> : <Unlock size={18} />}
                       </button>
                       <button 
                         onClick={() => setDeletingTenant(t)}
                         className="p-2 rounded-lg border-2 border-slate-100 text-slate-300 hover:border-red-200 hover:text-red-500 hover:bg-red-50 transition-all"
                         title="Remover pousada permanentemente"
                       >
                         <Trash2 size={18} />
                       </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    {/* Modal de Confirmação de Exclusão */}
    {deletingTenant && (
      <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[200] backdrop-blur-sm">
        <div className="bg-white p-8 rounded-3xl shadow-2xl w-full max-w-sm mx-4 border-2 border-red-100">
          <div className="flex flex-col items-center text-center gap-4">
            <div className="bg-red-100 p-4 rounded-2xl">
              <AlertTriangle size={32} className="text-red-600" />
            </div>
            <div>
              <h2 className="text-xl font-black text-slate-800">Remover Pousada?</h2>
              <p className="text-slate-500 text-sm mt-2">
                Você está prestes a deletar permanentemente
                <span className="font-black text-slate-800 block mt-1">&ldquo;{deletingTenant.name}&rdquo;</span>
              </p>
              <p className="text-xs text-red-500 font-bold mt-3 bg-red-50 p-3 rounded-xl">
                ⚠️ Todos os usuários e dados serão removidos. Esta ação é irreversível.
              </p>
            </div>
            <div className="flex gap-3 w-full">
              <button
                onClick={() => setDeletingTenant(null)}
                className="flex-1 py-3 rounded-2xl border-2 border-slate-200 font-bold text-slate-600 hover:bg-slate-50 transition-all"
              >
                Cancelar
              </button>
              <button
                onClick={() => deleteTenant(deletingTenant.id)}
                className="flex-1 py-3 rounded-2xl bg-red-600 text-white font-black hover:bg-red-700 transition-all active:scale-95"
              >
                Sim, Remover
              </button>
            </div>
          </div>
        </div>
      </div>
    )}
  </div>
  );
}

function KPICard({ title, value, icon, subtitle, progress, statusColor }: any) {
  return (
    <div className="bg-white p-6 rounded-[32px] border border-slate-100 shadow-xl shadow-slate-200/50 hover:scale-[1.02] transition-all group">
      <div className="flex justify-between items-start mb-4">
        <div className="p-3 bg-slate-50 rounded-2xl group-hover:bg-blue-50 transition-colors">
          {icon}
        </div>
        {statusColor && <div className={`w-3 h-3 rounded-full ${statusColor} animate-pulse`} />}
      </div>
      <div>
        <p className="text-xs font-black text-slate-400 uppercase tracking-widest mb-1">{title}</p>
        <h3 className="text-2xl font-black text-slate-900 tracking-tight italic">{value}</h3>
        <p className="text-xs text-slate-500 font-medium mt-1">{subtitle}</p>
      </div>
      {progress !== undefined && (
        <div className="mt-4 w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
          <div 
            className={`h-full transition-all duration-1000 ${progress > 80 ? 'bg-red-500' : 'bg-blue-600'}`} 
            style={{ width: `${progress}%` }} 
          />
        </div>
      )}
    </div>
  );
}
