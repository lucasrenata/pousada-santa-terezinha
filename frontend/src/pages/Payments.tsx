import { useEffect, useMemo, useRef, useState } from 'react';
import api from '../services/api';
import { useNavigate, useLocation } from 'react-router-dom';

type PaymentResponse = {
  payment_id: number | null;
  status?: string | null;
  amount?: number | null;
  qr_code?: string | null;
  qr_code_base64?: string | null;
};

interface Room {
  id: number;
  number: string;
  type: string;
  price_per_night: number;
  status: 'disponivel' | 'ocupado' | 'limpeza' | 'manutencao';
}

export default function Payments() {
  const navigate = useNavigate();
  const location = useLocation();
  const [roomNumber, setRoomNumber] = useState<string>('');
  const [payment, setPayment] = useState<PaymentResponse | null>(null);
  const [status, setStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [polling, setPolling] = useState<boolean>(false);
  const [summary, setSummary] = useState<{
    room_id: number;
    room_number: string;
    booking_id: number;
    guest_name?: string | null;
    guest_email?: string | null;
    daily_total: number;
    consumption_total: number;
    grand_total: number;
  } | null>(null);
  const timerRef = useRef<number | null>(null);

  const imgSrc = useMemo(() => {
    const base64 = payment?.qr_code_base64 ?? null;
    if (!base64) return null;
    return `data:image/png;base64,${base64}`;
  }, [payment]);

  function getErrorMessage(e: unknown, fallback: string) {
    if (e instanceof Error) return e.message || fallback;
    if (typeof e === 'object' && e !== null) {
      const resp = (e as Record<string, unknown>)['response'];
      if (typeof resp === 'object' && resp !== null) {
        const data = (resp as Record<string, unknown>)['data'];
        if (typeof data === 'object' && data !== null) {
          const detail = (data as Record<string, unknown>)['detail'];
          if (typeof detail === 'string') return detail;
        }
      }
    }
    return fallback;
  }

  async function loadSummary() {
    setError(null);
    setMessage(null);
    setPayment(null);
    setStatus('');
    setSummary(null);
    try {
      const num = roomNumber.trim();
      if (!num) throw new Error('Informe o número do quarto');
      const resp = await api.get(`/rooms/by-number/${encodeURIComponent(num)}`);
      const room = resp.data as Room;
      if (!room) throw new Error('Quarto não encontrado');
      setLoading(true);
      const res = await api.get(`/payments/summary/${room.id}`);
      setSummary(res.data);
      setLoading(false);
      setMessage('Resumo carregado');
    } catch (err: unknown) {
      setLoading(false);
      setError(getErrorMessage(err, 'Falha ao carregar resumo'));
    }
  }

  async function startPix() {
    setError(null);
    setMessage(null);
    setPayment(null);
    setStatus('');
    try {
      const num = roomNumber.trim();
      if (!num) throw new Error('Informe o número do quarto');
      const resp = await api.get(`/rooms/by-number/${encodeURIComponent(num)}`);
      const room = resp.data as Room;
      if (!room) throw new Error('Quarto não encontrado');
      if (!summary) {
        const s = await api.get(`/payments/summary/${room.id}`);
        setSummary(s.data);
      }
      setLoading(true);
      const res = await api.post(`/payments/checkout/${room.id}/pix`);
      const data = res.data as any;
      if (!data?.payment_id) {
        const causeDesc = Array.isArray(data?.error?.cause) && data.error.cause.length > 0 ? (data.error.cause[0]?.description ?? null) : null;
        const msg = data?.error?.message ?? causeDesc ?? 'Falha ao gerar pagamento PIX';
        setError(msg);
        setLoading(false);
        return;
      }
      setPayment(data);
      setStatus(data.status ?? '');
      setMessage('Pagamento PIX gerado');
      setLoading(false);
      beginPolling(data.payment_id);
    } catch (err: unknown) {
      setLoading(false);
      setError(getErrorMessage(err, 'Falha ao gerar PIX'));
    }
  }

  async function startCard() {
    setError(null);
    setMessage(null);
    setPayment(null);
    setStatus('');
    try {
      const num = roomNumber.trim();
      if (!num) throw new Error('Informe o número do quarto');
      const resp = await api.get(`/rooms/by-number/${encodeURIComponent(num)}`);
      const room = resp.data as Room;
      if (!room) throw new Error('Quarto não encontrado');
      if (!summary) {
        const s = await api.get(`/payments/summary/${room.id}`);
        setSummary(s.data);
      }
      setLoading(true);
      const res = await api.post(`/payments/checkout/${room.id}/card`);
      const data = res.data as any;
      const url = data?.sandbox_init_point ?? data?.init_point ?? null;
      if (!url) {
        const causeDesc = Array.isArray(data?.error?.cause) && data.error.cause.length > 0 ? (data.error.cause[0]?.description ?? null) : null;
        const msg = data?.error?.message ?? causeDesc ?? 'Falha ao iniciar pagamento por cartão';
        setError(msg);
        setLoading(false);
        return;
      }
      window.open(url, '_blank');
      setLoading(false);
      setMessage('Redirecionado para pagamento com cartão');
    } catch (err: unknown) {
      setLoading(false);
      setError(getErrorMessage(err, 'Falha ao iniciar pagamento por cartão'));
    }
  }

  function beginPolling(pid: number) {
    stopPolling();
    setPolling(true);
    timerRef.current = window.setInterval(async () => {
      try {
        const res = await api.get(`/payments/status/${pid}`);
        const st = (res.data?.status ?? '') as string;
        setStatus(st);
        if (st === 'approved') {
          stopPolling();
          setMessage('Pagamento aprovado');
        }
      } catch (e) {
        setError(getErrorMessage(e, 'Falha ao verificar status'));
      }
    }, 5000);
  }

  function stopPolling() {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setPolling(false);
  }

  function resetAll() {
    stopPolling();
    setPayment(null);
    setStatus('');
    setMessage(null);
    setError(null);
  }

  async function copyCode() {
    try {
      const code = payment?.qr_code ?? '';
      if (!code) return;
      await navigator.clipboard.writeText(code);
      setMessage('Código PIX copiado');
      setTimeout(() => setMessage(null), 2000);
    } catch (e) {
      setError(getErrorMessage(e, 'Falha ao copiar código'));
    }
  }

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, []);
  useEffect(() => {
    try {
      const params = new URLSearchParams(location.search || '');
      const rn = params.get('room');
      if (rn) setRoomNumber(rn);
    } catch {}
  }, [location.search]);

  return (
    <div className="p-4 sm:p-6">
      <div className="max-w-3xl mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-slate-800">Pagamentos</h1>
          <button className="text-sm px-3 py-2 rounded-lg border bg-white" onClick={() => navigate(-1)}>Voltar</button>
        </div>

        <div className="grid sm:grid-cols-3 gap-3">
          <div className="sm:col-span-1 border rounded-lg p-4 bg-white space-y-2">
            <p className="text-sm font-medium text-slate-700">Identificar Quarto</p>
            <label className="block text-xs text-slate-600">Número do quarto</label>
            <input className="border rounded-lg px-3 py-2 w-full" placeholder="Ex.: 101" value={roomNumber} onChange={(e) => setRoomNumber(e.target.value)} />
            <div className="grid grid-cols-2 gap-2">
              <button className="px-3 py-2 rounded-lg border bg-white" onClick={loadSummary} disabled={loading}>{loading ? 'Carregando...' : 'Carregar Resumo'}</button>
              <button className="px-3 py-2 rounded-lg border bg-white" onClick={resetAll}>Limpar</button>
            </div>
          </div>

          <div className="sm:col-span-2 grid gap-3">
            <div className="border rounded-lg p-4 bg-white">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-slate-700">Status</p>
                <span className={`inline-flex items-center gap-2 text-sm font-medium ${status === 'approved' ? 'text-green-600' : status ? 'text-yellow-700' : 'text-slate-500'}`}>
                  <span>{status === 'approved' ? '✅' : status ? '⏳' : '•'}</span>
                  <span>{status || 'Aguardando'}</span>
                </span>
              </div>
            </div>

            <div className="border rounded-lg p-4 bg-white">
              <p className="text-sm font-medium text-slate-700">Resumo</p>
              {summary ? (
                <div className="mt-2 grid sm:grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <p className="text-sm text-slate-600">Quarto</p>
                    <p className="text-sm font-medium">{summary.room_number}</p>
                    <p className="text-sm text-slate-600">Reserva</p>
                    <p className="text-sm font-medium">#{summary.booking_id}</p>
                    {summary.guest_name && <p className="text-sm font-medium">{summary.guest_name}</p>}
                    {summary.guest_email && <p className="text-xs text-slate-500">{summary.guest_email}</p>}
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-slate-600">Diárias</p>
                      <span className="text-sm font-medium">R$ {Number(summary.daily_total).toFixed(2)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-slate-600">Consumos</p>
                      <span className="text-sm font-medium">R$ {Number(summary.consumption_total).toFixed(2)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-slate-600">Total</p>
                      <span className="text-sm font-semibold">R$ {Number(summary.grand_total).toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-600">Informe o quarto e carregue o resumo.</p>
              )}
            </div>

            <div className="border rounded-lg p-4 bg-white">
              <p className="text-sm font-medium text-slate-700">Formas de Pagamento</p>
              <div className="mt-2 grid sm:grid-cols-2 gap-2">
                <button className="w-full px-3 py-2 rounded-lg bg-blue-600 text-white disabled:opacity-60" onClick={startPix} disabled={loading || !summary}>
                  {loading ? 'Gerando...' : 'Gerar PIX do Check-out'}
                </button>
                <button className="w-full px-3 py-2 rounded-lg bg-purple-600 text-white disabled:opacity-60" onClick={startCard} disabled={loading || !summary}>
                  {loading ? 'Abrindo...' : 'Pagar com Cartão'}
                </button>
              </div>
              {polling && (
                <button className="w-full mt-2 px-3 py-2 rounded-lg border bg-white" onClick={stopPolling}>
                  Parar verificação
                </button>
              )}
            </div>

            <div className="border rounded-lg p-4 bg-white">
              <p className="text-sm font-medium text-slate-700">QR PIX</p>
              {imgSrc ? (
                <div className="flex flex-col items-center gap-3 pt-2">
                  <div className="border-2 border-slate-300 rounded-xl p-2">
                    <img src={imgSrc} alt="QR Pix" className="w-56 h-56 object-contain" />
                  </div>
                  <p className="text-xs text-slate-500">Escaneie o QR para pagar via PIX</p>
                  <button className="px-4 py-2 rounded-lg bg-slate-800 text-white" onClick={copyCode}>Copiar código PIX</button>
                </div>
              ) : (
                <div className="text-sm text-slate-600">
                  {payment?.payment_id ? 'Pagamento criado. Aguarde o QR ou use o polling.' : 'QR aparecerá após gerar o PIX.'}
                </div>
              )}
            </div>
          </div>
        </div>

        {error && <div className="px-3 py-2 rounded-lg bg-red-100 text-red-700">{error}</div>}
        {message && <div className="px-3 py-2 rounded-lg bg-green-100 text-green-700">{message}</div>}
      </div>
    </div>
  );
}
