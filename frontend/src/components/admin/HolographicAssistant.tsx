import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Volume2, VolumeX, Sparkles, Send, MessageSquare, Headphones, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface HolographicAssistantProps {
  tenantId: number;
  onTranscription?: (text: string, role: 'user' | 'assistant') => void;
  initialMode?: 'voice' | 'chat';
}

export const HolographicAssistant: React.FC<HolographicAssistantProps> = ({ tenantId, onTranscription, initialMode = 'voice' }) => {
  const [isActive, setIsActive] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [textInput, setTextInput] = useState('');
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  
  const socketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-conectar se mudar para modo Chat
  useEffect(() => {
    if (initialMode === 'chat' && !isActive) {
      connect();
    }
  }, [initialMode]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatMessages]);

  // Sincronizar Mudo com Modo
  useEffect(() => {
    if (initialMode === 'chat') {
      setIsMuted(true);
    } else {
      setIsMuted(false);
    }
  }, [initialMode]);

  const connect = async () => {
    if (isActive) return;
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/admin/live/${tenantId}`;
      
      socketRef.current = new WebSocket(wsUrl);
      
      socketRef.current.onopen = () => {
        setIsActive(true);
        console.log('Conectado ao Holograma Admin Live');
      };
      
      socketRef.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const serverContent = data.server_content || data.serverContent;
        
        const modelTurn = serverContent?.model_turn || serverContent?.modelTurn;
        if (modelTurn?.parts) {
          modelTurn.parts.forEach((part: any) => {
            if (part.thought) return;
            if (part.text) {
              addMessage(part.text, 'assistant');
              if (onTranscription) onTranscription(part.text, 'assistant');
            }
          });
        }

        if (serverContent?.output_transcription?.text || serverContent?.outputTranscription?.text) {
          const text = serverContent.output_transcription?.text || serverContent.outputTranscription?.text;
          if (text) {
             addMessage(text, 'assistant');
             if (onTranscription) onTranscription(text, 'assistant');
          }
        }

        playAudioChunk(data);
      };
      
      socketRef.current.onclose = () => {
        setIsActive(false);
      };

      // Só inicia microfone se não estiver no modo chat
      if (initialMode === 'voice') {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
        const audioContext = new AudioContext({ sampleRate: 16000 });
        audioContextRef.current = audioContext;
        const source = audioContext.createMediaStreamSource(stream);
        const processor = audioContext.createScriptProcessor(4096, 1, 1);
        source.connect(processor);
        processor.connect(audioContext.destination);

        processor.onaudioprocess = (e) => {
          if (socketRef.current?.readyState !== WebSocket.OPEN || isMuted || initialMode === 'chat') return;
          const inputData = e.inputBuffer.getChannelData(0);
          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
          const bytes = new Uint8Array(pcmData.buffer);
          let binary = '';
          for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
          socketRef.current.send(JSON.stringify({ type: 'audio', data: btoa(binary) }));
        };
      }

    } catch (err) {
      console.error('❌ Falha na conexão:', err);
      setIsActive(false);
    }
  };

  const addMessage = (text: string, role: 'user' | 'assistant') => {
    setChatMessages(prev => [...prev, { id: Date.now() + Math.random(), text, role, time: new Date() }]);
  };

  const handleSendText = () => {
    if (!textInput.trim()) return;
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      // Se não estiver conectado, tenta conectar e avisar
      connect().then(() => {
         if (socketRef.current?.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({ type: 'text', data: textInput }));
            addMessage(textInput, 'user');
            if (onTranscription) onTranscription(textInput, 'user');
            setTextInput('');
         }
      });
      return;
    }
    
    socketRef.current.send(JSON.stringify({ type: 'text', data: textInput }));
    addMessage(textInput, 'user');
    if (onTranscription) onTranscription(textInput, 'user');
    setTextInput('');
  };

  const disconnect = () => {
    socketRef.current?.close();
    if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    if (audioContextRef.current) audioContextRef.current.close();
    setIsActive(false);
  };

  const audioContextOutRef = useRef<AudioContext | null>(null);
  const nextStartTimeRef = useRef(0);

  const playAudioChunk = async (data: any) => {
    const serverContent = data.server_content || data.serverContent;
    const modelTurn = serverContent?.model_turn || serverContent?.modelTurn;
    if (modelTurn?.parts) {
      setIsSpeaking(true);
      if (!audioContextOutRef.current) audioContextOutRef.current = new AudioContext({ sampleRate: 24000 });
      for (const part of modelTurn.parts) {
        const inlineData = part.inline_data || part.inlineData;
        if (inlineData?.data) {
          const binaryString = atob(inlineData.data);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i);
          const int16Data = new Int16Array(bytes.buffer);
          const float32Buffer = new Float32Array(int16Data.length);
          for (let i = 0; i < int16Data.length; i++) float32Buffer[i] = int16Data[i] / 0x7FFF;
          const ctx = audioContextOutRef.current;
          const buffer = ctx.createBuffer(1, float32Buffer.length, 24000);
          buffer.getChannelData(0).set(float32Buffer);
          const source = ctx.createBufferSource();
          source.buffer = buffer;
          source.connect(ctx.destination);
          const startTime = Math.max(ctx.currentTime, nextStartTimeRef.current);
          source.start(startTime);
          nextStartTimeRef.current = startTime + buffer.duration;
        }
      }
    }
    if (data.server_content?.turn_complete) {
      setTimeout(() => {
        if (audioContextOutRef.current && audioContextOutRef.current.currentTime >= nextStartTimeRef.current - 0.1) setIsSpeaking(false);
      }, 500);
    }
  };

  return (
    <div className={`flex flex-col items-center justify-between p-6 bg-slate-900 rounded-[2rem] shadow-2xl border border-indigo-500/30 overflow-hidden relative transition-all duration-500 ${
      initialMode === 'chat' ? 'flex-1 w-full h-full' : 'min-h-[500px]'
    }`}>
      {/* Background Glow */}
      <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/10 to-purple-500/10 pointer-events-none" />

      <AnimatePresence mode="wait">
        {initialMode === 'voice' ? (
          <motion.div
            key="voice-layout"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="flex flex-col items-center justify-center flex-1 z-10"
          >
            {/* Hologram Core */}
            <div className="relative mb-12">
              <motion.div 
                animate={{ rotate: 360 }}
                transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
                className="absolute -inset-12 border border-indigo-500/20 rounded-full border-dashed"
              />
              <motion.div
                animate={{
                  scale: isActive ? [1, 1.1, 1] : 1,
                  boxShadow: isActive 
                    ? ["0 0 30px rgba(79, 70, 229, 0.4)", "0 0 80px rgba(79, 70, 229, 0.6)", "0 0 30px rgba(79, 70, 229, 0.4)"]
                    : "0 0 20px rgba(79, 70, 229, 0.2)"
                }}
                transition={{ duration: 2, repeat: Infinity }}
                className={`w-40 h-40 rounded-full bg-gradient-to-br from-indigo-600 to-purple-700 flex items-center justify-center relative cursor-pointer ${!isActive && 'grayscale opacity-50'}`}
                onClick={isActive ? disconnect : connect}
              >
                <Sparkles className={`w-16 h-16 text-white ${isActive ? 'animate-pulse' : ''}`} />
                <div className="absolute -bottom-6 left-1/2 -translate-x-1/2">
                  <span className={`px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest flex items-center gap-2 ${
                    isActive ? 'bg-green-500 text-white shadow-lg' : 'bg-slate-700 text-slate-300'
                  }`}>
                    <div className={`w-2 h-2 rounded-full ${isActive ? 'bg-white animate-ping' : 'bg-slate-500'}`} />
                    {isActive ? 'Live' : 'Offline'}
                  </span>
                </div>
              </motion.div>
            </div>

            <div className="text-center space-y-3 mt-6">
              <h3 className="text-2xl font-black text-white tracking-tight">Ana: Assistente Holográfica</h3>
              <p className="text-slate-400 text-sm max-w-xs mx-auto font-medium">
                {isActive ? (isSpeaking ? 'Ana está processando seu pedido...' : 'Estou ouvindo. Pode falar.') : 'Clique no núcleo para iniciar a conversa'}
              </p>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="chat-layout"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="flex flex-col w-full h-full z-10 relative"
          >
            {/* Header do Chat */}
            <div className="flex items-center justify-between pb-4 border-b border-white/10 mb-4">
               <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center">
                     <Bot className="text-white" size={20} />
                  </div>
                  <div>
                     <h4 className="text-white font-bold">Ana (Chat)</h4>
                     <p className="text-[10px] text-green-400 font-bold uppercase tracking-wider">Online & Pronta</p>
                  </div>
               </div>
               {!isActive && (
                 <button onClick={connect} className="text-[10px] bg-indigo-600 text-white px-3 py-1 rounded-lg font-bold hover:bg-indigo-500 transition-all">
                    CONECTAR
                 </button>
               )}
            </div>

            {/* Lista de Mensagens */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-4 pr-2 mb-4 custom-scrollbar">
               {chatMessages.length === 0 && (
                 <div className="flex flex-col items-center justify-center h-full text-center p-8 opacity-50">
                    <MessageSquare size={48} className="text-indigo-400 mb-4" />
                    <p className="text-white font-medium">Inicie uma conversa por texto com a Ana.</p>
                    <p className="text-slate-400 text-xs mt-2">Ela pode criar relatórios, verificar quartos e muito mais.</p>
                 </div>
               )}
               {chatMessages.map(msg => (
                 <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] p-4 rounded-2xl text-sm ${
                       msg.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-none' : 'bg-slate-800 text-slate-200 rounded-tl-none border border-slate-700'
                    }`}>
                       <ReactMarkdown components={{
                          a: ({node, ...props}) => <a {...props} target="_blank" className="text-indigo-400 underline font-bold" />
                       }}>
                          {msg.text}
                       </ReactMarkdown>
                    </div>
                 </div>
               ))}
            </div>

            {/* Input de Texto */}
            <div className="relative">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
                placeholder="Digite seu comando para a Ana..."
                className="w-full bg-slate-800 border border-slate-700 rounded-2xl py-4 pl-6 pr-14 text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition-all shadow-2xl"
              />
              <button
                onClick={handleSendText}
                disabled={!textInput.trim()}
                className={`absolute right-2 top-1/2 -translate-y-1/2 p-2.5 rounded-xl transition-all ${
                  textInput.trim() ? 'bg-indigo-600 text-white hover:bg-indigo-500' : 'bg-slate-700 text-slate-500'
                }`}
              >
                <Send size={20} />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Footer Controls (Só voz) */}
      {initialMode === 'voice' && (
        <div className="flex gap-4 mt-8 relative z-10">
          <button 
            onClick={() => setIsMuted(!isMuted)}
            className={`p-4 rounded-2xl transition-all shadow-lg ${isMuted ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-slate-800 text-slate-400 hover:text-white border border-slate-700'}`}
          >
            {isMuted ? <MicOff size={24} /> : <Mic size={24} />}
          </button>
          <button onClick={disconnect} className="px-8 py-4 bg-slate-800 hover:bg-red-500/20 text-slate-400 hover:text-red-400 rounded-2xl font-black transition-all border border-slate-700 hover:border-red-500/30 shadow-lg uppercase tracking-widest text-xs">
            Desligar
          </button>
        </div>
      )}

      {/* Grid Floor Effect */}
      <div className="absolute bottom-0 inset-x-0 h-32 bg-[linear-gradient(to_bottom,transparent,rgba(79,70,229,0.05)_50%,rgba(79,70,229,0.1))] perspective-[1000px] pointer-events-none">
        <div className="absolute inset-0 bg-[grid-white-5] [mask-image:linear-gradient(to_top,white,transparent)]" />
      </div>
    </div>
  );
};
