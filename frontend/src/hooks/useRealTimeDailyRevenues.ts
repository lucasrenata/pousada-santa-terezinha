
import { useState, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useToast } from '@/hooks/use-toast';

export interface DailyRevenue {
  id: string;
  date: string;
  room_id: number;
  guest_name: string | null;
  guests_count: number;
  daily_rate: number;
  days_stayed: number;
  total_amount: number;
  check_in_date: string | null;
  check_out_date: string | null;
  status: 'active' | 'completed';
  created_at: string;
  updated_at: string;
}

export type PeriodFilter = 'today' | 'week';

export function useRealTimeDailyRevenues() {
  const [revenues, setRevenues] = useState<DailyRevenue[]>([]);
  const [loading, setLoading] = useState(true);
  const [periodFilter, setPeriodFilter] = useState<PeriodFilter>('today');
  const { toast } = useToast();

  const fetchRevenues = async (period: PeriodFilter = periodFilter) => {
    try {
      let query = supabase.from('daily_revenues').select('*');
      
      if (period === 'today') {
        query = query.eq('date', new Date().toISOString().split('T')[0]);
      } else if (period === 'week') {
        const today = new Date();
        const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
        query = query
          .gte('date', weekAgo.toISOString().split('T')[0])
          .lte('date', today.toISOString().split('T')[0])
          .eq('status', 'completed'); // Apenas receitas finalizadas na visão semanal
      }
      
      const { data, error } = await query.order('created_at', { ascending: false });

      if (error) {
        console.error('Erro ao carregar receitas diárias:', error);
        toast({
          title: "Erro",
          description: "Não foi possível carregar as receitas diárias",
          variant: "destructive",
        });
        return;
      }

      const typedRevenues = (data || []).map(revenue => ({
        ...revenue,
        status: revenue.status as 'active' | 'completed'
      })) as DailyRevenue[];

      setRevenues(typedRevenues);
    } catch (error) {
      console.error('Erro ao buscar receitas diárias:', error);
    } finally {
      setLoading(false);
    }
  };

  const clearDailyRevenues = async () => {
    try {
      let query = supabase.from('daily_revenues').delete();
      
      if (periodFilter === 'today') {
        query = query.eq('date', new Date().toISOString().split('T')[0]);
      } else {
        const today = new Date();
        const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
        query = query
          .gte('date', weekAgo.toISOString().split('T')[0])
          .lte('date', today.toISOString().split('T')[0]);
      }

      const { error } = await query;

      if (error) {
        console.error('Erro ao limpar receitas diárias:', error);
        toast({
          title: "Erro",
          description: "Não foi possível limpar as receitas diárias",
          variant: "destructive",
        });
        return;
      }

      toast({
        title: "Sucesso",
        description: `Receitas ${periodFilter === 'today' ? 'do dia' : 'da semana'} foram removidas com sucesso`,
      });
    } catch (error) {
      console.error('Erro ao limpar receitas diárias:', error);
      toast({
        title: "Erro",
        description: "Erro inesperado ao limpar receitas diárias",
        variant: "destructive",
      });
    }
  };

  const downloadRevenues = () => {
    try {
      import('jspdf').then((jsPDFModule) => {
        const jsPDF = (jsPDFModule as any).default || jsPDFModule.jsPDF;
        const doc = new jsPDF();
        const today = new Date();
        const totalRevenue = getTotalRevenue();
        
        // Configurar fonte
        doc.setFont('helvetica');
        
        // Título baseado no período
        doc.setFontSize(20);
        const title = periodFilter === 'today' ? 'Relatório de Receitas Diárias' : 'Relatório de Receitas Semanais';
        doc.text(title, 105, 20, { align: 'center' });
        
        // Data/Período
        doc.setFontSize(12);
        if (periodFilter === 'today') {
          doc.text(`Data: ${today.toLocaleDateString('pt-BR')}`, 20, 35);
        } else {
          const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
          doc.text(`Período: ${weekAgo.toLocaleDateString('pt-BR')} a ${today.toLocaleDateString('pt-BR')}`, 20, 35);
        }
        
        // Resumo
        doc.setFontSize(14);
        doc.text('Resumo:', 20, 50);
        doc.setFontSize(11);
        doc.text(`Total de Receitas: ${revenues.length}`, 20, 60);
        
        if (periodFilter === 'today') {
          doc.text(`Receitas Ativas: ${getActiveRevenues().length}`, 20, 68);
          doc.text(`Receitas Finalizadas: ${getCompletedRevenues().length}`, 20, 76);
        } else {
          doc.text(`Receitas Finalizadas na Semana: ${revenues.length}`, 20, 68);
        }
        
        doc.setFontSize(12);
        doc.text(`Receita Total: R$ ${totalRevenue.toFixed(2).replace('.', ',')}`, 20, 88);
        
        // Cabeçalho da tabela
        let y = 105;
        doc.setFontSize(10);
        doc.text('Data', 15, y);
        doc.text('Quarto', 35, y);
        doc.text('Hóspede', 55, y);
        doc.text('Pessoas', 85, y);
        doc.text('Diária', 105, y);
        doc.text('Dias', 125, y);
        doc.text('Total', 140, y);
        doc.text('Status', 165, y);
        
        // Linha separadora
        y += 5;
        doc.line(15, y, 190, y);
        y += 8;
        
        // Dados das receitas
        revenues.forEach((revenue) => {
          if (y > 270) { // Nova página se necessário
            doc.addPage();
            y = 20;
          }
          
          doc.text(`${new Date(revenue.date).toLocaleDateString('pt-BR')}`, 15, y);
          doc.text(`${revenue.room_id}`, 35, y);
          doc.text(`${revenue.guest_name || '-'}`, 55, y);
          doc.text(`${revenue.guests_count}`, 85, y);
          doc.text(`R$ ${revenue.daily_rate.toFixed(2).replace('.', ',')}`, 105, y);
          doc.text(`${revenue.days_stayed}`, 125, y);
          doc.text(`R$ ${revenue.total_amount.toFixed(2).replace('.', ',')}`, 140, y);
          doc.text(`${revenue.status === 'active' ? 'Ativo' : 'Finalizado'}`, 165, y);
          
          y += 8;
        });
        
        // Rodapé
        const pageCount = doc.getNumberOfPages();
        for (let i = 1; i <= pageCount; i++) {
          doc.setPage(i);
          doc.setFontSize(8);
          doc.text(`Página ${i} de ${pageCount}`, 190, 290, { align: 'right' });
          doc.text(`Gerado em: ${new Date().toLocaleString('pt-BR')}`, 20, 290);
        }
        
        // Download
        const fileName = periodFilter === 'today' 
          ? `receitas_${new Date().toISOString().split('T')[0]}.pdf`
          : `receitas_semana_${new Date().toISOString().split('T')[0]}.pdf`;
        doc.save(fileName);
        
        toast({
          title: "Download iniciado",
          description: "O relatório PDF foi baixado com sucesso",
        });
      });
    } catch (error) {
      console.error('Erro ao fazer download:', error);
      toast({
        title: "Erro",
        description: "Erro ao fazer download do relatório PDF",
        variant: "destructive",
      });
    }
  };

  const getTotalRevenue = () => {
    return revenues.reduce((sum, revenue) => sum + Number(revenue.total_amount), 0);
  };

  const getActiveRevenues = () => {
    return revenues.filter(revenue => revenue.status === 'active');
  };

  const getCompletedRevenues = () => {
    return revenues.filter(revenue => revenue.status === 'completed');
  };

  const changePeriodFilter = (newPeriod: PeriodFilter) => {
    setPeriodFilter(newPeriod);
    setLoading(true);
    fetchRevenues(newPeriod);
  };

  useEffect(() => {
    fetchRevenues();

    const channel = supabase
      .channel('daily-revenues-changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'daily_revenues'
        },
        (payload) => {
          console.log('Daily revenue update:', payload);
          fetchRevenues();
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return {
    revenues,
    loading,
    periodFilter,
    clearDailyRevenues,
    downloadRevenues,
    getTotalRevenue,
    getActiveRevenues,
    getCompletedRevenues,
    changePeriodFilter,
    refreshRevenues: fetchRevenues
  };
}
