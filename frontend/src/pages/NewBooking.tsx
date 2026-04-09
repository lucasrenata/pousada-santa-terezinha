import { useSearchParams, useNavigate } from 'react-router-dom';
import { ReservationForm } from '@/components/ReservationForm';
import MainLayout from '@/components/MainLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CalendarIcon } from 'lucide-react';

export default function NewBooking() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const roomIdStr = searchParams.get('roomId');
  const initialRoomId = roomIdStr || undefined;

  return (
    <div className="max-w-5xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-black text-slate-900 tracking-tight">Nova Reserva</h1>
        <p className="text-slate-500 mt-2 font-medium">Preencha os dados abaixo para registrar uma nova estadia.</p>
      </div>

      <Card className="border-slate-200 shadow-xl shadow-slate-200/50 overflow-hidden bg-white/80 backdrop-blur-sm">
        <CardHeader className="bg-slate-900 text-white border-b-0 pb-8">
          <CardTitle className="flex items-center gap-3 text-2xl">
            <div className="p-2 bg-white/10 rounded-lg">
              <CalendarIcon className="h-6 w-6 text-blue-400" />
            </div>
            Formulário de Reserva
          </CardTitle>
        </CardHeader>
        <CardContent className="p-8 -mt-4 bg-white rounded-t-3xl shadow-2xl relative z-10">
          <ReservationForm 
            initialRoomId={initialRoomId}
            onSuccess={() => navigate('/bookings')}
            onCancel={() => navigate('/bookings')}
          />
        </CardContent>
      </Card>
    </div>
  );
}
