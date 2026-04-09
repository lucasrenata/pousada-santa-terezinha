import React, { useState, useMemo, useEffect } from 'react';
import { Calendar } from '@/components/ui/calendar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CalendarIcon, Users, Clock, ArrowRight, MapPin, Info, CalendarHeart } from 'lucide-react';
import { format, isSameDay } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { useReservations, type Reservation } from '@/hooks/useReservations';
import api from '@/services/api';

// Utilitários locais
const formatCurrency = (val: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);

// Converte string ISO (YYYY-MM-DD...) para Objeto Date mantendo os componentes exatos
const parseISODate = (dateStr: string) => {
  if (!dateStr) return new Date();
  const datePart = dateStr.includes('T') ? dateStr.split('T')[0] : dateStr;
  const [y, m, d] = datePart.split('-').map(Number);
  return new Date(y, m - 1, d);
};

const formatDateDayMonth = (dateStr: string) => {
  if (!dateStr) return "";
  const datePart = dateStr.includes('T') ? dateStr.split('T')[0] : dateStr;
  const parts = datePart.split('-');
  return `${parts[2]}/${parts[1]}`;
};

interface RegionalEvent {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  location: string;
  color: string;
}

const statusColors: Record<Reservation['status'], string> = {
  pendente: 'bg-yellow-500',
  confirmado: 'bg-blue-500',
  ativo: 'bg-green-500',
  concluido: 'bg-slate-400',
  cancelado: 'bg-red-500'
};

const statusLabels: Record<Reservation['status'], string> = {
  pendente: 'Pendente',
  confirmado: 'Confirmada',
  ativo: 'Check-in',
  concluido: 'Finalizada',
  cancelado: 'Cancelada'
};

interface ReservationCalendarProps {
  reservations: Reservation[];
}

export function ReservationCalendar({ reservations }: ReservationCalendarProps) {
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
  const [regionalEvents, setRegionalEvents] = useState<RegionalEvent[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);

  // Busca eventos do mês exibido
  useEffect(() => {
    const fetchRegionalEvents = async () => {
      setLoadingEvents(true);
      try {
        const year = currentMonth.getFullYear();
        const res = await api.get(`/events/?year=${year}`);
        // Filtra localmente apenas os eventos que tocam o mês atual
        const monthStart = new Date(year, currentMonth.getMonth(), 1);
        const monthEnd = new Date(year, currentMonth.getMonth() + 1, 0);

        const filtered = res.data.filter((e: RegionalEvent) => {
          const start = new Date(e.start_date);
          const end = new Date(e.end_date);
          return (start <= monthEnd && end >= monthStart);
        });
        setRegionalEvents(filtered);
      } catch (err) {
        console.error("Erro ao buscar eventos regionais", err);
      } finally {
        setLoadingEvents(false);
      }
    };
    fetchRegionalEvents();
  }, [currentMonth]);

  const getReservationsForDate = (date: Date) => {
    return reservations.filter((r: Reservation) => {
      const checkIn = parseISODate(r.check_in_date);
      const checkOut = parseISODate(r.check_out_date);
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
    const modifiers: Record<string, Date[]> = {
      event: []
    };

    // Marcadores de Reservas
    reservations.forEach((r: Reservation) => {
      const checkIn = parseISODate(r.check_in_date);
      const status = r.status;
      if (!modifiers[status]) modifiers[status] = [];
      modifiers[status].push(checkIn);
    });

    // Marcadores de Eventos Regionais
    regionalEvents.forEach((e: RegionalEvent) => {
      const start = parseISODate(e.start_date);
      const end = parseISODate(e.end_date);
      let curr = new Date(start);
      while (curr <= end) {
        modifiers.event.push(new Date(curr));
        curr.setDate(curr.getDate() + 1);
      }
    });

    return modifiers;
  }, [reservations, regionalEvents]);

  const calendarModifiersClassNames: Record<string, string> = {
    pendente: 'border-b-2 border-yellow-500 font-bold',
    confirmado: 'border-b-2 border-blue-500 font-bold',
    ativo: 'border-b-2 border-green-500 font-bold',
    concluido: 'opacity-50',
    cancelado: 'border-b-2 border-red-500',
    event: 'bg-indigo-50/50 ring-1 ring-inset ring-indigo-200/50 rounded-sm'
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Coluna do Calendário + Eventos do Mês */}
      <div className="lg:col-span-2">
        <Card className="border-slate-200 shadow-sm overflow-hidden flex flex-col h-full">
          <CardHeader className="border-b border-slate-50 bg-slate-50/50 flex flex-row items-center justify-between py-4">
            <CardTitle className="flex items-center gap-2 text-slate-800 text-lg">
              <CalendarIcon className="h-5 w-5 text-blue-600" />
              Disponibilidade e Reservas
            </CardTitle>
            <Badge variant="outline" className="text-slate-500 font-bold border-slate-200">
              {format(currentMonth, 'MMMM yyyy', { locale: ptBR })}
            </Badge>
          </CardHeader>
          <CardContent className="p-0 flex flex-col md:flex-row divide-y md:divide-y-0 md:divide-x divide-slate-100 flex-1">

            {/* Lado Esquerdo: Calendário */}
            <div className="p-4 sm:p-6 flex-1 flex flex-col justify-center">
              <Calendar
                mode="single"
                selected={selectedDate}
                onSelect={(date) => date && setSelectedDate(date)}
                onMonthChange={setCurrentMonth}
                modifiers={calendarModifiers}
                modifiersClassNames={calendarModifiersClassNames}
                locale={ptBR}
                className="w-full flex justify-center"
              />

              <div className="mt-8 pt-6 border-t border-slate-50">
                <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-4">Legenda de Status</h4>
                <div className="flex flex-wrap gap-x-4 gap-y-2">
                  {(Object.entries(statusLabels) as [Reservation['status'], string][]).map(([status, label]) => (
                    <div key={status} className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${statusColors[status] || 'bg-slate-300'}`} />
                      <span className="text-[11px] font-bold text-slate-600 capitalize">{label}</span>
                    </div>
                  ))}
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-indigo-100 ring-1 ring-indigo-400" />
                    <span className="text-[11px] font-bold text-slate-600">Evento Regional</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Lado Direito: Calendário de Eventos (Regional) */}
            <div className="w-full md:w-80 bg-slate-50/30 p-4 sm:p-6 flex flex-col">
              <div className="flex items-center gap-2 mb-6">
                <Info size={16} className="text-indigo-600" />
                <h4 className="text-xs font-black text-slate-800 uppercase tracking-tight">Eventos de {format(currentMonth, 'MMMM', { locale: ptBR })}</h4>
              </div>

              {loadingEvents ? (
                <div className="flex-1 flex items-center justify-center">
                  <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : regionalEvents.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center opacity-40 space-y-2">
                  <CalendarHeart size={32} className="text-slate-300" />
                  <p className="text-[11px] font-medium text-slate-500">Nenhum evento regional<br />cadastrado este mês.</p>
                </div>
              ) : (
                <div className="space-y-3 overflow-y-auto max-h-[400px] pr-2 scrollbar-none">
                  {regionalEvents.map(e => (
                    <div key={e.id} className="bg-white rounded-xl p-3 border border-slate-100 shadow-sm hover:border-indigo-200 transition-colors">
                      <div className="flex items-center gap-2 mb-1">
                        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: e.color }} />
                        <span className="text-[11px] font-black text-slate-800 uppercase leading-none truncate">{e.name}</span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 font-bold">
                        <div className="flex items-center gap-1">
                          <span>{formatDateDayMonth(e.start_date)}</span>
                          <ArrowRight size={8} />
                          <span>{formatDateDayMonth(e.end_date)}</span>
                        </div>
                        <div className="flex items-center gap-0.5 text-indigo-400">
                          <MapPin size={10} />
                          <span>SP</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-6 pt-4 border-t border-slate-100">
                <p className="text-[10px] text-slate-400 font-bold text-center leading-tight uppercase italic">
                  Sincronize sua ocupação com os eventos locais da Canção Nova.
                </p>
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
                          Quarto {r.room_number || 'A definir'}
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