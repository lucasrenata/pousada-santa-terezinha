import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { useToast } from '@/hooks/use-toast';
import { useCustomers, Customer } from '@/hooks/useCustomers';

const customerSchema = z.object({
  name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  email: z.string().email('Email inválido'),
  phone: z.string().min(10, 'Telefone inválido (mínimo 10 dígitos)'),
  document: z.string().min(5, 'Documento inválido'),
  address_street: z.string().min(1, 'Rua é obrigatória'),
  address_number: z.string().min(1, 'Número é obrigatório'),
  address_neighborhood: z.string().min(1, 'Bairro é obrigatório'),
  address_city: z.string().min(1, 'Cidade é obrigatória'),
  address_state: z.string().min(2, 'Estado (UF) é obrigatório'),
  address_zip: z.string().min(8, 'CEP inválido'),
  profession: z.string().optional(),
  birth_date: z.string().min(1, 'Data de nascimento é obrigatória'),
  notes: z.string().optional()
});

type CustomerFormData = z.infer<typeof customerSchema>;

interface CustomerFormProps {
  customer?: Customer | null;
  onSuccess: (customer: Customer) => void;
  onCancel: () => void;
}

export function CustomerForm({ customer, onSuccess, onCancel }: CustomerFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { createCustomer, updateCustomer } = useCustomers();
  const { toast } = useToast();

  const form = useForm<CustomerFormData>({
    resolver: zodResolver(customerSchema),
    defaultValues: {
      name: customer?.name || '',
      email: customer?.email || '',
      phone: customer?.phone || '',
      document: customer?.document || '',
      address_street: customer?.address_street || '',
      address_number: customer?.address_number || '',
      address_neighborhood: customer?.address_neighborhood || '',
      address_city: customer?.address_city || '',
      address_state: customer?.address_state || '',
      address_zip: customer?.address_zip || '',
      profession: customer?.profession || '',
      birth_date: customer?.birth_date?.substring(0, 10) || '',
      notes: customer?.notes || ''
    }
  });

  const calculateAge = (birthDate: string) => {
    if (!birthDate) return null;
    const today = new Date();
    const birth = new Date(birthDate);
    if (isNaN(birth.getTime())) return null;
    
    let age = today.getFullYear() - birth.getFullYear();
    const m = today.getMonth() - birth.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) {
        age--;
    }
    return age;
  };

  const birthDateValue = form.watch('birth_date');
  const age = calculateAge(birthDateValue);

  const onSubmit = async (data: CustomerFormData) => {
    setIsSubmitting(true);
    
    try {
      // Garantir nulos em vez de strings vazias para o backend
      const payload = Object.fromEntries(
        Object.entries(data).map(([key, value]) => [key, value === '' ? null : value])
      );

      let result;
      if (customer) {
        result = await updateCustomer(customer.id, payload);
        toast({ title: "Sucesso", description: "Dados do hóspede atualizados." });
      } else {
        result = await createCustomer(payload);
        toast({ title: "Sucesso", description: "Hóspede cadastrado com sucesso!" });
      }

      onSuccess(result);
    } catch (error: any) {
      console.error('Erro ao salvar cliente:', error);
      toast({
        title: "Erro",
        description: error.response?.data?.detail || "Erro ao salvar hóspede",
        variant: "destructive"
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="w-full max-w-2xl mx-auto shadow-md border-slate-200">
      <CardHeader className="bg-slate-50 border-b border-slate-100 rounded-t-xl mb-6">
        <CardTitle className="text-xl font-bold text-slate-800">
          {customer ? 'Editar Hóspede' : 'Novo Hóspede'}
        </CardTitle>
        <CardDescription>
          Gerencie as informações detalhadas do hóspede principal.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
              
              {/* Seção 1: Identidade */}
              <div className="md:col-span-2">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Informações Pessoais</h4>
              </div>

              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem className="md:col-span-2">
                  <FormLabel className="font-semibold">Nome Completo *</FormLabel>
                  <FormControl><Input placeholder="Ex: João Silva" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />

              <FormField control={form.control} name="email" render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-semibold">Email *</FormLabel>
                  <FormControl><Input placeholder="joao@email.com" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />

              <FormField control={form.control} name="phone" render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-semibold">WhatsApp / Telefone *</FormLabel>
                  <FormControl><Input placeholder="(11) 99999-9999" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />

              <FormField control={form.control} name="document" render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-semibold">CPF ou RG *</FormLabel>
                  <FormControl><Input placeholder="000.000.000-00" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />

              <FormField control={form.control} name="birth_date" render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-semibold flex items-center justify-between">
                    Data de Nascimento *
                    {age !== null && age >= 0 && (
                      <span className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                        {age} anos
                      </span>
                    )}
                  </FormLabel>
                  <FormControl><Input type="date" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />

              <FormField control={form.control} name="profession" render={({ field }) => (
                <FormItem className="md:col-span-2">
                  <FormLabel className="font-semibold">Profissão</FormLabel>
                  <FormControl><Input placeholder="Ex: Empresário" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />

              {/* Seção 2: Endereço */}
              <div className="md:col-span-2 pt-4 border-t border-slate-100">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Endereço de Origem</h4>
              </div>

              <FormField control={form.control} name="address_zip" render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-semibold">CEP *</FormLabel>
                  <FormControl><Input placeholder="00000-000" {...field} /></FormControl>
                </FormItem>
              )} />

              <FormField control={form.control} name="address_street" render={({ field }) => (
                <FormItem className="md:col-span-2">
                  <FormLabel className="font-semibold">Rua / Logradouro *</FormLabel>
                  <FormControl><Input placeholder="Ex: Av. Atlântica" {...field} /></FormControl>
                </FormItem>
              )} />

              <FormField control={form.control} name="address_number" render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-semibold">Número *</FormLabel>
                  <FormControl><Input placeholder="Ex: 100" {...field} /></FormControl>
                </FormItem>
              )} />

              <FormField control={form.control} name="address_neighborhood" render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-semibold">Bairro *</FormLabel>
                  <FormControl><Input placeholder="Bairro" {...field} /></FormControl>
                </FormItem>
              )} />

              <FormField control={form.control} name="address_city" render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-semibold">Cidade *</FormLabel>
                  <FormControl><Input placeholder="Cidade" {...field} /></FormControl>
                </FormItem>
              )} />

             <FormField control={form.control} name="address_state" render={({ field }) => (
                <FormItem>
                  <FormLabel className="font-semibold">Estado (UF) *</FormLabel>
                  <FormControl><Input placeholder="Ex: SP" {...field} /></FormControl>
                </FormItem>
              )} />

              {/* Notas */}
              <FormField control={form.control} name="notes" render={({ field }) => (
                <FormItem className="md:col-span-2 pt-2">
                  <FormLabel className="font-semibold">Observações Gerais</FormLabel>
                  <FormControl>
                    <Textarea 
                      placeholder="Informações relevantes sobre o hóspede..."
                      className="resize-none h-24"
                      {...field} 
                    />
                  </FormControl>
                </FormItem>
              )} />
            </div>

            <div className="flex gap-4 pt-4 border-t border-slate-100">
              <Button type="button" variant="outline" onClick={onCancel} className="flex-1 font-bold">
                Cancelar
              </Button>
              <Button type="submit" disabled={isSubmitting} className="flex-1 font-bold bg-slate-900 hover:bg-slate-800">
                {isSubmitting ? 'Salvando...' : customer ? 'Atualizar Dados' : 'Salvar Cadastro'}
              </Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
