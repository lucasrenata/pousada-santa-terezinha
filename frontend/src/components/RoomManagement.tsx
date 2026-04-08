import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { User, Phone, Mail, DollarSign, Calendar, Check, X, Users, Home, Bed } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { supabase } from '@/integrations/supabase/client';
import { Tables } from '@/integrations/supabase/types';
import { calculateDaysStayed, calculateTotalAmount, formatCurrency } from '@/utils/dateCalculations';

type Room = Tables<'rooms'>;

export function RoomManagement() {
  const { toast } = useToast();
  const { roomId } = useParams();
  const [activeRoom, setActiveRoom] = useState(roomId ? parseInt(roomId) : 1);
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    value: '',
    guestsCount: '1',
  });
  const [editingGuests, setEditingGuests] = useState(false);
  const [tempGuestsCount, setTempGuestsCount] = useState('');
  const [editingRoomConfig, setEditingRoomConfig] = useState(false);
  const [tempRoomType, setTempRoomType] = useState<'privativo' | 'comunitario'>('privativo');
  const [tempMaxCapacity, setTempMaxCapacity] = useState('2');
  const [rooms, setRooms] = useState<Record<number, Room>>({});
  const [loading, setLoading] = useState(true);

  // Carregar dados dos quartos do Supabase
  const fetchRooms = async () => {
    try {
      const { data, error } = await supabase
        .from('rooms')
        .select('*')
        .order('id');

      if (error) {
        console.error('Erro ao carregar quartos:', error);
        toast({
          title: "Erro",
          description: "Não foi possível carregar os dados dos quartos",
          variant: "destructive",
        });
        return;
      }

      const roomsData: Record<number, Room> = {};
      data?.forEach(room => {
        roomsData[room.id] = room;
      });
      setRooms(roomsData);
    } catch (error) {
      console.error('Erro ao buscar quartos:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRooms();

    const channel = supabase
      .channel('rooms-changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'rooms'
        },
        (payload) => {
          console.log('Room update:', payload);
          fetchRooms();
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  // Effect to update activeRoom when roomId param changes
  useEffect(() => {
    if (roomId) {
      const roomIdNum = parseInt(roomId);
      if (!isNaN(roomIdNum)) {
        setActiveRoom(roomIdNum);
      }
    }
  }, [roomId]);

  const currentRoom = rooms[activeRoom];

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleCheckIn = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      toast({
        title: "Erro",
        description: "Nome do hóspede é obrigatório",
        variant: "destructive",
      });
      return;
    }

    const guestsCount = parseInt(formData.guestsCount);
    if (guestsCount < 1) {
      toast({
        title: "Erro",
        description: "Número de pessoas deve ser pelo menos 1",
        variant: "destructive",
      });
      return;
    }

    try {
      const { error } = await supabase
        .from('rooms')
        .update({
          status: 'occupied',
          guest_name: formData.name,
          guest_phone: formData.phone,
          guest_email: formData.email,
          daily_rate: parseFloat(formData.value) || null,
          guests_count: guestsCount,
          check_in_date: new Date().toISOString(),
        })
        .eq('id', activeRoom);

      if (error) {
        console.error('Erro no check-in:', error);
        toast({
          title: "Erro",
          description: "Não foi possível realizar o check-in",
          variant: "destructive",
        });
        return;
      }

      toast({
        title: "Check-in realizado!",
        description: `Quarto ${activeRoom} foi ocupado por ${formData.name}`,
      });

      setFormData({ name: '', phone: '', email: '', value: '', guestsCount: '1' });
    } catch (error) {
      console.error('Erro no check-in:', error);
      toast({
        title: "Erro",
        description: "Erro inesperado no check-in",
        variant: "destructive",
      });
    }
  };

  const handleUpdateGuests = async () => {
    const newGuestsCount = parseInt(tempGuestsCount);
    
    if (newGuestsCount < 1) {
      toast({
        title: "Erro",
        description: "Número de pessoas deve ser pelo menos 1",
        variant: "destructive",
      });
      return;
    }

    try {
      const { error } = await supabase
        .from('rooms')
        .update({
          guests_count: newGuestsCount,
        })
        .eq('id', activeRoom);

      if (error) {
        console.error('Erro ao atualizar número de pessoas:', error);
        toast({
          title: "Erro",
          description: "Não foi possível atualizar o número de pessoas",
          variant: "destructive",
        });
        return;
      }

      toast({
        title: "Atualizado!",
        description: `Número de pessoas do quarto ${activeRoom} foi atualizado`,
      });

      setEditingGuests(false);
      setTempGuestsCount('');
    } catch (error) {
      console.error('Erro ao atualizar:', error);
    }
  };

  const handleCheckOut = async () => {
    try {
      const { error } = await supabase
        .from('rooms')
        .update({
          status: 'cleaning',
          guest_name: null,
          guest_phone: null,
          guest_email: null,
          daily_rate: null,
          guests_count: null,
          check_out_date: new Date().toISOString(),
        })
        .eq('id', activeRoom);

      if (error) {
        console.error('Erro no check-out:', error);
        toast({
          title: "Erro",
          description: "Não foi possível realizar o check-out",
          variant: "destructive",
        });
        return;
      }

      toast({
        title: "Check-out realizado!",
        description: `Quarto ${activeRoom} foi liberado`,
      });

      setFormData({ name: '', phone: '', email: '', value: '', guestsCount: '1' });
    } catch (error) {
      console.error('Erro no check-out:', error);
      toast({
        title: "Erro",
        description: "Erro inesperado no check-out",
        variant: "destructive",
      });
    }
  };

  const markAsClean = async () => {
    try {
      const { error } = await supabase
        .from('rooms')
        .update({
          status: 'available',
        })
        .eq('id', activeRoom);

      if (error) {
        console.error('Erro ao marcar como limpo:', error);
        toast({
          title: "Erro",
          description: "Não foi possível marcar o quarto como limpo",
          variant: "destructive",
        });
        return;
      }

      toast({
        title: "Quarto pronto!",
        description: `Quarto ${activeRoom} está disponível para novos hóspedes`,
      });
    } catch (error) {
      console.error('Erro ao marcar como limpo:', error);
      toast({
        title: "Erro",
        description: "Erro inesperado ao marcar quarto como limpo",
        variant: "destructive",
      });
    }
  };

  const handleUpdateRoomConfig = async () => {
    const newMaxCapacity = parseInt(tempMaxCapacity);
    
    if (newMaxCapacity < 1) {
      toast({
        title: "Erro",
        description: "Capacidade deve ser pelo menos 1",
        variant: "destructive",
      });
      return;
    }

    try {
      const { error } = await supabase
        .from('rooms')
        .update({
          room_type: tempRoomType,
          max_capacity: newMaxCapacity,
        })
        .eq('id', activeRoom);

      if (error) {
        console.error('Erro ao atualizar configuração do quarto:', error);
        toast({
          title: "Erro",
          description: "Não foi possível atualizar a configuração do quarto",
          variant: "destructive",
        });
        return;
      }

      toast({
        title: "Atualizado!",
        description: `Configuração do quarto ${activeRoom} foi atualizada`,
      });

      setEditingRoomConfig(false);
    } catch (error) {
      console.error('Erro ao atualizar:', error);
    }
  };

  const getRoomTypeBadge = (roomType: string) => {
    if (roomType === 'comunitario') {
      return (
        <Badge variant="secondary" className="bg-blue-100 text-blue-800">
          <Users className="h-3 w-3 mr-1" />
          Comunitário
        </Badge>
      );
    }
    return (
      <Badge variant="secondary" className="bg-green-100 text-green-800">
        <Home className="h-3 w-3 mr-1" />
        Privativo
      </Badge>
    );
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'available':
        return <Badge variant="available">Disponível</Badge>;
      case 'occupied':
        return <Badge variant="occupied">Ocupado</Badge>;
      case 'cleaning':
        return <Badge variant="cleaning">Limpeza</Badge>;
      default:
        return <Badge variant="secondary">Desconhecido</Badge>;
    }
  };

  // Pre-fill form with guest data when switching rooms
  useEffect(() => {
    const room = currentRoom;
    if (room?.guest_name) {
      setFormData({
        name: room.guest_name || '',
        phone: room.guest_phone || '',
        email: room.guest_email || '',
        value: room.daily_rate?.toString() || '',
        guestsCount: room.guests_count?.toString() || '1',
      });
    } else {
      setFormData({ name: '', phone: '', email: '', value: '', guestsCount: '1' });
    }
  }, [activeRoom, currentRoom]);

  // Calculate values for occupied rooms
  const calculateRoomValues = (room: Room) => {
    if (!room.check_in_date || !room.daily_rate || !room.guests_count) {
      return null;
    }

    const daysStayed = calculateDaysStayed(room.check_in_date, room.check_out_date);
    const totalAmount = calculateTotalAmount(room.daily_rate, room.guests_count, daysStayed);

    return {
      daysStayed,
      totalAmount,
      dailyRate: room.daily_rate,
      guestsCount: room.guests_count,
    };
  };

  const roomValues = currentRoom ? calculateRoomValues(currentRoom) : null;

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="bg-gradient-card rounded-lg p-6 shadow-lg">
          <h2 className="text-2xl font-bold text-foreground mb-2">
            Gestão de Quartos
          </h2>
          <p className="text-muted-foreground">
            Carregando dados dos quartos...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-card rounded-lg p-6 shadow-lg">
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Gestão de Quartos
        </h2>
        <p className="text-muted-foreground">
          Gerencie check-ins, check-outs e status dos quartos
        </p>
      </div>

      {/* Room Tabs */}
      <Card>
        <CardHeader>
          <CardTitle>Selecionar Quarto</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 sm:grid-cols-6 lg:grid-cols-9 gap-2">
            {Object.values(rooms).map((room) => (
              <Button
                key={room.id}
                variant={activeRoom === room.id ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveRoom(room.id)}
                className="flex flex-col items-center p-3 h-auto"
              >
                <span className="font-semibold">{room.id}</span>
                <div className="mt-1">
                  {getStatusBadge(room.status)}
                </div>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Room Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Current Status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                Quarto {activeRoom}
                {currentRoom && getStatusBadge(currentRoom.status)}
              </div>
              {currentRoom && getRoomTypeBadge(currentRoom.room_type)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {currentRoom?.guest_name ? (
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{currentRoom.guest_name}</span>
                </div>
                {currentRoom.guest_phone && (
                  <div className="flex items-center space-x-2">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <span>{currentRoom.guest_phone}</span>
                  </div>
                )}
                {currentRoom.guest_email && (
                  <div className="flex items-center space-x-2">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <span>{currentRoom.guest_email}</span>
                  </div>
                )}
                {currentRoom.guests_count && (
                  <div className="flex items-center space-x-2">
                    <Users className="h-4 w-4 text-muted-foreground" />
                    <span>{currentRoom.guests_count} pessoa(s)</span>
                  </div>
                )}
                {currentRoom.check_in_date && (
                  <div className="flex items-center space-x-2">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <span>Check-in: {new Date(currentRoom.check_in_date).toLocaleDateString('pt-BR')}</span>
                  </div>
                )}
                
                {/* Cálculo de Valores */}
                {roomValues && (
                  <div className="mt-4 p-4 bg-muted/50 rounded-lg">
                    <h4 className="font-semibold mb-2">Cálculo da Estadia</h4>
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span>Diária por pessoa:</span>
                        <span>{formatCurrency(roomValues.dailyRate)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Número de pessoas:</span>
                        <span>{roomValues.guestsCount}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Dias de hospedagem:</span>
                        <span>{roomValues.daysStayed} dia(s)</span>
                      </div>
                      <hr className="my-2" />
                      <div className="flex justify-between font-bold text-lg">
                        <span>Total a pagar:</span>
                        <span className="text-green-600">{formatCurrency(roomValues.totalAmount)}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-muted-foreground">
                  {currentRoom?.status === 'cleaning' ? 
                    'Quarto em processo de limpeza' : 
                    'Quarto disponível para ocupação'
                  }
                </p>
                
                {/* Informações do quarto comunitário */}
                {currentRoom?.room_type === 'comunitario' && (
                  <div className="flex items-center gap-2 text-sm text-blue-700 bg-blue-50 p-2 rounded">
                    <Bed className="h-4 w-4" />
                    <span>Capacidade: {currentRoom.max_capacity} camas</span>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Ações</CardTitle>
          </CardHeader>
          <CardContent>
            {currentRoom?.status === 'available' && (
              <form onSubmit={handleCheckIn} className="space-y-4">
                <div>
                  <Label htmlFor="name">Nome do Hóspede *</Label>
                  <Input
                    id="name"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    placeholder="Nome completo"
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="phone">Telefone</Label>
                  <Input
                    id="phone"
                    name="phone"
                    value={formData.phone}
                    onChange={handleInputChange}
                    placeholder="(11) 99999-9999"
                  />
                </div>
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    value={formData.email}
                    onChange={handleInputChange}
                    placeholder="email@exemplo.com"
                  />
                </div>
                <div>
                  <Label htmlFor="value">Valor da Diária por Pessoa (R$)</Label>
                  <Input
                    id="value"
                    name="value"
                    type="number"
                    step="0.01"
                    value={formData.value}
                    onChange={handleInputChange}
                    placeholder="150.00"
                  />
                </div>
                <div>
                  <Label htmlFor="guestsCount">Número de Pessoas *</Label>
                  <Input
                    id="guestsCount"
                    name="guestsCount"
                    type="number"
                    min="1"
                    value={formData.guestsCount}
                    onChange={handleInputChange}
                    placeholder="1"
                    required
                  />
                </div>
                <Button type="submit" className="w-full">
                  <Check className="mr-2 h-4 w-4" />
                  Fazer Check-in
                </Button>
              </form>
            )}

            {currentRoom?.status === 'occupied' && (
              <div className="space-y-4">
                {/* Editar número de pessoas */}
                <div className="p-4 border rounded-lg">
                  <h4 className="font-medium mb-2">Atualizar Número de Pessoas</h4>
                  {!editingGuests ? (
                    <div className="flex items-center justify-between">
                      <span>Pessoas atuais: {currentRoom.guests_count}</span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setEditingGuests(true);
                          setTempGuestsCount(currentRoom.guests_count?.toString() || '1');
                        }}
                      >
                        Editar
                      </Button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <Input
                        type="number"
                        min="1"
                        value={tempGuestsCount}
                        onChange={(e) => setTempGuestsCount(e.target.value)}
                        placeholder="Número de pessoas"
                      />
                      <Button size="sm" onClick={handleUpdateGuests}>
                        <Check className="h-4 w-4" />
                      </Button>
                      <Button 
                        size="sm" 
                        variant="outline" 
                        onClick={() => {
                          setEditingGuests(false);
                          setTempGuestsCount('');
                        }}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>

                <Button 
                  onClick={handleCheckOut} 
                  variant="destructive" 
                  className="w-full"
                >
                  <X className="mr-2 h-4 w-4" />
                  Fazer Check-out
                </Button>
              </div>
            )}

            {currentRoom?.status === 'cleaning' && (
              <div className="space-y-4">
                <Button 
                  onClick={markAsClean} 
                  variant="default" 
                  className="w-full"
                >
                  <Check className="mr-2 h-4 w-4" />
                  Marcar como Limpo
                </Button>
              </div>
            )}

            {/* Configuração do Quarto */}
            <div className="mt-6 p-4 border rounded-lg bg-muted/30">
              <h4 className="font-medium mb-3 flex items-center gap-2">
                <Home className="h-4 w-4" />
                Configuração do Quarto
              </h4>
              {!editingRoomConfig ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span>Tipo:</span>
                    <span>{currentRoom?.room_type === 'comunitario' ? 'Comunitário' : 'Privativo'}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span>Capacidade máxima:</span>
                    <span>{currentRoom?.max_capacity} pessoa(s)</span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full mt-2"
                    onClick={() => {
                      setEditingRoomConfig(true);
                      setTempRoomType((currentRoom?.room_type as 'privativo' | 'comunitario') || 'privativo');
                      setTempMaxCapacity(currentRoom?.max_capacity?.toString() || '2');
                    }}
                  >
                    Editar Configuração
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div>
                    <Label>Tipo de Quarto</Label>
                    <Select value={tempRoomType} onValueChange={(v) => setTempRoomType(v as 'privativo' | 'comunitario')}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="privativo">Privativo</SelectItem>
                        <SelectItem value="comunitario">Comunitário</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Capacidade Máxima</Label>
                    <Input
                      type="number"
                      min="1"
                      value={tempMaxCapacity}
                      onChange={(e) => setTempMaxCapacity(e.target.value)}
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleUpdateRoomConfig} className="flex-1">
                      <Check className="h-4 w-4 mr-1" />
                      Salvar
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setEditingRoomConfig(false)}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
