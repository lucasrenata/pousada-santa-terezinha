import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import api from '../services/api';
import { useNavigate, Link } from 'react-router-dom';
import { Lock, User, Zap, ArrowRight } from 'lucide-react';

export default function Login() {
  type FormData = { username: string; password: string };
  const { register, handleSubmit } = useForm<FormData>();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [pousadaName, setPousadaName] = useState('ParcerIA');

  useEffect(() => {
    // Tenta carregar o nome da pousada se já estiver logado ou algo assim (contexto futuro)
    async function loadSettings() {
      try {
        const response = await api.get('/settings/');
        const nameSetting = response.data.find((s: any) => s.key === 'pousada_name');
        if (nameSetting) setPousadaName(nameSetting.value);
      } catch (err) {
        console.error("Erro ao carregar nome da pousada", err);
      }
    }
    // loadSettings(); // Desativado no login global para manter o branding ParcerIA
  }, []);

  const onSubmit = async (data: FormData) => {
    setError('');
    try {
      const params = new URLSearchParams();
      params.append('grant_type', 'password');
      params.append('username', data.username);
      params.append('password', data.password);

      const response = await api.post('/token', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      
      localStorage.setItem('token', response.data.access_token);
      if (response.data.role) {
        localStorage.setItem('role', response.data.role);
      }
      if (response.data.tenant_id) {
        localStorage.setItem('tenant_id', response.data.tenant_id.toString());
      }
      
      const role = (response.data.role ?? 'recepcionista');
      if (role === 'superadmin') {
        navigate('/super/dashboard');
      } else if (['admin', 'recepcionista'].includes(role)) {
        navigate('/dashboard');
      } else {
        navigate('/service');
      }
    } catch (err) {
      setError('Credenciais inválidas. Verifique seu usuário e senha.');
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 p-4">
      <div className="flex items-center gap-2 mb-8 cursor-pointer" onClick={() => navigate('/')}>
        <div className="bg-blue-600 p-2 rounded-xl shadow-blue-200 shadow-xl">
          <Zap size={24} className="text-white fill-white" />
        </div>
        <span className="text-3xl font-black text-slate-900 tracking-tighter italic">PARCER<span className="text-blue-600">IA</span></span>
      </div>

      <div className="bg-white p-10 rounded-[32px] shadow-2xl border border-slate-100 w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-black text-slate-800 tracking-tight italic">Bem-vindo de volta</h1>
          <p className="text-slate-400 font-medium">Acesse seu ambiente administrativo.</p>
        </div>
        
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div className="space-y-1.5">
            <label className="text-xs font-black uppercase text-slate-500 ml-1">Usuário</label>
            <div className="flex items-center border-2 border-slate-100 bg-slate-50 rounded-2xl px-4 py-3.5 focus-within:border-blue-500 transition-colors">
              <User size={20} className="text-slate-400 mr-3" />
              <input 
                {...register("username")} 
                className="bg-transparent outline-none w-full font-semibold text-slate-800" 
                placeholder="nome_usuario" 
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-black uppercase text-slate-500 ml-1">Senha</label>
            <div className="flex items-center border-2 border-slate-100 bg-slate-50 rounded-2xl px-4 py-3.5 focus-within:border-blue-500 transition-colors">
              <Lock size={20} className="text-slate-400 mr-3" />
              <input 
                {...register("password")} 
                type="password" 
                className="bg-transparent outline-none w-full font-semibold text-slate-800" 
                placeholder="••••••" 
              />
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-100 text-red-600 px-4 py-3 rounded-xl text-xs font-bold uppercase text-center">
              {error}
            </div>
          )}

          <button 
            type="submit" 
            className="w-full bg-slate-900 text-white py-4 rounded-2xl font-black text-lg shadow-xl hover:bg-slate-800 active:scale-95 transition-all flex items-center justify-center gap-2"
          >
            Entrar no Painel <ArrowRight size={20} />
          </button>
        </form>

        <div className="mt-10 pt-8 border-t border-slate-100 text-center">
          <p className="text-slate-400 font-medium text-sm">
            Ainda não tem o sistema ParcerIA?
          </p>
          <Link to="/signup" className="text-blue-600 font-black text-lg hover:underline mt-1 block">
            Cadastre sua pousada agora
          </Link>
        </div>
      </div>
    </div>
  );
}
