import { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import { Mic, MicOff, MessageSquare, Bot, X, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export interface GuestVoiceAssistantRef {
  sendTextMessage: (text: string) => void;
}

interface GuestVoiceAssistantProps {
  tenantId: string;
  onTranscription?: (text: string, role: 'user' | 'assistant') => void;
  onClose?: () => void;
  isMuted?: boolean;
  onMuteChange?: (muted: boolean) => void;
  viewMode?: 'voice' | 'chat';
  agentName?: string;
}

export const GuestVoiceAssistant = forwardRef<GuestVoiceAssistantRef, GuestVoiceAssistantProps>(({ 
  tenantId, 
  onTranscription,
  onClose,
  isMuted: controlledIsMuted,
  onMuteChange,
  viewMode = 'voice',
  agentName = 'Ana'
}, ref) => {
// ... (rest of component)
  const [isActive, setIsActive] = useState(false);
  const [internalIsMuted, setInternalIsMuted] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const isMuted = controlledIsMuted !== undefined ? controlledIsMuted : internalIsMuted;
  
  const socketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const isMutedRef = useRef(isMuted);

  // Sincroniza a referência do mute para o callback de áudio
  useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);

  const isConnectedRef = useRef(false);

  useEffect(() => {
    // Conecta apenas uma vez ao montar
    if (!isConnectedRef.current) {
      isConnectedRef.current = true;
      connect();
    }
    // Cleanup apenas ao desmontar de forma definitiva
    return () => {
      disconnect();
    };
  }, []);

  const pendingMessageRef = useRef<string | null>(null);  const nextStartTimeRef = useRef(0);
  const audioQueueRef = useRef<Float32Array[]>([]);

  const connect = async () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host.includes('localhost') ? 'localhost:8003' : window.location.host;
    
    // ENDPOINT EXCLUSIVO PARA HÓSPEDES
    const socket = new WebSocket(`${protocol}//${host}/ws/customer/live/${tenantId}?session_id=${localStorage.getItem('guest_session')}`);
    socketRef.current = socket;

    socket.onopen = () => {
      setIsActive(true);
      startAudioCapture();
      // Envia mensagem pendente se existir (primeira msg antes da conexão estar pronta)
      if (pendingMessageRef.current) {
        socket.send(JSON.stringify({ type: "text", data: pendingMessageRef.current }));
        if (onTranscription) onTranscription(pendingMessageRef.current, 'user');
        pendingMessageRef.current = null;
      }
    };

    socket.onmessage = async (event) => {
      const response = JSON.parse(event.data);
      
      // 1. Texto da Resposta (Model Turn)
      const modelTurn = response.server_content?.model_turn;
      if (modelTurn?.parts) {
        let fullText = "";
        modelTurn.parts.forEach((part: any) => {
            if (part.thought) return;
            if (part.text) fullText += part.text;
        });
        if (fullText && onTranscription) {
          onTranscription(fullText, 'assistant');
        }
      }

      // 2. Áudio da Resposta
      const audioPart = response.server_content?.model_turn?.parts?.find((p: any) => p.inline_data);
      if (audioPart) {
        queueAudioChunk(audioPart.inline_data.data);
      }
    };

    socket.onclose = () => {
      setIsActive(false);
      stopAudioCapture();
    };
  };

  const disconnect = () => {
    socketRef.current?.close();
    stopAudioCapture();
  };

  const startAudioCapture = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate: 16000 });
      }
      
      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }

      const source = audioContextRef.current.createMediaStreamSource(stream);
      const processor = audioContextRef.current.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (isMutedRef.current) return; // RESPEITA O MUTE EM TEMPO REAL

        const inputData = e.inputBuffer.getChannelData(0);
        const pcmData = floatTo16BitPCM(inputData);
        
        if (socketRef.current?.readyState === WebSocket.OPEN) {
          socketRef.current.send(JSON.stringify({
            type: "audio",
            data: base64Encode(pcmData)
          }));
        }
      };

      source.connect(processor);
      processor.connect(audioContextRef.current.destination);
    } catch (err) {
      console.error("Erro ao capturar áudio:", err);
    }
  };

  const stopAudioCapture = () => {
    processorRef.current?.disconnect();
  };

  const queueAudioChunk = (base64Audio: string) => {
    if (!audioContextRef.current) return;
    
    // Converte base64 para Float32Array (PCM 16bit -> Float32)
    const binary = atob(base64Audio);
    const len = binary.length / 2;
    const floatData = new Float32Array(len);
    const view = new DataView(new ArrayBuffer(binary.length));
    
    for (let i = 0; i < binary.length; i++) {
        view.setUint8(i, binary.charCodeAt(i));
    }
    
    for (let i = 0; i < len; i++) {
        const s = view.getInt16(i * 2, true);
        floatData[i] = s / 0x8000;
    }

    playSeamless(floatData);
  };

  const playSeamless = (floatData: Float32Array) => {
    const ctx = audioContextRef.current;
    if (!ctx) return;

    // Gemini Live envia áudio a 24000Hz. Tocar em 16000 causa o efeito 'slow motion'.
    const audioBuffer = ctx.createBuffer(1, floatData.length, 24000);
    audioBuffer.getChannelData(0).set(floatData);

    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);

    const currentTime = ctx.currentTime;
    if (nextStartTimeRef.current < currentTime) {
      nextStartTimeRef.current = currentTime + 0.05; // Pequeno buffer inicial
    }

    source.start(nextStartTimeRef.current);
    setIsSpeaking(true);
    
    nextStartTimeRef.current += audioBuffer.duration;
    
    source.onended = () => {
      if (ctx.currentTime >= nextStartTimeRef.current - 0.1) {
        setIsSpeaking(false);
      }
    };
  };

  // Helper functions
  const floatTo16BitPCM = (input: Float32Array) => {
    const output = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]));
      output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return output.buffer;
  };

  const base64Encode = (buffer: ArrayBuffer) => {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  };

  useImperativeHandle(ref, () => ({
    sendTextMessage: (text: string) => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: "text", data: text }));
        if (onTranscription) onTranscription(text, 'user');
      } else {
        // Socket ainda conectando: enfileira para enviar quando abrir
        pendingMessageRef.current = text;
      }
    }
  }));

  const handleMuteToggle = () => {
    if (onMuteChange) {
      onMuteChange(!isMuted);
    } else {
      setInternalIsMuted(!isMuted);
    }
  };

  return (
    <div className={`relative flex flex-col items-center justify-center p-6 bg-slate-900 rounded-[2.5rem] shadow-2xl border border-indigo-500/20 overflow-hidden transition-all duration-700 ${
      viewMode === 'voice' ? 'min-h-[400px] w-full' : 'min-h-[180px] py-4'
    }`}>
      {/* Background Glow */}
      <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/5 to-purple-500/5 pointer-events-none" />

      {/* Botão de Fechar */}
      {onClose && (
        <button 
          onClick={onClose}
          className="absolute top-6 right-6 p-2 text-slate-500 hover:text-white transition-colors z-20"
        >
          <X size={20} />
        </button>
      )}

      <motion.div
        layout
        className="flex flex-col items-center justify-center z-10 w-full"
      >
        {/* Hologram Core */}
        <div className={`relative transition-all duration-700 ${viewMode === 'voice' ? 'mb-10 scale-100' : 'mb-2 scale-75'}`}>
          <AnimatePresence>
            {isActive && !isMuted && (
               <motion.div 
                 initial={{ opacity: 0 }}
                 exit={{ opacity: 0 }}
                 className="absolute -inset-8 border border-indigo-500/20 rounded-full border-dashed"
                 animate={{ rotate: 360, opacity: 1 }}
                 transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
               />
            )}
          </AnimatePresence>

          <motion.div
            animate={{
              scale: isSpeaking ? [1, 1.05, 1] : 1,
              boxShadow: isSpeaking 
                ? ["0 0 20px rgba(79, 70, 229, 0.3)", "0 0 50px rgba(79, 70, 229, 0.5)", "0 0 20px rgba(79, 70, 229, 0.3)"]
                : "0 0 15px rgba(79, 70, 229, 0.1)"
            }}
            transition={{ duration: 2, repeat: Infinity }}
            className={`w-32 h-32 rounded-full bg-gradient-to-br from-slate-800 to-slate-950 flex items-center justify-center relative border-2 ${
              isSpeaking ? 'border-indigo-400' : 'border-slate-700'
            } ${!isActive && 'grayscale opacity-70'}`}
          >
            {isMuted ? (
              <MicOff className="w-10 h-10 text-red-400/80" />
            ) : (
              <Sparkles className={`w-10 h-10 text-indigo-400 ${isSpeaking ? 'animate-pulse' : ''}`} />
            )}
            
            {/* Status Indicator */}
            <div className="absolute -bottom-3 left-1/2 -translate-x-1/2">
              <span className={`px-3 py-1 rounded-full text-[8px] font-black uppercase tracking-widest flex items-center gap-1.5 shadow-xl ${
                isActive ? 'bg-green-500 text-white' : 'bg-slate-700 text-slate-300'
              }`}>
                <div className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-white animate-ping' : 'bg-slate-500'}`} />
                {isActive ? 'Online' : 'Offline'}
              </span>
            </div>
          </motion.div>
        </div>

        {viewMode === 'voice' && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center space-y-2"
          >
            <h3 className="text-xl font-black text-white tracking-tight">{agentName}: Sua Recepção</h3>
            <p className="text-slate-400 text-[11px] max-w-[200px] mx-auto font-bold uppercase tracking-wider leading-relaxed">
              {isMuted ? 'Microfone Silenciado' : (isSpeaking ? `${agentName} está falando...` : 'Estou ouvindo você')}
            </p>
          </motion.div>
        )}
      </motion.div>

      {/* Footer Controls (Compactos) */}
      <div className={`flex gap-3 relative z-10 transition-all duration-700 ${viewMode === 'voice' ? 'mt-8' : 'mt-2'}`}>
        <button
          onClick={handleMuteToggle}
          className={`p-3 rounded-2xl transition-all active:scale-90 border shadow-lg ${
            isMuted 
              ? 'bg-red-500/10 text-red-500 border-red-500/30' 
              : 'bg-slate-800 text-slate-400 hover:text-white border-slate-700'
          }`}
        >
          {isMuted ? <MicOff size={18} /> : <Mic size={18} />}
        </button>
        
        {viewMode === 'voice' && (
          <div className="flex items-center px-4 bg-slate-800/50 rounded-2xl border border-slate-700">
             <div className={`w-1.5 h-1.5 rounded-full mr-2 ${isSpeaking ? 'bg-indigo-500 animate-pulse' : 'bg-slate-500'}`} />
             <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Holograma Ativo</span>
          </div>
        )}
      </div>

      {/* Grid Floor Effect (Somente no modo voice) */}
      {viewMode === 'voice' && (
        <div className="absolute bottom-0 inset-x-0 h-24 bg-[linear-gradient(to_bottom,transparent,rgba(79,70,229,0.02)_50%,rgba(79,70,229,0.05))] perspective-[1000px] pointer-events-none">
          <div className="absolute inset-0 bg-[grid-white-5] [mask-image:linear-gradient(to_top,white,transparent)] opacity-20" />
        </div>
      )}
    </div>
  );
});

// Removido export default
