from fastapi import APIRouter, Depends, HTTPException
from .auth import get_current_admin

from sqlalchemy.orm import Session
from sqlalchemy import func, asc, desc
from datetime import date, datetime
from typing import Optional
import models, schemas
from database import get_db

router = APIRouter(prefix="/finance", tags=["Finance"])

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
    if end: query = query.filter(models.Revenue.created_at <= end)
    if category: query = query.filter(models.Revenue.category == category)
    if payment_method: query = query.filter(models.Revenue.payment_method == payment_method)
    if search:
        like = f"%{search.lower()}%"
        query = query.filter(models.Revenue.description.ilike(like))
    total_count = query.count()
    total = query.with_entities(func.coalesce(func.sum(models.Revenue.amount), 0.0)).scalar() or 0.0
    cats = query.with_entities(models.Revenue.category, func.sum(models.Revenue.amount)).group_by(models.Revenue.category).all()
    pays = query.with_entities(models.Revenue.payment_method, func.sum(models.Revenue.amount)).group_by(models.Revenue.payment_method).all()
    by_category = {c.value: float(v) for c, v in cats}
    by_payment = {p.value: float(v) for p, v in pays}
    sort_map = {
        "created_at": models.Revenue.created_at,
        "amount": models.Revenue.amount,
        "description": models.Revenue.description,
        "category": models.Revenue.category,
        "payment_method": models.Revenue.payment_method,
    }
    if sort_by in sort_map:
        col = sort_map[sort_by]
        query = query.order_by(desc(col) if sort_dir.lower() == "desc" else asc(col))
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)
    revenues = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total_revenue": total, 
        "transactions": total_count, 
        "data": revenues,
        "by_category": by_category,
        "by_payment_method": by_payment,
        "page": page,
        "page_size": page_size,
        "pages": (total_count // page_size) + (1 if total_count % page_size else 0)
    }

# 3. ATUALIZAR RECEITA
@router.put("/{revenue_id}", response_model=schemas.RevenueResponse)
def update_revenue(revenue_id: int, payload: schemas.RevenueUpdate, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    rev = db.query(models.Revenue).filter(models.Revenue.id == revenue_id).first()
    if not rev:
        raise HTTPException(status_code=404, detail="Receita não encontrada")
    if payload.description is not None: rev.description = payload.description
    if payload.amount is not None: rev.amount = payload.amount
    if payload.category is not None: rev.category = payload.category
    if payload.payment_method is not None: rev.payment_method = payload.payment_method
    if payload.booking_id is not None: rev.booking_id = payload.booking_id
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
