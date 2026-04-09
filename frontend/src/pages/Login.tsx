import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import api from '../services/api';
import { useNavigate } from 'react-router-dom';
import { Lock, User } from 'lucide-react';

export default function Login() {
  type FormData = { username: string; password: string };
  const { register, handleSubmit } = useForm<FormData>();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [pousadaName, setPousadaName] = useState('Pousada System');

  useEffect(() => {
    async function loadSettings() {
      try {
        const response = await api.get('/settings/');
        const nameSetting = response.data.find((s: any) => s.key === 'pousada_name');
        if (nameSetting) setPousadaName(nameSetting.value);
      } catch (err) {
        console.error("Erro ao carregar nome da pousada", err);
      }
    }
    loadSettings();
  }, []);

  const onSubmit = async (data: FormData) => {
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
      const role = (response.data.role ?? 'recepcionista') as 'admin' | 'recepcionista' | 'camareira' | 'manutencao';
      navigate(['admin', 'recepcionista'].includes(role) ? '/dashboard' : '/service');
    } catch {
      setError('Usuário ou senha incorretos');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-200">
      <div className="bg-white p-8 rounded-2xl shadow-xl w-96">
        <h1 className="text-2xl font-bold text-center mb-6 text-slate-800">{pousadaName}</h1>
        
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-600">Usuário</label>
            <div className="flex items-center border rounded-lg px-3 py-2 mt-1 focus-within:ring-2 ring-blue-500">
              <User size={18} className="text-slate-400 mr-2" />
              <input {...register("username")} className="outline-none w-full" placeholder="admin" />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600">Senha</label>
            <div className="flex items-center border rounded-lg px-3 py-2 mt-1 focus-within:ring-2 ring-blue-500">
              <Lock size={18} className="text-slate-400 mr-2" />
              <input {...register("password")} type="password" className="outline-none w-full" placeholder="••••••" />
            </div>
          </div>

          {error && <p className="text-red-500 text-sm text-center">{error}</p>}

          <button type="submit" className="w-full bg-blue-600 text-white py-2 rounded-lg font-semibold hover:bg-blue-700 transition">
            Entrar
          </button>
        </form>
      </div>
    </div>
  );
}
