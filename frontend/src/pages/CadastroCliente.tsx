import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { supabase } from '@/integrations/supabase/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Loader2, CheckCircle, Search } from 'lucide-react';
import { useRealTimeRooms } from '@/hooks/useRealTimeRooms';
import { Tables } from '@/integrations/supabase/types';
import { dateStringToUTCNoon } from '@/utils/dateCalculations';

type Customer = Tables<'customers'>;

const customerSchema = z.object({
  name: z.string().min(1, 'Nome é obrigatório'),
  email: z.string().email('Email inválido').min(1, 'Email é obrigatório'),
  phone: z.string().min(1, 'Telefone é obrigatório'),
  document: z.string().min(1, 'Documento (CPF/RG) é obrigatório'),
  address: z.string().min(1, 'Endereço é obrigatório'),
  city: z.string().min(1, 'Cidade é obrigatória'),
  state: z.string().min(1, 'Estado é obrigatório'),
  zip_code: z.string().min(1, 'CEP é obrigatório'),
  room_id: z.string().min(1, 'Quarto é obrigatório'),
  check_in_date: z.string().min(1, 'Data de check-in é obrigatória'),
  check_out_date: z.string().min(1, 'Data de check-out é obrigatória'),
  guests_count: z.number().min(1, 'Número de hóspedes é obrigatório'),
  total_reservation_value: z.number().min(0.01, 'Valor total da reserva é obrigatório'),
  notes: z.string().optional()
}).refine(data => new Date(data.check_out_date) > new Date(data.check_in_date), {
  message: "Data de check-out deve ser posterior ao check-in",
  path: ["check_out_date"]
});

type CustomerFormData = z.infer<typeof customerSchema>;

export default function CadastroCliente() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchDocument, setSearchDocument] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [foundCustomer, setFoundCustomer] = useState<Customer | null>(null);
  const { rooms, loading: roomsLoading } = useRealTimeRooms();

  const form = useForm<CustomerFormData>({
    resolver: zodResolver(customerSchema),
    defaultValues: {
      name: '',
      email: '',
      phone: '',
      document: '',
      address: '',
      city: '',
      state: '',
      zip_code: '',
      room_id: '',
      check_in_date: '',
      check_out_date: '',
      guests_count: 1,
      total_reservation_value: 0,
      notes: ''
    }
  });

  const normalizeDocument = (doc: string) => {
    return doc.replace(/[^\d]/g, '');
  };

  const searchCustomerByDocument = async () => {
    if (!searchDocument.trim()) return;
    
    try {
      setIsSearching(true);
      setError(null);
      
      const normalizedSearch = normalizeDocument(searchDocument);
      
      // First try exact match on normalized document
      let { data: customers, error } = await supabase
        .from('customers')
        .select('*')
        .eq('document', normalizedSearch);
      
      // If no exact match, try with original document and ilike pattern
      if (!customers?.length) {
        const { data: customersIlike, error: errorIlike } = await supabase
          .from('customers')
          .select('*')
          .ilike('document', `%${normalizedSearch}%`)
          .limit(1);
        
        customers = customersIlike;
        error = errorIlike;
      }

      if (error) {
        throw error;
      }

      if (customers && customers.length > 0) {
        const customer = customers[0];
        setFoundCustomer(customer);
        
        // Auto-fill form with customer data
        form.setValue('name', customer.name || '');
        form.setValue('email', customer.email || '');
        form.setValue('phone', customer.phone || '');
        form.setValue('document', customer.document || '');
        form.setValue('address', customer.address || '');
        form.setValue('city', customer.city || '');
        form.setValue('state', customer.state || '');
        form.setValue('zip_code', customer.zip_code || '');
        form.setValue('notes', customer.notes || '');
      } else {
        setFoundCustomer(null);
        setError('Cliente não encontrado com este documento.');
      }
    } catch (err) {
      console.error('Erro ao buscar cliente:', err);
      setError('Erro ao buscar cliente. Tente novamente.');
    } finally {
      setIsSearching(false);
    }
  };

  const onSubmit = async (data: CustomerFormData) => {
    try {
      setIsSubmitting(true);
      setError(null);

      // First, check room availability
      const { data: isAvailable, error: availabilityError } = await supabase.rpc(
        'check_room_availability',
        {
          p_room_id: parseInt(data.room_id),
          p_check_in: dateStringToUTCNoon(data.check_in_date),
          p_check_out: dateStringToUTCNoon(data.check_out_date)
        }
      );

      if (availabilityError) {
        throw new Error('Erro ao verificar disponibilidade do quarto');
      }

      if (!isAvailable) {
        setError('O quarto selecionado não está disponível para as datas escolhidas. Por favor, selecione outras datas ou outro quarto.');
        return;
      }

      let customerId: string;

      // Use existing customer or create new one
      if (foundCustomer) {
        // Update existing customer with new data
        const { data: updatedCustomer, error: updateError } = await supabase
          .from('customers')
          .update({
            name: data.name,
            email: data.email || null,
            phone: data.phone || null,
            address: data.address || null,
            city: data.city || null,
            state: data.state || null,
            zip_code: data.zip_code || null,
            notes: data.notes || null,
            total_reservation_value: (foundCustomer.total_reservation_value || 0) + data.total_reservation_value
          })
          .eq('id', foundCustomer.id)
          .select()
          .single();

        if (updateError) {
          throw updateError;
        }
        
        customerId = foundCustomer.id;
      } else {
        // Create new customer
        const customerData = {
          name: data.name,
          email: data.email || null,
          phone: data.phone || null,
          document: data.document || null,
          address: data.address || null,
          city: data.city || null,
          state: data.state || null,
          zip_code: data.zip_code || null,
          total_reservation_value: data.total_reservation_value || 0,
          notes: data.notes || null
        };

        const { data: customer, error: customerError } = await supabase
          .from('customers')
          .insert(customerData)
          .select()
          .single();

        if (customerError) {
          throw customerError;
        }
        
        customerId = customer.id;
      }

      // Convert dates to UTC noon format and calculate daily rate and days
      const checkInUTC = dateStringToUTCNoon(data.check_in_date);
      const checkOutUTC = dateStringToUTCNoon(data.check_out_date);
      
      const checkIn = new Date(data.check_in_date + 'T00:00:00');
      const checkOut = new Date(data.check_out_date + 'T00:00:00');
      const daysDiff = Math.ceil((checkOut.getTime() - checkIn.getTime()) / (1000 * 60 * 60 * 24));
      const dailyRate = data.total_reservation_value / (daysDiff * data.guests_count);

      // Create reservation
      const reservationData = {
        customer_id: customerId,
        room_id: parseInt(data.room_id),
        check_in_date: checkInUTC,
        check_out_date: checkOutUTC,
        guests_count: data.guests_count,
        daily_rate: dailyRate,
        total_amount: data.total_reservation_value,
        status: 'pending' as const,
        payment_status: 'pending' as const,
        notes: data.notes || null
      };

      const { error: reservationError } = await supabase
        .from('reservations')
        .insert(reservationData);

      if (reservationError) {
        throw reservationError;
      }

      setIsSubmitted(true);
    } catch (err: any) {
      console.error('Erro ao enviar formulário:', err);
      
      // Verificar se é erro de documento duplicado
      if (err?.code === '23505' || err?.message?.includes('customers_document_key')) {
        setError('Documento do hóspede já cadastrado. Use a busca acima para encontrar o cliente existente.');
      } else {
        setError(err instanceof Error ? err.message : 'Erro ao enviar formulário. Tente novamente.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSubmitted) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center">
            <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-foreground mb-2">
              Formulário enviado com sucesso!
            </h1>
            <p className="text-lg text-muted-foreground mb-2">
              Pousada Santa Terezinha do Menino Jesus agradece.
            </p>
            <p className="text-sm text-muted-foreground">
              Sua reserva foi criada com status "Pendente" e aparecerá no sistema de reservas.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl text-center">
              Cadastro de Cliente
            </CardTitle>
            <p className="text-center text-muted-foreground">
              Preencha todos os campos abaixo para completar sua reserva
            </p>
          </CardHeader>
          <CardContent>
            {/* Document Search Section */}
            <div className="mb-8 p-4 border rounded-lg bg-muted/50">
              <h3 className="text-lg font-semibold mb-3">Buscar Cliente Existente</h3>
              <div className="flex gap-2">
                <Input
                  placeholder="Digite o CPF/RG para buscar cliente existente"
                  value={searchDocument}
                  onChange={(e) => setSearchDocument(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      searchCustomerByDocument();
                    }
                  }}
                />
                <Button 
                  type="button"
                  onClick={searchCustomerByDocument}
                  disabled={isSearching || !searchDocument.trim()}
                >
                  {isSearching ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      <Search className="h-4 w-4 mr-1" />
                      Buscar
                    </>
                  )}
                </Button>
              </div>
              {foundCustomer && (
                <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded">
                  <p className="text-sm text-green-800">
                    <strong>Cliente encontrado:</strong> {foundCustomer.name}
                    {foundCustomer.email && ` - ${foundCustomer.email}`}
                  </p>
                  <p className="text-xs text-green-600 mt-1">
                    Os campos foram preenchidos automaticamente. Você pode editá-los se necessário.
                  </p>
                </div>
              )}
            </div>

            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Nome Completo *</FormLabel>
                        <FormControl>
                          <Input placeholder="Digite seu nome completo" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Email *</FormLabel>
                        <FormControl>
                          <Input type="email" placeholder="seu@email.com" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="phone"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Telefone *</FormLabel>
                        <FormControl>
                          <Input placeholder="(00) 00000-0000" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="document"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>CPF/RG *</FormLabel>
                        <FormControl>
                          <Input placeholder="000.000.000-00" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <FormField
                  control={form.control}
                  name="address"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Endereço *</FormLabel>
                      <FormControl>
                        <Input placeholder="Rua, número, complemento" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <FormField
                    control={form.control}
                    name="city"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Cidade *</FormLabel>
                        <FormControl>
                          <Input placeholder="Nome da cidade" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="state"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Estado *</FormLabel>
                        <FormControl>
                          <Input placeholder="SP" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="zip_code"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>CEP *</FormLabel>
                        <FormControl>
                          <Input placeholder="00000-000" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="room_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Quarto *</FormLabel>
                        <FormControl>
                          <Select onValueChange={field.onChange} defaultValue={field.value}>
                            <SelectTrigger>
                              <SelectValue placeholder={roomsLoading ? "Carregando quartos..." : "Selecione um quarto"} />
                            </SelectTrigger>
                            <SelectContent>
                              {!roomsLoading && rooms
                                .filter(room => room.status === 'available')
                                .map((room) => (
                                  <SelectItem key={room.id} value={room.id.toString()}>
                                    Quarto {room.id}
                                  </SelectItem>
                                ))
                              }
                            </SelectContent>
                          </Select>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="guests_count"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Número de Hóspedes *</FormLabel>
                        <FormControl>
                          <Input 
                            type="number" 
                            min="1" 
                            placeholder="1"
                            {...field}
                            onChange={(e) => field.onChange(parseInt(e.target.value) || 1)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="check_in_date"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Data de Check-in *</FormLabel>
                        <FormControl>
                          <Input 
                            type="date" 
                            {...field}
                            min={new Date().toISOString().split('T')[0]}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="check_out_date"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Data de Check-out *</FormLabel>
                        <FormControl>
                          <Input 
                            type="date" 
                            {...field}
                            min={new Date().toISOString().split('T')[0]}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <FormField
                  control={form.control}
                  name="total_reservation_value"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Valor Total da Reserva *</FormLabel>
                      <FormControl>
                        <Input 
                          type="number" 
                          min="0" 
                          step="0.01" 
                          placeholder="0,00"
                          {...field}
                          onChange={(e) => field.onChange(parseFloat(e.target.value) || 0)}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="notes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Observações (opcional)</FormLabel>
                      <FormControl>
                        <Textarea 
                          placeholder="Informações adicionais sobre sua reserva"
                          rows={3}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {error && (
                  <div className="text-destructive text-sm text-center">
                    {error}
                  </div>
                )}

                <Button 
                  type="submit" 
                  className="w-full"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Enviando...
                    </>
                  ) : (
                    'Enviar Formulário'
                  )}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}