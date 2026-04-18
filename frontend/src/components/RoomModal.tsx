import { useForm } from 'react-hook-form';
import { useEffect, useState } from 'react';
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
    id: string; // Número do quarto (PrimaryKey)
    type: string;
    price: string;
    max_capacity: number;
    floor?: number;
    description?: string;
  };
  
  const { register, handleSubmit, reset, setValue } = useForm<FormData>({ 
    defaultValues: { max_capacity: 2 } 
  });
  const [pricingModel, setPricingModel] = useState<'per_person' | 'per_room'>('per_person');

  async function loadPricingModel() {
    try {
      const res = await api.get('/settings/');
      const model = res.data.find((s: any) => s.key === 'pousada_pricing_model')?.value;
      if (model) setPricingModel(model as any);
    } catch {
      console.error('Falha ao carregar modelo de preço no modal');
    }
  }

  useEffect(() => {
    if (isOpen) {
        loadPricingModel();
    }
    if (initialData) {
      setValue('id', initialData.id);
      setValue('type', initialData.type);
      setValue('price', initialData.price_per_night.toString());
      setValue('max_capacity', initialData.max_capacity);
      setValue('floor', initialData.floor || 1);
      setValue('description', initialData.description || '');
    } else {
      reset({ id: '', type: 'simples', price: '', max_capacity: 2, floor: 1, description: '' });
    }
  }, [initialData, setValue, reset, isOpen]);

  if (!isOpen) return null;

  const onSubmit = async (data: FormData) => {
    try {
      const payload = {
        id: data.id,
        type: data.type,
        price_per_night: parseFloat(data.price),
        max_capacity: Number(data.max_capacity) || 2,
        floor: Number(data.floor) || 1,
        description: data.description || ''
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
            <input {...register("id", { required: true })} placeholder="Ex: 101" className="w-full border border-slate-300 rounded-lg p-2 focus:ring-2 ring-blue-500 outline-none" disabled={!!initialData} />
            {initialData && <p className="text-[10px] text-slate-400 mt-1">O número do quarto não pode ser alterado após a criação.</p>}
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
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Preço ({pricingModel === 'per_person' ? 'por pessoa' : 'por quarto'})
              </label>
              <input {...register("price", { required: true })} type="number" step="0.01" placeholder="0.00" className="w-full border border-slate-300 rounded-lg p-2 outline-none font-bold text-blue-600" />
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

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Observações / Características</label>
            <textarea
              {...register("description")}
              placeholder="Ex: Próximo ao elevador, cama de casal e beliche, térreo..."
              rows={3}
              className="w-full border border-slate-300 rounded-lg p-2 focus:ring-2 ring-blue-500 outline-none resize-none"
            />
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
