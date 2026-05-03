import { useState, useEffect, useRef } from 'react';
import { Send, User, Check, AlertCircle, Mic, Square } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import api from '../services/api';
import { Card, CardContent } from '../components/ui/card';
import { HolographicAssistant } from '../components/admin/HolographicAssistant';

export default function Chat() {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const tenantId = localStorage.getItem('tenant_id') ? Number(localStorage.getItem('tenant_id')) : 1;

  useEffect(() => {
    let sid = localStorage.getItem('chat_session_admin');
    if (!sid) {
      sid = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
      localStorage.setItem('chat_session_admin', sid);
    }
    setSessionId(sid);
    loadHistory(sid);
  }, []);

  const loadHistory = async (sid: string) => {
    try {
      const res = await api.get(`/chat/history/${sid}`, { params: { tenant_id: tenantId } });
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

  const handleSend = async (e?: React.FormEvent, textOverride?: string) => {
    e?.preventDefault();
    const finalMessage = textOverride || message;
    if (!finalMessage.trim() || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: finalMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMsg]);
    setMessage('');
    setLoading(true);

    try {
      const res = await api.post('/chat/admin', {
        message: userMsg.content,
        session_id: sessionId,
        tenant_id: tenantId
      });

      const { job_id } = res.data;

      const pollJob = async () => {
        try {
          const statusRes = await api.get(`/chat/job/${job_id}`);
          const { status, result, error } = statusRes.data;

          if (status === 'finished') {
            const botMsg: Message = {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content: result.response,
              timestamp: new Date()
            };
            setMessages(prev => [...prev, botMsg]);
            setLoading(false);
          } else if (status === 'failed') {
            throw new Error(error || "Erro no processamento do Admin Agent");
          } else {
            setTimeout(pollJob, 2000);
          }
        } catch (err) {
          console.error("Erro no polling Admin:", err);
          setMessages(prev => [...prev, {
            id: 'err-' + Date.now(),
            role: 'assistant',
            content: "Não consegui processar sua solicitação agora. Pode tentar novamente em instantes?",
            timestamp: new Date()
          }]);
          setLoading(false);
        }
      };

      setTimeout(pollJob, 1000);

    } catch (error) {
      console.error('Erro ao iniciar chat admin:', error);
      setMessages(prev => [...prev, {
        id: 'err-init',
        role: 'assistant',
        content: "Oops! Tive um problema em conectar com o assistente. Verifique sua conexão.",
        timestamp: new Date()
      }]);
      setLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await handleTranscription(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };
      recorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Erro ao acessar microfone:', err);
      alert('Não foi possível acessar o microfone. Verifique as permissões do seu navegador.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleTranscription = async (blob: Blob) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('audio', blob, 'recording.webm');
      const res = await api.post('/chat/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      if (res.data.text) {
        await handleSend(undefined, res.data.text);
      }
    } catch (error) {
      console.error('Erro na transcrição:', error);
      alert('Falha ao transcrever áudio.');
    } finally {
      setLoading(false);
    }
  };

  const handleLiveTranscription = (text: string, role: 'user' | 'assistant') => {
    setMessages(prev => {
      const lastMsg = prev[prev.length - 1];
      const now = new Date();
      
      // Se a última mensagem for do mesmo papel e for recente
      if (lastMsg && lastMsg.role === role && (now.getTime() - lastMsg.timestamp.getTime() < 5000)) {
        // Se o novo texto contiver o anterior (incremental), substitui
        if (text.startsWith(lastMsg.content)) {
          return [...prev.slice(0, -1), { ...lastMsg, content: text, timestamp: now }];
        }
        // Se for um link ou um texto diferente, anexa ou cria nova
        if (text.includes('](')) { // É um link markdown
           return [...prev, { id: 'live-' + now.getTime(), role, content: text, timestamp: now }];
        }
        // Caso contrário, apenas atualiza para manter a fluidez da fala
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
    <div className="flex flex-col h-[calc(100dvh-80px)] sm:h-[calc(100vh-100px)] w-full max-w-[1600px] mx-auto p-4 space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-4xl font-black text-slate-900 tracking-tight">Centro de Comando</h2>
          <p className="text-slate-500 font-medium">Gestão Administrativa Holográfica & Relatórios</p>
        </div>
        <div className="hidden md:flex gap-4 px-2">
          <div className="flex items-center gap-2 text-xs text-slate-400 font-medium bg-white px-3 py-1.5 rounded-full shadow-sm border">
            <Check size={14} className="text-green-500" /> IA Ativada
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400 font-medium bg-white px-3 py-1.5 rounded-full shadow-sm border">
             <AlertCircle size={14} className="text-indigo-500" /> Admin Live Mode
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 flex-1 overflow-hidden">
        {/* Coluna Esquerda: Holograma */}
        <div className="flex flex-col h-full">
          <HolographicAssistant 
            tenantId={tenantId} 
            onTranscription={handleLiveTranscription}
          />
          
          {/* Quick Stats or Info below Hologram */}
          <div className="mt-6 grid grid-cols-3 gap-4">
             <div className="bg-white p-4 rounded-3xl border border-slate-100 shadow-sm">
                <p className="text-[10px] uppercase font-bold text-slate-400 mb-1">Status</p>
                <p className="text-sm font-bold text-slate-800">Operacional</p>
             </div>
             <div className="bg-white p-4 rounded-3xl border border-slate-100 shadow-sm">
                <p className="text-[10px] uppercase font-bold text-slate-400 mb-1">Voz</p>
                <p className="text-sm font-bold text-slate-800">Ana v2.5</p>
             </div>
             <div className="bg-white p-4 rounded-3xl border border-slate-100 shadow-sm">
                <p className="text-[10px] uppercase font-bold text-slate-400 mb-1">Latência</p>
                <p className="text-sm font-bold text-green-500">Ultra-Baixa</p>
             </div>
          </div>
        </div>

        {/* Coluna Direita: Chat */}
        <Card className="flex flex-col shadow-2xl border-slate-200 overflow-hidden bg-white/80 backdrop-blur-sm h-full rounded-[2rem]">
          <div 
            ref={scrollRef}
            className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 scroll-smooth"
          >
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
                <div className="p-4 bg-slate-50 rounded-3xl border border-slate-100 w-24 h-24 flex items-center justify-center">
                  <img src="/ai-avatar.jpg" alt="AI Robot" className="w-full h-full object-cover rounded-2xl" />
                </div>
                <h3 className="font-bold text-slate-800 text-lg">Histórico de Relatórios</h3>
                <p className="text-sm text-slate-500 max-w-xs">
                  As respostas detalhadas e documentos gerados pela Ana aparecerão aqui.
                </p>
              </div>
            )}

            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2`}>
                <div className={`flex gap-3 max-w-[90%] ${m.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                  <div className={`p-4 rounded-2xl text-sm shadow-sm ${
                    m.role === 'user' 
                      ? 'bg-indigo-600 text-white rounded-tr-none' 
                      : 'bg-slate-50 text-slate-800 rounded-tl-none border border-slate-100'
                  }`}>
                    <ReactMarkdown 
                      components={{
                        a: ({ node, ...props }: any) => (
                          <a href={props.href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 mt-2 bg-white text-indigo-700 px-4 py-2 rounded-lg font-bold border border-indigo-200 hover:bg-indigo-50 transition-all no-underline shadow-sm mb-1">
                            <span>📄</span> {props.children}
                          </a>
                        ),
                        p: ({ children }: any) => <p className="mb-0 whitespace-pre-wrap">{children}</p>
                      }}
                    >
                      {m.content}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            ))}
            {loading && <div className="text-xs text-slate-400 italic">Ana está processando...</div>}
          </div>

          <CardContent className="p-4 bg-slate-50/50 border-t border-slate-100">
            <form onSubmit={(e) => handleSend(e)} className="flex gap-2">
              <input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Digite aqui ou fale com a Ana ao lado..."
                className="flex-1 bg-white border border-slate-200 rounded-2xl px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              />
              <button type="submit" disabled={loading || !message.trim()} className="bg-indigo-600 hover:bg-indigo-700 text-white p-3 rounded-2xl shadow-lg transition-all disabled:opacity-50">
                <Send size={20} />
              </button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}
