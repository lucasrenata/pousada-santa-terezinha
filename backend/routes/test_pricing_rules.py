import pytest
from datetime import datetime, date
from utils.pricing import calculate_daily_rates_count, calculate_reservation_total
from database import SessionLocal, set_tenant_context
import models

def test_calculate_daily_rates_count_dynamic_rules():
    # 1. Test standard check-in/out logic using default rules
    # Check-in at 14:00, check-out at 14:00 (1 night) -> should be 1 day
    d1 = datetime(2026, 7, 20, 14, 0)
    d2 = datetime(2026, 7, 21, 14, 0)
    days = calculate_daily_rates_count(d1, d2, "14:00", "14:00", policy_check_in_time="14:00", policy_check_out_time="14:00")
    assert days == 1

    # Check-in at 14:00, check-out at 14:01 (just past check-out limit) -> should be 2 days
    days = calculate_daily_rates_count(d1, d2, "14:00", "14:01", policy_check_in_time="14:00", policy_check_out_time="14:00")
    assert days == 2

    # Check-in at 13:59 (early check-in), check-out at 14:00 -> should be 2 days
    days = calculate_daily_rates_count(d1, d2, "13:59", "14:00", policy_check_in_time="14:00", policy_check_out_time="14:00")
    assert days == 2

    # 2. Test using customized rules: check-in 15:00, check-out 11:00
    # Check-in at 15:00, check-out at 11:00 -> should be 1 day
    days = calculate_daily_rates_count(d1, d2, "15:00", "11:00", policy_check_in_time="15:00", policy_check_out_time="11:00")
    assert days == 1

    # Check-out at 11:01 (past 11:00 limit) -> should be 2 days
    days = calculate_daily_rates_count(d1, d2, "15:00", "11:01", policy_check_in_time="15:00", policy_check_out_time="11:00")
    assert days == 2

    # Check-in at 14:59 (early check-in) -> should be 2 days
    days = calculate_daily_rates_count(d1, d2, "14:59", "11:00", policy_check_in_time="15:00", policy_check_out_time="11:00")
    assert days == 2

def test_calculate_reservation_total_per_room():
    # 1. Per room pricing model
    settings = {
        "pousada_pricing_model": "per_room",
        "pousada_rate_child_percentage": "50.0",
        "pousada_rate_infant_fixed": "25.0"
    }
    pricing = calculate_reservation_total(
        daily_rate=150.0,
        days=2,
        ages=[30, 25],  # 2 adults
        settings=settings
    )
    # 2 days * 150.0 = 300.0
    assert pricing["total"] == 300.0

def test_calculate_reservation_total_per_person():
    # 2. Per person pricing model
    settings = {
        "pousada_pricing_model": "per_person",
        "pousada_rate_child_percentage": "50.0",
        "pousada_rate_infant_fixed": "25.0"
    }
    pricing = calculate_reservation_total(
        daily_rate=150.0,
        days=2,
        ages=[30, 25, 10, 3], # 2 adults, 1 child (50%), 1 infant (25.0 flat/day)
        settings=settings
    )
    # Adult 1: 2 * 150.0 = 300.0
    # Adult 2: 2 * 150.0 = 300.0
    # Child (10): 2 * 150.0 * 0.5 = 150.0
    # Infant (3): 2 * 25.0 = 50.0
    # Total: 300 + 300 + 150 + 50 = 800.0
    assert pricing["total"] == 800.0
