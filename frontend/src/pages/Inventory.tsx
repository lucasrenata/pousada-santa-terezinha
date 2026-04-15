import React, { useEffect, useState, useRef, useCallback } from 'react';
import api from '../services/api';
import type { AxiosError } from 'axios';
import { 
  Package, Plus, Search, FileText, BarChart3, ArrowUpDown, 
  Edit, Trash2, Archive, Upload, Download, AlertTriangle,
  ChevronRight, Filter, ShoppingCart, TrendingUp, DollarSign
} from 'lucide-react';

interface Product {
  id: number;
  name: string;
  price: number;
  category: string;
  stock_quantity: number;
  min_stock: number;
  is_active: boolean;
  unit_measure?: string;
  max_stock?: number | null;
  barcode?: string | null;
  cost_price?: number;
  markup_percent?: number;
}

interface StockDashboard {
  total_products: number;
  total_value: number; // Venda
  total_cost_value: number; // Custo
  potential_profit: number; // Lucro
  low_stock_count: number;
  low_stock_items: Product[];
}

interface StockEntryItem {
  id: number;
  product_id: number;
  quantity: number;
  unit_price?: number | null;
}

interface StockEntry {
  id: number;
  supplier?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  note?: string | null;
  created_at: string;
  items: StockEntryItem[];
}

interface Category {
  id: number;
  name: string;
}

type Tab = 'geral' | 'produtos' | 'relatorios';
const TABS: { id: Tab; label: string }[] = [
  { id: 'geral',     label: '📊 Visão Geral' },
  { id: 'produtos',  label: '📦 Produtos' },
  { id: 'relatorios', label: '📄 Relatórios' },
];

export default function Inventory() {
  const role = localStorage.getItem('role');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeTab, setActiveTab] = useState<Tab>('geral');
  const [products, setProducts] = useState<Product[]>([]);
  const [dashboard, setDashboard] = useState<StockDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [editing, setEditing] = useState<Product | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  const [editForm, setEditForm] = useState({
    name: '', price: '', category: '', stock_quantity: '', min_stock: '', barcode: '', cost_price: '', markup_percent: '',
  });
  const [form, setForm] = useState({
    name: '', price: '', category: '', stock_quantity: '', min_stock: '5', barcode: '', cost_price: '', markup_percent: '',
  });

  const [uploadSummary, setUploadSummary] = useState<StockEntry | null>(null);
  const [entries, setEntries] = useState<StockEntry[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [isAddingCategory, setIsAddingCategory] = useState(false);
  const [newCatName, setNewCatName] = useState('');
  
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [sortOrder, setSortOrder] = useState<'name' | 'stock_asc' | 'stock_desc'>('name');

  const fmtCurrency = (v: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [listRes, dashRes] = await Promise.all([
        api.get('/products/', { params: { only_active: true } }),
        api.get('/products/dashboard'),
      ]);
      setProducts(listRes.data);
      setDashboard(dashRes.data);
    } catch {
      setError('Falha ao carregar estoque');
    }
  }, []);

  const loadEntries = useCallback(async () => {
    try {
      const res = await api.get('/products/stock/entries');
      setEntries(res.data);
    } catch { /* erro silencioso */ }
  }, []);

  const loadCategories = useCallback(async () => {
    try {
      const res = await api.get('/products/categories');
      setCategories(res.data);
    } catch { /* erro silencioso */ }
  }, []);

  useEffect(() => { load(); loadEntries(); loadCategories(); }, [load, loadEntries, loadCategories]);

  // Cálculo de preço sugerido
  useEffect(() => {
    const cost = parseFloat(form.cost_price) || 0;
    const markup = parseFloat(form.markup_percent) || 0;
    if (cost > 0 || markup > 0) {
      setForm(f => ({ ...f, price: (cost * (1 + markup / 100)).toFixed(2) }));
    }
  }, [form.cost_price, form.markup_percent]);

  useEffect(() => {
    const cost = parseFloat(editForm.cost_price) || 0;
    const markup = parseFloat(editForm.markup_percent) || 0;
    if (cost > 0 || markup > 0) {
      setEditForm(f => ({ ...f, price: (cost * (1 + markup / 100)).toFixed(2) }));
    }
  }, [editForm.cost_price, editForm.markup_percent]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault(); setMessage(null); setError(null);
    
    // Validação básica
    if (!form.price || isNaN(parseFloat(form.price))) return setError('Preço de venda é obrigatório e deve ser numérico');
    if (!form.category) return setError('Selecione uma categoria');

    try {
      await api.post('/products/', {
        ...form,
        price: parseFloat(form.price),
        stock_quantity: parseInt(form.stock_quantity) || 0,
        min_stock: parseInt(form.min_stock) || 5,
        cost_price: parseFloat(form.cost_price) || 0,
        markup_percent: parseFloat(form.markup_percent) || 0,
      });
      setMessage('Produto cadastrado com sucesso!');
      setForm({ name: '', price: '', category: '', stock_quantity: '', min_stock: '5', barcode: '', cost_price: '', markup_percent: '' });
      setIsModalOpen(false); await load();
    } catch (err: any) { setError(err.response?.data?.detail ?? 'Erro ao cadastrar'); }
  }

  async function submitEdit(e: React.FormEvent) {
    e.preventDefault(); if (!editing) return;
    
    if (!editForm.price || isNaN(parseFloat(editForm.price))) return setError('Preço de venda deve ser numérico');

    try {
      await api.put(`/products/${editing.id}`, {
        ...editForm,
        price: parseFloat(editForm.price),
        stock_quantity: parseInt(editForm.stock_quantity) || 0,
        min_stock: parseInt(editForm.min_stock) || 0,
        cost_price: parseFloat(editForm.cost_price) || 0,
        markup_percent: parseFloat(editForm.markup_percent) || 0,
      });
      setEditing(null); setMessage('Produto atualizado!'); await load();
      setIsModalOpen(false);
    } catch (err: any) { setError(err.response?.data?.detail ?? 'Erro ao atualizar'); }
  }

  async function handleAddCategory() {
    if (!newCatName.trim()) return;
    try {
      const res = await api.post('/products/categories', { name: newCatName.trim() });
      setCategories(prev => [...prev.filter(c => c.name !== res.data.name), res.data]);
      if (editing) setEditForm(f => ({ ...f, category: res.data.name }));
      else setForm(f => ({ ...f, category: res.data.name }));
      setNewCatName(''); setIsAddingCategory(false);
    } catch { setError('Erro ao adicionar categoria'); }
  }

  async function archiveProduct(id: number) {
    if (!confirm('Deseja arquivar este produto?')) return;
    try { await api.put(`/products/${id}`, { is_active: false }); await load(); setMessage('Produto arquivado'); }
    catch { setError('Erro ao arquivar'); }
  }

  async function handleInvoiceUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const fd = new FormData(); fd.append('file', file);
      const endpoint = file.type.includes('image') || file.name.toLowerCase().endsWith('.pdf') ? '/products/stock/ocr' : '/products/stock/receipt';
      const res = await api.post(endpoint, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setUploadSummary(res.data); await load(); await loadEntries(); setMessage('Estoque atualizado!');
    } catch { setError('Erro ao processar arquivo'); } finally { e.target.value = ''; }
  }

  const downloadReport = async (type: 'inventory' | 'shopping') => {
    try {
      const endpoint = type === 'inventory' ? '/products/reports/inventory' : '/products/reports/shopping-list';
      const response = await api.get(endpoint, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', type === 'inventory' ? 'inventario.pdf' : 'lista_compras.pdf');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch { setError('Erro ao gerar relatório'); }
  };

  const filteredProducts = products.filter(p => {
    const matchesSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase()) || (p.barcode?.includes(searchTerm));
    const matchesCat = !filterCategory || p.category === filterCategory;
    return matchesSearch && matchesCat;
  }).sort((a,b) => {
    if (sortOrder === 'stock_asc') return a.stock_quantity - b.stock_quantity;
    if (sortOrder === 'stock_desc') return b.stock_quantity - a.stock_quantity;
    return a.name.localeCompare(b.name);
  });

  const productCategories = Array.from(new Set([...categories.map(c => c.name), ...products.map(p => p.category)]));

  const btnPrimary = 'bg-blue-600 text-white px-5 py-2.5 rounded-xl shadow-lg shadow-blue-100 hover:bg-blue-700 transition font-bold text-sm flex items-center gap-2';
  const inputCls = 'border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white w-full transition-all';

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-slate-50/50 -m-8">
      
      {/* ── Sidebar ── */}
      <aside className="w-full md:w-64 bg-white border-r border-slate-200 p-6 flex flex-col gap-6">
        <div>
          <h2 className="text-2xl font-black text-slate-800 tracking-tight flex items-center gap-2">
            <Package className="text-blue-600" />
            ParcerIA
          </h2>
          <p className="text-[10px] uppercase font-bold text-slate-400 tracking-widest mt-1 ml-8">Gestão de Estoque</p>
        </div>

        <nav className="space-y-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${
                activeTab === tab.id 
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-100' 
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
              }`}
            >
              <span className="text-lg">{tab.label.split(' ')[0]}</span>
              {tab.label.split(' ').slice(1).join(' ')}
            </button>
          ))}
        </nav>

        <div className="mt-auto pt-6 border-t border-slate-100">
          <div className="bg-slate-50 rounded-2xl p-4">
            <p className="text-[10px] font-bold text-slate-400 uppercase mb-2">Saúde do Estoque</p>
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-slate-500">Alertas</span>
                <span className="font-bold text-red-500">{dashboard?.low_stock_count ?? 0}</span>
              </div>
              <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-red-500 transition-all duration-500" 
                  style={{ width: `${Math.min(((dashboard?.low_stock_count ?? 0) / (dashboard?.total_products || 1)) * 100, 100)}%` }} 
                />
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="flex-1 p-4 md:p-8 space-y-8 max-w-6xl mx-auto w-full">
        {error && <div className="bg-red-50 text-red-700 rounded-xl border border-red-200 p-4 text-sm flex items-center gap-3"><AlertTriangle size={18}/>{error}</div>}
        {message && <div className="bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-200 p-4 text-sm flex items-center gap-3"><Package size={18}/>{message}</div>}

        {/* ══ ABA: VISÃO GERAL ══ */}
        {activeTab === 'geral' && (
          <div className="space-y-8 animate-in fade-in duration-500">
            <div className="flex justify-between items-end">
              <div>
                <h3 className="text-2xl font-bold text-slate-800">Visão Geral</h3>
                <p className="text-slate-500 text-sm">Resumo da saúde financeira e física do estoque.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-4 mb-4">
                  <div className="p-3 bg-blue-50 text-blue-600 rounded-2xl"><Package size={24}/></div>
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Produtos Ativos</p>
                </div>
                <p className="text-4xl font-black text-slate-800">{dashboard?.total_products ?? 0}</p>
              </div>
              <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-4 mb-4">
                  <div className="p-3 bg-amber-50 text-amber-600 rounded-2xl"><DollarSign size={24}/></div>
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Valor em Estoque (Custo)</p>
                </div>
                <p className="text-4xl font-black text-slate-800">{fmtCurrency(dashboard?.total_cost_value ?? 0)}</p>
              </div>
              <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-4 mb-4">
                  <div className="p-3 bg-emerald-50 text-emerald-600 rounded-2xl"><TrendingUp size={24}/></div>
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Lucro Estimado</p>
                </div>
                <p className="text-4xl font-black text-slate-800 font-mono">{fmtCurrency(dashboard?.potential_profit ?? 0)}</p>
              </div>
            </div>

            <div className="bg-white rounded-3xl border border-slate-200 overflow-hidden shadow-sm">
              <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex items-center gap-2 text-red-600 font-bold">
                <AlertTriangle size={20}/> Alerta de Reposição (Abaixo do Mínimo)
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50/50 text-slate-500 text-xs uppercase tracking-wider">
                    <tr>
                      <th className="px-6 py-4 text-left font-bold">Produto</th>
                      <th className="px-6 py-4 text-left font-bold">Categoria</th>
                      <th className="px-6 py-4 text-right font-bold">Estoque Atual</th>
                      <th className="px-6 py-4 text-right font-bold">Estoque Mínimo</th>
                      <th className="px-6 py-4 text-center font-bold">Déficit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {dashboard?.low_stock_items?.map(p => (
                      <tr key={p.id} className="hover:bg-red-50/30 transition-colors">
                        <td className="px-6 py-4 font-bold text-slate-800">{p.name}</td>
                        <td className="px-6 py-4 text-slate-500">{p.category}</td>
                        <td className="px-6 py-4 text-right font-black text-red-600">{p.stock_quantity}</td>
                        <td className="px-6 py-4 text-right font-semibold text-slate-500">{p.min_stock}</td>
                        <td className="px-6 py-4 text-center">
                          <span className="bg-red-100 text-red-700 px-3 py-1 rounded-full text-[10px] font-black uppercase">
                            - {(p.min_stock - p.stock_quantity)} {p.unit_measure || 'un'}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {!dashboard?.low_stock_items?.length && (
                      <tr><td colSpan={5} className="px-6 py-12 text-center text-slate-400 italic">Tudo em ordem! Nenhum produto abaixo do limite.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ══ ABA: PRODUTOS ══ */}
        {activeTab === 'produtos' && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
              <div>
                <h3 className="text-2xl font-bold text-slate-800">Gestão de Produtos</h3>
                <p className="text-slate-500 text-sm">Cadastre, edite e acompanhe seu inventário detalhadamente.</p>
              </div>
              <div className="flex gap-2">
                <button 
                  onClick={() => fileInputRef.current?.click()}
                  className="bg-indigo-600 text-white px-5 py-2.5 rounded-xl shadow-lg shadow-indigo-100 hover:bg-indigo-700 transition font-bold text-sm flex items-center gap-2"
                >
                  <Upload size={18}/> Importar XML
                </button>
                <input ref={fileInputRef} type="file" accept=".xml,.csv,.xlsx,.pdf,image/*" onChange={handleInvoiceUpload} className="hidden" />
                <button onClick={() => { setIsModalOpen(true); setEditing(null); }} className={btnPrimary}>
                  <Plus size={18}/> Novo Produto
                </button>
              </div>
            </div>

            <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm flex flex-wrap gap-4 items-end">
              <div className="flex-1 min-w-[250px]">
                <label className="block text-xs font-bold text-slate-400 uppercase mb-2">Buscar Produto</label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18}/>
                  <input 
                    className={inputCls + " pl-10"} 
                    placeholder="Nome ou código de barras..." 
                    value={searchTerm} 
                    onChange={e => setSearchTerm(e.target.value)} 
                  />
                </div>
              </div>
              <div className="w-full md:w-48">
                <label className="block text-xs font-bold text-slate-400 uppercase mb-2">Categoria</label>
                <select className={inputCls} value={filterCategory} onChange={e => setFilterCategory(e.target.value)}>
                  <option value="">Todas</option>
                  {productCategories.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="w-full md:w-48">
                <label className="block text-xs font-bold text-slate-400 uppercase mb-2">Ordenação</label>
                <select className={inputCls} value={sortOrder} onChange={e => setSortOrder(e.target.value as any)}>
                  <option value="name">Nome (A-Z)</option>
                  <option value="stock_asc">Menor Estoque</option>
                  <option value="stock_desc">Maior Estoque</option>
                </select>
              </div>
            </div>

            <div className="bg-white rounded-3xl border border-slate-200 overflow-hidden shadow-sm">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-100">
                  <tr>
                    <th className="px-6 py-4 text-left font-bold">Produto</th>
                    <th className="px-6 py-4 text-left font-bold">Preços (Custo/Venda)</th>
                    <th className="px-6 py-4 text-center font-bold">Estoque</th>
                    <th className="px-6 py-4 text-left font-bold">Fornecedor</th>
                    <th className="px-6 py-4 text-right"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredProducts.map(p => {
                    const isLow = p.stock_quantity <= p.min_stock;
                    return (
                      <tr key={p.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-6 py-4">
                          <p className="font-bold text-slate-800">{p.name}</p>
                          <p className="text-[10px] text-slate-400 font-mono tracking-tighter">{p.barcode || 'SEM BARRAS'}</p>
                        </td>
                        <td className="px-6 py-4">
                          <p className="text-xs text-slate-500">Custo: {fmtCurrency(p.cost_price || 0)}</p>
                          <p className="text-sm font-black text-blue-600">Venda: {fmtCurrency(p.price)}</p>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <div className={`inline-flex flex-col items-center px-3 py-1.5 rounded-2xl ${isLow ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}`}>
                            <span className="text-sm font-black">{p.stock_quantity}</span>
                            <span className="text-[10px] font-bold uppercase tracking-tight">{p.unit_measure || 'un'}</span>
                          </div>
                          <p className="text-[10px] text-slate-400 mt-1 uppercase font-bold">Mín: {p.min_stock}</p>
                        </td>
                        <td className="px-6 py-4 text-slate-500 text-xs italic">{p.supplier || '-'}</td>
                        <td className="px-6 py-4">
                          <div className="flex justify-end gap-1">
                            <button onClick={() => { setEditing(p); setEditForm({
                              name: p.name, price: String(p.price), category: p.category, stock_quantity: String(p.stock_quantity), 
                              min_stock: String(p.min_stock), barcode: p.barcode || '', cost_price: String(p.cost_price || 0), 
                              markup_percent: String(p.markup_percent || 0),
                            }); setIsModalOpen(true); }} className="p-2 rounded-xl hover:bg-blue-50 text-slate-400 hover:text-blue-600 transition-colors">
                              <Edit size={16}/>
                            </button>
                            {role === 'admin' && (
                              <button onClick={() => archiveProduct(p.id)} className="p-2 rounded-xl hover:bg-red-50 text-slate-400 hover:text-red-500 transition-colors">
                                <Archive size={16}/>
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ══ ABA: RELATÓRIOS ══ */}
        {activeTab === 'relatorios' && (
          <div className="space-y-8 animate-in fade-in duration-500">
            <div>
              <h3 className="text-2xl font-bold text-slate-800">Centro de Relatórios</h3>
              <p className="text-slate-500 text-sm">Gere documentos PDF customizados para sua gestão.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white rounded-3xl border border-slate-200 p-8 shadow-sm hover:border-blue-300 transition-colors group">
                <div className="p-4 bg-blue-50 text-blue-600 rounded-3xl w-fit mb-6 transition-transform group-hover:scale-110"><FileText size={32}/></div>
                <h4 className="text-xl font-bold text-slate-800 mb-2">Inventário Geral</h4>
                <p className="text-slate-500 text-sm mb-6">Lista completa de todos os ativos em estoque com valoração baseada em preço de custo.</p>
                <button onClick={() => downloadReport('inventory')} className={btnPrimary + ' w-full'}>
                  <Download size={18}/> Gerar Inventário em PDF
                </button>
              </div>

              <div className="bg-white rounded-3xl border border-slate-200 p-8 shadow-sm hover:border-amber-300 transition-colors group">
                <div className="p-4 bg-amber-50 text-amber-600 rounded-3xl w-fit mb-6 transition-transform group-hover:scale-110"><ShoppingCart size={32}/></div>
                <h4 className="text-xl font-bold text-slate-800 mb-2">Lista de Compras Inteligente</h4>
                <p className="text-slate-500 text-sm mb-6">Reúne itens abaixo do mínimo e produtos de alto giro que estão se aproximando do limite.</p>
                <button onClick={() => downloadReport('shopping')} className="bg-amber-600 text-white px-5 py-2.5 rounded-xl shadow-lg shadow-amber-100 hover:bg-amber-700 transition font-bold text-sm flex items-center gap-2 w-full">
                  <Download size={18}/> Gerar Lista de Compras
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Modal Novo/Editar ── */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-[2rem] w-full max-w-2xl shadow-2xl overflow-hidden border border-slate-200 animate-in zoom-in-95 duration-200">
            <div className="p-8 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <h3 className="text-xl font-black text-slate-800 flex items-center gap-3">
                <Plus className="text-blue-600" size={24} />
                {editing ? `Editar Produto #${editing.id}` : 'Nova Ficha de Produto'}
              </h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600 p-2 hover:bg-slate-100 rounded-full transition-colors">
                <Plus size={24} className="rotate-45" />
              </button>
            </div>
            <form onSubmit={editing ? submitEdit : handleCreate} className="p-8 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="md:col-span-2">
                  <label className="block text-xs font-bold text-slate-400 uppercase mb-2 tracking-widest">Identificação do Produto</label>
                  <input required className={inputCls + ' text-lg'} placeholder="Ex: Cerveja Budweiser 350ml" 
                    value={editing ? editForm.name : form.name} 
                    onChange={e => editing ? setEditForm({...editForm, name: e.target.value}) : setForm({...form, name: e.target.value})} 
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase mb-2 tracking-widest">Código de Barras</label>
                  <input className={inputCls} placeholder="EAN / GTIN" 
                    value={editing ? editForm.barcode : form.barcode} 
                    onChange={e => editing ? setEditForm({...editForm, barcode: e.target.value}) : setForm({...form, barcode: e.target.value})} 
                  />
                </div>
                <div className="relative">
                  <label className="block text-xs font-bold text-slate-400 uppercase mb-2 tracking-widest">Categoria</label>
                  {!isAddingCategory ? (
                    <div className="flex gap-2">
                      <select required className={inputCls} 
                        value={editing ? editForm.category : form.category} 
                        onChange={e => {
                          const val = e.target.value;
                          if (val === 'NEW') setIsAddingCategory(true);
                          else editing ? setEditForm({...editForm, category: val}) : setForm({...form, category: val});
                        }}
                      >
                        <option value="">Selecione...</option>
                        {productCategories.map(c => <option key={c} value={c}>{c}</option>)}
                        <option value="NEW" className="font-bold text-blue-600">+ Adicionar Nova...</option>
                      </select>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <input autoFocus className={inputCls} placeholder="Nome da categoria..." 
                        value={newCatName} onChange={e => setNewCatName(e.target.value)} 
                        onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), handleAddCategory())}
                      />
                      <button type="button" onClick={handleAddCategory} className="bg-blue-600 text-white px-3 rounded-xl hover:bg-blue-700 transition">
                        <Plus size={20}/>
                      </button>
                      <button type="button" onClick={() => setIsAddingCategory(false)} className="bg-slate-100 text-slate-400 px-3 rounded-xl hover:bg-slate-200 transition">
                        <Plus size={20} className="rotate-45" />
                      </button>
                    </div>
                  )}
                </div>
                
                <div className="md:col-span-2 p-6 bg-slate-50 rounded-3xl border border-slate-200 grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-[10px] font-black text-slate-400 uppercase mb-1">Preço Custo</label>
                    <input type="number" step="0.01" className={inputCls} placeholder="0,00" 
                      value={editing ? editForm.cost_price : form.cost_price} 
                      onChange={e => editing ? setEditForm({...editForm, cost_price: e.target.value}) : setForm({...form, cost_price: e.target.value})} 
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black text-slate-400 uppercase mb-1">Markup (%)</label>
                    <input type="number" className={inputCls} placeholder="0 %" 
                      value={editing ? editForm.markup_percent : form.markup_percent} 
                      onChange={e => editing ? setEditForm({...editForm, markup_percent: e.target.value}) : setForm({...form, markup_percent: e.target.value})} 
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-black text-blue-500 uppercase mb-1">Preço Venda</label>
                    <input required type="number" step="0.01" className={inputCls + ' border-blue-200 font-bold text-blue-600'} 
                      value={editing ? editForm.price : form.price} 
                      onChange={e => editing ? setEditForm({...editForm, price: e.target.value}) : setForm({...form, price: e.target.value})} 
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase mb-2 tracking-widest">Estoq. Atual</label>
                  <input required type="number" className={inputCls} 
                    value={editing ? editForm.stock_quantity : form.stock_quantity} 
                    onChange={e => editing ? setEditForm({...editForm, stock_quantity: e.target.value}) : setForm({...form, stock_quantity: e.target.value})} 
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase mb-2 tracking-widest">Estoq. Mínimo</label>
                  <input required type="number" className={inputCls + ' border-amber-200'} 
                    value={editing ? editForm.min_stock : form.min_stock} 
                    onChange={e => editing ? setEditForm({...editForm, min_stock: e.target.value}) : setForm({...form, min_stock: e.target.value})} 
                  />
                </div>
              </div>

              <div className="flex gap-4 pt-4">
                <button type="button" onClick={() => setIsModalOpen(false)} className="flex-1 py-4 text-slate-500 font-bold hover:bg-slate-50 rounded-2xl transition-all">
                  Descartar
                </button>
                <button type="submit" className="flex-2 py-4 bg-blue-600 text-white font-black rounded-2xl hover:bg-blue-700 transition-all shadow-xl shadow-blue-100">
                  {editing ? 'Atualizar Produto' : 'Concluir Cadastro'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
