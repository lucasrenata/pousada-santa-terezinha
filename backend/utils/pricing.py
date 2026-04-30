from datetime import datetime, time, timedelta, date
import math

def calculate_daily_rates_count(
    check_in_date: datetime,
    check_out_date: datetime,
    check_in_time_str: str = None,
    check_out_time_str: str = None,
    policy_check_in_time: str = "14:00",
    policy_check_out_time: str = "12:00"
) -> int:
    """
    Calcula o número de diárias seguindo a lógica hoteleira:
    - Early Check-in: Se entrar antes do horário da política.
    - Late Check-out: Se sair depois do horário da política.
    """
    def parse_time(time_str, default_str="14:00"):
        if not time_str:
            time_str = default_str
        try:
            h, m = map(int, time_str.split(':'))
            return h + (m / 60.0)
        except:
            return 14.0

    ci_hour = parse_time(check_in_time_str, policy_check_in_time)
    co_hour = parse_time(check_out_time_str, policy_check_out_time)
    limit_ci = parse_time(policy_check_in_time, "14:00")
    limit_co = parse_time(policy_check_out_time, "12:00")

    base_check_in = check_in_date.date() if hasattr(check_in_date, "date") else check_in_date
    # Regra Early Check-in: Se entrar antes do limite, conta uma diária a mais (retroage a data de entrada)
    if ci_hour < limit_ci:
        base_check_in -= timedelta(days=1)
        
    base_check_out = check_out_date.date() if hasattr(check_out_date, "date") else check_out_date
    
    diff = (base_check_out - base_check_in).days
    
    # Regra Late Check-out: se sair após o limite, +1 diária
    total_days = diff
    if co_hour > limit_co:
        total_days += 1
        
    return max(1, total_days)

def calculate_reservation_total(
    daily_rate: float,
    days: int,
    ages: list[int],
    settings: dict = None
) -> dict:
    """
    Calcula o valor total da reserva baseado nas idades ou no modelo de precificação.
    """
    # Valores padrão
    model = "per_person"
    child_percentage = 0.5
    infant_fixed = 25.0
    # Novas faixas etárias
    age_infant_until = 6
    age_child_until = 12
    
    if settings:
        model = settings.get('pousada_pricing_model', 'per_person')
        try:
            raw_child = settings.get('pousada_rate_child_percentage')
            if raw_child and str(raw_child).strip():
                child_percentage = float(raw_child) / 100.0
            
            raw_infant = settings.get('pousada_rate_infant_fixed')
            if raw_infant and str(raw_infant).strip():
                infant_fixed = float(raw_infant)
                
            age_infant_until = int(settings.get('age_infant_until', 6))
            age_child_until = int(settings.get('age_child_until', 12))
        except (ValueError, TypeError):
            pass

    if model == "per_room":
        total = daily_rate * days
        return {
            "total": total,
            "pricing_model": "per_room",
            "breakdown": [{"age": None, "amount": total, "rate_type": f"Valor fixo por quarto ({days} diárias)"}]
        }

    breakdown = []
    total = 0.0
    
    for age in ages:
        amount = 0.0
        rate_type = ""
        
        if age > age_child_until:
            amount = daily_rate * days
            rate_type = "Diária completa"
        elif age > age_infant_until:
            amount = (daily_rate * child_percentage) * days
            perc_display = int(child_percentage * 100)
            rate_type = f"Diária reduzida ({perc_display}%)"
        else:
            amount = infant_fixed * days
            rate_type = f"Taxa fixa (R$ {infant_fixed:.2f}/dia)"
            
        breakdown.append({"age": age, "amount": amount, "rate_type": rate_type})
        total += amount
        
    return {
        "total": total,
        "pricing_model": "per_person",
        "breakdown": breakdown
    }
