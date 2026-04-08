import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, Filter, CalendarDays, Calendar, Users, BarChart3, TrendingUp, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { useReservations, Reservation } from '@/hooks/useReservations';
import api from '@/services/api';
import { ReservationCard } from '@/components/ReservationCard';
import { ReservationForm } from '@/components/ReservationForm';
import { ReservationCalendar } from '@/components/ReservationCalendar';
import { CustomerSearchModal } from '@/components/CustomerSearchModal';

const formatCurrency = (val: number) => 
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);

export default function Reservations() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showForm, setShowForm] = useState(false);
  const [showCustomerSearch, setShowCustomerSearch] = useState(false);
  const [editingReservation, setEditingReservation] = useState<Reservation | null>(null);
  const [deletingReservation, setDeletingReservation] = useState<Reservation | null>(null);
  
  const { reservations, loading, deleteReservation, updateReservation } = useReservations();
  const { toast } = useToast();
  const navigate = useNavigate();

  // Filter reservations
  const filteredReservations = useMemo(() => {
    return reservations.filter((reservation: Reservation) => {
      const matchesSearch = searchQuery === '' || 
        reservation.guest_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (reservation.room_number && reservation.room_number.includes(searchQuery));
      
      const matchesStatus = statusFilter === 'all' || reservation.status === statusFilter;
      
      return matchesSearch && matchesStatus;
    });
  }, [reservations, searchQuery, statusFilter]);

  // Get statistics
  const stats = useMemo(() => {
    const total = reservations.length;
    const pending = reservations.filter((r: Reservation) => r.status === 'pendente').length;
    const confirmed = reservations.filter((r: Reservation) => r.status === 'confirmado').length;
    const checkedIn = reservations.filter((r: Reservation) => r.status === 'ativo').length;
    const revenue = reservations
      .filter((r: Reservation) => r.status !== 'cancelado')
      .reduce((sum: number, r: Reservation) => sum + Number(r.total_amount), 0);
    
    return { total, pending, confirmed, checkedIn, revenue };
  }, [reservations]);

  const handleEditReservation = (reservation: Reservation) => {
    setEditingReservation(reservation);
    setShowForm(true);
  };

  const handleDeleteReservation = async () => {
    if (!deletingReservation) return;
    try {
      await deleteReservation(deletingReservation.id);
      toast({ title: "Sucesso", description: "Reserva excluída permanentemente." });
    } catch (error) {
      toast({ title: "Erro", description: "Não foi possível excluir a reserva.", variant: "destructive" });
    } finally {
      setDeletingReservation(null);
    }
  };

  const handleCheckIn = async (reservation: Reservation) => {
    try {
      if (!reservation.room_id) {
        toast({ title: "Erro", description: "Atribua um quarto antes do check-in.", variant: "destructive" });
        return;
      }
      await api.post('/bookings/checkin', { booking_id: reservation.id, room_id: reservation.room_id });
      // Call updateReservation just to refresh locally, or window.location.reload()
      await updateReservation(reservation.id, { status: 'ativo' });
      toast({ title: "Check-in realizado!", description: "O hóspede agora está com status ATIVO." });
    } catch (error: any) {
      toast({ title: "Erro", description: error.response?.data?.detail || "Falha ao realizar check-in.", variant: "destructive" });
    }
  };

  const handleCheckOut = async (reservation: Reservation) => {
    try {
      if (!reservation.room_id) return;
      await api.post(`/bookings/checkout/${reservation.room_id}`, { payment_method: 'pix' });
      await updateReservation(reservation.id, { status: 'concluido' });
      toast({ title: "Check-out realizado!", description: "Reserva finalizada com sucesso. Receita registrada e quarto em Limpeza." });
    } catch (error: any) {
      toast({ title: "Erro", description: error.response?.data?.detail || "Falha ao realizar check-out.", variant: "destructive" });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-2">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-medium text-slate-500">Sincronizando reservas...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4 sm:p-8 space-y-8 animate-in fade-in duration-500">
      {/* Header Profissional */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-4xl font-black text-slate-900 tracking-tight">Reservas</h1>
          <p className="text-slate-500 font-medium">Controle central de estadias e ocupação</p>
        </div>
        <div className="flex gap-3 w-full sm:w-auto">
          <Button 
            onClick={() => setShowCustomerSearch(true)} 
            variant="outline" 
            className="flex-1 sm:flex-none gap-2 font-bold border-slate-200"
          >
            <Users className="h-4 w-4" />
            Hóspedes
          </Button>
          <Button 
            onClick={() => navigate('/bookings/new')} 
            className="flex-1 sm:flex-none gap-2 font-bold bg-blue-600 hover:bg-blue-700 shadow-lg shadow-blue-200"
          >
            <Plus className="h-4 w-4" />
            Nova Reserva
          </Button>
        </div>
      </div>

      {/* Grid de Estatísticas Premium */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
         {[
           { label: 'Total', value: stats.total, color: 'text-slate-900', icon: BarChart3 },
           { label: 'Pendentes', value: stats.pending, color: 'text-yellow-600', icon: Clock },
           { label: 'Confirmadas', value: stats.confirmed, color: 'text-blue-600', icon: Calendar },
           { label: 'Check-ins', value: stats.checkedIn, color: 'text-green-600', icon: TrendingUp },
         ].map((stat, i) => (
           <Card key={i} className="border-none shadow-sm bg-white overflow-hidden group">
             <div className="p-5 flex items-center justify-between">
               <div>
                 <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">{stat.label}</p>
                 <p className={`text-3xl font-black ${stat.color}`}>{stat.value}</p>
               </div>
               <stat.icon className="h-8 w-8 text-slate-100 group-hover:text-slate-200 transition-colors" />
             </div>
           </Card>
         ))}

         <Card className="border-none shadow-sm bg-slate-900 text-white lg:col-span-1">
           <div className="p-5">
             <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">Receita Prevista</p>
             <p className="text-2xl font-black">{formatCurrency(stats.revenue)}</p>
           </div>
         </Card>
      </div>

      {/* Barra de Busca e Filtros */}
      <Card className="border-slate-200 shadow-sm bg-white/50 backdrop-blur-sm">
        <CardContent className="p-4 sm:p-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 h-4 w-4" />
              <Input
                placeholder="Buscar por nome do hóspede ou número do quarto..."
                value={searchQuery}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                className="pl-10 h-11 border-slate-200 focus-visible:ring-blue-500"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full md:w-56 h-11 font-medium bg-white border-slate-200">
                <SelectValue placeholder="Todos os Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os Status</SelectItem>
                <SelectItem value="pendente">Pendentes</SelectItem>
                <SelectItem value="confirmado">Confirmadas</SelectItem>
                <SelectItem value="ativo">Em Estadia (Check-in)</SelectItem>
                <SelectItem value="concluido">Concluídas</SelectItem>
                <SelectItem value="cancelado">Canceladas</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Tabs de Visualização */}
      <Tabs defaultValue="list" className="w-full space-y-6">
        <div className="flex justify-between items-center">
          <TabsList className="bg-slate-100 p-1">
            <TabsTrigger value="list" className="gap-2 font-bold data-[state=active]:bg-white data-[state=active]:text-blue-600">
              <CalendarDays className="h-4 w-4" />
              Lista de Cards
            </TabsTrigger>
            <TabsTrigger value="calendar" className="gap-2 font-bold data-[state=active]:bg-white data-[state=active]:text-blue-600">
              <Calendar className="h-4 w-4" />
              Calendário Interativo
            </TabsTrigger>
          </TabsList>
          <div className="text-xs font-bold text-slate-400 uppercase hidden sm:block">
            {filteredReservations.length} resultados encontrados
          </div>
        </div>

        <TabsContent value="list" className="animate-in slide-in-from-bottom-2 duration-300">
          {filteredReservations.length === 0 ? (
            <Card className="border-dashed border-2 bg-transparent">
              <CardContent className="flex flex-col items-center justify-center py-20 text-center opacity-30">
                <CalendarDays size={64} className="mb-4" />
                <h3 className="text-xl font-bold">Nenhuma reserva localizada</h3>
                <p className="max-w-xs">Tente ajustar seus filtros ou crie uma nova reserva.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {filteredReservations.map((reservation: Reservation) => (
                <ReservationCard
                  key={reservation.id}
                  reservation={reservation}
                  onEdit={handleEditReservation}
                  onDelete={(res: Reservation) => setDeletingReservation(res)}
                  onCheckIn={handleCheckIn}
                  onCheckOut={handleCheckOut}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="calendar" className="animate-in zoom-in-95 duration-300">
          <ReservationCalendar />
        </TabsContent>
      </Tabs>

      {/* Diálogo do Formulário (Nova/Editar) */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-slate-50 sm:rounded-3xl p-6 sm:p-10 shadow-2xl border-none">
          <ReservationForm
            reservation={editingReservation}
            onSuccess={() => { setShowForm(false); window.location.reload(); }}
            onCancel={() => setShowForm(false)}
          />
        </DialogContent>
      </Dialog>


      {/* Confirmação de Exclusão */}
      <AlertDialog open={!!deletingReservation} onOpenChange={() => setDeletingReservation(null)}>
        <AlertDialogContent className="rounded-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-xl font-black">Confirmar Exclusão</AlertDialogTitle>
            <AlertDialogDescription className="font-medium text-slate-500">
              Deseja realmente remover a reserva de <span className="text-slate-900 font-bold">{deletingReservation?.guest_name}</span>?
              Esta operação não poderá ser revertida.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2">
            <AlertDialogCancel className="font-bold border-none bg-slate-100 hover:bg-slate-200">Voltar</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteReservation} className="bg-red-600 hover:bg-red-700 font-bold">Sim, Excluir</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Modal de Busca de Hóspedes */}
      <CustomerSearchModal
        open={showCustomerSearch}
        onOpenChange={setShowCustomerSearch}
      />
    </div>
  );
}