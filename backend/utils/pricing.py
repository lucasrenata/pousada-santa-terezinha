from datetime import datetime, time, timedelta
import math

def calculate_daily_rates_count(
    check_in_date: datetime,
    check_out_date: datetime,
    check_in_time_str: str = None,
    check_out_time_str: str = None
) -> int:
    """
    Calcula o número de diárias seguindo a lógica hoteleira profissional:
    - Início padrão: 14:00
    - Check-out padrão: 14:00
    - Check-in antecipado (< 14:00) = +1 diária
    - Check-out tardio (> 14:00) = +1 diária
    """
    # Constantes
    STANDARD_HOUR = 14
    
    # Horários efetivos (se não informados, usa o padrão 14:00)
    def parse_time(time_str):
        if not time_str:
            return STANDARD_HOUR
        try:
            h, m = map(int, time_str.split(':'))
            return h + (m / 60.0)
        except:
            return STANDARD_HOUR

    ci_hour = parse_time(check_in_time_str)
    co_hour = parse_time(check_out_time_str)

    # Ajuste de datas para o cálculo base
    # Se check-in < 14:00, conta como se tivesse chegado no dia anterior (cobra 1 extra)
    base_check_in = check_in_date.date()
    if ci_hour < STANDARD_HOUR:
        base_check_in -= timedelta(days=1)
        
    base_check_out = check_out_date.date()
    
    # Diferença básica em dias
    diff = (base_check_out - base_check_in).days
    
    # Regra de Check-out tardio: se sair após as 14:00, +1 diária
    total_days = diff
    if co_hour > STANDARD_HOUR:
        total_days += 1
        
    # No mínimo 1 diária se houve ocupação
    return max(1, total_days)

def calculate_reservation_total(
    daily_rate: float,
    days: int,
    ages: list[int],
    settings: dict = None
) -> dict:
    """
    Calcula o valor total da reserva baseado nas idades.
    Busca valores nas settings dinâmicas se fornecidas.
    """
    # Valores padrão se não houver settings
    child_percentage = 0.5 # 50%
    infant_fixed = 25.0    # R$ 25
    
    if settings:
        try:
            raw_child = settings.get('pousada_rate_child_percentage')
            if raw_child and str(raw_child).strip():
                child_percentage = float(raw_child) / 100.0
            
            raw_infant = settings.get('pousada_rate_infant_fixed')
            if raw_infant and str(raw_infant).strip():
                infant_fixed = float(raw_infant)
        except (ValueError, TypeError):
            # Mantém os padrões seguros definidos acima se houver erro na conversão
            pass

    breakdown = []
    total = 0.0
    
    for age in ages:
        amount = 0.0
        rate_type = ""
        
        if age >= 13:
            amount = daily_rate * days
            rate_type = "Diária completa"
        elif age >= 7:
            # Meia diária dinâmica (padrão 50%)
            amount = (daily_rate * child_percentage) * days
            perc_display = int(child_percentage * 100)
            rate_type = f"Diária reduzida ({perc_display}%)"
        else:
            # Taxa fixa dinâmica (padrão R$ 25)
            amount = infant_fixed * days
            rate_type = f"Taxa fixa (R$ {infant_fixed:.2f}/dia)"
            
        breakdown.append({
            "age": age,
            "amount": amount,
            "rate_type": rate_type
        })
        total += amount
        
    return {
        "total": total,
        "breakdown": breakdown
    }
