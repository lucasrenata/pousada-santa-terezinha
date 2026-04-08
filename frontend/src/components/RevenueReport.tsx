
import React from 'react';
import { ArrowLeft, Download, Trash2, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useRealTimeDailyRevenues, PeriodFilter } from '@/hooks/useRealTimeDailyRevenues';
import { formatCurrency } from '@/utils/dateCalculations';
import { useToast } from '@/hooks/use-toast';

interface RevenueReportProps {
  onNavigate: (view: 'dashboard' | 'rooms' | 'inventory' | 'revenue') => void;
}

export function RevenueReport({ onNavigate }: RevenueReportProps) {
  const { 
    revenues, 
    loading, 
    periodFilter,
    getTotalRevenue, 
    getActiveRevenues, 
    getCompletedRevenues, 
    clearDailyRevenues, 
    downloadRevenues,
    changePeriodFilter
  } = useRealTimeDailyRevenues();
  const { toast } = useToast();

  const totalRevenue = getTotalRevenue();
  const activeRevenues = getActiveRevenues();
  const completedRevenues = getCompletedRevenues();

  const handleClearRevenues = async () => {
    if (revenues.length === 0) {
      toast({
        title: "Aviso",
        description: "Não há receitas para limpar.",
      });
      return;
    }

    try {
      await clearDailyRevenues();
    } catch (error) {
      console.error('Erro ao limpar receitas:', error);
    }
  };

  const handleDownloadRevenues = () => {
    if (revenues.length === 0) {
      toast({
        title: "Aviso",
        description: "Não há receitas para fazer download.",
      });
      return;
    }

    downloadRevenues();
  };

  const handlePeriodChange = (value: PeriodFilter) => {
    changePeriodFilter(value);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button 
            variant="outline" 
            onClick={() => onNavigate('dashboard')}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Voltar ao Dashboard
          </Button>
        </div>
        <Card>
          <CardContent className="p-6">
            <p className="text-muted-foreground">Carregando dados de receitas...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button 
            variant="outline" 
            onClick={() => onNavigate('dashboard')}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Voltar ao Dashboard
          </Button>
          <div>
            <h2 className="text-2xl font-bold">Relatório de Receitas</h2>
            <p className="text-muted-foreground">
              {periodFilter === 'today' ? 'Receitas do dia atual' : 'Receitas da última semana'}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Select value={periodFilter} onValueChange={handlePeriodChange}>
            <SelectTrigger className="w-[140px]">
              <Calendar className="h-4 w-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="today">Hoje</SelectItem>
              <SelectItem value="week">Semana</SelectItem>
            </SelectContent>
          </Select>
          <Button 
            variant="outline" 
            onClick={handleDownloadRevenues}
            className="flex items-center gap-2"
            disabled={revenues.length === 0}
          >
            <Download className="h-4 w-4" />
            Baixar PDF
          </Button>
          <Button 
            variant="outline" 
            onClick={handleClearRevenues}
            className="flex items-center gap-2"
            disabled={revenues.length === 0}
          >
            <Trash2 className="h-4 w-4" />
            Limpar Receitas
          </Button>
        </div>
      </div>

      {/* Total Revenue Card */}
      <Card className="bg-gradient-card">
        <CardHeader>
          <CardTitle className="text-lg">
            {periodFilter === 'today' ? 'Receita Total do Dia' : 'Receita Total da Semana'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-success">
            {formatCurrency(totalRevenue)}
          </div>
          <p className="text-muted-foreground mt-1">
            {revenues.length} {revenues.length === 1 ? 'receita registrada' : 'receitas registradas'}
          </p>
          {periodFilter === 'today' && (
            <div className="flex gap-4 mt-3 text-sm">
              <span className="text-muted-foreground">
                Ativas: {activeRevenues.length}
              </span>
              <span className="text-muted-foreground">
                Finalizadas: {completedRevenues.length}
              </span>
            </div>
          )}
          {periodFilter === 'week' && (
            <div className="mt-3 text-sm text-muted-foreground">
              Receitas finalizadas nos últimos 7 dias
            </div>
          )}
        </CardContent>
      </Card>

      {/* Receitas Ativas - Apenas para visão diária */}
      {periodFilter === 'today' && activeRevenues.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Receitas Ativas (Hóspedes Atuais)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {activeRevenues.map((revenue) => (
                <div 
                  key={revenue.id} 
                  className="flex items-center justify-between p-4 rounded-lg border bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-semibold text-lg">Quarto {revenue.room_id}</span>
                      <Badge variant="success">Ativo</Badge>
                      {revenue.guest_name && (
                        <span className="text-muted-foreground">• {revenue.guest_name}</span>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <div className="flex gap-4">
                        <span>{revenue.guests_count} {revenue.guests_count === 1 ? 'pessoa' : 'pessoas'}</span>
                        <span>•</span>
                        <span>{formatCurrency(revenue.daily_rate)} por pessoa/dia</span>
                      </div>
                      <div>
                        {revenue.days_stayed} {revenue.days_stayed === 1 ? 'dia' : 'dias'} de hospedagem
                      </div>
                      {revenue.check_in_date && (
                        <div>
                          Check-in: {new Date(revenue.check_in_date).toLocaleDateString('pt-BR')}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-bold text-green-600">
                      {formatCurrency(revenue.total_amount)}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatCurrency(revenue.daily_rate)} × {revenue.guests_count} × {revenue.days_stayed}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Receitas Finalizadas */}
      {completedRevenues.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>
              {periodFilter === 'today' ? 'Receitas Finalizadas (Check-outs do Dia)' : 'Receitas Finalizadas da Semana'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {completedRevenues.map((revenue) => (
                <div 
                  key={revenue.id} 
                  className="flex items-center justify-between p-4 rounded-lg border bg-muted/20"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-semibold text-lg">Quarto {revenue.room_id}</span>
                      <Badge variant="secondary">Finalizado</Badge>
                      {revenue.guest_name && (
                        <span className="text-muted-foreground">• {revenue.guest_name}</span>
                      )}
                      <span className="text-xs text-muted-foreground">
                        • {new Date(revenue.date).toLocaleDateString('pt-BR')}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <div className="flex gap-4">
                        <span>{revenue.guests_count} {revenue.guests_count === 1 ? 'pessoa' : 'pessoas'}</span>
                        <span>•</span>
                        <span>{formatCurrency(revenue.daily_rate)} por pessoa/dia</span>
                      </div>
                      <div>
                        {revenue.days_stayed} {revenue.days_stayed === 1 ? 'dia' : 'dias'} de hospedagem
                      </div>
                      <div className="flex gap-4">
                        {revenue.check_in_date && (
                          <span>
                            Check-in: {new Date(revenue.check_in_date).toLocaleDateString('pt-BR')}
                          </span>
                        )}
                        {revenue.check_out_date && (
                          <span>
                            Check-out: {new Date(revenue.check_out_date).toLocaleDateString('pt-BR')}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl font-bold">
                      {formatCurrency(revenue.total_amount)}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatCurrency(revenue.daily_rate)} × {revenue.guests_count} × {revenue.days_stayed}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {revenues.length === 0 && (
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-muted-foreground">
              {periodFilter === 'today' 
                ? 'Nenhuma receita registrada para hoje'
                : 'Nenhuma receita finalizada na última semana'
              }
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
