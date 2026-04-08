import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Search, User, MapPin, Phone, Mail, FileText, Calendar, Briefcase, Edit, UserPlus } from 'lucide-react';
import { useCustomers, Customer } from '@/hooks/useCustomers';
import { CustomerForm } from '@/components/CustomerForm';

interface CustomerSearchModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CustomerSearchModal({ open, onOpenChange }: CustomerSearchModalProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const { searchCustomers, getCustomerById } = useCustomers();

  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    setSelectedCustomer(null);
    setIsEditing(false);
    setIsCreating(false);
    
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const results = await searchCustomers(query);
      setSearchResults(results);
    } catch (error) {
      console.error('Erro na busca:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectCustomer = (customer: Customer) => {
    setSelectedCustomer(customer);
    setSearchResults([]);
    setSearchQuery('');
    setIsEditing(false);
    setIsCreating(false);
  };

  const handleActionSuccess = async (customer: Customer) => {
    setSelectedCustomer(customer);
    setIsEditing(false);
    setIsCreating(false);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Não informado';
    try {
       return new Date(dateString).toLocaleDateString('pt-BR');
    } catch {
       return dateString;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto border-none p-0 bg-slate-50/50 shadow-2xl">
        <div className="bg-slate-900 p-6 text-white flex items-center justify-between">
          <div>
            <h2 className="text-xl font-black flex items-center gap-2">
              <User size={24} className="text-blue-400" />
              Gestão de Hóspedes
            </h2>
            <p className="text-xs text-slate-400 font-bold uppercase tracking-widest mt-1">Base de dados centralizada</p>
          </div>
          <Button 
            onClick={() => setIsCreating(true)} 
            disabled={isCreating}
            className="bg-blue-600 hover:bg-blue-700 font-bold gap-2 shadow-lg shadow-blue-900/40"
          >
            <UserPlus size={18} />
            Novo Registro
          </Button>
        </div>

        <div className="p-6 space-y-6">
          {/* Campo de Busca */}
          {!isCreating && !isEditing && (
             <div className="relative group">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-slate-400 h-5 w-5 transition-colors group-focus-within:text-blue-500" />
              <Input
                placeholder="Nome, documento ou email..."
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                className="pl-12 h-14 bg-white border-slate-200 text-lg rounded-2xl shadow-sm focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          )}

          {/* Form de Criação/Edição */}
          {(isCreating || isEditing) && (
            <div className="animate-in fade-in slide-in-from-bottom-4">
              <CustomerForm
                customer={isEditing ? selectedCustomer : null}
                onSuccess={handleActionSuccess}
                onCancel={() => { setIsEditing(false); setIsCreating(false); }}
              />
            </div>
          )}

          {/* Resultados da Busca */}
          {!isCreating && !isEditing && searchQuery.length >= 2 && searchResults.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest pl-1">Resultados Localizados</h3>
              <div className="grid gap-3">
                {searchResults.map((customer) => (
                  <Card 
                    key={customer.id} 
                    className="group cursor-pointer hover:border-blue-200 hover:shadow-md transition-all border-slate-100"
                    onClick={() => handleSelectCustomer(customer)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center gap-4">
                        <div className="p-3 bg-slate-100 text-slate-400 rounded-xl group-hover:bg-blue-600 group-hover:text-white transition-colors">
                          <User size={20} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-bold text-slate-800 truncate">{customer.name}</h4>
                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 font-medium">
                            <span className="flex items-center gap-1"><Mail size={12} /> {customer.email || '-'}</span>
                            <span className="flex items-center gap-1"><Phone size={12} /> {customer.phone || '-'}</span>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Estado Vazio */}
          {!isCreating && !isEditing && searchQuery.length >= 2 && searchResults.length === 0 && !isSearching && (
            <div className="text-center py-12 opacity-40">
              <Search size={48} className="mx-auto mb-2" />
              <p className="font-medium">Nenhum hóspede encontrado para "{searchQuery}"</p>
            </div>
          )}

          {/* Detalhes do Cliente Selecionado */}
          {selectedCustomer && !isEditing && !isCreating && (
            <div className="space-y-4 animate-in fade-in slide-in-from-right-4">
              <div className="flex items-center justify-between border-b pb-2">
                <h3 className="text-sm font-black text-slate-400 uppercase tracking-widest">Destaque do Cadastro</h3>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => setIsEditing(true)}
                  className="text-blue-600 font-bold hover:bg-blue-50"
                >
                  <Edit className="h-4 w-4 mr-2" />
                  Editar Perfil
                </Button>
              </div>
              
              <Card className="border-none shadow-sm overflow-hidden bg-white">
                <CardContent className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {/* Coluna 1: Info Básica */}
                    <div className="space-y-6">
                      <div className="flex items-center gap-4">
                        <div className="w-16 h-16 bg-slate-900 text-white rounded-2xl flex items-center justify-center font-black text-2xl shadow-xl">
                          {selectedCustomer.name.substring(0, 1).toUpperCase()}
                        </div>
                        <div>
                          <h2 className="text-2xl font-black text-slate-900 leading-tight">{selectedCustomer.name}</h2>
                          <p className="text-sm font-bold text-blue-600">Hóspede Registrado</p>
                        </div>
                      </div>

                      <div className="grid gap-4 bg-slate-50 p-4 rounded-xl">
                        <div className="flex items-center gap-3 text-sm">
                          <Mail className="h-4 w-4 text-slate-400" />
                          <span className="font-semibold text-slate-700">{selectedCustomer.email || 'Não informado'}</span>
                        </div>
                        <div className="flex items-center gap-3 text-sm">
                          <Phone className="h-4 w-4 text-slate-400" />
                          <span className="font-semibold text-slate-700">{selectedCustomer.phone || 'Não informado'}</span>
                        </div>
                        <div className="flex items-center gap-3 text-sm">
                          <FileText className="h-4 w-4 text-slate-400" />
                          <span className="font-semibold text-slate-700">Doc: {selectedCustomer.document || 'Pendente'}</span>
                        </div>
                      </div>
                    </div>

                    {/* Coluna 2: Endereço e Detalhes */}
                    <div className="space-y-6">
                       <div className="space-y-3">
                        <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-1">
                          <MapPin size={12} /> Localização de Origem
                        </h4>
                        <div className="text-sm space-y-1">
                          <p className="font-bold text-slate-800">{selectedCustomer.address_street || 'Rua não informada'}, {selectedCustomer.address_number || 'S/N'}</p>
                          <p className="text-slate-500 font-medium">{selectedCustomer.address_neighborhood || 'Bairro -'} • {selectedCustomer.address_city || 'Cidade'}/{selectedCustomer.address_state || 'UF'}</p>
                          <p className="text-xs text-slate-400">CEP: {selectedCustomer.address_zip || '-'}</p>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-1">
                            <Calendar size={12} /> Nascimento
                          </h4>
                          <p className="text-sm font-bold text-slate-800">{formatDate(selectedCustomer.birth_date)}</p>
                        </div>
                        <div className="space-y-1">
                          <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-1">
                            <Briefcase size={12} /> Profissão
                          </h4>
                          <p className="text-sm font-bold text-slate-800">{selectedCustomer.profession || 'Não informado'}</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {selectedCustomer.notes && (
                    <div className="mt-8 pt-6 border-t border-slate-100">
                      <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Observações Internas</h4>
                      <p className="text-sm text-slate-600 bg-slate-50 p-3 rounded-lg border-l-4 border-slate-200">{selectedCustomer.notes}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>

        <div className="p-4 bg-white border-t border-slate-100 flex justify-end">
           <Button variant="outline" onClick={() => onOpenChange(false)} className="font-bold">
            Concluir e Sair
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
