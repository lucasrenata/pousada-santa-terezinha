import { useState } from 'react';
import { useForm } from 'react-hook-form';
import api from '../services/api';
import { useNavigate, Link } from 'react-router-dom';
import { User, Mail, Lock, Building2, Zap, ArrowRight, CheckCircle2 } from 'lucide-react';
import { useToast } from '../hooks/use-toast';

export default function Signup() {
  type FormData = { 
    pousada_name: string; 
    admin_username: string; 
    admin_full_name: string;
    admin_email: string;
    admin_password: string;
  };
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [usernameError, setUsernameError] = useState('');
  const [emailError, setEmailError] = useState('');

  const checkAvailability = async (field: 'username' | 'email', value: string) => {
    if (!value) return;
    try {
      const response = await api.post('/auth/validate-field', { field, value });
      if (!response.data.available) {
        if (field === 'username') setUsernameError(response.data.message);
        else setEmailError(response.data.message);
      } else {
        if (field === 'username') setUsernameError('');
        else setEmailError('');
      }
    } catch (err) {
      console.error("Erro na validação:", err);
    }
  };

  const onSubmit = async (data: FormData) => {
    // Validação de senha forte
    const passRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$/;
    if (!passRegex.test(data.admin_password)) {
      setPasswordError('A senha deve ter no mínimo 8 caracteres, com Maiúscula, Minúscula, Número e Especial (!@#$).');
      return;
    }
    setPasswordError('');

    setLoading(true);
    try {
      const response = await api.post('/auth/signup', data);
      const { payment_url } = response.data;

      if (payment_url) {
        toast({
          title: "Ambiente Pré-Configurado! 🚀",
          description: "Redirecionando para o pagamento da taxa de ativação...",
        });
        
        // Pequeno delay para ler o Toast e redirecionar
        setTimeout(() => {
          window.location.href = payment_url;
        }, 2000);
      } else {
        toast({
          title: "Pousada Cadastrada! 🎉",
          description: "Agora você já pode fazer login no seu novo ambiente.",
        });
        
        setTimeout(() => {
          navigate('/login');
        }, 1500);
      }
      
    } catch (err: any) {
      console.error("Erro no cadastro:", err);
      
      let errorMessage = "Verifique os dados e tente novamente.";
      
      if (err.response?.status === 404) {
        errorMessage = "O servidor de cadastro não foi encontrado (404). Contate o suporte.";
      } else if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        errorMessage = typeof detail === 'string' ? detail : JSON.stringify(detail);
      } else if (err.message) {
        errorMessage = err.message;
      }

      toast({
        title: "Erro no cadastro",
        description: errorMessage,
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  // Efeito para capturar erros de pagamento vindos do redirecionamento
  useState(() => {
    const params = new URLSearchParams(window.location.search);
    const errorParam = params.get('error');
    if (errorParam === 'payment_failed') {
       toast({
         title: "Falha no Pagamento",
         description: "Não conseguimos confirmar sua taxa de ativação. Tente cadastrar novamente.",
         variant: "destructive"
       });
    }
  });

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-white">
      {/* Lado Esquerdo - Info (Estético) */}
      <div className="hidden lg:flex flex-col justify-center p-20 bg-slate-900 text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-600/30 blur-[120px] rounded-full -mr-48 -mt-48"></div>
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-indigo-600/20 blur-[100px] rounded-full -ml-40 -mb-40"></div>
        
        <div className="relative z-10 space-y-8">
           <div className="flex items-center gap-2 mb-12">
              <Zap size={32} className="text-blue-500 fill-blue-500" />
              <span className="text-3xl font-black tracking-tighter italic uppercase">Parcer<span className="text-blue-500">IA</span></span>
           </div>
           
           <h2 className="text-5xl font-black leading-tight italic">O futuro da sua <br/> pousada começa <br/> <span className="text-blue-500">agora.</span></h2>
           
           <div className="space-y-6 pt-10">
              <BenefitItem text="Provisionamento imediato do ambiente" />
              <BenefitItem text="Isolamento total de dados e segurança" />
              <BenefitItem text="Acesso ilimitado aos Agentes de IA" />
              <BenefitItem text="Sem fidelidade ou taxas escondidas" />
           </div>
        </div>
      </div>

      {/* Lado Direito - Formulário */}
      <div className="flex flex-col justify-center items-center p-8 md:p-12">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center">
            <h1 className="text-4xl font-black text-slate-900 tracking-tight italic">Criar Conta</h1>
            <p className="text-slate-500 mt-2 font-medium">Preencha os dados da sua pousada para começar.</p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div className="space-y-4">
              {/* Nome da Pousada */}
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase text-slate-500 ml-1">Nome da Pousada</label>
                <div className="flex items-center border-2 border-slate-100 bg-slate-50 rounded-2xl px-4 py-3.5 focus-within:border-blue-500 transition-colors">
                  <Building2 size={20} className="text-slate-400 mr-3" />
                  <input 
                    {...register("pousada_name", { required: true })} 
                    className="bg-transparent outline-none w-full font-semibold text-slate-800" 
                    placeholder="Ex: Pousada Vila do Sol" 
                  />
                </div>
              </div>

              {/* Nome do Dono (Admin) */}
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase text-slate-500 ml-1">Seu Nome Completo</label>
                <div className="flex items-center border-2 border-slate-100 bg-slate-50 rounded-2xl px-4 py-3.5 focus-within:border-blue-500 transition-colors">
                  <User size={20} className="text-slate-400 mr-3" />
                  <input 
                    {...register("admin_full_name", { required: true })} 
                    className="bg-transparent outline-none w-full font-semibold text-slate-800" 
                    placeholder="Ex: Carlos Albuquerque" 
                  />
                </div>
              </div>

              {/* Email do Dono (Admin) */}
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase text-slate-500 ml-1">E-mail Corporativo</label>
                <div className="flex items-center border-2 border-slate-100 bg-slate-50 rounded-2xl px-4 py-3.5 focus-within:border-blue-500 transition-colors">
                  <Mail size={20} className="text-slate-400 mr-3" />
                  <input 
                    {...register("admin_email", { 
                      required: true, 
                      pattern: /^\S+@\S+$/i,
                      onBlur: (e) => checkAvailability('email', e.target.value)
                    })} 
                    type="email"
                    className="bg-transparent outline-none w-full font-semibold text-slate-800" 
                    placeholder="Ex: carlos@pousada.com" 
                  />
                </div>
                {emailError && <span className="text-[10px] text-red-500 font-bold ml-1 uppercase">{emailError}</span>}
              </div>

              {/* Username Admin */}
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase text-slate-500 ml-1">Crie um Login (Usuário)</label>
                <div className="flex items-center border-2 border-slate-100 bg-slate-50 rounded-2xl px-4 py-3.5 focus-within:border-blue-500 transition-colors">
                  <User size={20} className="text-slate-400 mr-3" />
                  <input 
                    {...register("admin_username", { 
                      required: true,
                      onBlur: (e) => checkAvailability('username', e.target.value)
                    })} 
                    className="bg-transparent outline-none w-full font-semibold text-slate-800" 
                    placeholder="Ex: admin_joao" 
                  />
                </div>
                {usernameError && <span className="text-[10px] text-red-500 font-bold ml-1 uppercase">{usernameError}</span>}
              </div>

              {/* Senha */}
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase text-slate-500 ml-1">Crie uma Senha Segura</label>
                <div className="flex items-center border-2 border-slate-100 bg-slate-50 rounded-2xl px-4 py-3.5 focus-within:border-blue-500 transition-colors">
                  <Lock size={20} className="text-slate-400 mr-3" />
                  <input 
                    type="password" 
                    className="bg-transparent outline-none w-full font-semibold text-slate-800" 
                    placeholder="••••••••" 
                    {...register("admin_password", { 
                        required: true, 
                        minLength: 8,
                        onChange: (e) => setPasswordError('')
                    })} 
                  />
                </div>
                {passwordError && <span className="text-[10px] text-red-500 font-bold ml-1 uppercase">{passwordError}</span>}
                {errors.admin_password && !passwordError && <span className="text-[10px] text-red-500 font-bold ml-1 uppercase underline decoration-2">Mínimo 8 caracteres</span>}
              </div>
            </div>

            <button 
              type="submit" 
              disabled={loading}
              className="w-full bg-blue-600 text-white py-4 rounded-2xl font-black text-lg shadow-blue-200 shadow-xl hover:bg-blue-700 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center justify-center gap-2"
            >
              {loading ? "Processando..." : (
                <>Criar e Acessar <ArrowRight size={20} /></>
              )}
            </button>
          </form>

          <p className="text-center text-slate-400 font-medium text-sm">
            Já tem uma conta? <Link to="/login" className="text-blue-600 font-bold hover:underline">Fazer Login</Link>
          </p>
          
          <div className="pt-8 border-t border-slate-100">
             <p className="text-[10px] text-slate-400 text-center uppercase font-black leading-tight">
                Ao se cadastrar, você concorda com nossos <br/> Termos de Serviço e Política de Privacidade.
             </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function BenefitItem({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-4">
      <div className="bg-blue-500/20 p-1.5 rounded-full text-blue-500">
         <CheckCircle2 size={24} />
      </div>
      <span className="text-lg font-bold text-slate-300 italic">{text}</span>
    </div>
  );
}
