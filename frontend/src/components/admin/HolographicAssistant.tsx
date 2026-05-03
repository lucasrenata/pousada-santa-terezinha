import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Volume2, VolumeX, Sparkles } from 'lucide-react';

interface HolographicAssistantProps {
  tenantId: number;
  onTranscription?: (text: string, role: 'user' | 'assistant') => void;
}

export const HolographicAssistant: React.FC<HolographicAssistantProps> = ({ tenantId, onTranscription }) => {
  const [isActive, setIsActive] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  
  const socketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Efeito Visual de Ondas (Simulação de áudio)
  useEffect(() => {
    if (isActive && !isSpeaking) {
      const interval = setInterval(() => {
        setAudioLevel(Math.random() * 0.3 + 0.1);
      }, 150);
      return () => clearInterval(interval);
    }
  }, [isActive, isSpeaking]);

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

        // Se houver turn do modelo com texto (ex: links de relatórios)
        const modelTurn = serverContent?.model_turn || serverContent?.modelTurn;
        if (modelTurn?.parts) {
          modelTurn.parts.forEach((part: any) => {
            // Filtrar partes que são apenas pensamentos/raciocínio interno da IA
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
      console.log('🎙️ Microfone acessado com sucesso');
      streamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: 16000 });
      await audioContext.resume();
      console.log(`🎙️ AudioContext iniciado a ${audioContext.sampleRate}Hz`);
      
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);

      source.connect(processor);
      processor.connect(audioContext.destination);

      processor.onaudioprocess = (e) => {
        // Usar o readyState do socket diretamente para evitar problemas de closure
        if (socketRef.current?.readyState !== WebSocket.OPEN || isMuted) return;
        
        const inputData = e.inputBuffer.getChannelData(0);
        // Converter Float32 para Int16 (PCM)
        const pcmData = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
        }
        
        // Converter para Base64 e enviar
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
      console.error('❌ Falha ao acessar microfone ou configurar áudio:', err);
      setIsActive(false);
    }
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
          
          // Converter Int16 PCM para Float32
          const int16Data = new Int16Array(bytes.buffer);
          const float32Buffer = new Float32Array(int16Data.length);
          for (let i = 0; i < int16Data.length; i++) {
            float32Buffer[i] = int16Data[i] / 0x7FFF;
          }
          
          // Agendar reprodução
          const ctx = audioContextOutRef.current;
          const buffer = ctx.createBuffer(1, float32Buffer.length, 24000);
          buffer.getChannelData(0).set(float32Buffer);
          
          const source = ctx.createBufferSource();
          source.buffer = buffer;
          source.connect(ctx.destination);
          
          const startTime = Math.max(ctx.currentTime, nextStartTimeRef.current);
          source.start(startTime);
          nextStartTimeRef.current = startTime + buffer.duration;

          source.onended = () => {
            if (ctx.currentTime >= nextStartTimeRef.current - 0.1) {
               // setIsSpeaking(false); // Só desativa se for o último chunk
            }
          };
        }
      }
    }
    
    // Detectar fim de fala ou interrupção
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
      // Parar áudio atual se necessário
      if (audioContextOutRef.current) {
        audioContextOutRef.current.close();
        audioContextOutRef.current = new AudioContext({ sampleRate: 24000 });
      }
    }
  };

  return (
    <div className="flex flex-col items-center justify-center p-8 bg-slate-900 rounded-[2rem] shadow-2xl border border-indigo-500/30 overflow-hidden relative min-h-[400px]">
      {/* Background Glow */}
      <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/10 to-purple-500/10 pointer-events-none" />
      
      {/* Hologram Core */}
      <div className="relative z-10 flex flex-col items-center">
        <div className="relative mb-12">
          {/* Outer Rings */}
          <motion.div 
            animate={{ rotate: 360 }}
            transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
            className="absolute -inset-8 border border-indigo-500/20 rounded-full border-dashed"
          />
          <motion.div 
            animate={{ rotate: -360 }}
            transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
            className="absolute -inset-4 border border-purple-500/20 rounded-full border-dotted"
          />

          {/* Main Sphere */}
          <motion.div
            animate={{
              scale: isActive ? [1, 1.1, 1] : 1,
              boxShadow: isActive 
                ? [
                    "0 0 20px rgba(79, 70, 229, 0.4)",
                    "0 0 60px rgba(79, 70, 229, 0.6)",
                    "0 0 20px rgba(79, 70, 229, 0.4)"
                  ]
                : "0 0 20px rgba(79, 70, 229, 0.2)"
            }}
            transition={{ duration: 2, repeat: Infinity }}
            className={`w-32 h-32 rounded-full bg-gradient-to-br from-indigo-600 to-purple-700 flex items-center justify-center relative cursor-pointer overflow-hidden ${!isActive && 'grayscale opacity-50'}`}
            onClick={toggleConnection}
          >
            {/* Energy Waves */}
            <AnimatePresence>
              {isActive && (
                <motion.div
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 2, opacity: [0, 0.5, 0] }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="absolute inset-0 bg-indigo-400 rounded-full pointer-events-none"
                />
              )}
            </AnimatePresence>
            
            <Sparkles className={`w-12 h-12 text-white transition-all ${isActive ? 'animate-pulse' : ''}`} />
          </motion.div>

          {/* Status Badge */}
          <div className="absolute -bottom-4 left-1/2 -translate-x-1/2">
            <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest flex items-center gap-1 ${
              isActive ? 'bg-green-500 text-white shadow-[0_0_10px_rgba(34,197,94,0.5)]' : 'bg-slate-700 text-slate-300'
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-white animate-ping' : 'bg-slate-500'}`} />
              {isActive ? 'Live' : 'Offline'}
            </span>
          </div>
        </div>

        <div className="text-center space-y-2">
          <h3 className="text-xl font-bold text-white tracking-tight">Ana: Assistente Holográfica</h3>
          <p className="text-slate-400 text-sm max-w-xs mx-auto">
            {isActive 
              ? (isSpeaking ? 'Ana está falando...' : 'Ouvindo você...') 
              : 'Clique no núcleo para iniciar a conversa por voz'}
          </p>
        </div>

        {/* Controls */}
        <div className="flex gap-4 mt-8">
          <button 
            onClick={() => setIsMuted(!isMuted)}
            className={`p-3 rounded-2xl transition-all ${isMuted ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
          >
            {isMuted ? <MicOff size={20} /> : <Mic size={20} />}
          </button>
          <button className="p-3 rounded-2xl bg-slate-800 text-slate-400 hover:text-white transition-all">
            <Volume2 size={20} />
          </button>
        </div>
      </div>

      {/* Grid Floor Effect */}
      <div className="absolute bottom-0 inset-x-0 h-24 bg-[linear-gradient(to_bottom,transparent,rgba(79,70,229,0.05)_50%,rgba(79,70,229,0.1))] perspective-[1000px]">
        <div className="absolute inset-0 bg-[grid-white-5] [mask-image:linear-gradient(to_top,white,transparent)]" />
      </div>
    </div>
  );
};
