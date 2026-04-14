import { useState, useEffect } from 'react';
import api from '@/services/api';

export interface Companion {
  id: number;
  name: string;
  age: number;
}

export interface Reservation {
  id: number;
  room_id: string;
  room_number: string | null;
  guest_name: string;
  status: 'pendente' | 'confirmado' | 'ativo' | 'concluido' | 'cancelado';
  total_guests: number;
  total_amount: number;
  deposit_amount: number;
  payment_status: 'pending' | 'partial' | 'paid' | 'cancelled';
  check_in_date: string;
  check_out_date: string;
  check_in_time?: string;
  check_out_time?: string;
  notes?: string;
  payment_receipt_url?: string;
  companions: Companion[];
}

export function useReservations() {
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchReservations = async (start?: string, end?: string) => {
    setLoading(true);
    try {
      const response = await api.get('/bookings/', {
        params: { start, end }
      });
      setReservations(response.data);
    } catch (error) {
      console.error('Erro ao buscar reservas:', error);
    } finally {
      setLoading(false);
    }
  };

  const createReservation = async (reservationData: any) => {
    try {
      const response = await api.post('/bookings/', reservationData);
      await fetchReservations();
      return response.data;
    } catch (error) {
      console.error('Erro ao criar reserva:', error);
      throw error;
    }
  };

  const updateReservation = async (id: number, reservationData: any) => {
    try {
      // O backend usa /bookings/reschedule para datas ou endpoints específicos para status
      // Por simplicidade na migração, vamos assumir que o backend terá um PATCH genérico em breve
      // ou usaremos os endpoints específicos.
      const response = await api.put(`/bookings/${id}`, reservationData);
      await fetchReservations();
      return response.data;
    } catch (error) {
      console.error('Erro ao atualizar reserva:', error);
      throw error;
    }
  };

  const deleteReservation = async (id: number) => {
    try {
      await api.delete(`/bookings/${id}`);
      setReservations(prev => prev.filter(r => r.id !== id));
    } catch (error) {
      console.error('Erro ao deletar reserva:', error);
      throw error;
    }
  };

  const checkReservationConflicts = async (roomId: string, checkIn: string, checkOut: string) => {
    try {
      // O backend já faz a validação de disponibilidade no POST, 
      // mas podemos chamar o GET /availability para uma checagem prévia
      const response = await api.get('/bookings/availability', {
        params: { start: checkIn, end: checkOut }
      });
      const availableRooms = response.data;
      const isAvailable = availableRooms.some((r: any) => r.id === roomId);
      
      if (!isAvailable) {
        return {
          type: 'total',
          message: 'Quarto indisponível no período selecionado.'
        };
      }
      return null;
    } catch (error) {
      console.error('Erro ao verificar conflitos:', error);
      return null;
    }
  };

  useEffect(() => {
    fetchReservations();
  }, []);

  return {
    reservations,
    loading,
    createReservation,
    updateReservation,
    deleteReservation,
    checkReservationConflicts,
    refetch: fetchReservations
  };
}