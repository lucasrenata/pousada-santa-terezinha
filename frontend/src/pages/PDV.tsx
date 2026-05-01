import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Plus, Search, ShoppingCart, Wallet, Receipt, 
  Trash2, CreditCard, Banknote, QrCode, User, 
  Package, ChevronRight, X, Minus, Trash, LogOut,
  Maximize2, Weight, Coffee, Barcode, Utensils,
  ChartLine, Tag, CheckCircle2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import api from '@/services/api';

// --- TYPES ---
interface Product {
  id: number;
  name: string;
  price: number;
  category: string;
  stock_quantity: number;
  barcode?: string;
}

interface ComandaItem {
  id: number;
  comanda_id: number;
  product_id?: number;
  quantity: number;
  unit_price: number;
  description?: string;
  type: 'produto' | 'peso' | 'marmitex';
}

interface Comanda {
  id: number;
  identificador: string;
  status: 'aberta' | 'paga' | 'cancelada' | 'lancada_no_quarto';
  total: number;
  booking_id?: number;
  items: ComandaItem[];
}

interface CaixaSession {
  id: number;
  status: 'aberto' | 'fechado';
  opening_balance: number;
  opened_at: string;
}

interface ActiveReservation {
  id: number;
  room_number: string;
  guest_name: string;
}

// --- UI COMPONENTS: ACTION CARDS ---
const ActionCard = ({ title, icon: Icon, color, children, onAdd, disabled }: any) => (
  <Card className={`border-slate-200 shadow-sm overflow-hidden transition-all ${disabled ? 'opacity-50 grayscale' : 'hover:border-slate-300'}`}>
    <CardHeader className="p-4 bg-slate-50/50 flex flex-row items-center gap-2 border-b border-slate-100">
      <div className={`p-1.5 rounded-lg ${color} bg-white shadow-sm`}>
        <Icon size={16} />
      </div>
      <CardTitle className="text-xs font-black text-slate-700 uppercase tracking-widest">{title}</CardTitle>
    </CardHeader>
    <CardContent className="p-4 flex gap-2">
      {children}
      {onAdd && (
        <Button 
          variant="secondary" 
          className="font-bold text-xs px-4 rounded-xl" 
          onClick={onAdd}
          disabled={disabled}
        >
          Adicionar
        </Button>
      )}
    </CardContent>
  </Card>
);

export default function PDV() {
  const { toast } = useToast();
  const comandaInputRef = useRef<HTMLInputElement>(null);
  const productBarcodeRef = useRef<HTMLInputElement>(null);
  
  // Data States
  const [caixa, setCaixa] = useState<CaixaSession | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [activeComandas, setActiveComandas] = useState<Comanda[]>([]);
  const [selectedComanda, setSelectedComanda] = useState<Comanda | null>(null);
  const [activeReservations, setActiveReservations] = useState<ActiveReservation[]>([]);
  
  // Input States
  const [comandaScannerValue, setComandaScannerValue] = useState('');
  const [productBarcodeValue, setProductBarcodeValue] = useState('');
  const [searchProductName, setSearchProductName] = useState('');
  const [pesoValue, setPesoValue] = useState('');
  const [marmitexValue, setMarmitexValue] = useState('');
  const [discountAmount, setDiscountAmount] = useState(0);
  
  // UI States
  const [showCaixaModal, setShowCaixaModal] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [openingBalance, setOpeningBalance] = useState('0');
  const [closingBalance, setClosingBalance] = useState('0');
  const [movimentacaoAmount, setMovimentacaoAmount] = useState('');
  const [movimentacaoDesc, setMovimentacaoDesc] = useState('');
  const [caixaSummary, setCaixaSummary] = useState<any>(null);

  // --- QUICK ACCESS (ATALHOS) ---
  const [showQuickAccessModal, setShowQuickAccessModal] = useState(false);
  const [isUpdatingQuickAccess, setIsUpdatingQuickAccess] = useState(false);
  const [tempSelectedIds, setTempSelectedIds] = useState<number[]>([]);
  const quickAccessProducts = useMemo(() => products.filter(p => p.is_quick_access), [products]);

  // Sincroniza seleção temporária ao abrir o modal
  useEffect(() => {
    if (showQuickAccessModal) {
      setTempSelectedIds(quickAccessProducts.map(p => p.id));
    }
  }, [showQuickAccessModal, quickAccessProducts]);

  // --- MULTI-COMANDA MODE ---
  const [isMultiMode, setIsMultiMode] = useState(false);
  const [multiSelectedIds, setMultiSelectedIds] = useState<number[]>([]);

  const selectedMultiComandas = useMemo(() => {
    return activeComandas.filter(c => multiSelectedIds.includes(c.id));
  }, [activeComandas, multiSelectedIds]);

  const grandTotal = useMemo(() => {
    if (isMultiMode) {
      return selectedMultiComandas.reduce((acc, c) => acc + (c.total || 0), 0);
    }
    return selectedComanda?.total || 0;
  }, [isMultiMode, selectedMultiComandas, selectedComanda]);

  const formatCurrency = (v: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);

  // Load Data
  useEffect(() => {
    loadData();
    comandaInputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (caixa && showCaixaModal) {
      loadCaixaSummary();
    }
  }, [caixa, showCaixaModal]);

  const loadCaixaSummary = async () => {
    try {
      const res = await api.get('/pdv/caixa/summary');
      setCaixaSummary(res.data);
    } catch (err) {
      console.error("Erro ao carregar resumo do caixa", err);
    }
  };

  const loadData = async () => {
    try {
      const [caixaRes, productsRes, comandasRes, reservationsRes] = await Promise.all([
        api.get('/pdv/caixa/status'),
        api.get('/products/'),
        api.get('/pdv/comandas/'),
        api.get('/bookings/')
      ]);
      
      setCaixa(caixaRes.data);
      setProducts(productsRes.data);
      setActiveComandas(comandasRes.data);
      setActiveReservations(reservationsRes.data.filter((r: any) => r.status === 'ativo'));
    } catch (err) {
      toast({ title: "Erro", description: "Falha ao carregar dados.", variant: "destructive" });
    }
  };

  // --- LOGIC: SCANNER COMANDA ---
  const handleScannerComanda = async (e: React.KeyboardEvent) => {
    if (e.key !== 'Enter' || !comandaScannerValue) return;

    // 1. Verificar se já existe aberta localmente
    let existente = activeComandas.find(c => c.identificador === comandaScannerValue);
    
    if (!existente) {
      try {
        const res = await api.post('/pdv/comandas/', { identificador: comandaScannerValue });
        existente = res.data;
        setActiveComandas(prev => {
          const jaExiste = prev.find(c => c.id === res.data.id);
          if (jaExiste) return prev;
          return [...prev, res.data];
        });
      } catch (err) {
        toast({ title: "Erro", description: "Erro ao processar comanda.", variant: "destructive" });
        return;
      }
    }

    if (isMultiMode) {
      if (multiSelectedIds.includes(existente!.id)) {
        toast({ title: "Atenção", description: "Esta comanda já está selecionada." });
      } else {
        setMultiSelectedIds(prev => [...prev, existente!.id]);
        toast({ title: "Comanda Adicionada", description: `ID: ${existente!.identificador}` });
      }
      setComandaScannerValue('');
    } else {
      setSelectedComanda(existente!);
      setComandaScannerValue('');
      toast({ title: "Comanda Selecionada", description: `Ativa: ${existente!.identificador}` });
      setTimeout(() => productBarcodeRef.current?.focus(), 100);
    }
  };

  // --- LOGIC: SCANNER PRODUTO ---
  const handleScannerProduct = async (e: React.KeyboardEvent) => {
    if (e.key !== 'Enter' || !productBarcodeValue || !selectedComanda) return;

    const produto = products.find(p => p.barcode === productBarcodeValue);
    if (produto) {
      await addItemToComanda(produto);
      setProductBarcodeValue('');
    } else {
      toast({ title: "Não encontrado", description: "Produto com este código não localizado.", variant: "destructive" });
    }
  };

  const addItemToComanda = async (product: typeof products[0] | null, manualData?: { price: number, desc: string, type: 'peso' | 'marmitex' }) => {
    const target = isMultiMode ? selectedMultiComandas[0] : selectedComanda;
    
    if (!target) {
      toast({ title: "Atenção", description: isMultiMode ? "Selecione pelo menos uma comanda primeiro." : "Identifique a comanda no topo.", variant: "destructive" });
      comandaInputRef.current?.focus();
      return;
    }

    try {
      const itemData = product ? {
        product_id: product.id,
        quantity: 1,
        unit_price: product.price,
        description: product.name,
        type: 'produto'
      } : {
        quantity: 1,
        unit_price: manualData!.price,
        description: manualData!.desc,
        type: manualData!.type
      };

      const res = await api.post(`/pdv/comandas/${target.id}/itens/`, itemData);
      
      const updatedComanda = {
        ...target,
        items: [...(target.items || []), res.data],
        total: (target.total || 0.0) + itemData.unit_price
      };
      
      if (isMultiMode) {
        setActiveComandas(prev => prev.map(c => c.id === updatedComanda.id ? updatedComanda : c));
      } else {
        setSelectedComanda(updatedComanda);
        setActiveComandas(prev => prev.map(c => c.id === updatedComanda.id ? updatedComanda : c));
      }
      
      if (manualData?.type === 'peso') setPesoValue('');
      if (manualData?.type === 'marmitex') setMarmitexValue('');
    } catch (err) {
      toast({ title: "Erro", description: "Erro ao adicionar item.", variant: "destructive" });
    }
  };

  const removeItemFromComanda = async (itemId: number) => {
    try {
      await api.delete(`/pdv/comandas/itens/${itemId}`);
      const item = selectedComanda?.items.find(i => i.id === itemId);
      if (!selectedComanda || !item) return;

      const updatedComanda = {
        ...selectedComanda,
        items: selectedComanda.items.filter(i => i.id !== itemId),
        total: selectedComanda.total - (item.unit_price * item.quantity)
      };
      
      setSelectedComanda(updatedComanda);
      setActiveComandas(prev => prev.map(c => c.id === updatedComanda.id ? updatedComanda : c));
    } catch (err) {
      toast({ title: "Erro", description: "Erro ao remover item.", variant: "destructive" });
    }
  };

  const updateItemQuantity = async (itemId: number, newQty: number) => {
    if (newQty < 0.1) return; // Mínimo para pratos por peso também
    try {
      const res = await api.patch(`/pdv/comandas/itens/${itemId}`, { quantity: newQty });
      if (selectedComanda) {
        const updatedItems = selectedComanda.items.map(it => it.id === itemId ? res.data : it);
        const newTotal = updatedItems.reduce((acc, it) => acc + (it.unit_price * it.quantity), 0);
        const updatedComanda = { ...selectedComanda, items: updatedItems, total: newTotal };
        setSelectedComanda(updatedComanda);
        setActiveComandas(prev => prev.map(c => c.id === updatedComanda.id ? updatedComanda : c));
      }
    } catch (err) {
      toast({ title: "Erro", description: "Erro ao atualizar quantidade.", variant: "destructive" });
    }
  };

  const finalizeSale = async (paymentMethod?: string, bookingId?: number) => {
    try {
      if (isMultiMode) {
        if (selectedMultiComandas.length === 0) return;
        const payload = { 
          comanda_ids: multiSelectedIds,
          payment_method: paymentMethod,
          lancada_no_quarto: !!bookingId,
          booking_id: bookingId,
          discount: discountAmount
        };
        await api.post('/pdv/comandas/batch-finalizar', payload);
        toast({ title: "Sucesso!", description: `${selectedMultiComandas.length} comandas finalizadas.` });
        setMultiSelectedIds([]);
      } else {
        if (!selectedComanda) return;
        const payload = bookingId 
          ? { lancada_no_quarto: true, booking_id: bookingId, discount: discountAmount } 
          : { payment_method: paymentMethod, discount: discountAmount };
        await api.post(`/pdv/comandas/${selectedComanda.id}/finalizar`, payload);
        toast({ title: "Sucesso!", description: "Venda finalizada." });
        setSelectedComanda(null);
      }
      
      setShowPaymentModal(false);
      setDiscountAmount(0); // Reset desconto
      loadData();
      comandaInputRef.current?.focus();
    } catch (err: any) {
      toast({ title: "Erro", description: err.response?.data?.detail || "Erro ao finalizar.", variant: "destructive" });
    }
  };

  const handleOpenCaixa = async () => {
    try {
      const res = await api.post('/pdv/caixa/abrir', { opening_balance: parseFloat(openingBalance) });
      setCaixa(res.data);
      toast({ title: "Sucesso", description: "Caixa aberto com sucesso!" });
      loadCaixaSummary();
    } catch (err) {
      toast({ title: "Erro", description: "Erro ao abrir o caixa.", variant: "destructive" });
    }
  };

  const handleCloseCaixa = async () => {
    try {
      await api.post('/pdv/caixa/fechar?closing_balance=' + closingBalance);
      setCaixa(null);
      setShowCaixaModal(false);
      toast({ title: "Sucesso", description: "Caixa fechado com sucesso!" });
    } catch (err) {
      toast({ title: "Erro", description: "Erro ao fechar o caixa.", variant: "destructive" });
    }
  };

  const handleMovimentacao = async (tipo: 'suprimento' | 'sangria') => {
    if (!movimentacaoAmount || !movimentacaoDesc) {
      toast({ title: "Atenção", description: "Preencha valor e descrição.", variant: "destructive" });
      return;
    }
    try {
      await api.post('/pdv/caixa/movimentar', {
        type: tipo,
        amount: parseFloat(movimentacaoAmount),
        description: movimentacaoDesc
      });
      toast({ title: "Sucesso", description: `${tipo === 'suprimento' ? 'Entrada' : 'Retirada'} registrada.` });
      setMovimentacaoAmount('');
      setMovimentacaoDesc('');
      loadCaixaSummary();
    } catch (err) {
      toast({ title: "Erro", description: "Erro ao registrar movimentação.", variant: "destructive" });
    }
  };

  const handleUpdateQuickAccess = async (ids: number[]) => {
    setIsUpdatingQuickAccess(true);
    try {
      await api.patch('/products/bulk-quick-access', { product_ids: ids });
      toast({ title: "Sucesso", description: "Atalhos atualizados!" });
      loadData(); // Recarrega produtos para refletir a mudança
      setShowQuickAccessModal(false);
    } catch (err) {
      toast({ title: "Erro", description: "Falha ao salvar atalhos.", variant: "destructive" });
    } finally {
      setIsUpdatingQuickAccess(false);
    }
  };

  // --- FILTERS & CATEGORIES ---
  const filteredProductsBySearch = useMemo(() => {
    return products.filter(p => p.name.toLowerCase().includes(searchProductName.toLowerCase()));
  }, [products, searchProductName]);

  const categories = useMemo(() => Array.from(new Set(products.map(p => p.category))), [products]);

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] md:h-screen bg-slate-50 -mx-4 sm:-mx-6 lg:-mx-8 -my-4 md:-my-8 relative overflow-hidden font-sans">
      
      {/* ── TOP BAR: SCANNER GLOBAL ── */}
      <div className="bg-white border-b border-slate-200 px-4 md:px-8 py-4 z-40 shadow-sm flex-shrink-0">
        <div className="max-w-[1600px] mx-auto flex items-center gap-6">
           <div className="flex items-center gap-3 pr-6 border-r border-slate-100">
             <div className="p-2 bg-blue-600 rounded-xl text-white shadow-lg shadow-blue-100 hidden sm:block">
               <Receipt size={24} />
             </div>
             <div>
               <h1 className="text-lg font-black text-slate-800 tracking-tight leading-none mb-1">PDV Flex</h1>
               <div className="flex items-center gap-1.5">
                  <Badge variant={caixa ? "success" : "destructive"} className="h-1.5 w-1.5 rounded-full p-0" />
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{caixa ? `Caixa ON #${caixa.id}` : "Caixa OFF"}</span>
               </div>
             </div>
           </div>

           <div className="flex-1 relative group">
              <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-blue-500 transition-colors">
                <Barcode size={22} />
              </div>
              <Input 
                 ref={comandaInputRef} disabled={!caixa}
                 placeholder="Ler código da COMANDA ou nome avulso..." 
                 className="h-14 pl-14 text-xl font-bold bg-slate-100/50 border-none rounded-2xl focus:bg-white focus:ring-2 focus:ring-blue-400 transition-all shadow-inner"
                 value={comandaScannerValue}
                 onChange={e => setComandaScannerValue(e.target.value)}
                 onKeyDown={handleScannerComanda}
              />
              <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
                 <kbd className="hidden sm:inline-flex h-6 items-center gap-1 rounded border bg-slate-50 px-1.5 font-mono text-[10px] font-medium text-slate-400 opacity-100">
                   <span className="text-xs">↵</span> ENTER
                 </kbd>
              </div>
           </div>

            <div className="flex items-center gap-2 pl-6 border-l border-slate-100">
             <Button 
                variant={isMultiMode ? "default" : "outline"}
                disabled={!caixa}
                onClick={() => {
                  setIsMultiMode(!isMultiMode);
                  if (!isMultiMode) {
                    setSelectedComanda(null);
                    setMultiSelectedIds([]);
                    toast({ title: "Modo Múltiplo Ativo", description: "Leia as comandas que deseja unir." });
                  } else {
                    toast({ title: "Modo Único Ativo" });
                  }
                }}
             >
               <Receipt size={20} />
               <span className="hidden lg:inline">{isMultiMode ? "Múltiplo: ON" : "Modo Múltiplo"}</span>
             </Button>

             <Button 
                variant="ghost" 
                className="rounded-xl border-emerald-100 font-bold gap-2 h-12 hover:bg-emerald-50 text-emerald-600"
                onClick={() => setShowCaixaModal(true)}
             >
               <Wallet size={20} className="text-emerald-600" />
               <span className="hidden lg:inline">Gestão de Caixa</span>
             </Button>
           </div>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row flex-1 overflow-y-auto lg:overflow-hidden max-w-[1600px] mx-auto w-full p-4 lg:p-8 gap-4 lg:gap-8">
        
        {/* ── LEFT COLUMN: INPUTS (60%) ── */}
        <div className="flex-[3] flex flex-col gap-4 lg:gap-6 overflow-visible lg:overflow-hidden min-h-[500px] lg:min-h-0">
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
             {/* Lançar Prato por Peso */}
             <ActionCard 
               title="Lançar Prato por Peso" 
               icon={Weight} 
               color="text-orange-500" 
               disabled={!caixa}
               onAdd={() => {
                 const val = parseFloat(pesoValue);
                 if (val > 0) addItemToComanda(null, { price: val, desc: 'Prato por Peso', type: 'peso' });
               }}
             >
               <div className="relative flex-1">
                 <span className="absolute left-3 top-1/2 -translate-y-1/2 font-bold text-slate-300 text-sm">R$</span>
                 <Input 
                   type="number" 
                   placeholder="0,00" 
                   className="pl-10 h-10 border-slate-200 bg-white" 
                   value={pesoValue} 
                   onChange={e => setPesoValue(e.target.value)}
                   onKeyDown={e => {
                     if (e.key === 'Enter') {
                       const val = parseFloat(pesoValue);
                       if (val > 0) addItemToComanda(null, { price: val, desc: 'Prato por Peso', type: 'peso' });
                     }
                   }}
                 />
               </div>
             </ActionCard>

             {/* Lançar Marmitex */}
             <ActionCard 
               title="Lançar Marmitex" 
               icon={Utensils} 
               color="text-emerald-500" 
               disabled={!caixa}
               onAdd={() => {
                 const val = parseFloat(marmitexValue);
                 if (val > 0) addItemToComanda(null, { price: val, desc: 'Marmitex', type: 'marmitex' });
               }}
             >
               <div className="relative flex-1">
                 <span className="absolute left-3 top-1/2 -translate-y-1/2 font-bold text-slate-300 text-sm">R$</span>
                 <Input 
                   type="number" 
                   placeholder="0,00" 
                   className="pl-10 h-10 border-slate-200 bg-white" 
                   value={marmitexValue} 
                   onChange={e => setMarmitexValue(e.target.value)}
                   onKeyDown={e => {
                     if (e.key === 'Enter') {
                       const val = parseFloat(marmitexValue);
                       if (val > 0) addItemToComanda(null, { price: val, desc: 'Marmitex', type: 'marmitex' });
                     }
                   }}
                 />
               </div>
             </ActionCard>

             {/* Adicionar por Código de Barras */}
             <ActionCard title="Adicionar por Código" icon={Barcode} color="text-blue-500" disabled={!caixa}>
               <Input 
                 ref={productBarcodeRef}
                 placeholder="Leia o código de barras do produto aqui..." 
                 className="h-10 border-slate-200 bg-white" 
                 value={productBarcodeValue}
                 onChange={e => setProductBarcodeValue(e.target.value)}
                 onKeyDown={handleScannerProduct}
               />
             </ActionCard>

             {/* Buscar por Nome */}
             <ActionCard title="Buscar por Nome" icon={Search} color="text-slate-500" disabled={!caixa}>
                <div className="relative w-full">
                  <Input 
                    placeholder="Digite o nome do produto..." 
                    className="h-10 border-slate-200 bg-white pr-10" 
                    value={searchProductName}
                    onChange={e => setSearchProductName(e.target.value)}
                  />
                  {searchProductName && (
                    <button 
                      onClick={() => setSearchProductName('')}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
             </ActionCard>
          </div>

          {/* Atalhos Rápidos */}
          <Card className="flex-1 border-slate-200 shadow-sm overflow-hidden flex flex-col">
            <CardHeader className="p-4 bg-slate-50/50 flex flex-row items-center justify-between border-b border-slate-100">
               <div className="flex items-center gap-2">
                 <div className={`p-1.5 rounded-lg shadow-sm ${searchProductName ? 'text-blue-600 bg-blue-50' : 'text-purple-600 bg-white'}`}>
                   {searchProductName ? <Search size={16} /> : <Coffee size={16} />}
                 </div>
                 <CardTitle className="text-xs font-black text-slate-700 uppercase tracking-widest">
                   {searchProductName ? `Resultados: "${searchProductName}"` : "Atalhos Rápidos"}
                 </CardTitle>
               </div>
               <Button 
                variant="ghost" size="sm" 
                className="h-8 px-2 text-[10px] font-black uppercase text-slate-400 hover:text-purple-600 hover:bg-purple-50 gap-1.5"
                onClick={() => setShowQuickAccessModal(true)}
               >
                 <Package size={14} />
                 Escolher Atalhos
               </Button>
            </CardHeader>
            <CardContent className={`p-4 flex-1 flex flex-col overflow-hidden ${!caixa && 'opacity-50 grayscale pointer-events-none'}`}>
               <ScrollArea className="h-full pr-4">
                  {searchProductName ? (
                    // MODO BUSCA
                    filteredProductsBySearch.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center py-10 opacity-30 border-2 border-dashed border-slate-100 rounded-3xl">
                        <Search size={48} className="mb-2" />
                        <p className="text-sm font-bold">Nenhum produto encontrado.</p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 lg:grid-cols-5 2xl:grid-cols-6 gap-2">
                         {filteredProductsBySearch.map(product => (
                           <Button 
                             key={product.id}
                             variant="outline"
                             className="h-auto p-2.5 flex flex-col items-start gap-0.5 rounded-xl border-slate-200 hover:border-blue-400 hover:bg-blue-50/50 transition-all group"
                             onClick={() => {
                               addItemToComanda(product);
                               setSearchProductName(''); // Limpa após selecionar
                             }}
                           >
                              <span className="text-[8px] font-bold text-slate-400 uppercase tracking-tighter truncate w-full">{product.category}</span>
                              <span className="font-bold text-slate-800 text-[11px] line-clamp-1 text-left w-full group-hover:text-blue-700">{product.name}</span>
                              <span className="font-black text-blue-600 text-xs">{formatCurrency(product.price)}</span>
                           </Button>
                         ))}
                      </div>
                    )
                  ) : (
                    // MODO ATALHOS
                    quickAccessProducts.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center py-10 opacity-30 border-2 border-dashed border-slate-100 rounded-3xl">
                        <Coffee size={48} className="mb-2" />
                        <p className="text-sm font-bold">Nenhum atalho configurado.</p>
                        <Button variant="link" onClick={() => setShowQuickAccessModal(true)}>Clique aqui para escolher</Button>
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 lg:grid-cols-5 2xl:grid-cols-6 gap-2">
                         {quickAccessProducts.map(product => (
                           <Button 
                             key={product.id}
                             variant="outline"
                             className="h-auto p-2.5 flex flex-col items-start gap-0.5 rounded-xl border-slate-200 hover:border-purple-400 hover:bg-purple-50/50 transition-all group"
                             onClick={() => addItemToComanda(product)}
                           >
                              <span className="text-[8px] font-bold text-slate-400 uppercase tracking-tighter truncate w-full">{product.category}</span>
                              <span className="font-bold text-slate-800 text-[11px] line-clamp-1 text-left w-full group-hover:text-purple-700">{product.name}</span>
                              <span className="font-black text-purple-600 text-xs">{formatCurrency(product.price)}</span>
                           </Button>
                         ))}
                      </div>
                    )
                  )}
               </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* ── RIGHT COLUMN: SUMMARY (40%) ── */}
        <div className="flex-[2] flex flex-col min-h-[600px] lg:min-h-0 lg:h-full bg-white rounded-3xl lg:rounded-[2.5rem] border border-slate-200 shadow-xl overflow-hidden shadow-slate-200/50">
           
           {(!selectedComanda && !isMultiMode) || (isMultiMode && selectedMultiComandas.length === 0) ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-12 opacity-40">
                 <div className="p-8 bg-slate-50 rounded-full mb-6 border border-slate-100">
                    <Receipt size={80} className="text-slate-400 stroke-1" />
                 </div>
                 <h2 className="text-2xl font-black text-slate-800 mb-2 font-mono">
                   {isMultiMode ? "Modo Múltiplas Comandas" : "Nenhuma Comanda Ativa"}
                 </h2>
                 <p className="text-sm text-slate-500 max-w-[280px]">
                   {isMultiMode 
                    ? "Leia o código das comandas que deseja agrupar no pagamento."
                    : "Leia o código de uma comanda ou digite o número no topo para começar a adicionar itens."}
                 </p>
              </div>
           ) : (
              <div className="flex-1 flex flex-col overflow-hidden">
                 {/* Summary Header */}
                 <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
                    <div>
                       <Badge className={`${isMultiMode ? 'bg-orange-600' : 'bg-blue-600'} text-white border-none font-black px-3 py-1 mb-1 shadow-md shadow-blue-100 uppercase tracking-widest text-[10px]`}>
                         {isMultiMode ? `Pagando ${selectedMultiComandas.length} Comandas` : "Comanda Selecionada"}
                       </Badge>
                       <h3 className="text-3xl font-black text-slate-800 tracking-tighter">
                         {isMultiMode 
                          ? `${selectedMultiComandas.length} selecionadas` 
                          : selectedComanda?.identificador}
                       </h3>
                    </div>
                    <div className="text-right">
                       <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Total Geral</p>
                       <p className={`text-2xl font-black ${isMultiMode ? 'text-orange-600' : 'text-blue-600'}`}>{formatCurrency(grandTotal)}</p>
                    </div>
                 </div>

                 {/* Items List */}
                 <ScrollArea className="flex-1 px-8 py-6">
                    {isMultiMode ? (
                      <div className="space-y-6">
                        {selectedMultiComandas.map((cmd, idx) => (
                           <div key={cmd.id} className={`p-5 rounded-3xl border-2 transition-all ${idx === 0 ? 'border-emerald-200 bg-emerald-50/30 ring-2 ring-emerald-100' : 'border-slate-100 bg-slate-50/50'}`}>
                             <div className="flex justify-between items-center mb-3">
                               <div className="flex items-center gap-2">
                                 <h4 className="font-black text-slate-800">#{cmd.identificador}</h4>
                                 {idx === 0 && <Badge className="bg-emerald-600 text-[8px] h-4">PRIMÁRIA (RECEBE ITENS)</Badge>}
                               </div>
                               <div className="flex items-center gap-3">
                                 <span className="font-bold text-sm text-slate-600">{formatCurrency(cmd.total)}</span>
                                 <Button 
                                    size="icon" variant="ghost" className="h-7 w-7 rounded-full text-rose-400 hover:text-rose-600 hover:bg-rose-50"
                                    onClick={() => setMultiSelectedIds(prev => prev.filter(id => id !== cmd.id))}
                                  >
                                    <X size={14} />
                                  </Button>
                               </div>
                             </div>
                             <div className="space-y-1 opacity-70">
                                {cmd.items.slice(0, 3).map(it => (
                                  <p key={it.id} className="text-[10px] font-bold text-slate-500">• {it.quantity}x {it.description}</p>
                                ))}
                                {cmd.items.length > 3 && <p className="text-[10px] font-bold text-slate-400 italic font-mono">+ {cmd.items.length - 3} itens</p>}
                             </div>
                           </div>
                        ))}
                        <Button 
                          variant="ghost" className="w-full border-2 border-dashed border-slate-200 text-slate-400 font-bold rounded-2xl h-12"
                          onClick={() => {setMultiSelectedIds([]); setIsMultiMode(false);}}
                        >
                          Cancelar e Limpar Seleção
                        </Button>
                      </div>
                    ) : (
                      selectedComanda && (
                        <div className="space-y-4">
                           {selectedComanda.items.map(item => (
                               <div key={item.id} className="flex items-center justify-between group p-3 rounded-2xl hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-100">
                                  <div className="flex-1 min-w-0 pr-2">
                                     <p className="font-bold text-slate-800 truncate text-sm">{item.description}</p>
                                     <p className="text-[10px] font-bold text-slate-400">{formatCurrency(item.unit_price)}</p>
                                  </div>

                                  <div className="flex items-center gap-3">
                                     {/* MULTIPLICADOR INTEGRADO */}
                                     <div className="flex items-center gap-1 bg-white border border-slate-100 p-0.5 rounded-lg shadow-sm">
                                        <Button 
                                          variant="ghost" size="icon" className="h-6 w-6 rounded-md hover:bg-slate-50 text-slate-400"
                                          onClick={() => updateItemQuantity(item.id, Math.max(0.1, item.quantity - 1))}
                                        >
                                          <Minus size={12} />
                                        </Button>
                                        <Input 
                                          type="number" 
                                          className="w-10 h-6 text-center font-black bg-transparent border-none p-0 focus-visible:ring-0 shadow-none text-[11px]" 
                                          value={item.quantity} 
                                          onChange={e => updateItemQuantity(item.id, parseFloat(e.target.value) || 1)}
                                        />
                                        <Button 
                                          variant="ghost" size="icon" className="h-6 w-6 rounded-md hover:bg-slate-50 text-slate-400"
                                          onClick={() => updateItemQuantity(item.id, item.quantity + 1)}
                                        >
                                          <Plus size={12} />
                                        </Button>
                                     </div>

                                     <div className="text-right min-w-[70px]">
                                        <p className="font-black text-slate-900 text-sm whitespace-nowrap">{formatCurrency(item.unit_price * item.quantity)}</p>
                                     </div>
                                     
                                     <Button 
                                       size="icon" 
                                       variant="ghost" 
                                       className="h-8 w-8 rounded-full text-slate-200 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
                                       onClick={() => removeItemFromComanda(item.id)}
                                     >
                                       <X size={16} />
                                     </Button>
                                  </div>
                               </div>
                            ))}
                        </div>
                      )
                    )}
                 </ScrollArea>

                 {/* Summary Footer */}
                 <div className="p-8 pt-6 border-t border-slate-100 space-y-6">
                    <div className="flex items-center justify-between">
                       <p className="text-sm font-black text-slate-400 uppercase tracking-widest">Total do Pedido</p>
                       <p className={`text-4xl font-black ${isMultiMode ? 'text-orange-600' : 'text-slate-900'} tracking-tighter`}>{formatCurrency(grandTotal)}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                       <Button 
                          variant="outline" 
                          className="h-14 rounded-2xl border-slate-200 font-black text-slate-400 hover:bg-red-50 hover:text-red-600 transition-all uppercase tracking-tighter text-xs"
                          onClick={() => {
                            if (isMultiMode) setMultiSelectedIds([]);
                            else setSelectedComanda(null);
                          }}
                       >
                          {isMultiMode ? "Limpar Seleção" : "Trocar Comanda"}
                       </Button>
                       <Button 
                          className={`h-14 rounded-2xl ${isMultiMode ? 'bg-orange-600 hover:bg-orange-700 shadow-orange-100' : 'bg-blue-600 hover:bg-blue-700 shadow-blue-200'} font-black shadow-xl transition-all uppercase tracking-tighter text-xs`}
                          disabled={isMultiMode ? selectedMultiComandas.length === 0 : !selectedComanda || selectedComanda.items.length === 0}
                          onClick={() => setShowPaymentModal(true)}
                       >
                          {isMultiMode ? `Pagar ${selectedMultiComandas.length} Comandas` : "Finalizar Venda"}
                       </Button>
                    </div>
                 </div>
              </div>
           )}
        </div>
      </div>

      {/* ── MODALS (CAIXA / PAYMENT) ── */}
      {/* (Mantendo o código dos outros modais para integridade funcional) */}
      
      {/* MODAL CAIXA REFORMULADO */}
      <Dialog open={showCaixaModal} onOpenChange={setShowCaixaModal}>
        <DialogContent className="max-w-4xl bg-white rounded-[2rem] p-0 border-none shadow-2xl overflow-hidden h-[85vh] flex flex-col">
          <DialogHeader className="p-8 border-b border-slate-100 bg-white sticky top-0 z-10">
            <DialogTitle className="text-2xl font-black text-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Wallet className="text-blue-600" size={28} />
                Gestão de Caixa
              </div>
              {caixa && (
                <Badge className="bg-emerald-100 text-emerald-700 border-none font-black px-4 py-1 rounded-full text-xs">
                  ABERTO EM {new Date(caixa.opened_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                </Badge>
              )}
            </DialogTitle>
          </DialogHeader>

          <ScrollArea className="flex-1">
            <div className="p-8 space-y-8">
              {!caixa ? (
                <div className="py-12 text-center space-y-6">
                  <div className="p-8 bg-blue-50 text-blue-600 rounded-[2.5rem] inline-flex mb-2">
                    <Wallet size={64} />
                  </div>
                  <div className="space-y-2">
                    <h4 className="text-2xl font-black text-slate-800 tracking-tighter">Caixa Fechado</h4>
                    <p className="text-slate-400 font-bold text-sm">Informe o valor em dinheiro para iniciar o turno</p>
                  </div>
                  <div className="relative max-w-[280px] mx-auto">
                    <span className="absolute left-6 top-1/2 -translate-y-1/2 font-black text-2xl text-slate-300">R$</span>
                    <Input 
                      type="number" 
                      className="pl-16 h-20 bg-slate-50 border-none rounded-3xl text-3xl font-black text-slate-800 focus-visible:ring-blue-500 shadow-inner" 
                      value={openingBalance} 
                      onChange={e => setOpeningBalance(e.target.value)} 
                    />
                  </div>
                  <Button className="w-full max-w-[280px] h-16 bg-blue-600 hover:bg-blue-700 rounded-3xl font-black text-lg shadow-xl shadow-blue-200 transition-all" onClick={handleOpenCaixa}>
                    ABRIR TURNO
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  {/* Lado Esquerdo: Resumo Financeiro */}
                  <div className="space-y-6">
                    <Card className="p-6 border-none bg-slate-50 rounded-3xl space-y-4">
                      <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <ChartLine size={14} /> Saldo de Dinheiro (Em Mãos)
                      </h4>
                      <div className="space-y-3">
                         <div className="flex justify-between text-sm font-bold text-slate-600">
                           <span>Abertura:</span>
                           <span>{formatCurrency(caixaSummary?.opening_balance || 0)}</span>
                         </div>
                         <div className="flex justify-between text-sm font-bold text-emerald-600">
                           <span>Vendas (Dinheiro):</span>
                           <span>+ {formatCurrency(caixaSummary?.vendas_dinheiro || 0)}</span>
                         </div>
                         <div className="flex justify-between text-sm font-bold text-emerald-600">
                           <span>Suprimentos:</span>
                           <span>+ {formatCurrency(caixaSummary?.entradas_total || 0)}</span>
                         </div>
                         <div className="flex justify-between text-sm font-bold text-rose-500">
                           <span>Sangrias/Retiradas:</span>
                           <span>- {formatCurrency(caixaSummary?.retiradas_total || 0)}</span>
                         </div>
                         <div className="pt-3 border-t border-slate-200 flex justify-between items-end">
                           <span className="text-sm font-black text-slate-900">SALDO EM DINHEIRO:</span>
                           <span className="text-2xl font-black text-slate-900">{formatCurrency(caixaSummary?.saldo_dinheiro || 0)}</span>
                         </div>
                      </div>
                    </Card>

                    <Card className="p-6 border-none bg-blue-50/50 rounded-3xl space-y-4">
                      <h4 className="text-xs font-black text-blue-400 uppercase tracking-widest">
                        Outros Recebimentos (Não Dinheiro)
                      </h4>
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs font-bold text-slate-600">
                           <span>PIX:</span>
                           <span>{formatCurrency(caixaSummary?.vendas_pix || 0)}</span>
                        </div>
                        <div className="flex justify-between text-xs font-bold text-slate-600">
                           <span>Cartão Débito:</span>
                           <span>{formatCurrency(caixaSummary?.vendas_debito || 0)}</span>
                        </div>
                        <div className="flex justify-between text-xs font-bold text-slate-600">
                           <span>Cartão Crédito:</span>
                           <span>{formatCurrency(caixaSummary?.vendas_credito || 0)}</span>
                        </div>
                        <div className="pt-2 border-t border-blue-100 flex justify-between text-sm font-black text-blue-700">
                           <span>TOTAL GERAL (BRUTO):</span>
                           <span>{formatCurrency(caixaSummary?.saldo_geral || 0)}</span>
                        </div>
                      </div>
                    </Card>
                    
                    <div className="p-6 border-2 border-dashed border-slate-100 rounded-3xl space-y-4">
                      <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest">Fechar Turno</h4>
                      <Input 
                        type="number" 
                        placeholder="Valor Final em Dinheiro R$" 
                        className="h-12 bg-slate-50 border-none rounded-2xl text-center font-black" 
                        value={closingBalance} 
                        onChange={e => setClosingBalance(e.target.value)} 
                      />
                      <Button variant="destructive" className="w-full h-12 rounded-2xl font-black shadow-lg shadow-red-100" onClick={handleCloseCaixa}>
                        ENCERRAR CAIXA
                      </Button>
                    </div>
                  </div>

                  {/* Lado Direito: Movimentações e Histórico */}
                  <div className="space-y-6">
                    <Tabs defaultValue="movimentar" className="w-full">
                      <TabsList className="w-full bg-slate-100 p-1 rounded-2xl mb-4">
                        <TabsTrigger value="movimentar" className="flex-1 rounded-xl font-black text-xs">LANÇAMENTOS</TabsTrigger>
                        <TabsTrigger value="historico" className="flex-1 rounded-xl font-black text-xs">HISTÓRICO</TabsTrigger>
                      </TabsList>
                      
                      <TabsContent value="movimentar" className="space-y-4">
                        <Card className="p-6 border-slate-100 rounded-3xl space-y-4">
                          <h4 className="text-sm font-black text-slate-800">Nova Movimentação</h4>
                          <div className="space-y-3">
                            <Input 
                              type="number" 
                              placeholder="Valor R$" 
                              className="h-12 bg-slate-50 border-none rounded-2xl font-bold"
                              value={movimentacaoAmount}
                              onChange={e => setMovimentacaoAmount(e.target.value)}
                            />
                            <Textarea 
                              placeholder="Descrição (ex: Troco, Sangria p/ Depósito)" 
                              className="bg-slate-50 border-none rounded-2xl font-bold resize-none"
                              value={movimentacaoDesc}
                              onChange={e => setMovimentacaoDesc(e.target.value)}
                            />
                            <div className="grid grid-cols-2 gap-3">
                              <Button 
                                className="bg-emerald-600 hover:bg-emerald-700 rounded-2xl font-black text-xs h-12"
                                onClick={() => handleMovimentacao('suprimento')}
                              >
                                SUPRIMENTO (+)
                              </Button>
                              <Button 
                                variant="destructive" 
                                className="rounded-2xl font-black text-xs h-12"
                                onClick={() => handleMovimentacao('sangria')}
                              >
                                SANGRIA (-)
                              </Button>
                            </div>
                          </div>
                        </Card>
                      </TabsContent>

                      <TabsContent value="historico">
                        <ScrollArea className="h-[400px]">
                          <div className="space-y-2 pr-4">
                            {caixaSummary?.movements?.length === 0 && (
                              <p className="text-center py-12 text-xs font-bold text-slate-300 italic">Nenhuma movimentação ainda.</p>
                            )}
                            {[...(caixaSummary?.movements || [])].reverse().map((mov: any) => (
                              <div key={mov.id} className="p-4 bg-white border border-slate-100 rounded-2xl flex justify-between items-center group hover:border-blue-200 transition-all">
                                <div className="flex items-center gap-3">
                                  <div className={`p-2 rounded-xl ${
                                    mov.type === 'suprimento' ? 'bg-emerald-50 text-emerald-600' : 
                                    mov.type === 'venda' ? 'bg-blue-50 text-blue-600' :
                                    'bg-rose-50 text-rose-500'
                                  }`}>
                                    {mov.type === 'venda' ? <Tag size={16} /> : <Banknote size={16} />}
                                  </div>
                                  <div>
                                    <p className="text-xs font-black text-slate-700 uppercase tracking-tighter">{mov.description || mov.type}</p>
                                    <p className="text-[10px] font-bold text-slate-400">{new Date(mov.created_at).toLocaleTimeString()}</p>
                                  </div>
                                </div>
                                <p className={`text-sm font-black ${
                                  mov.type === 'suprimento' || mov.type === 'venda' ? 'text-emerald-600' : 'text-rose-500'
                                }`}>
                                  {mov.type === 'suprimento' || mov.type === 'venda' ? '+' : '-'} {formatCurrency(mov.amount)}
                                </p>
                              </div>
                            ))}
                          </div>
                        </ScrollArea>
                      </TabsContent>
                    </Tabs>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>

      {/* MODAL PAGAMENTO */}
      <Dialog open={showPaymentModal} onOpenChange={setShowPaymentModal}>
        <DialogContent className="max-w-3xl p-0 bg-slate-50 rounded-[3rem] border-none shadow-2xl overflow-hidden">
           <div className="grid grid-cols-1 md:grid-cols-5 h-full min-h-[500px]">
              <div className="md:col-span-2 bg-white p-10 border-r border-slate-100 flex flex-col justify-between">
                 <div>
                    <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4">Total a Pagar</h4>
                    <p className="text-4xl font-black text-blue-600 mb-1">
                      {formatCurrency(Math.max(0, (selectedComanda?.total || grandTotal) - discountAmount))}
                    </p>
                    {discountAmount > 0 && (
                      <p className="text-xs font-bold text-slate-400 line-through mb-2">Original: {formatCurrency(selectedComanda?.total || grandTotal)}</p>
                    )}
                    <Badge className="bg-blue-50 text-blue-600 border-none font-black px-4 py-1.5 rounded-lg">Comanda #{selectedComanda?.identificador || 'Lote'}</Badge>
                    
                    <div className="mt-8 space-y-2">
                       <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Desconto (R$)</h4>
                       <div className="relative">
                          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-300 font-bold">R$</span>
                          <Input 
                            type="number" 
                            className="pl-10 h-10 bg-slate-50 border-none rounded-xl font-black text-slate-700" 
                            placeholder="0,00"
                            value={discountAmount || ''}
                            onChange={e => setDiscountAmount(parseFloat(e.target.value) || 0)}
                          />
                       </div>
                    </div>
                 </div>
                 <div className="space-y-4 pt-10 border-t border-slate-100">
                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Resumo Rápido</p>
                    <div className="space-y-2 opacity-60">
                       {isMultiMode ? (
                         selectedMultiComandas.map(c => (
                           <p key={c.id} className="text-xs font-bold text-slate-700 truncate">• {c.identificador} ({formatCurrency(c.total)})</p>
                         ))
                       ) : (
                         selectedComanda?.items.slice(0, 5).map(item => (
                           <p key={item.id} className="text-xs font-bold text-slate-700 truncate">• {item.quantity}x {item.description}</p>
                         ))
                       )}
                    </div>
                 </div>
              </div>
              <div className="md:col-span-3 p-10 flex flex-col h-full bg-slate-50">
                 <h3 className="text-xl font-black text-slate-800 mb-8 font-mono tracking-tighter uppercase">Escolha o Destino</h3>
                 <Tabs defaultValue="direct" className="w-full flex-1 flex flex-col">
                    <TabsList className="bg-white p-1.5 rounded-2xl mb-8 shadow-sm">
                       <TabsTrigger value="direct" className="flex-1 rounded-xl font-black data-[state=active]:bg-blue-600 data-[state=active]:text-white">Pagamento Direto</TabsTrigger>
                       <TabsTrigger value="room" className="flex-1 rounded-xl font-black data-[state=active]:bg-indigo-600 data-[state=active]:text-white">Lançar no Quarto</TabsTrigger>
                    </TabsList>
                    <TabsContent value="direct" className="mt-0 flex-1">
                       <div className="grid grid-cols-2 gap-4">
                          {[{id:'pix',label:'PIX',icon:QrCode},{id:'credito',label:'Crédito',icon:CreditCard},{id:'debito',label:'Débito',icon:CreditCard},{id:'dinheiro',label:'Dinheiro',icon:Banknote}].map(pay => (
                            <Button key={pay.id} variant="outline" className="h-24 flex-col gap-3 rounded-[2rem] border-white bg-white hover:border-blue-400 hover:bg-blue-50 shadow-sm font-black text-slate-700" onClick={() => finalizeSale(pay.id)}>
                              <pay.icon size={28} className="text-blue-600" />{pay.label}
                            </Button>
                          ))}
                       </div>
                    </TabsContent>
                    <TabsContent value="room" className="mt-0 flex-1">
                       <ScrollArea className="h-[280px]">
                          <div className="space-y-3 pr-4">
                             {activeReservations.length === 0 ? <p className="text-center text-xs opacity-50 py-10 italic">Nenhum hóspede ativo.</p> : activeReservations.map(res => (
                               <Button key={res.id} variant="outline" className="w-full h-16 justify-between rounded-2xl border-white bg-white hover:bg-indigo-50 shadow-sm" onClick={() => finalizeSale(undefined, res.id)}>
                                 <div className="flex flex-col items-start"><span className="font-black text-indigo-600 text-[10px] uppercase">Quarto {res.room_number}</span><span className="font-bold text-slate-800">{res.guest_name}</span></div>
                                 <ChevronRight size={18} className="text-slate-200" />
                               </Button>
                             ))}
                          </div>
                       </ScrollArea>
                    </TabsContent>
                 </Tabs>
              </div>
           </div>
        </DialogContent>
      </Dialog>

      {/* MODAL CONFIGURAR ATALHOS */}
      <Dialog open={showQuickAccessModal} onOpenChange={setShowQuickAccessModal}>
        <DialogContent className="max-w-2xl bg-white rounded-[2rem] p-8 border-none shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
          <DialogHeader>
            <DialogTitle className="text-2xl font-black text-slate-800 flex items-center gap-3">
              <div className="p-2 bg-purple-100 text-purple-600 rounded-xl"><Package size={24} /></div>
              Escolher Atalhos Rápidos
            </DialogTitle>
            <p className="text-slate-400 font-bold text-sm">Selecione os produtos que aparecerão na grade principal do PDV (Favoritos).</p>
          </DialogHeader>

          <div className="my-6 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <Input 
              placeholder="Pesquisar produtos..." 
              className="pl-10 h-12 bg-slate-50 border-none rounded-2xl font-bold"
              value={searchProductName}
              onChange={e => setSearchProductName(e.target.value)}
            />
          </div>

          <ScrollArea className="flex-1 pr-4">
            <div className="grid grid-cols-1 gap-2">
              {[...products].sort((a,b) => a.name.localeCompare(b.name)).filter(p => !searchProductName || p.name.toLowerCase().includes(searchProductName.toLowerCase())).map(product => {
                const isSelected = tempSelectedIds.includes(product.id);
                return (
                  <div 
                    key={product.id}
                    className={`flex items-center justify-between p-4 rounded-2xl border-2 cursor-pointer transition-all ${isSelected ? 'border-purple-500 bg-purple-50' : 'border-slate-100 bg-slate-50 hover:border-slate-200'}`}
                    onClick={() => {
                      if (isSelected) {
                        setTempSelectedIds(prev => prev.filter(id => id !== product.id));
                      } else {
                        setTempSelectedIds(prev => [...prev, product.id]);
                      }
                    }}
                  >
                    <div className="flex items-center gap-4">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-black ${isSelected ? 'bg-purple-600 text-white' : 'bg-white text-slate-300'}`}>
                        {isSelected ? <Minus size={20} /> : <Plus size={20} />}
                      </div>
                      <div>
                        <p className="font-bold text-slate-800 uppercase text-[10px] tracking-widest">{product.category}</p>
                        <p className="font-black text-slate-700">{product.name}</p>
                      </div>
                    </div>
                    <p className="font-black text-slate-900">{formatCurrency(product.price)}</p>
                  </div>
                );
              })}
            </div>
          </ScrollArea>

          <DialogFooter className="mt-8">
            <Button 
               disabled={isUpdatingQuickAccess}
               className="w-full h-14 bg-slate-900 hover:bg-slate-800 text-white font-black rounded-2xl shadow-xl shadow-slate-200" 
               onClick={() => handleUpdateQuickAccess(tempSelectedIds)}
            >
              {isUpdatingQuickAccess ? "SALVANDO..." : (
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={20} />
                  SALVAR E CONCLUÍR ({tempSelectedIds.length})
                </div>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
