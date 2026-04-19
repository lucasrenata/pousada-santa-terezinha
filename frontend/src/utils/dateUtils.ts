/**
 * Utilitário para lidar com datas no fuso horário de Brasília (UTC-3).
 * Evita problemas com .toISOString() que converte para UTC e avança o dia após as 21:00h.
 */

export const getTodayISODate = (): string => {
  const d = new Date();
  // Forçamos o deslocamento para garantir YYYY-MM-DD local
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

export const formatToBrasiliaDate = (dateStr: string): string => {
  if (!dateStr) return '';
  // Se vier apenas YYYY-MM-DD, adicionamos o horário do meio do dia para evitar problemas de fuso no construtor Date
  const date = dateStr.includes('T') ? new Date(dateStr) : new Date(dateStr + 'T12:00:00');
  return date.toLocaleDateString('pt-BR');
};

export const getBrasiliaNow = (): Date => {
  return new Date();
};
