import React from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Calendar, CheckCircle, AlertCircle, Clock, Users, Home } from 'lucide-react';

interface RoomInfo {
  roomType: 'privativo' | 'comunitario';
  maxCapacity: number;
  occupiedBeds: number;
  availableBeds: number;
}

interface AvailabilityIndicatorProps {
  isChecking: boolean;
  isAvailable: boolean;
  conflictInfo: any;
  suggestions: Array<{
    checkIn: Date;
    checkOut: Date;
    reason: string;
  }>;
  roomInfo?: RoomInfo | null;
  guestsCount?: number;
}

export function AvailabilityIndicator({ 
  isChecking, 
  isAvailable, 
  conflictInfo, 
  suggestions,
  roomInfo,
  guestsCount = 1
}: AvailabilityIndicatorProps) {
  if (isChecking) {
    return (
      <Alert>
        <Clock className="h-4 w-4" />
        <AlertDescription>
          Verificando disponibilidade...
        </AlertDescription>
      </Alert>
    );
  }

  // Mostrar informações do quarto comunitário
  if (roomInfo && roomInfo.roomType === 'comunitario') {
    const hasEnoughBeds = roomInfo.availableBeds >= guestsCount;
    
    return (
      <div className="space-y-3">
        {/* Info do quarto comunitário */}
        <Alert className={hasEnoughBeds ? "border-blue-200 bg-blue-50" : "border-orange-200 bg-orange-50"}>
          <Users className="h-4 w-4" />
          <AlertDescription>
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="bg-blue-100 text-blue-800">
                  <Home className="h-3 w-3 mr-1" />
                  Quarto Comunitário
                </Badge>
                <span className="text-sm">
                  Capacidade: {roomInfo.maxCapacity} camas
                </span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <span>
                  🛏️ <strong>{roomInfo.availableBeds}</strong> vaga(s) disponível(eis)
                </span>
                {roomInfo.occupiedBeds > 0 && (
                  <span className="text-muted-foreground">
                    ({roomInfo.occupiedBeds} ocupada(s))
                  </span>
                )}
              </div>
              {!hasEnoughBeds && (
                <span className="text-orange-700 font-medium">
                  ⚠️ Vagas insuficientes para {guestsCount} hóspede(s)
                </span>
              )}
              {hasEnoughBeds && isAvailable && (
                <span className="text-green-700 font-medium">
                  ✅ Há vagas para {guestsCount} hóspede(s)
                </span>
              )}
            </div>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  // Quarto privativo disponível
  if (isAvailable) {
    return (
      <Alert className="border-green-200 bg-green-50">
        <CheckCircle className="h-4 w-4 text-green-600" />
        <AlertDescription className="text-green-800">
          <div className="flex items-center gap-2">
            {roomInfo?.roomType === 'privativo' && (
              <Badge variant="secondary" className="bg-green-100 text-green-800">
                <Home className="h-3 w-3 mr-1" />
                Quarto Privativo
              </Badge>
            )}
            Quarto disponível no período selecionado
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  if (conflictInfo) {
    const getConflictColor = (type: string) => {
      switch (type) {
        case 'total':
          return 'destructive';
        case 'partial':
          return 'destructive';
        case 'same_day':
          return 'secondary';
        default:
          return 'secondary';
      }
    };

    const getConflictText = (type: string) => {
      switch (type) {
        case 'total':
          return 'Conflito Total';
        case 'partial':
          return 'Conflito Parcial';
        case 'same_day':
          return 'Mesmo Dia';
        default:
          return 'Conflito';
      }
    };

    return (
      <div className="space-y-3">
        <Alert variant={getConflictColor(conflictInfo.type) as any}>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <div className="flex items-center justify-between">
              <span>{conflictInfo.message}</span>
              <Badge variant={getConflictColor(conflictInfo.type) as any}>
                {getConflictText(conflictInfo.type)}
              </Badge>
            </div>
          </AlertDescription>
        </Alert>

        {suggestions.length > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="h-4 w-4 text-blue-600" />
              <span className="text-sm font-medium text-blue-800">
                Datas alternativas sugeridas:
              </span>
            </div>
            <div className="space-y-1">
              {suggestions.map((suggestion, index) => (
                <div key={index} className="text-xs text-blue-700 bg-white rounded px-2 py-1">
                  <span className="font-medium">{suggestion.reason}:</span>{' '}
                  {suggestion.checkIn.toLocaleDateString('pt-BR')} até{' '}
                  {suggestion.checkOut.toLocaleDateString('pt-BR')}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return null;
}
