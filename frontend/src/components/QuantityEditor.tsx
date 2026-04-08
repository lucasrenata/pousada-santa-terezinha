
import React, { useState, useEffect, useRef } from 'react';
import { Input } from '@/components/ui/input';
import { useToast } from '@/hooks/use-toast';

interface QuantityEditorProps {
  itemId: string;
  initialQuantity: number;
  unit: string;
  onUpdate: (id: string, newQuantity: number) => Promise<void>;
  disabled?: boolean;
}

export function QuantityEditor({ 
  itemId, 
  initialQuantity, 
  unit, 
  onUpdate, 
  disabled = false 
}: QuantityEditorProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [tempQuantity, setTempQuantity] = useState(initialQuantity.toString());
  const [isUpdating, setIsUpdating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  useEffect(() => {
    setTempQuantity(initialQuantity.toString());
  }, [initialQuantity]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleStartEdit = () => {
    if (disabled || isUpdating) return;
    console.log('Iniciando edição para item:', itemId);
    setIsEditing(true);
    setTempQuantity(initialQuantity.toString());
  };

  const handleCancel = () => {
    console.log('Cancelando edição para item:', itemId);
    setIsEditing(false);
    setTempQuantity(initialQuantity.toString());
  };

  const handleSubmit = async () => {
    const newQuantity = parseInt(tempQuantity);
    
    if (isNaN(newQuantity) || newQuantity < 0) {
      toast({
        title: "Erro",
        description: "Quantidade deve ser um número válido e não negativo",
        variant: "destructive",
      });
      return;
    }

    if (newQuantity === initialQuantity) {
      setIsEditing(false);
      return;
    }

    try {
      console.log('Atualizando quantidade:', { itemId, oldQuantity: initialQuantity, newQuantity });
      setIsUpdating(true);
      await onUpdate(itemId, newQuantity);
      setIsEditing(false);
    } catch (error) {
      console.error('Erro ao atualizar quantidade:', error);
      setTempQuantity(initialQuantity.toString());
    } finally {
      setIsUpdating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancel();
    }
  };

  if (isEditing) {
    return (
      <Input
        ref={inputRef}
        type="number"
        min="0"
        value={tempQuantity}
        onChange={(e) => setTempQuantity(e.target.value)}
        onBlur={handleSubmit}
        onKeyDown={handleKeyDown}
        className="w-20 h-8 text-center text-sm"
        disabled={isUpdating}
      />
    );
  }

  return (
    <span 
      className={`w-20 text-center font-medium px-2 py-1 rounded transition-colors ${
        disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-muted/50'
      }`}
      onClick={handleStartEdit}
      title={disabled ? "Não é possível editar durante atualizações" : "Clique para editar a quantidade"}
    >
      {initialQuantity} {unit}
    </span>
  );
}
