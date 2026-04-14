import { useState, useEffect, useRef } from 'react';
import { Send, User, Bot, Check, ShieldCheck, Phone, Paperclip, Loader2 } from 'lucide-react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import api from '../services/api';
import { toast } from 'sonner';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export default function GuestChatPage() {
  const { tenant_id } = useParams();
  const navigate = useNavigate();
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [pousadaName, setPousadaName] = useState('Pousada System');
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Recupera o ID da reserva das mensagens (para saber onde anexar o comprovante)
  const getLatestBookingId = () => {
    // Percorre as mensagens da mais recente para a mais antiga
    for (let i = messages.length - 1; i >= 0; i--) {
      const content = messages[i].content;
      const match = content.match(/ID #(\d+)/);
      if (match) return match[1];
    }
    return null;
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const bookingId = getLatestBookingId();
    if (!bookingId) {
      const errorMsg: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: '⚠️ Não consegui localizar o número da sua reserva nesta conversa. Por favor, me informe o ID ou CPF para que eu possa vincular o seu comprovante.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMsg]);
      return;
    }

    // Mensagem de "Enviando"
    const processingMsg: Message = {
      id: "proc-" + Date.now(),
      role: 'assistant',
      content: `⏳ Enviando comprovante para a reserva #${bookingId}...`,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, processingMsg]);

    const formData = new FormData();
    formData.append('file', file);

    try {
      await api.post(`/bookings/${bookingId}/receipt?tenant_id=${tenant_id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      // Remove a mensagem de processamento e adiciona a de sucesso
      setMessages(prev => prev.filter(m => m.id !== processingMsg.id));
      const successMsg: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `✅ Comprovante da reserva #${bookingId} recebido com sucesso! Nossa equipe de recepção vai validar as informações agora.`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, successMsg]);
      
    } catch (err: any) {
      console.error('Erro no upload:', err);
      setMessages(prev => prev.filter(m => m.id !== processingMsg.id));
      
      const errorMsg: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `❌ Ops! Tivemos um problema ao enviar o comprovante da reserva #${bookingId}. Verifique se o arquivo é uma imagem válida ou tente novamente em instantes.`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      // Limpa o input para permitir novo upload
      event.target.value = '';
    }
  };

  // Inicializa sessão e busca configurações
// ... (rest of useEffects)
  useEffect(() => {
    let sid = localStorage.getItem(`guest_session`);
    if (!sid) {
      sid = 'guest_' + Math.random().toString(36).substring(2, 15);
      localStorage.setItem(`guest_session`, sid);
    }
    setSessionId(sid);
    loadHistory(sid);
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await api.get(`/settings/?tenant_id=${tenant_id}`);
      const nameSetting = response.data.find((s: any) => s.key === 'pousada_name');
      if (nameSetting) setPousadaName(nameSetting.value);
    } catch (err) {
      console.error("Erro ao carregar nome da pousada", err);
    }
  };

  const loadHistory = async (sid: string) => {
    try {
      const res = await api.get(`/chat/history/${sid}`);
      setMessages(res.data.map((m: any) => ({
        ...m,
        timestamp: new Date(m.timestamp)
      })));
    } catch (error) {
      console.error('Erro ao carregar histórico:', error);
    }
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMsg]);
    setMessage('');
    setLoading(true);

    try {
      const res = await api.post('/chat/customer', {
        message: userMsg.content,
        session_id: sessionId,
        tenant_id: parseInt(tenant_id || "1")
      });

      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: res.data.response,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, botMsg]);
    } catch (error) {
      setMessages(prev => [...prev, {
        id: 'err',
        role: 'assistant',
        content: "Desculpe, tive um pequeno problema técnico. Poderia repetir por favor?",
        timestamp: new Date()
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto h-screen flex flex-col p-2 sm:p-4 lg:p-6 animate-in fade-in duration-700">
      {/* Header Compacto - Top Left */}
      <header className="flex items-center gap-4 mb-4 mt-2 px-4 self-start">
        <div className="w-12 h-12 bg-gradient-to-br from-indigo-600 to-blue-500 rounded-2xl shadow-lg shadow-indigo-100 flex items-center justify-center transition-transform hover:scale-105 active:scale-95 cursor-default">
           <Bot size={28} className="text-white" />
        </div>
        <div className="text-left">
          <h1 className="text-xl font-black text-slate-800 tracking-tight leading-none">{pousadaName}</h1>
          <div className="flex items-center gap-2 mt-1">
            <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
            <p className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">Atendimento Inteligente</p>
          </div>
        </div>
      </header>

      {/* Chat Container - Full Height */}
      <div className="flex-1 bg-white/40 backdrop-blur-xl border border-white/60 shadow-2xl rounded-[2.5rem] flex flex-col overflow-hidden relative">

        {/* Messages Area */}
        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-hide"
        >
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
               <div className="p-4 bg-indigo-50/50 rounded-2xl border border-indigo-100/50">
                  <p className="text-slate-600 text-sm font-medium italic">"Olá, vamos fazer uma reserva hoje!"</p>
               </div>
               <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-tighter">Sua conversa é segura e privada</p>
            </div>
          )}

          {messages.map((m) => (
            <div 
              key={m.id} 
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-4 duration-500`}
            >
              <div className={`flex gap-3 max-w-[90%] ${m.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm ${
                  m.role === 'user' ? 'bg-slate-800 text-white' : 'bg-indigo-600 text-white'
                }`}>
                  {m.role === 'user' ? <User size={14} /> : <Bot size={14} />}
                </div>
                <div className={`p-4 rounded-2xl text-sm leading-relaxed shadow-lg ${
                  m.role === 'user' 
                    ? 'bg-slate-900/90 text-white rounded-tr-none' 
                    : 'bg-white/80 text-slate-800 rounded-tl-none border border-slate-100'
                }`}>
                  <ReactMarkdown 
                    components={{
                      a: ({ node, ...props }: any) => {
                        const isInternal = props.href?.startsWith('/');
                        if (isInternal) {
                          return (
                            <button 
                              onClick={() => navigate(props.href)}
                              className="inline-flex items-center gap-2 mt-3 bg-indigo-600 text-white px-5 py-2.5 rounded-xl font-bold border-none hover:bg-indigo-700 transition-all no-underline shadow-lg shadow-indigo-100 mb-1 group"
                            >
                              <Check size={16} /> {props.children}
                            </button>
                          );
                        }
                        return (
                          <a 
                            {...props} 
                            target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-2 mt-3 bg-indigo-600 text-white px-5 py-2.5 rounded-xl font-bold border-none hover:bg-indigo-700 transition-all no-underline shadow-lg shadow-indigo-100 mb-1 group"
                          >
                            <Check size={16} /> {props.children}
                          </a>
                        );
                      },
                      p: ({ children }: any) => <p className="mb-0 whitespace-pre-wrap">{children}</p>,
                      img: ({ node, ...props }: any) => (
                        <span className="block mt-4 mb-2 bg-white p-3 rounded-2xl shadow-sm border border-slate-100 w-fit">
                          <img {...props} className="w-48 h-48 object-contain rounded-xl opacity-90 mix-blend-multiply" alt="QR Code PIX" />
                        </span>
                      )
                    }}
                  >
                    {m.content}
                  </ReactMarkdown>
                  <span className={`text-[10px] mt-2 block opacity-40 font-bold ${m.role === 'user' ? 'text-right' : 'text-left'}`}>
                    {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-white/80 backdrop-blur-sm border border-slate-100 p-4 rounded-2xl rounded-tl-none shadow-sm flex gap-1.5 items-center">
                <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" />
              </div>
            </div>
          )}
        </div>

        {/* Action Input Area */}
        <div className="p-4 sm:p-6 bg-white/50 border-t border-white/60 backdrop-blur-md">
          <form onSubmit={handleSend} className="relative group flex gap-2">
            <div className="relative flex-1">
              <input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Digite sua mensagem aqui..."
                className="w-full bg-white border-2 border-slate-100 rounded-2xl pl-5 pr-14 py-4 text-sm focus:ring-4 focus:ring-indigo-100 focus:border-indigo-400 outline-none transition-all placeholder:text-slate-300 font-medium shadow-inner"
              />
              <button
                type="submit"
                disabled={loading || !message.trim()}
                className="absolute right-2 top-2 bottom-2 aspect-square bg-indigo-600 hover:bg-slate-900 text-white flex items-center justify-center rounded-xl shadow-lg shadow-indigo-100 transition-all disabled:opacity-30 active:scale-90"
              >
                <Send size={18} />
              </button>
            </div>
            
            {/* Botão de Anexo */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="w-14 h-14 flex-shrink-0 bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center rounded-2xl transition-all active:scale-90 border-2 border-slate-200/50"
              title="Anexar Comprovante PIX"
            >
              {uploading ? <Loader2 size={20} className="animate-spin" /> : <Paperclip size={20} />}
            </button>
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              accept="image/*,application/pdf"
              onChange={handleFileUpload}
            />
          </form>
          <div className="flex justify-between items-center mt-4 px-2">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400 font-bold uppercase">
               <ShieldCheck size={12} className="text-indigo-400" /> Criptografia Ponta-a-Ponta
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400 font-bold uppercase">
               <Phone size={12} className="text-slate-300" /> Suporte 24/7 Ativo
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
