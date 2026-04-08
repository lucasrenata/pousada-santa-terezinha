import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { AlertTriangle, Calendar, User, Clock, CalendarDays, ArrowRight } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Tables } from '@/integrations/supabase/types';
import { isoToLocalDateIgnoringTZ } from '@/utils/dateCalculations';

type ReservationWithDetails = Tables<'reservations'> & {
  customers: Tables<'customers'>;
  rooms: Tables<'rooms'>;
};

interface ConflictInfo {
  type: 'total' | 'partial' | 'same_day';
  conflictingReservations: ReservationWithDetails[];
  message: string;
}

interface ConflictWarningDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conflictInfo: ConflictInfo | null;
  roomNumber: number;
  checkInDate: string;
  checkOutDate: string;
  onConfirm: () => void;
  onCancel: () => void;
  onSuggestDates?: (dates: { checkIn: Date; checkOut: Date }) => void;
  allowForceCreation?: boolean;
  suggestions?: Array<{
    checkIn: Date;
    checkOut: Date;
    reason: string;
  }>;
}

export function ConflictWarningDialog({
  open,
  onOpenChange,
  conflictInfo,
  roomNumber,
  checkInDate,
  checkOutDate,
  onConfirm,
  onCancel,
  onSuggestDates,
  allowForceCreation = false,
  suggestions = []
}: ConflictWarningDialogProps) {
  if (!conflictInfo) return null;

  const getConflictTypeInfo = (type: string) => {
    switch (type) {
      case 'total':
        return {
          title: 'Conflito Total de Datas',
          color: 'destructive',
          description: 'As datas selecionadas se sobrepõem completamente com outra reserva.'
        };
      case 'partial':
        return {
          title: 'Conflito Parcial de Datas',
          color: 'warning',
          description: 'As datas selecionadas se sobrepõem parcialmente com outra reserva.'
        };
      case 'same_day':
        return {
          title: 'Check-out e Check-in no Mesmo Dia',
          color: 'secondary',
          description: 'Existe um check-out no mesmo dia do seu check-in.'
        };
      default:
        return {
          title: 'Conflito de Reserva',
          color: 'destructive',
          description: 'Foi detectado um conflito com as datas selecionadas.'
        };
    }
  };

  const typeInfo = getConflictTypeInfo(conflictInfo.type);
  const isBlocking = conflictInfo.type === 'total' || 
    conflictInfo.conflictingReservations.some(r => r.status === 'confirmed' || r.status === 'checked_in');

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-2xl">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            {typeInfo.title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-base">
            {typeInfo.description}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-4">
          {/* Informações da nova reserva */}
          <Card className="p-4 bg-blue-50 border-blue-200">
            <h4 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              Nova Reserva
            </h4>
            <div className="text-sm text-blue-800">
              <p><strong>Quarto:</strong> {roomNumber}</p>
              <p><strong>Check-in:</strong> {format(isoToLocalDateIgnoringTZ(checkInDate), 'PPP', { locale: ptBR })}</p>
              <p><strong>Check-out:</strong> {format(isoToLocalDateIgnoringTZ(checkOutDate), 'PPP', { locale: ptBR })}</p>
            </div>
          </Card>

          {/* Reservas conflitantes */}
          <div>
            <h4 className="font-semibold mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Reservas Conflitantes ({conflictInfo.conflictingReservations.length})
            </h4>
            
            <div className="space-y-3 max-h-60 overflow-y-auto">
              {conflictInfo.conflictingReservations.map((reservation) => (
                <Card key={reservation.id} className="p-3 border-red-200 bg-red-50">
                  <div className="flex justify-between items-start">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-red-700" />
                        <span className="font-medium text-red-900">
                          {reservation.customers.name}
                        </span>
                        <Badge variant={
                          reservation.status === 'confirmed' ? 'default' :
                          reservation.status === 'checked_in' ? 'destructive' :
                          'secondary'
                        }>
                          {reservation.status === 'pending' ? 'Pendente' :
                           reservation.status === 'confirmed' ? 'Confirmada' :
                           reservation.status === 'checked_in' ? 'Check-in' :
                           reservation.status === 'checked_out' ? 'Check-out' :
                           'Cancelada'}
                        </Badge>
                      </div>
                      
                         <div className="text-sm text-red-700 flex items-center gap-4">
                           <div className="flex items-center gap-1">
                             <Clock className="h-3 w-3" />
                             <span>
                               {format(isoToLocalDateIgnoringTZ(reservation.check_in_date), 'dd/MM', { locale: ptBR })} 
                               {' - '}
                               {format(isoToLocalDateIgnoringTZ(reservation.check_out_date), 'dd/MM', { locale: ptBR })}
                             </span>
                           </div>
                           <span>{reservation.guests_count} hóspede{reservation.guests_count > 1 ? 's' : ''}</span>
                         </div>

                      {reservation.customers.phone && (
                        <p className="text-xs text-red-600">
                          📞 {reservation.customers.phone}
                        </p>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>

          {/* Mensagem do conflito */}
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
            <p className="text-sm text-amber-800">
              <AlertTriangle className="h-4 w-4 inline mr-1" />
              {conflictInfo.message}
            </p>
          </div>

          {/* Sugestões de datas alternativas */}
          {suggestions.length > 0 && (
            <div>
              <h4 className="font-semibold mb-3 flex items-center gap-2">
                <CalendarDays className="h-4 w-4 text-blue-600" />
                Datas Alternativas Sugeridas
              </h4>
              
              <div className="space-y-2">
                {suggestions.map((suggestion, index) => (
                  <Card key={index} className="p-3 border-blue-200 bg-blue-50 hover:bg-blue-100 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm">
                          <span className="font-medium text-blue-900">{suggestion.reason}</span>
                          <Badge variant="outline" className="text-blue-700 border-blue-300">
                            {Math.ceil((suggestion.checkOut.getTime() - suggestion.checkIn.getTime()) / (1000 * 60 * 60 * 24))} dias
                          </Badge>
                        </div>
                        <div className="text-sm text-blue-700 flex items-center gap-2">
                          <span>{format(suggestion.checkIn, 'dd/MM/yyyy', { locale: ptBR })}</span>
                          <ArrowRight className="h-3 w-3" />
                          <span>{format(suggestion.checkOut, 'dd/MM/yyyy', { locale: ptBR })}</span>
                        </div>
                      </div>
                      
                      {onSuggestDates && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-blue-700 border-blue-300 hover:bg-blue-200"
                          onClick={() => onSuggestDates({
                            checkIn: suggestion.checkIn,
                            checkOut: suggestion.checkOut
                          })}
                        >
                          Usar estas datas
                        </Button>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>

        <AlertDialogFooter className="flex-col sm:flex-row gap-2">
          <AlertDialogCancel onClick={onCancel}>
            Cancelar
          </AlertDialogCancel>
          
          {allowForceCreation && !isBlocking && (
            <AlertDialogAction 
              onClick={onConfirm}
              className="bg-amber-600 hover:bg-amber-700"
            >
              Criar Mesmo Assim
            </AlertDialogAction>
          )}
          
          {isBlocking && (
            <div className="text-sm text-red-600 font-medium">
              Não é possível criar esta reserva devido aos conflitos existentes.
            </div>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}