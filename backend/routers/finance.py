from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from .auth import get_current_admin

from sqlalchemy.orm import Session
from sqlalchemy import func, asc, desc, and_
from datetime import date, datetime, timedelta
from typing import Optional, List
import os
from utils.finance_pdf import generate_financial_report
import models, schemas
from database import get_db, set_tenant_context

router = APIRouter(prefix="/finance", tags=["Finance"])

# =============================================================================
# RECEITAS (existentes)
# =============================================================================

# 1. LANÇAR RECEITA (Manual)
@router.post("/", response_model=schemas.RevenueResponse)
def add_revenue(revenue: schemas.RevenueCreate, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    set_tenant_context(db, admin.tenant_id)
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
    set_tenant_context(db, admin.tenant_id)
    query = db.query(models.Revenue)
    if start: query = query.filter(models.Revenue.created_at >= datetime.combine(start, datetime.min.time()))
    if end:   query = query.filter(models.Revenue.created_at <= datetime.combine(end, datetime.max.time()))
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
    set_tenant_context(db, admin.tenant_id)
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
    set_tenant_context(db, admin.tenant_id)
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
    set_tenant_context(db, admin.tenant_id)
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
    set_tenant_context(db, admin.tenant_id)
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
    set_tenant_context(db, admin.tenant_id)
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
    set_tenant_context(db, admin.tenant_id)
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
    set_tenant_context(db, admin.tenant_id)
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

    # --- Saldo Positivo do Mês (Acumulado) ---
    month_start = today.replace(day=1)
    month_revenue = db.query(func.coalesce(func.sum(models.Revenue.amount), 0.0)).filter(
        models.Revenue.created_at >= datetime.combine(month_start, datetime.min.time())
    ).scalar() or 0.0
    
    month_expense = db.query(func.coalesce(func.sum(models.Expense.amount), 0.0)).filter(
        models.Expense.is_paid == True,
        models.Expense.paid_date >= month_start
    ).scalar() or 0.0

    return {
        "revenue_today":    round(revenue_today, 2),
        "expense_today":    round(expense_today, 2),
        "net_today":        round(revenue_today - expense_today, 2),
        "monthly_net":      round(month_revenue - month_expense, 2),
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
    set_tenant_context(db, admin.tenant_id)
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
# 11. EXPORTAÇÃO DE RELATÓRIO PDF (ELITE)
@router.get("/reports/export")
def export_financial_pdf(
    start: Optional[date] = None,
    end:   Optional[date] = None,
    mode:  str = Query("full", enum=["full", "summary"]),
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin),
    bg_tasks: BackgroundTasks = None
):
    set_tenant_context(db, admin.tenant_id)
    if not end: end = date.today()
    if not start: start = end - timedelta(days=29)

    start_dt = datetime.combine(start, datetime.min.time())
    end_dt   = datetime.combine(end,   datetime.max.time())

    # Coleta de Totais
    revs = db.query(models.Revenue).filter(
        models.Revenue.created_at >= start_dt,
        models.Revenue.created_at <= end_dt
    ).all()
    
    exps = db.query(models.Expense).filter(
        models.Expense.is_paid == True,
        models.Expense.paid_date >= start,
        models.Expense.paid_date <= end
    ).all()

    total_revenue = sum(r.amount for r in revs)
    total_expense = sum(e.amount for e in exps)
    total_discounts = sum(r.discount or 0.0 for r in revs) # Assume descontos registrados na receita
    
    # Listas detalhadas
    incomes_list = [{
        "data": r.created_at.strftime("%d/%m/%Y"),
        "desc": r.description,
        "cat": r.category.value if r.category else "Geral",
        "valor": r.amount,
        "desconto": r.discount or 0.0
    } for r in revs]

    outcomes_list = [{
        "data": e.paid_date.strftime("%d/%m/%Y") if e.paid_date else "-",
        "desc": e.description,
        "cat": e.category.value if e.category else "Geral",
        "metodo": "Transferência", # Ou buscar do campo se houver
        "valor": e.amount
    } for e in exps]

    # Categorização
    by_category = {}
    for r in revs:
        cat = r.category.value if r.category else "Geral"
        by_category[cat] = by_category.get(cat, 0) + r.amount
        
    expense_by_category = {}
    for e in exps:
        cat = e.category.value if e.category else "Geral"
        expense_by_category[cat] = expense_by_category.get(cat, 0) + e.amount

    # Timeline (Reutilizada da lógica de cash-flow)
    timeline = []
    cursor = start
    while cursor <= end:
        d_start = datetime.combine(cursor, datetime.min.time())
        d_end = datetime.combine(cursor, datetime.max.time())
        d_rev = sum(r.amount for r in revs if d_start <= r.created_at <= d_end)
        d_exp = sum(e.amount for e in exps if e.paid_date == cursor)
        timeline.append({
            "date": cursor.strftime("%d/%m/%Y"),
            "revenue": d_rev,
            "expense": d_exp,
            "net": d_rev - d_exp
        })
        cursor += timedelta(days=1)

    data = {
        "start": start.strftime("%d/%m/%Y"),
        "end": end.strftime("%d/%m/%Y"),
        "total_revenue": total_revenue,
        "total_expense": total_expense,
        "total_discounts": total_discounts,
        "incomes_list": incomes_list,
        "outcomes_list": outcomes_list,
        "by_category": by_category,
        "expense_by_category": expense_by_category,
        "timeline": timeline
    }

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"finance_exec_{ts}.pdf"
    path = generate_financial_report(data, filename, tenant_id=admin.tenant_id, mode=mode)

    def remove_file(path: str):
        try:
            if os.path.exists(path): os.remove(path)
        except Exception as e: print(f"Erro ao deletar relatório: {e}")

    if bg_tasks:
        bg_tasks.add_task(remove_file, path)
    
    return FileResponse(path, media_type="application/pdf", filename=filename)
def _period_summary(db: Session, start: date, end: date) -> dict:
    """Helper: calcula receita, despesa e KPIs de ocupação para um período rico."""
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt   = datetime.combine(end,   datetime.max.time())
    days = (end - start).days + 1

    # 1. Totais Básicos
    revenue = db.query(func.coalesce(func.sum(models.Revenue.amount), 0.0)).filter(
        models.Revenue.created_at >= start_dt, models.Revenue.created_at <= end_dt
    ).scalar() or 0.0

    expense = db.query(func.coalesce(func.sum(models.Expense.amount), 0.0)).filter(
        models.Expense.is_paid == True,
        models.Expense.paid_date >= start, models.Expense.paid_date <= end
    ).scalar() or 0.0

    # 2. Breakdowns (Receitas e Despesas por Categoria)
    rev_cats = db.query(models.Revenue.category, func.sum(models.Revenue.amount)).filter(
        models.Revenue.created_at >= start_dt, models.Revenue.created_at <= end_dt
    ).group_by(models.Revenue.category).all()
    by_category = {c.value: float(v) for c, v in rev_cats}

    exp_cats = db.query(models.Expense.category, func.sum(models.Expense.amount)).filter(
        models.Expense.is_paid == True,
        models.Expense.paid_date >= start, models.Expense.paid_date <= end
    ).group_by(models.Expense.category).all()
    expense_by_category = {c.value: float(v) for c, v in exp_cats}

    # 3. Meios de Pagamento
    pay_methods = db.query(models.Revenue.payment_method, func.sum(models.Revenue.amount)).filter(
        models.Revenue.created_at >= start_dt, models.Revenue.created_at <= end_dt
    ).group_by(models.Revenue.payment_method).all()
    by_payment = {p.value if p else 'quarto': float(v) for p, v in pay_methods}

    # 4. Mix de Produtos (Top Vendas do PDV)
    prod_mix = db.query(models.PDVSaleItem.product_name, func.sum(models.PDVSaleItem.quantity)).join(
        models.PDVSale
    ).filter(
        models.PDVSale.created_at >= start_dt, models.PDVSale.created_at <= end_dt
    ).group_by(models.PDVSaleItem.product_name).all()
    product_mix = {name: float(qty) for name, qty in prod_mix}

    # 5. Métricas de Ocupação e Hotelaria
    total_rooms = db.query(models.Room).count() or 1
    
    # Estimativa de booked_nights: soma de dias de estadias que interceptam o período
    # (Simplified: sum of nights for each booking within the range)
    # Using real_check_in/out if available, fallback to scheduled
    # For a high-fidelity X-ray, we count actual nights stayed within the window
    checkins = db.query(models.Booking).filter(
        models.Booking.real_check_in >= start_dt, models.Booking.real_check_in <= end_dt
    ).count()

    hospedagem_revenue = by_category.get('hospedagem', 0.0)
    
    # Cálculo de ADR e RevPAR
    # Para simplificar e manter performance, usaremos checkins como base de diárias se o hotel for rotativo
    # Ou calculamos a ocupação real via BookingRoom
    booked_rooms_count = db.query(func.count(models.BookingRoom.id)).join(models.Booking).filter(
        models.Booking.check_in_date <= end_dt,
        models.Booking.check_out_date >= start_dt,
        models.Booking.status.in_(['confirmado', 'ativo', 'concluido'])
    ).scalar() or 0
    
    occupancy_rate = (booked_rooms_count / (total_rooms * days)) * 100 if (total_rooms * days) > 0 else 0

    return {
        "start":     start.isoformat(),
        "end":       end.isoformat(),
        "days":      days,
        "revenue":   round(float(revenue), 2),
        "expense":   round(float(expense), 2),
        "net":       round(float(revenue) - float(expense), 2),
        "checkins":  checkins,
        "by_category": by_category,
        "expense_by_category": expense_by_category,
        "by_payment": by_payment,
        "product_mix": product_mix,
        "occupancy_rate": round(occupancy_rate, 1),
        "adr": round(hospedagem_revenue / max(checkins, 1), 2) if checkins > 0 else 0.0,
        "revpar": round(hospedagem_revenue / (total_rooms * days), 2) if (total_rooms * days) > 0 else 0.0,
        "ticket_medio": round(float(revenue) / max(checkins, 1), 2) if checkins > 0 else 0.0
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
    set_tenant_context(db, admin.tenant_id)
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
            "occupancy_rate":    delta(period_a["occupancy_rate"],    period_b["occupancy_rate"]),
            "adr":               delta(period_a["adr"],               period_b["adr"]),
            "revpar":            delta(period_a["revpar"],            period_b["revpar"]),
            "ticket_medio":      delta(period_a["ticket_medio"],      period_b["ticket_medio"]),
        }
    }

# =============================================================================
# FECHAMENTOS DE CAIXA (PDV)
# =============================================================================

@router.get("/caixa-closings", response_model=List[schemas.CaixaSessionResponse])
def list_caixa_closings(
    start: Optional[date] = None,
    end:   Optional[date] = None,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    """Lista sessões de caixa fechadas com resumos consolidados"""
    set_tenant_context(db, admin.tenant_id)
    query = db.query(models.CaixaSession).filter(
        models.CaixaSession.status == models.CaixaStatus.FECHADO
    )
    
    if start:
        query = query.filter(models.CaixaSession.closed_at >= datetime.combine(start, datetime.min.time()))
    if end:
        query = query.filter(models.CaixaSession.closed_at <= datetime.combine(end, datetime.max.time()))
        
    closings = query.order_by(desc(models.CaixaSession.closed_at)).all()
    
    # Injetar o nome do usuário manualmente para o schema response_model
    for c in closings:
        c.user_full_name = c.user.full_name or c.user.username if c.user else "N/A"
        
    return closings

# =============================================================================
# HISTÓRICO DE VENDAS (PDV)
# =============================================================================

@router.get("/pdv-sales", response_model=List[schemas.PDVSaleResponse])
def list_pdv_sales(
    start: Optional[date] = None,
    end:   Optional[date] = None,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    """Lista o histórico imutável de vendas do PDV"""
    set_tenant_context(db, admin.tenant_id)
    query = db.query(models.PDVSale)
    
    if start:
        query = query.filter(models.PDVSale.created_at >= datetime.combine(start, datetime.min.time()))
    if end:
        query = query.filter(models.PDVSale.created_at <= datetime.combine(end, datetime.max.time()))
        
    return query.order_by(desc(models.PDVSale.created_at)).all()

@router.get("/pdv-sales/{sale_id}", response_model=schemas.PDVSaleResponse)
def get_pdv_sale_detail(
    sale_id: int,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin)
):
    """Retorna os detalhes de uma venda específica (incluindo snapshot dos itens)"""
    set_tenant_context(db, admin.tenant_id)
    sale = db.query(models.PDVSale).filter(models.PDVSale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    return sale
