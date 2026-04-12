import React, { useEffect, useState, useRef } from 'react';
import api from '../services/api';
import type { AxiosError } from 'axios';

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
  total_value: number;
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
export default function Inventory() {
  const role = localStorage.getItem('role');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [dashboard, setDashboard] = useState<StockDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [editing, setEditing] = useState<Product | null>(null);
  const [editForm, setEditForm] = useState({
    name: '',
    price: '',
    category: '',
    stock_quantity: '',
    min_stock: '',
    barcode: '',
    cost_price: '',
    markup_percent: '',
  });
  const [uploadSummary, setUploadSummary] = useState<StockEntry | null>(null);
  const [entries, setEntries] = useState<StockEntry[]>([]);
  const [entryFilters, setEntryFilters] = useState({
    supplier: '',
    invoice_number: '',
    start: '',
    end: '',
  });
  const [receiptMeta, setReceiptMeta] = useState({
    supplier: '',
    invoice_number: '',
    invoice_date: '',
    note: '',
  });

  const [form, setForm] = useState({
    name: '',
    price: '',
    category: '',
    stock_quantity: '',
    min_stock: '5',
    barcode: '',
    cost_price: '',
    markup_percent: '',
  });

  const [searchTerm, setSearchTerm] = useState('');

  async function load() {
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
  }

  useEffect(() => {
    const t = setTimeout(() => {
      load();
    }, 0);
    return () => clearTimeout(t);
  }, []);
  useEffect(() => {
    loadEntries();
  }, []);
  useEffect(() => {
    const t = setTimeout(() => {
      loadEntries();
    }, 200);
    return () => clearTimeout(t);
  }, [entryFilters.supplier, entryFilters.invoice_number, entryFilters.start, entryFilters.end]);
  
  // Cálculo automático de preço de venda (Criação)
  useEffect(() => {
    const cost = parseFloat(form.cost_price) || 0;
    const markup = parseFloat(form.markup_percent) || 0;
    if (cost > 0 || markup > 0) {
      const calculated = cost * (1 + markup / 100);
      setForm(f => ({ ...f, price: calculated.toFixed(2) }));
    }
  }, [form.cost_price, form.markup_percent]);

  // Cálculo automático de preço de venda (Edição)
  useEffect(() => {
    const cost = parseFloat(editForm.cost_price) || 0;
    const markup = parseFloat(editForm.markup_percent) || 0;
    if (cost > 0 || markup > 0) {
      const calculated = cost * (1 + markup / 100);
      setEditForm(f => ({ ...f, price: calculated.toFixed(2) }));
    }
  }, [editForm.cost_price, editForm.markup_percent]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setError(null);
    try {
      const payload = {
        name: form.name,
        price: parseFloat(form.price),
        category: form.category,
        stock_quantity: parseInt(form.stock_quantity) || 0,
        min_stock: parseInt(form.min_stock) || 5,
        cost_price: parseFloat(form.cost_price) || 0.0,
        markup_percent: parseFloat(form.markup_percent) || 0.0,
        is_active: true,
        is_quick_access: false,
      };
      await api.post('/products/', payload);
      setMessage('Produto criado');
      setForm({ name: '', price: '', category: '', stock_quantity: '', min_stock: '5', barcode: '', cost_price: '', markup_percent: '' });
      await load();
    } catch (err) {
      const axErr = err as AxiosError<{ detail?: string }>;
      const msg = axErr.response?.data?.detail ?? 'Erro ao criar produto';
      setError(msg);
    }
  }
  
  async function deleteEntry(id: number) {
    if (!window.confirm('Tem certeza que deseja excluir esta entrada? O estoque será revertido.')) return;
    try {
      await api.delete(`/products/stock/entries/${id}`);
      setMessage('Entrada excluída e estoque revertido');
      await load();
      await loadEntries();
    } catch {
      setError('Falha ao excluir entrada');
    }
  }

  async function loadEntries() {
    try {
      const params: any = {};
      if (entryFilters.supplier) params.supplier = entryFilters.supplier;
      if (entryFilters.invoice_number) params.invoice_number = entryFilters.invoice_number;
      if (entryFilters.start) params.start = entryFilters.start;
      if (entryFilters.end) params.end = entryFilters.end;
      const res = await api.get('/products/stock/entries', { params });
      setEntries(res.data);
    } catch {
      // silencioso
    }
  }
  function formatMoney(v: number) {
    return `R$ ${Number(v ?? 0).toFixed(2)}`;
  }
  function stockStatus(p: Product) {
    const q = p.stock_quantity ?? 0;
    const min = p.min_stock ?? 0;
    const max = p.max_stock ?? null;
    if (q <= min) return { label: `Baixo (${q})`, className: 'bg-red-600 text-white' };
    if (max != null && q >= max) return { label: `Bom (${q})`, className: 'bg-green-600 text-white' };
    return { label: `Normal (${q})`, className: 'bg-slate-300 text-slate-800' };
  }
  async function archiveProduct(p: Product) {
    try {
      await api.put(`/products/${p.id}`, { is_active: false });
      await load();
      setMessage('Produto arquivado');
    } catch {
      setError('Falha ao arquivar produto');
    }
  }
  
  function openEdit(p: Product) {
    setEditing(p);
    setEditForm({
      name: p.name,
      price: String(p.price),
      category: p.category,
      stock_quantity: String(p.stock_quantity),
      min_stock: String(p.min_stock),
      barcode: p.barcode || '',
      cost_price: String(p.cost_price || 0),
      markup_percent: String(p.markup_percent || 0),
    });
  }
  async function submitEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setError(null);
    setMessage(null);
    try {
      const payload: any = {};
      if (editForm.name) payload.name = editForm.name;
      if (editForm.price) payload.price = parseFloat(editForm.price);
      if (editForm.category) payload.category = editForm.category;
      if (editForm.stock_quantity) payload.stock_quantity = parseInt(editForm.stock_quantity);
      if (editForm.min_stock) payload.min_stock = parseInt(editForm.min_stock);
      if (editForm.cost_price) payload.cost_price = parseFloat(editForm.cost_price);
      if (editForm.markup_percent) payload.markup_percent = parseFloat(editForm.markup_percent);
      payload.barcode = editForm.barcode || null;
      await api.put(`/products/${editing.id}`, payload);
      setEditing(null);
      await load();
      setMessage('Produto atualizado');
    } catch (err) {
      const axErr = err as AxiosError<{ detail?: string }>;
      const msg = axErr.response?.data?.detail ?? 'Erro ao atualizar produto';
      setError(msg);
    }
  }
  async function handleInvoiceUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setMessage(null);
    setUploadSummary(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const params: any = {};
      if (receiptMeta.supplier) params.supplier = receiptMeta.supplier;
      if (receiptMeta.invoice_number) params.invoice_number = receiptMeta.invoice_number;
      if (receiptMeta.invoice_date) params.invoice_date = receiptMeta.invoice_date;
      if (receiptMeta.note) params.note = receiptMeta.note;
      const endpoint = file.type.includes('image') || file.name.toLowerCase().endsWith('.pdf') ? '/products/stock/ocr' : '/products/stock/receipt';
      const res = await api.post(endpoint, fd, { params, headers: { 'Content-Type': 'multipart/form-data' } });
      setUploadSummary(res.data as StockEntry);
      await load();
      await loadEntries();
      setMessage('Estoque atualizado pela nota fiscal');
    } catch {
      setError('Falha ao processar nota fiscal');
    } finally {
      e.target.value = '';
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Estoque</h2>
        <p className="text-slate-500">KPIs e cadastro rápido de produtos.</p>
      </div>

      {error && <div className="bg-red-50 text-red-700 rounded-lg border border-red-200 p-4">{error}</div>}
      {message && <div className="bg-green-50 text-green-700 rounded-lg border border-green-200 p-4">{message}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <p className="text-sm text-slate-500">Produtos ativos</p>
          <p className="text-3xl font-bold text-slate-800">{dashboard?.total_products ?? 0}</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <p className="text-sm text-slate-500">Valor total em estoque</p>
          <p className="text-3xl font-bold text-slate-800">
            R$ {(dashboard?.total_value ?? 0).toFixed(2)}
          </p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <p className="text-sm text-slate-500">Itens com estoque baixo</p>
          <p className="text-3xl font-bold text-slate-800">{dashboard?.low_stock_count ?? 0}</p>
        </div>
      </div>

      {dashboard?.low_stock_items?.length ? (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-lg p-4">
          <p className="font-semibold mb-2">Atenção: estoque baixo</p>
          <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {dashboard.low_stock_items.map((p) => (
              <li key={p.id} className="bg-white border border-yellow-200 rounded-lg p-3 flex justify-between">
                <span>{p.name} — {p.category}</span>
                <span className="font-medium">Qtd: {p.stock_quantity}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <p className="text-lg font-semibold text-slate-800 mb-4">Buscar Produtos</p>
        <div className="relative">
          <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400">
            🔍
          </span>
          <input
            type="text"
            placeholder="Pesquisar por nome ou código de barras..."
            className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <p className="text-lg font-semibold text-slate-800 mb-4">Cadastro de Produto</p>
        <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Nome</label>
            <input
              placeholder="Ex: Coca-Cola 350ml"
              className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Código de Barras</label>
            <input
              placeholder="Escaneie ou digite"
              className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
              value={form.barcode}
              onChange={(e) => setForm((f) => ({ ...f, barcode: e.target.value }))}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Categoria</label>
            <input
              placeholder="Ex: Bebidas"
              className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
              value={form.category}
              onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Custo (R$)</label>
            <input
              type="number"
              step="0.01"
              placeholder="0.00"
              className="w-full border rounded-lg px-3 py-2 bg-slate-50 focus:ring-2 focus:ring-blue-500 outline-none"
              value={form.cost_price}
              onChange={(e) => setForm((f) => ({ ...f, cost_price: e.target.value }))}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Margem (%)</label>
            <input
              type="number"
              placeholder="0"
              className="w-full border rounded-lg px-3 py-2 bg-slate-50 focus:ring-2 focus:ring-blue-500 outline-none"
              value={form.markup_percent}
              onChange={(e) => setForm((f) => ({ ...f, markup_percent: e.target.value }))}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Preço de Venda</label>
            <input
              type="number"
              step="0.01"
              placeholder="0.00"
              className="w-full border border-blue-200 bg-blue-50 font-bold rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
              value={form.price}
              onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Qtd em Estoque</label>
            <input
              type="number"
              placeholder="0"
              className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
              value={form.stock_quantity}
              onChange={(e) => setForm((f) => ({ ...f, stock_quantity: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Estoque Mínimo</label>
            <input
              type="number"
              placeholder="5"
              className="w-full border rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
              value={form.min_stock}
              onChange={(e) => setForm((f) => ({ ...f, min_stock: e.target.value }))}
            />
          </div>
          <div className="lg:col-span-3 flex justify-end">
            <button
              type="submit"
              className="bg-blue-600 text-white px-8 py-2 rounded-lg shadow-md hover:bg-blue-700 transition font-semibold"
            >
              Criar Produto
            </button>
          </div>
        </form>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-lg font-semibold text-slate-800">Produtos</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg shadow hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
            >
              <span>Upload Nota Fiscal</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.pdf,image/*,.xml"
              onChange={handleInvoiceUpload}
              className="hidden"
            />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <input placeholder="Fornecedor" className="border rounded-lg px-3 py-2 text-sm" value={receiptMeta.supplier} onChange={(e) => setReceiptMeta((m) => ({ ...m, supplier: e.target.value }))} />
          <input placeholder="NF" className="border rounded-lg px-3 py-2 text-sm" value={receiptMeta.invoice_number} onChange={(e) => setReceiptMeta((m) => ({ ...m, invoice_number: e.target.value }))} />
          <input type="date" className="border rounded-lg px-3 py-2 text-sm" value={receiptMeta.invoice_date} onChange={(e) => setReceiptMeta((m) => ({ ...m, invoice_date: e.target.value }))} />
          <input placeholder="Observação" className="border rounded-lg px-3 py-2 text-sm w-60" value={receiptMeta.note} onChange={(e) => setReceiptMeta((m) => ({ ...m, note: e.target.value }))} />
        </div>
        {uploadSummary && (
          <div className="mb-4 bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm text-slate-700">
            <p className="font-semibold">Entrada registrada #{uploadSummary.id}</p>
            <p>Fornecedor: {uploadSummary.supplier || '—'} • NF: {uploadSummary.invoice_number || '—'} • Data: {uploadSummary.invoice_date || '—'}</p>
            <p>Itens: {uploadSummary.items?.length ?? 0}</p>
          </div>
        )}
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">Produto</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">Categoria</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">Custo/Venda</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">Markup</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">Estoque</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">Código</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {products
                .filter(p => 
                  p.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                  (p.barcode && p.barcode.includes(searchTerm))
                )
                .map((p) => {
                const st = stockStatus(p);
                return (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="px-4 py-4">
                      <div className="font-semibold text-slate-800">{p.name}</div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-slate-700">{p.category}</div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-xs text-slate-500">Custo: {formatMoney(p.cost_price || 0)}</div>
                      <div className="text-sm font-bold text-slate-800">Venda: {formatMoney(p.price)}</div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-slate-700">{p.markup_percent || 0}%</div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-slate-800">{p.stock_quantity} {p.unit_measure || 'unidade'}</div>
                      <div className="text-xs text-slate-500">Min: {p.min_stock} {p.max_stock != null ? `| Max: ${p.max_stock}` : ''}</div>
                    </td>
                    <td className="px-4 py-4">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${st.className}`}>{st.label}</span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-slate-800">{p.barcode || '—'}</div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <button className="p-2 rounded-lg border bg-white hover:bg-slate-50" onClick={() => openEdit(p)} title="Editar">✏️</button>
                        {role === 'admin' && (
                          <button className="p-2 rounded-lg border bg-white hover:bg-red-50 text-red-600" onClick={() => archiveProduct(p)} title="Arquivar">🗑️</button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {products.length === 0 && (
                <tr>
                  <td className="px-4 py-6 text-slate-500" colSpan={7}>Nenhum produto encontrado</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      
      {editing && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setEditing(null)}>
          <div className="bg-white rounded-2xl w-full max-w-lg p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <div>
                <p className="text-sm text-slate-500">Produto #{editing.id}</p>
                <h3 className="text-xl font-bold text-slate-800">{editing.name}</h3>
              </div>
              <button onClick={() => setEditing(null)} className="px-3 py-2 rounded-lg border bg-white">Fechar</button>
            </div>
            <form onSubmit={submitEdit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Nome</label>
                <input className="w-full border rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500" placeholder="Nome" value={editForm.name} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Código de Barras</label>
                <input className="w-full border rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500" placeholder="Código de barras" value={editForm.barcode} onChange={(e) => setEditForm((f) => ({ ...f, barcode: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Categoria</label>
                <input className="w-full border rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500" placeholder="Categoria" value={editForm.category} onChange={(e) => setEditForm((f) => ({ ...f, category: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Custo (R$)</label>
                <input className="w-full border rounded-lg px-3 py-2 outline-none bg-slate-50 focus:ring-2 focus:ring-blue-500" type="number" step="0.01" value={editForm.cost_price} onChange={(e) => setEditForm((f) => ({ ...f, cost_price: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Margem (%)</label>
                <input className="w-full border rounded-lg px-3 py-2 outline-none bg-slate-50 focus:ring-2 focus:ring-blue-500" type="number" value={editForm.markup_percent} onChange={(e) => setEditForm((f) => ({ ...f, markup_percent: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Preço de Venda</label>
                <input className="w-full border border-blue-200 bg-blue-50 font-bold rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500" type="number" step="0.01" value={editForm.price} onChange={(e) => setEditForm((f) => ({ ...f, price: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Quantidade</label>
                <input className="w-full border rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500" type="number" placeholder="Quantidade" value={editForm.stock_quantity} onChange={(e) => setEditForm((f) => ({ ...f, stock_quantity: e.target.value }))} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Estoque Mínimo</label>
                <input className="w-full border rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500" type="number" placeholder="Estoque mínimo" value={editForm.min_stock} onChange={(e) => setEditForm((f) => ({ ...f, min_stock: e.target.value }))} />
              </div>
              
              <div className="flex gap-2 col-span-1 sm:col-span-2 mt-4 pt-4 border-t border-slate-100">
                <button type="submit" className="flex-1 bg-blue-600 text-white px-5 py-2.5 rounded-lg shadow-md hover:bg-blue-700 transition font-semibold">Salvar alterações</button>
                <button type="button" onClick={() => setEditing(null)} className="flex-1 border px-5 py-2.5 rounded-lg bg-white hover:bg-slate-50 font-semibold text-slate-700">Cancelar</button>
              </div>
            </form>
          </div>
        </div>
      )}
      
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <p className="text-lg font-semibold text-slate-800">Entradas de Estoque</p>
          <div className="flex gap-2">
            <input placeholder="Fornecedor" className="border rounded-lg px-2 py-1 text-sm" value={entryFilters.supplier} onChange={(e) => setEntryFilters((f) => ({ ...f, supplier: e.target.value }))} />
            <input placeholder="NF" className="border rounded-lg px-2 py-1 text-sm" value={entryFilters.invoice_number} onChange={(e) => setEntryFilters((f) => ({ ...f, invoice_number: e.target.value }))} />
            <input type="date" className="border rounded-lg px-2 py-1 text-sm" value={entryFilters.start} onChange={(e) => setEntryFilters((f) => ({ ...f, start: e.target.value }))} />
            <input type="date" className="border rounded-lg px-2 py-1 text-sm" value={entryFilters.end} onChange={(e) => setEntryFilters((f) => ({ ...f, end: e.target.value }))} />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3">
          {entries.map((en) => (
            <div key={en.id} className="border rounded-xl p-3 flex justify-between items-start group">
              <div>
                <div className="flex justify-between">
                  <p className="font-semibold text-slate-800">#{en.id} • {en.supplier || '—'} • NF {en.invoice_number || '—'}</p>
                </div>
                <p className="text-sm text-slate-600">{new Date(en.created_at).toLocaleString('pt-BR')}</p>
                <p className="text-sm text-slate-600">Data NF: {en.invoice_date || '—'} • Itens: {en.items?.length ?? 0}</p>
              </div>
              {role === 'admin' && (
                <button 
                  onClick={() => deleteEntry(en.id)}
                  className="opacity-0 group-hover:opacity-100 p-2 text-red-600 hover:bg-red-50 rounded-lg transition"
                  title="Excluir entrada"
                >
                  🗑️
                </button>
              )}
            </div>
          ))}
          {entries.length === 0 && <div className="text-slate-500">Sem entradas encontradas para os filtros.</div>}
        </div>
      </div>
    </div>
  );
}
