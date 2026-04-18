
from datetime import datetime, date, timedelta
import sys
import os

# Mocking the functions to test locally
def calculate_daily_rates_count(
    check_in_date,
    check_out_date,
    check_in_time_str = None,
    check_out_time_str = None
) -> int:
    STANDARD_HOUR = 14
    
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

    base_check_in = check_in_date.date() if hasattr(check_in_date, "date") and not isinstance(check_in_date, date) else check_in_date
    if ci_hour < STANDARD_HOUR:
        base_check_in -= timedelta(days=1)
        
    base_check_out = check_out_date.date() if hasattr(check_out_date, "date") and not isinstance(check_out_date, date) else check_out_date
    
    diff = (base_check_out - base_check_in).days
    
    total_days = diff
    if co_hour > STANDARD_HOUR:
        total_days += 1
        
    return max(1, total_days)

def calculate_reservation_total(daily_rate, days, ages, settings=None):
    total = 0.0
    for age in ages:
        if age >= 13:
            total += (daily_rate * days)
        elif age >= 7:
            total += (daily_rate * 0.5) * days
        else:
            total += 25.0 * days
    return {"total": total}

# Test Case from user screenshot
ci_date = datetime(2026, 4, 18)
co_date = datetime(2026, 4, 20)
ci_time = "14:00"
co_time = "12:00"
rate = 100.0
ages = [37]

days = calculate_daily_rates_count(ci_date, co_date, ci_time, co_time)
pricing = calculate_reservation_total(rate, days, ages)

print(f"Datas: {ci_date} {ci_time} ate {co_date} {co_time}")
print(f"Diarias calculadas: {days}")
print(f"Total calculado: {pricing['total']}")

# Hypothetical case where it returns 100
ci_date_2 = datetime(2026, 4, 18)
co_date_2 = datetime(2026, 4, 19)
days_2 = calculate_daily_rates_count(ci_date_2, co_date_2, ci_time, co_time)
print(f"Test 2 (18 to 19): Diarias: {days_2}")
