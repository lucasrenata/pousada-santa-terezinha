import { useState, useEffect } from 'react';
import api from '@/services/api';

export interface DailySnapshot {
  date: string;
  // campos reais do backend /finance/daily-snapshot
  revenue_today: number;
  expense_today: number;
  net_today: number;
  occupancy_pct: number;       // backend usa occupancy_pct, não occupancy_rate
  total_rooms: number;
  occupied_rooms: number;
  available_rooms: number;
  guests_on_site: number;
  checkins_today: number;
  checkouts_today: number;
  avg_ticket: number;
  overdue_expenses: number;
  monthly_net: number;
}

const EMPTY_SNAPSHOT: DailySnapshot = {
  date: new Date().toISOString().slice(0, 10),
  revenue_today: 0,
  expense_today: 0,
  net_today: 0,
  occupancy_pct: 0,
  total_rooms: 0,
  occupied_rooms: 0,
  available_rooms: 0,
  guests_on_site: 0,
  checkins_today: 0,
  checkouts_today: 0,
  avg_ticket: 0,
  overdue_expenses: 0,
  monthly_net: 0,
};

export function useDailySnapshot() {
  const [snapshot, setSnapshot] = useState<DailySnapshot>(EMPTY_SNAPSHOT);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSnapshot = async () => {
    try {
      const response = await api.get('/finance/daily-snapshot');
      setSnapshot(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Erro ao buscar daily-snapshot:', err);
      setError(err?.message ?? 'Erro desconhecido');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSnapshot();
    // Atualiza a cada 60 segundos
    const interval = setInterval(fetchSnapshot, 60_000);
    return () => clearInterval(interval);
  }, []);

  return { snapshot, loading, error, refetch: fetchSnapshot };
}
