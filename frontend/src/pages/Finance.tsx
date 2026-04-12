import React, { useEffect, useState } from 'react';
import api from '../services/api';

type RevenueCategory = 'hospedagem' | 'consumo' | 'outros';
type PaymentMethod = 'pix' | 'credito' | 'debito' | 'dinheiro';

interface Revenue {
  id: number;
  description: string;
  amount: number;
  category: RevenueCategory;
  payment_method: PaymentMethod;
  created_at: string;
  booking_id?: number | null;
}

export default function Finance() {
  const [start, setStart] = useState<string>('');
  const [end, setEnd] = useState<string>('');
  const [summary, setSummary] = useState<{ total_revenue: number; transactions: number } | null>(null);
  const [revenues, setRevenues] = useState<Revenue[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<RevenueCategory | ''>('');
  const [filterPayment, setFilterPayment] = useState<PaymentMethod | ''>('');
  const [search, setSearch] = useState<string>('');
  const [byCategory, setByCategory] = useState<Record<string, number>>({});
  const [byPayment, setByPayment] = useState<Record<string, number>>({});
  const [editing, setEditing] = useState<Revenue | null>(null);
  const [editForm, setEditForm] = useState({
    description: '',
    amount: '',
    category: '' as RevenueCategory | '',
    payment_method: '' as PaymentMethod | '',
    booking_id: '',
  });

  const [form, setForm] = useState({
    description: '',
    amount: '',
    category: 'hospedagem' as RevenueCategory,
    payment_method: 'pix' as PaymentMethod,
    booking_id: '',
  });
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [pages, setPages] = useState<number>(0);
  const [sortBy, setSortBy] = useState<'created_at' | 'amount' | 'description' | 'category' | 'payment_method'>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const palette = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16'];
  
  function headerSort(field: 'created_at' | 'amount' | 'description' | 'category' | 'payment_method') {
    if (sortBy === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortDir('desc');
    }
    setPage(1);
    setTimeout(loadReport, 0);
  }
  function sortArrow(field: typeof sortBy) {
    if (sortBy !== field) return '';
    return sortDir === 'asc' ? '↑' : '↓';
  }
  function getPageNumbers(total: number, current: number) {
    const nums: (number | string)[] = [];
    if (total <= 7) {
      for (let i = 1; i <= total; i++) nums.push(i);
      return nums;
    }
    nums.push(1);
    if (current > 3) nums.push('...');
    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    for (let i = start; i <= end; i++) nums.push(i);
    if (current < total - 2) nums.push('...');
    nums.push(total);
    return nums;
  }
  
  function PieChart({ data }: { data: Record<string, number> }) {
    const entries = Object.entries(data);
    const total = entries.reduce((acc, [, v]) => acc + v, 0);
    const size = 140;
    const r = 55;
    const c = 2 * Math.PI * r;
    let acc = 0;
    return (
      <div className="flex items-center gap-4">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
            <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth={20} />
            {entries.map(([k, v], i) => {
              const dash = total ? (v / total) * c : 0;
              const el = (
                <circle
                  key={k}
                  cx={size / 2}
                  cy={size / 2}
                  r={r}
                  fill="none"
                  stroke={palette[i % palette.length]}
                  strokeWidth={20}
                  strokeDasharray={`${dash} ${c - dash}`}
                  strokeDashoffset={c - acc}
                />
              );
              acc += dash;
              return el;
            })}
          </g>
          <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fontSize="14" fill="#0f172a">
            {`R$ ${(total ?? 0).toFixed(2)}`}
          </text>
        </svg>
        <div className="space-y-1">
          {entries.map(([k, v], i) => (
            <div key={k} className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: palette[i % palette.length] }} />
              <span className="text-slate-700">{k}</span>
              <span className="ml-auto font-semibold">R$ {v.toFixed(2)}</span>
            </div>
          ))}
          {entries.length === 0 && <p className="text-slate-500">Sem dados</p>}
        </div>
      </div>
    );
  }
  
  function BarChart({ data }: { data: Record<string, number> }) {
    const entries = Object.entries(data);
    const max = entries.reduce((acc, [, v]) => Math.max(acc, v), 0) || 1;
    return (
      <div className="space-y-2">
        {entries.map(([k, v], i) => (
          <div key={k}>
            <div className="flex justify-between text-sm text-slate-600">
              <span>{k}</span>
              <span className="font-semibold text-slate-800">R$ {v.toFixed(2)}</span>
            </div>
            <div className="h-3 bg-slate-200 rounded">
              <div
                className="h-3 rounded"
                style={{ width: `${(v / max) * 100}%`, backgroundColor: palette[i % palette.length] }}
              />
            </div>
          </div>
        ))}
        {entries.length === 0 && <p className="text-slate-500">Sem dados</p>}
      </div>
    );
  }

  function toDateString(date: string) {
    if (!date) return undefined;
    const d = new Date(date);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  async function loadReport() {
    try {
      setError(null);
      const params: Record<string, string> = {};
      const s = toDateString(start);
      const e = toDateString(end);
      if (s) params.start = s;
      if (e) params.end = e;
      if (filterCategory) params.category = filterCategory;
      if (filterPayment) params.payment_method = filterPayment;
      const q = search.trim();
      if (q) params.search = q;
      params.page = String(page);
      params.page_size = String(pageSize);
      params.sort_by = sortBy;
      params.sort_dir = sortDir;
      const res = await api.get('/finance/report', { params });
      setSummary({ total_revenue: res.data.total_revenue, transactions: res.data.transactions });
      setRevenues(res.data.data);
      setByCategory(res.data.by_category ?? {});
      setByPayment(res.data.by_payment_method ?? {});
      setPages(res.data.pages ?? 0);
    } catch {
      setError('Falha ao carregar relatório financeiro');
    }
  }

  useEffect(() => {
    const t = setTimeout(() => {
      loadReport();
    }, 0);
    return () => clearTimeout(t);
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setError(null);
    try {
      const payload = {
        description: form.description,
        amount: parseFloat(form.amount),
        category: form.category,
        payment_method: form.payment_method,
        booking_id: form.booking_id ? parseInt(form.booking_id) : null,
      };
      await api.post('/finance/', payload);
      setMessage('Receita lançada');
      setForm({ description: '', amount: '', category: 'hospedagem', payment_method: 'pix', booking_id: '' });
      await loadReport();
    } catch {
      setError('Erro ao lançar receita');
    }
  }
  


  function startEdit(r: Revenue) {
    setEditing(r);
    setEditForm({
      description: r.description,
      amount: String(r.amount),
      category: r.category,
      payment_method: r.payment_method,
      booking_id: r.booking_id ? String(r.booking_id) : '',
    });
  }

  async function submitEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    try {
      const payload: any = {};
      if (editForm.description) payload.description = editForm.description;
      if (editForm.amount) payload.amount = parseFloat(editForm.amount);
      if (editForm.category) payload.category = editForm.category;
      if (editForm.payment_method) payload.payment_method = editForm.payment_method;
      if (editForm.booking_id) payload.booking_id = parseInt(editForm.booking_id);
      await api.put(`/finance/${editing.id}`, payload);
      setEditing(null);
      await loadReport();
      setMessage('Receita atualizada');
    } catch {
      setError('Erro ao atualizar receita');
    }
  }

  async function deleteRevenue(id: number) {
    try {
      await api.delete(`/finance/${id}`);
      await loadReport();
      setMessage('Receita excluída');
    } catch {
      setError('Erro ao excluir receita');
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-800">Financeiro</h2>
        <p className="text-slate-500">Relatório simples e lançamento de receitas.</p>
      </div>

      {error && <div className="bg-red-50 text-red-700 rounded-lg border border-red-200 p-4">{error}</div>}
      {message && <div className="bg-green-50 text-green-700 rounded-lg border border-green-200 p-4">{message}</div>}

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <p className="text-lg font-semibold text-slate-800 mb-4">Filtro</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-8 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Início</label>
            <input type="date" className="border rounded-lg px-3 py-2 w-full" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Fim</label>
            <input type="date" className="border rounded-lg px-3 py-2 w-full" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Categoria</label>
            <select className="border rounded-lg px-3 py-2 w-full" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value as RevenueCategory | '')}>
              <option value="">Todas</option>
              <option value="hospedagem">Hospedagem</option>
              <option value="consumo">Consumo</option>
              <option value="outros">Outros</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Forma</label>
            <select className="border rounded-lg px-3 py-2 w-full" value={filterPayment} onChange={(e) => setFilterPayment(e.target.value as PaymentMethod | '')}>
              <option value="">Todas</option>
              <option value="pix">PIX</option>
              <option value="credito">Crédito</option>
              <option value="debito">Débito</option>
              <option value="dinheiro">Dinheiro</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Buscar</label>
            <input className="border rounded-lg px-3 py-2 w-full" placeholder="Descrição..." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Ordenar por</label>
            <select className="border rounded-lg px-3 py-2 w-full" value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)}>
              <option value="created_at">Data</option>
              <option value="amount">Valor</option>
              <option value="description">Descrição</option>
              <option value="category">Categoria</option>
              <option value="payment_method">Forma</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Direção</label>
            <select className="border rounded-lg px-3 py-2 w-full" value={sortDir} onChange={(e) => setSortDir(e.target.value as typeof sortDir)}>
              <option value="desc">Desc</option>
              <option value="asc">Asc</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">Itens por página</label>
            <select className="border rounded-lg px-3 py-2 w-full" value={pageSize} onChange={(e) => setPageSize(parseInt(e.target.value))}>
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={loadReport} className="bg-slate-800 text-white px-4 py-2 rounded-lg hover:bg-slate-900 w-full h-10">Aplicar</button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <p className="text-sm text-slate-500">Receita total</p>
          <p className="text-3xl font-bold text-slate-800">R$ {(summary?.total_revenue ?? 0).toFixed(2)}</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <p className="text-sm text-slate-500">Transações</p>
          <p className="text-3xl font-bold text-slate-800">{summary?.transactions ?? 0}</p>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <p className="text-sm text-slate-500">Última atualização</p>
          <p className="text-3xl font-bold text-slate-800">{new Date().toLocaleString()}</p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <p className="text-lg font-semibold text-slate-800 mb-3">Por categoria</p>
          <PieChart data={byCategory} />
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <p className="text-lg font-semibold text-slate-800 mb-3">Por forma</p>
          <BarChart data={byPayment} />
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <p className="text-lg font-semibold text-slate-800 mb-4">Lançar Receita</p>
        <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <input
            placeholder="Descrição"
            className="border rounded-lg px-3 py-2"
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          />
          <input
            type="number"
            step="0.01"
            placeholder="Valor"
            className="border rounded-lg px-3 py-2"
            value={form.amount}
            onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
          />
          <select
            className="border rounded-lg px-3 py-2"
            value={form.category}
            onChange={(e) => setForm((f) => ({ ...f, category: e.target.value as RevenueCategory }))}
          >
            <option value="hospedagem">Hospedagem</option>
            <option value="consumo">Consumo</option>
            <option value="outros">Outros</option>
          </select>
          <select
            className="border rounded-lg px-3 py-2"
            value={form.payment_method}
            onChange={(e) => setForm((f) => ({ ...f, payment_method: e.target.value as PaymentMethod }))}
          >
            <option value="pix">PIX</option>
            <option value="credito">Crédito</option>
            <option value="debito">Débito</option>
            <option value="dinheiro">Dinheiro</option>
          </select>
          <input
            type="number"
            placeholder="Reserva (opcional)"
            className="border rounded-lg px-3 py-2"
            value={form.booking_id}
            onChange={(e) => setForm((f) => ({ ...f, booking_id: e.target.value }))}
          />
          <button type="submit" className="bg-blue-600 text-white px-5 py-2 rounded-lg shadow-md hover:bg-blue-700 transition font-semibold">Salvar</button>
        </form>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <p className="text-lg font-semibold text-slate-800 mb-4">Transações</p>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-slate-600">
                <th className="py-2">
                  <button className="flex items-center gap-1 hover:underline" onClick={() => headerSort('created_at')}>
                    <span>Data</span><span>{sortArrow('created_at')}</span>
                  </button>
                </th>
                <th className="py-2">
                  <button className="flex items-center gap-1 hover:underline" onClick={() => headerSort('description')}>
                    <span>Descrição</span><span>{sortArrow('description')}</span>
                  </button>
                </th>
                <th className="py-2">
                  <button className="flex items-center gap-1 hover:underline" onClick={() => headerSort('amount')}>
                    <span>Valor</span><span>{sortArrow('amount')}</span>
                  </button>
                </th>
                <th className="py-2">
                  <button className="flex items-center gap-1 hover:underline" onClick={() => headerSort('category')}>
                    <span>Categoria</span><span>{sortArrow('category')}</span>
                  </button>
                </th>
                <th className="py-2">
                  <button className="flex items-center gap-1 hover:underline" onClick={() => headerSort('payment_method')}>
                    <span>Forma</span><span>{sortArrow('payment_method')}</span>
                  </button>
                </th>
                <th className="py-2">Reserva</th>
                <th className="py-2">Ações</th>
              </tr>
            </thead>
            <tbody>
              {revenues.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="py-2">{new Date(r.created_at).toLocaleString()}</td>
                  <td className="py-2">{r.description}</td>
                  <td className="py-2">R$ {r.amount.toFixed(2)}</td>
                  <td className="py-2">{r.category}</td>
                  <td className="py-2">{r.payment_method}</td>
                  <td className="py-2">{r.booking_id ?? '-'}</td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      <button onClick={() => startEdit(r)} className="px-3 py-1 border rounded-lg bg-white hover:bg-slate-50">Editar</button>
                      <button onClick={() => deleteRevenue(r.id)} className="px-3 py-1 border rounded-lg bg-white hover:bg-slate-50">Excluir</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-slate-600">Página {page} de {Math.max(pages, 1)}</p>
          <div className="flex items-center gap-2">
            <button
              className="px-3 py-1 rounded-lg border bg-white hover:bg-slate-50"
              disabled={page <= 1}
              onClick={() => { setPage((p) => Math.max(1, p - 1)); setTimeout(loadReport, 0); }}
            >
              Anterior
            </button>
            {getPageNumbers(pages, page).map((n, idx) => (
              typeof n === 'number' ? (
                <button
                  key={`${n}-${idx}`}
                  className={`px-3 py-1 rounded-lg border ${n === page ? 'bg-blue-600 text-white border-blue-600' : 'bg-white hover:bg-slate-50'}`}
                  onClick={() => { setPage(n); setTimeout(loadReport, 0); }}
                >
                  {n}
                </button>
              ) : (
                <span key={`dots-${idx}`} className="px-2 text-slate-500">…</span>
              )
            ))}
            <button
              className="px-3 py-1 rounded-lg border bg-white hover:bg-slate-50"
              disabled={page >= pages}
              onClick={() => { setPage((p) => p + 1); setTimeout(loadReport, 0); }}
            >
              Próxima
            </button>
          </div>
        </div>
        {editing && (
          <div className="mt-6 border-t pt-4">
            <p className="text-lg font-semibold text-slate-800 mb-3">Editar Receita</p>
            <form onSubmit={submitEdit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <input className="border rounded-lg px-3 py-2" placeholder="Descrição" value={editForm.description} onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))} />
              <input className="border rounded-lg px-3 py-2" type="number" step="0.01" placeholder="Valor" value={editForm.amount} onChange={(e) => setEditForm((f) => ({ ...f, amount: e.target.value }))} />
              <select className="border rounded-lg px-3 py-2" value={editForm.category} onChange={(e) => setEditForm((f) => ({ ...f, category: e.target.value as RevenueCategory }))}>
                <option value="">Categoria</option>
                <option value="hospedagem">Hospedagem</option>
                <option value="consumo">Consumo</option>
                <option value="outros">Outros</option>
              </select>
              <select className="border rounded-lg px-3 py-2" value={editForm.payment_method} onChange={(e) => setEditForm((f) => ({ ...f, payment_method: e.target.value as PaymentMethod }))}>
                <option value="">Forma</option>
                <option value="pix">PIX</option>
                <option value="credito">Crédito</option>
                <option value="debito">Débito</option>
                <option value="dinheiro">Dinheiro</option>
              </select>
              <input className="border rounded-lg px-3 py-2" type="number" placeholder="Reserva (opcional)" value={editForm.booking_id} onChange={(e) => setEditForm((f) => ({ ...f, booking_id: e.target.value }))} />
              <div className="flex gap-2">
                <button type="submit" className="bg-blue-600 text-white px-5 py-2 rounded-lg shadow-md hover:bg-blue-700 transition font-semibold">Salvar alterações</button>
                <button type="button" onClick={() => setEditing(null)} className="border px-5 py-2 rounded-lg bg-white hover:bg-slate-50">Cancelar</button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
