import { useState, useEffect, useMemo } from 'react';
import { useForm, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { CalendarIcon, Calculator, Clock, Plus, Trash2, AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { useReservations, Reservation } from '@/hooks/useReservations';
import { useRealTimeRooms } from '@/hooks/useRealTimeRooms';
import { useCustomers } from '@/hooks/useCustomers';
import { CustomerSearch } from './CustomerSearch';
import { CustomerForm } from './CustomerForm';
import { cn } from '@/lib/utils';

// Schema de validação Zod
const reservationSchema = z.object({
  guest_id: z.number().min(1, 'Selecione um hóspede'),
  room_id: z.string().min(1, 'Selecione um quarto'),
  check_in_date: z.date({ required_error: 'Data de check-in é obrigatória' }),
  check_out_date: z.date({ required_error: 'Data de check-out é obrigatória' }),
  check_in_time: z.string().default('14:00'),
  check_out_time: z.string().default('14:00'),
  total_guests: z.number().min(1).default(1),
  daily_rate: z.number().min(0, 'A diária deve ser zero ou mais'),
  deposit_amount: z.number().min(0).default(0),
  payment_status: z.enum(['pending', 'partial', 'paid', 'cancelled']).default('pending'),
  status: z.enum(['pendente', 'confirmado', 'ativo', 'concluido', 'cancelado']).default('pendente'),
  notes: z.string().optional(),
  mode: z.string().default('normal'),
  companions: z.array(z.object({
    name: z.string().min(1, 'Nome do acompanhante é obrigatório'),
    age: z.coerce.number().min(0, 'Idade inválida')
  })).default([])
}).refine((data) => data.check_out_date > data.check_in_date, {
  message: "Check-out deve ser após o check-in",
  path: ["check_out_date"],
});

type ReservationFormData = z.infer<typeof reservationSchema>;

interface ReservationFormProps {
  reservation?: Reservation | null;
  initialRoomId?: string;
  onSuccess: () => void;
  onCancel: () => void;
}

export function ReservationForm({ reservation, initialRoomId, onSuccess, onCancel }: ReservationFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<any | null>(null);
  const [pricingModel, setPricingModel] = useState<'per_person' | 'per_room'>('per_person');
  const [childPercentage, setChildPercentage] = useState(50);
  const [infantFixedRate, setInfantFixedRate] = useState(30);
  const [showCustomerForm, setShowCustomerForm] = useState(false);
  
  const { createReservation, updateReservation } = useReservations();
  const { rooms } = useRealTimeRooms();
  const { getCustomerById } = useCustomers();
  const { toast } = useToast();
  
  const [availableRooms, setAvailableRooms] = useState<any[]>([]);
  const [isCheckingAvailability, setIsCheckingAvailability] = useState(false);
  const [roomConflict, setRoomConflict] = useState(false);

  const form = useForm<ReservationFormData>({
    resolver: zodResolver(reservationSchema),
    defaultValues: {
      guest_id: reservation?.id ? 0 : 0, // Será setado no useEffect
      room_id: initialRoomId || "", 
      check_in_date: reservation?.check_in_date ? new Date(reservation.check_in_date) : new Date(),
      check_out_date: reservation?.check_out_date ? new Date(reservation.check_out_date) : new Date(new Date().setDate(new Date().getDate() + 1)),
      check_in_time: reservation?.check_in_time || '14:00',
      check_out_time: reservation?.check_out_time || '12:00',
      total_guests: reservation?.total_guests || 1,
      daily_rate: reservation?.total_amount ? 0 : 0, // Lógica de cálculo ou manual
      deposit_amount: reservation?.deposit_amount || 0,
      payment_status: reservation?.payment_status || 'pending',
      status: reservation?.status || 'pendente',
      notes: reservation?.notes || '',
      mode: 'normal',
      companions: reservation?.companions || []
    }
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "companions"
  });

  // Cálculo automático do Total Presumido (Visual apenas no form)
  const watchedValues = form.watch(['check_in_date', 'check_out_date', 'check_in_time', 'check_out_time', 'daily_rate', 'total_guests', 'companions']);
  
  const totalPresumed = useMemo(() => {
    const [start, end, ciTime, coTime, rate, guests, companionsList] = watchedValues;
    if (!start || !end || !rate) return 0;

    // Regra hoteleira de contagem de diárias (baseada no backend logic)
    const calculateDays = (d1: Date, d2: Date, h1: string, h2: string) => {
      const msPerDay = 24 * 60 * 60 * 1000;
      let diff = Math.ceil((new Date(d2).setHours(0,0,0,0) - new Date(d1).setHours(0,0,0,0)) / msPerDay);
      if (diff < 1) diff = 1;

      const hour1 = parseInt(h1.split(':')[0]);
      const hour2 = parseInt(h2.split(':')[0]);

      if (hour1 < 14) diff += 1; // Check-in antecipado
      if (hour2 >= 14) diff += 1; // Check-out tardio

      return diff;
    };

    const days = calculateDays(start, end, ciTime, coTime);
    
    if (pricingModel === 'per_room') {
      return days * rate;
    }

    // Lógica Per Person (Adultos full, Crianças %, Bebês fixo)
    let total = 0;
    const allAges = [18, ...(companionsList?.map(c => Number(c.age)) || [])];
    
    allAges.forEach(age => {
      if (age >= 13) total += (days * rate);
      else if (age >= 7) total += (days * rate * (childPercentage / 100));
      else total += (days * infantFixedRate); 
    });

    return total;
  }, [watchedValues, pricingModel, childPercentage, infantFixedRate]);

  // --- BUSCA DE DISPONIBILIDADE E CONFIGS EM TEMPO REAL ---
  const checkInDate = form.watch('check_in_date');
  const checkOutDate = form.watch('check_out_date');
  const checkInTime = form.watch('check_in_time');
  const checkOutTime = form.watch('check_out_time');
  const companions = form.watch('companions');
  const currentMode = form.watch('mode');

  // Busca o modelo de precificação ativo
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await api.get('/settings/');
        const model = response.data.find((s: any) => s.key === 'pousada_pricing_model');
        const childPct = response.data.find((s: any) => s.key === 'pousada_rate_child_percentage');
        const infantFixed = response.data.find((s: any) => s.key === 'pousada_rate_infant_fixed');
        
        if (model) setPricingModel(model.value as any);
        if (childPct) setChildPercentage(Number(childPct.value));
        if (infantFixed) setInfantFixedRate(Number(infantFixed.value));
      } catch (err) {
        console.error("Erro ao carregar modelo de preços", err);
      }
    };
    fetchSettings();
  }, []);

  // Mantém total_guests sincronizado com acompanhantes no modo normal
  useEffect(() => {
    if (currentMode === 'normal') {
      const currentTotal = form.getValues('total_guests');
      const expectedTotal = 1 + (companions?.length || 0);
      if (currentTotal !== expectedTotal) {
        form.setValue('total_guests', expectedTotal);
      }
    }
  }, [companions, currentMode, form]);

  useEffect(() => {
    const fetchAvailability = async () => {
      if (!checkInDate || !checkOutDate) return;
      
      setIsCheckingAvailability(true);
      try {
        // Formata as datas com horários para a busca
        const start = new Date(checkInDate);
        const [hIn, mIn] = checkInTime.split(':').map(Number);
        start.setHours(hIn || 14, mIn || 0);

        const end = new Date(checkOutDate);
        const [hOut, mOut] = checkOutTime.split(':').map(Number);
        end.setHours(hOut || 12, mOut || 0);

        const response = await api.get('/bookings/availability', {
          params: {
            start: start.toISOString(),
            end: end.toISOString(),
            exclude_booking_id: reservation?.id || undefined
          }
        });

        const available = response.data;
        setAvailableRooms(available);

        // Verifica se o quarto pré-selecionado (vindo da URL ou Edit) está disponível
        const currentRoomId = form.getValues('room_id');
        if (currentRoomId && currentRoomId !== "") {
          const isRoomAvailable = available.some((r: any) => r.id === currentRoomId);
          setRoomConflict(!isRoomAvailable);
        } else {
          setRoomConflict(false);
        }
      } catch (error) {
        console.error("Erro ao buscar disponibilidade:", error);
      } finally {
        setIsCheckingAvailability(false);
      }
    };

    const timer = setTimeout(fetchAvailability, 500); // Debounce para não sobrecarregar o server
    return () => clearTimeout(timer);
  }, [checkInDate, checkOutDate, checkInTime, checkOutTime]);

  // Se for edição, carregar os dados da reserva
  useEffect(() => {
    if (reservation) {
      form.reset({
        guest_id: reservation.guest_id || 0,
        room_id: reservation.room_id || "",
        mode: reservation.mode || 'normal',
        check_in_date: new Date(reservation.check_in_date),
        check_out_date: new Date(reservation.check_out_date),
        check_in_time: reservation.check_in_time || "14:00",
        check_out_time: reservation.check_out_time || "14:00",
        daily_rate: reservation.daily_rate || 0,
        total_guests: reservation.total_guests || 1,
        notes: reservation.notes || "",
        companions: reservation.companions || [],
      });
      if (reservation.guest_id && reservation.guest_name) {
         setSelectedCustomer({ id: reservation.guest_id, name: reservation.guest_name });
      }
    }
  }, [reservation, form]);

  const onSubmit = async (data: ReservationFormData) => {
    setIsSubmitting(true);
    try {
      // O backend espera check_in_date como string ISO ou Date. 
      // Vamos formatar adequadamente.
      const payload = {
        ...data,
        check_in_date: data.check_in_date.toISOString(),
        check_out_date: data.check_out_date.toISOString(),
      };

      if (reservation) {
        // Para edição, o backend usa reschedule ou teremos um put genérico
        await updateReservation(reservation.id, payload);
        toast({ title: "Reserva Atualizada", description: "As alterações foram salvas com sucesso." });
      } else {
        await createReservation(payload);
        toast({ title: "Reserva Criada", description: "A reserva foi registrada no sistema." });
      }
      onSuccess();
    } catch (error: any) {
      console.error(error);
      toast({ 
        title: "Erro ao salvar", 
        description: error.response?.data?.detail || "Ocorreu um erro inesperado.",
        variant: "destructive"
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (showCustomerForm) {
    return (
      <CustomerForm 
        onSuccess={(c: any) => { 
          setSelectedCustomer(c); 
          form.setValue('guest_id', c.id); 
          setShowCustomerForm(false); 
        }} 
        onCancel={() => setShowCustomerForm(false)} 
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Seleção de Hóspede */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">Passo 1</Badge>
          <h3 className="font-bold text-slate-700">Identificação do Hóspede Principal</h3>
        </div>
        <CustomerSearch 
          onSelectCustomer={(c: any) => { 
            setSelectedCustomer(c); 
            form.setValue('guest_id', c.id); 
          }} 
          onCreateNew={() => setShowCustomerForm(true)}
          selectedCustomer={selectedCustomer}
        />
        {form.formState.errors.guest_id && (
          <p className="text-xs text-red-500 font-medium">{form.formState.errors.guest_id.message}</p>
        )}
      </section>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
          
          {/* 2. Período da Estadia */}
          <section className="space-y-4 pt-4 border-t border-slate-100">
            <div className="flex items-center gap-2 mb-4">
              <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">Passo 2</Badge>
              <h3 className="font-bold text-slate-700">Período da Estadia</h3>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <FormField control={form.control} name="check_in_date" render={({ field }: { field: any }) => (
                <FormItem className="flex flex-col">
                  <FormLabel className="text-slate-600 font-semibold">Data de Entrada</FormLabel>
                  <Popover>
                    <PopoverTrigger asChild>
                      <FormControl>
                        <Button variant="outline" className={cn("pl-3 text-left font-normal border-slate-200", !field.value && "text-muted-foreground")}>
                          {field.value ? format(field.value, "PPP", { locale: ptBR }) : <span>Escolha uma data</span>}
                          <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                        </Button>
                      </FormControl>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar mode="single" selected={field.value} onSelect={field.onChange} disabled={(date: Date) => date < new Date(new Date().setHours(0,0,0,0))} initialFocus locale={ptBR} />
                    </PopoverContent>
                  </Popover>
                  <FormMessage />
                </FormItem>
              )} />

              <FormField control={form.control} name="check_out_date" render={({ field }: { field: any }) => (
                <FormItem className="flex flex-col">
                  <FormLabel className="text-slate-600 font-semibold">Data de Saída</FormLabel>
                  <Popover>
                    <PopoverTrigger asChild>
                      <FormControl>
                        <Button variant="outline" className={cn("pl-3 text-left font-normal border-slate-200", !field.value && "text-muted-foreground")}>
                          {field.value ? format(field.value, "PPP", { locale: ptBR }) : <span>Escolha uma data</span>}
                          <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                        </Button>
                      </FormControl>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar mode="single" selected={field.value} onSelect={field.onChange} disabled={(date: Date) => date <= form.getValues('check_in_date')} initialFocus locale={ptBR} />
                    </PopoverContent>
                  </Popover>
                  <FormMessage />
                </FormItem>
              )} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <FormField control={form.control} name="check_in_time" render={({ field }: { field: any }) => (
                <FormItem>
                  <FormLabel className="text-slate-600 font-semibold">Horário Check-in</FormLabel>
                  <div className="relative">
                    <Clock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                    <Input type="time" className="pl-10 border-slate-200" {...field} />
                  </div>
                </FormItem>
              )} />
              <FormField control={form.control} name="check_out_time" render={({ field }: { field: any }) => (
                <FormItem>
                  <FormLabel className="text-slate-600 font-semibold">Horário Check-out</FormLabel>
                   <div className="relative">
                    <Clock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                    <Input type="time" className="pl-10 border-slate-200" {...field} />
                  </div>
                </FormItem>
              )} />
            </div>
          </section>

          {/* 3. Escolha da Acomodação */}
          <section className="space-y-4 pt-4 border-t border-slate-100">
            <div className="flex items-center gap-2 mb-4">
              <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">Passo 3</Badge>
              <h3 className="font-bold text-slate-700">Escolha da Acomodação</h3>
            </div>

            {roomConflict && (
              <Alert variant="destructive" className="bg-red-50 text-red-700 border-red-200">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Conflito de Disponibilidade</AlertTitle>
                <AlertDescription>
                  Este quarto já possui uma reserva confirmada para o período selecionado. Por favor, escolha outra acomodação ou altere as datas.
                </AlertDescription>
              </Alert>
            )}

            <FormField control={form.control} name="room_id" render={({ field }: { field: any }) => (
              <FormItem>
                <FormLabel className="text-slate-600 font-semibold">Quarto Disponível</FormLabel>
                 <Select onValueChange={field.onChange} value={field.value || ""}>
                  <FormControl>
                    <SelectTrigger className={cn("bg-white border-slate-200 focus:ring-blue-500", roomConflict && "border-red-500 ring-red-200")}>
                      <SelectValue placeholder={isCheckingAvailability ? "Verificando vagas..." : "Selecione o quarto"} />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {/* Exibe o quarto selecionado mesmo se houver conflito (para que o usuário veja qual é) */}
                    {availableRooms.length === 0 && !isCheckingAvailability && (
                      <div className="p-4 text-center text-sm text-slate-400">Nenhum quarto livre para este período.</div>
                    )}
                    {availableRooms.map((r: any) => (
                      <SelectItem key={r.id} value={r.id}>
                        Quarto {r.id} - {r.type} (Cap. {r.max_capacity} pessoas)
                      </SelectItem>
                    ))}
                    
                    {/* GARANTIA DE EXIBIÇÃO: Se o quarto atual não está na lista de disponíveis, mostra ele mesmo assim */}
                    {field.value && !availableRooms.find(r => r.id === field.value) && (
                       <SelectItem value={field.value} className="font-bold text-blue-600">
                         Quarto {field.value} (Atual)
                       </SelectItem>
                    )}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )} />
          </section>

          {/* 3. Acompanhantes */}
          <section className="space-y-4 pt-4 border-t border-slate-100">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">Passo 3</Badge>
                <h3 className="font-bold text-slate-700">Acompanhantes</h3>
              </div>
              <Button type="button" variant="outline" size="sm" onClick={() => append({ name: '', age: 18 })} className="text-blue-600 border-blue-200 hover:bg-blue-50">
                <Plus size={16} className="mr-1" /> Add Acompanhante
              </Button>
            </div>
            
            <div className="space-y-3">
              {fields.map((field, index) => (
                <div key={field.id} className="flex gap-3 items-end bg-slate-50 p-3 rounded-lg border border-slate-100">
                  <div className="flex-1 space-y-2">
                    <FormLabel className="text-[10px] uppercase font-bold text-slate-400">Nome</FormLabel>
                    <Input {...form.register(`companions.${index}.name` as const)} placeholder="Nome completo" className="bg-white" />
                  </div>
                  <div className="w-24 space-y-2">
                    <FormLabel className="text-[10px] uppercase font-bold text-slate-400">Idade</FormLabel>
                    <Input type="number" {...form.register(`companions.${index}.age` as const)} className="bg-white" />
                  </div>
                  <Button type="button" variant="ghost" size="icon" onClick={() => remove(index)} className="text-slate-400 hover:text-red-500 mb-0.5">
                    <Trash2 size={18} />
                  </Button>
                </div>
              ))}
              {fields.length === 0 && (
                <div className="text-center py-6 border-2 border-dashed border-slate-100 rounded-xl text-slate-400 text-sm italic">
                  Nenhum acompanhante adicionado.
                </div>
              )}
            </div>
          </section>

          {/* 4. Financeiro e Status */}
          <section className="space-y-4 pt-4 border-t border-slate-100 bg-slate-50/50 -mx-6 p-6">
             <div className="flex items-center gap-2 mb-4">
              <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">Passo 4</Badge>
              <h3 className="font-bold text-slate-700">Valores e Status</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <FormField control={form.control} name="daily_rate" render={({ field }: { field: any }) => (
                <FormItem>
                  <FormLabel className="text-slate-600 font-semibold">Valor da Diária (R$)</FormLabel>
                  <Input type="number" step="0.01" {...field} onChange={(e: React.ChangeEvent<HTMLInputElement>) => field.onChange(Number(e.target.value))} className="bg-white font-bold" />
                </FormItem>
              )} />

              <FormField control={form.control} name="deposit_amount" render={({ field }: { field: any }) => (
                <FormItem>
                  <FormLabel className="text-slate-600 font-semibold">Depósito / Sinal (R$)</FormLabel>
                  <Input type="number" step="0.01" {...field} onChange={(e: React.ChangeEvent<HTMLInputElement>) => field.onChange(Number(e.target.value))} className="bg-white font-bold text-green-600" />
                </FormItem>
              )} />

              <FormField control={form.control} name="payment_status" render={({ field }: { field: any }) => (
                <FormItem>
                  <FormLabel className="text-slate-600 font-semibold">Status Pagamento</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl><SelectTrigger className="bg-white"><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      <SelectItem value="pending">Pendente</SelectItem>
                      <SelectItem value="partial">Parcial</SelectItem>
                      <SelectItem value="paid">Pago</SelectItem>
                      <SelectItem value="cancelled">Cancelado</SelectItem>
                    </SelectContent>
                  </Select>
                </FormItem>
              )} />

              <FormField control={form.control} name="status" render={({ field }: { field: any }) => (
                <FormItem>
                  <FormLabel className="text-slate-600 font-semibold">Status da Reserva</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl><SelectTrigger className="bg-white"><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      <SelectItem value="pendente">Pendente</SelectItem>
                      <SelectItem value="confirmado">Confirmada</SelectItem>
                      <SelectItem value="ativo">Check-in Realizado</SelectItem>
                    </SelectContent>
                  </Select>
                </FormItem>
              )} />
            </div>

            <div className="mt-6 p-4 rounded-xl bg-blue-600 text-white flex justify-between items-center shadow-lg shadow-blue-200">
              <div className="flex items-center gap-3">
                <Calculator size={24} className="opacity-50" />
                <div>
                  <p className="text-[10px] uppercase font-bold opacity-70">Estimativa Total</p>
                  <p className="text-2xl font-black">R$ {totalPresumed.toFixed(2)}</p>
                </div>
              </div>
              <div className="text-right">
                <Badge variant="outline" className="border-white/30 text-white bg-white/10">Diária: R$ {watchedValues[4]?.toFixed(2) || '0.00'}</Badge>
              </div>
            </div>
          </section>

          {/* Observações */}
          <FormField control={form.control} name="notes" render={({ field }: { field: any }) => (
            <FormItem>
              <FormLabel className="text-slate-600 font-semibold">Observações Internas</FormLabel>
              <FormControl>
                <Textarea placeholder="Detalhes extras sobre a reserva, preferências do hóspede, etc." className="resize-none border-slate-200 bg-white min-h-[100px]" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )} />

          <div className="flex justify-end gap-3 pt-6">
            <Button type="button" variant="outline" onClick={onCancel}>Descartar</Button>
            <Button type="submit" disabled={isSubmitting} className="bg-slate-900 hover:bg-slate-800 px-10 font-bold">
              {isSubmitting ? 'Processando...' : (reservation ? 'Salvar Alterações' : 'Criar Reserva')}
            </Button>
          </div>

        </form>
      </Form>
    </div>
  );
}
