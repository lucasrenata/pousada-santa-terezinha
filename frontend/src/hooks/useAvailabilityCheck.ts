import { useState, useCallback, useRef, useEffect } from 'react';
import api from '@/services/api';

interface AvailabilityCheck {
  isChecking: boolean;
  conflictInfo: any;
  isAvailable: boolean;
  suggestions: Array<{
    checkIn: Date;
    checkOut: Date;
    reason: string;
  }>;
  roomInfo: {
    roomType: 'privativo' | 'comunitario';
    maxCapacity: number;
    occupiedBeds: number;
    availableBeds: number;
  } | null;
}

export function useAvailabilityCheck() {
  const [availabilityState, setAvailabilityState] = useState<AvailabilityCheck>({
    isChecking: false,
    conflictInfo: null,
    isAvailable: true,
    suggestions: [],
    roomInfo: null
  });

  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastCheckRef = useRef<string>('');

  const generateAlternativeDates = useCallback((originalCheckIn: Date, originalCheckOut: Date) => {
    const suggestions = [];
    const daysBetween = Math.ceil((originalCheckOut.getTime() - originalCheckIn.getTime()) / (1000 * 60 * 60 * 24));
    
    // Sugerir datas uma semana antes
    const weekBefore = new Date(originalCheckIn);
    weekBefore.setDate(weekBefore.getDate() - 7);
    const weekBeforeEnd = new Date(weekBefore);
    weekBeforeEnd.setDate(weekBeforeEnd.getDate() + daysBetween);
    
    suggestions.push({
      checkIn: weekBefore,
      checkOut: weekBeforeEnd,
      reason: 'Uma semana antes'
    });

    // Sugerir datas uma semana depois
    const weekAfter = new Date(originalCheckOut);
    weekAfter.setDate(weekAfter.getDate() + 1);
    const weekAfterEnd = new Date(weekAfter);
    weekAfterEnd.setDate(weekAfterEnd.getDate() + daysBetween);
    
    suggestions.push({
      checkIn: weekAfter,
      checkOut: weekAfterEnd,
      reason: 'Uma semana depois'
    });

    return suggestions;
  }, []);

  const checkAvailability = useCallback(async (roomId: number, checkIn: Date, checkOut: Date, excludeReservationId?: number, guestsCount: number = 1) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    const checkKey = `${roomId}-${checkIn?.toISOString()}-${checkOut?.toISOString()}-${excludeReservationId || ''}-${guestsCount}`;
    if (checkKey === lastCheckRef.current) return;
    lastCheckRef.current = checkKey;

    if (!roomId || !checkIn || !checkOut) {
      setAvailabilityState(prev => ({ ...prev, isChecking: false, conflictInfo: null, isAvailable: true, roomInfo: null }));
      return;
    }

    setAvailabilityState(prev => ({ ...prev, isChecking: true }));

    timeoutRef.current = setTimeout(async () => {
      try {
        const response = await api.get('/bookings/availability', {
          params: {
            start: checkIn.toISOString(),
            end: checkOut.toISOString(),
            guests: guestsCount
          }
        });

        const availableRooms = response.data;
        const targetRoom = availableRooms.find((r: any) => r.id === roomId);
        const isAvailable = !!targetRoom;

        // Se não disponível, buscar detalhes do porquê (pode ser consultando as reservas do quarto)
        // Por enquanto, simplificamos a resposta
        setAvailabilityState({
          isChecking: false,
          conflictInfo: !isAvailable ? { type: 'total', message: 'Indisponível' } : null,
          isAvailable,
          suggestions: !isAvailable ? generateAlternativeDates(checkIn, checkOut) : [],
          roomInfo: targetRoom ? {
            roomType: targetRoom.type,
            maxCapacity: targetRoom.max_capacity,
            occupiedBeds: 0, // O backend já filtrou, então assumimos que cabe
            availableBeds: targetRoom.max_capacity
          } : null
        });
      } catch (error) {
        console.error('Erro ao verificar disponibilidade:', error);
        setAvailabilityState(prev => ({ ...prev, isChecking: false, isAvailable: true }));
      }
    }, 500);
  }, [generateAlternativeDates]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return {
    ...availabilityState,
    checkAvailability
  };
}
