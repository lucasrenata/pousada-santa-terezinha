import React from 'react';
import { Bed, Users, TrendingUp, DollarSign, Trash2, Download, Package } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useRealTimeRooms } from '@/hooks/useRealTimeRooms';
import { useRealTimeActivities } from '@/hooks/useRealTimeActivities';
import { useRealTimeDailyRevenues } from '@/hooks/useRealTimeDailyRevenues';
import { formatCurrency } from '@/utils/dateCalculations';
import { supabase } from '@/integrations/supabase/client';
import { useToast } from '@/hooks/use-toast';

interface DashboardProps {
  onNavigate: (view: 'dashboard' | 'rooms' | 'inventory' | 'revenue') => void;
}

export function Dashboard({ onNavigate }: DashboardProps) {
  const { rooms, loading: roomsLoading } = useRealTimeRooms();
  const { activities, loading: activitiesLoading } = useRealTimeActivities();
  const { 
    revenues, 
    loading: revenuesLoading, 
    getTotalRevenue, 
    clearDailyRevenues, 
    downloadRevenues 
  } = useRealTimeDailyRevenues();
  const { toast } = useToast();

  // Calcular estatísticas dos quartos
  const totalRooms = rooms.length;
  const occupiedRooms = rooms.filter(room => room.status === 'occupied').length;
  const availableRooms = rooms.filter(room => room.status === 'available').length;
  const cleaningRooms = rooms.filter(room => room.status === 'cleaning').length;

  // Calcular total de hóspedes (soma do número de pessoas em todos os quartos ocupados)
  const totalGuests = rooms
    .filter(room => room.status === 'occupied')
    .reduce((sum, room) => sum + (room.guests_count || 0), 0);

  // Usar receita das receitas diárias
  const todayRevenue = getTotalRevenue();

  // Calcular taxa de ocupação
  const occupancyRate = totalRooms > 0 ? Math.round((occupiedRooms / totalRooms) * 100) : 0;

  // Função para limpar todas as atividades
  const handleClearActivities = async () => {
    try {
      const { error } = await supabase
        .from('activities')
        .delete()
        .neq('id', '00000000-0000-0000-0000-000000000000');

      if (error) {
        console.error('Erro ao limpar atividades:', error);
        toast({
          title: "Erro",
          description: "Não foi possível limpar as atividades.",
          variant: "destructive",
        });
        return;
      }

      toast({
        title: "Sucesso",
        description: "Todas as atividades foram removidas.",
      });
    } catch (error) {
      console.error('Erro ao limpar atividades:', error);
      toast({
        title: "Erro", 
        description: "Erro inesperado ao limpar atividades.",
        variant: "destructive",
      });
    }
  };

  // Função para limpar receitas diárias
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

  // Função para fazer download das receitas
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

  // Função para obter badge de status do quarto
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'available':
        return <Badge variant="available">Livre</Badge>;
      case 'occupied':
        return <Badge variant="occupied">Ocupado</Badge>;
      case 'cleaning':
        return <Badge variant="cleaning">Limpeza</Badge>;
      default:
        return <Badge variant="secondary">Desconhecido</Badge>;
    }
  };

  // Função para formatar tipo de atividade
  const getActivityBadge = (type: string) => {
    switch (type) {
      case 'checkin':
        return <Badge variant="success">Check-in</Badge>;
      case 'checkout':
        return <Badge variant="secondary">Check-out</Badge>;
      case 'cleaning':
        return <Badge variant="cleaning">Limpeza</Badge>;
      case 'inventory':
        return <Badge variant="warning">Estoque</Badge>;
      default:
        return <Badge variant="secondary">{type}</Badge>;
    }
  };

  // Função para formatar horário
  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };


  if (roomsLoading || revenuesLoading) {
    return (
      <div className="space-y-6">
        <div className="bg-gradient-card rounded-lg p-6 shadow-lg">
          <h2 className="text-2xl font-bold text-foreground mb-2">
            Bem-vindo ao Dashboard
          </h2>
          <p className="text-muted-foreground">
            Carregando dados da pousada...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div className="bg-gradient-card rounded-lg p-6 shadow-lg">
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Bem-vindo ao Dashboard
        </h2>
        <p className="text-muted-foreground">
          Visão geral das operações da pousada 
        </p>
      </div>

      {/* Stats Cards - Now 3 columns instead of 4 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Taxa de Ocupação</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{occupancyRate}%</div>
            <p className="text-xs text-muted-foreground">
              {occupiedRooms} de {totalRooms} quartos ocupados
            </p>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Quartos Disponíveis</CardTitle>
            <Bed className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-success">{availableRooms}</div>
            <p className="text-xs text-muted-foreground">
              {cleaningRooms} em limpeza
            </p>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Hóspedes Ativos</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalGuests}</div>
            <p className="text-xs text-muted-foreground">
              Hospedados atualmente
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Receita do Dia - with updated button */}
      <Card className="bg-gradient-card">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="h-5 w-5" />
              Receita do Dia
            </CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Baseado no histórico de receitas diárias
            </p>
          </div>
          <div className="flex gap-2">
            <Button 
              variant="outline" 
              size="sm"
              onClick={handleDownloadRevenues}
              className="flex items-center gap-2"
            >
              <Download className="h-4 w-4" />
              Baixar PDF
            </Button>
            <Button 
              variant="outline" 
              size="sm"
              onClick={handleClearRevenues}
              className="flex items-center gap-2"
            >
              <Trash2 className="h-4 w-4" />
              Limpar
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-success">
            {formatCurrency(todayRevenue)}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {revenues.length} {revenues.length === 1 ? 'receita registrada' : 'receitas registradas'}
          </p>
        </CardContent>
      </Card>

      {/* Quick Actions & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Ações Rápidas</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button 
              onClick={() => onNavigate('rooms')} 
              className="w-full justify-start"
              variant="outline"
            >
              <Bed className="mr-2 h-4 w-4" />
              Gerenciar Quartos
            </Button>
            <Button 
              onClick={() => onNavigate('inventory')} 
              className="w-full justify-start"
              variant="outline"
            >
              <Package className="mr-2 h-4 w-4" />
              Controlar Estoque
            </Button>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>Atividades Recentes</CardTitle>
            {activities.length > 0 && (
              <Button 
                variant="outline" 
                size="sm"
                onClick={handleClearActivities}
                className="flex items-center gap-2 text-destructive hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
                Limpar
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {activitiesLoading ? (
              <p className="text-muted-foreground">Carregando atividades...</p>
            ) : activities.length === 0 ? (
              <p className="text-muted-foreground">Nenhuma atividade recente</p>
            ) : (
              <div className="space-y-3">
                {activities.slice(0, 4).map((activity) => (
                  <div key={activity.id} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                    <div className="flex items-center space-x-3">
                      {getActivityBadge(activity.type)}
                      <span className="text-sm">{activity.message}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatTime(activity.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Room Status Overview */}
      <Card>
        <CardHeader>
          <CardTitle>Status dos Quartos</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 sm:grid-cols-6 lg:grid-cols-9 gap-3">
            {rooms.map((room) => (
              <div
                key={room.id}
                className={`aspect-square rounded-lg border-2 p-2 text-center transition-all hover:shadow-md cursor-pointer ${
                  room.status === 'occupied'
                    ? 'border-destructive bg-destructive/10 hover:bg-destructive/20' 
                    : room.status === 'cleaning'
                    ? 'border-warning bg-warning/10 hover:bg-warning/20'
                    : 'border-success bg-success/10 hover:bg-success/20'
                }`}
                onClick={() => window.location.href = `/quartos/${room.id}`}
              >
                <div className="text-sm font-semibold">{room.id}</div>
                <div className="mt-1">
                  {getStatusBadge(room.status)}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
