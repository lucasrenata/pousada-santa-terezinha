import { useForm } from 'react-hook-form';
import { useEffect } from 'react';
import api from '../services/api';
import type { AxiosError } from 'axios';
import { X } from 'lucide-react';

interface RoomModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialData?: any | null;
}

export default function RoomModal({ isOpen, onClose, onSuccess, initialData }: RoomModalProps) {
  type FormData = {
    number: string;
    type: string;
    price: string;
    max_capacity: number;
    floor?: number;
  };
  
  const { register, handleSubmit, reset, setValue } = useForm<FormData>({ 
    defaultValues: { max_capacity: 2 } 
  });

  useEffect(() => {
    if (initialData) {
      setValue('number', initialData.number);
      setValue('type', initialData.type);
      setValue('price', initialData.price_per_night.toString());
      setValue('max_capacity', initialData.max_capacity);
      setValue('floor', initialData.floor || 1);
    } else {
      reset({ number: '', type: 'simples', price: '', max_capacity: 2, floor: 1 });
    }
  }, [initialData, setValue, reset, isOpen]);

  if (!isOpen) return null;

  const onSubmit = async (data: FormData) => {
    try {
      const payload = {
        number: data.number,
        type: data.type,
        price_per_night: parseFloat(data.price),
        max_capacity: Number(data.max_capacity) || 2,
        floor: Number(data.floor) || 1
      };
      
      if (initialData) {
        await api.put(`/rooms/${initialData.id}`, payload);
      } else {
        await api.post('/rooms/', payload);
      }
      
      reset();
      onSuccess();
      onClose();
    } catch (error) {
      const axErr = error as AxiosError<{ detail?: string }>;
      alert(axErr.response?.data?.detail || 'Erro ao salvar quarto.');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-md p-6 shadow-2xl animate-in fade-in zoom-in duration-200">
        
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-slate-800">
            {initialData ? 'Editar Quarto' : 'Novo Quarto'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Número do Quarto</label>
            <input {...register("number", { required: true })} placeholder="Ex: 101" className="w-full border border-slate-300 rounded-lg p-2 focus:ring-2 ring-blue-500 outline-none" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Tipo</label>
              <select {...register("type")} className="w-full border border-slate-300 rounded-lg p-2 bg-white outline-none">
                <option value="simples">Simples</option>
                <option value="casal">Casal</option>
                <option value="luxo">Luxo</option>
                <option value="familia">Família</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Preço (Diária)</label>
              <input {...register("price", { required: true })} type="number" step="0.01" placeholder="0.00" className="w-full border border-slate-300 rounded-lg p-2 outline-none" />
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Capacidade</label>
              <input
                {...register("max_capacity", { required: true, min: 1 })}
                type="number"
                min={1}
                className="w-full border border-slate-300 rounded-lg p-2 outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Andar</label>
              <input
                {...register("floor", { min: 0 })}
                type="number"
                className="w-full border border-slate-300 rounded-lg p-2 outline-none"
              />
            </div>
          </div>

          <div className="pt-4 flex gap-3">
            <button type="button" onClick={onClose} className="flex-1 py-2 text-slate-600 font-medium hover:bg-slate-100 rounded-lg transition">
              Cancelar
            </button>
            <button type="submit" className="flex-1 py-2 bg-blue-600 text-white font-bold rounded-lg hover:bg-blue-700 transition">
              Salvar Alterações
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
