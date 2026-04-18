import { useState, useEffect, useRef } from 'react';
import { Send, User, Check, AlertCircle, Mic, Square } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import api from '../services/api';
import { Card, CardContent } from '../components/ui/card';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export default function Chat() {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

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
      const tenantId = localStorage.getItem('tenant_id') ? Number(localStorage.getItem('tenant_id')) : 0;
      const res = await api.post('/chat/admin', {
        message: userMsg.content,
        session_id: sessionId,
        tenant_id: tenantId
      });

      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: res.data.response,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, botMsg]);
    } catch (error) {
      console.error('Erro no chat:', error);
      setMessages(prev => [...prev, {
        id: 'err',
        role: 'assistant',
        content: "Oops! Tive um problema em processar sua solicitação. Verifique sua conexão ou tente novamente mais tarde.",
        timestamp: new Date()
      }]);
    } finally {
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

  return (
    <div className="flex flex-col h-[calc(100dvh-100px)] sm:h-[calc(100vh-120px)] max-w-5xl mx-auto space-y-4 px-2 sm:px-0">
      <div>
        <h2 className="text-3xl font-black text-slate-900 tracking-tight">Assistente Administrativo</h2>
        <p className="text-slate-500 font-medium">Relatórios, estoque e gestão inteligente via IA</p>
      </div>

      <Card className="flex-1 flex flex-col shadow-xl border-slate-200 overflow-hidden bg-slate-50/50">
        {/* Mensagens */}
        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 scroll-smooth"
        >
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-4 animate-in fade-in zoom-in duration-500">
              <div className="p-4 bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden w-24 h-24 flex items-center justify-center">
                <img src="/ai-avatar.jpg" alt="AI Robot" className="w-full h-full object-cover" />
              </div>
              <div>
                <h3 className="font-bold text-slate-800 text-lg">Olá Admin! Como posso ajudar?</h3>
                <p className="text-sm text-slate-500 max-w-xs">
                  Posso gerar relatórios financeiros, verificar estoque, consultar reservas e mais.
                </p>
              </div>
            </div>
          )}

          {messages.map((m) => (
            <div 
              key={m.id} 
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-in slide-in-from-bottom-2 duration-300`}
            >
              <div className={`flex gap-3 max-w-[90%] sm:max-w-[80%] ${m.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 overflow-hidden ${
                  m.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white border text-slate-600 shadow-sm'
                }`}>
                  {m.role === 'user' ? <User size={16} /> : <img src="/ai-avatar.jpg" alt="Bot" className="w-full h-full object-cover" />}
                </div>
                <div className={`p-4 rounded-2xl text-sm leading-relaxed shadow-sm ${
                  m.role === 'user' 
                    ? 'bg-indigo-600 text-white rounded-tr-none' 
                    : 'bg-white text-slate-800 rounded-tl-none border border-slate-100'
                }`}>
                  <ReactMarkdown 
                    components={{
                      a: ({ node, ...props }: any) => (
                        <a 
                          {...props} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-2 mt-2 bg-indigo-50 text-indigo-700 px-4 py-2 rounded-lg font-bold border border-indigo-200 hover:bg-indigo-100 transition-all no-underline shadow-sm mb-1"
                        >
                          <span>📄</span> {props.children}
                        </a>
                      ),
                      p: ({ children }: any) => <p className="mb-0 whitespace-pre-wrap">{children}</p>
                    }}
                  >
                    {m.content}
                  </ReactMarkdown>
                  <span className={`text-[10px] mt-2 block opacity-50 ${m.role === 'user' ? 'text-right' : 'text-left'}`}>
                    {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start animate-pulse">
              <div className="bg-white border border-slate-100 p-4 rounded-2xl rounded-tl-none shadow-sm flex gap-2">
                <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce delay-100" />
                <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce delay-200" />
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <CardContent className="p-3 sm:p-4 bg-white border-t border-slate-100">
          <form onSubmit={(e) => handleSend(e)} className="flex gap-2 sm:gap-3">
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={isRecording ? "Ouvindo..." : "Solicite um relatório, dados de estoque, reservas..."}
              className={`flex-1 bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all ${isRecording ? 'animate-pulse ring-2 ring-red-500' : ''}`}
            />
            
            <button
              type="button"
              onClick={isRecording ? stopRecording : startRecording}
              disabled={loading}
              className={`p-3 rounded-xl shadow-lg transition-all ${
                isRecording 
                  ? 'bg-red-500 text-white animate-pulse' 
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {isRecording ? <Square size={20} /> : <Mic size={20} />}
            </button>

            <button
              type="submit"
              disabled={loading || !message.trim() || isRecording}
              className="bg-indigo-600 hover:bg-indigo-700 text-white p-3 rounded-xl shadow-lg shadow-indigo-200 transition-all disabled:opacity-50 disabled:shadow-none"
            >
              <Send size={20} />
            </button>
          </form>
        </CardContent>
      </Card>
      
      {/* Footer Tips */}
      <div className="flex flex-wrap gap-4 px-2">
        <div className="flex items-center gap-2 text-xs text-slate-400 font-medium">
          <Check size={14} className="text-green-500" /> IA do Sistema Ativada
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400 font-medium">
           <AlertCircle size={14} className="text-indigo-500" /> Assistente Administrativo
        </div>
      </div>
    </div>
  );
}
