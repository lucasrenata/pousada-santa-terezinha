import { useState, useEffect, useRef } from 'react';
import { Send, User, Bot, Check, AlertCircle } from 'lucide-react';
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
      const res = await api.post('/chat/admin', {
        message: userMsg.content,
        session_id: sessionId
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

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] max-w-5xl mx-auto space-y-4">
      <div>
        <h2 className="text-3xl font-black text-slate-900 tracking-tight">Assistente Administrativo</h2>
        <p className="text-slate-500 font-medium">Relatórios, estoque e gestão inteligente via IA</p>
      </div>

      <Card className="flex-1 flex flex-col shadow-xl border-slate-200 overflow-hidden bg-slate-50/50">
        {/* Mensagens */}
        <div 
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-6 space-y-4 scroll-smooth"
        >
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-4 animate-in fade-in zoom-in duration-500">
              <div className="p-4 bg-white rounded-3xl shadow-sm border border-slate-100">
                <Bot size={48} className="text-indigo-500" />
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
              <div className={`flex gap-3 max-w-[80%] ${m.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  m.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white border text-slate-600 shadow-sm'
                }`}>
                  {m.role === 'user' ? <User size={16} /> : <Bot size={16} />}
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
        <CardContent className="p-4 bg-white border-t border-slate-100">
          <form onSubmit={handleSend} className="flex gap-3">
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Solicite um relatório, dados de estoque, reservas..."
              className="flex-1 bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
            />
            <button
              type="submit"
              disabled={loading || !message.trim()}
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
          <Check size={14} className="text-green-500" /> GPT-4o Mini Ativado
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400 font-medium">
           <AlertCircle size={14} className="text-indigo-500" /> Assistente Administrativo
        </div>
      </div>
    </div>
  );
}
