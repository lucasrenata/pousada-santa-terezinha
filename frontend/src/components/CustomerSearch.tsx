import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Search, Plus, User, IdCard } from 'lucide-react';
import { useCustomers, Customer } from '@/hooks/useCustomers';

interface CustomerSearchProps {
  onSelectCustomer: (customer: Customer) => void;
  onCreateNew: () => void;
  selectedCustomer?: Customer | null;
}

export function CustomerSearch({ onSelectCustomer, onCreateNew, selectedCustomer }: CustomerSearchProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Customer[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const { searchCustomers } = useCustomers();

  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    
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

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 h-4 w-4" />
          <Input
            placeholder="Pesquisar por nome, CPF, email ou telefone..."
            value={searchQuery}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleSearch(e.target.value)}
            className="pl-10 h-11 border-slate-200 focus:ring-blue-500"
          />
        </div>
        <Button onClick={onCreateNew} variant="outline" className="h-11 font-bold border-slate-200 hover:bg-slate-50">
          <Plus className="h-4 w-4 mr-2 text-blue-600" />
          Novo Cadastro
        </Button>
      </div>

      {selectedCustomer && (
        <Card className="bg-blue-50/50 border-blue-100 shadow-sm animate-in fade-in duration-300">
          <CardContent className="p-4">
            <div className="flex items-center gap-4">
              <div className="p-2.5 bg-blue-600 text-white rounded-full">
                <User size={20} />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="font-bold text-slate-900 truncate">{selectedCustomer.name}</h4>
                <div className="flex items-center gap-3 text-xs text-slate-500 font-medium">
                  <span className="flex items-center gap-1">
                    <IdCard size={12} />
                    {selectedCustomer.document || 'Sem documento'}
                  </span>
                  <span>•</span>
                  <span className="truncate">{selectedCustomer.email || 'Sem email'}</span>
                </div>
              </div>
              <Badge className="bg-blue-600 text-white border-0 text-[10px] uppercase font-bold px-2 py-0">Principal</Badge>
            </div>
          </CardContent>
        </Card>
      )}

      {searchQuery.length >= 2 && searchResults.length > 0 && (
        <Card className="border-slate-200 shadow-xl overflow-hidden animate-in slide-in-from-top-2">
          <CardContent className="p-0">
            <div className="max-h-72 overflow-y-auto divide-y divide-slate-100">
              {searchResults.map((customer) => (
                <div
                  key={customer.id}
                  className="p-4 hover:bg-slate-50 cursor-pointer transition-colors flex items-center gap-4"
                  onClick={() => {
                    onSelectCustomer(customer);
                    setSearchQuery('');
                    setSearchResults([]);
                  }}
                >
                  <div className="p-2 bg-slate-100 text-slate-400 rounded-full group-hover:bg-blue-100 group-hover:text-blue-600">
                    <User size={18} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-bold text-slate-800 text-sm truncate">{customer.name}</h4>
                    <p className="text-xs text-slate-500 truncate">
                      {customer.document} {customer.email ? `• ${customer.email}` : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {searchQuery.length >= 2 && searchResults.length === 0 && !isSearching && (
        <div className="text-center py-6 bg-slate-50 rounded-xl border border-dashed border-slate-200">
          <p className="text-sm text-slate-500 font-medium italic mb-3">Nenhum hóspede localizado.</p>
          <Button 
            onClick={onCreateNew} 
            variant="outline" 
            size="sm"
            className="font-bold text-blue-600 border-blue-100 bg-white"
          >
            <Plus className="h-4 w-4 mr-2" />
            Cadastrar "{searchQuery}"
          </Button>
        </div>
      )}

      {isSearching && (
        <div className="flex justify-center py-6">
          <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      )}
    </div>
  );
}