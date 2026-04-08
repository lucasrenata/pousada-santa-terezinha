import React, { useState, useMemo } from 'react';
import { Calendar } from '@/components/ui/calendar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CalendarIcon, Users, Clock, ArrowRight } from 'lucide-react';
import { format, isSameDay } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { useReservations, Reservation } from '@/hooks/useReservations';

// Utilitários locais
const formatCurrency = (val: number) => 
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);

const isoToLocalDateIgnoringTZ = (dateStr: string) => {
  const d = new Date(dateStr);
  return new Date(d.getTime() + d.getTimezoneOffset() * 60000);
};

const statusColors: Record<string, string> = {
  pendente: 'bg-yellow-500',
  confirmado: 'bg-blue-500',
  ativo: 'bg-green-500',
  concluido: 'bg-slate-400',
  cancelado: 'bg-red-500'
};

const statusLabels: Record<string, string> = {
  pendente: 'Pendente',
  confirmado: 'Confirmada',
  ativo: 'Check-in',
  concluido: 'Finalizada',
  cancelado: 'Cancelada'
};

export function ReservationCalendar() {
  const { reservations } = useReservations();
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());

  const getReservationsForDate = (date: Date) => {
    return reservations.filter((r: Reservation) => {
      const checkIn = new Date(r.check_in_date);
      const checkOut = new Date(r.check_out_date);
      // Normalizar para comparação apenas de data
      const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
      const ci = new Date(checkIn.getFullYear(), checkIn.getMonth(), checkIn.getDate());
      const co = new Date(checkOut.getFullYear(), checkOut.getMonth(), checkOut.getDate());
      return d >= ci && d <= co;
    });
  };

  const selectedDateReservations = useMemo(() => {
    return getReservationsForDate(selectedDate);
  }, [reservations, selectedDate]);

  const calendarModifiers = useMemo(() => {
    const modifiers: Record<string, Date[]> = {};
    
    reservations.forEach((r: Reservation) => {
      const checkIn = new Date(r.check_in_date);
      const status = r.status;
      
      if (!modifiers[status]) {
        modifiers[status] = [];
      }
      modifiers[status].push(checkIn);
    });
    
    return modifiers;
  }, [reservations]);

  const calendarModifiersClassNames = {
    pendente: 'border-b-2 border-yellow-500 font-bold',
    confirmado: 'border-b-2 border-blue-500 font-bold',
    ativo: 'border-b-2 border-green-500 font-bold',
    concluido: 'opacity-50',
    cancelado: 'border-b-2 border-red-500'
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Coluna do Calendário */}
      <div className="lg:col-span-2">
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="border-b border-slate-50 bg-slate-50/50">
            <CardTitle className="flex items-center gap-2 text-slate-800">
              <CalendarIcon className="h-5 w-5 text-blue-600" />
              Disponibilidade e Reservas
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-6">
            <Calendar
              mode="single"
              selected={selectedDate}
              onSelect={(date) => date && setSelectedDate(date)}
              modifiers={calendarModifiers}
              modifiersClassNames={calendarModifiersClassNames}
              locale={ptBR}
              className="rounded-xl border border-slate-100 shadow-inner w-full flex justify-center"
            />
            
            <div className="mt-8 pt-6 border-t border-slate-100">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Legenda de Status</h4>
              <div className="flex flex-wrap gap-4">
                {Object.entries(statusLabels).map(([status, label]: [string, string]) => (
                  <div key={status} className="flex items-center gap-2">
                    <div className={`w-2.5 h-2.5 rounded-full ${statusColors[status]}`} />
                    <span className="text-sm font-medium text-slate-600">{label}</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Coluna de Detalhes do Dia */}
      <div className="space-y-4">
        <Card className="border-slate-200 shadow-sm overflow-hidden h-full flex flex-col">
          <CardHeader className="bg-slate-900 text-white py-4">
            <div className="text-xs font-bold opacity-60 uppercase tracking-widest">{format(selectedDate, 'EEEE', { locale: ptBR })}</div>
            <CardTitle className="text-xl">
              {format(selectedDate, "dd 'de' MMMM", { locale: ptBR })}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 flex-1 overflow-y-auto max-h-[500px]">
            {selectedDateReservations.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center space-y-3 opacity-40">
                <CalendarIcon size={48} className="text-slate-300" />
                <p className="text-sm font-medium">Nenhuma reserva ativa para este dia.</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                    Ocupação ({selectedDateReservations.length} Quarto{selectedDateReservations.length > 1 ? 's' : ''})
                  </h4>
                </div>
                {selectedDateReservations.map((r: Reservation) => (
                  <div key={r.id} className="group p-3 rounded-xl border border-slate-100 bg-white hover:border-blue-200 hover:shadow-md transition-all">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="font-bold text-slate-800 group-hover:text-blue-600 transition-colors">
                          {r.guest_name}
                        </p>
                        <p className="text-xs font-semibold text-slate-500">
                          Quarto {r.room_number || 'S/D'}
                        </p>
                      </div>
                      <Badge className={`${statusColors[r.status]} text-white border-0 text-[10px] px-2 py-0`}>
                        {statusLabels[r.status]}
                      </Badge>
                    </div>
                    
                    <div className="space-y-2 mt-2">
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <div className="flex items-center gap-1">
                          <Clock size={12} />
                          <span>Check-in em {format(new Date(r.check_in_date), 'dd/MM')}</span>
                        </div>
                        <ArrowRight size={12} />
                        <div>Check-out em {format(new Date(r.check_out_date), 'dd/MM')}</div>
                      </div>
                      
                      <div className="flex items-center justify-between pt-1 border-t border-slate-50">
                        <div className="flex items-center gap-1 text-[11px] font-medium text-slate-600">
                          <Users size={12} />
                          <span>{r.total_guests} hóspedes</span>
                        </div>
                        <span className="text-xs font-bold text-slate-900">
                          {formatCurrency(r.total_amount)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}