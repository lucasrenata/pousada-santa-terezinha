import { useState, useEffect } from 'react';
import api from '@/services/api';

export interface Customer {
  id: number;
  name: string;
  email: string;
  phone: string;
  document: string;
  birth_date: string | null;
  profession?: string;
  address_zip?: string;
  address_street?: string;
  address_number?: string;
  address_neighborhood?: string;
  address_city?: string;
  address_state?: string;
}

export function useCustomers() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchCustomers = async () => {
    try {
      const response = await api.get('/guests/');
      setCustomers(response.data);
    } catch (error) {
      console.error('Erro ao buscar clientes:', error);
    } finally {
      setLoading(false);
    }
  };

  const searchCustomers = async (query: string) => {
    try {
      // O backend pode ter um endpoint de busca ou filtramos no front se a lista for pequena.
      // Por enquanto, vamos buscar todos e filtrar no front ou assumir que o backend suporta ?q=
      const response = await api.get('/guests/', {
        params: { q: query }
      });
      return response.data;
    } catch (error) {
      console.error('Erro ao buscar clientes:', error);
      return [];
    }
  };

  const createCustomer = async (customerData: any) => {
    try {
      const response = await api.post('/guests/', customerData);
      await fetchCustomers();
      return response.data;
    } catch (error) {
      console.error('Erro ao criar cliente:', error);
      throw error;
    }
  };

  const updateCustomer = async (id: number, customerData: any) => {
    try {
      const response = await api.put(`/guests/${id}`, customerData);
      await fetchCustomers();
      return response.data;
    } catch (error) {
      console.error('Erro ao atualizar cliente:', error);
      throw error;
    }
  };

  const getCustomerById = async (id: number) => {
    try {
      const response = await api.get(`/guests/${id}`);
      return response.data;
    } catch (error) {
      console.error('Erro ao buscar cliente:', error);
      return null;
    }
  };

  const deleteCustomer = async (id: number) => {
    try {
      await api.delete(`/guests/${id}`);
      setCustomers(prev => prev.filter(c => c.id !== id));
    } catch (error) {
      console.error('Erro ao deletar cliente:', error);
      throw error;
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  return {
    customers,
    loading,
    searchCustomers,
    getCustomerById,
    createCustomer,
    updateCustomer,
    deleteCustomer,
    refetch: fetchCustomers
  };
}