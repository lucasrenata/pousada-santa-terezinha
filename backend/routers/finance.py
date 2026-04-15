from fastapi import APIRouter, Depends, HTTPException
from .auth import get_current_admin

from sqlalchemy.orm import Session
from sqlalchemy import func, asc, desc, and_
from datetime import date, datetime, timedelta
from typing import Optional, List
import models, schemas
from database import get_db

router = APIRouter(prefix="/finance", tags=["Finance"])

# =============================================================================
# RECEITAS (existentes)
# =============================================================================

# 1. LANÇAR RECEITA (Manual)
@router.post("/", response_model=schemas.RevenueResponse)
def add_revenue(revenue: schemas.RevenueCreate, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    new_rev = models.Revenue(
        description=revenue.description,
        amount=revenue.amount,
        category=revenue.category,
        payment_method=revenue.payment_method,
        booking_id=revenue.booking_id,
        created_at=datetime.now()
    )
    db.add(new_rev)
    db.commit()
    db.refresh(new_rev)
    return new_rev

# 2. RELATÓRIO COM FILTROS E QUEBRA
@router.get("/report")
def get_report(
    start: Optional[date] = None,
    end: Optional[date] = None,
    category: Optional[models.RevenueCategory] = None,
    payment_method: Optional[models.PaymentMethod] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: Optional[str] = "created_at",
    sort_dir: str = "desc",
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    query = db.query(models.Revenue)
    if start: query = query.filter(models.Revenue.created_at >= start)
    if end:   query = query.filter(models.Revenue.created_at <= end)
    if category:        query = query.filter(models.Revenue.category == category)
    if payment_method:  query = query.filter(models.Revenue.payment_method == payment_method)
    if search:
        query = query.filter(models.Revenue.description.ilike(f"%{search.lower()}%"))

    total_count = query.count()
    total = query.with_entities(func.coalesce(func.sum(models.Revenue.amount), 0.0)).scalar() or 0.0
    cats  = query.with_entities(models.Revenue.category,       func.sum(models.Revenue.amount)).group_by(models.Revenue.category).all()
    pays  = query.with_entities(models.Revenue.payment_method, func.sum(models.Revenue.amount)).group_by(models.Revenue.payment_method).all()
    by_category = {c.value: float(v) for c, v in cats}
    by_payment  = {p.value: float(v) for p, v in pays}

    sort_map = {
        "created_at": models.Revenue.created_at,
        "amount":     models.Revenue.amount,
        "description":    models.Revenue.description,
        "category":       models.Revenue.category,
        "payment_method": models.Revenue.payment_method,
    }
    if sort_by in sort_map:
        col = sort_map[sort_by]
        query = query.order_by(desc(col) if sort_dir.lower() == "desc" else asc(col))

    page      = max(page, 1)
    page_size = max(min(page_size, 200), 1)
    revenues  = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total_revenue": total,
        "transactions":  total_count,
        "data":          revenues,
        "by_category":   by_category,
        "by_payment_method": by_payment,
        "page":      page,
        "page_size": page_size,
        "pages": (total_count // page_size) + (1 if total_count % page_size else 0)
    }

# 3. ATUALIZAR RECEITA
@router.put("/{revenue_id}", response_model=schemas.RevenueResponse)
def update_revenue(revenue_id: int, payload: schemas.RevenueUpdate, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    rev = db.query(models.Revenue).filter(models.Revenue.id == revenue_id).first()
    if not rev:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    if payload.description    is not None: rev.description    = payload.description
    if payload.amount         is not None: rev.amount         = payload.amount
    if payload.category       is not None: rev.category       = payload.category
    if payload.payment_method is not None: rev.payment_method = payload.payment_method
    if payload.booking_id     is not None: rev.booking_id     = payload.booking_id
    db.commit()
    db.refresh(rev)
    return rev

# 4. EXCLUIR RECEITA
@router.delete("/{revenue_id}")
def delete_revenue(revenue_id: int, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    rev = db.query(models.Revenue).filter(models.Revenue.id == revenue_id).first()
    if not rev:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    db.delete(rev)
    db.commit()
    return {"message": "Receita excluída"}


# =============================================================================
# DESPESAS / CONTAS A PAGAR  (NOVOS)
# =============================================================================

# 5. CRIAR DESPESA
@router.post("/expenses/", response_model=schemas.ExpenseResponse)
def create_expense(
    data: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    expense = models.Expense(
        description=data.description,
        amount=data.amount,
        category=data.category,
        due_date=data.due_date,
        notes=data.notes,
        created_by=admin.username,
        created_at=datetime.now()
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense

# 6. LISTAR / FILTRAR DESPESAS
@router.get("/expenses/", response_model=List[schemas.ExpenseResponse])
def list_expenses(
    start:      Optional[date] = None,
    end:        Optional[date] = None,
    category:   Optional[models.ExpenseCategory] = None,
    is_paid:    Optional[bool] = None,
    overdue:    Optional[bool] = None,      # Vencidas e não pagas
    search:     Optional[str] = None,
    page:       int = 1,
    page_size:  int = 25,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    query = db.query(models.Expense)

    if start:    query = query.filter(models.Expense.created_at >= start)
    if end:      query = query.filter(models.Expense.created_at <= end)
    if category: query = query.filter(models.Expense.category == category)
    if is_paid is not None: query = query.filter(models.Expense.is_paid == is_paid)
    if overdue:
        today = date.today()
        query = query.filter(
            models.Expense.is_paid == False,
            models.Expense.due_date < today,
            models.Expense.due_date.isnot(None)
        )
    if search:
        query = query.filter(models.Expense.description.ilike(f"%{search}%"))

    page      = max(page, 1)
    page_size = max(min(page_size, 200), 1)
    return query.order_by(desc(models.Expense.created_at)).offset((page - 1) * page_size).limit(page_size).all()

# 7. EDITAR / MARCAR COMO PAGO
@router.put("/expenses/{expense_id}", response_model=schemas.ExpenseResponse)
def update_expense(
    expense_id: int,
    payload: schemas.ExpenseUpdate,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")

    if payload.description    is not None: expense.description    = payload.description
    if payload.amount         is not None: expense.amount         = payload.amount
    if payload.category       is not None: expense.category       = payload.category
    if payload.due_date       is not None: expense.due_date       = payload.due_date
    if payload.notes          is not None: expense.notes          = payload.notes
    if payload.payment_method is not None: expense.payment_method = payload.payment_method

    # Lógica de marcação de pagamento
    if payload.is_paid is not None:
        expense.is_paid   = payload.is_paid
        expense.paid_date = payload.paid_date if payload.paid_date else (date.today() if payload.is_paid else None)

    db.commit()
    db.refresh(expense)
    return expense

# 8. EXCLUIR DESPESA
@router.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")
    db.delete(expense)
    db.commit()
    return {"message": "Despesa excluída"}


# =============================================================================
# KPIs DIÁRIOS — Dashboard  (NOVO)
# =============================================================================

# 9. SNAPSHOT DO DIA (para o Dashboard)
@router.get("/daily-snapshot")
def daily_snapshot(
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    now   = datetime.now()
    today = now.date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day   = datetime.combine(today, datetime.max.time())

    # --- Receita do día ---
    revenue_today = db.query(
        func.coalesce(func.sum(models.Revenue.amount), 0.0)
    ).filter(
        models.Revenue.created_at >= start_of_day,
        models.Revenue.created_at <= end_of_day
    ).scalar() or 0.0

    # --- Despesa do dia (pagas hoje) ---
    expense_today = db.query(
        func.coalesce(func.sum(models.Expense.amount), 0.0)
    ).filter(
        models.Expense.paid_date == today
    ).scalar() or 0.0

    # --- Quartos ---
    rooms = db.query(models.Room).all()
    total_rooms   = len(rooms) or 1
    occupied      = sum(1 for r in rooms if r.status == models.RoomStatus.OCUPADO)
    available     = sum(1 for r in rooms if r.status == models.RoomStatus.DISPONIVEL)
    occupancy_pct = round((occupied / total_rooms) * 100, 1)

    # --- Hóspedes no local ---
    active_bookings = db.query(models.Booking).filter(
        models.Booking.status.in_([models.BookingStatus.ATIVO, models.BookingStatus.CONFIRMADO]),
        models.Booking.check_in_date  <= now,
        models.Booking.check_out_date >= now
    ).all()
    guests_on_site = sum(b.total_guests or 0 for b in active_bookings)

    # --- Movimentações do día ---
    checkins_today = db.query(models.Booking).filter(
        models.Booking.real_check_in >= start_of_day,
        models.Booking.real_check_in <= end_of_day
    ).count()

    checkouts_today = db.query(models.Booking).filter(
        models.Booking.real_check_out >= start_of_day,
        models.Booking.real_check_out <= end_of_day
    ).count()

    # --- Ticket médio (reservas ativas) ---
    amounts = [b.total_amount for b in active_bookings if b.total_amount]
    avg_ticket = round(sum(amounts) / len(amounts), 2) if amounts else 0.0

    # --- Despesas vencidas não pagas ---
    overdue_count = db.query(models.Expense).filter(
        models.Expense.is_paid == False,
        models.Expense.due_date < today,
        models.Expense.due_date.isnot(None)
    ).count()

    return {
        "revenue_today":    round(revenue_today, 2),
        "expense_today":    round(expense_today, 2),
        "net_today":        round(revenue_today - expense_today, 2),
        "occupancy_pct":    occupancy_pct,
        "total_rooms":      total_rooms,
        "occupied_rooms":   occupied,
        "available_rooms":  available,
        "guests_on_site":   guests_on_site,
        "checkins_today":   checkins_today,
        "checkouts_today":  checkouts_today,
        "avg_ticket":       avg_ticket,
        "overdue_expenses": overdue_count,
    }


# =============================================================================
# FLUXO DE CAIXA  (NOVO)
# =============================================================================

# 10. FLUXO DE CAIXA — Receitas vs Despesas vs Saldo
@router.get("/cash-flow")
def cash_flow(
    start: Optional[date] = None,
    end:   Optional[date] = None,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    # Default: último 30 dias
    if not end:   end   = date.today()
    if not start: start = end - timedelta(days=29)

    start_dt = datetime.combine(start, datetime.min.time())
    end_dt   = datetime.combine(end,   datetime.max.time())

    # --- Totais do período ---
    total_revenue = db.query(
        func.coalesce(func.sum(models.Revenue.amount), 0.0)
    ).filter(
        models.Revenue.created_at >= start_dt,
        models.Revenue.created_at <= end_dt
    ).scalar() or 0.0

    total_expense = db.query(
        func.coalesce(func.sum(models.Expense.amount), 0.0)
    ).filter(
        models.Expense.is_paid == True,
        models.Expense.paid_date >= start,
        models.Expense.paid_date <= end
    ).scalar() or 0.0

    # --- Receitas por categoria ---
    rev_by_cat = db.query(
        models.Revenue.category, func.sum(models.Revenue.amount)
    ).filter(
        models.Revenue.created_at >= start_dt,
        models.Revenue.created_at <= end_dt
    ).group_by(models.Revenue.category).all()

    # --- Despesas por categoria ---
    exp_by_cat = db.query(
        models.Expense.category, func.sum(models.Expense.amount)
    ).filter(
        models.Expense.is_paid == True,
        models.Expense.paid_date >= start,
        models.Expense.paid_date <= end
    ).group_by(models.Expense.category).all()

    # --- Timeline diária (receita - despesa dia a dia) ---
    timeline = []
    cursor = start
    while cursor <= end:
        cursor_dt_start = datetime.combine(cursor, datetime.min.time())
        cursor_dt_end   = datetime.combine(cursor, datetime.max.time())

        day_rev = db.query(
            func.coalesce(func.sum(models.Revenue.amount), 0.0)
        ).filter(
            models.Revenue.created_at >= cursor_dt_start,
            models.Revenue.created_at <= cursor_dt_end
        ).scalar() or 0.0

        day_exp = db.query(
            func.coalesce(func.sum(models.Expense.amount), 0.0)
        ).filter(
            models.Expense.is_paid == True,
            models.Expense.paid_date == cursor
        ).scalar() or 0.0

        timeline.append({
            "date":    cursor.isoformat(),
            "revenue": round(float(day_rev), 2),
            "expense": round(float(day_exp), 2),
            "net":     round(float(day_rev) - float(day_exp), 2),
        })
        cursor += timedelta(days=1)

    # --- Despesas pendentes (não pagas) ---
    pending_expenses = db.query(
        func.coalesce(func.sum(models.Expense.amount), 0.0)
    ).filter(
        models.Expense.is_paid == False
    ).scalar() or 0.0

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "total_revenue":      round(float(total_revenue), 2),
        "total_expense":      round(float(total_expense), 2),
        "net_result":         round(float(total_revenue) - float(total_expense), 2),
        "pending_expenses":   round(float(pending_expenses), 2),
        "revenue_by_category": {c.value: round(float(v), 2) for c, v in rev_by_cat},
        "expense_by_category": {c.value: round(float(v), 2) for c, v in exp_by_cat},
        "timeline":            timeline,
    }


# =============================================================================
# COMPARATIVO DE PERÍODOS  (NOVO)
# =============================================================================

def _period_summary(db: Session, start: date, end: date) -> dict:
    """Helper: calcula receita, despesa e KPIs de ocupação para um período."""
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt   = datetime.combine(end,   datetime.max.time())

    revenue = db.query(
        func.coalesce(func.sum(models.Revenue.amount), 0.0)
    ).filter(
        models.Revenue.created_at >= start_dt,
        models.Revenue.created_at <= end_dt
    ).scalar() or 0.0

    expense = db.query(
        func.coalesce(func.sum(models.Expense.amount), 0.0)
    ).filter(
        models.Expense.is_paid == True,
        models.Expense.paid_date >= start,
        models.Expense.paid_date <= end
    ).scalar() or 0.0

    checkins = db.query(models.Booking).filter(
        models.Booking.real_check_in >= start_dt,
        models.Booking.real_check_in <= end_dt
    ).count()

    checkouts = db.query(models.Booking).filter(
        models.Booking.real_check_out >= start_dt,
        models.Booking.real_check_out <= end_dt
    ).count()

    days = (end - start).days + 1

    return {
        "start":     start.isoformat(),
        "end":       end.isoformat(),
        "days":      days,
        "revenue":   round(float(revenue), 2),
        "expense":   round(float(expense), 2),
        "net":       round(float(revenue) - float(expense), 2),
        "checkins":  checkins,
        "checkouts": checkouts,
        "daily_avg_revenue": round(float(revenue) / days, 2) if days else 0.0,
    }

# 11. COMPARATIVO A vs B
@router.get("/compare")
def compare_periods(
    p1_start: date,
    p1_end:   date,
    p2_start: date,
    p2_end:   date,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    period_a = _period_summary(db, p1_start, p1_end)
    period_b = _period_summary(db, p2_start, p2_end)

    def delta(a: float, b: float) -> dict:
        """Retorna variação absoluta e percentual de A para B."""
        diff = b - a
        pct  = round((diff / a) * 100, 1) if a else None
        return {"absolute": round(diff, 2), "percent": pct}

    return {
        "period_a":  period_a,
        "period_b":  period_b,
        "delta": {
            "revenue":           delta(period_a["revenue"],           period_b["revenue"]),
            "expense":           delta(period_a["expense"],           period_b["expense"]),
            "net":               delta(period_a["net"],               period_b["net"]),
            "checkins":          delta(period_a["checkins"],          period_b["checkins"]),
            "daily_avg_revenue": delta(period_a["daily_avg_revenue"], period_b["daily_avg_revenue"]),
        }
    }
