import { useState, useEffect } from 'react';
import api from '@/services/api';

export interface Room {
  id: number;
  number: string;
  type: string;
  price_per_night: number;
  status: 'DISPONIVEL' | 'OCUPADO' | 'LIMPEZA' | 'MANUTENCAO';
  max_capacity: number;
}

export function useRealTimeRooms() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchRooms = async () => {
    try {
      const response = await api.get('/rooms/');
      setRooms(response.data);
    } catch (error) {
      console.error('Erro ao buscar quartos:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRooms();
    
    // Polling de 5 em 5 segundos como alternativa ao real-time do Supabase
    const interval = setInterval(fetchRooms, 5000);
    return () => clearInterval(interval);
  }, []);

  return { rooms, loading, refetch: fetchRooms };
}
