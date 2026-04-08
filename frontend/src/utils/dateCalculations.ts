
// Date string input from date picker (YYYY-MM-DD) to UTC noon ISO string
export const dateStringToUTCNoon = (dateString: string): string => {
  return `${dateString}T12:00:00.000Z`;
};

// Local Date object to UTC noon ISO string
export const localDateToUTCNoonISO = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}T12:00:00.000Z`;
};

// ISO string to local date ignoring timezone (only parse YYYY-MM-DD portion)
export const isoToLocalDateIgnoringTZ = (isoString: string): Date => {
  const dateOnly = isoString.split('T')[0]; // Get YYYY-MM-DD part
  const [year, month, day] = dateOnly.split('-').map(Number);
  return new Date(year, month - 1, day); // Create local date
};

/**
 * Calcula o número de diárias seguindo a lógica hoteleira profissional
 * 
 * Regras:
 * - Horário padrão de início da diária: 14:00
 * - Horário limite para check-out sem cobrança extra: 14:00
 * - Se check-in < 14:00 → cobra diária do dia anterior
 * - Se check-out > 14:00 → cobra diária extra
 * 
 * @param checkInDate - Data de check-in (Date)
 * @param checkInTime - Horário de check-in (HH:MM string) ou null
 * @param checkOutDate - Data de check-out (Date)
 * @param checkOutTime - Horário de check-out (HH:MM string) ou null
 * @returns Número de diárias a cobrar
 */
export const calculateDailyRatesWithHours = (
  checkInDate: Date,
  checkInTime: string | null,
  checkOutDate: Date,
  checkOutTime: string | null
): number => {
  // Constantes do sistema
  const DAILY_RATE_START_HOUR = 14; // 14:00
  const CHECKOUT_LIMIT_HOUR = 14;   // 14:00

  // Converter horários de string para número (ex: "03:30" → 3.5)
  const parseTime = (timeStr: string | null): number => {
    if (!timeStr) return DAILY_RATE_START_HOUR; // Default: 14:00
    const [hours, minutes] = timeStr.split(':').map(Number);
    return hours + (minutes / 60);
  };

  const checkInHour = parseTime(checkInTime);
  const checkOutHour = parseTime(checkOutTime);

  // Criar cópias das datas para não mudar os originais
  let adjustedCheckIn = new Date(checkInDate);
  let adjustedCheckOut = new Date(checkOutDate);

  // Zerar horários para comparar apenas dias
  adjustedCheckIn.setHours(0, 0, 0, 0);
  adjustedCheckOut.setHours(0, 0, 0, 0);

  // REGRA 1: Se check-in for antes das 14:00, subtrair 1 dia (cobra diária do dia anterior)
  if (checkInHour < DAILY_RATE_START_HOUR) {
    adjustedCheckIn.setDate(adjustedCheckIn.getDate() - 1);
  }

  // Calcular diferença em dias
  const diffTime = adjustedCheckOut.getTime() - adjustedCheckIn.getTime();
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

  // REGRA 2: Se check-out for depois das 14:00, adicionar 1 diária
  let totalDays = diffDays;
  if (checkOutHour > CHECKOUT_LIMIT_HOUR) {
    totalDays += 1;
  }

  // Garantir no mínimo 1 diária
  return Math.max(1, totalDays);
};

export const calculateDaysStayed = (
  checkInDate: string, 
  checkOutDate?: string,
  checkInTime?: string | null,
  checkOutTime?: string | null
): number => {
  const checkIn = new Date(checkInDate);
  const endDate = checkOutDate ? new Date(checkOutDate) : new Date();
  
  // Se tiver horários, usar a lógica avançada
  if (checkInTime || checkOutTime) {
    return calculateDailyRatesWithHours(checkIn, checkInTime || null, endDate, checkOutTime || null);
  }
  
  // Fallback: lógica antiga (sem horários)
  const diffTime = endDate.getTime() - checkIn.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return Math.max(1, diffDays);
};

export const calculateTotalAmount = (
  dailyRate: number, 
  guestsCount: number, 
  daysStayed: number
): number => {
  return dailyRate * guestsCount * daysStayed;
};

export const formatCurrency = (amount: number): string => {
  return amount.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  });
};

// Calcula o valor total da reserva baseado nas idades dos hóspedes
// Regras: ≥13 anos = diária completa, 7-12 anos = meia diária, ≤6 anos = R$ 25,00
export const calculateReservationTotal = (
  dailyRate: number,
  days: number,
  ages: number[]
): { total: number; breakdown: { age: number; amount: number; rateType: string }[] } => {
  const breakdown = ages.map(age => {
    let amount = 0;
    let rateType = '';
    
    if (age >= 13) {
      amount = dailyRate * days;
      rateType = 'Diária completa';
    } else if (age >= 7) {
      amount = (dailyRate / 2) * days;
      rateType = 'Meia diária';
    } else {
      amount = 25 * days;
      rateType = 'Taxa fixa (R$ 25/dia)';
    }
    
    return { age, amount, rateType };
  });
  
  const total = breakdown.reduce((sum, item) => sum + item.amount, 0);
  
  return { total, breakdown };
};
