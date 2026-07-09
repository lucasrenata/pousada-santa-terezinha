import { useState, useEffect, useRef } from 'react';
import { Send, User, Check, ShieldCheck, Phone, Paperclip, Loader2, Bot, RefreshCw, Mic, MessageSquare, Headphones, MicOff } from 'lucide-react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import api from '../services/api';
import { toast } from 'sonner';
import { Card, CardContent } from '../components/ui/card';
import { GuestVoiceAssistant, GuestVoiceAssistantRef } from '../components/customer/GuestVoiceAssistant';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export default function GuestChatPage() {
  const { tenant_id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [pousadaName, setPousadaName] = useState('Estabelecimento');
  const [aiName, setAiName] = useState('Ana');
  const [viewMode, setViewMode] = useState<'voice' | 'chat'>('voice');
  const [isMuted, setIsMuted] = useState(false);
  const voiceAssistantRef = useRef<GuestVoiceAssistantRef>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Recupera o ID da reserva das mensagens (para saber onde anexar o comprovante)
  const getLatestBookingId = () => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const content = messages[i].content;
      // Regex mais flexível: Procura por #123, "reserva 123", "id 123" ou apenas o número isolado se houver contexto
      const match = content.match(/(?:reserva|id|#)\s*:?\s*#?(\d{1,6})/i);
      if (match) return match[1];
    }
    return null;
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const bookingId = getLatestBookingId();
    if (!bookingId) {
      toast.error('Não localizei o número da reserva nesta conversa.');
      return;
    }

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
      
      setMessages(prev => prev.filter(m => m.id !== processingMsg.id));
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `✅ Comprovante da reserva #${bookingId} recebido com sucesso!`,
        timestamp: new Date()
      }]);
    } catch (err: any) {
      setMessages(prev => prev.filter(m => m.id !== processingMsg.id));
      toast.error('Erro ao enviar comprovante.');
    } finally {
      event.target.value = '';
    }
  };

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
      const tenantResp = await api.get(`/settings/public/tenant/${tenant_id}`);
      if (tenantResp.data.name) setPousadaName(tenantResp.data.name);

      const response = await api.get(`/settings/public/${tenant_id}`);
      const aiNameSetting = response.data.find((s: any) => s.key === 'ai_receptionist_name');
      if (aiNameSetting) setAiName(aiNameSetting.value);
    } catch (err) {
      console.error("Erro ao carregar configurações públicas", err);
    }
  };

  const loadHistory = async (sid: string) => {
    try {
      const res = await api.get(`/chat/history/${sid}?tenant_id=${tenant_id}`);
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

    // Lógica de "Auto-Wake": A primeira mensagem ou qualquer mensagem ativa a voz se estiver no mudo/desativada
    // No caso do Guest, sempre enviamos via WebSocket do Assistant para garantir a resposta falada
    voiceAssistantRef.current?.sendTextMessage(userMsg.content);
  };

  const handleLiveTranscription = (text: string, role: 'user' | 'assistant') => {
    setMessages(prev => {
      const lastMsg = prev[prev.length - 1];
      const now = new Date();
      
      // Se for um link markdown ou algo especial, sempre adiciona como nova mensagem
      if (text.includes('](')) {
        return [...prev, { id: 'live-link-' + now.getTime(), role, content: text, timestamp: now }];
      }

      // Se a última mensagem for do mesmo papel e for recente, tentamos atualizar em vez de duplicar
      if (lastMsg && lastMsg.role === role && (now.getTime() - lastMsg.timestamp.getTime() < 8000)) {
        // Se a última mensagem FOR um link, não sobrescreve
        if (lastMsg.content.includes('](')) {
           return [...prev, { id: 'live-' + now.getTime(), role, content: text, timestamp: now }];
        }

        // Se o novo texto contiver o anterior (incremental), substitui para manter fluidez
        if (text.length > lastMsg.content.length && text.startsWith(lastMsg.content)) {
          return [...prev.slice(0, -1), { ...lastMsg, content: text, timestamp: now }];
        }
        
        // Se o texto for diferente e não incremental, mas muito curto, ignoramos para não poluir
        if (text === lastMsg.content) return prev;

        // Se o texto for diferente e não incremental, anexa em vez de substituir
        if (text !== lastMsg.content && !text.startsWith(lastMsg.content)) {
           return [...prev, { id: 'live-' + now.getTime(), role, content: text, timestamp: now }];
        }

        return [...prev.slice(0, -1), { ...lastMsg, content: text, timestamp: now }];
      }
      
      return [...prev, {
        id: 'live-' + now.getTime(),
        role: role,
        content: text,
        timestamp: now
      }];
    });
  };

  return (
    <div className="flex flex-col min-h-[calc(100dvh)] w-full max-w-[1600px] mx-auto p-2 sm:p-6 space-y-4 sm:space-y-6 font-sans">
      {/* Header com Branding e Controles */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white/50 backdrop-blur-md p-4 sm:p-6 rounded-[2rem] border border-white/60 shadow-xl">
        <div className="flex items-center gap-4">
          <div className="relative">
            <div className="w-12 h-12 bg-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-200">
              <Bot className="text-white" size={24} />
            </div>
            <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 border-2 border-white rounded-full"></div>
          </div>
          <div>
            <h1 className="font-black text-slate-800 tracking-tight text-lg leading-tight">{pousadaName}</h1>
            <p className="text-[10px] font-bold text-indigo-600 uppercase tracking-widest">Atendimento Inteligente</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3 w-full md:w-auto overflow-x-auto pb-2 md:pb-0">
          <button
            onClick={() => setIsMuted(!isMuted)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-2xl text-[10px] font-black transition-all border shadow-sm shrink-0 ${
              isMuted 
                ? 'bg-red-50 text-red-600 border-red-200' 
                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
            }`}
          >
            {isMuted ? <MicOff size={14} /> : <Mic size={14} />}
            {isMuted ? 'MICROFONE DESATIVADO' : 'MICROFONE ATIVO'}
          </button>

          <div className="flex bg-slate-100 p-1 rounded-2xl border border-slate-200 shadow-inner shrink-0">
            <button
              onClick={() => setViewMode('voice')}
              className={`px-4 py-2 rounded-xl text-[10px] font-bold transition-all flex items-center gap-2 ${
                viewMode === 'voice' ? 'bg-white text-indigo-600 shadow-md' : 'text-slate-400'
              }`}
            >
              <Headphones size={14} /> VOZ
            </button>
            <button
              onClick={() => setViewMode('chat')}
              className={`px-4 py-2 rounded-xl text-[10px] font-bold transition-all flex items-center gap-2 ${
                viewMode === 'chat' ? 'bg-white text-indigo-600 shadow-md' : 'text-slate-400'
              }`}
            >
              <MessageSquare size={14} /> CHAT
            </button>
          </div>

          <button 
            onClick={() => setMessages([])}
            className="p-2.5 text-slate-400 hover:text-indigo-600 transition-all rounded-xl hover:bg-indigo-50 border border-transparent hover:border-indigo-100 shrink-0"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      {/* Grid Principal */}
      <div className={`grid gap-4 sm:gap-8 flex-1 overflow-hidden transition-all duration-700 grid-cols-1 ${
        viewMode === 'voice' ? 'lg:grid-cols-[1.1fr_0.9fr]' : 'lg:grid-cols-[0.7fr_1.3fr]'
      }`}>
        
        {/* Lado Esquerdo: Assistente Holográfico */}
        <motion.div 
          layout
          className="flex flex-col h-full min-h-[300px] sm:min-h-0"
        >
          <GuestVoiceAssistant 
            ref={voiceAssistantRef}
            tenantId={tenant_id || "0"}
            viewMode={viewMode}
            isMuted={isMuted}
            onMuteChange={setIsMuted}
            onTranscription={handleLiveTranscription}
            agentName={aiName}
          />
          
          <div className="hidden sm:grid grid-cols-2 gap-4 mt-6">
             <div className="bg-white/50 backdrop-blur-sm p-4 rounded-3xl border border-white/60 shadow-sm">
                <p className="text-[9px] uppercase font-black text-slate-400 mb-1 tracking-widest">Status da IA</p>
                <p className="text-xs font-bold text-slate-800 flex items-center gap-2">
                   <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span> {aiName} Online
                </p>
             </div>
             <div className="bg-white/50 backdrop-blur-sm p-4 rounded-3xl border border-white/60 shadow-sm">
                <p className="text-[9px] uppercase font-black text-slate-400 mb-1 tracking-widest">Conexão</p>
                <p className="text-xs font-bold text-indigo-600">Ultra-Baixa Latência</p>
             </div>
          </div>
        </motion.div>

        {/* Lado Direito: Histórico de Chat */}
        <motion.div
          layout
          className="flex flex-col h-full min-h-[400px] sm:min-h-0 overflow-hidden"
        >
          <Card className="flex flex-col shadow-2xl border-white/60 overflow-hidden bg-white/60 backdrop-blur-xl h-full rounded-[2.5rem]">
            <div 
              ref={scrollRef}
              className="flex-1 overflow-y-auto p-4 sm:p-8 space-y-6 scroll-smooth"
            >
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-center space-y-6 opacity-60">
                  <div className="w-20 h-20 bg-indigo-50 rounded-3xl flex items-center justify-center">
                    <MessageSquare className="text-indigo-400" size={32} />
                  </div>
                  <div className="space-y-2">
                    <h3 className="font-black text-slate-800 text-lg">Olá, eu sou a {aiName}!</h3>
                    <p className="text-sm text-slate-500 max-w-[240px] font-medium leading-relaxed">
                      Como posso ajudar em sua estadia hoje? Você pode falar ou digitar.
                    </p>
                  </div>
                </div>
              )}

              {messages.map((msg) => (
                <div 
                  key={msg.id}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in slide-in-from-bottom-4 duration-500`}
                >
                  <div className={`flex items-end gap-3 max-w-[90%] sm:max-w-[85%] ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                    <div className={`w-8 h-8 rounded-xl flex-shrink-0 flex items-center justify-center shadow-lg ${
                      msg.role === 'user' ? 'bg-slate-900 text-white' : 'bg-white text-indigo-600 border border-slate-100'
                    }`}>
                      {msg.role === 'user' ? <User size={14} /> : <Bot size={14} />}
                    </div>
                    <div className={`p-4 sm:p-5 rounded-[1.75rem] text-[14px] font-semibold leading-relaxed shadow-xl backdrop-blur-sm ${
                      msg.role === 'user' 
                        ? 'bg-slate-900 text-white rounded-br-none' 
                        : 'bg-white/90 text-slate-800 border border-slate-100 rounded-bl-none shadow-indigo-50/50'
                    }`}>
                      <ReactMarkdown 
                        className="prose prose-sm max-w-none prose-slate font-medium"
                        components={{
                          a: ({ node, ...props }: any) => (
                            <a href={props.href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 mt-2 bg-indigo-600 text-white px-4 py-2 rounded-xl font-bold hover:bg-indigo-700 transition-all no-underline shadow-md mb-1">
                              <span>🔗</span> {props.children}
                            </a>
                          ),
                          p: ({ children }: any) => <p className="mb-0 whitespace-pre-wrap">{children}</p>
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              ))}
              {loading && <div className="text-[10px] text-slate-400 font-bold animate-pulse uppercase tracking-widest">Processando resposta...</div>}
            </div>

            <CardContent className="p-4 sm:p-6 bg-white/50 border-t border-white/60">
              <form onSubmit={handleSend} className="flex gap-3 max-w-4xl mx-auto relative items-center">
                <div className="relative flex-1 group">
                  <input
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Escreva sua dúvida ou pedido..."
                    className="w-full bg-slate-50/80 border-2 border-transparent rounded-[2rem] pl-6 pr-14 py-4 text-sm focus:bg-white focus:ring-[8px] focus:ring-indigo-500/5 focus:border-indigo-400 outline-none transition-all placeholder:text-slate-300 font-bold shadow-inner"
                  />
                  <button
                    type="submit"
                    disabled={loading || !message.trim()}
                    className="absolute right-2 top-2 bottom-2 aspect-square bg-slate-900 hover:bg-indigo-600 text-white flex items-center justify-center rounded-[1.5rem] shadow-lg transition-all disabled:opacity-20 active:scale-90"
                  >
                    <Send size={18} />
                  </button>
                </div>
                
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-12 h-12 flex-shrink-0 bg-white hover:bg-slate-50 text-slate-400 flex items-center justify-center rounded-2xl transition-all active:scale-90 border-2 border-slate-100 shadow-sm"
                >
                  <Paperclip size={20} />
                </button>
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  className="hidden" 
                  accept="image/*,application/pdf"
                  onChange={handleFileUpload}
                />
              </form>
            </CardContent>
          </Card>
        </motion.div>
      </div>
      
      {/* Footer / Info Mobile */}
      <div className="flex flex-wrap justify-center gap-6 py-2 opacity-60">
        <div className="flex items-center gap-2 text-[8px] text-slate-500 font-black uppercase tracking-[0.2em]">
           <div className="w-1.5 h-1.5 bg-green-500 rounded-full"></div> Atendimento Prioritário
        </div>
        <div className="flex items-center gap-2 text-[8px] text-slate-500 font-black uppercase tracking-[0.2em]">
           <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-ping"></div> ParcerIA v2026
        </div>
      </div>
    </div>
  );
}
