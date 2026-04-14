import { format } from 'date-fns';
import { ptBR } from 'date-fns'; // Locale para datas (opcional se não usar format)
import { Calendar, Users, CreditCard, Clock, UserPlus, Phone, Mail, Edit, Trash2, Eye, FileText, CheckCircle2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Reservation } from '@/hooks/useReservations';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

// Utilitários de formatação locais para evitar erros de importação
const formatCurrency = (val: number) => 
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);

const formatDate = (dateStr: string) => {
  if (!dateStr) return "";
  try {
    // Isolamos apenas a parte da data (antes do 'T' se houver)
    const datePart = dateStr.includes('T') ? dateStr.split('T')[0] : dateStr;
    const parts = datePart.split('-');
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    return dateStr;
  } catch {
    return dateStr;
  }
};

interface ReservationCardProps {
  reservation: Reservation;
  onEdit?: (reservation: Reservation) => void;
  onDelete?: (reservation: Reservation) => void;
  onCheckIn?: (reservation: Reservation) => void;
  onCheckOut?: (reservation: Reservation) => void;
}

const statusLabels: Record<string, string> = {
  pendente: 'Pendente',
  confirmado: 'Confirmada',
  ativo: 'Check-in',
  concluido: 'Finalizada',
  cancelado: 'Cancelada'
};

const statusVariants: Record<string, any> = {
  pendente: 'secondary',
  confirmado: 'default',
  ativo: 'default',
  concluido: 'secondary',
  cancelado: 'destructive'
};

const paymentLabels: Record<string, string> = {
  pending: 'Pendente',
  partial: 'Parcial',
  paid: 'Pago',
  cancelled: 'Cancelado'
};

const paymentVariants: Record<string, any> = {
  pending: 'secondary',
  partial: 'outline',
  paid: 'default',
  cancelled: 'destructive'
};

export function ReservationCard({ reservation, onEdit, onDelete, onCheckIn, onCheckOut }: ReservationCardProps) {
  const hasReceipt = !!reservation.payment_receipt_url;
  
  // Lógica robusta: Prioriza VITE_API_URL se definida no build. 
  // Caso contrário, usa /api (padrão produção) em vez de localhost.
  const apiBaseUrl = import.meta.env.VITE_API_URL && import.meta.env.VITE_API_URL !== 'http://localhost:8003' 
    ? import.meta.env.VITE_API_URL 
    : '/api';
    
  // Remove barras duplicadas para evitar links como //static
  const cleanBaseUrl = apiBaseUrl.endsWith('/') ? apiBaseUrl.slice(0, -1) : apiBaseUrl;
  const receiptFullUrl = reservation.payment_receipt_url ? `${cleanBaseUrl}${reservation.payment_receipt_url}` : null;

  return (
    <Card className={`w-full hover:shadow-lg transition-all duration-300 relative overflow-hidden bg-white ${
      hasReceipt ? 'border-green-200 shadow-green-50/50 border-2' : 'border-slate-200'
    }`}>
      {/* Marcador Lateral de Status */}
      <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${
        hasReceipt ? 'bg-green-500 shadow-[2px_0_10px_rgba(34,197,94,0.3)]' :
        reservation.status === 'ativo' ? 'bg-green-500' : 
        reservation.status === 'confirmado' ? 'bg-blue-500' : 
        reservation.status === 'pendente' ? 'bg-yellow-500' : 'bg-slate-300'
      }`} />

      <CardContent className="p-5 space-y-4">
        {/* Header: Cliente e Status */}
        <div className="flex justify-between items-start">
          <div className="space-y-0.5">
            <h3 className="font-bold text-slate-800 text-lg leading-tight flex items-center gap-2">
              {reservation.guest_name}
              {hasReceipt && <CheckCircle2 size={16} className="text-green-500" title="Comprovante Enviado" />}
              {reservation.guest_age !== undefined && reservation.guest_age !== null && (
                <span className="ml-1 text-sm font-normal text-slate-500">
                  ({reservation.guest_age} anos)
                </span>
              )}
            </h3>
            <div className="flex items-center gap-2">
              <p className="text-sm font-semibold text-blue-600">
                Quarto {reservation.room_number || 'A definir'}
              </p>
              <Badge variant={statusVariants[reservation.status]} className="text-[10px] px-2 py-0">
                {statusLabels[reservation.status]}
              </Badge>
            </div>
          </div>
          <div className="flex gap-1">
            {hasReceipt && (
              <Dialog>
                <DialogTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-green-600 hover:text-green-700 hover:bg-green-50">
                    <Eye size={18} />
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-[500px] border-none shadow-2xl overflow-hidden p-0 bg-slate-950">
                  <DialogHeader className="p-4 bg-white/10 backdrop-blur-md absolute top-0 left-0 right-0 z-10 border-b border-white/10">
                    <DialogTitle className="text-white flex items-center gap-2">
                      <FileText size={18} /> Comprovante de Pagamento - #{reservation.id}
                    </DialogTitle>
                  </DialogHeader>
                  <div className="flex items-center justify-center p-2 pt-16 min-h-[300px]">
                    {reservation.payment_receipt_url?.toLowerCase().endsWith('.pdf') ? (
                      <div className="text-center p-10 space-y-4">
                        <FileText size={64} className="text-blue-400 mx-auto" />
                        <p className="text-white text-sm">Este comprovante é um PDF.</p>
                        <Button asChild>
                           <a href={receiptFullUrl!} target="_blank" rel="noreferrer">Abrir PDF em nova aba</a>
                        </Button>
                      </div>
                    ) : (
                      <img 
                        src={receiptFullUrl!} 
                        alt="Comprovante" 
                        className="max-h-[70vh] w-auto object-contain rounded-lg shadow-2xl"
                      />
                    )}
                  </div>
                </DialogContent>
              </Dialog>
            )}
            <Button variant="ghost" size="icon" onClick={() => onEdit?.(reservation)} className="h-8 w-8 text-slate-400 hover:text-blue-600">
              <Edit size={16} />
            </Button>
            <Button variant="ghost" size="icon" onClick={() => onDelete?.(reservation)} className="h-8 w-8 text-slate-400 hover:text-red-600">
              <Trash2 size={16} />
            </Button>
          </div>
        </div>

        {/* Datas e Horários */}
        <div className="grid grid-cols-2 gap-3 py-2 border-y border-slate-50">
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
              <Calendar size={14} className="text-blue-500" />
              Check-in
            </div>
            <div className="text-sm font-bold text-slate-700">
              {formatDate(reservation.check_in_date)}
              <span className="ml-1 font-normal text-slate-400 text-[11px]">{reservation.check_in_time}</span>
            </div>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
              <Calendar size={14} className="text-red-400" />
              Check-out
            </div>
            <div className="text-sm font-bold text-slate-700">
              {formatDate(reservation.check_out_date)}
              <span className="ml-1 font-normal text-slate-400 text-[11px]">{reservation.check_out_time}</span>
            </div>
          </div>
        </div>

        {/* Info de Hospedes e Valores */}
        <div className="flex justify-between items-end">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Users size={16} className="text-slate-400" />
              <span className="font-medium">{reservation.total_guests} hóspede{reservation.total_guests > 1 ? 's' : ''}</span>
            </div>
            <div className="flex items-center gap-2">
              <CreditCard size={16} className="text-slate-400" />
              <Badge variant={paymentVariants[reservation.payment_status]} className="text-[10px]">
                {paymentLabels[reservation.payment_status]}
              </Badge>
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs text-slate-400 font-medium">Total da Reserva</p>
            <p className="text-xl font-bold text-slate-900">{formatCurrency(reservation.total_amount)}</p>
            {reservation.deposit_amount > 0 && (
              <p className="text-[11px] text-green-600 font-semibold">Depósito: {formatCurrency(reservation.deposit_amount)}</p>
            )}
          </div>
        </div>

        {/* Acompanhantes (se houver) */}
        {reservation.companions && reservation.companions.length > 0 && (
          <div className="bg-slate-50 rounded-lg p-3 space-y-1.5 border border-slate-100">
            <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              <UserPlus size={14} />
              Acompanhantes
            </div>
            <div className="text-xs text-slate-600 space-y-0.5">
              {reservation.companions.map((c: any) => (
                <div key={c.id} className="flex justify-between">
                  <span>{c.name}</span>
                  <span className="text-slate-400">{c.age} anos</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Observações */}
        {reservation.notes && (
          <div className="space-y-1">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Observações</p>
            <p className="text-xs text-slate-600 bg-yellow-50/50 p-2 rounded border border-yellow-100/50 italic">
              "{reservation.notes}"
            </p>
          </div>
        )}

        {/* Ações de Check-in/out */}
        {(reservation.status === 'confirmado' || reservation.status === 'ativo') && (
          <div className="pt-2">
            {reservation.status === 'confirmado' && (
              <Button 
                className="w-full bg-blue-600 hover:bg-blue-700 text-white shadow-md shadow-blue-200"
                onClick={() => onCheckIn?.(reservation)}
              >
                Fazer Check-In
              </Button>
            )}
            {reservation.status === 'ativo' && (
              <Button 
                variant="outline"
                className="w-full border-green-200 text-green-700 hover:bg-green-50"
                onClick={() => onCheckOut?.(reservation)}
              >
                Fazer Check-Out
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}