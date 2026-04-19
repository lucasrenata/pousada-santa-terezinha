import React, { useEffect, useState, useCallback } from 'react';
import api from '../services/api';
import {
  TrendingUp, TrendingDown, Minus, DollarSign,
  CheckCircle, Clock, Trash2, Pencil, Plus, ArrowRightLeft, FileText
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────
type RevenueCategory = 'hospedagem' | 'consumo' | 'outros';
type PaymentMethod = 'pix' | 'credito' | 'debito' | 'dinheiro';
type ExpenseCategory =
  | 'agua' | 'energia' | 'internet' | 'manutencao' | 'salarios' | 'limpeza'
  | 'fornecedor' | 'marketing' | 'impostos' | 'aluguel' | 'alimentacao' | 'outros';

interface Revenue {
  id: number;
  description: string;
  amount: number;
  category: RevenueCategory;
  payment_method: PaymentMethod;
  created_at: string;
  booking_id?: number | null;
}

interface Expense {
  id: number;
  description: string;
  amount: number;
  category: ExpenseCategory;
  due_date: string;
  paid_date?: string | null;
  is_paid: boolean;
  payment_method?: PaymentMethod | null;
  notes?: string | null;
  created_at: string;
}

interface CashFlowItem {
  date: string;
  revenue: number;
  expense: number;
  net: number;       // backend retorna 'net', não 'balance'
}

interface CfSummary {
  total_revenue: number;
  total_expense: number;
  net_result: number;
  pending_expenses: number;
}

// Formato real do compare endpoint
interface PeriodSummary {
  start: string; end: string; days: number;
  revenue: number; expense: number; net: number;
  checkins: number; 
  by_category: Record<string, number>;
  expense_by_category: Record<string, number>;
  by_payment: Record<string, number>;
  product_mix: Record<string, number>;
  occupancy_rate: number;
  adr: number;
  revpar: number;
  ticket_medio: number;
}
interface DeltaItem { absolute: number; percent: number | null; }
interface CompareResult {
  period_a: PeriodSummary;
  period_b: PeriodSummary;
  delta: { 
    revenue: DeltaItem; 
    expense: DeltaItem; 
    net: DeltaItem; 
    checkins: DeltaItem;
    occupancy_rate: DeltaItem;
    adr: DeltaItem;
    revpar: DeltaItem;
    ticket_medio: DeltaItem;
  };
}

interface CaixaSession {
  id: number;
  user_full_name?: string;
  status: 'aberto' | 'fechado';
  opened_at: string;
  closed_at?: string;
  opening_balance: number;
  closing_balance?: number;
  summary_json?: {
    user_name: string;
    opening_balance: number;
    vendas_dinheiro: number;
    vendas_pix: number;
    vendas_debito: number;
    vendas_credito: number;
    entradas_total: number;
    retiradas_total: number;
    saldo_dinheiro: number;
    saldo_geral: number;
    comandas_processadas: number;
  };
}

interface PDVSaleItem {
  id: number;
  product_name: string;
  quantity: number;
  unit_price: number;
  total_item: number;
}

interface PDVSale {
  id: number;
  comanda_identificador: string;
  total_amount: number;
  discount: number;
  payment_method: PaymentMethod;
  created_at: string;
  items?: PDVSaleItem[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fmtCurrency = (v: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);

const fmtDate = (s: string) =>
  new Date(s + 'T12:00:00').toLocaleDateString('pt-BR');

const palette = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16'];

const EXPENSE_LABELS: Record<string, string> = {
  agua: 'Água', energia: 'Energia', internet: 'Internet',
  manutencao: 'Manutenção', salarios: 'Salários', limpeza: 'Limpeza',
  fornecedor: 'Fornecedor', marketing: 'Marketing', impostos: 'Impostos',
  aluguel: 'Aluguel', alimentacao: 'Alimentação', outros: 'Outros'
};

// ─── Charts ───────────────────────────────────────────────────────────────────
function PieChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  const total = entries.reduce((acc, [, v]) => acc + v, 0);
  const size = 140; const r = 55; const c = 2 * Math.PI * r;
  let acc = 0;
  return (
    <div className="flex items-center gap-4 flex-wrap">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth={20} />
          {entries.map(([k, v], i) => {
            const dash = total ? (v / total) * c : 0;
            const el = <circle key={k} cx={size / 2} cy={size / 2} r={r} fill="none"
              stroke={palette[i % palette.length]} strokeWidth={20}
              strokeDasharray={`${dash} ${c - dash}`} strokeDashoffset={c - acc} />;
            acc += dash; return el;
          })}
        </g>
        <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fontSize="11" fill="#0f172a" fontWeight="bold">
          {fmtCurrency(total)}
        </text>
      </svg>
      <div className="space-y-1 text-sm">
        {entries.map(([k, v], i) => (
          <div key={k} className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: palette[i % palette.length] }} />
            <span className="text-slate-600">{k}</span>
            <span className="ml-auto font-semibold text-slate-800">{fmtCurrency(v)}</span>
          </div>
        ))}
        {entries.length === 0 && <p className="text-slate-400 italic text-xs">Sem dados</p>}
      </div>
    </div>
  );
}

function BarChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  const max = entries.reduce((acc, [, v]) => Math.max(acc, v), 0) || 1;
  return (
    <div className="space-y-3">
      {entries.map(([k, v], i) => (
        <div key={k}>
          <div className="flex justify-between text-sm text-slate-600 mb-1">
            <span>{k}</span>
            <span className="font-semibold text-slate-800">{fmtCurrency(v)}</span>
          </div>
          <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all duration-700"
              style={{ width: `${(v / max) * 100}%`, backgroundColor: palette[i % palette.length] }} />
          </div>
        </div>
      ))}
      {entries.length === 0 && <p className="text-slate-400 italic text-xs">Sem dados</p>}
    </div>
  );
}

// ─── Delta badge ──────────────────────────────────────────────────────────────
function Delta({ pct, inverted = false }: { pct: number; inverted?: boolean }) {
  const isGood = inverted ? pct < 0 : pct > 0;
  const color = pct === 0 ? 'text-slate-500' : isGood ? 'text-emerald-600' : 'text-red-500';
  const Icon = pct === 0 ? Minus : pct > 0 ? TrendingUp : TrendingDown;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold ${color}`}>
      <Icon size={13} />
      {pct === 0 ? '0%' : `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`}
    </span>
  );
}

// ─── Tab navigation ───────────────────────────────────────────────────────────
type Tab = 'receitas' | 'despesas' | 'fluxo' | 'fechamentos' | 'pdv' | 'comparativo' | 'relatorios';
const TABS: { id: Tab; label: string }[] = [
  { id: 'receitas', label: '💰 Receitas' },
  { id: 'despesas', label: '📋 Despesas' },
  { id: 'pdv', label: '🛒 Vendas PDV' },
  { id: 'fechamentos', label: '⚖️ Fechamentos' },
  { id: 'fluxo', label: '📊 Fluxo de Caixa' },
  { id: 'comparativo', label: '🔀 Comparativo' },
  { id: 'relatorios', label: '📈 Relatórios' },
];

// ─── Main component ───────────────────────────────────────────────────────────
export default function Finance() {
  const [activeTab, setActiveTab] = useState<Tab>('receitas');
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  // Auto-clear messages
  useEffect(() => {
    if (!message && !error) return;
    const t = setTimeout(() => { setMessage(null); setError(null); }, 4000);
    return () => clearTimeout(t);
  }, [message, error]);

  // Modal States
  const [isRevModalOpen, setIsRevModalOpen] = useState(false);
  const [isExpModalOpen, setIsExpModalOpen] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [exportConfig, setExportConfig] = useState({
    start: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10),
    end: new Date().toISOString().slice(0, 10),
    mode: 'full' as 'full' | 'summary'
  });

  const closeFormModals = () => {
    setIsRevModalOpen(false);
    setIsExpModalOpen(false);
    setEditing(null);
    setEditingExp(null);
  };

  // ════════════════════════════════════════════════════════════════
  // ABA 1 — RECEITAS (código original preservado)
  // ════════════════════════════════════════════════════════════════
  const [start, setStart] = useState(() => new Date().toISOString().slice(0, 10));
  const [end, setEnd] = useState(() => new Date().toISOString().slice(0, 10));
  const [summary, setSummary] = useState<{ total_revenue: number; transactions: number } | null>(null);
  const [revenues, setRevenues] = useState<Revenue[]>([]);
  const [filterCategory, setFilterCategory] = useState<RevenueCategory | ''>('');
  const [filterPayment, setFilterPayment] = useState<PaymentMethod | ''>('');
  const [search, setSearch] = useState('');
  const [byCategory, setByCategory] = useState<Record<string, number>>({});
  const [byPayment, setByPayment] = useState<Record<string, number>>({});
  const [editing, setEditing] = useState<Revenue | null>(null);
  const [editForm, setEditForm] = useState({ description: '', amount: '', category: '' as RevenueCategory | '', payment_method: '' as PaymentMethod | '', booking_id: '' });
  const [form, setForm] = useState({ description: '', amount: '', category: 'hospedagem' as RevenueCategory, payment_method: 'pix' as PaymentMethod, booking_id: '' });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [pages, setPages] = useState(0);
  const [sortBy, setSortBy] = useState<'created_at' | 'amount' | 'description' | 'category' | 'payment_method'>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  function toDateString(date: string) {
    if (!date) return undefined;
    return date; 
  }
  function sortArrow(field: typeof sortBy) { return sortBy !== field ? '' : sortDir === 'asc' ? '↑' : '↓'; }
  function headerSort(field: typeof sortBy) {
    if (sortBy === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc'); else { setSortBy(field); setSortDir('desc'); }
    setPage(1); setTimeout(loadReport, 0);
  }
  function getPageNumbers(total: number, current: number) {
    const nums: (number | string)[] = [];
    if (total <= 7) { for (let i = 1; i <= total; i++) nums.push(i); return nums; }
    nums.push(1); if (current > 3) nums.push('...');
    for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) nums.push(i);
    if (current < total - 2) nums.push('...'); nums.push(total); return nums;
  }

  async function loadReport() {
    try {
      setError(null);
      const params: Record<string, string> = {};
      const s = toDateString(start); const e = toDateString(end);
      if (s) params.start = s; if (e) params.end = e;
      if (filterCategory) params.category = filterCategory;
      if (filterPayment) params.payment_method = filterPayment;
      const q = search.trim(); if (q) params.search = q;
      params.page = String(page); params.page_size = String(pageSize);
      params.sort_by = sortBy; params.sort_dir = sortDir;
      const res = await api.get('/finance/report', { params });
      setSummary({ total_revenue: res.data.total_revenue, transactions: res.data.transactions });
      setRevenues(res.data.data);
      setByCategory(res.data.by_category ?? {});
      setByPayment(res.data.by_payment_method ?? {});
      setPages(res.data.pages ?? 0);
    } catch { setError('Falha ao carregar relatório'); }
  }
  useEffect(() => { loadReport(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault(); setMessage(null); setError(null);
    try {
      await api.post('/finance/', { description: form.description, amount: parseFloat(form.amount), category: form.category, payment_method: form.payment_method, booking_id: form.booking_id ? parseInt(form.booking_id) : null });
      setMessage('Receita lançada!'); setForm({ description: '', amount: '', category: 'hospedagem', payment_method: 'pix', booking_id: '' }); setIsRevModalOpen(false); await loadReport();
    } catch { setError('Erro ao lançar receita'); }
  }
  function startEdit(r: Revenue) { setEditing(r); setEditForm({ description: r.description, amount: String(r.amount), category: r.category, payment_method: r.payment_method, booking_id: r.booking_id ? String(r.booking_id) : '' }); setIsRevModalOpen(true); }
  async function submitEdit(e: React.FormEvent) {
    e.preventDefault(); if (!editing) return;
    try {
      const payload: any = {};
      if (editForm.description) payload.description = editForm.description;
      if (editForm.amount) payload.amount = parseFloat(editForm.amount);
      if (editForm.category) payload.category = editForm.category;
      if (editForm.payment_method) payload.payment_method = editForm.payment_method;
      if (editForm.booking_id) payload.booking_id = parseInt(editForm.booking_id);
      await api.put(`/finance/${editing.id}`, payload); setEditing(null); setIsRevModalOpen(false); await loadReport(); setMessage('Receita atualizada!');
    } catch { setError('Erro ao atualizar receita'); }
  }
  async function deleteRevenue(id: number) {
    if (!confirm('Excluir esta receita?')) return;
    try { await api.delete(`/finance/${id}`); await loadReport(); setMessage('Receita excluída'); }
    catch { setError('Erro ao excluir'); }
  }

  // ════════════════════════════════════════════════════════════════
  // ABA 2 — DESPESAS
  // ════════════════════════════════════════════════════════════════
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [expLoading, setExpLoading] = useState(false);
  const [expFilterCat, setExpFilterCat] = useState<ExpenseCategory | ''>('');
  const [expFilterPaid, setExpFilterPaid] = useState<'all' | 'paid' | 'pending'>('all');
  const [expStart, setExpStart] = useState('');
  const [expEnd, setExpEnd] = useState('');
  const [editingExp, setEditingExp] = useState<Expense | null>(null);
  const [expForm, setExpForm] = useState({
    description: '', amount: '', category: 'outros' as ExpenseCategory,
    due_date: '', payment_method: '' as PaymentMethod | '', notes: '',
  });

  const loadExpenses = useCallback(async () => {
    setExpLoading(true);
    try {
      const params: Record<string, string> = {};
      if (expFilterCat) params.category = expFilterCat;
      if (expFilterPaid === 'paid') params.is_paid = 'true';
      if (expFilterPaid === 'pending') params.is_paid = 'false';
      if (expStart) params.start = expStart;
      if (expEnd) params.end = expEnd;
      const res = await api.get('/finance/expenses/', { params });
      setExpenses(res.data.data ?? res.data);
    } catch { setError('Falha ao carregar despesas'); }
    finally { setExpLoading(false); }
  }, [expFilterCat, expFilterPaid, expStart, expEnd]);

  useEffect(() => { if (activeTab === 'despesas') loadExpenses(); }, [activeTab, loadExpenses]);

  async function createExpense(e: React.FormEvent) {
    e.preventDefault(); setMessage(null); setError(null);
    try {
      await api.post('/finance/expenses/', {
        description: expForm.description, amount: parseFloat(expForm.amount),
        category: expForm.category, due_date: expForm.due_date,
        payment_method: expForm.payment_method || null, notes: expForm.notes || null,
      });
      setMessage('Despesa lançada!');
      setExpForm({ description: '', amount: '', category: 'outros', due_date: '', payment_method: '', notes: '' });
      setIsExpModalOpen(false);
      await loadExpenses();
    } catch { setError('Erro ao lançar despesa'); }
  }

  async function markAsPaid(exp: Expense) {
    try {
      await api.put(`/finance/expenses/${exp.id}`, { is_paid: true, paid_date: new Date().toISOString().slice(0, 10) });
      setMessage('Marcada como paga!'); await loadExpenses();
    } catch { setError('Erro ao marcar como paga'); }
  }

  async function deleteExpense(id: number) {
    if (!confirm('Excluir esta despesa?')) return;
    try { await api.delete(`/finance/expenses/${id}`); setMessage('Despesa excluída'); await loadExpenses(); }
    catch { setError('Erro ao excluir despesa'); }
  }

  async function submitEditExp(e: React.FormEvent) {
    e.preventDefault(); if (!editingExp) return;
    try {
      const payload: any = {
        description: expForm.description,
        amount: parseFloat(expForm.amount),
        category: expForm.category,
        due_date: expForm.due_date,
        payment_method: expForm.payment_method || null,
        notes: expForm.notes || null,
      };
      await api.put(`/finance/expenses/${editingExp.id}`, payload);
      setEditingExp(null); setMessage('Despesa atualizada!'); setIsExpModalOpen(false); await loadExpenses();
    } catch { setError('Erro ao atualizar despesa'); }
  }

  function startEditExp(exp: Expense) {
    setEditingExp(exp);
    setExpForm({
      description: exp.description, amount: String(exp.amount),
      category: exp.category, due_date: exp.due_date,
      payment_method: exp.payment_method ?? '', notes: exp.notes ?? '',
    });
    setIsExpModalOpen(true);
  }

  // ════════════════════════════════════════════════════════════════
  // ABA 3 — FLUXO DE CAIXA
  // ════════════════════════════════════════════════════════════════
  const [cashFlow, setCashFlow] = useState<CashFlowItem[]>([]);
  const [cfLoading, setCfLoading] = useState(false);
  const [cfStart, setCfStart] = useState(() => { const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10); });
  const [cfEnd, setCfEnd] = useState(() => new Date().toISOString().slice(0, 10));

  const [cfSummary, setCfSummary] = useState<CfSummary>({ total_revenue: 0, total_expense: 0, net_result: 0, pending_expenses: 0 });

  const loadCashFlow = useCallback(async () => {
    setCfLoading(true);
    try {
      const res = await api.get('/finance/cash-flow', { params: { start: cfStart, end: cfEnd } });
      // Backend retorna um OBJETO com chave 'timeline', não um array diretamente
      const data = res.data;
      setCashFlow(Array.isArray(data.timeline) ? data.timeline : []);
      setCfSummary({
        total_revenue: data.total_revenue ?? 0,
        total_expense: data.total_expense ?? 0,
        net_result: data.net_result ?? 0,
        pending_expenses: data.pending_expenses ?? 0,
      });
    } catch { setError('Falha ao carregar fluxo de caixa'); }
    finally { setCfLoading(false); }
  }, [cfStart, cfEnd]);

  useEffect(() => { if (activeTab === 'fluxo') loadCashFlow(); }, [activeTab, loadCashFlow]);
  
  // ════════════════════════════════════════════════════════════════
  // ABA 4 — COMPARATIVO
  // ════════════════════════════════════════════════════════════════
  const [p1Start, setP1Start] = useState(() => {
    const d = new Date(); d.setMonth(d.getMonth() - 1); d.setDate(1);
    return d.toISOString().slice(0, 10);
  });
  const [p1End, setP1End] = useState(() => {
    const d = new Date(); d.setDate(0);
    return d.toISOString().slice(0, 10);
  });
  const [p2Start, setP2Start] = useState(() => {
    const d = new Date(); d.setDate(1);
    return d.toISOString().slice(0, 10);
  });
  const [p2End, setP2End] = useState(() => new Date().toISOString().slice(0, 10));
  const [cmpLoading, setCmpLoading] = useState(false);
  const [cmpResult, setCmpResult] = useState<any>(null);

  async function loadCompare() {
    if (!p1Start || !p1End || !p2Start || !p2End) { setError('Preencha os 4 campos de data'); return; }
    setCmpLoading(true);
    try {
      const res = await api.get('/finance/compare', { params: { p1_start: p1Start, p1_end: p1End, p2_start: p2Start, p2_end: p2End } });
      setCmpResult(res.data);
    } catch { setError('Falha ao carregar comparativo'); }
    finally { setCmpLoading(false); }
  }

  // ════════════════════════════════════════════════════════════════
  // ABA 5 — FECHAMENTOS DE CAIXA
  // ════════════════════════════════════════════════════════════════
  const [closings, setClosings] = useState<CaixaSession[]>([]);
  const [closingsLoading, setClosingsLoading] = useState(false);
  const [closingsStart, setClosingsStart] = useState('');
  const [closingsEnd, setClosingsEnd] = useState('');

  const loadClosings = useCallback(async () => {
    setClosingsLoading(true);
    try {
      const params: any = {};
      if (closingsStart) params.start = closingsStart;
      if (closingsEnd) params.end = closingsEnd;
      const res = await api.get('/finance/caixa-closings', { params });
      setClosings(res.data);
    } catch {
      setError('Falha ao carregar históricos de fechamento');
    } finally {
      setClosingsLoading(false);
    }
  }, [closingsStart, closingsEnd]);

  useEffect(() => {
    if (activeTab === 'fechamentos') loadClosings();
  }, [activeTab, loadClosings]);

  // ════════════════════════════════════════════════════════════════
  // ABA 6 — HISTÓRICO DE VENDAS PDV
  // ════════════════════════════════════════════════════════════════
  const [pdvSales, setPdvSales] = useState<PDVSale[]>([]);
  const [pdvLoading, setPdvLoading] = useState(false);
  const [pdvStart, setPdvStart] = useState('');
  const [pdvEnd, setPdvEnd] = useState('');
  const [selectedSale, setSelectedSale] = useState<PDVSale | null>(null);

  const loadPdvSales = useCallback(async () => {
    setPdvLoading(true);
    try {
      const params: any = {};
      if (pdvStart) params.start = pdvStart;
      if (pdvEnd) params.end = pdvEnd;
      const res = await api.get('/finance/pdv-sales', { params });
      setPdvSales(res.data);
    } catch {
      setError('Falha ao carregar histórico de vendas do PDV');
    } finally {
      setPdvLoading(false);
    }
  }, [pdvStart, pdvEnd]);

  const viewSaleDetail = async (sale: PDVSale) => {
    try {
      const res = await api.get(`/finance/pdv-sales/${sale.id}`);
      setSelectedSale(res.data);
    } catch {
      setError('Falha ao carregar detalhes da venda');
    }
  };

  useEffect(() => {
    if (activeTab === 'pdv') loadPdvSales();
  }, [activeTab, loadPdvSales]);

  // ════════════════════════════════════════════════════════════════
  // INPUT / SELECT helpers
  // ════════════════════════════════════════════════════════════════
  const inputCls = 'border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white w-full';
  const btnPrimary = 'bg-blue-600 text-white px-5 py-2 rounded-xl shadow hover:bg-blue-700 transition font-semibold text-sm disabled:opacity-50';
  const btnSecondary = 'border border-slate-200 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 text-sm font-medium transition';

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-slate-50/50">

      {/* ── Sidebar de Navegação ── */}
      <aside className="w-full md:w-64 bg-white border-r border-slate-200 p-6 flex flex-col gap-6">
        <div>
          <h2 className="text-2xl font-black text-slate-800 tracking-tight flex items-center gap-2">
            <DollarSign className="text-blue-600" />
            ParcerIA
          </h2>
          <p className="text-[10px] uppercase font-bold text-slate-400 tracking-widest mt-1 ml-8">Gestão Financeira</p>
        </div>

        <nav className="space-y-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${activeTab === tab.id
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-100'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
                }`}
            >
              <span className="text-lg">{tab.label.split(' ')[0]}</span>
              {tab.label.split(' ').slice(1).join(' ')}
            </button>
          ))}
        </nav>
        <div className="mt-auto pt-6 border-t border-slate-100 flex flex-col gap-3">
          <div className="bg-slate-50 rounded-2xl p-4">
            <p className="text-[10px] font-bold text-slate-400 uppercase mb-2">Resumo Rápido</p>
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-slate-500">Saldo Hoje</span>
                <span className={`text-xs font-bold ${cfSummary.net_result >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                  {fmtCurrency(cfSummary.net_result)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Conteúdo Principal ── */}
      <main className="flex-1 p-4 md:p-8 space-y-8 max-w-6xl mx-auto w-full">
        {/* Alertas */}
        {error && <div className="bg-red-50 text-red-700 rounded-xl border border-red-200 p-4 text-sm animate-in fade-in slide-in-from-top-2">{error}</div>}
        {message && <div className="bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-200 p-4 text-sm animate-in fade-in slide-in-from-top-2">{message}</div>}


        {/* ══════════════════════════════════ ABA RECEITAS ══════════════════════════════════ */}
        {activeTab === 'receitas' && (
          <div className="space-y-6 animate-in fade-in duration-500">

            <div className="flex justify-between items-end gap-4">
              <div>
                <h3 className="text-2xl font-bold text-slate-800">Receitas</h3>
                <p className="text-slate-500 text-sm">Controle de entradas e pagamentos de hóspedes.</p>
              </div>
              <button
                onClick={() => { setIsRevModalOpen(true); setEditing(null); setForm({ description: '', amount: '', category: 'hospedagem', payment_method: 'pix', booking_id: '' }); }}
                className={btnPrimary + " flex items-center gap-2 py-3 px-6 shadow-blue-200 shadow-lg"}
              >
                <Plus size={18} /> Nova Receita
              </button>
            </div>

            {/* Filtros */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
              <p className="text-base font-semibold text-slate-800 mb-4">Filtro de Período</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9 gap-3">
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Início</label><input type="date" className={inputCls} value={start} onChange={e => setStart(e.target.value)} /></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Fim</label><input type="date" className={inputCls} value={end} onChange={e => setEnd(e.target.value)} /></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Categoria</label>
                  <select className={inputCls} value={filterCategory} onChange={e => setFilterCategory(e.target.value as RevenueCategory | '')}>
                    <option value="">Todas</option><option value="hospedagem">Hospedagem</option><option value="consumo">Consumo</option><option value="outros">Outros</option>
                  </select></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Forma</label>
                  <select className={inputCls} value={filterPayment} onChange={e => setFilterPayment(e.target.value as PaymentMethod | '')}>
                    <option value="">Todas</option><option value="pix">PIX</option><option value="credito">Crédito</option><option value="debito">Débito</option><option value="dinheiro">Dinheiro</option>
                  </select></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Buscar</label><input className={inputCls} placeholder="Descrição..." value={search} onChange={e => setSearch(e.target.value)} /></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Ordenar</label>
                  <select className={inputCls} value={sortBy} onChange={e => setSortBy(e.target.value as typeof sortBy)}>
                    <option value="created_at">Data</option><option value="amount">Valor</option><option value="description">Descrição</option><option value="category">Categoria</option><option value="payment_method">Forma</option>
                  </select></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Direção</label>
                  <select className={inputCls} value={sortDir} onChange={e => setSortDir(e.target.value as typeof sortDir)}>
                    <option value="desc">Desc</option><option value="asc">Asc</option>
                  </select></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Por página</label>
                  <select className={inputCls} value={pageSize} onChange={e => setPageSize(parseInt(e.target.value))}>
                    <option value={10}>10</option><option value={25}>25</option><option value={50}>50</option>
                  </select></div>
                <div className="flex items-end"><button onClick={loadReport} className={btnPrimary + ' w-full'}>Aplicar</button></div>
              </div>
            </div>

            {/* KPI cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-2xl border border-slate-200 p-5"><p className="text-xs text-slate-500 mb-1">Receita Total</p><p className="text-3xl font-black text-slate-800">{fmtCurrency(summary?.total_revenue ?? 0)}</p></div>
              <div className="bg-white rounded-2xl border border-slate-200 p-5"><p className="text-xs text-slate-500 mb-1">Transações</p><p className="text-3xl font-black text-slate-800">{summary?.transactions ?? 0}</p></div>
              <div className="bg-white rounded-2xl border border-slate-200 p-5"><p className="text-xs text-slate-500 mb-1">Última atualização</p><p className="text-xl font-bold text-slate-800">{new Date().toLocaleTimeString('pt-BR')}</p></div>
            </div>

            {/* Gráficos */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white rounded-2xl border border-slate-200 p-6"><p className="text-sm font-semibold text-slate-700 mb-4">Por categoria</p><PieChart data={byCategory} /></div>
              <div className="bg-white rounded-2xl border border-slate-200 p-6"><p className="text-sm font-semibold text-slate-700 mb-4">Por forma de pagamento</p><BarChart data={byPayment} /></div>
            </div>

            {/* Tabela de receitas */}
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
              <div className="p-5 border-b border-slate-100"><p className="text-base font-semibold text-slate-800">Transações</p></div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600 text-xs">
                    <tr>
                      {(['created_at', 'description', 'amount', 'category', 'payment_method'] as const).map(field => (
                        <th key={field} className="px-4 py-3 text-left font-semibold">
                          <button className="hover:text-slate-900 flex items-center gap-1" onClick={() => headerSort(field)}>
                            {{ created_at: 'Data', description: 'Descrição', amount: 'Valor', category: 'Categoria', payment_method: 'Forma' }[field]} {sortArrow(field)}
                          </button>
                        </th>
                      ))}
                      <th className="px-4 py-3 text-left font-semibold">Reserva</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {revenues.map(r => (
                      <tr key={r.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3 text-slate-600">{new Date(r.created_at).toLocaleDateString('pt-BR')}</td>
                        <td className="px-4 py-3 font-medium text-slate-800">{r.description}</td>
                        <td className="px-4 py-3 text-emerald-700 font-semibold">{fmtCurrency(r.amount)}</td>
                        <td className="px-4 py-3"><span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded-lg text-xs font-medium capitalize">{r.category}</span></td>
                        <td className="px-4 py-3 uppercase text-xs text-slate-500">{r.payment_method}</td>
                        <td className="px-4 py-3 text-slate-500">{r.booking_id ?? '-'}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1">
                            <button onClick={() => startEdit(r)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700"><Pencil size={14} /></button>
                            <button onClick={() => deleteRevenue(r.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-500 hover:text-red-600"><Trash2 size={14} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {revenues.length === 0 && <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-400 italic">Sem registros para este filtro</td></tr>}
                  </tbody>
                </table>
              </div>
              {/* Paginação */}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════ ABA DESPESAS ══════════════════════════════════ */}
        {activeTab === 'despesas' && (
          <div className="space-y-6 animate-in fade-in duration-500">

            <div className="flex justify-between items-end gap-4">
              <div>
                <h3 className="text-2xl font-bold text-slate-800">Despesas</h3>
                <p className="text-slate-500 text-sm">Gestão de contas a pagar e custos fixos.</p>
              </div>
              <button
                onClick={() => { setIsExpModalOpen(true); setEditingExp(null); setExpForm({ description: '', amount: '', category: 'outros', due_date: '', payment_method: '', notes: '' }); }}
                className={btnPrimary + " flex items-center gap-2 py-3 px-6 shadow-blue-200 shadow-lg"}
              >
                <Plus size={18} /> Nova Despesa
              </button>
            </div>

            {/* Filtros despesas */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <div className="flex flex-wrap gap-3 items-end">
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Início</label><input type="date" className={inputCls} value={expStart} onChange={e => setExpStart(e.target.value)} /></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Fim</label><input type="date" className={inputCls} value={expEnd} onChange={e => setExpEnd(e.target.value)} /></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Categoria</label>
                  <select className={inputCls + ' min-w-[140px]'} value={expFilterCat} onChange={e => setExpFilterCat(e.target.value as ExpenseCategory | '')}>
                    <option value="">Todas</option>
                    {Object.entries(EXPENSE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Status</label>
                  <select className={inputCls} value={expFilterPaid} onChange={e => setExpFilterPaid(e.target.value as typeof expFilterPaid)}>
                    <option value="all">Todas</option><option value="pending">Pendentes</option><option value="paid">Pagas</option>
                  </select></div>
                <button onClick={loadExpenses} className={btnPrimary}>Filtrar</button>
              </div>
            </div>

            {/* Tabela de despesas */}
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600 text-xs">
                    <tr>
                      <th className="px-4 py-3 text-left font-semibold">Descrição</th>
                      <th className="px-4 py-3 text-left font-semibold">Valor</th>
                      <th className="px-4 py-3 text-left font-semibold">Categoria</th>
                      <th className="px-4 py-3 text-left font-semibold">Vencimento</th>
                      <th className="px-4 py-3 text-left font-semibold">Status</th>
                      <th className="px-4 py-3 text-left font-semibold">Ações</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {expLoading && <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400 text-xs">Carregando...</td></tr>}
                    {!expLoading && expenses.map(exp => {
                      const overdue = !exp.is_paid && exp.due_date < new Date().toISOString().slice(0, 10);
                      return (
                        <tr key={exp.id} className={`hover:bg-slate-50 transition-colors ${overdue ? 'bg-red-50/40' : ''}`}>
                          <td className="px-4 py-3 font-medium text-slate-800">
                            {exp.description}
                            {exp.notes && <p className="text-xs text-slate-400 mt-0.5">{exp.notes}</p>}
                          </td>
                          <td className="px-4 py-3 text-red-600 font-semibold">{fmtCurrency(exp.amount)}</td>
                          <td className="px-4 py-3"><span className="bg-orange-50 text-orange-700 px-2 py-0.5 rounded-lg text-xs font-medium">{EXPENSE_LABELS[exp.category] ?? exp.category}</span></td>
                          <td className={`px-4 py-3 text-xs ${overdue ? 'text-red-600 font-bold' : 'text-slate-500'}`}>{fmtDate(exp.due_date)}{overdue && <span className="ml-1 text-[10px] bg-red-100 text-red-600 px-1 rounded">VENCIDA</span>}</td>
                          <td className="px-4 py-3">
                            {exp.is_paid
                              ? <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-lg text-xs font-semibold"><CheckCircle size={11} />Paga{exp.paid_date && ` · ${fmtDate(exp.paid_date)}`}</span>
                              : <span className="inline-flex items-center gap-1 text-amber-700 bg-amber-50 px-2 py-0.5 rounded-lg text-xs font-semibold"><Clock size={11} />Pendente</span>
                            }
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex gap-1">
                              {!exp.is_paid && <button onClick={() => markAsPaid(exp)} title="Marcar como paga" className="p-1.5 rounded-lg hover:bg-emerald-50 text-slate-500 hover:text-emerald-700"><CheckCircle size={14} /></button>}
                              <button onClick={() => startEditExp(exp)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700"><Pencil size={14} /></button>
                              <button onClick={() => deleteExpense(exp.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-500 hover:text-red-600"><Trash2 size={14} /></button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                    {!expLoading && expenses.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-slate-400 italic">Nenhuma despesa encontrada</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ══════════════════════════════════ ABA FLUXO DE CAIXA ══════════════════════════════════ */}
        {activeTab === 'fluxo' && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div>
              <h3 className="text-2xl font-bold text-slate-800">Fluxo de Caixa</h3>
              <p className="text-slate-500 text-sm">Visão consolidada de entradas e saídas.</p>
            </div>
            {/* Filtro período */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <div className="flex flex-wrap gap-3 items-end">
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Início</label><input type="date" className={inputCls} value={cfStart} onChange={e => setCfStart(e.target.value)} /></div>
                <div><label className="block text-xs font-medium text-slate-600 mb-1">Fim</label><input type="date" className={inputCls} value={cfEnd} onChange={e => setCfEnd(e.target.value)} /></div>
                <button onClick={loadCashFlow} className={btnPrimary}>Aplicar</button>
              </div>
            </div>

            {/* Totais — vindos diretamente do backend (pré-calculados) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-gradient-to-br from-emerald-600 to-teal-700 text-white rounded-2xl p-5">
                <p className="text-xs opacity-70 mb-1">Total Receitas</p>
                <p className="text-3xl font-black">{fmtCurrency(cfSummary.total_revenue)}</p>
              </div>
              <div className="bg-gradient-to-br from-red-500 to-rose-600 text-white rounded-2xl p-5">
                <p className="text-xs opacity-70 mb-1">Total Despesas Pagas</p>
                <p className="text-3xl font-black">{fmtCurrency(cfSummary.total_expense)}</p>
              </div>
              <div className={`text-white rounded-2xl p-5 bg-gradient-to-br ${cfSummary.net_result >= 0 ? 'from-blue-600 to-indigo-700' : 'from-slate-600 to-slate-700'}`}>
                <p className="text-xs opacity-70 mb-1">Saldo Líquido</p>
                <p className="text-3xl font-black">{fmtCurrency(cfSummary.net_result)}</p>
                {cfSummary.pending_expenses > 0 && <p className="text-[10px] opacity-60 mt-1">{fmtCurrency(cfSummary.pending_expenses)} em contas pendentes</p>}
              </div>
            </div>

            {/* Tabela diária */}
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
              <div className="p-4 border-b border-slate-100 flex justify-between items-center">
                <p className="text-sm font-semibold text-slate-800">Detalhamento Diário</p>
              </div>
              {cfLoading ? <div className="p-8 text-center text-slate-400 text-sm">Carregando...</div> : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-xs text-slate-600">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold">Data</th>
                        <th className="px-4 py-3 text-right font-semibold text-emerald-700">+ Receitas</th>
                        <th className="px-4 py-3 text-right font-semibold text-red-600">− Despesas</th>
                        <th className="px-4 py-3 text-right font-semibold">= Saldo</th>
                        <th className="px-4 py-3 text-right font-semibold">Gráfico</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {cashFlow.map(row => {
                        const maxVal = Math.max(...cashFlow.map(r => r.revenue || 0), 1);
                        return (
                          <tr key={row.date} className="hover:bg-slate-50 transition-colors">
                            <td className="px-4 py-3 font-medium text-slate-700">{fmtDate(row.date)}</td>
                            <td className="px-4 py-3 text-right text-emerald-700 font-semibold">{fmtCurrency(row.revenue)}</td>
                            <td className="px-4 py-3 text-right text-red-600 font-semibold">{row.expense > 0 ? fmtCurrency(row.expense) : '—'}</td>
                            <td className={`px-4 py-3 text-right font-bold ${row.net >= 0 ? 'text-slate-800' : 'text-red-600'}`}>{fmtCurrency(row.net)}</td>
                            <td className="px-4 py-3 w-32">
                              <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                <div className="h-full bg-blue-500" style={{ width: `${((row.revenue || 0) / maxVal) * 100}%` }} />
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ══════════════════════════════════ ABA COMPARATIVO (RAIO-X) ══════════════════════════════════ */}
        {activeTab === 'comparativo' && (
          <div className="space-y-6 animate-in fade-in duration-500 pb-12">
            <div className="flex justify-between items-end">
              <div>
                <h3 className="text-2xl font-black text-slate-800 tracking-tight">Raio-X Comparativo</h3>
                <p className="text-slate-500 text-sm">Análise estratégica de performance e demanda entre períodos selecionados.</p>
              </div>
              <div className="bg-violet-600/5 p-2 rounded-2xl border border-violet-100">
                <ArrowRightLeft className="text-violet-600" size={24} />
              </div>
            </div>

            {/* Seletor de períodos */}
            <div className="bg-white rounded-[2.5rem] border border-slate-200 p-8 shadow-sm">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="p-6 rounded-3xl border border-blue-100 bg-blue-50/30">
                  <p className="text-[10px] font-black text-blue-700 uppercase tracking-widest mb-4">Período A (Referência)</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div><label className="text-[10px] font-bold text-slate-400 uppercase mb-2 block">Início</label><input type="date" className={inputCls} value={p1Start} onChange={e => setP1Start(e.target.value)} /></div>
                    <div><label className="text-[10px] font-bold text-slate-400 uppercase mb-2 block">Fim</label><input type="date" className={inputCls} value={p1End} onChange={e => setP1End(e.target.value)} /></div>
                  </div>
                </div>
                <div className="p-6 rounded-3xl border border-violet-100 bg-violet-50/30">
                  <p className="text-[10px] font-black text-violet-700 uppercase tracking-widest mb-4">Período B (Comparativo)</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div><label className="text-[10px] font-bold text-slate-400 uppercase mb-2 block">Início</label><input type="date" className={inputCls} value={p2Start} onChange={e => setP2Start(e.target.value)} /></div>
                    <div><label className="text-[10px] font-bold text-slate-400 uppercase mb-2 block">Fim</label><input type="date" className={inputCls} value={p2End} onChange={e => setP2End(e.target.value)} /></div>
                  </div>
                </div>
              </div>
              <button 
                onClick={loadCompare} 
                disabled={cmpLoading} 
                className="w-full mt-6 bg-slate-900 hover:bg-black text-white py-4 rounded-2xl font-black text-xs tracking-widest transition-all shadow-lg active:scale-[0.98]"
              >
                {cmpLoading ? 'PROCESSANDO ANÁLISE...' : 'GERAR RAIO-X COMPARATIVO'}
              </button>
            </div>

            {/* Resultado Rico (Raio-X) */}
            {cmpResult && (() => {
              const { period_a, period_b, delta } = cmpResult;
              
              const mainKpis = [
                { label: 'Receita Total', a: period_a.revenue, b: period_b.revenue, d: delta.revenue, isCurrency: true },
                { label: 'Despesas Pagas', a: period_a.expense, b: period_b.expense, d: delta.expense, isCurrency: true, inverted: true },
                { label: 'Saldo Líquido', a: period_a.net, b: period_b.net, d: delta.net, isCurrency: true },
              ];

              const hotelKpis = [
                { label: 'ADR (Diária Média)', a: period_a.adr, b: period_b.adr, d: delta.adr, isCurrency: true },
                { label: 'Ocupação', a: period_a.occupancy_rate, b: period_b.occupancy_rate, d: delta.occupancy_rate, suffix: '%' },
                { label: 'RevPAR', a: period_a.revpar, b: period_b.revpar, d: delta.revpar, isCurrency: true },
                { label: 'Ticket Médio/Ref', a: period_a.ticket_medio, b: period_b.ticket_medio, d: delta.ticket_medio, isCurrency: true },
              ];

              const allProducts = Array.from(new Set([...Object.keys(period_a.product_mix || {}), ...Object.keys(period_b.product_mix || {})])).sort();

              return (
                <div className="space-y-10 animate-in slide-in-from-bottom-4 duration-500">
                  
                  {/* Grid de KPIs Financeiros */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {mainKpis.map(kpi => (
                      <div key={kpi.label} className="bg-white p-7 rounded-[2rem] border border-slate-200 shadow-sm transition-all hover:shadow-md">
                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4">{kpi.label}</p>
                        <div className="flex justify-between items-end">
                          <div>
                            <p className="text-2xl font-black text-slate-800">{fmtCurrency(kpi.b)}</p>
                            <p className="text-[10px] text-slate-400 mt-1">Anterior: {fmtCurrency(kpi.a)}</p>
                          </div>
                          <div className="text-right">
                             <Delta pct={kpi.d?.percent ?? 0} inverted={kpi.inverted} />
                             <p className="text-[10px] text-slate-400 font-bold mt-1">{kpi.d?.absolute >= 0 ? '+' : ''}{fmtCurrency(kpi.d?.absolute || 0)}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Dash de Performance Hoteleira */}
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                     {hotelKpis.map(kpi => (
                        <div key={kpi.label} className="bg-slate-900 text-white p-6 rounded-[2rem] shadow-xl">
                           <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-3">{kpi.label}</p>
                           <h4 className="text-xl font-black mb-1">{kpi.isCurrency ? fmtCurrency(kpi.b) : `${kpi.b}${kpi.suffix || ''}`}</h4>
                           <div className="flex items-center gap-2">
                              {kpi.d && <Delta pct={kpi.d.percent ?? 0} />}
                              <span className="text-[9px] text-slate-500 font-bold">vs anterior</span>
                           </div>
                        </div>
                     ))}
                  </div>

                  {/* Comparativo de Mix de Produtos (Demanda por Evento) */}
                  <div className="bg-white rounded-[2.5rem] border border-slate-200 overflow-hidden shadow-sm">
                    <div className="p-8 border-b border-slate-100 flex justify-between items-center bg-slate-50/30">
                       <div>
                         <h4 className="text-lg font-black text-slate-800 tracking-tight">Raio-X de Demanda (Mix de Vendas)</h4>
                         <p className="text-xs text-slate-500">Compare a performance de venda item a item entre os períodos.</p>
                       </div>
                       <div className="bg-violet-600 text-white px-4 py-2 rounded-2xl text-[10px] font-black uppercase tracking-widest">
                          Business Intelligence
                       </div>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-[10px] uppercase font-bold text-slate-500 border-b border-slate-100">
                          <tr>
                            <th className="px-8 py-5 text-left">Produto / Serviço</th>
                            <th className="px-8 py-5 text-center bg-blue-50/30 text-blue-700 border-x border-blue-100/50">Qtd Período A</th>
                            <th className="px-8 py-5 text-center bg-violet-50/30 text-violet-700 border-x border-violet-100/50">Qtd Período B</th>
                            <th className="px-8 py-5 text-center">Variação Real</th>
                            <th className="px-8 py-5 text-right pr-12">Crescimento %</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {allProducts.length === 0 ? (
                            <tr><td colSpan={5} className="px-8 py-24 text-center text-slate-400 italic">Nenhum dado de venda disponível para comparação nestes períodos.</td></tr>
                          ) : allProducts.map(name => {
                            const qa = period_a.product_mix?.[name] || 0;
                            const qb = period_b.product_mix?.[name] || 0;
                            const diff = qb - qa;
                            const pct = qa > 0 ? (diff / qa) * 100 : 0;
                            return (
                              <tr key={name} className="hover:bg-slate-50/50 transition-colors">
                                <td className="px-8 py-6 font-bold text-slate-700">{name}</td>
                                <td className="px-8 py-6 text-center font-mono text-slate-500 bg-blue-50/5 border-x border-blue-100/50">{qa}</td>
                                <td className="px-8 py-6 text-center font-black text-slate-900 bg-violet-50/5 border-x border-violet-100/50">{qb}</td>
                                <td className={`px-8 py-6 text-center font-bold ${diff >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                                  {diff > 0 ? '+' : ''}{diff}
                                </td>
                                <td className="px-8 py-6 text-right pr-12">
                                  <div className="flex items-center justify-end gap-3">
                                    <div className="w-24 h-2 bg-slate-100 rounded-full overflow-hidden">
                                       <div className={`h-full rounded-full ${diff >= 0 ? 'bg-emerald-500' : 'bg-red-500'}`} style={{ width: `${Math.min(Math.abs(pct), 100)}%` }} />
                                    </div>
                                    <span className={`text-[11px] font-black ${diff >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                                      {diff > 0 ? '+' : ''}{pct.toFixed(0)}%
                                    </span>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Mix de Faturamento Comparativo */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                     <div className="bg-white p-10 rounded-[2.5rem] border border-slate-200 shadow-sm">
                        <h5 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-6 border-b border-slate-100 pb-4 flex justify-between">
                           <span>Mix de Receita A</span>
                           <span className="text-[10px] font-normal lowercase italic text-slate-400">{fmtDate(period_a.start)}</span>
                        </h5>
                        <PieChart data={period_a.by_category} />
                     </div>
                     <div className="bg-white p-10 rounded-[2.5rem] border border-slate-200 shadow-sm">
                        <h5 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-6 border-b border-slate-100 pb-4 flex justify-between">
                           <span>Mix de Receita B</span>
                           <span className="text-[10px] font-normal lowercase italic text-slate-400">{fmtDate(period_b.start)}</span>
                        </h5>
                        <PieChart data={period_b.by_category} />
                     </div>
                  </div>

                </div>
              );
            })()}
          </div>
        )}


        {/* ══════════════════════════════════ ABA FECHAMENTOS ══════════════════════════════════ */}
        {activeTab === 'fechamentos' && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div>
              <h3 className="text-2xl font-bold text-slate-800 tracking-tight">Governança de Caixa</h3>
              <p className="text-slate-500 text-sm">Histórico consolidado de turnos e conferência de valores.</p>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <div className="flex flex-wrap gap-3 items-end">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Início</label>
                  <input type="date" className={inputCls} value={closingsStart} onChange={e => setClosingsStart(e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Fim</label>
                  <input type="date" className={inputCls} value={closingsEnd} onChange={e => setClosingsEnd(e.target.value)} />
                </div>
                <button onClick={loadClosings} className={btnPrimary}>Filtrar Histórico</button>
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600 text-[10px] uppercase font-bold tracking-wider">
                    <tr>
                      <th className="px-4 py-4 text-left">Data/Hora</th>
                      <th className="px-4 py-4 text-left">Operador</th>
                      <th className="px-4 py-4 text-right">Abertura</th>
                      <th className="px-4 py-4 text-center">Vendas por Meio</th>
                      <th className="px-4 py-4 text-right">Retiradas</th>
                      <th className="px-4 py-4 text-right">Saldo do Dia</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {closingsLoading && <tr><td colSpan={6} className="px-4 py-12 text-center text-slate-400">Carregando auditoria...</td></tr>}
                    {!closingsLoading && closings.map(c => {
                      const s = c.summary_json;
                      if (!s) return null;
                      return (
                        <tr key={c.id} className="hover:bg-slate-50/80 transition-colors">
                          <td className="px-4 py-4">
                            <p className="font-bold text-slate-800">{new Date(c.closed_at!).toLocaleDateString('pt-BR')}</p>
                            <p className="text-[10px] text-slate-400">{new Date(c.closed_at!).toLocaleTimeString('pt-BR')}</p>
                          </td>
                          <td className="px-4 py-4">
                            <span className="text-xs font-semibold text-slate-600">{c.user_full_name}</span>
                          </td>
                          <td className="px-4 py-4 text-right text-slate-500 font-medium">
                            {fmtCurrency(s.opening_balance)}
                          </td>
                          <td className="px-4 py-4">
                            <div className="flex flex-wrap gap-2 justify-center">
                              <div className="flex flex-col items-center px-2 py-1 bg-slate-50 rounded-lg min-w-[70px]">
                                <span className="text-[8px] font-bold text-slate-400">DIN</span>
                                <span className="text-[10px] font-bold text-slate-700">{fmtCurrency(s.vendas_dinheiro)}</span>
                              </div>
                              <div className="flex flex-col items-center px-2 py-1 bg-blue-50 rounded-lg min-w-[70px]">
                                <span className="text-[8px] font-bold text-blue-400">PIX</span>
                                <span className="text-[10px] font-bold text-blue-700">{fmtCurrency(s.vendas_pix)}</span>
                              </div>
                              <div className="flex flex-col items-center px-2 py-1 bg-indigo-50 rounded-lg min-w-[70px]">
                                <span className="text-[8px] font-bold text-indigo-400">CARTÃO</span>
                                <span className="text-[10px] font-bold text-indigo-700">{fmtCurrency(s.vendas_debito + s.vendas_credito)}</span>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-4 text-right text-red-500 font-semibold">
                            {fmtCurrency(s.retiradas_total)}
                          </td>
                          <td className="px-4 py-4 text-right">
                            <p className="text-sm font-black text-slate-900">{fmtCurrency(s.saldo_geral)}</p>
                            <p className="text-[9px] text-slate-400 font-bold uppercase">{s.comandas_processadas} comandas</p>
                          </td>
                        </tr>
                      );
                    })}
                    {!closingsLoading && closings.length === 0 && (
                      <tr><td colSpan={6} className="px-4 py-16 text-center text-slate-400 italic">Nenhum fechamento registrado no período.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ══════════════════════════════════ ABA VENDAS PDV (NOVO) ══════════════════════════════════ */}
        {activeTab === 'pdv' && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex justify-between items-end gap-4">
              <div>
                <h3 className="text-2xl font-bold text-slate-800 tracking-tight">Histórico de Vendas PDV</h3>
                <p className="text-slate-500 text-sm">Registro permanente de todas as comandas finalizadas.</p>
              </div>
              <div className="flex gap-2 bg-white p-1 rounded-2xl border border-slate-200 shadow-sm">
                 <div className="flex items-center px-3 border-r border-slate-100">
                   <label className="text-[10px] font-bold text-slate-400 uppercase mr-2">De</label>
                   <input type="date" className="text-xs font-semibold focus:outline-none bg-transparent" value={pdvStart} onChange={e => setPdvStart(e.target.value)} />
                 </div>
                 <div className="flex items-center px-3">
                   <label className="text-[10px] font-bold text-slate-400 uppercase mr-2">Até</label>
                   <input type="date" className="text-xs font-semibold focus:outline-none bg-transparent" value={pdvEnd} onChange={e => setPdvEnd(e.target.value)} />
                 </div>
                 <button onClick={loadPdvSales} className="bg-blue-600 text-white p-2 rounded-xl hover:bg-blue-700 transition">
                   <Plus size={16} className="rotate-45" />
                 </button>
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600 text-[10px] uppercase font-bold tracking-wider">
                    <tr>
                      <th className="px-5 py-4 text-left">Horário</th>
                      <th className="px-5 py-4 text-left">Comanda/Mesa</th>
                      <th className="px-5 py-4 text-right">Subtotal</th>
                      <th className="px-5 py-4 text-right">Desconto</th>
                      <th className="px-5 py-4 text-right">Total Final</th>
                      <th className="px-5 py-4 text-center">Forma Pagto</th>
                      <th className="px-5 py-4 text-center">Ações</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {pdvLoading && <tr><td colSpan={7} className="px-5 py-12 text-center text-slate-400">Carregando histórico de vendas...</td></tr>}
                    {!pdvLoading && pdvSales.map(sale => (
                      <tr key={sale.id} className="hover:bg-slate-50/80 transition-colors cursor-pointer" onClick={() => viewSaleDetail(sale)}>
                        <td className="px-5 py-4">
                          <p className="font-bold text-slate-800">{new Date(sale.created_at).toLocaleDateString('pt-BR')}</p>
                          <p className="text-[10px] text-slate-400 font-mono uppercase">{new Date(sale.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</p>
                        </td>
                        <td className="px-5 py-4">
                          <span className="text-xs font-bold text-blue-700 bg-blue-50 px-2 py-1 rounded-lg">
                            {sale.comanda_identificador}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-right text-slate-500 line-through decoration-slate-300">
                          {fmtCurrency(sale.total_amount + (sale.discount || 0))}
                        </td>
                        <td className="px-5 py-4 text-right text-red-500 font-medium">
                          -{fmtCurrency(sale.discount || 0)}
                        </td>
                        <td className="px-5 py-4 text-right">
                          <span className="text-sm font-black text-slate-900">{fmtCurrency(sale.total_amount)}</span>
                        </td>
                        <td className="px-5 py-4 text-center">
                          {sale.payment_method ? (
                            <span className="text-[10px] font-black uppercase px-2 py-1 bg-emerald-50 text-emerald-700 rounded-md border border-emerald-100">
                              {sale.payment_method}
                            </span>
                          ) : (
                            <span className="text-[10px] font-bold uppercase px-2 py-1 bg-amber-50 text-amber-600 rounded-md">
                              LANÇ. QUARTO
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-4 text-center">
                           <button 
                             onClick={(e) => { e.stopPropagation(); viewSaleDetail(sale); }}
                             className="p-2 rounded-xl hover:bg-blue-50 text-blue-600 transition border border-transparent hover:border-blue-100"
                             title="Ver Detalhes do Consumo"
                           >
                              <FileText size={16} />
                           </button>
                        </td>
                      </tr>
                    ))}
                    {!pdvLoading && pdvSales.length === 0 && (
                      <tr><td colSpan={7} className="px-5 py-16 text-center text-slate-400 italic">Nenhuma venda registrada para este período.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ══════════════════════════════════ ABA RELATÓRIOS ══════════════════════════════════ */}
        {activeTab === 'relatorios' && (
          <div className="space-y-6 animate-in fade-in duration-500 max-w-2xl">
            <div className="flex justify-between items-end">
              <div>
                <h3 className="text-2xl font-black text-slate-800 tracking-tight">Relatórios Elite</h3>
                <p className="text-slate-500 text-sm">Gere documentos de padrão bancário para análise ou contabilidade.</p>
              </div>
              <div className="bg-blue-600/5 p-2 rounded-2xl border border-blue-100">
                <TrendingUp className="text-blue-600" size={24} />
              </div>
            </div>

            <div className="bg-white rounded-[2.5rem] shadow-sm border border-slate-200 overflow-hidden">
              <div className="bg-slate-900 p-8 text-white">
                <h4 className="font-bold text-xl mb-1">Configurar Exportação Profissional</h4>
                <p className="text-slate-400 text-xs">O documento será gerado seguindo as diretrizes visuais Qualitec.</p>
              </div>

              <div className="p-10 space-y-8">
                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Data de Início</label>
                    <input
                      type="date"
                      className={inputCls + " text-sm font-semibold py-3"}
                      value={exportConfig.start}
                      onChange={e => setExportConfig({ ...exportConfig, start: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Data de Término</label>
                    <input
                      type="date"
                      className={inputCls + " text-sm font-semibold py-3"}
                      value={exportConfig.end}
                      onChange={e => setExportConfig({ ...exportConfig, end: e.target.value })}
                    />
                  </div>
                </div>

                <div className="space-y-4">
                  <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Nível de Detalhamento</label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <button
                      onClick={() => setExportConfig({ ...exportConfig, mode: 'summary' })}
                      className={`p-5 rounded-3xl border-2 text-left transition-all relative overflow-hidden group ${exportConfig.mode === 'summary'
                          ? 'border-blue-600 bg-blue-50/50 shadow-md shadow-blue-50'
                          : 'border-slate-100 bg-slate-50/30 hover:border-slate-200 hover:bg-slate-50'
                        }`}
                    >
                      <div className="flex justify-between items-center mb-2">
                        <p className={`font-black text-sm ${exportConfig.mode === 'summary' ? 'text-blue-700' : 'text-slate-600'}`}>Resumido</p>
                        {exportConfig.mode === 'summary' && <CheckCircle size={18} className="text-blue-600" />}
                      </div>
                      <p className="text-[10px] text-slate-500 font-medium leading-relaxed">KPIs comparativos, gráficos de categoria e visão geral corporativa de saldo.</p>
                    </button>

                    <button
                      onClick={() => setExportConfig({ ...exportConfig, mode: 'full' })}
                      className={`p-5 rounded-3xl border-2 text-left transition-all relative overflow-hidden group ${exportConfig.mode === 'full'
                          ? 'border-blue-700 bg-blue-50/50 shadow-md shadow-blue-50'
                          : 'border-slate-100 bg-slate-50/30 hover:border-slate-200 hover:bg-slate-50'
                        }`}
                    >
                      <div className="flex justify-between items-center mb-2">
                        <p className={`font-black text-sm ${exportConfig.mode === 'full' ? 'text-blue-800' : 'text-slate-600'}`}>Completo</p>
                        {exportConfig.mode === 'full' && <CheckCircle size={18} className="text-blue-700" />}
                      </div>
                      <p className="text-[10px] text-slate-500 font-medium leading-relaxed">Inclui Extrato Analítico detalhado e Fluxo de Caixa Diário completo para auditoria.</p>
                    </button>
                  </div>
                </div>

                <div className="pt-6">
                  <button
                    onClick={async () => {
                      setMessage('Iniciando geração do PDF executivo... aguarde um instante.');
                      try {
                        const res = await api.get('/finance/reports/export', {
                          params: exportConfig,
                          responseType: 'blob'
                        });
                        const url = window.URL.createObjectURL(new Blob([res.data]));
                        const link = document.createElement('a');
                        link.href = url;
                        link.setAttribute('download', `Relatorio_Financeiro_${exportConfig.mode}_${new Date().toISOString().slice(0, 10)}.pdf`);
                        document.body.appendChild(link);
                        link.click();
                        setMessage('Relatório financeiro gerado e pronto para download!');
                      } catch {
                        setError('Falha ao processar relatório. Tente um período com mais transações.');
                      }
                    }}
                    className="w-full bg-blue-600 hover:bg-slate-900 text-white py-5 rounded-3xl font-black text-sm tracking-widest shadow-xl shadow-blue-100 transition-all flex items-center justify-center gap-3 active:scale-[0.98]"
                  >
                    📥 BAIXAR RELATÓRIO PDF
                  </button>
                </div>
              </div>
            </div>

            <div className="p-6 bg-blue-50/50 rounded-3xl border border-blue-100 flex items-start gap-4">
              <div className="bg-blue-600 text-white p-2 rounded-xl">
                <FileText size={20} />
              </div>
              <div>
                <p className="text-xs font-bold text-blue-900 uppercase tracking-tighter mb-1">Sistema Profissional ParcerIA</p>
                <p className="text-xs text-blue-700/80 leading-relaxed">Este relatório utiliza o motor Executive Engine v2 para garantir precisão e elegância bancária. Ideal para tomada de decisão estratégica.</p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Modais de Formulário ── */}

      {/* Modal Receitas */}
      {isRevModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl w-full max-w-xl shadow-2xl overflow-hidden border border-slate-200 animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                <Plus className="text-blue-600" size={20} />
                {editing ? `Editar Receita #${editing.id}` : 'Lançar Nova Receita'}
              </h3>
              <button onClick={closeFormModals} className="text-slate-400 hover:text-slate-600 p-2 hover:bg-slate-100 rounded-full transition-colors">
                <Plus size={24} className="rotate-45" />
              </button>
            </div>
            <form onSubmit={editing ? submitEdit : handleCreate} className="p-8 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="md:col-span-2">
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Descrição da Receita</label>
                  <input
                    placeholder="Ex: Diária quarto 101, Venda de refrigerante..."
                    required
                    className={inputCls + " text-lg py-3"}
                    value={editing ? editForm.description : form.description}
                    onChange={e => editing ? setEditForm({ ...editForm, description: e.target.value }) : setForm({ ...form, description: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Valor (R$)</label>
                  <input
                    type="number" step="0.01"
                    placeholder="0,00"
                    required
                    className={inputCls + " text-lg py-3 font-mono"}
                    value={editing ? editForm.amount : form.amount}
                    onChange={e => editing ? setEditForm({ ...editForm, amount: e.target.value }) : setForm({ ...form, amount: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Categoria</label>
                  <select
                    className={inputCls + " py-3"}
                    value={editing ? editForm.category : form.category}
                    onChange={e => editing ? setEditForm({ ...editForm, category: e.target.value as RevenueCategory }) : setForm({ ...form, category: e.target.value as RevenueCategory })}
                  >
                    <option value="hospedagem">Hospedagem</option>
                    <option value="consumo">Consumo</option>
                    <option value="outros">Outros</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Forma de Pagamento</label>
                  <select
                    className={inputCls + " py-3"}
                    value={editing ? editForm.payment_method : form.payment_method}
                    onChange={e => editing ? setEditForm({ ...editForm, payment_method: e.target.value as PaymentMethod }) : setForm({ ...form, payment_method: e.target.value as PaymentMethod })}
                  >
                    <option value="pix">PIX</option>
                    <option value="credito">Crédito</option>
                    <option value="debito">Débito</option>
                    <option value="dinheiro">Dinheiro</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Reserva Vinculada (Opcional)</label>
                  <input
                    type="number"
                    placeholder="ID da Reserva"
                    className={inputCls + " py-3"}
                    value={editing ? editForm.booking_id : form.booking_id}
                    onChange={e => editing ? setEditForm({ ...editForm, booking_id: e.target.value }) : setForm({ ...form, booking_id: e.target.value })}
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <button type="button" onClick={closeFormModals} className="flex-1 py-4 text-slate-600 font-bold hover:bg-slate-50 rounded-2xl transition-all border border-transparent hover:border-slate-200">
                  Cancelar
                </button>
                <button type="submit" className="flex-1 py-4 bg-blue-600 text-white font-bold rounded-2xl hover:bg-blue-700 transition-all shadow-lg shadow-blue-100">
                  {editing ? 'Salvar Alterações' : 'Lançar Receita'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Despesas */}
      {isExpModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl w-full max-w-xl shadow-2xl overflow-hidden border border-slate-200 animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                <Plus className="text-red-500" size={20} />
                {editingExp ? `Editar Despesa` : 'Lançar Nova Despesa'}
              </h3>
              <button onClick={closeFormModals} className="text-slate-400 hover:text-slate-600 p-2 hover:bg-slate-100 rounded-full transition-colors">
                <Plus size={24} className="rotate-45" />
              </button>
            </div>
            <form onSubmit={editingExp ? submitEditExp : createExpense} className="p-8 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="md:col-span-2">
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Descrição da Despesa</label>
                  <input
                    placeholder="Ex: Conta de Luz, Manutenção Ar Condicionado..."
                    required
                    className={inputCls + " text-lg py-3"}
                    value={expForm.description}
                    onChange={e => setExpForm({ ...expForm, description: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Valor (R$)</label>
                  <input
                    type="number" step="0.01"
                    placeholder="0,00"
                    required
                    className={inputCls + " text-lg py-3 font-mono"}
                    value={expForm.amount}
                    onChange={e => setExpForm({ ...expForm, amount: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Categoria</label>
                  <select
                    required
                    className={inputCls + " py-3"}
                    value={expForm.category}
                    onChange={e => setExpForm({ ...expForm, category: e.target.value as ExpenseCategory })}
                  >
                    {Object.entries(EXPENSE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Vencimento</label>
                  <input
                    type="date"
                    required
                    className={inputCls + " py-3"}
                    value={expForm.due_date}
                    onChange={e => setExpForm({ ...expForm, due_date: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Observações</label>
                  <input
                    placeholder="Opcional..."
                    className={inputCls + " py-3"}
                    value={expForm.notes || ''}
                    onChange={e => setExpForm({ ...expForm, notes: e.target.value })}
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <button type="button" onClick={closeFormModals} className="flex-1 py-4 text-slate-600 font-bold hover:bg-slate-50 rounded-2xl transition-all border border-transparent hover:border-slate-200">
                  Cancelar
                </button>
                <button type="submit" className="flex-1 py-4 bg-red-600 text-white font-bold rounded-2xl hover:bg-red-700 transition-all shadow-lg shadow-red-100">
                  {editingExp ? 'Salvar Alterações' : 'Lançar Despesa'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Exportação Elite */}
      {isExportModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="bg-gradient-to-r from-blue-700 to-indigo-800 p-6 text-white text-center">
              <h3 className="text-xl font-bold">Relatório Executivo Elite</h3>
              <p className="text-blue-100 text-xs mt-1">Gere um documento de padrão bancário para análise</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Início</label>
                  <input type="date" className={inputCls} value={exportConfig.start} onChange={e => setExportConfig({ ...exportConfig, start: e.target.value })} />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Fim</label>
                  <input type="date" className={inputCls} value={exportConfig.end} onChange={e => setExportConfig({ ...exportConfig, end: e.target.value })} />
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Nível de Detalhamento</label>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <button
                    onClick={() => setExportConfig({ ...exportConfig, mode: 'summary' })}
                    className={`p-3 rounded-xl border text-center transition ${exportConfig.mode === 'summary' ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-500'}`}
                  >
                    <p className="font-bold text-sm">Resumido</p>
                    <p className="text-[10px] opacity-70">KPIs e Gráficos</p>
                  </button>
                  <button
                    onClick={() => setExportConfig({ ...exportConfig, mode: 'full' })}
                    className={`p-3 rounded-xl border text-center transition ${exportConfig.mode === 'full' ? 'border-blue-600 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-50'}`}
                  >
                    <p className="font-bold text-sm">Completo</p>
                    <p className="text-[10px] opacity-70">Extrato + Fluxo</p>
                  </button>
                </div>
              </div>

              <div className="flex gap-2 pt-4">
                <button onClick={closeFormModals} className={btnSecondary + ' flex-1'}>Cancelar</button>
                <button
                  onClick={async () => {
                    setMessage('Gerando relatório... aguarde um instante.');
                    try {
                      // Usar window.location.origin + api.defaults.baseURL para construir a URL se necessário, 
                      // mas aqui vamos usar o axios com responseType blob
                      const res = await api.get('/finance/reports/export', {
                        params: exportConfig,
                        responseType: 'blob'
                      });
                      const url = window.URL.createObjectURL(new Blob([res.data]));
                      const link = document.createElement('a');
                      link.href = url;
                      link.setAttribute('download', `Relatorio_Financeiro_${exportConfig.mode}_${new Date().toISOString().slice(0, 10)}.pdf`);
                      document.body.appendChild(link);
                      link.click();
                      closeFormModals();
                    } catch { setError('Falha ao exportar PDF'); }
                  }}
                  className={btnPrimary + ' flex-1'}
                >
                  Download PDF
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Detalhes da Venda PDV */}
      {selectedSale && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
          <div className="bg-white rounded-[2.5rem] w-full max-w-2xl shadow-2xl overflow-hidden border border-slate-200 animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
            <div className="p-8 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <div>
                <h3 className="text-2xl font-black text-slate-800 tracking-tight flex items-center gap-3">
                  <div className="bg-blue-600 text-white p-2 rounded-2xl">
                    <FileText size={20} />
                  </div>
                  Detalhes da Comanda
                </h3>
                <p className="text-xs text-slate-400 mt-1 uppercase font-bold tracking-widest">{selectedSale.comanda_identificador} · Registro #{selectedSale.id}</p>
              </div>
              <button onClick={() => setSelectedSale(null)} className="text-slate-400 hover:text-slate-600 p-3 hover:bg-slate-100 rounded-2xl transition-all">
                <Plus size={24} className="rotate-45" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-8">
               <div className="bg-slate-50 rounded-3xl p-6 mb-8 border border-slate-200/60 flex justify-between items-center">
                  <div>
                    <p className="text-[10px] font-black text-slate-400 uppercase mb-1">Data do Consumo</p>
                    <p className="text-sm font-bold text-slate-700">{new Date(selectedSale.created_at).toLocaleString('pt-BR')}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] font-black text-slate-400 uppercase mb-1">Método de Pagamento</p>
                    <p className="text-sm font-bold text-emerald-600 uppercase">{selectedSale.payment_method || 'Lançado no Quarto'}</p>
                  </div>
               </div>

               <div className="space-y-4">
                  <p className="text-[10px] font-black text-slate-400 uppercase px-1 tracking-widest">Itens Consumidos/Serviços</p>
                  <div className="rounded-3xl border border-slate-100 overflow-hidden shadow-sm">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50/50 text-slate-500 text-[10px] uppercase font-bold border-b border-slate-100">
                        <tr>
                          <th className="px-4 py-3 text-left">Item Descrição</th>
                          <th className="px-4 py-3 text-center">Qtd</th>
                          <th className="px-4 py-3 text-right">Unitário</th>
                          <th className="px-4 py-3 text-right">Subtotal</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {selectedSale.items?.map(item => (
                          <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                            <td className="px-4 py-3 font-semibold text-slate-700">{item.product_name}</td>
                            <td className="px-4 py-3 text-center text-slate-500 font-medium">{item.quantity}</td>
                            <td className="px-4 py-3 text-right text-slate-500 font-mono">{fmtCurrency(item.unit_price)}</td>
                            <td className="px-4 py-3 text-right font-bold text-slate-800">{fmtCurrency(item.total_item)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
               </div>
            </div>

            <div className="p-8 bg-slate-900 text-white rounded-t-[3rem] shadow-[0_-20px_50px_rgba(0,0,0,0.1)]">
               <div className="space-y-3">
                  <div className="flex justify-between items-center opacity-60">
                    <span className="text-xs font-bold uppercase tracking-widest">Subtotal Acumulado</span>
                    <span className="font-mono text-sm">{fmtCurrency(selectedSale.total_amount + selectedSale.discount)}</span>
                  </div>
                  <div className="flex justify-between items-center text-red-400">
                    <span className="text-xs font-bold uppercase tracking-widest">Desconto Aplicado</span>
                    <span className="font-mono text-sm">-{fmtCurrency(selectedSale.discount)}</span>
                  </div>
                  <div className="h-px bg-white/10 my-4" />
                  <div className="flex justify-between items-end">
                    <div>
                      <p className="text-[10px] font-black text-blue-400 uppercase tracking-[0.2em] mb-1">Total da Venda</p>
                      <h4 className="text-4xl font-black">{fmtCurrency(selectedSale.total_amount)}</h4>
                    </div>
                    <button 
                      onClick={() => setSelectedSale(null)}
                      className="bg-white text-slate-900 px-8 py-3 rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-blue-400 hover:text-white transition-all shadow-xl shadow-black/20 active:scale-95"
                    >
                      Fechar Recibo
                    </button>
                  </div>
               </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
