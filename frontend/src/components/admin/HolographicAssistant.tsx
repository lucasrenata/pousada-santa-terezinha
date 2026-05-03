import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Volume2, VolumeX, Sparkles, Send, MessageSquare, Headphones } from 'lucide-react';

interface HolographicAssistantProps {
  tenantId: number;
  onTranscription?: (text: string, role: 'user' | 'assistant') => void;
}

export const HolographicAssistant: React.FC<HolographicAssistantProps> = ({ tenantId, onTranscription }) => {
  const [isActive, setIsActive] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [mode, setMode] = useState<'voice' | 'chat'>('voice');
  const [textInput, setTextInput] = useState('');
  
  const socketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Efeito Visual de Ondas (Simulação de áudio)
  useEffect(() => {
    if (isActive && !isSpeaking && mode === 'voice') {
      const interval = setInterval(() => {
        setAudioLevel(Math.random() * 0.3 + 0.1);
      }, 150);
      return () => clearInterval(interval);
    }
  }, [isActive, isSpeaking, mode]);

  // Sincronizar Mudo com Modo
  useEffect(() => {
    if (mode === 'chat') {
      setIsMuted(true);
    } else {
      setIsMuted(false);
    }
  }, [mode]);

  const toggleConnection = async () => {
    if (isActive) {
      disconnect();
    } else {
      await connect();
    }
  };

  const connect = async () => {
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
        
        // Tratar Transcrições e Partes de Texto
        const serverContent = data.server_content || data.serverContent;
        if (serverContent?.input_transcription?.text || serverContent?.inputTranscription?.text) {
          const text = serverContent.input_transcription?.text || serverContent.inputTranscription?.text;
          if (text && onTranscription) onTranscription(text, 'user');
        }

        const modelTurn = serverContent?.model_turn || serverContent?.modelTurn;
        if (modelTurn?.parts) {
          modelTurn.parts.forEach((part: any) => {
            if (part.thought) return;
            if (part.text && onTranscription) {
              onTranscription(part.text, 'assistant');
            }
          });
        }

        if (serverContent?.output_transcription?.text || serverContent?.outputTranscription?.text) {
          const text = serverContent.output_transcription?.text || serverContent.outputTranscription?.text;
          if (text && onTranscription) onTranscription(text, 'assistant');
        }

        // Tratar Áudio e Estado de Fala
        playAudioChunk(data);
      };
      
      socketRef.current.onclose = () => {
        setIsActive(false);
        console.log('Conexão encerrada');
      };

      // Iniciar Microfone e Streaming
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: 16000 });
      await audioContext.resume();
      
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);

      source.connect(processor);
      processor.connect(audioContext.destination);

      processor.onaudioprocess = (e) => {
        if (socketRef.current?.readyState !== WebSocket.OPEN || isMuted || mode === 'chat') return;
        
        const inputData = e.inputBuffer.getChannelData(0);
        const pcmData = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
        }
        
        const bytes = new Uint8Array(pcmData.buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        const base64Audio = btoa(binary);
        
        socketRef.current.send(JSON.stringify({
          type: 'audio',
          data: base64Audio
        }));
      };

    } catch (err) {
      console.error('❌ Falha na conexão:', err);
      setIsActive(false);
    }
  };

  const handleSendText = () => {
    if (!textInput.trim() || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;
    
    // Enviar texto para o Gemini via WebSocket
    socketRef.current.send(JSON.stringify({
      type: 'text',
      data: textInput
    }));
    
    // Adicionar localmente ao histórico (via prop)
    if (onTranscription) onTranscription(textInput, 'user');
    setTextInput('');
  };

  const disconnect = () => {
    socketRef.current?.close();
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
    }
    setIsActive(false);
  };

  const audioContextOutRef = useRef<AudioContext | null>(null);
  const nextStartTimeRef = useRef(0);

  const playAudioChunk = async (data: any) => {
    const serverContent = data.server_content || data.serverContent;
    const modelTurn = serverContent?.model_turn || serverContent?.modelTurn;
    
    if (modelTurn?.parts) {
      setIsSpeaking(true);
      if (!audioContextOutRef.current) {
        audioContextOutRef.current = new AudioContext({ sampleRate: 24000 });
      }

      for (const part of modelTurn.parts) {
        const inlineData = part.inline_data || part.inlineData;
        if (inlineData?.data) {
          const audioB64 = inlineData.data;
          const binaryString = atob(audioB64);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          
          const int16Data = new Int16Array(bytes.buffer);
          const float32Buffer = new Float32Array(int16Data.length);
          for (let i = 0; i < int16Data.length; i++) {
            float32Buffer[i] = int16Data[i] / 0x7FFF;
          }
          
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
        if (audioContextOutRef.current && audioContextOutRef.current.currentTime >= nextStartTimeRef.current - 0.1) {
          setIsSpeaking(false);
        }
      }, 500);
    }

    if (data.server_content?.interrupted) {
      setIsSpeaking(false);
      nextStartTimeRef.current = 0;
      if (audioContextOutRef.current) {
        audioContextOutRef.current.close();
        audioContextOutRef.current = new AudioContext({ sampleRate: 24000 });
      }
    }
  };

  return (
    <div className="flex flex-col items-center justify-between p-8 bg-slate-900 rounded-[2rem] shadow-2xl border border-indigo-500/30 overflow-hidden relative min-h-[500px]">
      {/* Background Glow */}
      <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/10 to-purple-500/10 pointer-events-none" />
      
      {/* Mode Toggle Switch */}
      <div className="relative z-20 flex bg-slate-800/50 p-1 rounded-xl border border-slate-700 mb-6">
        <button
          onClick={() => setMode('voice')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
            mode === 'voice' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Headphones size={14} /> MODO VOZ
        </button>
        <button
          onClick={() => setMode('chat')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
            mode === 'chat' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <MessageSquare size={14} /> MODO CHAT
        </button>
      </div>

      <AnimatePresence mode="wait">
        {mode === 'voice' ? (
          <motion.div
            key="voice-mode"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="flex flex-col items-center justify-center flex-1"
          >
            {/* Hologram Core */}
            <div className="relative mb-12">
              <motion.div 
                animate={{ rotate: 360 }}
                transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
                className="absolute -inset-8 border border-indigo-500/20 rounded-full border-dashed"
              />
              <motion.div
                animate={{
                  scale: isActive ? [1, 1.1, 1] : 1,
                  boxShadow: isActive 
                    ? ["0 0 20px rgba(79, 70, 229, 0.4)", "0 0 60px rgba(79, 70, 229, 0.6)", "0 0 20px rgba(79, 70, 229, 0.4)"]
                    : "0 0 20px rgba(79, 70, 229, 0.2)"
                }}
                transition={{ duration: 2, repeat: Infinity }}
                className={`w-32 h-32 rounded-full bg-gradient-to-br from-indigo-600 to-purple-700 flex items-center justify-center relative cursor-pointer ${!isActive && 'grayscale opacity-50'}`}
                onClick={toggleConnection}
              >
                <Sparkles className={`w-12 h-12 text-white ${isActive ? 'animate-pulse' : ''}`} />
                <div className="absolute -bottom-4 left-1/2 -translate-x-1/2">
                  <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest flex items-center gap-1 ${
                    isActive ? 'bg-green-500 text-white shadow-lg' : 'bg-slate-700 text-slate-300'
                  }`}>
                    {isActive ? 'Live' : 'Offline'}
                  </span>
                </div>
              </motion.div>
            </div>

            <div className="text-center space-y-2 mt-4">
              <h3 className="text-xl font-bold text-white tracking-tight">Ana: Assistente de Voz</h3>
              <p className="text-slate-400 text-sm max-w-xs mx-auto">
                {isActive ? (isSpeaking ? 'Ana está falando...' : 'Ouvindo você...') : 'Clique no núcleo para iniciar'}
              </p>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="chat-mode"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="flex flex-col w-full max-w-md space-y-6 flex-1 pt-4"
          >
            <div className="bg-slate-800/30 p-6 rounded-3xl border border-indigo-500/10 flex-1 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-full bg-indigo-500/20 flex items-center justify-center mb-4">
                <MessageSquare className="text-indigo-400" size={32} />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">Modo Chat Ativado</h3>
              <p className="text-slate-400 text-sm">
                Envie comandos de texto para a Ana. Ela processará relatórios e pedidos da mesma forma.
              </p>
            </div>

            <div className="relative group">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
                placeholder={isActive ? "Digite sua dúvida ou comando..." : "Conecte primeiro para conversar..."}
                disabled={!isActive}
                className="w-full bg-slate-800 border border-slate-700 rounded-2xl py-4 pl-6 pr-14 text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition-all shadow-xl"
              />
              <button
                onClick={handleSendText}
                disabled={!isActive || !textInput.trim()}
                className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-xl transition-all ${
                  isActive && textInput.trim() ? 'bg-indigo-600 text-white hover:bg-indigo-500' : 'bg-slate-700 text-slate-500'
                }`}
              >
                <Send size={20} />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Footer Controls */}
      <div className="flex gap-4 mt-8 relative z-10">
        {!isActive ? (
          <button 
            onClick={connect}
            className="px-8 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-bold transition-all shadow-lg flex items-center gap-2"
          >
            <Sparkles size={18} /> CONECTAR ANA
          </button>
        ) : (
          <>
            {mode === 'voice' && (
              <button 
                onClick={() => setIsMuted(!isMuted)}
                className={`p-3 rounded-2xl transition-all ${isMuted ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
              >
                {isMuted ? <MicOff size={20} /> : <Mic size={20} />}
              </button>
            )}
            <button 
              onClick={disconnect}
              className="px-6 py-3 bg-slate-800 hover:bg-red-500/20 text-slate-400 hover:text-red-400 rounded-2xl font-bold transition-all border border-transparent hover:border-red-500/30"
            >
              ENCERRAR
            </button>
          </>
        )}
      </div>

      {/* Grid Floor Effect */}
      <div className="absolute bottom-0 inset-x-0 h-24 bg-[linear-gradient(to_bottom,transparent,rgba(79,70,229,0.05)_50%,rgba(79,70,229,0.1))] perspective-[1000px] pointer-events-none">
        <div className="absolute inset-0 bg-[grid-white-5] [mask-image:linear-gradient(to_top,white,transparent)]" />
      </div>
    </div>
  );
};
